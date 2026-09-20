"""
test_crawlers.py — Live connectivity + parser test for all 9 crawlers.

Tests each adapter's fetch_listing() and verifies:
  1. Listing page reachable (not blocked)
  2. At least 1 CandidateDocument returned
  3. fetch_detail() + parse() on the first candidate produces a valid
     CanonicalCircular with all required §4.4 fields populated

Usage:
  python test_crawlers.py karnataka_dpar --timeout 45
  python test_crawlers.py pib --timeout 45 --json
  python test_crawlers.py all       # explicitly opt in to all nine sources

Requires: pip install -r requirements.txt; no MongoDB connection is made.
Exit codes: 0 = all documents validated, 1 = blocked/failed diagnostic,
2 = invalid command. A failure is a report, not an instruction to retry.
"""

import asyncio
import argparse
import json
import math
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

# Use the same endpoint corrections as production, including existing DB configs.
from crawlers.source_config import normalize_source_config
for _config in ADAPTERS.values():
    _config["source"] = normalize_source_config(_config["source"])

REQUIRED_FIELDS = [
    ("id",                           lambda c: bool(c.id)),
    ("source.source_id",             lambda c: bool(c.source.source_id)),
    ("source.source_name",           lambda c: bool(c.source.source_name)),
    ("source.source_url",            lambda c: bool(c.source.source_url)),
    ("source.official_document_url", lambda c: bool(c.source.official_document_url)),
    ("identity.title_original",      lambda c: bool(c.identity.title_original)),
    ("content.original_text",        lambda c: bool(c.content.original_text.strip())),
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


async def test_adapter(name: str, config: dict, timeout_seconds: float = 45) -> dict:
    """Run one bounded diagnostic. Never repeat the run automatically."""
    result = {
        "name": name,
        "listing_reachable": False,
        "listing_blocked": False,
        "listing_block_reason": None,
        "listing_http_status": None,
        "listing_not_modified": False,
        "candidates_found": 0,
        "detail_reachable": False,
        "detail_blocked": False,
        "detail_block_reason": None,
        "detail_http_status": None,
        "parse_ok": False,
        "required_fields_passed": [],
        "required_fields_failed": [],
        "processing_status": None,
        "circular_id": None,
        "content_length": 0,
        "timed_out": False,
        "error": None,
    }
    adapter = None
    t0 = time.monotonic()
    try:
        from config import get_settings
        get_settings.cache_clear()
        cls = _import_class(config["class"])
        adapter = cls(config["source"])
        await asyncio.wait_for(
            _check_adapter(adapter, config["source"], result),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        result["timed_out"] = True
        result["error"] = f"Diagnostic exceeded {timeout_seconds:g}s; stopped without rerunning"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if adapter is not None:
            await adapter.close()
        result["elapsed_s"] = round(time.monotonic() - t0, 1)
    return result


async def _check_adapter(adapter, source: dict, result: dict) -> None:
    # Probe once for the HTTP status, then reuse this response during listing.
    # A second conditional GET could return 304 and masquerade as a parser bug.
    seed_url = source["seed_urls"][0]
    raw = await adapter.fetch(seed_url)
    result["listing_http_status"] = raw.status_code
    if raw.blocked:
        result["listing_blocked"] = True
        result["listing_block_reason"] = raw.block_reason
        result["error"] = f"Listing blocked: {raw.block_reason} (HTTP {raw.status_code})"
        if raw.error_detail:
            result["error"] += f": {raw.error_detail}"
        return
    if raw.not_modified:
        result["listing_reachable"] = True
        result["listing_not_modified"] = True
        result["error"] = "Listing unchanged (HTTP 304); no cached body available to validate the parser"
        return
    if not 200 <= raw.status_code < 300:
        result["error"] = f"Listing returned HTTP {raw.status_code}; parser was not tested"
        return
    result["listing_reachable"] = True
    if not raw.body:
        result["error"] = f"Listing returned HTTP {raw.status_code} with an empty body"
        return

    original_fetch = adapter.fetch

    async def reuse_probe(url):
        return raw if url == seed_url else await original_fetch(url)

    adapter.fetch = reuse_probe
    try:
        candidates = await adapter.fetch_listing()
    finally:
        adapter.fetch = original_fetch
    result["candidates_found"] = len(candidates)
    if not candidates:
        result["error"] = (
            f"No document links found after listing probe HTTP {raw.status_code}; "
            "inspect the fetched HTML before changing the parser"
        )
        return

    candidate = candidates[0]
    fetched = await adapter.fetch_detail(candidate)
    result["detail_http_status"] = fetched.status_code
    if fetched.blocked:
        result["detail_blocked"] = True
        result["detail_block_reason"] = fetched.block_reason
        result["error"] = f"Detail blocked: {fetched.block_reason} (HTTP {fetched.status_code})"
        if fetched.error_detail:
            result["error"] += f": {fetched.error_detail}"
        return
    if fetched.not_modified:
        result["error"] = "Detail unchanged (HTTP 304); no cached body available to validate extraction"
        return
    if not 200 <= fetched.status_code < 300 or not fetched.body:
        result["error"] = f"Detail returned HTTP {fetched.status_code} or an empty body; parser was not tested"
        return

    result["detail_reachable"] = True
    circular = await adapter.parse(candidate, fetched)
    result["processing_status"] = circular.processing.status
    result["circular_id"] = circular.id
    result["content_length"] = len(circular.content.original_text)
    for field_name, check_fn in REQUIRED_FIELDS:
        try:
            passed = check_fn(circular)
        except Exception:
            passed = False
        key = "required_fields_passed" if passed else "required_fields_failed"
        result[key].append(field_name)
    result["parse_ok"] = not result["required_fields_failed"]
    if not result["parse_ok"]:
        result["error"] = "Parser returned a document with missing or invalid required fields"


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
            info("No document parsed or saved by this diagnostic")
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

    if r["error"]:
        fail(f"Error: {r['error']}")


def _positive_timeout(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timeout must be a positive number") from exc
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("timeout must be a finite positive number")
    return seconds


async def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=[*ADAPTERS, "all"])
    parser.add_argument("--timeout", type=_positive_timeout, default=45,
                        help="wall-clock budget per adapter in seconds (default: 45)")
    parser.add_argument("--json", action="store_true", help="print machine-readable results")
    parser.add_argument("--rss", action="store_true", help="use the official PIB RSS listing (pib only)")
    args = parser.parse_args(argv)
    if args.rss and args.source != "pib":
        parser.error("--rss can only be used with the pib source")
    target = args.source
    adapters_to_test = (
        {target: ADAPTERS[target]} if target != "all"
        else ADAPTERS
    )

    if not args.json:
        print(f"\n{BOLD}{'='*62}")
        print("  JanVaani — Crawler Adapter Live Test ({} adapters)".format(len(adapters_to_test)))
        print(f"{'='*62}{RESET}")

    results = []
    for name, config in adapters_to_test.items():
        if args.rss:
            from crawlers.source_config import PIB_RSS_URL
            config = dict(config, source=dict(config["source"], seed_urls=[PIB_RSS_URL]))
        if not args.json:
            print(f"\n{CYAN}Testing {name} (budget: {args.timeout:g}s)...{RESET}", flush=True)
        r = await test_adapter(name, config, timeout_seconds=args.timeout)
        results.append(r)
        if not args.json:
            print_result(r)

    exit_code = 0 if all(r["parse_ok"] for r in results) else 1
    if args.json:
        print(json.dumps(results, indent=2))
        return exit_code

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
    print("  Finished. Blocked/failed sources were not automatically rerun.")
    return exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
