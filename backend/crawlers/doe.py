"""
Department of Expenditure adapter — doe.gov.in
"""

from crawlers.base import BaseCrawlerAdapter


class DoeAdapter(BaseCrawlerAdapter):

    async def get_listing_urls(self) -> list[str]:
        return self.source.get("seed_urls", [])

    async def parse_listing_page(self, html: str, base_url: str) -> list[dict]:
        raise NotImplementedError("DoeAdapter.parse_listing_page")

    async def parse_detail_page(self, html: str, url: str) -> dict:
        raise NotImplementedError("DoeAdapter.parse_detail_page")
