"""
Karnataka DPAR adapter — dpar.karnataka.gov.in
"""

from crawlers.base import BaseCrawlerAdapter


class KarnatakaDparAdapter(BaseCrawlerAdapter):

    async def get_listing_urls(self) -> list[str]:
        return self.source.get("seed_urls", [])

    async def parse_listing_page(self, html: str, base_url: str) -> list[dict]:
        raise NotImplementedError("KarnatakaDparAdapter.parse_listing_page")

    async def parse_detail_page(self, html: str, url: str) -> dict:
        raise NotImplementedError("KarnatakaDparAdapter.parse_detail_page")
