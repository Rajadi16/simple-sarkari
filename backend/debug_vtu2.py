import asyncio
import httpx
from crawlers.wordpress_karnataka import WordPressKarnatakaAdapter
from crawlers.base import FetchResult
from models.circular import CandidateDocument
from services.extraction_service import extract_html

async def run():
    adapter = WordPressKarnatakaAdapter({"source_id": "vtu", "name": "VTU", "base_domains": ["vtu.ac.in"], "seed_urls": ["https://vtu.ac.in/en/category/administration-circulars/"]})
    cands = await adapter.fetch_listing()
    print("Found", len(cands), "candidates")
    for cand in cands[:2]:
        print(cand.title, cand.detail_url)

asyncio.run(run())
