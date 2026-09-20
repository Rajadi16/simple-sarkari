"""
SSP Karnataka adapter — ssp.karnataka.gov.in

Person 1 (Aditya) — Ingestion & Source Verification

SSP (Samaja Suraksha Parishe / Social Security) Karnataka.
ASP.NET site. Notices are listed in a #noticeSection or table on the homepage.
PDFs are linked from notices. verify=False for NIC CA.
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


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class SspKarnatakaAdapter(BaseCrawlerAdapter):
    """Adapter for SSP Karnataka (ssp.karnataka.gov.in)."""

    PARSER_NAME = "ssp_karnataka_v1"
    PARSER_VERSION = "1.0.0"

    async def _get_client(self):
        import httpx
        if self._client is None or self._client.is_closed:
            settings = self.settings
            self._client = httpx.AsyncClient(
                headers={"User-Agent": settings.crawler_user_agent},
                timeout=httpx.Timeout(settings.crawler_request_timeout_seconds),
                follow_redirects=True, max_redirects=5,
                verify=False,
            )
        return self._client

    async def fetch_listing(self) -> list[CandidateDocument]:
        candidates: list[CandidateDocument] = []
        seed_urls = self.source.get("seed_urls", ["https://ssp.karnataka.gov.in/"])
        max_docs = self.source.get("max_documents_per_run", 50)

        for seed_url in seed_urls:
            result = await self.fetch(seed_url)
            if result.blocked or not result.body:
                continue
            html = result.body.decode("utf-8", errors="replace")
            soup = BeautifulSoup(html, "lxml")
            date_pat = re.compile(r"\b\d{1,2}[\-/.]\d{1,2}[\-/.]\d{4}\b", re.I)
            base_host = urlparse(seed_url).hostname or ""

            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                abs_url = urljoin(seed_url, href)
                is_pdf = href.lower().endswith(".pdf")
                is_notice = any(k in href.lower() for k in ["notice", "circular", "order", "news"])
                if not (is_pdf or is_notice):
                    continue
                if urlparse(abs_url).hostname not in (base_host, "www." + base_host):
                    continue
                title = _clean(a.get_text()) or href.split("/")[-1]
                date_text = self._find_date_near(a, date_pat)
                candidates.append(CandidateDocument(
                    source_id="ssp_karnataka",
                    detail_url=abs_url,
                    document_url=abs_url if is_pdf else None,
                    title=title[:500],
                    published_date_text=date_text,
                    document_type="circular" if "circular" in href.lower() else "notification",
                    department="Social Security and Pensions Department, Karnataka",
                    language="kn",
                    discovered_from_url=seed_url,
                ))
                if len(candidates) >= max_docs:
                    break

        seen: set[str] = set()
        return [c for c in candidates if not (c.detail_url in seen or seen.add(c.detail_url))][:max_docs]

    def _find_date_near(self, anchor, date_pat) -> Optional[str]:
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

    async def fetch_detail(self, candidate: CandidateDocument) -> FetchResult:
        return await self.fetch(candidate.detail_url)

    async def parse(self, candidate: CandidateDocument, result: FetchResult) -> CanonicalCircular:
        circular_id = "circular_" + uuid.uuid4().hex
        now = utcnow()
        ct = (result.content_type or "").lower()

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
        title = ext.get("title") or candidate.title or "SSP Karnataka Notice"

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
                source_id="ssp_karnataka",
                source_name="SSP Karnataka",
                source_domain="ssp.karnataka.gov.in",
                source_url=candidate.detail_url,
                discovered_from_url=candidate.discovered_from_url,
                official_document_url=candidate.detail_url,
                source_reference_id=candidate.source_reference_id,
            ),
            classification=Classification(
                government_level="state", state="Karnataka",
                department="Social Security and Pensions Department, Karnataka",
                document_type=candidate.document_type or "notification",
                category="social_welfare",
                language="kn",
            ),
            identity=Identity(title_original=title),
            dates=Dates(published_date=published_date, date_text_original=date_text),
            content=content, attachments=attachments,
            provenance=Provenance(
                retrieved_at=result.fetched_at, retrieval_timezone="Asia/Kolkata",
                http_status=result.status_code,
                content_hash=result.content_hash or self.compute_hash(result.body),
                parser_name=self.PARSER_NAME, parser_version=self.PARSER_VERSION,
                robots_checked=self.source.get("respect_robots", True), terms_checked=True,
            ),
            extraction=extraction,
            processing=Processing(status="extracted", published=False),
            source_specific_metadata={"ssl_note": "NIC_CA_verify_false"},
            created_at=now, updated_at=now,
        )
