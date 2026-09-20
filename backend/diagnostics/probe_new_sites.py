"""Probe all 16 new sites: check reachability, content-type, PDF links, page structure."""
import asyncio, sys, time
sys.path.insert(0, '..')
from config import get_settings; get_settings.cache_clear()
from bs4 import BeautifulSoup

SITES = [
    ("vtu",        "https://vtu.ac.in/",                               "vtu.ac.in"),
    ("kseab",      "https://kseab.karnataka.gov.in/",                  "kseab.karnataka.gov.in"),
    ("kea",        "https://kea.kar.nic.in/",                          "kea.kar.nic.in"),
    ("bescom",     "https://bescom.karnataka.gov.in/",                  "bescom.karnataka.gov.in"),
    ("kptcl",      "https://kptcl.karnataka.gov.in/",                  "kptcl.karnataka.gov.in"),
    ("kerc",       "https://kerc.karnataka.gov.in/",                   "kerc.karnataka.gov.in"),
    ("mescom",     "https://mescom.karnataka.gov.in/",                  "mescom.karnataka.gov.in"),
    ("bwssb",      "https://bwssb.karnataka.gov.in/",                  "bwssb.karnataka.gov.in"),
    ("kuwsdb",     "https://kuwsdb.karnataka.gov.in/",                 "kuwsdb.karnataka.gov.in"),
    ("gba",        "https://gba.karnataka.gov.in/",                    "gba.karnataka.gov.in"),
    ("bbmp",       "https://bbmp.gov.in/",                             "bbmp.gov.in"),
    ("kspcb",      "https://kspcb.karnataka.gov.in/",                  "kspcb.karnataka.gov.in"),
    ("sevasindhu", "https://sevasindhu.karnataka.gov.in/",             "sevasindhu.karnataka.gov.in"),
    ("ssp",        "https://ssp.karnataka.gov.in/",                    "ssp.karnataka.gov.in"),
    ("karnataka",  "https://karnataka.gov.in/",                        "karnataka.gov.in"),
    ("ksrtc",      "https://www.ksrtc.in/",                            "ksrtc.in"),
]

async def probe_one(session, name, url, domain):
    import httpx
    settings = get_settings()
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": settings.crawler_user_agent},
            follow_redirects=True, timeout=15, verify=False
        ) as c:
            r = await c.get(url)
        elapsed = round(time.monotonic() - t0, 1)
        ct = r.headers.get("content-type","")[:40]
        body = r.text
        soup = BeautifulSoup(body, "lxml")

        # Count PDF links
        pdf_links = [a["href"] for a in soup.find_all("a", href=True) if ".pdf" in a["href"].lower()]

        # Detect CMS patterns
        cms = "unknown"
        if "eprerna" in body.lower() or "e-prerna" in body.lower():
            cms = "e-prerna"
        elif "drupal" in body.lower() or "sites/default" in body.lower():
            cms = "drupal"
        elif "wordpress" in body.lower() or "wp-content" in body.lower():
            cms = "wordpress"
        elif "joomla" in body.lower():
            cms = "joomla"
        elif "__viewstate" in body.lower() or "aspx" in r.url.path.lower():
            cms = "aspnet"
        elif "nicwebsite" in body.lower() or "nic.in" in body.lower():
            cms = "nic-template"

        # Find circular/notice/order page links
        circ_links = []
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True).lower()
            href = a["href"].lower()
            if any(k in text or k in href for k in ["circular", "notice", "order", "notification", "tender", "press", "gazette"]):
                circ_links.append(a["href"][:80])

        print(f"[{r.status_code}] {name:<12} {elapsed}s | {ct} | CMS:{cms} | PDFs:{len(pdf_links)} | circular-links:{len(circ_links)}")
        if circ_links[:3]:
            for lnk in circ_links[:3]:
                print(f"         {lnk}")
        return name, r.status_code, cms, pdf_links[:2], circ_links[:3]
    except Exception as e:
        elapsed = round(time.monotonic() - t0, 1)
        print(f"[ERR] {name:<12} {elapsed}s | {type(e).__name__}: {str(e)[:60]}")
        return name, 0, "error", [], []

async def main():
    tasks = [probe_one(None, name, url, domain) for name, url, domain in SITES]
    await asyncio.gather(*tasks)

asyncio.run(main())
