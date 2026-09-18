"""
Processing job routes — admin endpoints for monitoring background tasks.

All endpoints require reviewer authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from lib.db import get_db
from lib.security import require_reviewer
from lib.dates import utcnow

router = APIRouter(prefix="/admin/jobs", tags=["jobs"], dependencies=[Depends(require_reviewer)])


def _clean(doc: dict) -> dict:
    """Remove internal Mongo _id before returning to client."""
    doc.pop("_id", None)
    return doc


# ─── GET / — list jobs ────────────────────────────────────────────────────────

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
) -> dict:
    """List processing jobs with filters and pagination."""
    query: dict = {}
    if job_type:
        query["job_type"] = job_type
    if status:
        query["status"] = status
    if source_id:
        query["source_id"] = source_id
    if document_id:
        query["document_id"] = document_id
    if created_after or created_before:
        query["created_at"] = {}
        if created_after:
            query["created_at"]["$gte"] = created_after
        if created_before:
            query["created_at"]["$lte"] = created_before

    skip = (page - 1) * limit
    total = await db.jobs.count_documents(query)
    cursor = db.jobs.find(query).sort("created_at", -1).skip(skip).limit(limit)
    items = [_clean(doc) async for doc in cursor]

    return {"items": items, "total": total, "page": page, "limit": limit}


# ─── GET /{job_id} ────────────────────────────────────────────────────────────

@router.get("/{job_id}")
async def get_job(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Get a single job by ID."""
    doc = await db.jobs.find_one({"_id": job_id})
    if not doc:
        # Also check by the `id` field in case it was inserted without _id alignment
        doc = await db.jobs.find_one({"id": job_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return _clean(doc)


# ─── POST /{job_id}/retry ─────────────────────────────────────────────────────

@router.post("/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_job(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Retry a failed job.

    Resets status to 'pending' and increments the attempt counter.
    Re-enqueuing is handled by the worker polling this collection.
    """
    doc = await db.jobs.find_one({"_id": job_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    if doc.get("status") != "failed":
        raise HTTPException(
            status_code=409,
            detail=f"Only failed jobs can be retried — current status is '{doc.get('status')}'",
        )

    await db.jobs.update_one(
        {"_id": job_id},
        {
            "$set": {
                "status": "pending",
                "error_message": None,
                "started_at": None,
                "completed_at": None,
                "updated_at": utcnow().isoformat(),
            },
            "$inc": {"attempts": 1},
        },
    )
    return {"job_id": job_id, "status": "pending"}


# ─── POST /{job_id}/cancel ────────────────────────────────────────────────────

@router.post("/{job_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_job(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Cancel a pending or running job."""
    doc = await db.jobs.find_one({"_id": job_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    if doc.get("status") not in ("pending", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"Only pending or running jobs can be cancelled — current status is '{doc.get('status')}'",
        )

    await db.jobs.update_one(
        {"_id": job_id},
        {"$set": {"status": "cancelled", "updated_at": utcnow().isoformat()}},
    )
    return {"job_id": job_id, "status": "cancelled"}
