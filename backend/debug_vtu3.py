import sys
sys.path.insert(0, ".")
import asyncio
from test_crawlers import ADAPTERS
from crawlers.wordpress_karnataka import WordPressKarnatakaAdapter
from services.extraction_service import extract_html

async def run():
    src = ADAPTERS["vtu"]["source"]
    adapter = WordPressKarnatakaAdapter(src)
    cands = await adapter.fetch_listing()
    print("Found candidates:", len(cands))
    if not cands: return
    r = await adapter.fetch_detail(cands[0])
    ext = extract_html(r.body, cands[0].detail_url)
    t = ext.get("original_text", "")
    print(f"LEN: {len(t)}")
    print(f"TEXT: {t[:500]}")

asyncio.run(run())
