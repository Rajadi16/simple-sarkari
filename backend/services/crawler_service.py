"""
Crawler service — orchestrates a full crawl run for one source.

Person 1 (Aditya) — Ingestion & Source Verification

Pipeline per run:
  1. Load source config from DB (or accept a pre-loaded Source dict)
  2. Robots.txt check via security module (already done per-URL in base adapter)
  3. Instantiate the right adapter from ADAPTER_REGISTRY
  4. Call adapter.fetch_listing() → list[CandidateDocument]
  5. For each candidate:
       a. Dedup check (content_hash + source_reference_id in Mongo)
       b. fetch_detail() → FetchResult
       c. If blocked  → save stub with status="manual_review_required"
       d. If success  → adapter.parse() → CanonicalCircular
       e. store_raw() → populate provenance s3_key fields
       f. save_circular() → upsert into Mongo
  6. Respect crawl_policy limits throughout
  7. Update CrawlRun record with telemetry

On any blocked/failed fetch: record reason, move on — never retry automatically,
never escalate to proxy/stealth tricks.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase

from config import get_settings
from lib.dates import utcnow
from models.source import CrawlRun, Source
from crawlers.source_config import normalize_source_config
from models.circular import (
    CanonicalCircular,
    CandidateDocument,
    SourceInfo,
    Classification,
    Identity,
    Dates,
    Content,
    Provenance,
    Extraction,
    Processing,
)
from services.provenance_service import (
    compute_content_hash,
    is_duplicate,
    store_raw,
    save_circular,
    build_provenance,
    log_ingestion_event,
)

# ─── Adapter registry ────────────────────────────────────────────────────────
# Maps source adapter key → adapter class.
# Populated lazily to avoid circular imports at module load time.

ADAPTER_REGISTRY: dict[str, type] = {}


def _load_adapters() -> None:
    from crawlers.pib import PibAdapter
    ADAPTER_REGISTRY["pib"] = PibAdapter

    # Other adapters — stubs exist in repo; register so they don't break imports
    try:
        from crawlers.dopt import DoptAdapter
        ADAPTER_REGISTRY["dopt"] = DoptAdapter
    except Exception:
        pass
    try:
        from crawlers.egazette import EGazetteAdapter
        ADAPTER_REGISTRY["egazette"] = EGazetteAdapter
    except Exception:
        pass
    try:
        from crawlers.doe import DoeAdapter
        ADAPTER_REGISTRY["doe"] = DoeAdapter
    except Exception:
        pass
    try:
        from crawlers.india_gov import IndiaGovAdapter
        ADAPTER_REGISTRY["india_gov"] = IndiaGovAdapter
    except Exception:
        pass
    try:
        from crawlers.karnataka_egazette import KarnatakaGazetteAdapter
        ADAPTER_REGISTRY["karnataka_egazette"] = KarnatakaGazetteAdapter
    except Exception:
        pass
    try:
        from crawlers.karnataka_dpar import KarnatakaDparAdapter
        ADAPTER_REGISTRY["karnataka_dpar"] = KarnatakaDparAdapter
    except Exception:
        pass
    try:
        from crawlers.karnataka_finance import KarnatakaFinanceAdapter
        ADAPTER_REGISTRY["karnataka_finance"] = KarnatakaFinanceAdapter
    except Exception:
        pass
    try:
        from crawlers.karnataka_itbt import KarnatakaItbtAdapter
        ADAPTER_REGISTRY["karnataka_itbt"] = KarnatakaItbtAdapter
    except Exception:
        pass

    # ── New Karnataka / education adapters ───────────────────────────────────
    try:
        from crawlers.drupal_karnataka import DrupalKarnatakaAdapter
        for source_id in ("bescom", "kptcl", "kerc", "mescom", "bwssb",
                          "kuwsdb", "kspcb", "kseab", "gba", "ksrtc"):
            ADAPTER_REGISTRY[source_id] = DrupalKarnatakaAdapter
    except Exception:
        pass
    try:
        from crawlers.wordpress_karnataka import WordPressKarnatakaAdapter
        ADAPTER_REGISTRY["vtu"] = WordPressKarnatakaAdapter
        ADAPTER_REGISTRY["karnataka_gov"] = WordPressKarnatakaAdapter
    except Exception:
        pass
    try:
        from crawlers.ssp_karnataka import SspKarnatakaAdapter
        ADAPTER_REGISTRY["ssp_karnataka"] = SspKarnatakaAdapter
    except Exception:
        pass
    try:
        from crawlers.sevasindhu import SevaSindhuAdapter
        ADAPTER_REGISTRY["sevasindhu"] = SevaSindhuAdapter
    except Exception:
        pass


def get_adapter(adapter_name: str, source_config: dict):
    """Instantiate the adapter for the given source key."""
    if not ADAPTER_REGISTRY:
        _load_adapters()
    cls = ADAPTER_REGISTRY.get(adapter_name)
    if cls is None:
        raise ValueError(
            f"No adapter registered for '{adapter_name}'. "
            f"Available: {list(ADAPTER_REGISTRY.keys())}"
        )
    return cls(source_config)


# ─── Source loading ───────────────────────────────────────────────────────────

async def load_source(db: AsyncIOMotorDatabase, source_id: str) -> Optional[dict]:
    """
    Load source config from the `sources` collection.
    Returns an independent, flattened adapter configuration or None.
    """
    doc = await db.sources.find_one({"source_id": source_id})
    return normalize_source_config(doc) if doc else None


async def ensure_pib_source(db: AsyncIOMotorDatabase) -> None:
    """Seed the PIB source into the DB if it doesn't exist yet. Idempotent."""
    from models.source import PIB_SOURCE
    existing = await db.sources.find_one({"source_id": "pib"})
    if not existing:
        doc = PIB_SOURCE.model_dump(mode="json")
        doc["_id"] = "pib"
        await db.sources.insert_one(doc)


