"""
Job Research UI — Prompt-driven with GitHub profile matching

Type a natural language prompt, enter your GitHub profile in the sidebar,
and get match scores + improvement suggestions for each job.

Run with: streamlit run mcp-server/frontend.py
"""

import asyncio
import json
import re
from pathlib import Path

import httpx
import streamlit as st
from bs4 import BeautifulSoup

import db

ANALYSIS_FILE = Path(__file__).parent / "claude_analysis.json"


def _run_async(coro):
    """Run an async coroutine from sync Streamlit code."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BROWSER_PROFILE_DIR = Path(__file__).parent / "browser-profile"
BROWSER_PROFILE_DIR.mkdir(exist_ok=True)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

LOCATIONS = {
    "kl": "Kuala Lumpur, Malaysia", "kuala lumpur": "Kuala Lumpur, Malaysia",
    "selangor": "Selangor, Malaysia", "pj": "Petaling Jaya, Selangor, Malaysia",
    "petaling jaya": "Petaling Jaya, Selangor, Malaysia",
    "penang": "Penang, Malaysia", "johor": "Johor, Malaysia",
    "malaysia": "Malaysia", "singapore": "Singapore", "remote": "Remote",
    "london": "London, United Kingdom", "new york": "New York, NY",
    "nyc": "New York, NY", "sf": "San Francisco, CA",
    "san francisco": "San Francisco, CA",
}

# Skill keywords for matching (lowercase)
SKILL_KEYWORDS = {
    "python", "javascript", "typescript", "java", "go", "rust", "c++", "sql",
    "react", "nextjs", "next.js", "vue", "angular", "fastapi", "flask", "django",
    "docker", "kubernetes", "k8s", "aws", "gcp", "azure", "terraform",
    "git", "ci/cd", "github actions", "jenkins",
    "langchain", "llm", "rag", "vector database", "faiss", "chromadb", "pinecone",
    "openai", "anthropic", "groq", "ollama", "hugging face", "huggingface",
    "pytorch", "tensorflow", "scikit-learn", "sklearn", "onnx", "mlflow",
    "triton", "mlops", "machine learning", "deep learning", "nlp", "computer vision",
    "streamlit", "gradio", "playwright", "selenium", "beautifulsoup",
    "grpc", "protobuf", "protocol buffers", "mcp", "model context protocol",
    "agentic", "agent", "multi-agent", "function calling", "tool use",
    "prompt engineering", "embeddings", "nomic", "bge",
    "postgresql", "mongodb", "redis", "mysql", "sqlite",
    "langfuse", "ragas", "evaluation", "observability",
    "duckduckgo", "web scraping", "automation",
    "linux", "wsl", "bash", "shell",
    "fastembed", "pydantic", "asyncio", "httpx",
    "data science", "data engineering", "etl", "data pipeline",
}

# ---------------------------------------------------------------------------
# LLM job analysis (local Ollama → Claude API fallback)
# ---------------------------------------------------------------------------

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:14b"

_LLM_SYSTEM_PROMPT = """You are a hiring manager reviewing job-candidate fit.
You will receive a JSON object with:
- "profile": candidate's GitHub repos and detected skills
- "job": job title, company, location, and full description

Return ONLY a JSON object (no markdown, no explanation) with these fields:
{
  "score": <integer 1-10>,
  "why": "<1-2 sentences explaining fit>",
  "strengths": ["<skill or project that matches>", ...],
  "gaps": ["<skill the job wants but candidate lacks>", ...],
  "experience_fit": "<1 sentence on experience level match>"
}

Scoring guide:
- 9-10: Nearly perfect match, has almost all required skills
- 7-8: Strong match, has most key skills, minor gaps
- 5-6: Partial match, has some skills but notable gaps
- 3-4: Weak match, missing many requirements
- 1-2: Poor match, very different skill set

Be specific — reference the candidate's actual repos/skills by name. Be honest about gaps."""


def _call_ollama(prompt: str, timeout: int = 120) -> str | None:
    """Call local Ollama model. Returns response text or None on failure."""
    import urllib.request
    import urllib.error
    try:
        body = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "system": _LLM_SYSTEM_PROMPT,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 800},
        }).encode()
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return data.get("response", "")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def _call_claude_api(prompt: str) -> str | None:
    """Fallback: call Claude API. Requires ANTHROPIC_API_KEY env var."""
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import urllib.request
        body = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 800,
            "system": _LLM_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"]
    except Exception:
        return None


