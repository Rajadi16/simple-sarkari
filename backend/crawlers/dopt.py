"""
DoPT (Department of Personnel & Training) adapter — dopt.gov.in

Person 1 (Aditya) — Ingestion & Source Verification

DoPT publishes orders, circulars, and OMs as PDF links on listing pages.
The listing pages use a table structure with subject, date, and PDF download link.

Seed URL example:
  https://dopt.gov.in/
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup, Tag

from crawlers.base import BaseCrawlerAdapter, FetchResult
from lib.dates import parse_indian_date, utcnow
from models.circular import (
    CandidateDocument,
    CanonicalCircular,
    SourceInfo,
    Classification,
    Identity,
    Dates,
    Content,
    ContentSection,
    Attachment,
    Provenance,
    Extraction,
    Processing,
)

import uuid


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# DoPT listing pages — subject + pdf link in table rows
_LISTING_URLS = [
    "https://dopt.gov.in/",
]

# Patterns that identify a DoPT order/circular PDF link
_DOC_LINK_PATTERNS = re.compile(
    r"\.pdf(?:[?#]|$)",
    re.I,
)


class DoptAdapter(BaseCrawlerAdapter):
    """Adapter for the Department of Personnel & Training."""

    PARSER_NAME = "dopt_circular_v1"
    PARSER_VERSION = "1.0.0"

    # ─── Listing ─────────────────────────────────────────────────────────

    async def fetch_listing(self) -> list[CandidateDocument]:
        candidates: list[CandidateDocument] = []
        seed_urls = self.listing_urls(_LISTING_URLS)
        max_docs = self.source.get("max_documents_per_run", 50)

        for seed_url in seed_urls:
            if len(candidates) >= max_docs:
                break
            result = await self.fetch(seed_url)
            if result.blocked or not result.body:
                continue
            html = result.body.decode("utf-8", errors="replace")
            candidates.extend(self._parse_listing_html(html, seed_url))

        return candidates[:max_docs]

    def _parse_listing_html(
        self, html: str, base_url: str
    ) -> list[CandidateDocument]:
        soup = BeautifulSoup(html, "lxml")
        candidates: list[CandidateDocument] = []
        seen: set[str] = set()

        # DoPT listing: table rows where one cell has a PDF link
        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            # Find a PDF / document link in this row
            doc_link: Optional[str] = None
            link_title: Optional[str] = None
            for a in row.find_all("a", href=True):
                href = a["href"].strip()
                abs_href = urljoin(base_url, href)
                if (_DOC_LINK_PATTERNS.search(href)
                        and self.is_allowed_domain(abs_href)
                        and urlparse(abs_href).scheme == "https"):
                    doc_link = abs_href
                    link_title = _clean(a.get_text())
                    break

            if not doc_link or doc_link in seen:
                continue
            seen.add(doc_link)

            # Subject — longest non-link cell text
            subject = ""
            for cell in cells:
                t = _clean(cell.get_text())
                if len(t) > len(subject) and not cell.find("a", href=True):
                    subject = t

            # If no non-link subject found, use link text
            if not subject:
                subject = link_title or doc_link

            # Date — scan cells for a date pattern
            date_text = self._find_date_in_row(cells)

            is_pdf = urlparse(doc_link).path.lower().endswith(".pdf")
            doc_type = "circular"
            if "order" in doc_link.lower() or "order" in subject.lower():
                doc_type = "order"
            elif "notification" in doc_link.lower():
                doc_type = "notification"
            elif "om" in subject.lower()[:20]:
                doc_type = "office_memorandum"

            candidates.append(CandidateDocument(
                source_id="dopt",
                detail_url=doc_link,
                document_url=doc_link if is_pdf else None,
                title=subject[:500] if subject else None,
                published_date_text=date_text,
                document_type=doc_type,
                department="Department of Personnel and Training",
                language="en-IN",
                discovered_from_url=base_url,
                source_reference_id=None,
            ))

        # Also scan standalone PDF links outside tables
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            abs_href = urljoin(base_url, href)
            if not urlparse(abs_href).path.lower().endswith(".pdf"):
                continue
            if abs_href in seen:
                continue
            if not self.is_allowed_domain(abs_href) or urlparse(abs_href).scheme != "https":
                continue
            seen.add(abs_href)
            title = _clean(a.get_text()) or "DoPT Document"
            candidates.append(CandidateDocument(
                source_id="dopt",
                detail_url=abs_href,
                document_url=abs_href,
                title=title[:500],
                document_type="circular",
                department="Department of Personnel and Training",
                language="en-IN",
                discovered_from_url=base_url,
            ))

        return candidates

    def _find_date_in_row(self, cells) -> Optional[str]:
        date_pattern = re.compile(
            r"\b\d{1,2}[\s\-/](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
            r"|January|February|March|April|May|June|July|August|September|October"
            r"|November|December)[\s\-/]\d{4}\b"
            r"|\b\d{1,2}/\d{1,2}/\d{4}\b"
            r"|\b\d{4}-\d{2}-\d{2}\b",
            re.I,
        )
        for cell in cells:
            m = date_pattern.search(cell.get_text())
            if m:
                return m.group(0)
        return None

    # ─── Detail fetch ─────────────────────────────────────────────────────

    async def fetch_detail(self, candidate: CandidateDocument) -> FetchResult:
        return await self.fetch(candidate.detail_url)

    # ─── Parse ────────────────────────────────────────────────────────────

    async def parse(
        self, candidate: CandidateDocument, result: FetchResult
    ) -> CanonicalCircular:
        circular_id = "circular_" + uuid.uuid4().hex
        now = utcnow()
        content_type = result.content_type or ""

        # ── PDF document ──
        if "pdf" in content_type or urlparse(candidate.detail_url).path.lower().endswith(".pdf"):
            from services.extraction_service import extract_pdf, build_content, build_extraction
            ext_result = extract_pdf(result.body, candidate.detail_url)
            content = build_content(ext_result)
            extraction = build_extraction(ext_result)
            method = "pdf"
            title = ext_result.get("title") or candidate.title or "DoPT Document"
        else:
            # HTML detail page
            from services.extraction_service import extract_html, build_content, build_extraction
            ext_result = extract_html(result.body, candidate.detail_url)
            content = build_content(ext_result)
            extraction = build_extraction(ext_result)
            method = "html"
            title = ext_result.get("title") or candidate.title or "DoPT Document"

        extraction.method = method

        # Date
        date_text = candidate.published_date_text
        published_date: Optional[str] = None
        if date_text:
            dt = parse_indian_date(date_text)
            if dt:
                published_date = dt.strftime("%Y-%m-%d")

        # Attachment (for PDF candidate)
        attachments = []
        if candidate.detail_url.lower().endswith(".pdf"):
            attachments.append(Attachment(
                url=candidate.detail_url,
                type="pdf",
                title=title,
                file_size_bytes=len(result.body) if result.body else None,
                s3_key=None,
            ))

        return CanonicalCircular(
            id=circular_id,
            source=SourceInfo(
                source_id="dopt",
                source_name="Department of Personnel and Training",
                source_domain="dopt.gov.in",
                source_url=candidate.detail_url,
                discovered_from_url=candidate.discovered_from_url,
                official_document_url=candidate.detail_url,
                source_reference_id=candidate.source_reference_id,
            ),
            classification=Classification(
                government_level="central",
                state=None,
                department="Department of Personnel and Training",
                document_type=candidate.document_type or "circular",
                category="personnel_administration",
                language="en-IN",
            ),
            identity=Identity(
                title_original=title,
            ),
            dates=Dates(
                published_date=published_date,
                date_text_original=date_text,
            ),
            content=content,
            attachments=attachments,
            provenance=Provenance(
                retrieved_at=result.fetched_at,
                retrieval_timezone="Asia/Kolkata",
                http_status=result.status_code,
                content_hash=result.content_hash or self.compute_hash(result.body),
                parser_name=self.PARSER_NAME,
                parser_version=self.PARSER_VERSION,
                robots_checked=self.source.get("respect_robots", True),
                terms_checked=True,
            ),
            extraction=extraction,
            processing=Processing(status="extracted", published=False),
            source_specific_metadata={},
            created_at=now,
            updated_at=now,
        )