async def ensure_all_sources(db: AsyncIOMotorDatabase) -> None:
    """
    Seed all new Karnataka / education sources into the DB.
    Idempotent — skips any source_id already present.
    """
    from models.source import ALL_NEW_SOURCES
    for source in ALL_NEW_SOURCES:
        existing = await db.sources.find_one({"source_id": source.source_id})
        if not existing:
            doc = source.model_dump(mode="json")
            doc["_id"] = source.source_id
            await db.sources.insert_one(doc)


# ─── Crawl run record helpers ─────────────────────────────────────────────────

async def _create_crawl_run(
    db: AsyncIOMotorDatabase, source_id: str
) -> CrawlRun:
    run = CrawlRun(
        id=str(uuid.uuid4()),
        source_id=source_id,
        status="running",
        started_at=utcnow(),
    )
    doc = run.model_dump(mode="json")
    doc["_id"] = run.id
    await db.crawl_runs.insert_one(doc)
    return run


async def _update_crawl_run(
    db: AsyncIOMotorDatabase, run: CrawlRun, **updates
) -> None:
    await db.crawl_runs.update_one(
        {"_id": run.id},
        {"$set": updates},
    )


# ─── Blocked-fetch stub builder ───────────────────────────────────────────────

def _build_blocked_circular(
    candidate: CandidateDocument,
    source_doc: dict,
    block_reason: str,
    http_status: Optional[int],
    retrieved_at: datetime,
) -> CanonicalCircular:
    """
    Build a minimal CanonicalCircular with status='manual_review_required'
    for a fetch that was blocked/failed.

    Only populates fields we actually know — never invents values.
    content.original_text is set to empty string (not null) to keep the
    schema valid; extraction.status = 'failed' signals the problem.
    """
    circular_id = "circular_" + uuid.uuid4().hex
    now = utcnow()

    # Stub content hash from the candidate URL so dedup still works
    stub_hash = compute_content_hash(candidate.detail_url.encode())

    return CanonicalCircular(
        id=circular_id,
        source=SourceInfo(
            source_id=candidate.source_id,
            source_name=source_doc.get("name", candidate.source_id),
            source_domain=source_doc.get("base_domains", [""])[0],
            source_url=candidate.detail_url,
            discovered_from_url=candidate.discovered_from_url,
            official_document_url=candidate.detail_url,
            source_reference_id=candidate.source_reference_id,
        ),
        classification=Classification(
            government_level=source_doc.get("government_level", "central"),
            state=source_doc.get("state"),
            department=candidate.department or source_doc.get("name", "Unknown"),
            document_type=candidate.document_type or "unknown",
            language=candidate.language or "en-IN",
        ),
        identity=Identity(
            title_original=candidate.title or f"[Blocked] {candidate.detail_url}",
        ),
        dates=Dates(
            date_text_original=candidate.published_date_text,
        ),
        content=Content(
            original_text="",   # empty — blocked before extraction
            clean_text=None,
            sections=[],
        ),
        provenance=Provenance(
            retrieved_at=retrieved_at,
            retrieval_timezone="Asia/Kolkata",
            http_status=http_status,
            content_hash=stub_hash,
            robots_checked=source_doc.get("respect_robots", True),
            terms_checked=True,
        ),
        extraction=Extraction(
            status="failed",
            method="html",
            confidence=0.0,
            warnings=[f"blocked:{block_reason}"],
            missing_fields=["content.original_text"],
        ),
        processing=Processing(
            status="manual_review_required",
            published=False,
        ),
        source_specific_metadata={"block_reason": block_reason},
        created_at=now,
        updated_at=now,
    )


