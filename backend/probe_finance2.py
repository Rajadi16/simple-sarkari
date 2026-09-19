import asyncio, httpx, sys, re
sys.path.insert(0, '.')
from config import get_settings; get_settings.cache_clear()
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from lib.security import ALLOWED_DOMAINS

async def probe():
    settings = get_settings()
    async with httpx.AsyncClient(
        headers={"User-Agent": settings.crawler_user_agent},
        follow_redirects=True, timeout=20, verify=False
    ) as c:
        r = await c.get("https://finance.karnataka.gov.in/page/Government-Orders/en")
        soup = BeautifulSoup(r.text, 'lxml')
        found = 0
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            is_pdf = href.lower().endswith('.pdf') or '/uploads/' in href or '/storage/' in href
            if not is_pdf:
                continue
            abs_url = urljoin("https://finance.karnataka.gov.in/page/Government-Orders/en", href)
            from urllib.parse import urlparse
            host = urlparse(abs_url).hostname
            allowed = host in ALLOWED_DOMAINS
            title = re.sub(r'\s+', ' ', a.get_text()).strip()[:60]
            if not allowed:
                print(f"BLOCKED (host={host}): {title!r} -> {abs_url[:80]}")
            else:
                found += 1
                if found <= 5:
                    print(f"OK (host={host}): {title!r} -> {abs_url[:80]}")
        print(f"\nTotal OK: {found}")

asyncio.run(probe())
