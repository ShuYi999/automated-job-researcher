"""
Standalone LinkedIn login — run this once to authenticate.

Opens a Chromium window. Log into LinkedIn, then close the window.
Your session is saved to ./browser-profile/ and reused by the app.

Usage:
    python mcp-server/setup_login.py
"""

import asyncio
import re
from pathlib import Path

BROWSER_PROFILE_DIR = Path(__file__).parent / "browser-profile"
BROWSER_PROFILE_DIR.mkdir(exist_ok=True)


async def main():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Playwright not installed. Run:")
        print("  pip install playwright && playwright install --with-deps chromium")
        return

    print("Opening LinkedIn login page...")
    print("Log in normally, then wait — the window will close automatically.\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE_DIR),
            headless=False,
            args=["--no-sandbox"],
        )
        page = await browser.new_page()
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

        if "feed" in page.url or "mynetwork" in page.url:
            print("Already logged in! Session is ready.")
            await browser.close()
            return

        print("Waiting up to 120 seconds for you to log in...")
        try:
            await page.wait_for_url(
                re.compile(r"linkedin\.com/feed|linkedin\.com/mynetwork"),
                timeout=120_000,
            )
            print("\nLogin successful! Session saved to browser-profile/")
            print("You can now run: streamlit run mcp-server/frontend.py")
        except Exception:
            print("\nTimed out. Run this script again to retry.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
