"""Create deterministic JanVaani demo data in MongoDB.

Usage:
    python seed_demo.py
    python seed_demo.py --published
    python seed_demo.py --reset

This script never calls AWS and never creates a real government publication.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from config import get_settings
from models.circular import CanonicalCircular, SimplificationBlock
from models.review import Review
from models.translation import Translation


DEMO_CIRCULAR_ID = "demo-circular-farmer-deadline"
DEMO_TRANSLATION_ID = "demo-translation-hi-IN"
DEMO_REVIEW_ID = "demo-review-hi-IN"


def build_circular(published: bool) -> CanonicalCircular:
    now = datetime.now(timezone.utc)
    return CanonicalCircular(
        id=DEMO_CIRCULAR_ID,
        source={
            "source_id": "pib",
            "source_name": "Press Information Bureau",
            "source_domain": "pib.gov.in",
            "source_url": "https://www.pib.gov.in/",
            "official_document_url": "https://www.pib.gov.in/",
            "source_reference_id": "DEMO-2026-001",
        },
        classification={
            "government_level": "central",
            "department": "Ministry of Agriculture and Farmers Welfare",
            "document_type": "circular",
            "language": "en-IN",
        },
        identity={
            "title_original": "Deadline extended for farmer assistance applications",
            "subject_original": "Farmer assistance application deadline",
        },
        dates={
            "published_date": "2026-06-01",
            "effective_until": "2026-06-30",
            "date_text_original": "Applications may be submitted until 30 June 2026.",
        },
        content={
            "original_text": (
                "The Ministry of Agriculture and Farmers Welfare has extended the "
                "deadline for eligible small farmers to submit assistance applications "
                "until 30 June 2026 through the official portal."
            ),
            "clean_text": (
                "Eligible small farmers may submit assistance applications through "
                "the official portal until 30 June 2026."
            ),
        },
        provenance={
            "retrieved_at": now,
            "retrieval_timezone": "Asia/Kolkata",
            "http_status": None,
            "content_hash": "sha256:demo-farmer-deadline-2026",
            "parser_name": "demo_seed_v1",
            "parser_version": "1.0.0",
            "robots_checked": False,
            "terms_checked": True,
        },
        extraction={
            "status": "complete",
            "method": "text",
            "confidence": 1.0,
        },
        processing={
            "status": "published" if published else "translation_generated",
            "published": published,
            "translation_languages": ["hi-IN"],
        },
        simplification=SimplificationBlock(
            urgency_level="medium",
            simplified_title="Farmer assistance deadline extended",
            summary="Eligible small farmers have until 30 June 2026 to apply.",
            simplified_text=(
                "Eligible small farmers can submit their assistance application "
                "through the official portal by 30 June 2026."
            ),
            key_points=["The new application deadline is 30 June 2026."],
            action_items=["Submit the application through the official portal."],
            deadlines=[{"date": "30 June 2026", "description": "Application deadline"}],
            target_audience=["Eligible small farmers"],
            warnings=["This is synthetic demo data, not an official publication."],
            source_excerpts=[
                "Applications may be submitted until 30 June 2026 through the official portal."
            ],
        ),
        created_at=now,
        updated_at=now,
    )


def build_translation(published: bool) -> Translation:
    return Translation(
        id=DEMO_TRANSLATION_ID,
        circular_id=DEMO_CIRCULAR_ID,
        language="hi-IN",
        revision=1,
        translated_title="किसान सहायता की समय सीमा बढ़ाई गई",
        translated_text=(
            "पात्र छोटे किसान 30 जून 2026 तक आधिकारिक पोर्टल के माध्यम से "
            "सहायता के लिए आवेदन जमा कर सकते हैं।"
        ),
        translated_summary="पात्र छोटे किसानों के पास आवेदन करने के लिए 30 जून 2026 तक का समय है।",
        model_id="demo-seed",
        prompt_version="demo-seed-v1",
        status="approved" if published else "draft",
    )


def build_review(published: bool) -> Review:
    return Review(
        id=DEMO_REVIEW_ID,
        circular_id=DEMO_CIRCULAR_ID,
        translation_id=DEMO_TRANSLATION_ID,
        language="hi-IN",
        status="approved" if published else "draft",
        simplified_title="Farmer assistance deadline extended",
        simplified_text=(
            "Eligible small farmers can submit their assistance application "
            "through the official portal by 30 June 2026."
        ),
        translation_text=(
            "पात्र छोटे किसान 30 जून 2026 तक आधिकारिक पोर्टल के माध्यम से "
            "सहायता के लिए आवेदन जमा कर सकते हैं।"
        ),
        reviewer_notes="Synthetic demo record for workflow testing.",
        reviewed_at=datetime.now(timezone.utc) if published else None,
    )


async def seed(published: bool, reset: bool) -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongo_url)
    db = client[settings.db_name]
    try:
        if reset:
            await db.circulars.delete_one({"_id": DEMO_CIRCULAR_ID})
            await db.translations.delete_one({"_id": DEMO_TRANSLATION_ID})
            await db.reviews.delete_one({"_id": DEMO_REVIEW_ID})
            print("Removed demo records.")
            return

        circular = build_circular(published)
        translation = build_translation(published)
        review = build_review(published)

        circular_doc = circular.model_dump(mode="json")
        circular_doc["_id"] = circular.id
        translation_doc = translation.model_dump(mode="json")
        translation_doc["_id"] = translation.id
        review_doc = review.model_dump(mode="json")
        review_doc["_id"] = review.id

        await db.circulars.replace_one({"_id": circular.id}, circular_doc, upsert=True)
        await db.translations.replace_one({"_id": translation.id}, translation_doc, upsert=True)
        await db.reviews.replace_one({"_id": review.id}, review_doc, upsert=True)
        print({"circular_id": circular.id, "review_id": review.id, "published": published})
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed JanVaani demo data")
    parser.add_argument("--published", action="store_true", help="Seed an approved public record")
    parser.add_argument("--reset", action="store_true", help="Remove the demo records")
    args = parser.parse_args()
    asyncio.run(seed(published=args.published, reset=args.reset))
