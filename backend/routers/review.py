"""
Review workflow routes — the human approval pipeline.

All endpoints require reviewer authentication.
The approve endpoint is the ONLY way content can become published.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from lib.db import get_db
from lib.security import require_reviewer
from models.review import ReviewEditRequest, ReviewRedraftRequest, ReviewRejectRequest

router = APIRouter(prefix="/admin/reviews", tags=["reviews"], dependencies=[Depends(require_reviewer)])


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
):
    """
    Get the review queue with filters and pagination.

    TODO: Join reviews with circulars for display data, paginate.
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{review_id}")
async def get_review(review_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Get a single review item with the associated circular and translation.

    TODO: Fetch review + circular + translation, return combined view.
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.patch("/{review_id}")
async def save_edits(
    review_id: str,
    body: ReviewEditRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Save reviewer edits to a translation.

    TODO: Update review with edited fields, set status to "in_review".
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{review_id}/redraft")
async def request_redraft(
    review_id: str,
    body: ReviewRedraftRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Request AI to redraft the translation with feedback.

    TODO:
      1. Set review status to "changes_requested"
      2. Call AI service with feedback
      3. Create new translation revision
      4. Update review with new draft
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{review_id}/approve")
async def approve_review(review_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Approve a translation for publication.

    THIS IS THE ONLY ENDPOINT THAT CAN SET published=True.

    TODO:
      1. Set review.status = "approved"
      2. Set translation.status = "approved"
      3. If all translations approved: set circular.published = True
      4. Queue audio generation
      5. Log audit event
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{review_id}/reject")
async def reject_review(
    review_id: str,
    body: ReviewRejectRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Reject a translation.

    TODO: Set review.status = "rejected", log reason, create audit event.
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{review_id}/flag")
async def flag_review(review_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Flag a review item for audit.

    TODO: Create audit event with flag details.
    """
    raise HTTPException(status_code=501, detail="Not implemented")
