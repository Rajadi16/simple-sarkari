"""
Source and crawler management routes — admin endpoints.

All endpoints require reviewer authentication.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from lib.db import get_db
from lib.security import require_reviewer
from models.source import Source, CrawlRunRequest

router = APIRouter(prefix="/admin", tags=["sources"], dependencies=[Depends(require_reviewer)])


# ─── Source CRUD ──────────────────────────────────────────────────────────────

@router.get("/sources")
async def list_sources(db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    List all registered sources.

    TODO: Fetch all from sources collection, return list.
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/sources/{source_id}")
async def get_source(source_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Get a single source by ID.

    TODO: Fetch from DB, 404 if not found.
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/sources")
async def create_source(source: Source, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Add a new source to the registry.

    TODO: Validate, insert, return created source.
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.patch("/sources/{source_id}")
async def update_source(source_id: str, updates: dict, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Partially update a source configuration.

    TODO: Validate updates, apply $set, return updated source.
    """
    raise HTTPException(status_code=501, detail="Not implemented")


# ─── Crawler ──────────────────────────────────────────────────────────────────

@router.post("/sources/{source_id}/crawl")
async def trigger_crawl(
    source_id: str,
    body: CrawlRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Trigger a crawler run for the given source.

    Runs as a background task. Returns a run ID for status polling.

    TODO:
      1. Verify source exists and is enabled
      2. Create crawl_run record
      3. Enqueue background task (crawler_service.run_crawl)
      4. Return {"run_id": ..., "status": "pending"}
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/crawl-runs/{run_id}")
async def get_crawl_run(run_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Get the status of a crawl run.

    TODO: Fetch from DB, return CrawlRun.
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/sources/{source_id}/telemetry")
async def get_source_telemetry(source_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Get crawl telemetry for a source (recent runs, success rates, document counts).

    TODO: Aggregate recent crawl_runs for the source.
    """
    raise HTTPException(status_code=501, detail="Not implemented")
