"""
Export LinkedIn session for Playwright.

Usage:
  # Export cookies from Cookie-Editor JSON (easiest)
  #   1. Install "Cookie-Editor" Chrome extension
  #   2. Log into linkedin.com in your browser
  #   3. Cookie-Editor → Export → Save as JSON
  #   4. Then:
  python scripts/export_linkedin_cookies.py import cookies.json

  # Export browser profile (run on your HOST where X11 works)
  #   Opens a browser window — you log in manually, complete any challenge
  #   Profile saved to .linkedin_browser/ for use in Docker
  python scripts/export_linkedin_cookies.py profile

  # Connect to running Chrome via CDP
  #   google-chrome --remote-debugging-port=9222
  #   Log into linkedin.com in that Chrome, then:
  python scripts/export_linkedin_cookies.py cdp
"""

import argparse
import asyncio
import json
import pickle
import shutil
import sys
from pathlib import Path

from playwright.async_api import async_playwright

COOKIE_DIR = Path(".linkedin_cookies")
COOKIE_FILE = COOKIE_DIR / "cookies.pkl"
PROFILE_DIR = Path(".linkedin_browser")


def convert_cookie_editor_json(raw: list[dict]) -> list[dict]:
    """Convert Cookie-Editor JSON export to Playwright cookie format."""
    playwright_cookies = []
    for c in raw:
        if not c.get("name"):
            continue
        same_site = {"no_restriction": "None", "lax": "Lax", "strict": "Strict"}.get(
            c.get("sameSite", "").lower(), "None"
        )
        pw_cookie = {
            "name": c["name"],
            "value": c.get("value", ""),
            "domain": c.get("domain", ""),
            "path": c.get("path", "/"),
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False),
            "sameSite": same_site,
        }
        expires = c.get("expirationDate")
        if expires:
            pw_cookie["expires"] = expires
        playwright_cookies.append(pw_cookie)
    return playwright_cookies


async def export_profile():
    """Open Chromium headed, let user log in, save FULL browser profile."""
    print("Opening Chromium (headless=false)...")
    print("Log into LinkedIn manually in the browser window.")
    print("If LinkedIn shows a challenge, complete it.")
    print("After you see the feed page, press ENTER here to save the profile.")
    print()

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 720},
            locale="pt-BR",
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://www.linkedin.com/login", wait_until="load")

        input("Press ENTER after logging in and seeing the feed... > ")

        final_url = page.url
        print(f"URL atual: {final_url}")

        has_li_at = any(c["name"] == "li_at" for c in await context.cookies())

        await context.close()

    if has_li_at:
        print(f"✅ li_at cookie presente — perfil salvo em {PROFILE_DIR}")
        print("  Agora o Docker vai usar este perfil.")
    else:
        print(f"⚠️  li_at cookie ausente. Perfil salvo em {PROFILE_DIR}")
        print("  Mas pode não funcionar para scraping sem o cookie de autenticação.")


async def export_via_cdp():
    """Connect to Chrome via CDP and save profile."""
    print("Connecting to Chrome via CDP at http://localhost:9222...")
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0] if browser.contexts else await browser.new_context()

        cookies = await context.cookies()
        has_li_at = any(c["name"] == "li_at" for c in cookies)

        COOKIE_DIR.mkdir(parents=True, exist_ok=True)
        with open(COOKIE_FILE, "wb") as f:
            pickle.dump(cookies, f)

        print(f"Saved {len(cookies)} cookies to {COOKIE_FILE}")
        print(f"li_at cookie present: {has_li_at}")
        if not has_li_at:
            print("⚠️  li_at not found. Make sure you're logged into linkedin.com")
        await browser.close()


def import_from_json(json_path: str):
    """Import cookies from Cookie-Editor JSON export."""
    path = Path(json_path)
    if not path.exists():
        print(f"File not found: {json_path}")
        sys.exit(1)

    with open(path) as f:
        raw = json.load(f)

    if isinstance(raw, dict) and "cookies" in raw:
        raw = raw["cookies"]

    cookies = convert_cookie_editor_json(raw)
    has_li_at = any(c["name"] == "li_at" for c in cookies)

    COOKIE_DIR.mkdir(parents=True, exist_ok=True)
    with open(COOKIE_FILE, "wb") as f:
        pickle.dump(cookies, f)

    print(f"Converted {len(cookies)} cookies to {COOKIE_FILE}")
    print(f"li_at cookie present: {has_li_at}")
    if has_li_at:
        print("✅ LinkedIn auth cookie found — should work for scraping!")
    else:
        print("⚠️  li_at cookie not found. Make sure you export AFTER logging into linkedin.com.")


def main():
    parser = argparse.ArgumentParser(description="Export LinkedIn session for Playwright")
    parser.add_argument("mode", nargs="?", default="import",
                        choices=["import", "profile", "cdp"],
                        help="import (from Cookie-Editor JSON), profile (headed browser), cdp (connect Chrome)")
    parser.add_argument("file", nargs="?",
                        help="JSON file path (for import mode)")

    args = parser.parse_args()

    if args.mode == "profile":
        asyncio.run(export_profile())
    elif args.mode == "cdp":
        asyncio.run(export_via_cdp())
    else:
        if not args.file:
            print("Usage: python scripts/export_linkedin_cookies.py import <cookies.json>")
            sys.exit(1)
        import_from_json(args.file)


if __name__ == "__main__":
    main()
