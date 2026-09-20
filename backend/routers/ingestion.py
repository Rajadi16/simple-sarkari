"""
Ingestion routes — admin endpoints for manual document ingestion.

Person 1 (Aditya) — Ingestion & Source Verification

Endpoints:
  POST /api/admin/ingestions/url     — single-URL fallback ingestion
  POST /api/admin/ingestions/text    — pasted-text fallback (no network fetch)
  GET  /api/admin/ingestions/{id}    — ingestion job status
  POST /api/admin/ingestions/{id}/retry — manual retry only (never automatic)

All endpoints require Bearer token auth (lib/security.require_reviewer).
URL ingestion validates against lib/security.validate_url before any fetch.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from motor.motor_asyncio import AsyncIOMotorDatabase

from lib.db import get_db
from lib.security import require_reviewer, validate_url
from lib.dates import utcnow
from workers.ingestion_worker import process_url_ingestion, process_text_ingestion

router = APIRouter(
    prefix="/admin/ingestions",
    tags=["ingestion"],
    dependencies=[Depends(require_reviewer)],
)


# ─── Request / response models ────────────────────────────────────────────────

class UrlIngestionRequest(BaseModel):
    url: str
    source_id: str

    @field_validator("url")
    @classmethod
    def url_must_be_allowed(cls, v: str) -> str:
        try:
            return validate_url(v)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class TextIngestionRequest(BaseModel):
    title: str
    publisher: str                          # used as source_name + department fallback
    source_url: str                         # canonical URL of the original document
    source_id: str = "manual"
    department: Optional[str] = None        # overrides publisher if provided
    document_type: str = "circular"
    original_language: str = "en-IN"
    government_level: str = "central"
    state: Optional[str] = None
    date_text: Optional[str] = None         # raw date string as it appears on the document
    text: str
    target_languages: list[str] = Field(default_factory=list)


class IngestionJobResponse(BaseModel):
    job_id: str
    status: str
    circular_id: Optional[str] = None
    processing_status: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _create_job(
    db: AsyncIOMotorDatabase,
    job_type: str,
    payload: dict,
) -> str:
    """Insert a new ingestion job record and return its ID."""
    job_id = str(uuid.uuid4())
    await db.ingestion_jobs.insert_one({
        "_id": job_id,
        "job_type": job_type,
        "status": "pending",
        "payload": payload,
        "circular_id": None,
        "processing_status": None,
        "error": None,
        "created_at": utcnow().isoformat(),
        "started_at": None,
        "completed_at": None,
    })
    return job_id


async def _get_job(db: AsyncIOMotorDatabase, job_id: str) -> dict:
    doc = await db.ingestion_jobs.find_one({"_id": job_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingestion job '{job_id}' not found",
        )
    return doc


def _job_to_response(doc: dict) -> IngestionJobResponse:
    return IngestionJobResponse(
        job_id=doc["_id"],
        status=doc.get("status", "unknown"),
        circular_id=doc.get("circular_id"),
        processing_status=doc.get("processing_status"),
        error=doc.get("error"),
        created_at=doc.get("created_at"),
        started_at=doc.get("started_at"),
        completed_at=doc.get("completed_at"),
    )


# ─── POST /url ────────────────────────────────────────────────────────────────

@router.post("/url", status_code=status.HTTP_202_ACCEPTED)
async def ingest_url(
    body: UrlIngestionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Trigger ingestion of a single government URL.

    Validates URL against the allowlist before queuing.
    Runs extraction as a background task — poll GET /{job_id} for status.

    Returns 202 immediately with a job_id.
    """
    job_id = await _create_job(
        db,
        job_type="url_ingestion",
        payload={"url": body.url, "source_id": body.source_id},
    )

    background_tasks.add_task(
        process_url_ingestion,
        db=db,
        job_id=job_id,
        url=body.url,
        source_id=body.source_id,
    )

    return {"job_id": job_id, "status": "pending"}


# ─── POST /text ───────────────────────────────────────────────────────────────

@router.post("/text", status_code=status.HTTP_202_ACCEPTED)
async def ingest_text(
    body: TextIngestionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Ingest pasted government text directly — no network fetch.

    Builds a full CanonicalCircular from the provided text.
    provenance.http_status and raw_*_s3_key will be null (correct — there
    was no HTTP fetch).

    Returns 202 immediately with a job_id.
    """
    payload = {
        "title": body.title,
        "text": body.text,
        "source_id": body.source_id,
        "source_name": body.publisher,
        "source_url": body.source_url,
        "publisher": body.publisher,
        "department": body.department or body.publisher,
        "document_type": body.document_type,
        "original_language": body.original_language,
        "government_level": body.government_level,
        "state": body.state,
        "date_text": body.date_text,
        "target_languages": body.target_languages,
    }

    job_id = await _create_job(db, job_type="text_ingestion", payload=payload)

    background_tasks.add_task(
        process_text_ingestion,
        db=db,
        job_id=job_id,
        data=payload,
    )

    return {"job_id": job_id, "status": "pending"}


# ─── GET /{id} ────────────────────────────────────────────────────────────────

@router.get("/{job_id}", response_model=IngestionJobResponse)
async def get_ingestion_status(
    job_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> IngestionJobResponse:
    """
    Poll the status of an ingestion job.

    Status values:
      pending   — queued, not yet started
      running   — background task in progress
      completed — circular written to Mongo (check processing_status field)
      failed    — unrecoverable error (check error field)

    processing_status on completed jobs:
      extracted               — successfully extracted, ready for Team 3
      manual_review_required  — fetch was blocked; document needs manual attention
    """
    doc = await _get_job(db, job_id)
    return _job_to_response(doc)


# ─── POST /{id}/retry ─────────────────────────────────────────────────────────

@router.post("/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_ingestion(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Manually retry a failed ingestion job.

    Only jobs with status='failed' can be retried.
    Never retried automatically — this endpoint is the only retry path.
    """
    doc = await _get_job(db, job_id)

    if doc.get("status") not in ("failed", "pending"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job status is '{doc.get('status')}' — only failed or pending jobs can be retried",
        )

    # Reset job status
    await db.ingestion_jobs.update_one(
        {"_id": job_id},
        {
            "$set": {
                "status": "pending",
                "error": None,
                "started_at": None,
                "completed_at": None,
            }
        },
    )

    payload = doc.get("payload", {})
    job_type = doc.get("job_type", "url_ingestion")

    if job_type == "url_ingestion":
        background_tasks.add_task(
            process_url_ingestion,
            db=db,
            job_id=job_id,
            url=payload["url"],
            source_id=payload["source_id"],
        )
    elif job_type == "text_ingestion":
        background_tasks.add_task(
            process_text_ingestion,
            db=db,
            job_id=job_id,
            data=payload,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown job type '{job_type}' — cannot retry",
        )

    return {"job_id": job_id, "status": "pending"}
