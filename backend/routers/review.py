"""
Review workflow routes — the human approval pipeline.

All endpoints require reviewer authentication.
The approve endpoint is the ONLY way content can become published.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from lib.db import get_db
from lib.security import require_reviewer
from lib.dates import utcnow
from models.review import ReviewEditRequest, ReviewRedraftRequest, ReviewRejectRequest
from services.ai_service import simplify_document

router = APIRouter(
    prefix="/admin/reviews",
    tags=["reviews"],
    dependencies=[Depends(require_reviewer)],
)


def _clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


async def _get_review_or_404(db: AsyncIOMotorDatabase, review_id: str) -> dict:
    doc = await db.reviews.find_one({"_id": review_id})
    if not doc:
        doc = await db.reviews.find_one({"id": review_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found")
    return doc


# ─── GET / — review queue ─────────────────────────────────────────────────────

@router.get("/")
async def list_reviews(
    status: str | None = Query(None, description="draft | in_review | approved | rejected"),
    language: str | None = Query(None),
    source_id: str | None = Query(None),
    department: str | None = Query(None),
    priority: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Get the review queue with filters and pagination.

    Joins each review with its circular's identity/source fields for display.
    """
    query: dict = {}
    if status:
        query["status"] = status
    if language:
        query["language"] = language

    skip = (page - 1) * limit
    total = await db.reviews.count_documents(query)
    cursor = db.reviews.find(query).sort("created_at", -1).skip(skip).limit(limit)
    reviews = [_clean(doc) async for doc in cursor]

    # Enrich each review with minimal circular metadata for the queue view
    circular_ids = list({r["circular_id"] for r in reviews if r.get("circular_id")})
    circulars_by_id: dict = {}
    if circular_ids:
        circ_cursor = db.circulars.find(
            {"id": {"$in": circular_ids}},
            {"id": 1, "identity.title_original": 1, "source.source_name": 1,
             "classification.department": 1, "dates.published_date": 1},
        )
        async for c in circ_cursor:
            c.pop("_id", None)
            circulars_by_id[c["id"]] = c

    for review in reviews:
        review["circular"] = circulars_by_id.get(review.get("circular_id"))

    # Apply source_id / department filters post-join (denormalised filter)
    if source_id:
        reviews = [
            r for r in reviews
            if r.get("circular", {}) and
            r["circular"].get("source", {}).get("source_id") == source_id
        ]
    if department:
        reviews = [
            r for r in reviews
            if r.get("circular", {}) and
            r["circular"].get("classification", {}).get("department") == department
        ]

    return {"items": reviews, "total": total, "page": page, "limit": limit}


# ─── GET /{review_id} ─────────────────────────────────────────────────────────

