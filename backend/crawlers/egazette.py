"""
eGazette of India adapter — egazette.gov.in

Person 1 (Aditya) — Ingestion & Source Verification

eGazette publishes official Indian gazettes as PDFs. The listing page
has a search interface; we target the "Recent Gazettes" or direct
listing pages that return gazette entries with PDF download links.

Uses the shared HTTPS client with certificate verification enabled.
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

_LISTING_URLS = ["https://egazette.gov.in/"]

_PDF_PATTERN = re.compile(r"\.pdf$", re.I)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class EGazetteAdapter(BaseCrawlerAdapter):
    """Adapter for the eGazette of India (egazette.gov.in)."""

    PARSER_NAME = "egazette_india_v1"
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

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not _PDF_PATTERN.search(href):
                continue
            abs_url = urljoin(base_url, href)
            if not self.is_allowed_domain(abs_url):
                continue

            title = _clean(a.get_text()) or self._title_from_filename(href)
            date_text = self._find_date_near(a)
            gazette_num = self._extract_gazette_number(href, title)

            candidates.append(CandidateDocument(
                source_id="egazette",
                detail_url=abs_url,
                document_url=abs_url,
                title=title[:500],
                published_date_text=date_text,
                document_type="gazette_notification",
                department="Ministry of Law and Justice",
                language="en-IN",
                discovered_from_url=base_url,
                source_reference_id=gazette_num,
            ))

        return candidates

    def _title_from_filename(self, href: str) -> str:
        name = urlparse(href).path.split("/")[-1]
        return re.sub(r"[_\-]", " ", name.replace(".pdf", "")).strip()

    def _find_date_near(self, anchor) -> Optional[str]:
        date_pat = re.compile(
            r"\b\d{1,2}[\-/]\d{1,2}[\-/]\d{4}\b"
            r"|\b\d{4}[\-/]\d{2}[\-/]\d{2}\b",
            re.I,
        )
        el = anchor
        for _ in range(4):
            parent = el.parent
            if parent is None:
                break
            m = date_pat.search(parent.get_text())
            if m:
                return m.group(0)
            el = parent
        return None

    def _extract_gazette_number(self, href: str, title: str) -> Optional[str]:
        m = re.search(r"(CG-[A-Z\-0-9]+|Gaz[a-z]*[\s_\-]No[\s_\-]?\d+)", href + " " + title, re.I)
        return m.group(0) if m else None

    async def fetch_detail(self, candidate: CandidateDocument) -> FetchResult:
        return await self.fetch(candidate.detail_url)

    async def parse(self, candidate: CandidateDocument, result: FetchResult) -> CanonicalCircular:
        circular_id = "circular_" + uuid.uuid4().hex
        now = utcnow()

        from services.extraction_service import extract_pdf, build_content, build_extraction
        ext_result = extract_pdf(result.body, candidate.detail_url)
        content = build_content(ext_result)
        extraction = build_extraction(ext_result)
        extraction.method = "pdf"

        title = ext_result.get("title") or candidate.title or "eGazette Notification"

        date_text = candidate.published_date_text
        published_date: Optional[str] = None
        if date_text:
            dt = parse_indian_date(date_text)
            published_date = dt.strftime("%Y-%m-%d") if dt else None

        return CanonicalCircular(
            id=circular_id,
            source=SourceInfo(
                source_id="egazette",
                source_name="eGazette of India",
                source_domain="egazette.gov.in",
                source_url=candidate.detail_url,
                discovered_from_url=candidate.discovered_from_url,
                official_document_url=candidate.detail_url,
                source_reference_id=candidate.source_reference_id,
            ),
            classification=Classification(
                government_level="central",
                state=None,
                department="Ministry of Law and Justice",
                document_type="gazette_notification",
                category="legislation",
                language="en-IN",
            ),
            identity=Identity(
                title_original=title,
                gazette_number=candidate.source_reference_id,
            ),
            dates=Dates(published_date=published_date, date_text_original=date_text),
            content=content,
            attachments=[Attachment(
                url=candidate.detail_url, type="pdf", title=title,
                file_size_bytes=len(result.body) if result.body else None, s3_key=None,
            )],
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