# ─── Single-URL ingestion (used by both crawler and /url endpoint) ────────────

async def _store_primary_capture(circular: CanonicalCircular, result) -> None:
    """Store fetched PDFs once, with the right extension and provenance field."""
    is_pdf = result.body.startswith(b"%PDF-") or "pdf" in (result.content_type or "").lower()
    extension = "pdf" if is_pdf else "html"
    key, _s3_backed = await store_raw(circular.id, result.body, extension)
    if is_pdf:
        circular.provenance.raw_pdf_s3_key = key
        for attachment in circular.attachments:
            if attachment.url == result.url and attachment.type == "pdf":
                attachment.s3_key = key
                attachment.file_size_bytes = len(result.body)
    else:
        circular.provenance.raw_html_s3_key = key
    circular.provenance.content_hash = result.content_hash or compute_content_hash(result.body)


def _require_extracted_text(circular: CanonicalCircular) -> None:
    """Keep failed/empty extraction out of the automatic simplification path."""
    if not (circular.content.original_text or "").strip() or circular.extraction.status == "failed":
        circular.processing.status = "manual_review_required"


async def ingest_single_url(
    db: AsyncIOMotorDatabase,
    url: str,
    source_id: str,
    discovered_from_url: Optional[str] = None,
) -> CanonicalCircular:
    """
    Fetch, extract, and store a single URL.

    Used by:
      - crawler_service.run_crawl()  (for each candidate)
      - ingestion_worker.process_url_ingestion()  (manual /url endpoint)

    Returns the CanonicalCircular (status = "extracted" or
    "manual_review_required").
    """
    source_doc = await load_source(db, source_id)
    if source_doc is None:
        # Only PIB has an implicit seed. Other IDs require their own registry entry.
        if source_id != "pib":
            raise ValueError(f"Source '{source_id}' not found in DB")
        from models.source import PIB_SOURCE
        source_doc = PIB_SOURCE.to_crawler_config()

    adapter = get_adapter(source_doc.get("adapter", source_id), source_doc)

    try:
        async with asyncio.timeout(get_settings().crawler_run_timeout_seconds):
            candidate = CandidateDocument(
                source_id=source_id,
                detail_url=url,
                discovered_from_url=discovered_from_url,
                source_reference_id=None,
            )

            # Try to extract PRID from the URL for dedup purposes
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(url).query)
            prid_val = qs.get("PRID") or qs.get("prid")
            if prid_val:
                candidate.source_reference_id = f"PRID={prid_val[0]}"

            fetch_result = await adapter.fetch_detail(candidate)
            retrieved_at = fetch_result.fetched_at

            # ── Blocked fetch ──
            if fetch_result.blocked:
                # Dedup blocked stubs by source_reference_id (PRID) — don't create
                # a new stub every time the same URL is re-attempted while still blocked.
                if candidate.source_reference_id:
                    existing_blocked = await db.circulars.find_one(
                        {
                            "source.source_reference_id": candidate.source_reference_id,
                            "processing.status": "manual_review_required",
                        },
                        projection={"_id": 1},
                    )
                    if existing_blocked:
                        existing = await db.circulars.find_one({"_id": existing_blocked["_id"]})
                        if existing:
                            existing.pop("_id", None)
                            return CanonicalCircular(**existing)

                circular = _build_blocked_circular(
                    candidate,
                    source_doc,
                    fetch_result.block_reason or "unknown",
                    fetch_result.status_code or None,
                    retrieved_at,
                )
                await save_circular(db, circular)
                await log_ingestion_event(
                    db,
                    event_type="fetch_blocked",
                    circular_id=circular.id,
                    source_id=source_id,
                    detail={"url": url, "reason": fetch_result.block_reason},
                )
                return circular

            if fetch_result.not_modified:
                existing = await db.circulars.find_one({
                    "source.source_id": source_id,
                    "source.source_url": url,
                    "processing.status": {"$ne": "manual_review_required"},
                })
                if existing:
                    existing.pop("_id", None)
                    return CanonicalCircular(**existing)
                adapter.invalidate_fetch_cache()
                raise ValueError("HTTP 304 without a stored document; no response body to extract")

            # ── Dedup check ──
            if fetch_result.content_hash and await is_duplicate(db, fetch_result.content_hash):
                # Return the existing document rather than a new stub
                existing = await db.circulars.find_one(
                    {"provenance.content_hash": fetch_result.content_hash}
                )
                if existing:
                    # Re-hydrate as CanonicalCircular — strip Mongo _id first
                    existing.pop("_id", None)
                    return CanonicalCircular(**existing)
                # Shouldn't happen, but if it does fall through to re-parse

            # ── Parse ──
            circular = await adapter.parse(candidate, fetch_result)

            await _store_primary_capture(circular, fetch_result)

            # ── Handle any PDF attachments ──
            for attachment in circular.attachments:
                if attachment.type == "pdf" and attachment.url and attachment.s3_key is None:
                    pdf_result = await adapter.fetch(attachment.url)
                    if not pdf_result.blocked and pdf_result.body:
                        pdf_key, pdf_s3 = await store_raw(circular.id, pdf_result.body, "pdf")
                        attachment.s3_key = pdf_key
                        attachment.file_size_bytes = len(pdf_result.body)
                        # If we got a PDF and there's no HTML text, extract from PDF
                        if not circular.content.original_text:
                            from services.extraction_service import extract_pdf, build_content, build_extraction
                            pdf_data = extract_pdf(pdf_result.body)
                            circular.content = build_content(pdf_data)
                            circular.extraction = build_extraction(pdf_data)
                            circular.provenance.raw_pdf_s3_key = pdf_key
                        circular.processing.status = "extracted"

            # ── Save ──
            _require_extracted_text(circular)
            if circular.processing.status == "manual_review_required":
                adapter.invalidate_fetch_cache()
            await save_circular(db, circular)
            await log_ingestion_event(
                db,
                event_type="circular_extracted",
                circular_id=circular.id,
                source_id=source_id,
                detail={"url": url, "status": circular.processing.status},
            )

            return circular
    except BaseException:
        adapter.invalidate_fetch_cache()
        raise
    finally:
        await asyncio.wait_for(adapter.close(), timeout=5)


