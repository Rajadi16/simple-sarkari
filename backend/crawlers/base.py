"""
Base crawler adapter — every source-specific adapter inherits from this.

Person 1 (Aditya) — Ingestion & Source Verification

Provides respectful crawling primitives:
  - HTTPS-only fetching via httpx
  - Domain allowlist enforcement (lib/security.validate_url)
  - robots.txt checking before every fetch (lib/security.check_robots_txt)
  - ETag / Last-Modified caching to avoid re-fetching unchanged pages
  - Configurable per-domain request delay (~1 req / several seconds)
  - Request timeout + max response-size cap
  - Descriptive User-Agent from config
  - Hard stop on 403, 429, CAPTCHA / login redirect, WAF block —
    no retry, no stealth tricks; caller receives a blocked FetchResult
    and should write processing.status = "manual_review_required"
"""

from __future__ import annotations

import abc
import asyncio
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse, urljoin

import httpx

from config import get_settings
from lib.security import validate_url, check_robots_txt
from lib.dates import utcnow
from models.circular import CandidateDocument, CanonicalCircular
from crawlers.source_config import normalize_source_config


# ─── ETag / Last-Modified cache ──────────────────────────────────────────────
# Maps URL → {"etag": str | None, "last_modified": str | None}
_etag_cache: dict[str, dict] = {}


@dataclass
class FetchResult:
    """
    Result of fetching a single URL.

    `blocked` is True when the source actively rejected the request
    (403, 429, CAPTCHA, login redirect, WAF). The caller must NOT retry;
    it should record `block_reason` and mark the document
    processing.status = "manual_review_required".

    `not_modified` is True when the server returned 304 — content unchanged,
    skip re-processing.
    """
    url: str
    status_code: int
    content_type: str | None = None
    body: bytes = b""
    content_hash: str | None = None
    etag: str | None = None
    last_modified: str | None = None

    # Failure flags — mutually exclusive with a valid body
    blocked: bool = False
    block_reason: str | None = None      # "403_forbidden" | "429_rate_limited" |
                                          # "captcha_challenge" | "login_redirect" |
                                          # "waf_block" | "robots_disallowed" |
                                          # "domain_not_allowed" | "network_error"
    not_modified: bool = False           # True → 304; use cached content

    # Preserve the transport failure for diagnostics instead of guessing its cause.
    error_detail: str | None = None

    fetched_at: datetime = field(default_factory=utcnow)


def _detect_block(resp: httpx.Response) -> str | None:
    """
    Heuristic detection of soft blocks that don't surface as 403/429.

    Returns a block reason string, or None if the response looks legitimate.

    IMPORTANT: Be conservative — only flag pages that are clearly challenge/block
    pages, not legitimate pages that happen to reference CDN or security services
    in their HTML (e.g. cdnjs.cloudflare.com as a CSS/JS CDN is NOT a block).
    """
    url_lower = str(resp.url).lower()
    text_lower = resp.text[:4096].lower() if resp.content else ""

    # Login / auth redirect
    if resp.status_code in (301, 302, 307, 308):
        location = resp.headers.get("location", "").lower()
        if any(kw in location for kw in ("login", "signin", "auth", "captcha")):
            return "login_redirect"

    # Cloudflare challenge: must have challenge-specific markers, NOT just a CDN reference.
    # Real CF challenge pages have ray IDs, challenge forms, or specific title text.
    # Sites using cdnjs.cloudflare.com for CSS/JS are legitimate — do NOT flag those.
    cf_challenge_signals = (
        "just a moment",                    # CF "Just a moment..." title
        "enable javascript and cookies",    # CF JS challenge body text
        "checking your browser",            # CF browser check text
        "challenge-form",                   # CF challenge form id
        "cf-please-wait",                   # CF spinner div
        "ray id",                           # CF Ray-ID footer (only in challenge pages)
        "__cf_bm",                          # CF bot management cookie name in page
    )
    if any(sig in text_lower for sig in cf_challenge_signals):
        return "captcha_challenge"

    # CAPTCHA pages (non-CF)
    captcha_signals = (
        "captcha",
        "are you human",
        "bot check",
        "verify you are human",
        "ddos-guard",
    )
    if any(sig in text_lower for sig in captcha_signals):
        return "captcha_challenge"

    # WAF JSON / HTML block pages (status 200 with rejection body)
    if resp.status_code == 200:
        waf_signals = (
            "request rejected",             # F5/Imperva WAF
            "this request has been blocked", # generic WAF
            "access denied by policy",      # policy block
        )
        if any(sig in text_lower for sig in waf_signals):
            return "waf_block"

    return None


