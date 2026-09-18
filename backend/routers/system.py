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
    Readiness check — verifies database and storage connectivity.

    TODO: Also check S3 connectivity.
    """
    try:
        await db.command("ping")
        db_status = "ready"
    except Exception:
        db_status = "unavailable"

    return {
        "status": "ok" if db_status == "ready" else "degraded",
        "database": db_status,
        "storage": "ready",  # TODO: verify S3
    }