def _parse_llm_json(text: str) -> dict | None:
    """Extract JSON object from LLM response text."""
    text = text.strip()
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from markdown code block
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try finding first { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def _analyze_job_with_llm(job: dict, profile: dict) -> dict | None:
    """Analyze a single job against a profile using local LLM, Claude fallback."""
    profile_summary = {
        "repos": [r["name"] for r in profile.get("repos", [])[:10]],
        "skills": sorted(profile.get("skills", set())),
    }
    job_summary = {
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "location": job.get("location", ""),
        "description": job.get("description", "")[:4000],
    }
    prompt = json.dumps({"profile": profile_summary, "job": job_summary}, indent=2)

    # Try local Ollama first
    raw = _call_ollama(prompt)
    if raw:
        result = _parse_llm_json(raw)
        if result and "score" in result:
            result["source"] = "local"
            return result

    # Fallback to Claude API
    raw = _call_claude_api(prompt)
    if raw:
        result = _parse_llm_json(raw)
        if result and "score" in result:
            result["source"] = "claude"
            return result

    return None


# ---------------------------------------------------------------------------
# GitHub profile analyzer
# ---------------------------------------------------------------------------

async def _fetch_github_profile(username: str) -> dict:
    """Fetch repos and READMEs from GitHub to build a skill profile."""
    api_headers = {"Accept": "application/vnd.github.v3+json", **BROWSER_HEADERS}
    skills_found: set[str] = set()
    repos_info: list[dict] = []

    async with httpx.AsyncClient(headers=api_headers, follow_redirects=True, timeout=15) as client:
        # Fetch repos
        resp = await client.get(f"https://api.github.com/users/{username}/repos?per_page=30&sort=updated")
        if resp.status_code != 200:
            return {"error": f"GitHub API returned {resp.status_code}", "skills": set(), "repos": []}

        repos = resp.json()
        for repo in repos:
            if repo.get("fork"):
                continue
            name = repo.get("name", "")
            desc = (repo.get("description") or "").lower()
            lang = (repo.get("language") or "").lower()
            topics = [t.lower() for t in repo.get("topics", [])]
            repos_info.append({"name": name, "description": desc, "language": lang, "topics": topics})

            # Extract skills from repo metadata
            if lang:
                skills_found.add(lang)
            for topic in topics:
                skills_found.add(topic)

            # Fetch README for deeper skill extraction
            readme_resp = await client.get(
                f"https://api.github.com/repos/{username}/{name}/readme",
                headers={**api_headers, "Accept": "application/vnd.github.v3.raw"},
            )
            if readme_resp.status_code == 200:
                readme_text = readme_resp.text.lower()
                for skill in SKILL_KEYWORDS:
                    if skill in readme_text:
                        skills_found.add(skill)

    return {"skills": skills_found, "repos": repos_info}


def _match_job_to_profile(job_text: str, user_skills: set[str], *, card_mode: bool = False) -> dict:
    """Score how well a job matches the user's skill profile.

    card_mode=True uses a title-aware heuristic when full description isn't available.
    """
    text_lower = job_text.lower()

    # Find which skills the job mentions
    job_skills = set()
    for skill in SKILL_KEYWORDS:
        if skill in text_lower:
            job_skills.add(skill)

    if not job_skills and not card_mode:
        return {"score": 0, "matched": set(), "missing": set(), "job_skills": set()}

    matched = user_skills & job_skills
    missing = job_skills - user_skills

    if card_mode:
        # Title-level heuristic: check how relevant the role *sounds* to the user's domain.
        # Since titles are short, also check for broad category keywords.
        role_signals = {
            "ai": 2, "ml": 2, "machine learning": 2, "data scientist": 2,
            "data science": 2, "deep learning": 2, "nlp": 2,
            "software engineer": 1, "developer": 1, "backend": 1, "fullstack": 1,
            "full stack": 1, "data engineer": 1.5, "data analyst": 1,
            "generative ai": 2.5, "gen ai": 2.5, "llm": 2.5, "computer vision": 2,
            "devops": 1, "mlops": 2, "research": 1.5, "automation": 1,
            "python": 1.5, "cloud": 1, "platform": 0.5,
        }
        role_score = 0.0
        for signal, weight in role_signals.items():
            if signal in text_lower:
                role_score += weight

        # Combine: role relevance (0-5) + keyword overlap (0-5)
        role_part = min(role_score, 5.0)
        keyword_part = min(len(matched) * 2.5, 5.0) if job_skills else 0
        score = round(role_part + keyword_part)
    else:
        score = round(len(matched) / len(job_skills) * 10) if job_skills else 0

    return {
        "score": min(score, 10),
        "matched": matched,
        "missing": missing,
        "job_skills": job_skills,
    }


# ---------------------------------------------------------------------------
# Search / detail logic
# ---------------------------------------------------------------------------

def _build_search_url(keywords, location, date_posted, job_type, experience_level, start):
    base = "https://www.linkedin.com/jobs/search/"
    params = {"keywords": keywords, "location": location, "start": str(start)}
    date_map = {"24h": "r86400", "week": "r604800", "month": "r2592000"}
    if date_posted in date_map:
        params["f_TPR"] = date_map[date_posted]
    if job_type:
        params["f_JT"] = job_type.upper()
    exp_map = {"internship": "1", "entry": "2", "associate": "3",
               "mid": "4", "senior": "4", "director": "5", "executive": "6"}
    if experience_level.lower() in exp_map:
        params["f_E"] = exp_map[experience_level.lower()]
    return f"{base}?{'&'.join(f'{k}={v}' for k, v in params.items())}"


def _parse_job_cards(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for card in soup.find_all("div", class_=re.compile(r"job-search-card")):
        title_el = card.find("h3", class_=re.compile(r"base-search-card__title"))
        title = title_el.get_text(strip=True) if title_el else ""
        company_el = card.find("h4", class_=re.compile(r"base-search-card__subtitle"))
        company = company_el.get_text(strip=True) if company_el else ""
        loc_el = card.find("span", class_=re.compile(r"job-search-card__location"))
        loc = loc_el.get_text(strip=True) if loc_el else ""
        time_el = card.find("time")
        posted = time_el.get("datetime", time_el.get_text(strip=True)) if time_el else ""
        link_el = card.find("a", class_=re.compile(r"base-card__full-link"))
        href = link_el.get("href", "") if link_el else ""
        urn = card.get("data-entity-urn", "")
        urn_m = re.search(r"jobPosting:(\d+)", urn)
        url_m = re.search(r"/jobs/view/(\d+)", href)
        jid = (urn_m or url_m).group(1) if (urn_m or url_m) else ""
        if title and jid:
            jobs.append({"id": jid, "title": title, "company": company,
                         "location": loc, "posted": posted,
                         "url": f"https://www.linkedin.com/jobs/view/{jid}"})
    return jobs


async def _search_jobs(keywords, location="Remote", date_posted="month",
                       experience_level="", limit=25):
    all_jobs, start = [], 0
    async with httpx.AsyncClient(headers=BROWSER_HEADERS, follow_redirects=True, timeout=15) as client:
        while len(all_jobs) < limit:
            url = _build_search_url(keywords, location, date_posted, "", experience_level, start)
            try:
                resp = await client.get(url)
            except httpx.RequestError:
                break
            if resp.status_code != 200:
                break
            page = _parse_job_cards(resp.text)
            if not page:
                break
            all_jobs.extend(page)
            if len(page) < 25:
                break
            start += 25
            await asyncio.sleep(1)
    return all_jobs[:limit]


async def _get_job_detail(job_url):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"error": "Playwright not installed"}
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE_DIR), headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = await browser.new_page()
        try:
            await page.goto(job_url, wait_until="domcontentloaded", timeout=20_000)
            if "login" in page.url or "authwall" in page.url:
                return {"error": "Session expired. Run setup_session from Claude Code."}
            try:
                await page.wait_for_selector("h1, .jobs-unified-top-card", timeout=8_000)
            except Exception:
                pass
            page_text = await page.evaluate("() => document.body.innerText")
            lines = [ln.strip() for ln in page_text.split("\n") if ln.strip()]
            page_html = await page.content()
            soup = BeautifulSoup(page_html, "html.parser")
            company_el = soup.find("a", href=re.compile(r"/company/"))
            company = company_el.get_text(strip=True) if company_el else ""
            title = ""
            nav = {"home", "my network", "jobs", "messaging", "notifications",
                   "me", "for business", "skip to main content", "try premium"}
            for i, line in enumerate(lines[:25]):
                if line.lower() in nav or "notification" in line.lower():
                    continue
                if company and line.strip() == company.strip() and i + 1 < len(lines):
                    title = lines[i + 1]
                    break
            location = ""
            for line in lines[:30]:
                if " · " in line and any(k in line.lower() for k in ["ago", "applicant", "click", "reposted", "posted"]):
                    location = line.split(" · ")[0].strip()
                    break
            salary = ""
            sm = re.search(r"\$[\d,]+[kK]?(?:\s*[-–/]\s*\$[\d,]+[kK]?)?(?:\s*(?:per|/)\s*(?:year|yr|hour|hr))?", page_text, re.I)
            if sm:
                salary = sm.group(0)
            description = ""
            for i, line in enumerate(lines):
                if re.match(r"about the job", line, re.I):
                    stop = re.compile(r"^(about the company|similar jobs|people also viewed|show more|set alert|am i a good fit|referrals increase)", re.I)
                    dl = []
                    for ln in lines[i + 1:]:
                        if stop.match(ln):
                            break
                        dl.append(ln)
                    description = "\n".join(dl)
                    break
            apply_el = soup.find("a", href=re.compile(r"/jobs/apply|offsite", re.I))
            apply_url = apply_el.get("href", "") if apply_el else job_url
            jid = re.search(r"/jobs/view/(\d+)", job_url)
            return {"id": jid.group(1) if jid else "", "title": title, "company": company,
                    "location": location, "salary": salary, "description": description[:8000],
                    "apply_url": apply_url, "source_url": job_url}
        except Exception as e:
            return {"error": str(e)}
        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# Prompt parser
