"""
Extraction service — converts raw HTML / PDF bytes into structured text.

Person 1 (Aditya) — Ingestion & Source Verification

Responsibilities:
  - HTML → original_text (verbatim) + clean_text (boilerplate stripped)
  - PDF  → text per page, with page numbers in ContentSection objects
  - Never invent section headings or reorder content
  - Returns dicts consumed by provenance_service / crawler_service to
    populate the Content and Extraction sub-objects of CanonicalCircular
"""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup

from models.circular import Content, ContentSection, Extraction

# Tags and class fragments that are pure navigation / chrome
_NOISE_TAGS = [
    "nav", "header", "footer", "script", "style", "noscript",
    "iframe", "figure", "picture", "video", "audio", "form",
    "aside", "menu",
]
_NOISE_CLASS_PATTERNS = re.compile(
    r"nav|header|footer|sidebar|breadcrumb|pagination|social|share|"
    r"widget|banner|carousel|slider|advertisement|advert|cookie|"
    r"popup|modal|overlay|topbar|toolbar|search-bar",
    re.I,
)


def _clean_whitespace(text: str) -> str:
    """Collapse runs of whitespace to single spaces; strip edges."""
    return re.sub(r"\s+", " ", text).strip()


# ─── HTML extraction ─────────────────────────────────────────────────────────

def extract_html(raw_html: bytes, url: str = "") -> dict:
    """
    Extract text and metadata from raw HTML bytes.

    Returns a dict with keys:
      original_text  — verbatim text of the main content region
      clean_text     — same region after nav/boilerplate removal
      sections       — list of ContentSection (only when clearly structured)
      title          — page <title> or first <h1>, or None
      warnings       — list of string warnings (e.g. "no main content found")
      missing_fields — list of field names that could not be populated
    """
    warnings: list[str] = []
    missing_fields: list[str] = []

    # ── Parse for original_text (minimal processing) ──
    orig_soup = BeautifulSoup(raw_html, "lxml")
    content_orig = _find_main_content(orig_soup)
    if content_orig is None:
        warnings.append("no_main_content_found_using_full_body")
        content_orig = orig_soup.find("body") or orig_soup
    original_text = _clean_whitespace(content_orig.get_text(" ", strip=True))

    # ── Parse for clean_text (noise stripped) ──
    clean_soup = BeautifulSoup(raw_html, "lxml")
    _strip_noise(clean_soup)
    content_clean = _find_main_content(clean_soup)
    if content_clean is None:
        content_clean = clean_soup.find("body") or clean_soup
    clean_text = _clean_whitespace(content_clean.get_text(" ", strip=True))

    # ── Title ──
    title = _extract_html_title(orig_soup)
    if not title:
        missing_fields.append("identity.title_original")

    # ── Sections (only when clearly structured h2/h3 hierarchy exists) ──
    sections = _extract_sections_html(content_clean)

    if not original_text:
        missing_fields.append("content.original_text")

    return {
        "original_text": original_text,
        "clean_text": clean_text,
        "sections": sections,
        "title": title,
        "warnings": warnings,
        "missing_fields": missing_fields,
        "method": "html",
    }


def _find_main_content(soup: BeautifulSoup):
    """
    Locate the primary content container using known selectors,
    falling back to the largest <div> by text length.
    """
    priority_selectors = [
        {"id": "content"},
        {"id": "MCE_Body"},
        {"id": "lblPRDetail"},
        {"class": "innner-page"},      # PIB typo — kept intentionally
        {"class": "inner-page"},
        {"id": "main-content"},
        {"id": "main"},
        {"class": "main-content"},
        {"class": "article-body"},
        {"class": "entry-content"},
        {"class": "post-content"},
        {"class": "release-content"},
        {"role": "main"},
    ]
    for selector in priority_selectors:
        el = soup.find(**selector)
        if el and len(el.get_text(strip=True)) > 150:
            return el

    # Fallback: largest <div> by text length (exclude tiny nav divs)
    best = None
    best_len = 0
    for div in soup.find_all("div"):
        t = div.get_text(strip=True)
        if len(t) > best_len and len(t) > 150:
            best_len = len(t)
            best = div
    return best


def _strip_noise(soup: BeautifulSoup) -> None:
    """Remove navigation / boilerplate elements in-place."""
    for tag in _NOISE_TAGS:
        for el in soup.find_all(tag):
            el.decompose()
    # Class-based noise
    for el in soup.find_all(True):
        classes = " ".join(el.get("class", []))
        if _NOISE_CLASS_PATTERNS.search(classes):
            el.decompose()


def _extract_html_title(soup: BeautifulSoup) -> Optional[str]:
    """Extract title from <title> tag or first <h1>."""
    page_title = soup.find("title")
    if page_title:
        raw = _clean_whitespace(page_title.get_text())
        # Strip common " | SiteName" suffixes
        for sep in [" | PIB", " - PIB", " | Press Information Bureau",
                    " | Government of India", " | India"]:
            if sep in raw:
                raw = raw.split(sep)[0].strip()
        if raw:
            return raw
    h1 = soup.find("h1")
    if h1:
        t = _clean_whitespace(h1.get_text())
        if t:
            return t
    return None