async def run_crawl(
    db: AsyncIOMotorDatabase,
    source_id: str,
    max_pages: int = 5,
    max_documents: int = 50,
    run_id: Optional[str] = None,
) -> CrawlRun:
    """Run once within a deadline and persist a truthful terminal outcome.

    A failed run can contain documents saved before the failure. Counters are
    retained; blocked/empty listings must not masquerade as successful crawls.
    """
    if run_id is not None:
        doc = await db.crawl_runs.find_one({"_id": run_id})
        if doc is None:
            raise ValueError(f"Crawl run '{run_id}' not found in DB")
        run = CrawlRun.model_validate(doc)
        run.status = "running"
        await _update_crawl_run(db, run, status="running")
    else:
        run = await _create_crawl_run(db, source_id)

    adapter = None
    budget = get_settings().crawler_run_timeout_seconds
    try:
        async with asyncio.timeout(budget):
            source_doc = await load_source(db, source_id)
            if source_doc is None:
                raise ValueError(f"Source '{source_id}' not found in DB")
            if not source_doc.get("enabled", True):
                raise ValueError(f"Source '{source_id}' is paused or disabled")
            source_doc["max_pages_per_run"] = min(
                max_pages, source_doc.get("max_pages_per_run", max_pages)
            )
            source_doc["max_documents_per_run"] = min(
                max_documents, source_doc.get("max_documents_per_run", max_documents)
            )
            if min(source_doc["max_pages_per_run"], source_doc["max_documents_per_run"]) < 1:
                raise ValueError("Crawl page and document limits must be positive")
            adapter = get_adapter(source_doc.get("adapter", source_id), source_doc)
            await _crawl_documents(db, run, source_doc, adapter)
    except TimeoutError:
        run.errors.append({"reason": "crawl_timeout", "error": f"Crawl exceeded {budget:g}s; stopped without rerunning"})
    except asyncio.CancelledError:
        run.errors.append({"reason": "crawl_cancelled", "error": "Crawl was cancelled"})
        raise
    except Exception as exc:
        run.errors.append({"reason": "crawl_error", "error": f"{type(exc).__name__}: {exc}"})
    finally:
        if adapter is not None:
            if run.errors:
                adapter.invalidate_fetch_cache()
            try:
                await asyncio.wait_for(adapter.close(), timeout=5)
            except Exception as exc:
                run.errors.append({"reason": "cleanup_error", "error": str(exc)})
        run.status = "failed" if run.errors else "completed"
        run.completed_at = utcnow()
        await asyncio.wait_for(_update_crawl_run(
            db, run,
            **run.model_dump(mode="json", exclude={"id", "source_id", "started_at"}),
        ), timeout=5)
    return run


