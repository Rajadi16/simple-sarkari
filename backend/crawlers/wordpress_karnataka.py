"""
Generic WordPress adapter for Karnataka/state government websites.

Person 1 (Aditya) — Ingestion & Source Verification

Covers: vtu.ac.in, karnataka.gov.in
WordPress sites expose circulars via category pages and post listings.
PDFs are linked directly in post content or wp-content/uploads.
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


def _infer_doc_type(text: str, url: str) -> str:
    t = (text + " " + url).lower()
    if "circular" in t:
        return "circular"
    if "notification" in t or "notice" in t:
        return "notification"
    if "order" in t:
        return "order"
    if "result" in t:
        return "notification"
    return "circular"


class WordPressKarnatakaAdapter(BaseCrawlerAdapter):
    """Generic adapter for WordPress-based Karnataka government sites."""

    PARSER_NAME = "wordpress_karnataka_v1"
    PARSER_VERSION = "1.0.0"

    async def fetch_listing(self) -> list[CandidateDocument]:
        candidates: list[CandidateDocument] = []
        seed_urls = self.source.get("seed_urls", [])
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
        return [c for c in candidates
                if not (c.detail_url in seen or seen.add(c.detail_url))][:max_docs]

    def _parse_listing_html(self, html: str, base_url: str) -> list[CandidateDocument]:
        soup = BeautifulSoup(html, "lxml")
        candidates: list[CandidateDocument] = []
        base_host = urlparse(base_url).hostname or ""
        base_domains = self.source.get("base_domains", [base_host])
        date_pat = re.compile(
            r"\b\d{1,2}[\-/.]\d{1,2}[\-/.]\d{4}\b"
            r"|\b\d{4}-\d{2}-\d{2}\b"
            r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4}\b",
            re.I
        )

        # WP article links — post titles inside <h2 class="entry-title"> or <article>
        for article in soup.find_all(["article", "div"], class_=re.compile(r"post|entry|item", re.I)):
            a = article.find("a", href=True)
            if not a:
                continue
            href = a["href"].strip()
            abs_url = urljoin(base_url, href)
            host = urlparse(abs_url).hostname or ""
            if not any(host.endswith(d) for d in base_domains):
                continue
            title = _clean(a.get_text())
            if not title:
                continue
            date_text = None
            time_el = article.find("time")
            if time_el:
                date_text = _clean(time_el.get_text())
            if not date_text:
                m = date_pat.search(article.get_text())
                date_text = m.group(0) if m else None

            candidates.append(CandidateDocument(
                source_id=self.source.get("source_id", "wordpress_karnataka"),
                detail_url=abs_url,
                title=title[:500],
                published_date_text=date_text,
                document_type=_infer_doc_type(title, href),
                department=self.source.get("department", self.source.get("name", "")),
                language=self.source.get("language", "en-IN"),
                discovered_from_url=base_url,
            ))

        # Also pick up direct PDF links
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href.lower().endswith(".pdf"):
                continue
            abs_url = urljoin(base_url, href)
            host = urlparse(abs_url).hostname or ""
            if not any(host.endswith(d) for d in base_domains):
                continue
            title = _clean(a.get_text()) or href.split("/")[-1].replace(".pdf", "")
            date_text = self._find_date_near(a, date_pat)
            candidates.append(CandidateDocument(
                source_id=self.source.get("source_id", "wordpress_karnataka"),
                detail_url=abs_url,
                document_url=abs_url,
                title=title[:500],
                published_date_text=date_text,
                document_type=_infer_doc_type(title, href),
                department=self.source.get("department", self.source.get("name", "")),
                language=self.source.get("language", "en-IN"),
                discovered_from_url=base_url,
            ))

        return candidates

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
        title = ext.get("title") or candidate.title or self.source.get("name", "Document")

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

        source_domain = urlparse(candidate.detail_url).hostname or self.source.get("base_domains", [""])[0]

        return CanonicalCircular(
            id=circular_id,
            source=SourceInfo(
                source_id=self.source.get("source_id", "wordpress_karnataka"),
                source_name=self.source.get("name", "Karnataka Government"),
                source_domain=source_domain,
                source_url=candidate.detail_url,
                discovered_from_url=candidate.discovered_from_url,
                official_document_url=candidate.detail_url,
                source_reference_id=candidate.source_reference_id,
            ),
            classification=Classification(
                government_level=self.source.get("government_level", "state"),
                state=self.source.get("state", "Karnataka"),
                department=self.source.get("department", self.source.get("name", "Karnataka Government")),
                document_type=candidate.document_type or "circular",
                category=self.source.get("category"),
                language=self.source.get("language", "en-IN"),
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
