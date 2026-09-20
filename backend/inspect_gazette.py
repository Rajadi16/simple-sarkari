"""One bounded Selenium inspection of an accessible, interactive Gazette page.

Run locally with Chrome installed. This captures evidence for a source-specific
form parser; it does not claim successful ingestion or circumvent access blocks.
"""

import argparse
import asyncio
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys


def timeout_value(value):
    number = float(value)
    if not math.isfinite(number) or not 10 <= number <= 120:
        raise argparse.ArgumentTypeError("timeout must be between 10 and 120 seconds")
    return number


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=("egazette", "karnataka_egazette"))
    parser.add_argument("--output", type=Path, default=Path("data/browser-inspection"))
    parser.add_argument("--timeout", type=timeout_value, default=45)
    parser.add_argument("--wait-selector", default="form, table")
    parser.add_argument("--click-selector", action="append", default=[],
                        help="Optional selector verified from the page; at most three clicks")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    result = parser.parse_args(argv)
    if len(result.click_selector) > 3:
        parser.error("at most three click selectors are allowed")
    return result


def save_report(args, report):
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / f"{args.source}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)


async def preflight(source):
    from test_crawlers import ADAPTERS, _import_class
    config = ADAPTERS[source]
    adapter = _import_class(config["class"])(config["source"])
    url = adapter.source["seed_urls"][0]
    try:
        async with asyncio.timeout(15):
            fetched = await adapter.fetch(url)
        return url, fetched
    finally:
        await adapter.close()


def inspect(args):
    report = {"source": args.source, "status": "failed", "ingested": False}
    driver = None
    try:
        url, fetched = asyncio.run(preflight(args.source))
        report.update(url=url, preflight_http_status=fetched.status_code)
        if fetched.blocked or not fetched.body:
            report.update(reason=fetched.block_reason or "empty_response", error=fetched.error_detail)
            return 1

        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from config import get_settings
        from crawlers.base import _detect_block
        from lib.security import validate_url
        import httpx

        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1280,900")
        options.add_argument(f"--user-agent={get_settings().crawler_user_agent}")
        options.accept_insecure_certs = False
        options.page_load_strategy = "eager"
        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(0)
        driver.set_page_load_timeout(20)
        driver.set_script_timeout(10)
        driver.get(url)

        def check_page():
            validate_url(driver.current_url)
            # WebDriver has no ordinary main-document HTTP status API. This
            # synthetic response is used only for the existing text heuristic.
            response = httpx.Response(200, text=driver.page_source,
                                      request=httpx.Request("GET", driver.current_url))
            reason = _detect_block(response)
            if reason:
                raise ValueError(f"Browser stopped at an access challenge: {reason}")

        check_page()
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, args.wait_selector)))
        for selector in args.click_selector:
            check_page()
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector))).click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, args.wait_selector)))
        check_page()

        args.output.mkdir(parents=True, exist_ok=True)
        html_path = args.output / f"{args.source}.html"
        html_path.write_text(driver.page_source, encoding="utf-8")
        links = []
        for element in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
            link = element.get_attribute("href")
            try:
                validate_url(link or "")
            except ValueError:
                continue
            links.append({"url": link, "text": element.text})
        controls = []
        for element in driver.find_elements(By.CSS_SELECTOR, "input, button, select"):
            if element.get_attribute("type") == "hidden":
                continue  # session/viewstate fields remain in the local HTML capture
            controls.append({"tag": element.tag_name, "id": element.get_attribute("id"),
                             "name": element.get_attribute("name"), "type": element.get_attribute("type"),
                             "text": element.text})
        report.update(status="captured", final_url=driver.current_url,
                      rendered_http_status=None, html_file=str(html_path),
                      links=links, controls=controls)
        return 0
    except Exception as error:
        report.update(reason="inspection_error", error=f"{type(error).__name__}: {error}")
        return 1
    finally:
        # Save evidence before quit: the parent also bounds driver startup/cleanup.
        save_report(args, report)
        if driver is not None:
            driver.quit()


def stop_process_tree(process):
    """Terminate this inspection's browser/driver processes after its deadline."""
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, timeout=5, check=False)
    else:
        process.kill()
    process.wait(timeout=5)


def main(argv=None):
    args = arguments(argv)
    if args.worker:
        return inspect(args)
    original_args = list(sys.argv[1:] if argv is None else argv)
    command = [sys.executable, str(Path(__file__).resolve()), *original_args, "--worker"]
    process = subprocess.Popen(command, start_new_session=os.name == "posix")
    try:
        return process.wait(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        stop_process_tree(process)
        save_report(args, {"source": args.source, "status": "failed", "ingested": False,
                           "reason": "inspection_timeout", "timeout_seconds": args.timeout})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
