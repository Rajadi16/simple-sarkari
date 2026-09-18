"""
System routes — health checks and readiness probes.
"""

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from config import get_settings
from lib.db import get_db
from lib.aws import check_s3_access

router = APIRouter(tags=["system"])


@router.get("/health")
async def health():
    """Basic liveness check."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Readiness check — verifies database and configured storage connectivity.
    """
    # ── MongoDB ──
    try:
        await db.command("ping")
        db_status = "ready"
    except Exception:
        db_status = "unavailable"

    settings = get_settings()
    if not settings.aws_enabled:
        storage_status = "disabled"
    else:
        try:
            await check_s3_access()
            storage_status = "ready"
        except Exception:
            storage_status = "unavailable"

    return {
        "status": "ok" if db_status == "ready" and storage_status in ("ready", "disabled") else "degraded",
        "database": db_status,
        "storage": storage_status,
    }
