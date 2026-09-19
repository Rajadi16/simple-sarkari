"""Fetch one DPAR document and print the full CanonicalCircular JSON output."""
import asyncio, sys, json
sys.path.insert(0, '..')
from config import get_settings; get_settings.cache_clear()
from crawlers.karnataka_dpar import KarnatakaDparAdapter

source = {
    "source_id": "karnataka_dpar",
    "name": "Karnataka DPAR",
    "base_domains": ["dpar.karnataka.gov.in"],
    "seed_urls": ["https://dpar.karnataka.gov.in/page/Circulars/en"],
    "stop_on_403": True, "stop_on_429": True,
    "respect_robots": True, "request_delay_seconds": 2,
    "max_documents_per_run": 1,
}

async def main():
    adapter = KarnatakaDparAdapter(source)
    candidates = await adapter.fetch_listing()
    if not candidates:
        print("No candidates found"); return
    c = candidates[0]
    print(f"Found candidate: {c.title[:60]}")
    print(f"URL: {c.detail_url}\n")
    result = await adapter.fetch_detail(c)
    if result.blocked:
        print(f"Blocked: {result.block_reason}"); return
    circular = await adapter.parse(c, result)
    await adapter.close()
    # Print as JSON (mask raw text to keep output readable)
    d = circular.model_dump(mode="json")
    d["content"]["original_text"] = d["content"]["original_text"][:200] + "... [truncated]"
    d["content"]["clean_text"] = d["content"]["clean_text"][:200] + "... [truncated]" if d["content"].get("clean_text") else None
    print(json.dumps(d, indent=2, ensure_ascii=False))

asyncio.run(main())
