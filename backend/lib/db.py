"""
MongoDB async client via Motor.

Connection lifecycle is managed through the FastAPI lifespan context.
Use `get_db()` as a FastAPI dependency to access the database.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config import get_settings

# Module-level references — initialized in lifespan, not at import time.
_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    """Call once during application startup (lifespan)."""
    global _client, _db
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongo_url)
    _db = _client[settings.db_name]
    await _create_indexes()


async def close_db() -> None:
    """Call once during application shutdown (lifespan)."""
    global _client, _db
    if _client:
        _client.close()
    _client = None
    _db = None


def get_db() -> AsyncIOMotorDatabase:
    """FastAPI dependency — returns the active database handle."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call connect_db() first.")
    return _db


async def _create_indexes() -> None:
    """
    Ensure required indexes exist.
    Called once on startup — idempotent.
    """
    db = get_db()

    # circulars: migrate legacy flat-schema indexes before creating canonical ones.
    existing_indexes = await db.circulars.list_indexes().to_list(length=None)
    legacy_hash = next(
        (index for index in existing_indexes if index.get("name") == "provenance.content_hash_1"),
        None,
    )
    if legacy_hash and not legacy_hash.get("unique", False):
        await db.circulars.drop_index("provenance.content_hash_1")
    await db.circulars.create_index(
        "provenance.content_hash",
        name="provenance_content_hash_unique",
        unique=True,
        sparse=True,
    )

    for index_name in ("circulars_text_search",):
        if any(index.get("name") == index_name for index in existing_indexes):
            await db.circulars.drop_index(index_name)
    await db.circulars.create_index(
        [
            ("identity.title_original", "text"),
            ("identity.subject_original", "text"),
            ("classification.department", "text"),
            ("content.original_text", "text"),
            ("content.clean_text", "text"),
            ("simplification.simplified_title", "text"),
            ("simplification.summary", "text"),
            ("simplification.simplified_text", "text"),
            ("simplification.key_points", "text"),
        ],
        name="circulars_text_search",
        language_override="text_language",
    )

    await db.circulars.create_index(
        [("source.source_id", 1), ("dates.published_date", -1)]
    )
    await db.circulars.create_index(
        [("processing.published", 1), ("dates.published_date", -1)]
    )
    await db.circulars.create_index(
        [("classification.department", 1), ("dates.published_date", -1)]
    )
    await db.circulars.create_index(
        [
            ("classification.government_level", 1),
            ("classification.state", 1),
            ("dates.published_date", -1),
        ]
    )

    # translations
    await db.translations.create_index(
        [("circular_id", 1), ("language", 1), ("revision", 1)], unique=True
    )
    await db.translations.create_index([("status", 1), ("created_at", -1)])

    # reviews
    await db.reviews.create_index([("status", 1), ("created_at", -1)])
    await db.reviews.create_index([("assigned_to", 1), ("status", 1)])

    # jobs (Team 3)
    await db.jobs.create_index("idempotency_key", unique=True, sparse=True)
    await db.jobs.create_index([("status", 1), ("created_at", -1)])

    # ingestion_jobs (Person 1 — ingestion pipeline)
    await db.ingestion_jobs.create_index([("status", 1), ("created_at", -1)])
    await db.ingestion_jobs.create_index("job_type")

    # sources (Person 1 — source registry)
    await db.sources.create_index("source_id", unique=True)

    # crawl_runs (Person 1)
    await db.crawl_runs.create_index([("source_id", 1), ("started_at", -1)])
    await db.crawl_runs.create_index("status")

    # circulars — Person 1 specific indexes (nested CanonicalCircular fields)
    await db.circulars.create_index("source.source_id")
    await db.circulars.create_index("source.source_reference_id", sparse=True)
    await db.circulars.create_index("processing.status")

    # audio_assets
    await db.audio_assets.create_index(
        [("circular_id", 1), ("language", 1)], unique=True
    )

    # audit_events
    await db.audit_events.create_index([("created_at", -1)])
    await db.audit_events.create_index([("entity_type", 1), ("entity_id", 1)])
