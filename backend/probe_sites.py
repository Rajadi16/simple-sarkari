import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin

async def probe(url):
    print(f"Probing {url}")
    try:
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.get(url, follow_redirects=True)
            print(f"Status: {resp.status_code}")
            soup = BeautifulSoup(resp.text, "lxml")
            links = []
            for a in soup.find_all("a", href=True):
                links.append(a["href"])
            
            # Print unique links containing pdf, circular, order, node
            target_links = list(set([l for l in links if 'pdf' in l.lower() or 'circular' in l.lower() or 'order' in l.lower() or 'node' in l.lower()]))
            print(f"Found {len(target_links)} target links. First few: {target_links[:5]}")
    except Exception as e:
        print(f"Error: {e}")

async def main():
    await probe("https://gba.karnataka.gov.in/")
    await probe("https://www.ksrtc.in/")

asyncio.run(main())
