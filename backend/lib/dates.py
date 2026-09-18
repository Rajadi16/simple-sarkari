"""
Date parsing and timezone utilities for Indian government documents.

Government dates appear in many formats — DD/MM/YYYY, DD-MM-YYYY,
DD.MM.YYYY, "1st January 2025", etc.  Helpers here normalize to UTC
datetime objects with IST awareness.
"""

from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

# Common Indian government date formats — extend as needed.
_FORMATS = [
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y-%m-%d",
    "%d %B %Y",
    "%d %B, %Y",
    "%B %d, %Y",
    "%d-%b-%Y",
    "%d %b %Y",
]


def parse_indian_date(text: str) -> datetime | None:
    """
    Try common Indian date formats and return an IST-aware datetime,
    or None if no format matches.
    """
    cleaned = text.strip()
    for fmt in _FORMATS:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.replace(tzinfo=IST)
        except ValueError:
            continue
    return None


def utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def ist_now() -> datetime:
    """Return the current IST time as a timezone-aware datetime."""
    return datetime.now(IST)
