"""
Single-shot fetch of egazette.gov.in listing page.
Saves raw response body and prints diagnostics. Run once, do not retry.
"""
import asyncio, sys, json
sys.path.insert(0, '..')
from config import get_settings; get_settings.cache_clear()

TARGET_URL = "https://egazette.gov.in/(S(a))/default.aspx"
OUT_FILE = "egazette-listing.html"

async def main():
    import httpx
    settings = get_settings()

    result = {
        "requested_url": TARGET_URL,
        "final_url": None,
        "http_status": None,
        "content_type": None,
        "response_size_bytes": None,
        "error": None,
        "timed_out": False,
    }

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": settings.crawler_user_agent},
            follow_redirects=True,
            timeout=httpx.Timeout(45),
            verify=False,
        ) as client:
            resp = await client.get(TARGET_URL)

            result["final_url"]          = str(resp.url)
            result["http_status"]        = resp.status_code
            result["content_type"]       = resp.headers.get("content-type", "")
            result["response_size_bytes"]= len(resp.content)

            # Save exact body
            with open(OUT_FILE, "wb") as f:
                f.write(resp.content)
            result["saved_to"] = OUT_FILE

    except httpx.TimeoutException as exc:
        result["error"]    = f"TimeoutException: {exc}"
        result["timed_out"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    print(json.dumps(result, indent=2))

asyncio.run(main())
