"""
India.gov.in National Portal adapter — india.gov.in / www.india.gov.in

Person 1 (Aditya) — Ingestion & Source Verification

india.gov.in is the national portal aggregating content from all central
ministries. We target the "Policies & Rules" and "Notifications" sections
which list documents with links to source PDFs or HTML pages.

Seed URL note: confirm the correct listing URL before running — the portal
restructures its URLs periodically. Current best candidates:
  https://www.india.gov.in/my-government/policies
  https://www.india.gov.in/official-documents/notifications
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
from services.extraction_service import extract_html, extract_pdf, build_content, build_extraction

_LISTING_URLS = [
    "https://www.india.gov.in/my-government/policies",
    "https://www.india.gov.in/official-documents/notifications",
    "https://www.india.gov.in/my-government/acts-rules-regulations",
]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class IndiaGovAdapter(BaseCrawlerAdapter):
    """Adapter for the India.gov.in national portal."""

    PARSER_NAME = "india_gov_v1"
    PARSER_VERSION = "1.0.0"

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

        seen: set[str] = set()
        return [c for c in candidates if not (c.detail_url in seen or seen.add(c.detail_url))][:max_docs]

    def _parse_listing_html(self, html: str, base_url: str) -> list[CandidateDocument]:
        soup = BeautifulSoup(html, "lxml")
        candidates: list[CandidateDocument] = []

        # india.gov.in uses article cards or list items with links
        for item in soup.find_all(["li", "article", "div"], class_=re.compile(
            r"view-row|item|result|card|news|document|policy|notification", re.I
        )):
            anchors = item.find_all("a", href=True)
            if not anchors:
                continue

            for a in anchors:
                href = a["href"].strip()
                abs_url = urljoin(base_url, href)
                parsed = urlparse(abs_url)

                # Only follow links on india.gov.in or .gov.in PDF links
                if parsed.hostname not in ("india.gov.in", "www.india.gov.in"):
                    continue

                title = _clean(a.get_text())
                if not title or len(title) < 5:
                    title = _clean(item.get_text())[:200]

                # Date nearby
                date_text = self._find_date(item)
                is_pdf = href.lower().endswith(".pdf")

                candidates.append(CandidateDocument(
                    source_id="india_gov",
                    detail_url=abs_url,
                    document_url=abs_url if is_pdf else None,
                    title=title[:500],
                    published_date_text=date_text,
                    document_type="notification",
                    department="Government of India",
                    language="en-IN",
                    discovered_from_url=base_url,
                ))
                break  # one link per item

        return candidates

    def _find_date(self, el) -> Optional[str]:
        date_pat = re.compile(
            r"\b\d{1,2}\s+\w+\s+\d{4}\b"
            r"|\b\d{1,2}[\-/]\d{1,2}[\-/]\d{4}\b",
            re.I,
        )
        m = date_pat.search(el.get_text())
        return m.group(0) if m else None

    async def fetch_detail(self, candidate: CandidateDocument) -> FetchResult:
        return await self.fetch(candidate.detail_url)

    async def parse(self, candidate: CandidateDocument, result: FetchResult) -> CanonicalCircular:
        circular_id = "circular_" + uuid.uuid4().hex
        now = utcnow()
        ct = result.content_type or ""

        if "pdf" in ct or candidate.detail_url.lower().endswith(".pdf"):
            ext = extract_pdf(result.body, candidate.detail_url)
            method = "pdf"
        else:
            ext = extract_html(result.body, candidate.detail_url)
            method = "html"

        content = build_content(ext)
        extraction = build_extraction(ext)
        extraction.method = method
        title = ext.get("title") or candidate.title or "India.gov.in Document"

        date_text = candidate.published_date_text
        published_date: Optional[str] = None
        if date_text:
            dt = parse_indian_date(date_text)
            published_date = dt.strftime("%Y-%m-%d") if dt else None

        return CanonicalCircular(
            id=circular_id,
            source=SourceInfo(
                source_id="india_gov",
                source_name="India.gov.in National Portal",
                source_domain="india.gov.in",
                source_url=candidate.detail_url,
                discovered_from_url=candidate.discovered_from_url,
                official_document_url=candidate.detail_url,
                source_reference_id=candidate.source_reference_id,
            ),
            classification=Classification(
                government_level="central", state=None,
                department="Government of India",
                document_type=candidate.document_type or "notification",
                category=None,
                language="en-IN",
            ),
            identity=Identity(title_original=title),
            dates=Dates(published_date=published_date, date_text_original=date_text),
            content=content,
            attachments=[],
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
