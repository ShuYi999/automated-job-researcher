"""
LinkedIn Job Research MCP Server

Exposes four tools:
  - search_jobs       : public search, no auth (httpx)
  - get_job_detail    : full job details, auth required (Playwright)
  - setup_session     : one-time browser login flow
  - session_status    : health check for saved session

Browser sessions are persisted in ./browser-profile/ so LinkedIn login
survives across server restarts. Sessions auto-expire after
SESSION_MAX_AGE_DAYS (default 7) — the profile is wiped and the user
must re-run setup_session.

Rate limiting: get_job_detail enforces a 3s delay between requests to
avoid LinkedIn bot-detection (per ADR-004 SWE recommendation).
"""

import asyncio
import json
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BROWSER_PROFILE_DIR = Path(__file__).parent / "browser-profile"
BROWSER_PROFILE_DIR.mkdir(exist_ok=True)

# Seconds to wait between Playwright page fetches (rate limit guard)
RATE_LIMIT_DELAY = 3.0
_last_playwright_call: float = 0.0

# Session auto-expiry: wipe browser-profile/ after this many days
SESSION_MAX_AGE_DAYS = 7
_SESSION_TIMESTAMP_FILE = BROWSER_PROFILE_DIR / ".session_created"

# Fake browser headers so httpx requests are not immediately rejected
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "linkedin-job-research",
    instructions=(
        "Tools for researching LinkedIn job listings. "
        "Use search_jobs first to find jobs, then get_job_detail for full descriptions. "
        "Run setup_session once if get_job_detail returns an auth error."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_search_url(
    keywords: str,
    location: str,
    date_posted: str,
    job_type: str,
    experience_level: str,
    start: int,
) -> str:
    """Build a LinkedIn job search URL from filter params."""
    base = "https://www.linkedin.com/jobs/search/"
    params: dict[str, str] = {
        "keywords": keywords,
        "location": location,
        "start": str(start),
    }
    # Date posted filter: r86400=24h, r604800=week, r2592000=month
    date_map = {"24h": "r86400", "week": "r604800", "month": "r2592000"}
    if date_posted in date_map:
        params["f_TPR"] = date_map[date_posted]

    # Job type filter: F=full-time, P=part-time, C=contract, T=temporary, I=internship
    if job_type:
        params["f_JT"] = job_type.upper()

    # Experience level: 1=intern, 2=entry, 3=assoc, 4=mid-senior, 5=director, 6=exec
    exp_map = {
        "internship": "1",
        "entry": "2",
        "associate": "3",
        "mid": "4",
        "senior": "4",
        "director": "5",
        "executive": "6",
    }
    if experience_level.lower() in exp_map:
        params["f_E"] = exp_map[experience_level.lower()]

    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{base}?{query}"


def _parse_job_cards(html: str) -> list[dict[str, str]]:
    """Parse job cards from LinkedIn public search HTML."""
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[dict[str, str]] = []

    # LinkedIn public search uses <div class="base-search-card ... job-search-card">
    # inside <li> elements. Each card has:
    #   - data-entity-urn="urn:li:jobPosting:<id>"
    #   - <a class="base-card__full-link" href="...linkedin.com/jobs/view/<id>...">
    #   - <h3 class="base-search-card__title"> for job title
    #   - <h4 class="base-search-card__subtitle"> for company
    #   - <span class="job-search-card__location"> for location
    #   - <time> for posted date
    cards = soup.find_all("div", class_=re.compile(r"job-search-card"))

    for card in cards:
        # Title
        title_el = card.find("h3", class_=re.compile(r"base-search-card__title"))
        title = title_el.get_text(strip=True) if title_el else ""

        # Company
        company_el = card.find("h4", class_=re.compile(r"base-search-card__subtitle"))
        company = company_el.get_text(strip=True) if company_el else ""

        # Location
        location_el = card.find("span", class_=re.compile(r"job-search-card__location"))
        location = location_el.get_text(strip=True) if location_el else ""

        # Posted date
        time_el = card.find("time")
        posted = time_el.get("datetime", time_el.get_text(strip=True)) if time_el else ""

        # Job URL and ID from the full-link anchor or data-entity-urn
        link_el = card.find("a", class_=re.compile(r"base-card__full-link"))
        href = link_el.get("href", "") if link_el else ""

        # Extract job ID from the URN or URL
        urn = card.get("data-entity-urn", "")
        urn_match = re.search(r"jobPosting:(\d+)", urn)
        url_match = re.search(r"/jobs/view/(\d+)", href)
        job_id = (urn_match or url_match).group(1) if (urn_match or url_match) else ""

        if title and job_id:
            jobs.append({
                "id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "posted": posted,
                "url": f"https://www.linkedin.com/jobs/view/{job_id}",
            })

    return jobs


async def _enforce_rate_limit() -> None:
    """Ensure at least RATE_LIMIT_DELAY seconds between Playwright calls."""
    global _last_playwright_call
    elapsed = time.monotonic() - _last_playwright_call
    if elapsed < RATE_LIMIT_DELAY:
        await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)
    _last_playwright_call = time.monotonic()


