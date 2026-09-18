"""
Sources and crawler management routes — admin endpoints.

Person 1 (Aditya) — Ingestion & Source Verification

Endpoints:
  GET  /api/admin/sources                    — list all sources
  GET  /api/admin/sources/{source_id}        — get one source
  POST /api/admin/sources                    — add a source
  PATCH /api/admin/sources/{source_id}       — update source config
  POST /api/admin/sources/{source_id}/crawl  — trigger a crawl run
  GET  /api/admin/crawl-runs/{run_id}        — crawl run status
  GET  /api/admin/sources/{source_id}/telemetry — recent run stats

All endpoints require Bearer token auth.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from lib.db import get_db
from lib.security import require_reviewer
from lib.dates import utcnow
from models.source import Source, CrawlRun, CrawlRunRequest
from workers.ingestion_worker import process_crawl_run

router = APIRouter(
    prefix="/admin",
    tags=["sources"],
    dependencies=[Depends(require_reviewer)],
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _strip_id(doc: dict) -> dict:
    """Remove Mongo _id from a document dict before returning to client."""
    doc.pop("_id", None)
    return doc


async def _get_source_or_404(db: AsyncIOMotorDatabase, source_id: str) -> dict:
    doc = await db.sources.find_one({"source_id": source_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_id}' not found",
        )
    return _strip_id(doc)


# ─── Source CRUD ──────────────────────────────────────────────────────────────

@router.get("/sources")
async def list_sources(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> list[dict]:
    """Return all registered sources, sorted by name."""
    cursor = db.sources.find({}, {"_id": 0}).sort("name", 1)
    return [doc async for doc in cursor]


@router.get("/sources/{source_id}")
async def get_source(
    source_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Get a single source by source_id."""
    return await _get_source_or_404(db, source_id)


@router.post("/sources", status_code=status.HTTP_201_CREATED)
async def create_source(
    source: Source,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Register a new source in the registry.

    source_id must be unique. Returns 409 if already exists.
    """
    existing = await db.sources.find_one({"source_id": source.source_id})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Source '{source.source_id}' already exists",
        )

    doc = source.model_dump(mode="json")
    doc["_id"] = source.source_id
    await db.sources.insert_one(doc)
    return _strip_id(doc)


@router.patch("/sources/{source_id}")
async def update_source(
    source_id: str,
    updates: dict[str, Any],
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Partially update a source configuration.

    Accepts any subset of Source fields. source_id is immutable.
    Returns the updated document.
    """
    await _get_source_or_404(db, source_id)   # 404 if not found

    # Prevent changing the identity
    updates.pop("source_id", None)
    updates.pop("_id", None)
    updates["updated_at"] = utcnow().isoformat()

    await db.sources.update_one(
        {"source_id": source_id},
        {"$set": updates},
    )
    return await _get_source_or_404(db, source_id)


# ─── Crawl trigger ────────────────────────────────────────────────────────────

@router.post("/sources/{source_id}/crawl", status_code=status.HTTP_202_ACCEPTED)
async def trigger_crawl(
    source_id: str,
    body: CrawlRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Trigger a crawler run for the given source.

    Validates:
      - Source exists and status == 'active'
      - crawl_policy.enabled == true

    Runs as a BackgroundTask. Returns run_id immediately for polling.
    """
    source_doc = await _get_source_or_404(db, source_id)

    if source_doc.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Source '{source_id}' is not active (status='{source_doc.get('status')}')",
        )

    crawl_policy = source_doc.get("crawl_policy", {})
    if not crawl_policy.get("enabled", True):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Crawling is disabled for source '{source_id}' (crawl_policy.enabled=false)",
        )

    # Create the run record
    from services.crawler_service import _create_crawl_run
    run = await _create_crawl_run(db, source_id)

    background_tasks.add_task(
        process_crawl_run,
        db=db,
        run_id=run.id,
        source_id=source_id,
        max_pages=body.max_pages,
        max_documents=body.max_documents,
    )

    return {"run_id": run.id, "status": "pending"}


# ─── Crawl run status ─────────────────────────────────────────────────────────

@router.get("/crawl-runs/{run_id}")
async def get_crawl_run(
    run_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Get the status and telemetry for a specific crawl run.

    Status values: pending | running | completed | failed
    """
    doc = await db.crawl_runs.find_one({"_id": run_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crawl run '{run_id}' not found",
        )
    return _strip_id(doc)


# ─── Source telemetry ─────────────────────────────────────────────────────────

@router.get("/sources/{source_id}/telemetry")
async def get_source_telemetry(
    source_id: str,
    limit: int = 10,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Telemetry summary for a source: recent crawl runs + document counts.

    Returns:
      - recent_runs: last `limit` crawl runs (newest first)
      - total_circulars: total docs ingested from this source
      - extracted_count: docs with status='extracted'
      - manual_review_count: docs needing manual attention
      - last_run_at: timestamp of the most recent completed run
    """
    await _get_source_or_404(db, source_id)   # 404 guard

    # Recent crawl runs
    cursor = (
        db.crawl_runs
        .find({"source_id": source_id}, {"_id": 0})
        .sort("started_at", -1)
        .limit(limit)
    )
    recent_runs = [doc async for doc in cursor]

    # Circular counts
    total = await db.circulars.count_documents({"source.source_id": source_id})
    extracted = await db.circulars.count_documents({
        "source.source_id": source_id,
        "processing.status": "extracted",
    })
    manual_review = await db.circulars.count_documents({
        "source.source_id": source_id,
        "processing.status": "manual_review_required",
    })

    last_run_at: Optional[str] = None
    if recent_runs:
        last_run_at = recent_runs[0].get("completed_at") or recent_runs[0].get("started_at")

    return {
        "source_id": source_id,
        "total_circulars": total,
        "extracted_count": extracted,
        "manual_review_count": manual_review,
        "last_run_at": last_run_at,
        "recent_runs": recent_runs,
    }
