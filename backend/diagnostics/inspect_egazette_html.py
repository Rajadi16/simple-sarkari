"""Inspect the captured Karnataka eGazette HTML for form/postback structure."""
from bs4 import BeautifulSoup
from pathlib import Path

html = Path("data/browser-inspection/karnataka_egazette.html").read_text(encoding="utf-8")
soup = BeautifulSoup(html, "lxml")

print("=== FORMS ===")
for form in soup.find_all("form"):
    print(f"  action={form.get('action')!r}  method={form.get('method')!r}")

print("\n=== HIDDEN INPUTS (name + value length only) ===")
for inp in soup.find_all("input", type="hidden"):
    name = inp.get("name", "")
    val_len = len(inp.get("value", ""))
    print(f"  name={name!r}  value_len={val_len}")

print("\n=== RecentUploads category links ===")
for a in soup.find_all("a", href=True):
    href = a["href"]
    if "RecentUploads" in href:
        text = a.get_text(strip=True)[:60]
        print(f"  {text!r} -> {href}")

print("\n=== Session token in URLs ===")
# Extract the session token from any URL
import re
for a in soup.find_all("a", href=True):
    m = re.search(r'/\(S\(([^)]+)\)\)/', a["href"])
    if m:
        print(f"  session token: {m.group(1)!r}")
        break
