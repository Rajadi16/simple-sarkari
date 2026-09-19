"""
Provenance service — content hashing, raw-capture storage, deduplication.

Person 1 (Aditya) — Ingestion & Source Verification

Responsibilities:
  - sha256 content hash for duplicate detection
  - Store raw HTML/PDF exactly as fetched, key: raw/{id}/v{n}/original.{ext}
  - Prefer S3 (via lib/aws.py) when AWS credentials are configured;
    fall back to local disk under the same key structure so the pipeline
    works without AWS wired up.
  - Build the Provenance sub-object for CanonicalCircular
  - Duplicate check: returns True if content_hash already exists in Mongo

NOTE: lib/aws.py is Team 3's file. We call get_s3_client() / upload_to_s3()
from it rather than importing boto3 directly here.  If those symbols aren't
available (e.g. during isolated testing), we gracefully fall back to local
disk.  Team 3 may consolidate any minimal S3 helpers added here into
lib/aws.py later.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase

from config import get_settings
from lib.dates import utcnow
from models.circular import Provenance

# ─── Local storage root (mirrors S3 key structure) ───────────────────────────
# Resolved relative to the backend directory so it works regardless of CWD.
_LOCAL_DATA_ROOT = Path(__file__).resolve().parent.parent / "data"


def _local_path(key: str) -> Path:
    """Convert an S3-style key into a local filesystem path."""
    return _LOCAL_DATA_ROOT / key.replace("/", os.sep)


# ─── Content hashing ─────────────────────────────────────────────────────────

def compute_content_hash(raw_bytes: bytes) -> str:
    """Return 'sha256:<hex>' for the given raw bytes."""
    digest = hashlib.sha256(raw_bytes).hexdigest()
    return f"sha256:{digest}"


# ─── Duplicate detection ─────────────────────────────────────────────────────

async def is_duplicate(
    db: AsyncIOMotorDatabase,
    content_hash: str,
    source_reference_id: Optional[str] = None,
) -> bool:
    """
    Return True if a CanonicalCircular with this content_hash (or
    source_reference_id) already exists in the circulars collection.

    Checks content_hash first (reliable); then source_reference_id
    (faster for PIB PRID lookup as a secondary guard).
    """
    # Primary: exact content hash match
    existing = await db.circulars.find_one(
        {"provenance.content_hash": content_hash},
        projection={"_id": 1},
    )
    if existing:
        return True

    # Secondary: same source_reference_id (catches re-ingests of same PRID
    # even if the page content changed slightly, e.g. formatting tweaks)
    if source_reference_id:
        existing = await db.circulars.find_one(
            {"source.source_reference_id": source_reference_id},
            projection={"_id": 1},
        )
        if existing:
            return True

    return False


# ─── Raw capture storage ──────────────────────────────────────────────────────

async def store_raw(
    circular_id: str,
    raw_bytes: bytes,
    extension: str,        # "html" or "pdf"
    version: int = 1,
) -> tuple[str, bool]:
    """
    Persist the raw capture and return ``(key, is_s3_backed)``.

    Key format: raw/{circular_id}/v{version}/original.{extension}

    Tries S3 first; falls back to local disk if S3 is unavailable
    (missing credentials or boto3 error).  The key is the same either way,
    but ``is_s3_backed`` tells callers whether the file actually landed on S3
    so they can set ``provenance.is_s3_backed`` correctly.
    """
    key = f"raw/{circular_id}/v{version}/original.{extension}"
    content_type = "text/html" if extension == "html" else "application/pdf"

    if await _try_store_s3(key, raw_bytes, content_type):
        return key, True

    # Fall back to local disk
    _store_local(key, raw_bytes)
    return key, False


async def _try_store_s3(key: str, body: bytes, content_type: str) -> bool:
    """
    Attempt to upload to S3.  Returns True on success, False on any failure.
    Does NOT raise — callers fall back to local storage silently.
    """
    try:
        from lib.aws import upload_to_s3
        await upload_to_s3(key, body, content_type)
        return True
    except Exception:
        return False


def _store_local(key: str, body: bytes) -> None:
    """Write raw bytes to local disk, creating parent dirs as needed."""
    dest = _local_path(key)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)


async def retrieve_raw(key: str) -> bytes:
    """
    Retrieve a stored raw capture by its key.

    Tries S3 first; falls back to local disk.
    Raises FileNotFoundError if neither location has the file.
    """
    # Try S3
    try:
        from lib.aws import download_from_s3
        data = await download_from_s3(key)
        if data:
            return data
    except Exception:
        pass

    # Try local disk
    local = _local_path(key)
    if local.exists():
        return local.read_bytes()

    raise FileNotFoundError(f"Raw capture not found for key: {key}")


# ─── Provenance object builder ────────────────────────────────────────────────

def build_provenance(
    *,
    raw_bytes: bytes,
    retrieved_at: datetime,
    http_status: Optional[int],
    raw_html_s3_key: Optional[str] = None,
    raw_pdf_s3_key: Optional[str] = None,
    parser_name: Optional[str] = None,
    parser_version: Optional[str] = None,
    robots_checked: bool = True,
    terms_checked: bool = True,
    content_hash: Optional[str] = None,
) -> Provenance:
    """
    Build a Provenance sub-object from raw capture data.

    content_hash is computed here if not supplied.
    For the pasted-text path, pass raw_bytes=b"" and http_status=None.
    """
    if content_hash is None:
        content_hash = compute_content_hash(raw_bytes)

    return Provenance(
        retrieved_at=retrieved_at,
        retrieval_timezone="Asia/Kolkata",
        http_status=http_status,
        content_hash=content_hash,
        raw_html_s3_key=raw_html_s3_key,
        raw_pdf_s3_key=raw_pdf_s3_key,
        parser_name=parser_name,
        parser_version=parser_version,
        robots_checked=robots_checked,
        terms_checked=terms_checked,
    )


# ─── Persist CanonicalCircular to MongoDB ────────────────────────────────────

async def save_circular(
    db: AsyncIOMotorDatabase,
    circular,          # CanonicalCircular — avoid circular import with string annotation
) -> str:
    """
    Upsert a CanonicalCircular into the `circulars` collection.

    Uses circular.id as the _id for idempotent re-saves.
    Returns the circular id.
    """
    doc = circular.model_dump(mode="json")
    doc["_id"] = circular.id   # use our string ID as Mongo _id

    await db.circulars.replace_one(
        {"_id": circular.id},
        doc,
        upsert=True,
    )
    return circular.id


async def get_circular_by_id(
    db: AsyncIOMotorDatabase, circular_id: str
) -> Optional[dict]:
    """Fetch a circular document from MongoDB by its ID."""
    return await db.circulars.find_one({"_id": circular_id})


# ─── Audit event logging ─────────────────────────────────────────────────────

async def log_ingestion_event(
    db: AsyncIOMotorDatabase,
    *,
    event_type: str,
    circular_id: Optional[str],
    source_id: str,
    detail: dict | None = None,
) -> None:
    """
    Write a lightweight ingestion audit event to the audit_events collection.

    NOTE: Team 3 may define a richer log_event() in services/provenance_service.py
    or a dedicated audit service.  This is the minimal version for Person 1's
    pipeline; it writes to the same audit_events collection so both sides can
    read it.
    """
    event = {
        "event_type": event_type,
        "entity_type": "circular",
        "entity_id": circular_id,
        "source_id": source_id,
        "actor": "ingestion_pipeline",
        "detail": detail or {},
        "created_at": utcnow().isoformat(),
    }
    await db.audit_events.insert_one(event)