async def _check_playwright_installed() -> bool:
    """Check if playwright browsers are installed."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            _ = p
        return True
    except Exception:
        return False


def _record_session_timestamp() -> None:
    """Write current UTC time to the session timestamp file."""
    _SESSION_TIMESTAMP_FILE.write_text(datetime.now(timezone.utc).isoformat())


def _session_age_days() -> float | None:
    """Return session age in days, or None if no timestamp file exists."""
    if not _SESSION_TIMESTAMP_FILE.exists():
        return None
    try:
        created = datetime.fromisoformat(_SESSION_TIMESTAMP_FILE.read_text().strip())
        return (datetime.now(timezone.utc) - created).total_seconds() / 86400
    except (ValueError, OSError):
        return None


def _wipe_session() -> None:
    """Delete browser-profile/ contents and the timestamp file."""
    if BROWSER_PROFILE_DIR.exists():
        shutil.rmtree(BROWSER_PROFILE_DIR)
        BROWSER_PROFILE_DIR.mkdir(exist_ok=True)


def _check_session_expiry() -> dict[str, Any] | None:
    """If session is expired, wipe it and return an error dict. Otherwise None."""
    age = _session_age_days()
    if age is not None and age > SESSION_MAX_AGE_DAYS:
        _wipe_session()
        return {
            "error": (
                f"Session expired (created {age:.1f} days ago, "
                f"max {SESSION_MAX_AGE_DAYS} days). "
                "Profile wiped. Run setup_session to log in again."
            ),
            "auth_required": True,
            "expired": True,
        }
    return None


# ---------------------------------------------------------------------------
# Tool 1: search_jobs (public, httpx)
# ---------------------------------------------------------------------------

@mcp.tool()
async def search_jobs(
    keywords: str,
    location: str = "Remote",
    date_posted: str = "any_time",
    job_type: str = "",
    experience_level: str = "",
    limit: int = 25,
) -> list[dict[str, str]]:
    """
    Search LinkedIn job listings without authentication.

    Returns basic job metadata (title, company, location, posted date, URL).
    Full descriptions require get_job_detail.

    Args:
        keywords: Job title or skills, e.g. "software engineer python"
        location: City, country, or "Remote"
        date_posted: "any_time" | "24h" | "week" | "month"
        job_type: "" | "F" (full-time) | "P" (part-time) | "C" (contract) | "I" (internship)
        experience_level: "" | "entry" | "mid" | "senior" | "director" | "executive"
        limit: Max results to return (max ~60 per page; use multiples of 25 to paginate)
    """
    all_jobs: list[dict[str, str]] = []
    start = 0
    page_size = 25

    async with httpx.AsyncClient(headers=BROWSER_HEADERS, follow_redirects=True, timeout=15) as client:
        while len(all_jobs) < limit:
            url = _build_search_url(keywords, location, date_posted, job_type, experience_level, start)
            try:
                response = await client.get(url)
            except httpx.RequestError as e:
                return [{"error": f"Network error: {e}"}]

            if response.status_code != 200:
                return [{"error": f"HTTP {response.status_code} from LinkedIn search"}]

            page_jobs = _parse_job_cards(response.text)
            if not page_jobs:
                break  # No more results

            all_jobs.extend(page_jobs)
            if len(page_jobs) < page_size:
                break  # Last page
            start += page_size
            await asyncio.sleep(1)  # Polite delay between pages

    return all_jobs[:limit]


# ---------------------------------------------------------------------------
# Tool 2: get_job_detail (authenticated, Playwright)
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_job_detail(job_url: str) -> dict[str, Any]:
    """
    Get the full job description for a LinkedIn job listing.

    Requires an active LinkedIn session in the browser profile.
    Run setup_session first if you get an authentication error.

    Args:
        job_url: LinkedIn job URL, e.g. https://www.linkedin.com/jobs/view/1234567890
    """
    if not re.search(r"linkedin\.com/jobs/view/\d+", job_url):
        return {"error": "Invalid LinkedIn job URL. Expected: https://www.linkedin.com/jobs/view/<id>"}

    expired = _check_session_expiry()
    if expired:
        return expired

    await _enforce_rate_limit()

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"error": "Playwright not installed. Run: pip install playwright && playwright install chromium"}

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE_DIR),
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = await browser.new_page()

        try:
            await page.goto(job_url, wait_until="domcontentloaded", timeout=20_000)

            # Check for auth wall
            current_url = page.url
            if "linkedin.com/login" in current_url or "linkedin.com/authwall" in current_url:
                await browser.close()
                return {
                    "error": "LinkedIn requires login. Run setup_session tool first.",
                    "auth_required": True,
                }

            # Wait for job detail content to load
            try:
                await page.wait_for_selector(
                    "h1, .job-details-jobs-unified-top-card, .jobs-unified-top-card",
                    timeout=8_000,
                )
            except Exception:
                pass  # Continue with whatever is loaded

            # Extract all visible text (resilient to DOM/class changes)
            page_text = await page.evaluate("() => document.body.innerText")
            lines = [ln.strip() for ln in page_text.split("\n") if ln.strip()]

            # Job ID from URL
            id_match = re.search(r"/jobs/view/(\d+)", job_url)
            job_id = id_match.group(1) if id_match else ""

            # --- Text-based extraction ---
            # LinkedIn authenticated job pages follow a predictable text order:
            #   Company Name
            #   Job Title
            #   Location · Posted date · applicant count
            #   Salary (optional)
            #   On-site/Remote/Hybrid
            #   Full-time/Part-time/Contract
            #   ...
            #   About the job
            #   <description text>

            # Company: first line containing the company link text
            # (already extracted via page structure — use as anchor)
            page_html = await page.content()
            soup = BeautifulSoup(page_html, "html.parser")
            company_el = soup.find("a", href=re.compile(r"/company/"))
            company = company_el.get_text(strip=True) if company_el else ""

            # Title: find the line right after company name, or look for
            # a line near the top that isn't navigation
            title = ""
            nav_words = {"home", "my network", "jobs", "messaging", "notifications",
                         "me", "for business", "skip to main content", "try premium"}
            for i, line in enumerate(lines[:25]):
                if line.lower() in nav_words or "notification" in line.lower():
                    continue
                if company and line.strip() == company.strip():
                    # Title is the next non-empty line after company
                    if i + 1 < len(lines):
                        title = lines[i + 1]
                    break

            # Location: line containing " · " (separator) near the top
            location = ""
            for line in lines[:30]:
                if " · " in line and any(kw in line.lower() for kw in
                    ["ago", "applicant", "click", "reposted", "posted"]):
                    location = line.split(" · ")[0].strip()
                    break

            # Salary
            salary = ""
            salary_match = re.search(
                r"\$[\d,]+[kK]?(?:\s*[-–/]\s*\$[\d,]+[kK]?)?(?:\s*(?:per|/)\s*(?:year|yr|hour|hr))?",
                page_text,
                re.IGNORECASE,
            )
            if salary_match:
                salary = salary_match.group(0)

            # Description: everything after "About the job" marker
            description = ""
            about_idx = None
            for i, line in enumerate(lines):
                if re.match(r"about the job", line, re.IGNORECASE):
                    about_idx = i
                    break
            if about_idx is not None:
                # Collect lines until we hit a section like "About the company"
                # or common footer patterns
                stop_patterns = re.compile(
                    r"^(about the company|similar jobs|people also viewed|"
                    r"show more|set alert|am i a good fit|referrals increase)",
                    re.IGNORECASE,
                )
                desc_lines = []
                for line in lines[about_idx + 1:]:
                    if stop_patterns.match(line):
                        break
                    desc_lines.append(line)
                description = "\n".join(desc_lines)

            # Apply URL
            apply_el = soup.find("a", href=re.compile(r"/jobs/apply|offsite", re.I))
            apply_url = apply_el.get("href", "") if apply_el else job_url

            return {
                "id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "salary": salary,
                "description": description[:8000],
                "apply_url": apply_url,
                "source_url": job_url,
            }

        except Exception as e:
            return {"error": f"Failed to fetch job detail: {e}"}
        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# Tool 3: setup_session (one-time login)
# ---------------------------------------------------------------------------

@mcp.tool()
async def setup_session() -> dict[str, str]:
    """
    Open a visible browser window so you can log into LinkedIn manually.

    Run this once to establish a persistent session. Subsequent calls to
    get_job_detail will reuse the saved session from ./browser-profile/.

    The browser stays open for 120 seconds for you to log in.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "status": "error",
            "message": "Playwright not installed. Run: pip install playwright && playwright install chromium",
        }

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE_DIR),
            headless=False,  # Must be visible so user can log in
            args=["--no-sandbox"],
        )
        page = await browser.new_page()
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

        # Check if already logged in
        if "feed" in page.url or "mynetwork" in page.url:
            if not _SESSION_TIMESTAMP_FILE.exists():
                _record_session_timestamp()
            await browser.close()
            return {
                "status": "already_authenticated",
                "message": "Already logged into LinkedIn. get_job_detail is ready to use.",
                "profile_dir": str(BROWSER_PROFILE_DIR),
            }

        # Wait up to 120s for the user to log in manually
        try:
            await page.wait_for_url(
                re.compile(r"linkedin\.com/feed|linkedin\.com/mynetwork"),
                timeout=120_000,
            )
            _record_session_timestamp()
            session_status = "authenticated"
            message = (
                f"Login successful. Session saved (expires in {SESSION_MAX_AGE_DAYS} days). "
                "get_job_detail is ready to use."
            )
        except Exception:
            session_status = "timeout"
            message = "Login window timed out (120s). Try running setup_session again."

        await browser.close()
        return {
            "status": session_status,
            "message": message,
            "profile_dir": str(BROWSER_PROFILE_DIR),
        }


