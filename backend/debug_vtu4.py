import sys
sys.path.insert(0, ".")
import asyncio
from test_crawlers import ADAPTERS
from crawlers.wordpress_karnataka import WordPressKarnatakaAdapter

async def run():
    src = ADAPTERS["vtu"]["source"]
    adapter = WordPressKarnatakaAdapter(src)
    cands = await adapter.fetch_listing()
    print("Found candidates:", len(cands))
    if not cands: return
    cand = cands[0]
    print(f"CAND DETAIL: {cand.detail_url}")
    r = await adapter.fetch_detail(cand)
    print(f"CT: {r.content_type}")
    parsed = await adapter.parse(cand, r)
    print(f"ORIGINAL_TEXT: {len(parsed.content.original_text)}")

asyncio.run(run())
