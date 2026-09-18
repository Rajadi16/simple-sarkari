"""
Search service — MongoDB text search for published circulars.

For the hackathon, uses MongoDB text indexes.
Production should migrate to OpenSearch for Hindi/regional language search.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase


async def search_circulars(
    db: AsyncIOMotorDatabase,
    *,
    q: str | None = None,
    source_id: str | None = None,
    department: str | None = None,
    government_level: str | None = None,
    state: str | None = None,
    document_type: str | None = None,
    language: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    """
    Search published circulars with filters.

    TODO: Implement:
      1. Build MongoDB query filter (published=True + supplied filters)
      2. Apply $text search if q is provided
      3. Sort by published_at descending
      4. Apply pagination (skip/limit)
      5. Return {"items": [...], "total": N, "page": P, "limit": L}
    """
    raise NotImplementedError("search_circulars")


async def get_catalogue_filters(db: AsyncIOMotorDatabase) -> dict:
    """
    Return distinct filter values for the search UI.

    TODO: Aggregate distinct sources, departments, states, document_types,
    languages from published circulars.
    """
    raise NotImplementedError("get_catalogue_filters")
