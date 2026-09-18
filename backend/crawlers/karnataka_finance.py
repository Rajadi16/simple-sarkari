"""
Karnataka Finance Department adapter — finance.karnataka.gov.in
"""

from crawlers.base import BaseCrawlerAdapter


class KarnatakaFinanceAdapter(BaseCrawlerAdapter):

    async def get_listing_urls(self) -> list[str]:
        return self.source.get("seed_urls", [])

    async def parse_listing_page(self, html: str, base_url: str) -> list[dict]:
        raise NotImplementedError("KarnatakaFinanceAdapter.parse_listing_page")

    async def parse_detail_page(self, html: str, url: str) -> dict:
        raise NotImplementedError("KarnatakaFinanceAdapter.parse_detail_page")
