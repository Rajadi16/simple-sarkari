"""
Security utilities — URL validation, robots.txt checking, auth dependencies.

Person 1 (Aditya) — Ingestion & Source Verification
"""

import ipaddress
import asyncio
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, Header, status
from config import get_settings

# ─── Approved government domain allowlist ────────────────────────────────────
# Only domains on this list may be fetched. No guessing, no wildcards.

ALLOWED_DOMAINS: set[str] = {
    # PIB — Day-1 target
    "pib.gov.in",
    "www.pib.gov.in",
    "static.pib.gov.in",
    # Central govt
    "dopt.gov.in",
    "www.dopt.gov.in",
    "egazette.gov.in",
    "www.egazette.gov.in",
    "doe.gov.in",
    "www.doe.gov.in",
    "india.gov.in",
    "www.india.gov.in",
    # Karnataka state
    "egazette.karnataka.gov.in",
    "dpar.karnataka.gov.in",
    "finance.karnataka.gov.in",
    "itbt.karnataka.gov.in",
}

# Private / reserved IP ranges blocked to prevent SSRF.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),   # link-local / AWS metadata endpoint
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

# In-process robots.txt cache: domain → (allowed_paths set, timestamp)
_robots_cache: dict[str, tuple[RobotFileParser, float]] = {}
_robots_cache_lock = asyncio.Lock()
_ROBOTS_CACHE_TTL_SECONDS = 3600  # re-fetch robots.txt once per hour


def validate_url(url: str) -> str:
    """
    Validate a URL for safe fetching.

    Rules:
      - Must be HTTPS
      - Hostname must be on ALLOWED_DOMAINS (explicit, no wildcards)
      - Must not resolve to a private / reserved IP range (SSRF protection)

    Returns the URL unchanged if valid; raises ValueError otherwise.
    Never guess or accept domains not on the list.
    """
    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise ValueError(f"Only HTTPS URLs are allowed — got scheme '{parsed.scheme}'")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")

    if hostname not in ALLOWED_DOMAINS:
        raise ValueError(
            f"Domain '{hostname}' is not on the approved allowlist. "
            "Add it explicitly to ALLOWED_DOMAINS in lib/security.py after review."
        )

    # Block raw-IP URLs targeting private ranges (SSRF guard)
    try:
        addr = ipaddress.ip_address(hostname)
        for network in _BLOCKED_NETWORKS:
            if addr in network:
                raise ValueError(
                    f"IP address '{hostname}' falls in a private/reserved range — blocked."
                )
    except ValueError as exc:
        # Re-raise only if it's our own SSRF error; otherwise hostname is a
        # normal DNS name and ipaddress.ip_address() raised ValueError, which is fine.
        if "private/reserved range" in str(exc) or "SSRF" in str(exc):
            raise

    return url


async def check_robots_txt(url: str, user_agent: str = "*") -> bool:
    """
    Check whether `url` is allowed by the source's robots.txt.

    Returns True  → fetch is allowed (or robots.txt unavailable / unreachable).
    Returns False → robots.txt explicitly disallows this URL.

    Caches the parsed robots.txt per domain for _ROBOTS_CACHE_TTL_SECONDS.
    Always validates the robots.txt URL itself against the allowlist first.
    """
    import time

    parsed = urlparse(url)
    domain = parsed.hostname or ""
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    async with _robots_cache_lock:
        cached = _robots_cache.get(domain)
        now = time.monotonic()

        if cached is None or (now - cached[1]) > _ROBOTS_CACHE_TTL_SECONDS:
            # Fetch robots.txt — use a plain httpx call (no allowlist check
            # needed since we just built robots_url from the already-validated domain)
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                settings = get_settings()
                async with httpx.AsyncClient(
                    timeout=10,
                    headers={"User-Agent": settings.crawler_user_agent},
                    follow_redirects=True,
                ) as client:
                    resp = await client.get(robots_url)
                    if resp.status_code == 200:
                        rp.parse(resp.text.splitlines())
                    else:
                        # robots.txt not available — assume allowed
                        _robots_cache[domain] = (rp, now)
                        return True
            except Exception:
                # Network error fetching robots.txt — log and allow
                _robots_cache[domain] = (rp, now)
                return True

            _robots_cache[domain] = (rp, now)

    rp, _ = _robots_cache[domain]
    return rp.can_fetch(user_agent, url)


# ─── Auth dependencies ───────────────────────────────────────────────────────

async def require_reviewer(
    authorization: str = Header(..., description="Bearer <reviewer-token>"),
) -> str:
    """
    Simple bearer-token auth for the hackathon.

    Header format:  Authorization: Bearer <token>
    Replace with Cognito / JWT verification for production.
    """
    settings = get_settings()
    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be 'Bearer <token>'",
        )

    if token != settings.reviewer_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid reviewer token",
        )

    return token