async def _crawl_documents(db, run: CrawlRun, source_doc: dict, adapter) -> None:
    source_id = run.source_id
    # ── Listing ──
    try:
        candidates = await adapter.fetch_listing()
    finally:
        run.pages_fetched = sum(event["http_status"] > 0 for event in adapter.fetch_events)
    listing_events = list(adapter.fetch_events)
    for event in listing_events:
        if event["blocked"]:
            run.blocked_requests += 1
            run.errors.append(dict(event, stage="listing"))
    if run.errors:
        return
    if not candidates:
        if listing_events and all(event["not_modified"] for event in listing_events):
            return  # unchanged listings are an explicit no-op
        run.errors.append({
            "stage": "listing", "reason": "no_document_links",
            "error": "No documents discovered. Inspect the listing or use manual ingestion; do not rerun automatically.",
        })
        return
    run.documents_discovered = len(candidates)
    await _update_crawl_run(
        db, run, documents_discovered=run.documents_discovered
    )

    errors = run.errors
    docs_processed = 0

    for candidate in candidates[:source_doc["max_documents_per_run"]]:
        if docs_processed >= source_doc["max_documents_per_run"]:
            break

        # Dedup by source_reference_id first (fast path — no fetch needed)
        if candidate.source_reference_id:
            dup = await db.circulars.find_one(
                {"source.source_id": source_id,
                 "source.source_reference_id": candidate.source_reference_id,
                 "processing.status": {"$ne": "manual_review_required"}},
                projection={"_id": 1},
            )
            if dup:
                run.documents_duplicate += 1
                continue

        # ── Fetch detail ──
        fetch_result = await adapter.fetch_detail(candidate)
        retrieved_at = fetch_result.fetched_at

        if fetch_result.blocked:
            # Record block — do not retry
            blocked_circ = _build_blocked_circular(
                candidate,
                source_doc,
                fetch_result.block_reason or "unknown",
                fetch_result.status_code or None,
                retrieved_at,
            )
            await save_circular(db, blocked_circ)
            await log_ingestion_event(
                db,
                event_type="fetch_blocked",
                circular_id=blocked_circ.id,
                source_id=source_id,
                detail={
                    "url": candidate.detail_url,
                    "reason": fetch_result.block_reason,
                },
            )
            run.blocked_requests += 1
            errors.append({
                "url": candidate.detail_url,
                "reason": fetch_result.block_reason,
                "http_status": fetch_result.status_code,
                "error_detail": fetch_result.error_detail,
                "stage": "detail",
            })
            docs_processed += 1
            break  # terminal failure: no repeated requests to a rejecting source

        if fetch_result.not_modified:
            run.documents_duplicate += 1
            continue

        # ── Dedup by content hash ──
        if fetch_result.content_hash:
            if await is_duplicate(db, fetch_result.content_hash):
                run.documents_duplicate += 1
                continue

        # ── Parse ──
        try:
            circular = await adapter.parse(candidate, fetch_result)
        except Exception as exc:
            errors.append({
                "url": candidate.detail_url,
                "reason": f"parse_error: {exc}",
            })
            docs_processed += 1
            continue

        await _store_primary_capture(circular, fetch_result)

        # ── PDF attachments ──
        for attachment in circular.attachments:
            if attachment.type == "pdf" and attachment.url and attachment.s3_key is None:
                pdf_result = await adapter.fetch(attachment.url)
                if pdf_result.blocked:
                    run.blocked_requests += 1
                    errors.append({"stage": "attachment", "url": attachment.url,
                                   "reason": pdf_result.block_reason,
                                   "http_status": pdf_result.status_code,
                                   "error_detail": pdf_result.error_detail})
                    break
                if not pdf_result.blocked and pdf_result.body:
                    pdf_key, pdf_s3 = await store_raw(circular.id, pdf_result.body, "pdf")
                    attachment.s3_key = pdf_key
                    attachment.file_size_bytes = len(pdf_result.body)
                    if not circular.content.original_text:
                        from services.extraction_service import (
                            extract_pdf, build_content, build_extraction
                        )
                        pdf_data = extract_pdf(pdf_result.body)
                        circular.content = build_content(pdf_data)
                        circular.extraction = build_extraction(pdf_data)
                        circular.provenance.raw_pdf_s3_key = pdf_key

        # ── Save ──
        _require_extracted_text(circular)
        if circular.processing.status == "manual_review_required":
            errors.append({"stage": "extraction", "url": candidate.detail_url,
                           "reason": "extraction_incomplete"})
        await save_circular(db, circular)
        await log_ingestion_event(
            db,
            event_type="circular_extracted",
            circular_id=circular.id,
            source_id=source_id,
            detail={
                "url": candidate.detail_url,
                "status": circular.processing.status,
            },
        )
        run.documents_new += 1
        docs_processed += 1
        if adapter._halted is not None:
            break



