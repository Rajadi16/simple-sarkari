"""
Public routes — citizen-facing catalogue endpoints.

No authentication required. Only returns published content.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from lib.db import get_db
from lib.aws import generate_signed_url

router = APIRouter(tags=["public"])


def _clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


def _public_circular_view(doc: dict) -> dict:
    """
    Return a public-safe projection of a CanonicalCircular.

    Strips internal provenance fields and flattens the structure
    to what the frontend needs for listing and detail views.
    """
    simplification = doc.get("simplification") or {}
    content = doc.get("content") or {}
    source = doc.get("source") or {}
    identity = doc.get("identity") or {}
    dates = doc.get("dates") or {}
    classification = doc.get("classification") or {}
    processing = doc.get("processing") or {}
    provenance = doc.get("provenance") or {}
    attachments = doc.get("attachments") or []

    return {
        "id": doc.get("id"),
        # Identity
        "title": identity.get("title_original"),
        "document_number": identity.get("document_number"),
        # Source
        "source_id": source.get("source_id"),
        "source_name": source.get("source_name"),
        "source_url": source.get("source_url"),
        "official_document_url": source.get("official_document_url"),
        # Classification
        "government_level": classification.get("government_level"),
        "state": classification.get("state"),
        "department": classification.get("department"),
        "document_type": classification.get("document_type"),
        "language": classification.get("language"),
        # Dates
        "published_date": dates.get("published_date"),
        "effective_from": dates.get("effective_from"),
        "effective_until": dates.get("effective_until"),
        "last_updated": dates.get("last_updated"),
        "retrieved_at": provenance.get("retrieved_at"),
        # Original text (for detail view)
        "original_text": content.get("original_text"),
        # Simplification
        "simplified_title": simplification.get("simplified_title"),
        "summary": simplification.get("summary"),
        "simplified_text": simplification.get("simplified_text"),
        "required_action": simplification.get("required_action"),
        "who_is_affected": simplification.get("who_is_affected"),
        "important_dates": simplification.get("important_dates", []),
        "amounts": simplification.get("amounts", []),
        "eligibility": simplification.get("eligibility", []),
        "warnings": simplification.get("warnings", []),
        "keywords": simplification.get("keywords", []),
        "source_excerpts": simplification.get("source_excerpts", []),
        "attachments": attachments,
        # Status
        "published": processing.get("published", False),
        "translation_languages": processing.get("translation_languages", []),
        "audio_available": False,
        "review_date": processing.get("reviewed_at"),
    }


# ─── GET /circulars — search ──────────────────────────────────────────────────

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
) -> dict:
    """Search published circulars with filters and pagination."""
    query: dict = {"processing.published": True}

    if q:
        query["$text"] = {"$search": q}
    if source_id:
        query["source.source_id"] = source_id
    if department:
        query["classification.department"] = department
    if government_level:
        query["classification.government_level"] = government_level
    if state:
        query["classification.state"] = state
    if document_type:
        query["classification.document_type"] = document_type
    if language:
        query["classification.language"] = language
    if from_date or to_date:
        query["dates.published_date"] = {}
        if from_date:
            query["dates.published_date"]["$gte"] = from_date
        if to_date:
            query["dates.published_date"]["$lte"] = to_date

    skip = (page - 1) * limit
    total = await db.circulars.count_documents(query)

    sort_key = [("score", {"$meta": "textScore"})] if q else [("dates.published_date", -1)]
    projection = {"_id": 0} if not q else {"score": {"$meta": "textScore"}}

    cursor = db.circulars.find(query, projection).sort(sort_key).skip(skip).limit(limit)
    items = []
    async for doc in cursor:
        view = _public_circular_view(doc)
        audio = await db.audio_assets.find_one({"circular_id": view["id"], "status": "ready"}, {"_id": 1})
        view["audio_available"] = audio is not None
        items.append(view)

    return {"items": items, "total": total, "page": page, "limit": limit}


# ─── GET /circulars/{circular_id} ────────────────────────────────────────────

@router.get("/circulars/{circular_id}")
async def get_circular(
    circular_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Get a single published circular by ID."""
    doc = await db.circulars.find_one({"id": circular_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Circular '{circular_id}' not found")

    processing = doc.get("processing", {})
    if not processing.get("published", False):
        raise HTTPException(status_code=404, detail=f"Circular '{circular_id}' not found")

    view = _public_circular_view(doc)
    audio = await db.audio_assets.find_one({"circular_id": circular_id, "status": "ready"}, {"_id": 1})
    view["audio_available"] = audio is not None
    latest_review = await db.reviews.find_one(
        {"circular_id": circular_id, "status": {"$in": ["approved", "published"]}},
        sort=[("reviewed_at", -1)],
    )
    if latest_review:
        view["review_date"] = latest_review.get("reviewed_at")
    return view


# ─── GET /circulars/{circular_id}/translations/{language} ─────────────────────

@router.get("/circulars/{circular_id}/translations/{language}")
async def get_translation(
    circular_id: str,
    language: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Get the approved translation for a circular in the given language."""
    # Verify circular is published
    circ = await db.circulars.find_one(
        {"id": circular_id, "processing.published": True},
        {"_id": 0, "id": 1},
    )
    if not circ:
        raise HTTPException(status_code=404, detail=f"Circular '{circular_id}' not found")

    translation = await db.translations.find_one(
        {"circular_id": circular_id, "language": language, "status": "approved"}
    )
    if not translation:
        raise HTTPException(
            status_code=404,
            detail=f"No approved translation found for circular '{circular_id}' in language '{language}'",
        )

    translation.pop("_id", None)
    return translation


# ─── GET /circulars/{circular_id}/audio/{language} ────────────────────────────

@router.get("/circulars/{circular_id}/audio/{language}")
async def get_audio(
    circular_id: str,
    language: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Get a signed audio playback URL for the given circular and language.

    Returns {"audio_available": false, "text_available": true} when no audio
    exists yet or the language is not supported by Polly.
    """
    # Verify circular is published
    circ = await db.circulars.find_one(
        {"id": circular_id, "processing.published": True},
        {"_id": 0, "id": 1},
    )
    if not circ:
        raise HTTPException(status_code=404, detail=f"Circular '{circular_id}' not found")

    # Check for a ready audio asset
    audio = await db.audio_assets.find_one(
        {"circular_id": circular_id, "language": language, "status": "ready"}
    )
    if not audio or not audio.get("s3_key"):
        # Check if an approved translation exists (text is available even if audio isn't)
        translation_exists = await db.translations.find_one(
            {"circular_id": circular_id, "language": language, "status": "approved"},
            {"_id": 1},
        )
        return {
            "audio_available": False,
            "text_available": translation_exists is not None,
            "language": language,
        }

    signed_url = generate_signed_url(audio["s3_key"], expires_in=3600)
    return {
        "audio_available": True,
        "text_available": True,
        "language": language,
        "url": signed_url,
        "format": audio.get("format", "mp3"),
        "voice": audio.get("voice"),
        "expires_in": 3600,
    }


# ─── GET /catalogue/filters ───────────────────────────────────────────────────

@router.get("/catalogue/filters")
async def get_filters(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Return available filter values for the search UI.

    Only aggregates from published circulars.
    """
    base_match = {"processing.published": True}

    sources_cursor = db.circulars.aggregate([
        {"$match": base_match},
        {"$group": {"_id": "$source.source_id", "name": {"$first": "$source.source_name"}}},
        {"$sort": {"name": 1}},
    ])
    sources = [{"source_id": d["_id"], "name": d["name"]} async for d in sources_cursor if d["_id"]]

    departments_cursor = db.circulars.aggregate([
        {"$match": {**base_match, "classification.department": {"$ne": None}}},
        {"$group": {"_id": "$classification.department"}},
        {"$sort": {"_id": 1}},
    ])
    departments = [d["_id"] async for d in departments_cursor]

    states_cursor = db.circulars.aggregate([
        {"$match": {**base_match, "classification.state": {"$ne": None}}},
        {"$group": {"_id": "$classification.state"}},
        {"$sort": {"_id": 1}},
    ])
    states = [d["_id"] async for d in states_cursor]

    doc_types_cursor = db.circulars.aggregate([
        {"$match": {**base_match, "classification.document_type": {"$ne": None}}},
        {"$group": {"_id": "$classification.document_type"}},
        {"$sort": {"_id": 1}},
    ])
    document_types = [d["_id"] async for d in doc_types_cursor]

    languages_cursor = db.circulars.aggregate([
        {"$match": base_match},
        {"$unwind": "$processing.translation_languages"},
        {"$group": {"_id": "$processing.translation_languages"}},
        {"$sort": {"_id": 1}},
    ])
    languages = [d["_id"] async for d in languages_cursor]
    # Always include the base language
    if "en-IN" not in languages:
        languages = ["en-IN"] + languages

    return {
        "sources": sources,
        "departments": departments,
        "states": states,
        "document_types": document_types,
        "languages": languages,
    }
