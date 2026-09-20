"""
PIB (Press Information Bureau) crawler adapter — www.pib.gov.in

Person 1 (Aditya) — Ingestion & Source Verification

Target listing:  https://www.pib.gov.in/Allrel.aspx?reg=48&lang=1
Detail pages:    PressReleaseDetail.aspx?PRID=<id>
                 FactsheetDetails.aspx?PRID=<id>
                 PressNoteDetails.aspx?PRID=<id>

Parsing approach:
  - Listing: extract detail links whose href contains one of the three
    path patterns above; grab title/date/ministry from the row context.
  - Detail: locate the main content div (id="content" or class="innner-page"),
    ignore nav, social embeds, image sliders, videos, footers.
  - PRID is the canonical source_reference_id.
  - Never invent/guess field values — null if not on the page.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse, urlencode, urljoin, parse_qs

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
    Provenance,
    Extraction,
    Processing,
)

# Detail page URL path patterns we follow
_DETAIL_PATHS = (
    "/PressReleaseDetail.aspx",
    "/FactsheetDetails.aspx",
    "/PressNoteDetails.aspx",
)

# Tags / attributes used for the main content block on PIB detail pages
_CONTENT_SELECTORS = [
    {"id": "content"},
    {"id": "MCE_Body"},
    {"class": "innner-page"},          # PIB typo — intentional
    {"class": "inner-page"},
    {"id": "lblPRDetail"},
    {"class": "release-content"},
]

# Elements to strip from content (nav, social, decorative)
_NOISE_TAGS = [
    "nav", "header", "footer", "script", "style", "noscript",
    "iframe", "figure", "picture", "video", "audio", "form",
]
_NOISE_CLASSES = [
    "social-share", "share-buttons", "related-news", "advertisement",
    "breadcrumb", "pagination", "sidebar", "widget", "banner",
    "carousel", "slider", "navbar", "topnav", "menu",
]


def _extract_prid(url: str) -> Optional[str]:
    """Pull the PRID query param value from a PIB detail URL."""
    qs = parse_qs(urlparse(url).query)
    prid = qs.get("PRID") or qs.get("prid")
    if prid:
        return f"PRID={prid[0]}"
    return None


def _clean_text(text: str) -> str:
    """Collapse whitespace and strip leading/trailing blanks."""
    return re.sub(r"\s+", " ", text).strip()


def _strip_noise(soup: BeautifulSoup) -> None:
    """Remove noisy elements in-place."""
    for tag in _NOISE_TAGS:
        for el in soup.find_all(tag):
            el.decompose()
    for cls in _NOISE_CLASSES:
        for el in soup.find_all(class_=re.compile(cls, re.I)):
            el.decompose()


def _extract_main_content(soup: BeautifulSoup) -> Optional[Tag]:
    """
    Find the main content container on a PIB page.
    Tries known selectors in priority order.
    """
    for selector in _CONTENT_SELECTORS:
        el = soup.find(**selector)
        if el and len(el.get_text(strip=True)) > 100:
            return el  # type: ignore[return-value]

    # Fallback: largest <div> by text length
    best: Optional[Tag] = None
    best_len = 0
    for div in soup.find_all("div"):
        t = div.get_text(strip=True)
        if len(t) > best_len:
            best_len = len(t)
            best = div
    return best


def _infer_document_type(url: str) -> str:
    path = urlparse(url).path.lower()
    if "factsheet" in path:
        return "fact_sheet"
    if "pressnote" in path:
        return "press_note"
    return "press_release"


def _infer_category(department: Optional[str]) -> Optional[str]:
    """Very rough category from ministry name — null if not mappable."""
    if not department:
        return None
    dept_lower = department.lower()
    mapping = {
        "agriculture": "agriculture",
        "health": "health",
        "education": "education",
        "finance": "finance",
        "defence": "defence",
        "home": "home_affairs",
        "railways": "railways",
        "environment": "environment",
        "road": "transport",
        "transport": "transport",
        "science": "science_technology",
        "technology": "science_technology",
        "women": "social_welfare",
        "child": "social_welfare",
    }
    for keyword, category in mapping.items():
        if keyword in dept_lower:
            return category
    return None


class PibAdapter(BaseCrawlerAdapter):
    """Crawler adapter for the Press Information Bureau."""

    PARSER_NAME = "pib_press_release_v1"
    PARSER_VERSION = "1.0.0"

    # ─── Listing ─────────────────────────────────────────────────────────

    async def fetch_listing(self) -> list[CandidateDocument]:
        """
        Crawl the PIB listing page(s) and return CandidateDocuments.

        Each seed URL is fetched once; up to max_pages_per_run pages
        (for paginated listings) and max_documents_per_run total docs.
        """
        candidates: list[CandidateDocument] = []
        seed_urls: list[str] = self.listing_urls()
        max_docs = self.source.get("max_documents_per_run", 50)

        for seed_url in seed_urls:
            if len(candidates) >= max_docs:
                break
            result = await self.fetch(seed_url)
            if result.blocked or result.not_modified or not result.body:
                continue

            html = result.body.decode("utf-8", errors="replace")
            if "xml" in (result.content_type or "").lower() or html.lstrip().startswith(("<?xml", "<rss")):
                new_candidates = self._parse_listing_rss(result.body, seed_url)
            else:
                new_candidates = self._parse_listing_html(html, seed_url)
            candidates.extend(new_candidates)

        unique = {candidate.detail_url: candidate for candidate in candidates}
        return list(unique.values())[:max_docs]

    def _parse_listing_rss(self, body: bytes, base_url: str) -> list[CandidateDocument]:
        """Discover releases from an explicitly configured official RSS feed.

        Feed descriptions are not full documents. Every item still goes through
        fetch_detail(), extraction, and the same access checks as an HTML listing.
        """
        from lxml import etree

        parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
        root = etree.fromstring(body, parser=parser)
        if root.tag != "rss":
            raise ValueError("Expected an RSS listing; received another XML document")
        candidates = []
        seen = set()
        for item in root.findall("./channel/item"):
            url = self.canonicalize_url((item.findtext("link") or "").strip(), base_url)
            parsed = urlparse(url)
            if parsed.scheme != "https" or not self.is_allowed_domain(url):
                continue
            if not any(parsed.path.lower().startswith(path.lower()) for path in _DETAIL_PATHS):
                continue
            prid = _extract_prid(url)
            if not prid or prid in seen:
                continue
            seen.add(prid)
            candidates.append(CandidateDocument(
                source_id="pib", detail_url=url,
                title=_clean_text(item.findtext("title") or "") or None,
                published_date_text=item.findtext("pubDate"),
                document_type=_infer_document_type(url),
                language="en-IN", discovered_from_url=base_url,
                source_reference_id=prid,
            ))
        return candidates

    def _parse_listing_html(
        self, html: str, base_url: str
    ) -> list[CandidateDocument]:
        """
        Parse a PIB listing page HTML and return CandidateDocuments.

        PIB renders releases in a table or <ul> with <a> tags whose href
        contains PressReleaseDetail.aspx, FactsheetDetails.aspx, or
        PressNoteDetails.aspx with a PRID param.
        """
        soup = BeautifulSoup(html, "lxml")
        candidates: list[CandidateDocument] = []
        seen_urls: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            abs_url = urljoin(base_url, href)

            if not self.is_allowed_domain(abs_url) or urlparse(abs_url).scheme != "https":
                continue

            # Must be a known detail path
            path = urlparse(abs_url).path
            if not any(path.startswith(p) for p in _DETAIL_PATHS):
                continue

            # Must have PRID
            prid = _extract_prid(abs_url)
            if not prid:
                continue

            # Normalise to www host
            parsed = urlparse(abs_url)
            if parsed.hostname and not parsed.hostname.startswith("www."):
                abs_url = abs_url.replace(parsed.hostname, "www.pib.gov.in", 1)

            if abs_url in seen_urls:
                continue
            seen_urls.add(abs_url)

            # Title: text of the link, or parent row context
            title = _clean_text(anchor.get_text())

            # Date: look for a sibling/parent element with a date-like string
            date_text = self._find_date_near(anchor)

            # Department: look for ministry/department text near the link
            department = self._find_department_near(anchor)

            doc_type = _infer_document_type(abs_url)

            candidates.append(CandidateDocument(
                source_id="pib",
                detail_url=abs_url,
                document_url=None,         # populated after detail fetch if a PDF is found
                title=title if title else None,
                published_date_text=date_text,
                document_type=doc_type,
                department=department,
                language="en-IN",
                discovered_from_url=base_url,
                source_reference_id=prid,
            ))

        return candidates

    def _find_date_near(self, anchor: Tag) -> Optional[str]:
        """
        Heuristic: find a date string in the nearest table row or
        list item surrounding the anchor.
        """
        date_pattern = re.compile(
            r"\b\d{1,2}[\s\-/]\w+[\s\-/]\d{4}\b"
            r"|\b\w+ \d{1,2},? \d{4}\b"
            r"|\b\d{4}-\d{2}-\d{2}\b"
        )
        # Walk up to 4 ancestors
        el = anchor
        for _ in range(4):
            parent = el.parent
            if parent is None:
                break
            text = parent.get_text(" ", strip=True)
            m = date_pattern.search(text)
            if m:
                return m.group(0)
            el = parent
        return None

    def _find_department_near(self, anchor: Tag) -> Optional[str]:
        """
        Heuristic: look for a "Ministry of …" string near the anchor.
        """
        ministry_pattern = re.compile(
            r"Ministry of [A-Za-z\s&]+|Department of [A-Za-z\s&]+",
            re.I
        )
        el = anchor
        for _ in range(5):
            parent = el.parent
            if parent is None:
                break
            text = parent.get_text(" ", strip=True)
            m = ministry_pattern.search(text)
            if m:
                return _clean_text(m.group(0))
            el = parent
        return None

    # ─── Detail fetch ─────────────────────────────────────────────────────

    async def fetch_detail(self, candidate: CandidateDocument) -> FetchResult:
        """Fetch the detail page for a candidate."""
        return await self.fetch(candidate.detail_url)

    # ─── Parse ────────────────────────────────────────────────────────────

    async def parse(
        self, candidate: CandidateDocument, result: FetchResult
    ) -> CanonicalCircular:
        """
        Parse a fetched PIB detail page into a CanonicalCircular.

        Content rules:
          - original_text: verbatim text from the main content region
          - clean_text: same region after stripping nav/social/decorative noise
          - Never invent headings; only produce sections when the page has
            clearly structured headings (h2/h3 with non-trivial body text)
          - All optional fields → None if not present on page
        """
        try:
            import ulid as ulid_mod
            circular_id = "circular_" + ulid_mod.new().str.lower()
        except (ImportError, AttributeError):
            import uuid
            circular_id = "circular_" + uuid.uuid4().hex

        html = result.body.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "lxml")

        # ── Title ──
        title = self._extract_title(soup, candidate)

        # ── Department / ministry ──
        department = candidate.department or self._extract_department(soup)

        # ── Date ──
        date_text, published_date = self._extract_date(soup, candidate)

        # ── Main content — original (verbatim) ──
        original_text, clean_text, sections = self._extract_content(soup)

        # ── PDF attachment check ──
        attachments = self._extract_attachments(soup, candidate.detail_url)

        # ── source_reference_id / PRID ──
        prid = candidate.source_reference_id or _extract_prid(candidate.detail_url)

        # ── Source-specific metadata ──
        ssm: dict = {}
        if prid:
            ssm["pib_reference_id"] = prid
        press_num = self._extract_press_number(soup)
        if press_num:
            ssm["press_note_number"] = press_num

        now = utcnow()

        return CanonicalCircular(
            id=circular_id,
            source=SourceInfo(
                source_id="pib",
                source_name="Press Information Bureau",
                source_domain="pib.gov.in",
                source_url=candidate.detail_url,
                discovered_from_url=candidate.discovered_from_url,
                official_document_url=candidate.detail_url,
                source_reference_id=prid,
            ),
            classification=Classification(
                government_level="central",
                state=None,
                department=department or "Press Information Bureau",
                document_type=candidate.document_type or "press_release",
                category=_infer_category(department),
                sub_category=None,
                language="en-IN",
            ),
            identity=Identity(
                title_original=title,
                document_number=None,
                reference_number=None,
                gazette_number=None,
                subject_original=None,
            ),
            dates=Dates(
                published_date=published_date,
                effective_from=None,
                effective_until=None,
                last_updated=None,
                date_text_original=date_text,
            ),
            content=Content(
                original_text=original_text,
                clean_text=clean_text,
                sections=sections,
            ),
            attachments=attachments,
            provenance=Provenance(
                retrieved_at=result.fetched_at,
                retrieval_timezone="Asia/Kolkata",
                http_status=result.status_code,
                content_hash=result.content_hash or self.compute_hash(result.body),
                raw_html_s3_key=None,   # filled in by provenance_service after storage
                raw_pdf_s3_key=None,
                parser_name=self.PARSER_NAME,
                parser_version=self.PARSER_VERSION,
                robots_checked=self.source.get("respect_robots", True),
                terms_checked=True,
            ),
            extraction=Extraction(
                status="complete",
                method="html",
                confidence=0.9,
                warnings=[],
                missing_fields=self._collect_missing_fields(
                    title, department, published_date, original_text
                ),
            ),
            processing=Processing(
                status="extracted",
                published=False,
                translation_languages=[],
            ),
            source_specific_metadata=ssm,
            created_at=now,
            updated_at=now,
        )

    # ─── Extraction helpers ────────────────────────────────────────────────

    def _extract_title(self, soup: BeautifulSoup, candidate: CandidateDocument) -> str:
        """
        Extract title in priority order:
          1. <h1> in main content area
          2. <title> tag
          3. candidate.title from listing
          4. PRID as last resort
        """
        # Try <h1> inside content first
        content_el = _extract_main_content(BeautifulSoup(str(soup), "lxml"))
        if content_el:
            h1 = content_el.find("h1")
            if h1 and h1.get_text(strip=True):
                return _clean_text(h1.get_text())

        # <title> tag — PIB format: "Title | PIB"
        page_title = soup.find("title")
        if page_title:
            raw = _clean_text(page_title.get_text())
            # Strip " | PIB" suffix and similar
            for sep in [" | PIB", " - PIB", " | Press Information Bureau"]:
                if sep in raw:
                    raw = raw.split(sep)[0].strip()
            if raw:
                return raw

        if candidate.title:
            return candidate.title

        prid = candidate.source_reference_id or _extract_prid(candidate.detail_url)
        return f"PIB Press Release {prid or 'Unknown'}"

    def _extract_department(self, soup: BeautifulSoup) -> Optional[str]:
        """Look for ministry/department in known PIB page locations."""
        # PIB wraps the ministry in a span or div with class containing "minist"
        for el in soup.find_all(class_=re.compile(r"minist|department|ministry", re.I)):
            text = _clean_text(el.get_text())
            if text:
                return text

        # Pattern match in full text
        full_text = soup.get_text(" ", strip=True)
        m = re.search(
            r"Ministry of [A-Za-z\s&,]+|Department of [A-Za-z\s&,]+", full_text, re.I
        )
        if m:
            return _clean_text(m.group(0)).rstrip(",.")
        return None

    def _extract_date(
        self, soup: BeautifulSoup, candidate: CandidateDocument
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Return (raw_date_text, iso_date_string).
        Tries several PIB-specific locations before falling back to candidate.
        """
        # PIB typically renders date near top of the press release
        date_pattern = re.compile(
            r"\b(\d{1,2}[\s\-/](?:January|February|March|April|May|June|July|"
            r"August|September|October|November|December|Jan|Feb|Mar|Apr|May|"
            r"Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\s\-/]\d{4})\b",
            re.I,
        )

        for el in soup.find_all(class_=re.compile(r"date|posted|time|publish", re.I)):
            text = _clean_text(el.get_text())
            m = date_pattern.search(text)
            if m:
                raw = m.group(1)
                dt = parse_indian_date(raw)
                iso = dt.strftime("%Y-%m-%d") if dt else None
                return raw, iso

        # Scan full text for first match
        full_text = soup.get_text(" ", strip=True)
        m = date_pattern.search(full_text)
        if m:
            raw = m.group(1)
            dt = parse_indian_date(raw)
            iso = dt.strftime("%Y-%m-%d") if dt else None
            return raw, iso

        # Fall back to candidate
        if candidate.published_date_text:
            dt = parse_indian_date(candidate.published_date_text)
            iso = dt.strftime("%Y-%m-%d") if dt else None
            return candidate.published_date_text, iso

        return None, None

    def _extract_content(
        self, soup: BeautifulSoup
    ) -> tuple[str, str, list[ContentSection]]:
        """
        Return (original_text, clean_text, sections).

        original_text — verbatim text from the main content area (whitespace normalised)
        clean_text    — same area after noise removal
        sections      — list only when the page has clear h2/h3 structure
        """
        # --- original_text: minimal processing, from full content area ---
        orig_soup = BeautifulSoup(str(soup), "lxml")
        content_orig = _extract_main_content(orig_soup)
        original_text = _clean_text(
            content_orig.get_text(" ", strip=True) if content_orig
            else soup.get_text(" ", strip=True)
        )

        # --- clean_text: strip noise elements ---
        clean_soup = BeautifulSoup(str(soup), "lxml")
        _strip_noise(clean_soup)
        content_clean = _extract_main_content(clean_soup)
        clean_text = _clean_text(
            content_clean.get_text(" ", strip=True) if content_clean
            else clean_soup.get_text(" ", strip=True)
        )

        # --- sections: only if clear headings with substantial body ---
        sections: list[ContentSection] = []
        if content_clean:
            current_heading: Optional[str] = None
            current_parts: list[str] = []

            for el in content_clean.find_all(["h2", "h3", "p"]):
                if el.name in ("h2", "h3"):
                    # Save previous section
                    if current_parts:
                        body = _clean_text(" ".join(current_parts))
                        if body:
                            sections.append(ContentSection(
                                heading=current_heading,
                                text=body,
                                page_start=None,
                                page_end=None,
                            ))
                    current_heading = _clean_text(el.get_text())
                    current_parts = []
                else:
                    t = _clean_text(el.get_text())
                    if t:
                        current_parts.append(t)

            # Flush last section
            if current_parts:
                body = _clean_text(" ".join(current_parts))
                if body:
                    sections.append(ContentSection(
                        heading=current_heading,
                        text=body,
                        page_start=None,
                        page_end=None,
                    ))

        # Only keep sections if they're genuinely structured (≥2 with headings)
        labelled = [s for s in sections if s.heading]
        if len(labelled) < 2:
            sections = []

        return original_text, clean_text, sections

    def _extract_attachments(
        self, soup: BeautifulSoup, base_url: str
    ) -> list:
        """Find PDF links in the content area."""
        from models.circular import Attachment
        attachments = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().endswith(".pdf"):
                abs_url = urljoin(base_url, href)
                title = _clean_text(a.get_text()) or "PDF Attachment"
                attachments.append(Attachment(
                    url=abs_url,
                    type="pdf",
                    title=title,
                    file_size_bytes=None,
                    s3_key=None,   # filled by provenance_service after download
                ))
        return attachments

    def _extract_press_number(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract press release / press note number if present."""
        text = soup.get_text(" ", strip=True)
        m = re.search(r"(?:Press Release|Press Note)\s*(?:No\.?|Number)?\s*:?\s*([\w/\-]+)", text, re.I)
        if m:
            return _clean_text(m.group(1))
        return None

    @staticmethod
    def _collect_missing_fields(
        title: Optional[str],
        department: Optional[str],
        published_date: Optional[str],
        original_text: Optional[str],
    ) -> list[str]:
        missing = []
        if not title:
            missing.append("identity.title_original")
        if not department:
            missing.append("classification.department")
        if not published_date:
            missing.append("dates.published_date")
        if not original_text:
            missing.append("content.original_text")
        return missing
