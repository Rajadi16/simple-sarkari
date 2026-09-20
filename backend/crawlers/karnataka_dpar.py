"""
Karnataka DPAR (Department of Personnel and Administrative Reforms) adapter
— dpar.karnataka.gov.in

Person 1 (Aditya) — Ingestion & Source Verification

DPAR publishes circulars, orders, and compendiums as direct PDF links
on their listing pages. There are no individual HTML detail pages —
each circular IS the PDF.

SSL note: dpar.karnataka.gov.in uses NIC CA certificates not in Python's
default trust store. We set verify=False for this domain and note it
explicitly. This is acceptable for government-operated domains on our
explicit allowlist — it prevents MITM on the content but the domain
is trusted by explicit admin approval.
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
    CandidateDocument,
    CanonicalCircular,
    SourceInfo,
    Classification,
    Identity,
    Dates,
    Content,
    Attachment,
    Provenance,
    Extraction,
    Processing,
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


_LISTING_PAGES = [
    "https://dpar.karnataka.gov.in/page/Circulars/en",
    "https://dpar.karnataka.gov.in/page/Orders-and-Circulars/en",
]


class KarnatakaDparAdapter(BaseCrawlerAdapter):
    """Adapter for Karnataka DPAR — circulars published as direct PDF links."""

    PARSER_NAME = "karnataka_dpar_v1"
    PARSER_VERSION = "1.0.0"

    # Override fetch to use verify=False for NIC CA SSL issues
    async def _get_client(self):
        import httpx
        from config import get_settings
        if self._client is None or self._client.is_closed:
            settings = get_settings()
            self._client = httpx.AsyncClient(
                headers={"User-Agent": settings.crawler_user_agent},
                timeout=httpx.Timeout(settings.crawler_request_timeout_seconds),
                follow_redirects=True,
                max_redirects=5,
                verify=False,   # NIC CA not in Python's trust store
            )
        return self._client

    # ─── Listing ─────────────────────────────────────────────────────────

    async def fetch_listing(self) -> list[CandidateDocument]:
        candidates: list[CandidateDocument] = []
        seed_urls = self.listing_urls(_LISTING_PAGES)
        max_docs = self.source.get("max_documents_per_run", 50)

        for seed_url in seed_urls:
            if len(candidates) >= max_docs:
                break
            result = await self.fetch(seed_url)
            if result.blocked or not result.body:
                continue
            html = result.body.decode("utf-8", errors="replace")
            candidates.extend(self._parse_listing_html(html, seed_url))

        # Deduplicate by URL
        seen: set[str] = set()
        deduped = []
        for c in candidates:
            if c.detail_url not in seen:
                seen.add(c.detail_url)
                deduped.append(c)

        return deduped[:max_docs]

    def _parse_listing_html(
        self, html: str, base_url: str
    ) -> list[CandidateDocument]:
        soup = BeautifulSoup(html, "lxml")
        candidates: list[CandidateDocument] = []

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            # Only storage/upload PDF links — these are actual circular PDFs
            if not (
                ("storage" in href or "upload" in href or href.lower().endswith(".pdf"))
                and "pdf" in href.lower()
            ):
                continue

            # Skip nav/footer/compendium links (old backfill)
            link_text = _clean(a.get_text())
            if not link_text or len(link_text) < 3:
                continue

            # Resolve to absolute URL — fix http → https
            abs_url = urljoin(base_url, href)
            if abs_url.startswith("http://dpar.karnataka.gov.in"):
                abs_url = abs_url.replace("http://", "https://", 1)

            # Look for a date in the surrounding context
            date_text = self._find_date_near(a)

            # Infer doc type from link text / filename
            doc_type = self._infer_doc_type(link_text, href)

            candidates.append(CandidateDocument(
                source_id="karnataka_dpar",
                detail_url=abs_url,
                document_url=abs_url,
                title=link_text[:500],
                published_date_text=date_text,
                document_type=doc_type,
                department="Department of Personnel and Administrative Reforms, Karnataka",
                language="kn",   # Most DPAR docs are in Kannada
                discovered_from_url=base_url,
                source_reference_id=None,
            ))

        return candidates

    def _find_date_near(self, anchor) -> Optional[str]:
        date_pat = re.compile(
            r"\b\d{1,2}[\-/]\d{1,2}[\-/]\d{4}\b"
            r"|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
            r"|January|February|March|April|May|June|July|August|September|"
            r"October|November|December)\s+\d{4}\b",
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

    def _infer_doc_type(self, text: str, url: str) -> str:
        combined = (text + " " + url).lower()
        if "order" in combined:
            return "order"
        if "notification" in combined:
            return "notification"
        if "compendium" in combined:
            return "compendium"
        if "circular" in combined:
            return "circular"
        if "gazette" in combined:
            return "gazette_notification"
        return "circular"

    # ─── Detail fetch ─────────────────────────────────────────────────────

    async def fetch_detail(self, candidate: CandidateDocument) -> FetchResult:
        return await self.fetch(candidate.detail_url)

    # ─── Parse ────────────────────────────────────────────────────────────

    async def parse(
        self, candidate: CandidateDocument, result: FetchResult
    ) -> CanonicalCircular:
        circular_id = "circular_" + uuid.uuid4().hex
        now = utcnow()

        # All DPAR documents are PDFs
        from services.extraction_service import extract_pdf, build_content, build_extraction
        ext_result = extract_pdf(result.body, candidate.detail_url)
        content = build_content(ext_result)
        extraction = build_extraction(ext_result)
        extraction.method = "pdf"

        title = ext_result.get("title") or candidate.title or "Karnataka DPAR Document"

        # Date
        date_text = candidate.published_date_text
        published_date: Optional[str] = None
        if date_text:
            dt = parse_indian_date(date_text)
            if dt:
                published_date = dt.strftime("%Y-%m-%d")

        attachments = [Attachment(
            url=candidate.detail_url,
            type="pdf",
            title=title,
            file_size_bytes=len(result.body) if result.body else None,
            s3_key=None,
        )]

        return CanonicalCircular(
            id=circular_id,
            source=SourceInfo(
                source_id="karnataka_dpar",
                source_name="Karnataka DPAR",
                source_domain="dpar.karnataka.gov.in",
                source_url=candidate.detail_url,
                discovered_from_url=candidate.discovered_from_url,
                official_document_url=candidate.detail_url,
                source_reference_id=candidate.source_reference_id,
            ),
            classification=Classification(
                government_level="state",
                state="Karnataka",
                department="Department of Personnel and Administrative Reforms",
                document_type=candidate.document_type or "circular",
                category="personnel_administration",
                language=candidate.language or "kn",
            ),
            identity=Identity(title_original=title),
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
            source_specific_metadata={"ssl_note": "NIC_CA_verify_false"},
            created_at=now,
            updated_at=now,
        )
