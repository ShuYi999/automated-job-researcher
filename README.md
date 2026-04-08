# Job Research Automation

Automated LinkedIn job search + AI-powered profile matching. Search for jobs, get detailed descriptions, and receive personalized fit scores based on your GitHub portfolio.

⚠️ **Personal Use Only** — This tool is designed for individual job research. See [ADR-009: Legal Scope](#legal-scope--disclaimer) below for important usage guidelines.

## Architecture

### Two Independent Interfaces, Same Data

This project has **two ways to use it** — they share the same LinkedIn session and database, but their code paths are completely separate:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LinkedIn  ·  GitHub API  ·  Ollama               │
│                         (external services)                         │
└──────────┬──────────────────────────────────────┬───────────────────┘
           │                                      │
  ┌────────▼─────────┐                  ┌─────────▼────────┐
  │   frontend.py    │                  │    server.py     │
  │   (Streamlit)    │                  │   (MCP Server)   │
  │                  │                  │                  │
  │  Own httpx code  │                  │  Own httpx code  │
  │  Own Playwright  │                  │  Own Playwright  │
  │  Own LLM calls   │                  │  No LLM logic   │
  └──────┬───────────┘                  └────────┬─────────┘
         │                                       │
    User's browser                          Claude Code
    (localhost:8501)                         (terminal)
         │                                       │
         └──────── Both share ───────────────────┘
                   browser-profile/
                   jobs.db (SQLite)
```

**Path A: Streamlit UI** — You open `localhost:8501` in your browser, type a prompt, and `frontend.py` handles everything internally: searching LinkedIn, fetching details, calling Ollama, rendering results. No MCP involved.

**Path B: Claude Code** — You chat with Claude in the terminal, and Claude calls MCP tools (`search_jobs`, `get_job_detail`) which are served by `server.py` running as a local subprocess. Claude reads the results and responds in natural language.

### What is MCP?

**MCP (Model Context Protocol)** is a standard that lets AI assistants call external tools — like a plugin system. The MCP server in this project (`server.py`) exposes four tools:

| Tool | Auth Required | What It Does |
|------|:---:|---|
| `search_jobs` | No | Search LinkedIn publicly via httpx (titles, companies, locations) |
| `get_job_detail` | Yes | Fetch full job description via Playwright with a saved LinkedIn session |
| `setup_session` | — | Open a visible browser for one-time LinkedIn login |
| `session_status` | — | Check if the saved browser session is still valid |

The MCP server is **not a web server** — it runs as a child process of Claude Code, communicating over **stdio** (stdin/stdout) using JSON-RPC:

```
┌──────────────┐   JSON-RPC over stdio   ┌─────────────────┐
│  Claude Code  │ ──── "call search_jobs" ──►│   server.py    │
│  (AI client)  │ ◄── returns job list ──── │  (MCP server)  │
└──────────────┘                           └─────────────────┘
          ▲                                        ▲
          │                                        │
    Spawned when you              Defined in .mcp.json:
    start Claude Code             python3 server.py
```

When Claude Code starts, it reads `.mcp.json`, spawns `python3 server.py` as a subprocess, and keeps it alive for the session. No ports, no hosting — purely local.

### End-to-End Data Flow (Streamlit)

When you type a prompt like `"Find me AI engineer jobs in KL for fresh grads"`:

**Step 1 — Parse prompt** (`_parse_prompt`)

Your natural language is broken down into structured search parameters:
```
Input:  "Find me AI engineer jobs in KL for fresh grads"
Output: {
  queries: ["AI engineer", "machine learning engineer", "ML engineer"],
  location: "Kuala Lumpur, Malaysia",
  experience: "entry"
}
```
Location aliases are resolved (e.g., "KL" → "Kuala Lumpur, Malaysia"), experience level is detected, and role synonyms are generated.

**Step 2 — Public search** (`_search_jobs` via httpx)

For each query, an HTTP GET request is sent to LinkedIn's public search page (no login needed). The HTML response is parsed with BeautifulSoup to extract job cards — title, company, location, posted date, and URL. Results are de-duplicated across queries. This typically yields ~25-60 jobs.

**Step 3 — Batch fetch details** (`_get_job_detail` via Playwright)

The public search only returns basic card info — no full job descriptions. To get descriptions, the app takes the **top 15 unfetched jobs** and scrapes each one individually using Playwright with your saved LinkedIn session.

"Batch" here means a loop, not parallel requests — each job is fetched one at a time with a **3-second delay** between requests to avoid LinkedIn's bot detection. 15 jobs ≈ 45 seconds.

```python
to_fetch = [j for j in all_jobs if j["id"] not in cache][:15]
for job in to_fetch:
    detail = _get_job_detail(job["url"])  # one at a time, 3s apart
```

**Step 4 — LLM analysis** (`_analyze_job_with_llm`)

For up to 10 jobs that have full descriptions, the app sends your GitHub profile + the job description to an LLM and asks it to score the match:

```
Input:  { profile: {repos, skills}, job: {title, company, description} }
Output: { score: 8, why: "...", strengths: [...], gaps: [...], experience_fit: "..." }
```

The app tries **Ollama first** (local, free, private), then falls back to the **Claude API** if Ollama is unavailable. Both receive the exact same prompt and system instructions — the only difference is where the model runs:

| | Ollama (Qwen 2.5 14B) | Claude API (Sonnet) |
|---|---|---|
| **Runs on** | Your machine (`localhost:11434`) | Anthropic's servers |
| **Cost** | Free | Pay per token |
| **Speed** | ~30-120s per job (CPU) | ~2-5s per job |
| **Privacy** | Fully local, offline-capable | Data sent to Anthropic |
| **Requires** | 16+ GB RAM, Ollama running | `ANTHROPIC_API_KEY` env var |

**Step 5 — Persist and display**

All results are saved to SQLite (`jobs.db`) so they survive browser refreshes. The UI shows two tabs:
- **AI Analysis** — LLM-scored jobs ranked by fit, with strengths/gaps/reasoning
- **LinkedIn Search** — All jobs ranked by keyword heuristic score

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | 3.12 recommended |
| Ollama | Latest | Local LLM runtime |
| Chromium | Via Playwright | For authenticated LinkedIn scraping |

## Quick Start

### 1. Clone and install dependencies

```bash
git clone https://github.com/<your-username>/job-research-automation.git
cd job-research-automation

pip install -r mcp-server/requirements.txt
playwright install --with-deps chromium
```

### 2. Install Ollama and pull the model

```bash
# Install Ollama (Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull Qwen 2.5 14B (~9 GB download, works on CPU with 16+ GB RAM)
ollama pull qwen2.5:14b
```

> **macOS:** `brew install ollama` then `ollama pull qwen2.5:14b`
>
> **Windows:** Download from [ollama.com](https://ollama.com/download) then run the pull command

### 3. Start Ollama

```bash
ollama serve
```

Keep this running in a separate terminal.

### 4. Launch the Streamlit UI

```bash
streamlit run mcp-server/frontend.py
```

### 5. Authenticate with LinkedIn (first time only)

The app can search jobs without login (titles, companies, locations), but **full job descriptions and AI analysis** require a LinkedIn session.

```bash
python mcp-server/setup_login.py
```

This opens a Chromium browser window. Log into LinkedIn normally, then close the window. Your session cookies are saved to `mcp-server/browser-profile/` 

Sessions expire after ~7 days. Re-run the command when needed.

> **If you use Claude Code:** You can also authenticate by running the `setup_session` MCP tool instead. Copy `.mcp.json.example` to `.mcp.json`, update the path, and ask Claude to run `setup_session`.

### 6. Search for jobs

1. Enter your GitHub username in the sidebar
2. Type a search prompt: `"AI engineer jobs in KL and Selangor for fresh grad"`
3. Click **Search LinkedIn**
4. View results in two tabs:
   - **AI Analysis** — LLM-scored jobs with why/strengths/gaps
   - **LinkedIn Search** — Keyword-matched results with heuristic scores

## Using with Dev Containers

If you use VS Code with Dev Containers, just open the repo — `post-create.sh` handles everything automatically (Python deps, Playwright, Ollama, model pull).

## Project Structure

```
job-research-automation/
├── mcp-server/
│   ├── server.py           # MCP server — 4 tools (search, detail, session setup/status)
│   ├── frontend.py         # Streamlit UI — search, analysis, display
│   ├── db.py               # SQLite persistence layer
│   ├── setup_login.py      # Standalone LinkedIn login script
│   └── requirements.txt    # Python dependencies
├── decisions/              # Architecture Decision Records (ADRs)
├── setup/                  # Setup guides
├── .devcontainer/          # Dev container config
├── .mcp.json.example       # MCP config template (copy to .mcp.json)
└── CLAUDE.md               # Agent instructions
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `ANTHROPIC_API_KEY` | (none) | Optional — Claude API fallback if Ollama fails |

The app works fully offline with Ollama. The Claude API key is only used as a fallback if the local model is unavailable.

## Legal Scope & Disclaimer

⚠️ **This project is for personal use only.** It is designed for individual job researchers to automate their own job search. Do not use it for:
- Commercial job listing aggregation or resale
- Bulk data extraction for third parties
- Competitive analysis or market research
- Any use that violates the Terms of Service of LinkedIn or other platforms

**LinkedIn Scraping:** This tool uses Playwright to fetch authenticated job details from LinkedIn. While web scraping of publicly accessible data has been ruled legal by US courts (CFAA), LinkedIn's Terms of Service explicitly prohibit automated scraping. Using this tool risks account suspension. By using this software, you accept this risk and responsibility for your own account.

**Why This Scope?** See [ADR-009: Legal Scope & Personal Use Only](decisions/ADR-009-legal-scraping-scope.md) for the full legal analysis, multi-persona review, and design rationale behind personal-use-only scope.

**Disclaimer:** This software is provided "as-is" without warranty. Users are responsible for:
- Understanding and complying with LinkedIn's Terms of Service
- Respecting rate limiting and not overloading servers
- Compliance with applicable laws (CFAA, GDPR, CCPA, etc.)
- Any account suspensions or legal consequences resulting from misuse

For commercial use or bulk job data, use official APIs:
- LinkedIn Jobs Lookup API (requires partnership approval)
- Indeed API
- Crunchbase API
- G2 API

## Decision Log

| ADR | Decision | Status |
|-----|----------|--------|
| [ADR-001](decisions/ADR-001-linkedin-access-strategy.md) | How to access LinkedIn from Claude | Accepted |
| [ADR-002](decisions/ADR-002-chrome-integration-approach.md) | Which Chrome integration approach to use | Accepted |
| [ADR-003](decisions/ADR-003-poc-findings.md) | POC findings — WebFetch baseline & auth wall map | Accepted |
| [ADR-004](decisions/ADR-004-multi-persona-review.md) | Multi-persona review (SWE, QA, PM) | Accepted |
| [ADR-005](decisions/ADR-005-mcp-server-design.md) | MCP server design (FastMCP + Playwright) | Accepted |
| [ADR-006](decisions/ADR-006-local-llm-analysis.md) | Local LLM for job-profile analysis (Ollama + Qwen) | Accepted |
| [ADR-007](decisions/ADR-007-sqlite-persistence.md) | SQLite persistence for search results | Accepted |
| [ADR-008](decisions/ADR-008-scoring-strategy.md) | Job scoring strategy (keyword heuristic + LLM) | Accepted |
| [ADR-009](decisions/ADR-009-legal-scraping-scope.md) | Legal scope & personal use only | Accepted |

## License

Personal use only. LinkedIn scraping is for individual job research — not for commercial use or bulk data collection.
