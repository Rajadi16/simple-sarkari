"""
test_crawlers.py — Live connectivity + parser test for all 9 crawlers.

Tests each adapter's fetch_listing() and verifies:
  1. Listing page reachable (not blocked)
  2. At least 1 CandidateDocument returned
  3. fetch_detail() + parse() on the first candidate produces a valid
     CanonicalCircular with all required §4.4 fields populated

Usage:
  python test_crawlers.py           # test all adapters
  python test_crawlers.py pib       # test one adapter by name

Requires: MongoDB on localhost:27017, pip install -r requirements.txt
"""

import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):     print(f"    {GREEN}✓ {msg}{RESET}")
def fail(msg):   print(f"    {RED}✗ {msg}{RESET}")
def warn(msg):   print(f"    {YELLOW}⚠ {msg}{RESET}")
def info(msg):   print(f"    {CYAN}→ {msg}{RESET}")

# ── Adapter registry ──────────────────────────────────────────────────────────

ADAPTERS = {
    "pib": {
        "class": "crawlers.pib.PibAdapter",
        "source": {
            "source_id": "pib",
            "name": "Press Information Bureau",
            "base_domains": ["pib.gov.in", "www.pib.gov.in", "static.pib.gov.in"],
            "seed_urls": ["https://www.pib.gov.in/Allrel.aspx?reg=48&lang=1"],
            "adapter": "pib",
            "government_level": "central",
            "stop_on_403": True, "stop_on_429": True,
            "respect_robots": True, "request_delay_seconds": 2,
            "max_documents_per_run": 5, "max_pages_per_run": 1,
        },
    },
    "dopt": {
        "class": "crawlers.dopt.DoptAdapter",
        "source": {
            "source_id": "dopt",
            "name": "Department of Personnel and Training",
            "base_domains": ["dopt.gov.in", "www.dopt.gov.in"],
            "seed_urls": ["https://www.dopt.gov.in/orders-circulars"],
            "adapter": "dopt",
            "government_level": "central",
            "stop_on_403": True, "stop_on_429": True,
            "respect_robots": True, "request_delay_seconds": 2,
            "max_documents_per_run": 5, "max_pages_per_run": 1,
        },
    },
    "egazette": {
        "class": "crawlers.egazette.EGazetteAdapter",
        "source": {
            "source_id": "egazette",
            "name": "eGazette of India",
            "base_domains": ["egazette.gov.in", "www.egazette.gov.in"],
            "seed_urls": ["https://egazette.gov.in/(S(a))/default.aspx"],
            "adapter": "egazette",
            "government_level": "central",
            "stop_on_403": True, "stop_on_429": True,
            "respect_robots": True, "request_delay_seconds": 2,
            "max_documents_per_run": 5, "max_pages_per_run": 1,
        },
    },
    "doe": {
        "class": "crawlers.doe.DoeAdapter",
        "source": {
            "source_id": "doe",
            "name": "Department of Expenditure",
            "base_domains": ["doe.gov.in", "www.doe.gov.in"],
            "seed_urls": ["https://doe.gov.in/circulars"],
            "adapter": "doe",
            "government_level": "central",
            "stop_on_403": True, "stop_on_429": True,
            "respect_robots": True, "request_delay_seconds": 2,
            "max_documents_per_run": 5, "max_pages_per_run": 1,
        },
    },
    "india_gov": {
        "class": "crawlers.india_gov.IndiaGovAdapter",
        "source": {
            "source_id": "india_gov",
            "name": "India.gov.in National Portal",
            "base_domains": ["india.gov.in", "www.india.gov.in"],
            "seed_urls": ["https://www.india.gov.in/my-government/policies"],
            "adapter": "india_gov",
            "government_level": "central",
            "stop_on_403": True, "stop_on_429": True,
            "respect_robots": True, "request_delay_seconds": 2,
            "max_documents_per_run": 5, "max_pages_per_run": 1,
        },
    },
    "karnataka_egazette": {
        "class": "crawlers.karnataka_egazette.KarnatakaGazetteAdapter",
        "source": {
            "source_id": "karnataka_egazette",
            "name": "Karnataka eGazette",
            "base_domains": ["egazette.karnataka.gov.in"],
            "seed_urls": ["https://egazette.karnataka.gov.in/Gazettes.aspx"],
            "adapter": "karnataka_egazette",
            "government_level": "state",
            "stop_on_403": True, "stop_on_429": True,
            "respect_robots": True, "request_delay_seconds": 2,
            "max_documents_per_run": 3, "max_pages_per_run": 1,
        },
    },
    "karnataka_dpar": {
        "class": "crawlers.karnataka_dpar.KarnatakaDparAdapter",
        "source": {
            "source_id": "karnataka_dpar",
            "name": "Karnataka DPAR",
            "base_domains": ["dpar.karnataka.gov.in"],
            "seed_urls": ["https://dpar.karnataka.gov.in/page/Circulars/en"],
            "adapter": "karnataka_dpar",
            "government_level": "state",
            "stop_on_403": True, "stop_on_429": True,
            "respect_robots": True, "request_delay_seconds": 2,
            "max_documents_per_run": 3, "max_pages_per_run": 1,
        },
    },
    "karnataka_finance": {
        "class": "crawlers.karnataka_finance.KarnatakaFinanceAdapter",
        "source": {
            "source_id": "karnataka_finance",
            "name": "Karnataka Finance Department",
            "base_domains": ["finance.karnataka.gov.in"],
            "seed_urls": ["https://finance.karnataka.gov.in/page/Government-Orders/en"],
            "adapter": "karnataka_finance",
            "government_level": "state",
            "stop_on_403": True, "stop_on_429": True,
            "respect_robots": True, "request_delay_seconds": 2,
            "max_documents_per_run": 3, "max_pages_per_run": 1,
        },
    },
    "karnataka_itbt": {
        "class": "crawlers.karnataka_itbt.KarnatakaItbtAdapter",
        "source": {
            "source_id": "karnataka_itbt",
            "name": "Karnataka IT-BT Department",
            "base_domains": ["itbt.karnataka.gov.in"],
            "seed_urls": ["https://itbt.karnataka.gov.in/page/Notifications-and-Circulars/en"],
            "adapter": "karnataka_itbt",
            "government_level": "state",
            "stop_on_403": True, "stop_on_429": True,
            "respect_robots": True, "request_delay_seconds": 2,
            "max_documents_per_run": 3, "max_pages_per_run": 1,
        },
    },
}

