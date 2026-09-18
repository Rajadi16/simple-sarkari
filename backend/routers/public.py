"""
Public routes — citizen-facing catalogue endpoints.

No authentication required. Only returns published content.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from lib.db import get_db

router = APIRouter(tags=["public"])


# ─── Search ───────────────────────────────────────────────────────────────────

@router.get("/circulars")
async def search_circulars(
    q: str | None = Query(None, description="Full-text search query"),
    source_id: str | None = Query(None),
    department: str | None = Query(None),
    government_level: str | None = Query(None, description="'central' or 'state'"),
    state: str | None = Query(None),
    document_type: str | None = Query(None),
    language: str | None = Query(None, description="e.g. hi-IN, kn-IN"),
    from_date: str | None = Query(None, description="ISO date YYYY-MM-DD"),
    to_date: str | None = Query(None, description="ISO date YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Search published circulars with filters and pagination.

    TODO: Delegate to search_service.search_circulars()
    """
    raise HTTPException(status_code=501, detail="Not implemented")


# ─── Single circular ─────────────────────────────────────────────────────────

@router.get("/circulars/{circular_id}")
async def get_circular(
    circular_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Get a single published circular by ID.

    TODO: Fetch from DB, verify published=True, return circular.
    """
    raise HTTPException(status_code=501, detail="Not implemented")


# ─── Translations ─────────────────────────────────────────────────────────────

@router.get("/circulars/{circular_id}/translations/{language}")
async def get_translation(
    circular_id: str,
    language: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Get an approved translation for a circular in the given language.

    TODO: Fetch translation where status="approved", return it.
    """
    raise HTTPException(status_code=501, detail="Not implemented")


# ─── Audio ────────────────────────────────────────────────────────────────────

@router.get("/circulars/{circular_id}/audio/{language}")
async def get_audio(
    circular_id: str,
    language: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Get a signed audio playback URL for the given circular and language.

    TODO: Verify translation is approved, return signed S3 URL.
    If language not supported: return {"audio_available": false, "text_available": true}
    """
    raise HTTPException(status_code=501, detail="Not implemented")


# ─── Filters ──────────────────────────────────────────────────────────────────

@router.get("/catalogue/filters")
async def get_filters(
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Return available filter values for the search UI.

    Response: {sources: [], departments: [], states: [], document_types: [], languages: []}

    TODO: Delegate to search_service.get_catalogue_filters()
    """
    raise HTTPException(status_code=501, detail="Not implemented")
