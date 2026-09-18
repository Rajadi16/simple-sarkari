"""
System routes — health checks and readiness probes.
"""

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from lib.db import get_db

router = APIRouter(tags=["system"])


@router.get("/health")
async def health():
    """Basic liveness check."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Readiness check — verifies MongoDB and S3 connectivity.

    Returns:
      status       — "ok" if all checks pass, "degraded" if any fail
      database     — "ready" | "unavailable"
      storage      — "s3" | "local" | "unavailable"
      s3_bucket    — bucket name when storage == "s3", null otherwise
    """
    # ── MongoDB ──
    try:
        await db.command("ping")
        db_status = "ready"
    except Exception:
        db_status = "unavailable"

    # ── S3 ──
    storage_status = "unavailable"
    s3_bucket = None
    try:
        from config import get_settings
        from lib.aws import get_s3_client
        settings = get_settings()
        # head_bucket is a lightweight auth+existence check (no data transferred)
        get_s3_client().head_bucket(Bucket=settings.s3_bucket)
        storage_status = "s3"
        s3_bucket = settings.s3_bucket
    except Exception:
        # Credentials missing or bucket unreachable — check local fallback
        from pathlib import Path
        local_data = Path(__file__).resolve().parent.parent / "data"
        if local_data.is_dir():
            storage_status = "local"
        # else stays "unavailable"

    overall = "ok" if db_status == "ready" and storage_status in ("s3", "local") else "degraded"

    return {
        "status": overall,
        "database": db_status,
        "storage": storage_status,
        "s3_bucket": s3_bucket,
    }