REQUIRED_FIELDS = [
    ("id",                           lambda c: bool(c.id)),
    ("source.source_id",             lambda c: bool(c.source.source_id)),
    ("source.source_name",           lambda c: bool(c.source.source_name)),
    ("source.source_url",            lambda c: bool(c.source.source_url)),
    ("source.official_document_url", lambda c: bool(c.source.official_document_url)),
    ("identity.title_original",      lambda c: bool(c.identity.title_original)),
    ("classification.government_level", lambda c: bool(c.classification.government_level)),
    ("classification.department",    lambda c: bool(c.classification.department)),
    ("classification.document_type", lambda c: bool(c.classification.document_type)),
    ("classification.language",      lambda c: bool(c.classification.language)),
    ("provenance.retrieved_at",      lambda c: c.provenance.retrieved_at is not None),
    ("provenance.content_hash",      lambda c: c.provenance.content_hash.startswith("sha256:")),
    ("processing.status",            lambda c: c.processing.status in ("extracted", "manual_review_required")),
    ("processing.published",         lambda c: c.processing.published is False),
]


def _import_class(dotted_path: str):
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


async def test_adapter(name: str, config: dict) -> dict:
    """Run listing + detail + parse for one adapter. Returns result dict."""
    # Clear lru_cache so .env changes are picked up
    from config import get_settings
    get_settings.cache_clear()

    cls = _import_class(config["class"])
    source = config["source"]
    adapter = cls(source)

    result = {
        "name": name,
        "listing_reachable": False,
        "listing_blocked": False,
        "listing_block_reason": None,
        "candidates_found": 0,
        "detail_reachable": False,
        "detail_blocked": False,
        "detail_block_reason": None,
        "parse_ok": False,
        "required_fields_passed": [],
        "required_fields_failed": [],
        "processing_status": None,
        "circular_id": None,
        "content_length": 0,
        "error": None,
    }

    t0 = time.monotonic()

    try:
        # ── 1. Raw listing fetch first (to capture block reason) ──
        seed_url = source["seed_urls"][0]
        raw = await adapter.fetch(seed_url)
        result["elapsed_s"] = round(time.monotonic() - t0, 1)

        if raw.blocked:
            result["listing_blocked"] = True
            result["listing_block_reason"] = raw.block_reason
            result["error"] = f"Listing blocked: {raw.block_reason} (HTTP {raw.status_code})"
            await adapter.close()
            return result

        # ── 2. Full fetch_listing() ──
        candidates = await adapter.fetch_listing()
        result["candidates_found"] = len(candidates)

        if not candidates:
            result["listing_reachable"] = True   # page loaded but parser found nothing
            result["error"] = "Listing page loaded (200) but parser found 0 document links"
            await adapter.close()
            return result

        result["listing_reachable"] = True
        candidate = candidates[0]

        # ── 3. Fetch detail ──
        fetch_result = await adapter.fetch_detail(candidate)

        if fetch_result.blocked:
            result["detail_blocked"] = True
            result["detail_block_reason"] = fetch_result.block_reason
            from services.crawler_service import _build_blocked_circular
            from lib.dates import utcnow
            circular = _build_blocked_circular(
                candidate, source,
                fetch_result.block_reason or "blocked",
                fetch_result.status_code, utcnow()
            )
            result["processing_status"] = circular.processing.status
            result["circular_id"] = circular.id
        elif fetch_result.not_modified:
            result["detail_reachable"] = True
            result["error"] = "304 Not Modified — no body to parse"
            await adapter.close()
            return result
        else:
            result["detail_reachable"] = True
            # ── 4. Parse ──
            circular = await adapter.parse(candidate, fetch_result)
            result["parse_ok"] = True
            result["processing_status"] = circular.processing.status
            result["circular_id"] = circular.id
            result["content_length"] = len(circular.content.original_text)

        # ── 5. Required field checks ──
        for field_name, check_fn in REQUIRED_FIELDS:
            try:
                passed = check_fn(circular)
            except Exception:
                passed = False
            if passed:
                result["required_fields_passed"].append(field_name)
            else:
                result["required_fields_failed"].append(field_name)

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    result["elapsed_s"] = round(time.monotonic() - t0, 1)
    await adapter.close()
    return result


