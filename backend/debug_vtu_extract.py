import asyncio
from crawlers.manager import CrawlerManager
from models.circular import CandidateDocument

async def run():
    manager = CrawlerManager("sources.yaml")
    adapter = manager.get_adapter("vtu")
    cands = await adapter.fetch_listing()
    print("Found", len(cands), "candidates")
    if not cands:
        return
    
    cand = cands[0]
    print("Candidate:", cand.title, cand.detail_url)
    result = await adapter.fetch_detail(cand)
    
    from services.extraction_service import extract_html
    ext = extract_html(result.body, cand.detail_url)
    print("EXTRACTED TEXT:")
    print(ext["original_text"][:500])
    print("EXTRACTED TEXT LENGTH:", len(ext["original_text"]))

asyncio.run(run())
