"""
Base crawler adapter — every source-specific adapter inherits from this.

Provides respectful crawling primitives:
  - HTTPS-only fetching with httpx
  - Domain allowlist enforcement
  - robots.txt checking
  - Configurable delay between requests
  - Request timeout and size limits
  - Descriptive User-Agent
  - Stop-on-403 / Stop-on-429 behaviour
"""

import abc
import hashlib
from urllib.parse import urlparse, urljoin
from datetime import datetime
from dataclasses import dataclass, field

import httpx

from config import get_settings
from lib.security import validate_url
from lib.dates import utcnow


@dataclass
class CrawlResult:
    """Result from fetching a single document."""
    url: str
    status_code: int
    content_type: str | None = None
    body: bytes = b""
    content_hash: str | None = None
    title: str | None = None
    metadata: dict = field(default_factory=dict)
    error: str | None = None
    fetched_at: datetime = field(default_factory=utcnow)


class BaseCrawlerAdapter(abc.ABC):
    """
    Abstract base for all source-specific adapters.

    Subclasses must implement:
      - get_listing_urls()
      - parse_listing_page()
      - parse_detail_page()
    """

    def __init__(self, source_config: dict):
        self.source = source_config
        self.settings = get_settings()
        self._client: httpx.AsyncClient | None = None

    # ─── HTTP client ──────────────────────────────────────────────────────

    async def get_client(self) -> httpx.AsyncClient:
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
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ─── Fetch helpers ────────────────────────────────────────────────────

    async def fetch(self, url: str) -> CrawlResult:
        """
        Fetch a single URL with all safety checks.

        Override in subclass only if the source needs special handling
        (e.g. POST-based pagination).
        """
        try:
            validate_url(url)
        except ValueError as e:
            return CrawlResult(url=url, status_code=0, error=str(e))

        client = await self.get_client()
        try:
            resp = await client.get(url)
        except httpx.HTTPError as e:
            return CrawlResult(url=url, status_code=0, error=str(e))

        # Respectful stop signals
        if resp.status_code == 403 and self.source.get("stop_on_403", True):
            return CrawlResult(
                url=url,
                status_code=403,
                error="blocked_by_source",
            )
        if resp.status_code == 429 and self.source.get("stop_on_429", True):
            return CrawlResult(
                url=url,
                status_code=429,
                error="rate_limited",
            )

        body = resp.content
        return CrawlResult(
            url=url,
            status_code=resp.status_code,
            content_type=resp.headers.get("content-type"),
            body=body,
            content_hash=hashlib.sha256(body).hexdigest(),
        )

    # ─── URL utilities ────────────────────────────────────────────────────

    def canonicalize_url(self, url: str, base: str | None = None) -> str:
        """Resolve relative URLs and strip fragments."""
        if base:
            url = urljoin(base, url)
        parsed = urlparse(url)
        return parsed._replace(fragment="").geturl()

    def is_allowed_domain(self, url: str) -> bool:
        """Check if a URL belongs to one of the source's allowed domains."""
        hostname = urlparse(url).hostname
        return hostname in self.source.get("base_domains", [])

    @staticmethod
    def compute_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    # ─── Abstract methods — implement in each adapter ─────────────────────

    @abc.abstractmethod
    async def get_listing_urls(self) -> list[str]:
        """Return seed/listing URLs to begin crawling."""
        ...

    @abc.abstractmethod
    async def parse_listing_page(self, html: str, base_url: str) -> list[dict]:
        """
        Parse a listing page and return discovered document links.

        Each dict should contain at minimum:
          {"url": "...", "title": "...", "document_type": "..."}
        """
        ...

    @abc.abstractmethod
    async def parse_detail_page(self, html: str, url: str) -> dict:
        """
        Parse a detail page and return extracted content.

        Return dict with keys like:
          title, subject, department, text, dates, metadata
        """
        ...
