"""
Department of Expenditure adapter — doe.gov.in

Person 1 (Aditya) — Ingestion & Source Verification

DOE publishes office memoranda, circulars, and orders. The listing pages
follow a standard NIC/GOI table layout: subject | date | PDF link.

DNS note: doe.gov.in may have intermittent DNS resolution failures.
The base fetch layer handles this as a network_error block and records
processing.status = manual_review_required — no crash.
"""

from __future__ import annotations

import re
import uuid
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from crawlers.base import BaseCrawlerAdapter, FetchResult
from lib.dates import parse_indian_date, utcnow
from models.circular import (
    CandidateDocument, CanonicalCircular, SourceInfo, Classification,
    Identity, Dates, Content, Attachment, Provenance, Extraction, Processing,
)

_LISTING_URLS = [
    "https://doe.gov.in/circulars-and-orders",
    "https://doe.gov.in/office-memoranda",
    "https://doe.gov.in/orders",
]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _infer_doc_type(text: str, url: str) -> str:
    t = (text + url).lower()
    if "memorandum" in t or "o.m" in t or "/om" in t:
        return "office_memorandum"
    if "circular" in t:
        return "circular"
    if "order" in t:
        return "order"
    if "notification" in t:
        return "notification"
    return "circular"


class DoeAdapter(BaseCrawlerAdapter):
    """Adapter for the Department of Expenditure (doe.gov.in)."""

    PARSER_NAME = "doe_circular_v1"
    PARSER_VERSION = "1.0.0"

    async def fetch_listing(self) -> list[CandidateDocument]:
        candidates: list[CandidateDocument] = []
        seed_urls = self.source.get("seed_urls", _LISTING_URLS)
        max_docs = self.source.get("max_documents_per_run", 50)

        for seed_url in seed_urls:
            if len(candidates) >= max_docs:
                break
            result = await self.fetch(seed_url)
            if result.blocked or not result.body:
                continue
            html = result.body.decode("utf-8", errors="replace")
            candidates.extend(self._parse_listing_html(html, seed_url))

        seen: set[str] = set()
        return [c for c in candidates if not (c.detail_url in seen or seen.add(c.detail_url))][:max_docs]

    def _parse_listing_html(self, html: str, base_url: str) -> list[CandidateDocument]:
        soup = BeautifulSoup(html, "lxml")
        candidates: list[CandidateDocument] = []
        date_pat = re.compile(
            r"\b\d{1,2}[\-/.]\d{1,2}[\-/.]\d{4}\b"
            r"|\b\d{1,2}\s+\w+\s+\d{4}\b", re.I
        )

        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            pdf_url: Optional[str] = None
            anchor_text = ""
            for a in row.find_all("a", href=True):
                href = a["href"].strip()
                if ".pdf" in href.lower() or "download" in href.lower():
                    pdf_url = urljoin(base_url, href)
                    anchor_text = _clean(a.get_text())
                    break

            if not pdf_url:
                continue

            # Subject from longest non-link cell
            subject = anchor_text
            for cell in cells:
                t = _clean(cell.get_text())
                if len(t) > len(subject) and not cell.find("a", href=True):
                    subject = t

            # Date from cells
            date_text: Optional[str] = None
            for cell in cells:
                m = date_pat.search(cell.get_text())
                if m:
                    date_text = m.group(0)
                    break

            candidates.append(CandidateDocument(
                source_id="doe",
                detail_url=pdf_url,
                document_url=pdf_url,
                title=subject[:500] or "DOE Document",
                published_date_text=date_text,
                document_type=_infer_doc_type(subject, pdf_url),
                department="Department of Expenditure",
                language="en-IN",
                discovered_from_url=base_url,
            ))

        # Also catch standalone PDF links
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href.lower().endswith(".pdf"):
                continue
            abs_url = urljoin(base_url, href)
            if not self.is_allowed_domain(abs_url):
                continue
            title = _clean(a.get_text()) or "DOE Document"
            candidates.append(CandidateDocument(
                source_id="doe",
                detail_url=abs_url,
                document_url=abs_url,
                title=title[:500],
                document_type="circular",
                department="Department of Expenditure",
                language="en-IN",
                discovered_from_url=base_url,
            ))

        return candidates

    async def fetch_detail(self, candidate: CandidateDocument) -> FetchResult:
        return await self.fetch(candidate.detail_url)

    async def parse(self, candidate: CandidateDocument, result: FetchResult) -> CanonicalCircular:
        circular_id = "circular_" + uuid.uuid4().hex
        now = utcnow()
        ct = result.content_type or ""

        if "pdf" in ct or candidate.detail_url.lower().endswith(".pdf"):
            from services.extraction_service import extract_pdf, build_content, build_extraction
            ext = extract_pdf(result.body, candidate.detail_url)
            method = "pdf"
        else:
            from services.extraction_service import extract_html, build_content, build_extraction
            ext = extract_html(result.body, candidate.detail_url)
            method = "html"

        content = build_content(ext)
        extraction = build_extraction(ext)
        extraction.method = method
        title = ext.get("title") or candidate.title or "DOE Document"

        date_text = candidate.published_date_text
        published_date: Optional[str] = None
        if date_text:
            dt = parse_indian_date(date_text)
            published_date = dt.strftime("%Y-%m-%d") if dt else None

        attachments = []
        if candidate.detail_url.lower().endswith(".pdf"):
            attachments = [Attachment(
                url=candidate.detail_url, type="pdf", title=title,
                file_size_bytes=len(result.body) if result.body else None, s3_key=None,
            )]

        return CanonicalCircular(
            id=circular_id,
            source=SourceInfo(
                source_id="doe",
                source_name="Department of Expenditure",
                source_domain="doe.gov.in",
                source_url=candidate.detail_url,
                discovered_from_url=candidate.discovered_from_url,
                official_document_url=candidate.detail_url,
                source_reference_id=candidate.source_reference_id,
            ),
            classification=Classification(
                government_level="central", state=None,
                department="Department of Expenditure",
                document_type=candidate.document_type or "circular",
                category="finance",
                language="en-IN",
            ),
            identity=Identity(title_original=title),
            dates=Dates(published_date=published_date, date_text_original=date_text),
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
            created_at=now, updated_at=now,
        )
