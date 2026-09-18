"""
Ingestion worker — background task for URL and text ingestion.

Runs as a FastAPI BackgroundTask for the hackathon.
Production: SQS consumer or Lambda.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase


async def process_url_ingestion(db: AsyncIOMotorDatabase, ingestion_id: str, url: str, source_id: str) -> None:
    """
    Background task: ingest a document from a URL.

    TODO:
      1. Validate URL (security.validate_url)
      2. Fetch the page/PDF
      3. Store raw content in S3
      4. Create circular record
      5. Run extraction
      6. Queue AI processing
      7. Update ingestion status
    """
    raise NotImplementedError("process_url_ingestion")


async def process_text_ingestion(db: AsyncIOMotorDatabase, ingestion_id: str, data: dict) -> None:
    """
    Background task: ingest pasted government text.

    TODO:
      1. Create circular from provided text
      2. Calculate content hash
      3. Skip S3 raw storage (text provided directly)
      4. Queue AI simplification
      5. Update ingestion status
    """
    raise NotImplementedError("process_text_ingestion")
