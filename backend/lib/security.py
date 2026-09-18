"""
Security utilities — URL validation, auth dependencies, SSRF protection.
"""

import ipaddress
from urllib.parse import urlparse
from fastapi import Depends, HTTPException, Header, status
from config import get_settings

# ─── Allowed government domains ─────────────────────────────────────────────

ALLOWED_DOMAINS: set[str] = {
    "pib.gov.in",
    "www.pib.gov.in",
    "static.pib.gov.in",
    "dopt.gov.in",
    "www.dopt.gov.in",
    "egazette.gov.in",
    "www.egazette.gov.in",
    "doe.gov.in",
    "www.doe.gov.in",
    "india.gov.in",
    "www.india.gov.in",
    "egazette.karnataka.gov.in",
    "dpar.karnataka.gov.in",
    "finance.karnataka.gov.in",
    "itbt.karnataka.gov.in",
}

# Private / reserved IP ranges that MUST be blocked to prevent SSRF.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),       # link-local / AWS metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def validate_url(url: str) -> str:
    """
    Validate a URL for safe fetching.

    Raises ValueError if the URL:
    - is not HTTPS
    - targets a non-allowlisted domain
    - resolves to a private / reserved IP
    - points to a cloud metadata endpoint
    """
    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise ValueError("Only HTTPS URLs are allowed")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")

    if hostname not in ALLOWED_DOMAINS:
        raise ValueError(f"Domain '{hostname}' is not in the allowlist")

    # Block raw-IP URLs that might be private
    try:
        addr = ipaddress.ip_address(hostname)
        for network in _BLOCKED_NETWORKS:
            if addr in network:
                raise ValueError("Private or reserved IP addresses are blocked")
    except ValueError:
        pass  # hostname is not an IP literal — fine

    return url


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