def _extract_sections_html(content_el) -> list[ContentSection]:
    """
    Return sections only when the content has ≥2 labelled headings.
    Never invents headings for unlabelled paragraphs.
    """
    if content_el is None:
        return []

    sections: list[ContentSection] = []
    current_heading: Optional[str] = None
    current_parts: list[str] = []

    for el in content_el.find_all(["h2", "h3", "h4", "p", "li"]):
        if el.name in ("h2", "h3", "h4"):
            # Flush previous section
            if current_parts:
                body = _clean_whitespace(" ".join(current_parts))
                if body:
                    sections.append(ContentSection(
                        heading=current_heading,
                        text=body,
                        page_start=None,
                        page_end=None,
                    ))
            current_heading = _clean_whitespace(el.get_text())
            current_parts = []
        else:
            t = _clean_whitespace(el.get_text())
            if t:
                current_parts.append(t)

    # Flush final section
    if current_parts:
        body = _clean_whitespace(" ".join(current_parts))
        if body:
            sections.append(ContentSection(
                heading=current_heading,
                text=body,
                page_start=None,
                page_end=None,
            ))

    # Only return if at least 2 sections have explicit headings
    labelled = [s for s in sections if s.heading]
    if len(labelled) < 2:
        return []

    return sections


# ─── PDF extraction ──────────────────────────────────────────────────────────

def extract_pdf(raw_pdf: bytes, filename: str = "document.pdf") -> dict:
    """
    Extract text and metadata from raw PDF bytes using PyMuPDF (fitz).

    Returns a dict with keys:
      original_text  — full concatenated text across all pages
      clean_text     — same as original_text (PDFs have no nav chrome)
      sections       — list of ContentSection, one per page, with page numbers
      title          — from PDF metadata or first non-empty line of page 1
      warnings       — e.g. "scanned_page_detected" for image-only pages
      missing_fields — field names that could not be populated
      page_count     — total pages in the document
      method         — "pdf"
    """
    import fitz  # PyMuPDF

    warnings: list[str] = []
    missing_fields: list[str] = []
    sections: list[ContentSection] = []
    page_texts: list[str] = []

    doc = fitz.open(stream=raw_pdf, filetype="pdf")
    page_count = doc.page_count

    # PDF metadata title
    meta_title: Optional[str] = None
    metadata = doc.metadata
    if metadata and metadata.get("title"):
        meta_title = _clean_whitespace(metadata["title"])

    for page_num in range(page_count):
        page = doc[page_num]
        text = page.get_text("text")  # type: ignore[attr-defined]

        if not text or not text.strip():
            # Possibly a scanned / image page
            warnings.append(f"scanned_page_detected_page_{page_num + 1}")
            continue

        cleaned_page = _clean_whitespace(text)
        page_texts.append(cleaned_page)

        sections.append(ContentSection(
            heading=f"Page {page_num + 1}",
            text=cleaned_page,
            page_start=page_num + 1,
            page_end=page_num + 1,
        ))

    doc.close()

    original_text = " ".join(page_texts)
    clean_text = original_text  # PDFs don't have nav/boilerplate chrome

    # Title: metadata → first non-trivial line of page 1
    title = meta_title
    if not title and page_texts:
        first_line = page_texts[0].split("\n")[0].strip() if "\n" in page_texts[0] else ""
        # Only use if it looks like a title (not a date/number line)
        if first_line and len(first_line) > 10 and not re.match(r"^\d", first_line):
            title = first_line[:200]

    if not original_text:
        missing_fields.append("content.original_text")
        warnings.append("no_text_extracted_from_pdf")

    return {
        "original_text": original_text,
        "clean_text": clean_text,
        "sections": sections,
        "title": title,
        "warnings": warnings,
        "missing_fields": missing_fields,
        "page_count": page_count,
        "method": "pdf",
    }


# ─── Pasted-text path ────────────────────────────────────────────────────────

def extract_text(raw_text: str) -> dict:
    """
    Process pasted text directly — no fetch, no HTML/PDF parsing.

    Still produces a properly shaped Content object with warnings/missing_fields
    so the caller can build a valid CanonicalCircular.
    """
    cleaned = _clean_whitespace(raw_text)
    warnings: list[str] = []
    missing_fields: list[str] = []

    if not cleaned:
        warnings.append("empty_text_provided")
        missing_fields.append("content.original_text")

    return {
        "original_text": cleaned,
        "clean_text": cleaned,
        "sections": [],
        "title": None,           # must be supplied by caller for text ingestion
        "warnings": warnings,
        "missing_fields": missing_fields,
        "method": "text",
    }


# ─── Confidence heuristic ────────────────────────────────────────────────────

def compute_extraction_confidence(result: dict) -> float:
    """
    Simple 0–1 confidence score based on what was extracted.

    Not a hard gate — just informational metadata for downstream review.
    """
    score = 1.0
    if "no_main_content_found" in " ".join(result.get("warnings", [])):
        score -= 0.2
    if result.get("missing_fields"):
        score -= 0.1 * len(result["missing_fields"])
    if "scanned_page_detected" in " ".join(result.get("warnings", [])):
        score -= 0.3
    original = result.get("original_text", "")
    if len(original) < 100:
        score -= 0.2
    return max(0.0, round(score, 2))


# ─── Build Content + Extraction model objects ────────────────────────────────

def build_content(result: dict) -> Content:
    """Convert an extraction result dict into a Content model object."""
    return Content(
        original_text=result.get("original_text", ""),
        clean_text=result.get("clean_text"),
        sections=result.get("sections", []),
    )


def build_extraction(result: dict) -> Extraction:
    """Convert an extraction result dict into an Extraction model object."""
    return Extraction(
        status="complete" if result.get("original_text") else "failed",
        method=result.get("method", "html"),
        confidence=compute_extraction_confidence(result),
        warnings=result.get("warnings", []),
        missing_fields=result.get("missing_fields", []),
    )
