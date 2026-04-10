"""Local browser_container smoke test.

Usage:
  python scripts/browser_container_smoke.py --url http://127.0.0.1:8000 --out artifacts/home.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--out", default="artifacts/home.png")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1024})
        page.goto(args.url, wait_until="networkidle")
        page.screenshot(path=str(out_path), full_page=True)
        browser.close()

    print(f"Screenshot saved: {out_path}")


if __name__ == "__main__":
    main()
