import asyncio
import httpx
from bs4 import BeautifulSoup

async def probe():
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.get("https://vtu.ac.in/en/category/administration-circulars/", follow_redirects=True)
        soup = BeautifulSoup(resp.text, "lxml")
        # Check VTU structure
        for div in soup.find_all("div", limit=20):
            classes = div.attrs.get("class")
            if classes:
                print(classes)
                if "content" in " ".join(classes) or "main" in " ".join(classes):
                    print("Found main content class:", classes)

asyncio.run(probe())
