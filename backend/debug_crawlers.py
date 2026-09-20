import asyncio
from crawlers.drupal_karnataka import DrupalKarnatakaAdapter
from crawlers.base import FetchResult
from models.circular import CandidateDocument

async def run():
    adapter = DrupalKarnatakaAdapter({"source_id": "bescom", "name": "BESCOM", "seed_urls": ["https://bescom.karnataka.gov.in/43/circulars/en"]})
    cands = await adapter.fetch_listing()
    print("Found", len(cands), "candidates")
    if cands:
        cand = cands[0]
        res = await adapter.fetch_detail(cand)
        print("Fetched detail", len(res.body) if res.body else "No body")
        try:
            circ = await adapter.parse(cand, res)
            print("Success")
        except Exception as e:
            import traceback
            traceback.print_exc()

asyncio.run(run())
