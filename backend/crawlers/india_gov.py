"""
india.gov.in National Portal adapter
"""

from crawlers.base import BaseCrawlerAdapter


class IndiaGovAdapter(BaseCrawlerAdapter):

    async def get_listing_urls(self) -> list[str]:
        return self.source.get("seed_urls", [])

    async def parse_listing_page(self, html: str, base_url: str) -> list[dict]:
        raise NotImplementedError("IndiaGovAdapter.parse_listing_page")

    async def parse_detail_page(self, html: str, url: str) -> dict:
        raise NotImplementedError("IndiaGovAdapter.parse_detail_page")