def print_result(r: dict):
    name = r["name"]
    status_icon = (
        f"{GREEN}✓ PASS{RESET}" if r["parse_ok"]
        else f"{YELLOW}⚠ BLOCKED{RESET}" if r["detail_blocked"] or r["listing_blocked"]
        else f"{RED}✗ FAIL{RESET}"
    )
    print(f"\n  {BOLD}[{name}]{RESET}  {status_icon}  ({r.get('elapsed_s', '?')}s)")

    if r["listing_reachable"]:
        ok(f"Listing reachable — {r['candidates_found']} candidates found")
    else:
        fail(f"Listing not reachable — {r.get('error') or 'no candidates'}")

    if r["candidates_found"] > 0:
        if r["detail_blocked"]:
            warn(f"Detail blocked: {r['detail_block_reason']}")
            info(f"processing.status = {r['processing_status']} (correct)")
        elif r["detail_reachable"]:
            ok("Detail page fetched successfully")
        else:
            fail("Detail page not reachable")

    if r["parse_ok"]:
        ok(f"parse() succeeded — circular.id = {r['circular_id']}")
        ok(f"content.original_text length = {r['content_length']} chars")

    if r["required_fields_passed"]:
        ok(f"Required fields passed: {len(r['required_fields_passed'])}/{len(REQUIRED_FIELDS)}")
    if r["required_fields_failed"]:
        fail(f"Required fields MISSING: {r['required_fields_failed']}")

    if r["error"] and not r["detail_blocked"]:
        fail(f"Error: {r['error']}")


async def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    adapters_to_test = (
        {target: ADAPTERS[target]} if target and target in ADAPTERS
        else ADAPTERS
    )

    print(f"\n{BOLD}{'='*62}")
    print("  JanVaani — Crawler Adapter Live Test ({} adapters)".format(len(adapters_to_test)))
    print(f"{'='*62}{RESET}")

    results = []
    for name, config in adapters_to_test.items():
        print(f"\n{CYAN}Testing {name}...{RESET}")
        r = await test_adapter(name, config)
        results.append(r)
        print_result(r)

    # ── Summary table ──
    print(f"\n{BOLD}{'─'*62}")
    print("  SUMMARY")
    print(f"{'─'*62}{RESET}")
    print(f"  {'Adapter':<22} {'Listing':>8} {'Candidates':>12} {'Detail':>8} {'Parse':>7} {'Status'}")
    print(f"  {'─'*22} {'─'*8} {'─'*12} {'─'*8} {'─'*7} {'─'*22}")

    passed = blocked = failed = 0
    for r in results:
        listing = f"{GREEN}✓{RESET}" if r["listing_reachable"] else f"{RED}✗{RESET}"
        cands = str(r["candidates_found"])
        detail = (
            f"{YELLOW}BLK{RESET}" if r["detail_blocked"]
            else f"{GREEN}✓{RESET}" if r["detail_reachable"]
            else f"{RED}✗{RESET}"
        )
        parse = f"{GREEN}✓{RESET}" if r["parse_ok"] else f"{YELLOW}~{RESET}" if r["detail_blocked"] else f"{RED}✗{RESET}"
        status = r.get("processing_status") or r.get("error") or "—"
        print(f"  {r['name']:<22} {listing:>8} {cands:>12} {detail:>8} {parse:>7}  {status}")

        if r["parse_ok"]:
            passed += 1
        elif r["detail_blocked"] or r["listing_blocked"]:
            blocked += 1
        else:
            failed += 1

    print(f"\n  {GREEN}Parsed:  {passed}{RESET}  |  {YELLOW}Blocked: {blocked}{RESET}  |  {RED}Failed:  {failed}{RESET}")
    print(f"  Total:   {len(results)}\n")


if __name__ == "__main__":
    asyncio.run(main())
