import asyncio
import httpx
from bs4 import BeautifulSoup

async def probe():
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.get("https://gba.karnataka.gov.in/english", follow_redirects=True)
        soup = BeautifulSoup(resp.text, "lxml")
        links = []
        for a in soup.find_all("a", href=True):
            links.append((a.get_text(strip=True), a["href"]))
        print(f"Total links: {len(links)}")
        for text, href in links:
            if "circular" in href.lower() or "circular" in text.lower() or "notification" in text.lower():
                print(f"Potential link: {text}: {href}")

asyncio.run(probe())