# ---------------------------------------------------------------------------

def _parse_prompt(prompt: str) -> dict:
    text = prompt.lower().strip()
    location = "Remote"
    for key, val in sorted(LOCATIONS.items(), key=lambda x: -len(x[0])):
        if key in text:
            location = val
            text = re.sub(re.escape(key), "", text)
            break
    in_match = re.search(r"\bin\s+([\w\s]+?)(?:\s+(?:for|as|with|that|which)|$)", text)
    if in_match and location == "Remote":
        location = in_match.group(1).strip().title()
        text = text[:in_match.start()] + text[in_match.end():]
    experience = ""
    if any(w in text for w in ["fresh grad", "graduate", "entry level", "entry-level", "junior"]):
        experience = "entry"
    elif any(w in text for w in ["senior", "lead"]):
        experience = "senior"
    elif any(w in text for w in ["mid", "intermediate"]):
        experience = "mid"
    elif "intern" in text:
        experience = "internship"
    filler = {"find", "search", "look", "looking", "get", "show", "me", "for", "a", "an",
              "the", "some", "any", "jobs", "job", "roles", "role", "positions", "position",
              "openings", "fresh", "graduate", "graduates", "junior", "entry", "level",
              "senior", "mid", "intern", "internship", "that", "which", "are", "is",
              "related", "to", "with", "about", "please", "can", "you", "i", "want",
              "need", "help", "grads", "grad", "and"}
    words = [w for w in re.split(r"[\s/,]+", text) if w and w not in filler and len(w) > 1]

    # Build smart compound queries instead of splitting into single words.
    # Keep the full phrase as the primary query, then generate meaningful variations.
    core_phrase = " ".join(words).strip()
    queries = []
    if core_phrase:
        queries.append(core_phrase)

    # Generate meaningful multi-word variations (not single words)
    role_synonyms = {
        "ai engineer": ["artificial intelligence engineer", "machine learning engineer", "generative AI developer", "AI developer"],
        "ml engineer": ["machine learning engineer", "AI engineer", "data scientist"],
        "software engineer": ["software developer", "backend engineer", "full stack developer"],
        "data engineer": ["data pipeline engineer", "ETL developer"],
        "data scientist": ["data science", "machine learning scientist", "AI researcher"],
    }
    for key, synonyms in role_synonyms.items():
        if key in core_phrase:
            for syn in synonyms[:2]:  # max 2 synonyms per match
                queries.append(syn)
            break

    if not queries:
        queries = [prompt.strip()]

    seen, unique = set(), []
    for q in queries:
        q_lower = q.lower().strip()
        if q_lower and q_lower not in seen:
            seen.add(q_lower)
            unique.append(q)
    return {"queries": unique[:5], "location": location, "experience": experience}


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Job Research", page_icon="💼", layout="wide")