# ─── Pasted-text ingestion ────────────────────────────────────────────────────

async def ingest_pasted_text(
    db: AsyncIOMotorDatabase,
    *,
    title: str,
    text: str,
    source_id: str,
    source_name: str,
    source_url: str,
    department: str,
    document_type: str = "circular",
    language: str = "en-IN",
    government_level: str = "central",
    state: Optional[str] = None,
    date_text: Optional[str] = None,
) -> CanonicalCircular:
    """
    Build and store a CanonicalCircular from pasted text — no network fetch.

    Provenance fields that require a real HTTP fetch (http_status,
    raw_html_s3_key) are null, not fabricated.
    """
    from services.extraction_service import extract_text, build_content, build_extraction
    from lib.dates import parse_indian_date

    circular_id = "circular_" + uuid.uuid4().hex
    now = utcnow()

    extraction_result = extract_text(text)
    content = build_content(extraction_result)
    extraction = build_extraction(extraction_result)

    content_hash = compute_content_hash(text.encode("utf-8"))

    # Dedup check on pasted text too
    if await is_duplicate(db, content_hash):
        existing = await db.circulars.find_one({"provenance.content_hash": content_hash})
        if existing:
            existing.pop("_id", None)
            return CanonicalCircular(**existing)

    # Parse date if provided
    published_date: Optional[str] = None
    if date_text:
        dt = parse_indian_date(date_text)
        if dt:
            published_date = dt.strftime("%Y-%m-%d")

    circular = CanonicalCircular(
        id=circular_id,
        source=SourceInfo(
            source_id=source_id,
            source_name=source_name,
            source_domain=source_url.split("/")[2] if "://" in source_url else source_url,
            source_url=source_url,
            discovered_from_url=None,
            official_document_url=source_url,
            source_reference_id=None,
        ),
        classification=Classification(
            government_level=government_level,
            state=state,
            department=department,
            document_type=document_type,
            language=language,
        ),
        identity=Identity(
            title_original=title,
        ),
        dates=Dates(
            published_date=published_date,
            date_text_original=date_text,
        ),
        content=content,
        attachments=[],
        provenance=Provenance(
            retrieved_at=now,
            retrieval_timezone="Asia/Kolkata",
            http_status=None,              # no HTTP fetch — pasted text
            content_hash=content_hash,
            raw_html_s3_key=None,          # no raw capture
            raw_pdf_s3_key=None,
            parser_name="pasted_text_v1",
            parser_version="1.0.0",
            robots_checked=False,          # no URL to check
            terms_checked=True,
        ),
        extraction=extraction,
        processing=Processing(
            status="extracted",
            published=False,
        ),
        source_specific_metadata={"ingestion_method": "pasted_text"},
        created_at=now,
        updated_at=now,
    )

    await save_circular(db, circular)
    await log_ingestion_event(
        db,
        event_type="circular_extracted",
        circular_id=circular.id,
        source_id=source_id,
        detail={"method": "pasted_text", "title": title},
    )

    return circular
