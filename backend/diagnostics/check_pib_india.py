import asyncio, httpx, sys
sys.path.insert(0, '..')
from config import get_settings; get_settings.cache_clear()

async def check():
    s = get_settings()
    sites = [
        ('pib', 'https://www.pib.gov.in/Allrel.aspx?reg=48&lang=1'),
        ('india.gov', 'https://www.india.gov.in/my-government/policies'),
    ]
    async with httpx.AsyncClient(headers={'User-Agent': s.crawler_user_agent},
                                  follow_redirects=True, timeout=10) as c:
        for name, url in sites:
            try:
                r = await c.get(url)
                body = r.text[:120].replace('\n', ' ').strip()
                print(f'{name}: HTTP {r.status_code}')
                print(f'  body: {body}')
            except Exception as e:
                print(f'{name}: ERROR {type(e).__name__}: {e}')

asyncio.run(check())
