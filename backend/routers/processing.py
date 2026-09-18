"""
Processing job routes — admin endpoints for monitoring background tasks.

All endpoints require reviewer authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from lib.db import get_db
from lib.security import require_reviewer

router = APIRouter(prefix="/admin/jobs", tags=["jobs"], dependencies=[Depends(require_reviewer)])


@router.get("/")
async def list_jobs(
    job_type: str | None = Query(None, description="crawl | extraction | translation | audio"),
    status: str | None = Query(None, description="pending | running | completed | failed | cancelled"),
    source_id: str | None = Query(None),
    document_id: str | None = Query(None),
    created_after: str | None = Query(None, description="ISO datetime"),
    created_before: str | None = Query(None, description="ISO datetime"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    List processing jobs with filters and pagination.

    TODO: Build filter query, paginate, return results.
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{job_id}")
async def get_job(job_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Get a single job by ID.

    TODO: Fetch from DB, 404 if not found.
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{job_id}/retry")
async def retry_job(job_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Retry a failed job.

    TODO:
      1. Verify job exists and status is "failed"
      2. Reset status to "pending", increment attempts
      3. Re-enqueue background task
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Cancel a pending or running job.

    TODO: Set status to "cancelled".
    """
    raise HTTPException(status_code=501, detail="Not implemented")