# ---------------------------------------------------------------------------
# Tool 4: session_status (health check)
# ---------------------------------------------------------------------------

@mcp.tool()
async def session_status() -> dict[str, Any]:
    """
    Check whether the saved browser session is still authenticated with LinkedIn.

    Returns auth status and basic profile info if logged in.
    """
    expired = _check_session_expiry()
    if expired:
        return {**expired, "authenticated": False}

    await _enforce_rate_limit()

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"authenticated": False, "error": "Playwright not installed"}

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE_DIR),
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = await browser.new_page()

        try:
            await page.goto(
                "https://www.linkedin.com/feed/",
                wait_until="domcontentloaded",
                timeout=15_000,
            )
            current_url = page.url
            is_auth = "feed" in current_url or "mynetwork" in current_url

            result: dict[str, Any] = {
                "authenticated": is_auth,
                "current_url": current_url,
                "profile_dir": str(BROWSER_PROFILE_DIR),
            }

            if is_auth:
                page_text = await page.evaluate("() => document.body.innerText")
                age = _session_age_days()
                if age is not None:
                    remaining = SESSION_MAX_AGE_DAYS - age
                    result["session_age_days"] = round(age, 1)
                    result["expires_in_days"] = round(remaining, 1)
                    result["message"] = (
                        f"Session is active ({age:.1f} days old, "
                        f"expires in {remaining:.1f} days)."
                    )
                else:
                    result["message"] = "Session is active (no expiry timestamp found)."
            else:
                result["message"] = "Not authenticated. Run setup_session to log in."

            return result
        except Exception as e:
            return {"authenticated": False, "error": str(e)}
        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