st.markdown("""
<style>
    .block-container { max-width: 1200px; padding-top: 1.5rem; }
    [data-testid="stSidebar"] { min-width: 340px; }

    .prompt-header {
        background: linear-gradient(135deg, #0a66c2 0%, #004182 100%);
        padding: 1.8rem 2rem 1.2rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.2rem;
    }
    .prompt-header h1 { color: white; font-size: 1.5rem; margin: 0 0 0.3rem 0; }
    .prompt-header p { color: #b0d4f1; font-size: 0.85rem; margin: 0; }

    .search-tags { margin: 0.5rem 0 0.5rem 0; display: flex; gap: 0.5rem; flex-wrap: wrap; }
    .tag { display: inline-block; padding: 3px 10px; border-radius: 14px; font-size: 0.75rem; font-weight: 500; }
    .tag-blue { background: rgba(10,102,194,0.25); color: #58a6ff; }
    .tag-green { background: rgba(46,125,50,0.2); color: #66bb6a; }
    .tag-purple { background: rgba(156,39,176,0.2); color: #ce93d8; }

    .job-card {
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 10px;
        padding: 1.1rem 1.3rem;
        margin-bottom: 0.4rem;
        transition: border-color 0.15s;
    }
    .job-card:hover { border-color: #0a66c2; }
    .job-card-title { font-size: 1rem; font-weight: 600; color: #58a6ff; margin: 0 0 0.25rem 0; line-height: 1.3; }
    .job-card-company { font-size: 0.88rem; font-weight: 500; color: rgba(255,255,255,0.85); margin: 0 0 0.15rem 0; }
    .job-card-meta { font-size: 0.8rem; color: rgba(255,255,255,0.45); margin: 0 0 0.4rem 0; }

    .match-bar { display: flex; align-items: center; gap: 0.5rem; margin-top: 0.3rem; }
    .match-bar-bg { flex: 1; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden; }
    .match-bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
    .match-score { font-size: 0.78rem; font-weight: 600; min-width: 2.5rem; }
    .match-pills { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 0.3rem; }
    .pill { font-size: 0.68rem; padding: 1px 7px; border-radius: 10px; }
    .pill-green { background: rgba(46,125,50,0.25); color: #81c784; }
    .pill-red { background: rgba(211,47,47,0.2); color: #ef9a9a; }

    .detail-panel { border: 1px solid rgba(255,255,255,0.12); border-radius: 12px; padding: 1.8rem 2rem; margin-top: 0.8rem; }
    .detail-title { font-size: 1.4rem; font-weight: 700; color: #58a6ff; margin: 0 0 0.4rem 0; line-height: 1.3; }
    .detail-company { font-size: 1.05rem; color: rgba(255,255,255,0.85); margin: 0 0 0.2rem 0; }
    .detail-location { font-size: 0.9rem; color: rgba(255,255,255,0.55); margin: 0 0 0.5rem 0; }
    .detail-salary { display: inline-block; background: rgba(46,125,50,0.2); color: #66bb6a; padding: 3px 12px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.6rem; }
    .detail-btns { display: flex; gap: 0.7rem; margin: 0.8rem 0 1.2rem 0; }
    .detail-btns a { display: inline-block; padding: 0.45rem 1.4rem; border-radius: 24px; text-decoration: none; font-weight: 600; font-size: 0.85rem; transition: all 0.15s; }
    .btn-apply { background: #0a66c2; color: white !important; }
    .btn-apply:hover { background: #004182; }
    .btn-linkedin { background: transparent; border: 1px solid rgba(255,255,255,0.25); color: rgba(255,255,255,0.75) !important; }
    .btn-linkedin:hover { border-color: #0a66c2; color: #58a6ff !important; }
    .detail-divider { border: none; border-top: 1px solid rgba(255,255,255,0.1); margin: 0 0 1rem 0; }
    .detail-desc-title { font-size: 0.95rem; font-weight: 600; color: rgba(255,255,255,0.9); margin: 0 0 0.7rem 0; }
    .detail-desc { color: rgba(255,255,255,0.72); font-size: 0.88rem; line-height: 1.75; }

    .match-detail-section { border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 1.2rem 1.4rem; margin: 1rem 0; }
    .match-detail-title { font-size: 0.95rem; font-weight: 600; color: rgba(255,255,255,0.9); margin: 0 0 0.6rem 0; }

    .results-header { font-size: 0.85rem; color: rgba(255,255,255,0.45); margin: 0 0 0.6rem 0; }

    .sidebar-skill { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.72rem; margin: 2px; background: rgba(10,102,194,0.2); color: #58a6ff; }
    .sidebar-section { margin-bottom: 1.2rem; }
    .sidebar-title { font-size: 0.85rem; font-weight: 600; color: rgba(255,255,255,0.9); margin: 0 0 0.5rem 0; }
    .sidebar-repo { font-size: 0.8rem; color: rgba(255,255,255,0.7); margin: 0.2rem 0; }
    .improve-item { font-size: 0.82rem; color: rgba(255,255,255,0.75); margin: 0.3rem 0; padding: 0.4rem 0.6rem; border-left: 2px solid #ef9a9a; }

    .card-analysis { font-size: 0.75rem; margin-top: 0.4rem; padding-top: 0.4rem; border-top: 1px solid rgba(255,255,255,0.08); }
    .card-strengths { color: #66bb6a; margin: 0.15rem 0; }
    .card-gaps { color: #ef9a9a; margin: 0.15rem 0; }
    .card-why { color: rgba(255,255,255,0.55); margin: 0.15rem 0; font-style: italic; }

    /* Claude AI analysis cards */
    .ai-card { background: rgba(255,255,255,0.04); border: 1px solid rgba(88,166,255,0.25); border-radius: 10px; padding: 1.2rem 1.4rem; margin-bottom: 1rem; }
    .ai-card-rank { font-size: 0.7rem; color: rgba(255,255,255,0.4); text-transform: uppercase; letter-spacing: 1px; margin: 0 0 0.2rem 0; }
    .ai-card-title { font-size: 1.05rem; font-weight: 600; color: #58a6ff; margin: 0 0 0.1rem 0; }
    .ai-card-company { font-size: 0.88rem; color: rgba(255,255,255,0.7); margin: 0 0 0.3rem 0; }
    .ai-card-meta { font-size: 0.78rem; color: rgba(255,255,255,0.45); margin: 0 0 0.6rem 0; }
    .ai-card-why { font-size: 0.85rem; color: rgba(255,255,255,0.8); margin: 0.5rem 0; line-height: 1.45; }
    .ai-card-label { font-size: 0.75rem; font-weight: 600; margin: 0.4rem 0 0.15rem 0; }
    .ai-card-label-green { color: #66bb6a; }
    .ai-card-label-red { color: #ef9a9a; }
    .ai-card-list { font-size: 0.8rem; color: rgba(255,255,255,0.7); margin: 0 0 0.2rem 0; }
    .ai-card-fit { font-size: 0.78rem; color: rgba(255,255,255,0.5); margin: 0.4rem 0 0; font-style: italic; }
    .ai-section-title { font-size: 1.1rem; font-weight: 600; color: rgba(255,255,255,0.9); margin: 1.2rem 0 0.6rem 0; }
    .ai-improve { font-size: 0.85rem; color: rgba(255,255,255,0.75); margin: 0.3rem 0; padding: 0.5rem 0.8rem; border-radius: 6px; }
    .ai-improve-high { border-left: 3px solid #ef5350; background: rgba(239,83,80,0.06); }
    .ai-improve-medium { border-left: 3px solid #ffa726; background: rgba(255,167,38,0.06); }
    .ai-improve-low { border-left: 3px solid #66bb6a; background: rgba(102,187,106,0.06); }
    .ai-badge { display: inline-block; font-size: 0.65rem; padding: 2px 8px; border-radius: 8px; background: rgba(88,166,255,0.15); color: #58a6ff; margin-bottom: 0.6rem; }

    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# --- State ---
for key, default in [("jobs", []), ("selected_job_id", None), ("job_details_cache", {}),
                      ("last_parsed", None), ("github_profile", None), ("github_username", ""),
                      ("ai_analysis", None), ("current_search_id", None), ("db_loaded", False)]:
    if key not in st.session_state:
        st.session_state[key] = default

# Restore last search from DB on cold start
if not st.session_state.db_loaded:
    st.session_state.db_loaded = True
    latest = db.load_latest_search()
    if latest and not st.session_state.jobs:
        st.session_state.jobs = latest["jobs"]
        st.session_state.job_details_cache.update(latest["details"])
        st.session_state.current_search_id = latest["search_id"]
        st.session_state.last_parsed = {
            "queries": [latest["prompt"]],
            "location": latest["location"] or "",
            "experience": latest["experience"] or "",
        }
        if latest["analyses"]:
            st.session_state.ai_analysis = {
                "generated_at": latest["analyses"][0].get("analyzed_at", ""),
                "github_username": latest["analyses"][0].get("github_username", ""),
                "search_prompt": latest["prompt"],
                "jobs": latest["analyses"],
            }

# ---------------------------------------------------------------------------
# Sidebar — GitHub Profile
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### Your Profile")
    gh_input = st.text_input("GitHub URL or username",
                             value=st.session_state.github_username,
                             placeholder="e.g. octocat")

    if st.button("Analyze Profile", use_container_width=True):
        # Extract username from URL or direct input
        username = gh_input.strip().rstrip("/")
        if "github.com/" in username:
            username = username.split("github.com/")[-1].split("/")[0]
        st.session_state.github_username = username

        if username:
            with st.spinner(f"Analyzing {username}'s GitHub..."):
                profile = _run_async(_fetch_github_profile(username))
                st.session_state.github_profile = profile

    # Display profile info
    profile = st.session_state.github_profile
    if profile and "error" not in profile:
        st.markdown("---")

        # Repos
        repos = profile.get("repos", [])
        if repos:
            st.markdown(f'<div class="sidebar-section"><p class="sidebar-title">Repositories ({len(repos)})</p>', unsafe_allow_html=True)
            for r in repos[:10]:
                lang_badge = f' <span class="sidebar-skill">{r["language"]}</span>' if r["language"] else ""
                st.markdown(f'<p class="sidebar-repo">{r["name"]}{lang_badge}</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # Skills
        skills = sorted(profile.get("skills", set()))
        if skills:
            st.markdown(f'<div class="sidebar-section"><p class="sidebar-title">Skills Detected ({len(skills)})</p>', unsafe_allow_html=True)
            pills = "".join(f'<span class="sidebar-skill">{s}</span>' for s in skills)
            st.markdown(pills, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # Improvement suggestions (based on common job requirements vs user skills)
        st.markdown("---")
        st.markdown("### Areas to Improve")

        high_demand = {
            "react": "Frontend framework — needed for full-stack roles",
            "typescript": "TypeScript — increasingly required alongside Python",
            "nextjs": "Next.js — top frontend framework for AI products",
            "aws": "AWS — most asked cloud platform",
            "gcp": "GCP — popular for ML workloads",
            "azure": "Azure — enterprise AI deployments",
            "kubernetes": "Kubernetes — container orchestration at scale",
            "postgresql": "PostgreSQL — production database skills",
            "redis": "Redis — caching and real-time data",
            "terraform": "Terraform — infrastructure as code",
            "langchain": "LangChain — LLM application framework",
            "rag": "RAG — retrieval-augmented generation pipelines",
            "fastapi": "FastAPI — modern Python API framework",
            "django": "Django — full-featured Python web framework",
        }

        suggestions = []
        for skill, reason in high_demand.items():
            if skill not in profile.get("skills", set()):
                suggestions.append((skill, reason))

        if suggestions:
            for skill, reason in suggestions[:8]:
                st.markdown(f'<div class="improve-item"><b>{skill}</b> — {reason}</div>',
                            unsafe_allow_html=True)
        else:
            st.success("Strong profile! No major gaps detected.")

    elif profile and "error" in profile:
        st.error(profile["error"])
    else:
        st.markdown(
            '<p style="font-size:0.82rem; color:rgba(255,255,255,0.4);">'
            'Enter your GitHub to get match scores and improvement suggestions for each job.'
            '</p>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------

st.markdown("""
<div class="prompt-header">
    <h1>💼 Job Research</h1>
    <p>Describe what you're looking for — we'll search LinkedIn and rate how well you match</p>
</div>
""", unsafe_allow_html=True)

prompt = st.chat_input("e.g. Find me AI engineering jobs in KL for fresh grads")

if prompt:
    st.session_state.selected_job_id = None
    parsed = _parse_prompt(prompt)
    st.session_state.last_parsed = parsed

    # Auto-load GitHub profile if username entered but not yet analyzed
    if gh_input.strip() and not st.session_state.github_profile:
        username = gh_input.strip().rstrip("/")
        if "github.com/" in username:
            username = username.split("github.com/")[-1].split("/")[0]
        st.session_state.github_username = username
        if username:
            with st.spinner(f"Analyzing {username}'s GitHub..."):
                st.session_state.github_profile = _run_async(_fetch_github_profile(username))

    all_jobs, seen_ids = [], set()
    progress = st.progress(0, text="Searching...")
    n_queries = len(parsed["queries"])
    for i, query in enumerate(parsed["queries"]):
        progress.progress((i + 1) / (n_queries + 1),
                          text=f'Searching: "{query}" in {parsed["location"]}')
        results = _run_async(_search_jobs(
            keywords=query, location=parsed["location"],
            experience_level=parsed["experience"], limit=25))
        for job in results:
            if job.get("id") and job["id"] not in seen_ids:
                seen_ids.add(job["id"])
                all_jobs.append(job)

    # Batch-fetch descriptions for top jobs so card scores use full text
    profile = st.session_state.github_profile
    user_skills = profile.get("skills", set()) if profile and "error" not in profile else set()
    cache = st.session_state.job_details_cache  # local ref — safe for threads
    if user_skills and all_jobs:
        to_fetch = [j for j in all_jobs if j["id"] not in cache][:15]
        for idx, job in enumerate(to_fetch):
            progress.progress(
                (n_queries + (idx + 1) / len(to_fetch)) / (n_queries + 1),
                text=f"Fetching details ({idx+1}/{len(to_fetch)})...")
            try:
                detail = _run_async(_get_job_detail(job["url"]))
                if detail and "error" not in detail:
                    cache[job["id"]] = detail
                    db.save_detail(job["id"], detail)
            except Exception:
                pass

    # Run LLM analysis on fetched jobs
    if user_skills and cache:
        analyzed_jobs = []
        fetched_jobs = [j for j in all_jobs if j["id"] in cache and cache[j["id"]].get("description")]
        for idx, job in enumerate(fetched_jobs[:10]):
            progress.progress(
                0.85 + (idx + 1) / max(len(fetched_jobs[:10]), 1) * 0.15,
                text=f"AI analyzing ({idx+1}/{min(len(fetched_jobs), 10)})...")
            detail = cache[job["id"]]
            job_for_llm = {**job, "description": detail.get("description", "")}
            analysis = _analyze_job_with_llm(job_for_llm, profile)
            if analysis:
                analysis["id"] = job["id"]
                analysis["title"] = job.get("title", "")
                analysis["company"] = job.get("company", "")
                analysis["location"] = job.get("location", "")
                analysis["url"] = job.get("url", "")
                analyzed_jobs.append(analysis)

        if analyzed_jobs:
            analyzed_jobs.sort(key=lambda x: x.get("score", 0), reverse=True)
            # Build improvement summary from gaps
            gap_counts: dict[str, int] = {}
            for aj in analyzed_jobs:
                for gap in aj.get("gaps", []):
                    gap_counts[gap] = gap_counts.get(gap, 0) + 1
            top_gaps = sorted(gap_counts.items(), key=lambda x: -x[1])[:6]

            ai_data = {
                "generated_at": __import__("datetime").date.today().isoformat(),
                "github_username": st.session_state.github_username,
                "search_prompt": prompt,
                "jobs": analyzed_jobs,
                "improvement_summary": {
                    "high_priority": [{"skill": g, "reason": f"Mentioned in {c} of your top job matches"} for g, c in top_gaps[:2]],
                    "medium_priority": [{"skill": g, "reason": f"Mentioned in {c} of your top job matches"} for g, c in top_gaps[2:4]],
                    "low_priority": [{"skill": g, "reason": f"Mentioned in {c} of your top job matches"} for g, c in top_gaps[4:6]],
                },
            }
            st.session_state.ai_analysis = ai_data
            # Also save to file for persistence
            ANALYSIS_FILE.write_text(json.dumps(ai_data, indent=2, default=str))
            if st.session_state.current_search_id:
                db.save_analyses(st.session_state.current_search_id,
                                 st.session_state.github_username, analyzed_jobs)

    progress.empty()
    st.session_state.jobs = all_jobs

    # Persist to DB
    search_id = db.save_search(prompt, parsed["location"], parsed["experience"])
    db.save_jobs(search_id, all_jobs)
    st.session_state.current_search_id = search_id

# Search tags
if st.session_state.last_parsed and st.session_state.jobs:
    p = st.session_state.last_parsed
    tags = f'<span class="tag tag-blue">📍 {p["location"]}</span>'
    if p["experience"]:
        tags += f'<span class="tag tag-green">🎓 {p["experience"].title()} level</span>'
    tags += f'<span class="tag tag-purple">🔎 {", ".join(p["queries"][:3])}</span>'
    st.markdown(f'<div class="search-tags">{tags}</div>', unsafe_allow_html=True)


def _render_match_bar(job_text: str, user_skills: set[str]) -> str:
    """Render a match score bar based on job title keywords vs user skills."""
    match = _match_job_to_profile(job_text, user_skills, card_mode=True)
    score = match["score"]
    if score >= 7:
        color = "#66bb6a"
    elif score >= 4:
        color = "#ffa726"
    else:
        color = "#ef5350"
    pct = score * 10
    return f"""
<div class="match-bar">
    <div class="match-bar-bg"><div class="match-bar-fill" style="width:{pct}%;background:{color};"></div></div>
    <span class="match-score" style="color:{color};">{score}/10</span>
</div>"""


# ---------------------------------------------------------------------------
# Helper: render Claude AI analysis from file
# ---------------------------------------------------------------------------

def _render_claude_analysis():
    """Render AI analysis from session state or file."""
    data = st.session_state.ai_analysis
    if not data and ANALYSIS_FILE.exists():
        data = json.loads(ANALYSIS_FILE.read_text())
    if not data:
        st.info("No AI analysis available yet. Search with your GitHub profile loaded to generate one.")
        return

    source_label = "Local AI (Qwen)" if any(j.get("source") == "local" for j in data.get("jobs", [])) else "Claude AI"
    st.markdown(f'<span class="ai-badge">Analyzed by {source_label} \u2022 {data.get("generated_at", "")}</span>',
                unsafe_allow_html=True)

    for i, job in enumerate(data.get("jobs", [])):
        s = job["score"]
        color = "#66bb6a" if s >= 7 else "#ffa726" if s >= 4 else "#ef5350"
        pct = s * 10

        strengths_html = ", ".join(job.get("strengths", []))
        gaps_html = ", ".join(job.get("gaps", [])) or "None \u2014 you cover all listed skills!"

        st.markdown(f"""
<div class="ai-card">
<p class="ai-card-rank">#{i+1} Match</p>
<p class="ai-card-title">{job['title']}</p>
<p class="ai-card-company">{job['company']}</p>
<p class="ai-card-meta">\U0001f4cd {job['location']}  \u2022  Score: <span style="color:{color};font-weight:600;">{s}/10</span></p>
<div class="match-bar">
    <div class="match-bar-bg"><div class="match-bar-fill" style="width:{pct}%;background:{color};"></div></div>
</div>
<p class="ai-card-why">{job['why']}</p>
<p class="ai-card-label ai-card-label-green">\u2705 Your strengths:</p>
<p class="ai-card-list">{strengths_html}</p>
<p class="ai-card-label ai-card-label-red">\U0001f6a7 Gaps to fill:</p>
<p class="ai-card-list">{gaps_html}</p>
<p class="ai-card-fit">\U0001f3af {job.get('experience_fit', '')}</p>
<a href="{job['url']}" target="_blank" style="font-size:0.8rem;color:#58a6ff;">View on LinkedIn \u2197</a>
</div>
""", unsafe_allow_html=True)

    # Improvement summary
    improvements = data.get("improvement_summary", {})
    if improvements:
        st.markdown('<p class="ai-section-title">What to Improve</p>', unsafe_allow_html=True)
        for level, css_class in [("high_priority", "ai-improve-high"), ("medium_priority", "ai-improve-medium"), ("low_priority", "ai-improve-low")]:
            for item in improvements.get(level, []):
                st.markdown(f'<div class="ai-improve {css_class}"><b>{item["skill"]}</b> \u2014 {item["reason"]}</div>',
                            unsafe_allow_html=True)


# --- Detail view ---
if st.session_state.selected_job_id:
    job = next((j for j in st.session_state.jobs if j["id"] == st.session_state.selected_job_id), None)
    if job:
        if st.button("← Back to results"):
            st.session_state.selected_job_id = None
            st.rerun()

        if job["id"] not in st.session_state.job_details_cache:
            with st.spinner("Loading full details..."):
                detail = _run_async(_get_job_detail(job["url"]))
                st.session_state.job_details_cache[job["id"]] = detail
                if detail and "error" not in detail:
                    db.save_detail(job["id"], detail)

        detail = st.session_state.job_details_cache[job["id"]]

        if "error" in detail:
            st.error(detail["error"])
        else:
            title = detail.get("title") or job.get("title", "")
            company = detail.get("company") or job.get("company", "")
            loc = detail.get("location") or job.get("location", "")
            salary = detail.get("salary", "")
            desc = detail.get("description", "")
            apply_url = detail.get("apply_url", job["url"])
            source_url = detail.get("source_url", job["url"])

            salary_html = f'<span class="detail-salary">{salary}</span>' if salary else ""
            desc_escaped = desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            desc_html = f'<hr class="detail-divider"><p class="detail-desc-title">About the job</p><div class="detail-desc">{desc_escaped}</div>' if desc else ""

            st.markdown(f"""
<div class="detail-panel">
<p class="detail-title">{title}</p>
<p class="detail-company">{company}</p>
<p class="detail-location">📍 {loc}</p>
{salary_html}
<div class="detail-btns">
<a class="btn-apply" href="{apply_url}" target="_blank">Apply</a>
<a class="btn-linkedin" href="{source_url}" target="_blank">View on LinkedIn</a>
</div>
{desc_html}
</div>
""", unsafe_allow_html=True)

            # Match analysis (if profile loaded and description available)
            profile = st.session_state.github_profile
            if profile and "error" not in profile and desc:
                user_skills = profile.get("skills", set())
                match = _match_job_to_profile(desc + " " + title, user_skills)
                score = match["score"]
                matched = sorted(match["matched"])
                missing = sorted(match["missing"])

                if score >= 7:
                    color, label = "#66bb6a", "Strong Match"
                elif score >= 4:
                    color, label = "#ffa726", "Partial Match"
                else:
                    color, label = "#ef5350", "Weak Match"

                matched_pills = "".join(f'<span class="pill pill-green">{s}</span>' for s in matched)
                missing_pills = "".join(f'<span class="pill pill-red">{s}</span>' for s in missing)

                st.markdown(f"""
<div class="match-detail-section">
<p class="match-detail-title">Profile Match — <span style="color:{color};">{score}/10 {label}</span></p>
<div class="match-bar">
    <div class="match-bar-bg"><div class="match-bar-fill" style="width:{score*10}%;background:{color};"></div></div>
</div>
<br>
<p style="font-size:0.82rem;color:rgba(255,255,255,0.7);margin:0 0 0.3rem 0;">Skills you have:</p>
<div class="match-pills">{matched_pills if matched_pills else '<span style="font-size:0.78rem;color:rgba(255,255,255,0.4);">None detected</span>'}</div>
<br>
<p style="font-size:0.82rem;color:rgba(255,255,255,0.7);margin:0 0 0.3rem 0;">Skills to build:</p>
<div class="match-pills">{missing_pills if missing_pills else '<span style="font-size:0.78rem;color:rgba(255,255,255,0.4);">None — you cover all listed skills!</span>'}</div>
</div>
""", unsafe_allow_html=True)

# --- Tabbed results: AI Analysis + LinkedIn Search ---
elif st.session_state.jobs or st.session_state.ai_analysis or ANALYSIS_FILE.exists():
    has_analysis = bool(st.session_state.ai_analysis) or ANALYSIS_FILE.exists()
    has_jobs = bool(st.session_state.jobs)

    if has_analysis and has_jobs:
        tab_ai, tab_search = st.tabs(["🤖 AI Analysis", "🔍 LinkedIn Search"])
    elif has_analysis:
        tab_ai, tab_search = st.tabs(["🤖 AI Analysis", "🔍 LinkedIn Search"])
    else:
        tab_ai, tab_search = None, None

    # --- AI Analysis tab ---
    if has_analysis:
        with tab_ai:
            _render_claude_analysis()

    # --- LinkedIn Search tab ---
    target = tab_search if (has_analysis and has_jobs) else None

    if has_jobs:
        container = tab_search if tab_search else st
        with container:
            st.markdown(f'<p class="results-header">{len(st.session_state.jobs)} jobs found</p>',
                        unsafe_allow_html=True)

            profile = st.session_state.github_profile
            user_skills = profile.get("skills", set()) if profile and "error" not in profile else set()

            # Pre-compute scores using full descriptions when available
            jobs_with_scores = []
            for job in st.session_state.jobs:
                match = None
                if user_skills:
                    cached = st.session_state.job_details_cache.get(job["id"])
                    if cached and cached.get("description"):
                        full_text = cached["description"] + " " + job.get("title", "")
                        match = _match_job_to_profile(full_text, user_skills)
                    else:
                        card_text = " ".join([job.get("title", ""), job.get("company", ""), job.get("location", "")])
                        match = _match_job_to_profile(card_text, user_skills, card_mode=True)
                jobs_with_scores.append((match, job))
            jobs_with_scores.sort(key=lambda x: x[0]["score"] if x[0] else 0, reverse=True)

            cols = st.columns(2)
            for i, (match, job) in enumerate(jobs_with_scores):
                with cols[i % 2]:
                    match_html = ""
                    analysis_html = ""
                    if match and user_skills:
                        s = match["score"]
                        color = "#66bb6a" if s >= 7 else "#ffa726" if s >= 4 else "#ef5350"
                        pct = s * 10
                        match_html = f"""
<div class="match-bar">
    <div class="match-bar-bg"><div class="match-bar-fill" style="width:{pct}%;background:{color};"></div></div>
    <span class="match-score" style="color:{color};">{s}/10</span>
</div>"""
                        matched = sorted(match.get("matched", set()))
                        missing = sorted(match.get("missing", set()))
                        if matched:
                            strengths_str = ", ".join(matched[:6])
                            if len(matched) > 6:
                                strengths_str += f" +{len(matched)-6} more"
                            analysis_html += f'<p class="card-strengths">Strengths: {strengths_str}</p>'
                        if missing:
                            gaps_str = ", ".join(missing[:4])
                            if len(missing) > 4:
                                gaps_str += f" +{len(missing)-4} more"
                            analysis_html += f'<p class="card-gaps">Gaps: {gaps_str}</p>'
                        if not matched and not missing:
                            analysis_html += '<p class="card-why">No detailed match data — click View details for full analysis</p>'
                        if analysis_html:
                            analysis_html = f'<div class="card-analysis">{analysis_html}</div>'

                    st.markdown(f"""
<div class="job-card">
<p class="job-card-title">{job['title']}</p>
<p class="job-card-company">{job['company']}</p>
<p class="job-card-meta">📍 {job['location']}  ·  {job['posted']}</p>
{match_html}
{analysis_html}
</div>
""", unsafe_allow_html=True)
                    if st.button("View details", key=f"v_{job['id']}", use_container_width=True):
                        st.session_state.selected_job_id = job["id"]
                        st.rerun()

elif st.session_state.last_parsed:
    st.info("No jobs found. Try a different prompt — e.g. \"software engineer jobs in Selangor\"")
