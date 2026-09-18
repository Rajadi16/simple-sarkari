"""
Ingestion routes — internal team endpoints for manual document ingestion.

All endpoints require reviewer authentication.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from motor.motor_asyncio import AsyncIOMotorDatabase

from lib.db import get_db
from lib.security import require_reviewer

router = APIRouter(prefix="/admin/ingestions", tags=["ingestion"], dependencies=[Depends(require_reviewer)])


# ─── Request models ───────────────────────────────────────────────────────────

class UrlIngestionRequest(BaseModel):
    url: str
    source_id: str


class TextIngestionRequest(BaseModel):
    title: str
    publisher: str
    source_url: str
    original_language: str = "en-IN"
    text: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/url")
async def ingest_url(
    body: UrlIngestionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Trigger ingestion of a document from a URL.

    Runs as a background task. Returns an ingestion ID for status polling.

    TODO:
      1. Create ingestion record in DB
      2. Enqueue background task (ingestion_worker.process_url_ingestion)
      3. Return {"ingestion_id": ..., "status": "queued"}
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/text")
async def ingest_text(
    body: TextIngestionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Ingest pasted government text directly.

    TODO:
      1. Create ingestion record
      2. Create circular from text
      3. Enqueue AI processing
      4. Return {"ingestion_id": ..., "status": "queued"}
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{ingestion_id}")
async def get_ingestion_status(
    ingestion_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Get the current status of an ingestion job.

    TODO: Fetch from DB and return status + any errors.
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{ingestion_id}/retry")
async def retry_ingestion(
    ingestion_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Retry a failed ingestion.

    TODO: Reset status, re-enqueue background task.
    """
    raise HTTPException(status_code=501, detail="Not implemented")
