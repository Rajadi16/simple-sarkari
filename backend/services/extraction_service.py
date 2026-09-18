"""
Extraction service — converts raw HTML/PDF into structured text.

Responsibilities:
  - HTML text extraction (BeautifulSoup / lxml)
  - PDF text extraction (PyMuPDF)
  - Content hash calculation
  - Metadata extraction (title, dates, department)
"""

from motor.motor_asyncio import AsyncIOMotorDatabase


async def extract_html(raw_html: bytes, url: str) -> dict:
    """
    Extract text and metadata from raw HTML.

    TODO: Implement with BeautifulSoup:
      - Strip navigation, headers, footers
      - Extract main content
      - Pull title, dates, department from page structure
      - Return {"title": ..., "text": ..., "metadata": {...}}
    """
    raise NotImplementedError("extract_html")


async def extract_pdf(raw_pdf: bytes, filename: str) -> dict:
    """
    Extract text and metadata from a PDF.

    TODO: Implement with PyMuPDF:
      - Extract text per page
      - Detect scanned pages (for OCR queue)
      - Pull metadata from PDF properties
      - Return {"title": ..., "text": ..., "pages": [...], "metadata": {...}}
    """
    raise NotImplementedError("extract_pdf")


async def process_extraction(db: AsyncIOMotorDatabase, circular_id: str) -> None:
    """
    Full extraction pipeline for a circular.

    TODO:
      1. Load circular from DB
      2. Download raw content from S3
      3. Detect content type (HTML vs PDF)
      4. Call extract_html or extract_pdf
      5. Update circular with extracted text
      6. Update processing_status to "extracted"
    """
    raise NotImplementedError("process_extraction")
