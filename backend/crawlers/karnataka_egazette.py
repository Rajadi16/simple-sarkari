"""
Karnataka eGazette adapter — erajyapatra.karnataka.gov.in

Person 1 (Aditya) — Ingestion & Source Verification

Karnataka eGazette publishes state gazette notifications as PDFs.
Listing pages show gazette part, date, and a PDF download link.

Uses the official session-negotiating homepage and verified HTTPS. Direct PDF
links are supported; form-only downloads require a separately verified parser.
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

_LISTING_URLS = ["https://erajyapatra.karnataka.gov.in/"]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class KarnatakaGazetteAdapter(BaseCrawlerAdapter):
    """Adapter for Karnataka eGazette."""

    PARSER_NAME = "karnataka_egazette_v1"
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
        date_pat = re.compile(r"\b\d{1,2}[\-/.]\d{1,2}[\-/.]\d{4}\b", re.I)

        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            pdf_url: Optional[str] = None
            link_text = ""
            for a in row.find_all("a", href=True):
                href = a["href"].strip()
                if ".pdf" in href.lower() or "download" in href.lower() or "Gazette" in href:
                    pdf_url = urljoin(base_url, href)
                    link_text = _clean(a.get_text())
                    break
            if not pdf_url:
                continue

            # Subject from cells
            subject = link_text
            for cell in cells:
                t = _clean(cell.get_text())
                if len(t) > len(subject) and not cell.find("a", href=True):
                    subject = t

            # Date
            date_text: Optional[str] = None
            for cell in cells:
                m = date_pat.search(cell.get_text())
                if m:
                    date_text = m.group(0)
                    break

            # Gazette number from text
            gaz_num: Optional[str] = None
            row_text = row.get_text()
            m = re.search(r"(?:No|Part|Vol)\.?\s*[\w\-/]+", row_text, re.I)
            if m:
                gaz_num = _clean(m.group(0))[:50]

            candidates.append(CandidateDocument(
                source_id="karnataka_egazette",
                detail_url=pdf_url,
                document_url=pdf_url,
                title=subject[:500] or "Karnataka Gazette",
                published_date_text=date_text,
                document_type="gazette_notification",
                department="Government of Karnataka",
                language="kn",
                discovered_from_url=base_url,
                source_reference_id=gaz_num,
            ))

        # Standalone PDF links
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href.lower().endswith(".pdf"):
                continue
            abs_url = urljoin(base_url, href)
            if not self.is_allowed_domain(abs_url):
                continue
            title = _clean(a.get_text()) or "Karnataka Gazette"
            candidates.append(CandidateDocument(
                source_id="karnataka_egazette",
                detail_url=abs_url, document_url=abs_url,
                title=title[:500],
                document_type="gazette_notification",
                department="Government of Karnataka",
                language="kn",
                discovered_from_url=base_url,
            ))

        return candidates

    async def fetch_detail(self, candidate: CandidateDocument) -> FetchResult:
        return await self.fetch(candidate.detail_url)

    async def parse(self, candidate: CandidateDocument, result: FetchResult) -> CanonicalCircular:
        circular_id = "circular_" + uuid.uuid4().hex
        now = utcnow()

        from services.extraction_service import extract_pdf, build_content, build_extraction
        ext = extract_pdf(result.body, candidate.detail_url)
        content = build_content(ext)
        extraction = build_extraction(ext)
        extraction.method = "pdf"
        title = ext.get("title") or candidate.title or "Karnataka Gazette Notification"

        date_text = candidate.published_date_text
        published_date: Optional[str] = None
        if date_text:
            dt = parse_indian_date(date_text)
            published_date = dt.strftime("%Y-%m-%d") if dt else None

        return CanonicalCircular(
            id=circular_id,
            source=SourceInfo(
                source_id="karnataka_egazette",
                source_name="Karnataka eGazette",
                source_domain=urlparse(candidate.detail_url).hostname or "erajyapatra.karnataka.gov.in",
                source_url=candidate.detail_url,
                discovered_from_url=candidate.discovered_from_url,
                official_document_url=candidate.detail_url,
                source_reference_id=candidate.source_reference_id,
            ),
            classification=Classification(
                government_level="state", state="Karnataka",
                department="Government of Karnataka",
                document_type="gazette_notification",
                category="legislation",
                language=candidate.language or "kn",
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
                retrieved_at=result.fetched_at, retrieval_timezone="Asia/Kolkata",
                http_status=result.status_code,
                content_hash=result.content_hash or self.compute_hash(result.body),
                parser_name=self.PARSER_NAME, parser_version=self.PARSER_VERSION,
                robots_checked=self.source.get("respect_robots", True), terms_checked=True,
            ),
            extraction=extraction,
            processing=Processing(status="extracted", published=False),
            source_specific_metadata={},
            created_at=now, updated_at=now,
        )