@router.get("/{review_id}")
async def get_review(
    review_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Get a single review item with the associated circular and translation.
    """
    review = _clean(await _get_review_or_404(db, review_id))

    # Attach full circular
    circular = await db.circulars.find_one({"id": review["circular_id"]})
    if circular:
        circular.pop("_id", None)
    review["circular"] = circular

    # Attach translation
    t_id = review.get("translation_id")
    if t_id:
        translation = await db.translations.find_one({"_id": t_id})
        if not translation:
            translation = await db.translations.find_one({"id": t_id})
        if translation:
            translation.pop("_id", None)
        review["translation"] = translation

    return review


# ─── PATCH /{review_id} — save edits ─────────────────────────────────────────

@router.patch("/{review_id}")
async def save_edits(
    review_id: str,
    body: ReviewEditRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Save reviewer edits to a translation.

    Sets review status to 'in_review' and stores the edited fields.
    Only non-None fields in the request body are updated.
    """
    doc = await _get_review_or_404(db, review_id)
    if doc.get("status") in ("approved", "rejected"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot edit a review with status '{doc.get('status')}'",
        )

    updates: dict = {"status": "in_review", "updated_at": utcnow().isoformat()}
    for field, value in body.model_dump(exclude_none=True).items():
        updates[field] = value

    await db.reviews.update_one({"_id": doc["_id"]}, {"$set": updates})

    updated = _clean(await _get_review_or_404(db, review_id))
    return updated


# ─── POST /{review_id}/redraft ────────────────────────────────────────────────

@router.post("/{review_id}/redraft")
async def request_redraft(
    review_id: str,
    body: ReviewRedraftRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Request AI to redraft the translation with reviewer feedback.

    1. Marks review status as 'changes_requested'
    2. Fetches the circular's original text
    3. Re-runs simplification with the feedback appended
    4. Creates a new Translation revision
    5. Updates the review to point at the new translation
    """
    doc = await _get_review_or_404(db, review_id)
    if doc.get("status") in ("approved", "rejected"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot redraft a review with status '{doc.get('status')}'",
        )

    circular_id = doc["circular_id"]
    language = doc["language"]

    # Mark changes requested
    await db.reviews.update_one(
        {"_id": doc["_id"]},
        {"$set": {"status": "changes_requested", "updated_at": utcnow().isoformat()}},
    )

    # Load circular text
    circular = await db.circulars.find_one({"id": circular_id})
    if not circular:
        raise HTTPException(status_code=404, detail=f"Circular '{circular_id}' not found")

    text = (
        circular.get("content", {}).get("clean_text")
        or circular.get("content", {}).get("original_text")
        or ""
    )
    if not text:
        raise HTTPException(status_code=422, detail="Circular has no extractable text for redraft")

    # Re-run AI with feedback appended
    feedback_prompt = f"{text}\n\n---\nReviewer feedback: {body.feedback}"
    result = await simplify_document(feedback_prompt)

    # Determine next revision number
    old_t_id = doc.get("translation_id")
    old_translation = None
    if old_t_id:
        old_translation = await db.translations.find_one({"_id": old_t_id})
    old_revision = old_translation.get("revision", 1) if old_translation else 1

    # Create new Translation revision
    import uuid
    from models.translation import Translation
    from config import get_settings
    settings = get_settings()

    new_translation = Translation(
        circular_id=circular_id,
        language=language,
        revision=old_revision + 1,
        translated_title=result.simplified_title,
        translated_text=result.simplified_text,
        status="draft",
        model_id=settings.bedrock_model_id,
        prompt_version="v1",
    )
    t_dict = new_translation.model_dump()
    t_dict["_id"] = new_translation.id
    await db.translations.insert_one(t_dict)

    # Point review at new translation and reset to draft
    await db.reviews.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "translation_id": new_translation.id,
                "status": "draft",
                "simplified_title": None,
                "simplified_text": None,
                "translation_text": None,
                "updated_at": utcnow().isoformat(),
            }
        },
    )

    return {
        "review_id": review_id,
        "new_translation_id": new_translation.id,
        "revision": new_translation.revision,
        "status": "draft",
    }


# ─── POST /{review_id}/approve ────────────────────────────────────────────────

@router.post("/{review_id}/approve")
async def approve_review(
    review_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """
    Approve a translation for publication.

    THIS IS THE ONLY ENDPOINT THAT CAN SET published=True.

    1. Sets review.status = 'approved'
    2. Copies reviewer edits into the Translation document
    3. Sets translation.status = 'approved'
    4. If ALL translations for the circular are approved → sets circular.processing.published = True
    """
    doc = await _get_review_or_404(db, review_id)
    if doc.get("status") == "approved":
        raise HTTPException(status_code=409, detail="Review is already approved")
    if doc.get("status") == "rejected":
        raise HTTPException(status_code=409, detail="Cannot approve a rejected review")

    now = utcnow().isoformat()
    circular_id = doc["circular_id"]
    t_id = doc.get("translation_id")

    # 1. Approve the review
    await db.reviews.update_one(
        {"_id": doc["_id"]},
        {"$set": {"status": "approved", "reviewed_at": now, "updated_at": now}},
    )

    # 2. Copy reviewer edits → translation, mark approved
    if t_id:
        translation_updates: dict = {"status": "approved", "updated_at": now}
        if doc.get("simplified_text"):
            translation_updates["translated_text"] = doc["simplified_text"]
        if doc.get("simplified_title"):
            translation_updates["translated_title"] = doc["simplified_title"]
        if doc.get("translation_text"):
            translation_updates["translated_text"] = doc["translation_text"]

        await db.translations.update_one(
            {"_id": t_id},
            {"$set": translation_updates},
        )

    # 3. Check if all translations for this circular are approved
    all_reviews = await db.reviews.find({"circular_id": circular_id}).to_list(length=None)
    all_approved = all(r.get("status") == "approved" for r in all_reviews)

    if all_approved and all_reviews:
        await db.circulars.update_one(
            {"id": circular_id},
            {"$set": {"processing.published": True, "processing.status": "published", "updated_at": now}},
        )

    return {
        "review_id": review_id,
        "status": "approved",
        "circular_published": all_approved,
    }


# ─── POST /{review_id}/reject ─────────────────────────────────────────────────

@router.post("/{review_id}/reject")
async def reject_review(
    review_id: str,
    body: ReviewRejectRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Reject a translation with a mandatory reason."""
    doc = await _get_review_or_404(db, review_id)
    if doc.get("status") == "approved":
        raise HTTPException(status_code=409, detail="Cannot reject an already-approved review")

    now = utcnow().isoformat()
    await db.reviews.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "status": "rejected",
                "reviewer_notes": body.reason,
                "reviewed_at": now,
                "updated_at": now,
            }
        },
    )

    # Mark translation rejected too
    t_id = doc.get("translation_id")
    if t_id:
        await db.translations.update_one(
            {"_id": t_id},
            {"$set": {"status": "rejected", "updated_at": now}},
        )

    return {"review_id": review_id, "status": "rejected"}


# ─── POST /{review_id}/flag ───────────────────────────────────────────────────

@router.post("/{review_id}/flag")
async def flag_review(
    review_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Flag a review item for audit attention."""
    doc = await _get_review_or_404(db, review_id)

    now = utcnow().isoformat()

    # Log an audit event
    await db.audit_events.insert_one({
        "event_type": "review_flagged",
        "review_id": review_id,
        "circular_id": doc.get("circular_id"),
        "language": doc.get("language"),
        "created_at": now,
    })

    # Add a flag tag to the review
    await db.reviews.update_one(
        {"_id": doc["_id"]},
        {
            "$addToSet": {"risk_tags": "flagged"},
            "$set": {"updated_at": now},
        },
    )

    return {"review_id": review_id, "flagged": True}