class BaseCrawlerAdapter(abc.ABC):
    """
    Abstract base for all source-specific adapters.

    Subclasses must implement:
      - fetch_listing()  → list[CandidateDocument]
      - fetch_detail(candidate) → FetchResult
      - parse(candidate, fetch_result) → CanonicalCircular

    Subclasses may override `fetch()` only for sources that need POST-based
    pagination or non-standard auth — never to bypass safety checks.
    """

    # Subclasses declare these
    PARSER_NAME: str = "base"
    PARSER_VERSION: str = "1.0.0"

    def __init__(self, source_config: dict) -> None:
        self.source = normalize_source_config(source_config)
        self.settings = get_settings()
        self._client: httpx.AsyncClient | None = None
        # Per-instance delay tracking: domain → last fetch monotonic time
        self._last_fetch: dict[str, float] = {}
        # Metadata only: never retain PDF/HTML bodies in telemetry.
        self.fetch_events: list[dict] = []
        self._halted: FetchResult | None = None

    def listing_urls(self, defaults: list[str] | None = None) -> list[str]:
        """Apply the configured page budget to every adapter's seed loop."""
        limit = self.source.get("max_pages_per_run", 10)
        if limit < 1:
            raise ValueError("max_pages_per_run must be positive")
        return self.source.get("seed_urls", defaults or [])[:limit]

    def invalidate_fetch_cache(self) -> None:
        """A later, explicit retry must not skip documents from a failed run."""
        for event in self.fetch_events:
            _etag_cache.pop(event["url"], None)

    # ─── HTTP client lifecycle ────────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-create a shared async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": self.settings.crawler_user_agent},
                timeout=httpx.Timeout(self.settings.crawler_request_timeout_seconds),
                follow_redirects=True,
                max_redirects=5,
            )
        return self._client

    async def close(self) -> None:
        """Release HTTP client resources."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ─── Rate limiting ────────────────────────────────────────────────────

    async def _respect_delay(self, url: str) -> None:
        """Sleep if needed to honour the configured per-domain request delay."""
        import time
        domain = urlparse(url).hostname or url
        delay = self.source.get("request_delay_seconds",
                                self.settings.crawler_default_delay_seconds)
        last = self._last_fetch.get(domain, 0.0)
        elapsed = time.monotonic() - last
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._last_fetch[domain] = time.monotonic()

    # ─── Core fetch ───────────────────────────────────────────────────────

    async def fetch(self, url: str) -> FetchResult:
        """Record fetch outcomes and stop this run after an access rejection."""
        if self._halted is not None:
            return FetchResult(
                url=url, status_code=0, blocked=True,
                block_reason="run_stopped",
                error_detail=f"Stopped after {self._halted.block_reason} at {self._halted.url}",
            )
        result = await self._fetch(url)
        self.fetch_events.append({
            "url": url, "http_status": result.status_code,
            "reason": result.block_reason, "error_detail": result.error_detail,
            "blocked": result.blocked, "not_modified": result.not_modified,
        })
        if result.block_reason in {
            "403_forbidden", "429_rate_limited", "captcha_challenge",
            "login_redirect", "waf_block", "robots_disallowed",
        }:
            self._halted = result
        return result

    async def _fetch(self, url: str) -> FetchResult:
        """
        Fetch a single URL with all safety checks applied.

        Order of checks:
          1. validate_url  — HTTPS + allowlist + SSRF guard
          2. check_robots_txt — stop if disallowed
          3. rate delay
          4. ETag/Last-Modified conditional GET
          5. Size cap
          6. Hard stop on 403/429/soft-block signals
        """
        # 1. Domain / HTTPS / SSRF validation
        try:
            validate_url(url)
        except ValueError as exc:
            return FetchResult(url=url, status_code=0,
                               blocked=True, block_reason="domain_not_allowed",
                               body=b"", content_hash=None, error_detail=str(exc))

        # 2. robots.txt check
        if self.source.get("respect_robots", True):
            allowed = await check_robots_txt(url, self.settings.crawler_user_agent)
            if not allowed:
                return FetchResult(url=url, status_code=0,
                                   blocked=True, block_reason="robots_disallowed",
                                   body=b"", content_hash=None)

        # 3. Polite delay
        await self._respect_delay(url)

        # 4. Build conditional GET headers from cache
        headers: dict[str, str] = {}
        cached = _etag_cache.get(url, {})
        if cached.get("etag"):
            headers["If-None-Match"] = cached["etag"]
        if cached.get("last_modified"):
            headers["If-Modified-Since"] = cached["last_modified"]

        client = await self._get_client()
        try:
            resp = await client.get(url, headers=headers)
        except httpx.RemoteProtocolError:
            # Server closed the keep-alive connection — retry once with a fresh client
            await self.close()  # force client recreation
            client = await self._get_client()
            try:
                resp = await client.get(url, headers=headers)
            except Exception as exc2:
                return FetchResult(url=url, status_code=0,
                                   blocked=True, block_reason="network_error",
                                   body=b"", content_hash=None,
                                   error_detail=f"{type(exc2).__name__}: {exc2}")
        except Exception as exc:
            return FetchResult(url=url, status_code=0,
                               blocked=True, block_reason="network_error",
                               body=b"", content_hash=None,
                               error_detail=f"{type(exc).__name__}: {exc}")
        # 4b. 304 Not Modified
        if resp.status_code == 304:
            return FetchResult(url=url, status_code=304, not_modified=True,
                               body=b"", content_hash=None)

        # 5. Hard stop on explicit rejection codes — no retry
        if resp.status_code == 403:
            return FetchResult(url=url, status_code=403,
                               blocked=True, block_reason="403_forbidden",
                               body=b"", content_hash=None)
        if resp.status_code == 429:
            return FetchResult(url=url, status_code=429,
                               blocked=True, block_reason="429_rate_limited",
                               body=b"", content_hash=None)

        # 5b. Soft-block detection (CAPTCHA, login redirect, WAF)
        soft_block = _detect_block(resp)
        if soft_block:
            return FetchResult(url=url, status_code=resp.status_code,
                               blocked=True, block_reason=soft_block,
                               body=b"", content_hash=None)

        if not 200 <= resp.status_code < 300:
            return FetchResult(url=url, status_code=resp.status_code,
                               blocked=True, block_reason="http_error",
                               error_detail=f"HTTP {resp.status_code}")

        # 6. Size cap
        max_bytes = self.settings.crawler_max_page_size_mb * 1024 * 1024
        content_type = resp.headers.get("content-type", "")
        if "pdf" in content_type:
            max_bytes = self.settings.crawler_max_pdf_size_mb * 1024 * 1024
        body = resp.content
        if len(body) > max_bytes:
            return FetchResult(url=url, status_code=resp.status_code,
                               blocked=True, block_reason="response_too_large",
                               body=b"", content_hash=None)

        # Update ETag cache
        etag = resp.headers.get("etag")
        last_modified = resp.headers.get("last-modified")
        if etag or last_modified:
            _etag_cache[url] = {"etag": etag, "last_modified": last_modified}

        content_hash = "sha256:" + hashlib.sha256(body).hexdigest()
        return FetchResult(
            url=url,
            status_code=resp.status_code,
            content_type=content_type,
            body=body,
            content_hash=content_hash,
            etag=etag,
            last_modified=last_modified,
        )

    # ─── URL utilities ────────────────────────────────────────────────────

    def canonicalize_url(self, url: str, base: str | None = None) -> str:
        """Resolve relative URLs and strip fragments."""
        if base:
            url = urljoin(base, url)
        parsed = urlparse(url)
        return parsed._replace(fragment="").geturl()

    def is_allowed_domain(self, url: str) -> bool:
        """Check if URL belongs to one of the source's allowed domains."""
        hostname = urlparse(url).hostname
        return hostname in self.source.get("base_domains", [])

    @staticmethod
    def compute_hash(content: bytes) -> str:
        return "sha256:" + hashlib.sha256(content).hexdigest()

    # ─── Abstract interface — implement in each adapter ───────────────────

    @abc.abstractmethod
    async def fetch_listing(self) -> list[CandidateDocument]:
        """
        Crawl the source's listing/seed page(s) and return discovered
        CandidateDocuments. Must not fetch detail pages.
        """
        ...

    @abc.abstractmethod
    async def fetch_detail(self, candidate: CandidateDocument) -> FetchResult:
        """
        Fetch the full detail page for a candidate.
        Returns a FetchResult (may be blocked — check .blocked).
        """
        ...

    @abc.abstractmethod
    async def parse(
        self, candidate: CandidateDocument, result: FetchResult
    ) -> CanonicalCircular:
        """
        Parse a successfully fetched detail page / PDF and return a
        CanonicalCircular ready for storage.
        Only called when result.blocked is False.
        """
        ...
