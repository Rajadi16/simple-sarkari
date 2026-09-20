"""
Ingestion worker — background task wrappers for URL and text ingestion.

Person 1 (Aditya) — Ingestion & Source Verification

These are thin wrappers that run inside FastAPI's BackgroundTasks mechanism.
They:
  - Call the real pipeline in crawler_service / provenance_service
  - Update the ingestion job record in Mongo (status, result, error)
  - Never retry automatically — manual retry is exposed via the /retry endpoint

For the hackathon we use FastAPI BackgroundTasks (in-process async tasks).
Production upgrade path: replace the body with an SQS message dispatch while
keeping the same function signatures.
"""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from lib.dates import utcnow
from services.crawler_service import ingest_single_url, ingest_pasted_text
from services.ai_service import process_simplification
from services.translation_service import create_translations


# ─── Job status helpers ───────────────────────────────────────────────────────

async def _mark_running(db: AsyncIOMotorDatabase, job_id: str) -> None:
    await db.ingestion_jobs.update_one(
        {"_id": job_id},
        {"$set": {"status": "running", "started_at": utcnow().isoformat()}},
    )


async def _mark_done(
    db: AsyncIOMotorDatabase,
    job_id: str,
    circular_id: str,
    processing_status: str,
) -> None:
    await db.ingestion_jobs.update_one(
        {"_id": job_id},
        {
            "$set": {
                "status": "completed",
                "circular_id": circular_id,
                "processing_status": processing_status,
                "completed_at": utcnow().isoformat(),
            }
        },
    )


async def _mark_failed(
    db: AsyncIOMotorDatabase, job_id: str, error: str
) -> None:
    await db.ingestion_jobs.update_one(
        {"_id": job_id},
        {
            "$set": {
                "status": "failed",
                "error": error,
                "completed_at": utcnow().isoformat(),
            }
        },
    )


async def _run_simplification_if_extractable(
    db: AsyncIOMotorDatabase,
    circular_id: str,
    processing_status: str,
) -> str:
    """Run Bedrock simplification only after successful text extraction."""
    if processing_status != "extracted":
        return processing_status

    await process_simplification(db, circular_id)
    return "ai_draft_generated"


# ─── URL ingestion worker ─────────────────────────────────────────────────────

async def process_url_ingestion(
    db: AsyncIOMotorDatabase,
    job_id: str,
    url: str,
    source_id: str,
) -> None:
    """
    Background task: fetch, extract, and store a document from a URL.

    Writes processing.status = "extracted" on success, or
    "manual_review_required" on a blocked/failed fetch.
    Never retries automatically — use the /retry endpoint for manual retry.
    """
    await _mark_running(db, job_id)
    try:
        circular = await ingest_single_url(
            db=db,
            url=url,
            source_id=source_id,
        )
        processing_status = await _run_simplification_if_extractable(
            db, circular.id, circular.processing.status
        )
        if processing_status == "ai_draft_generated":
            await create_translations(
                db,
                circular.id,
                data.get("target_languages") or ["hi-IN"],
            )
            updated_doc = await db.circulars.find_one({"id": circular.id})
            if updated_doc:
                processing_status = updated_doc.get("processing", {}).get("status", "translation_generated")

        await _mark_done(db, job_id, circular.id, processing_status)
    except Exception as exc:
        await _mark_failed(db, job_id, str(exc))


# ─── Pasted-text ingestion worker ─────────────────────────────────────────────

async def process_text_ingestion(
    db: AsyncIOMotorDatabase,
    job_id: str,
    data: dict,
) -> None:
    """
    Background task: build a CanonicalCircular from pasted government text.

    No network fetch. provenance.http_status and raw_*_s3_key are null.
    processing.status = "extracted" on success.
    """
    await _mark_running(db, job_id)
    try:
        circular = await ingest_pasted_text(
            db=db,
            title=data["title"],
            text=data["text"],
            source_id=data.get("source_id", "manual"),
            source_name=data.get("source_name", data.get("publisher", "Manual Ingestion")),
            source_url=data.get("source_url", ""),
            department=data.get("department", data.get("publisher", "Unknown")),
            document_type=data.get("document_type", "circular"),
            language=data.get("original_language", "en-IN"),
            government_level=data.get("government_level", "central"),
            state=data.get("state"),
            date_text=data.get("date_text"),
        )
        processing_status = await _run_simplification_if_extractable(
            db, circular.id, circular.processing.status
        )
        if processing_status == "ai_draft_generated":
            await create_translations(db, circular.id, ["hi-IN", "kn-IN"])
            updated_doc = await db.circulars.find_one({"id": circular.id})
            if updated_doc:
                processing_status = updated_doc.get("processing", {}).get("status", "translation_generated")

        await _mark_done(db, job_id, circular.id, processing_status)
    except Exception as exc:
        await _mark_failed(db, job_id, str(exc))


# ─── Crawl worker ─────────────────────────────────────────────────────────────

async def process_crawl_run(
    db: AsyncIOMotorDatabase,
    run_id: str,
    source_id: str,
    max_pages: int,
    max_documents: int,
) -> None:
    """
    Background task: run a full crawl for a source.

    Updates the crawl_runs record (managed inside crawler_service.run_crawl).
    """
    from services.crawler_service import run_crawl
    await run_crawl(
        db=db,
        source_id=source_id,
        max_pages=max_pages,
        max_documents=max_documents,
        run_id=run_id,
    )
