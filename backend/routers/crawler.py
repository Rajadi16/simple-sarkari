"""
Crawler management routes — dedicated crawler-specific admin endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from lib.db import get_db
from lib.security import require_reviewer

router = APIRouter(prefix="/admin/crawler", tags=["crawler"], dependencies=[Depends(require_reviewer)])


@router.get("/status")
async def crawler_status(db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Get overall crawler system status.

    TODO: Return active/recent crawl runs, error rates, last run times per source.
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/runs")
async def list_crawl_runs(
    source_id: str | None = None,
    status: str | None = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    List recent crawl runs across all sources.

    TODO: Fetch from crawl_runs collection with optional filters.
    """
    raise HTTPException(status_code=501, detail="Not implemented")
