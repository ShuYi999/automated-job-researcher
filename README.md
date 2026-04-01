# Job Research Automation

Automated LinkedIn job search + AI-powered profile matching. Search for jobs, get detailed descriptions, and receive personalized fit scores based on your GitHub portfolio.

## How It Works

```
You (Streamlit UI)
 │
 ├─► LinkedIn Search ──► Job Descriptions ──► AI Analysis (Ollama/Qwen)
 │                                                │
 │                                                ▼
 └─► Tabbed Results: AI Analysis tab + LinkedIn Search tab
         │
         ▼
     SQLite (jobs.db) ──► Persists across refreshes
```

1. **Search** — Your prompt (e.g., "AI engineer jobs in KL for fresh grad") is expanded into compound queries with synonyms, then searched on LinkedIn
2. **Fetch details** — Full job descriptions are scraped for up to 15 jobs via Playwright (authenticated)
3. **Analyze** — A local LLM (Ollama + Qwen 2.5 14B) scores each job against your GitHub profile, identifying strengths, gaps, and experience fit
4. **Persist** — All results are saved to SQLite so they survive browser refreshes

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

The Streamlit UI fetches public search results without auth, but **full job descriptions** require a LinkedIn session. You have two options:

**Option A — Via Claude Code (recommended if you use Claude Code):**
1. Copy `.mcp.json.example` to `.mcp.json` and update the path
2. Run the `setup_session` MCP tool — a browser window opens for you to log in
3. Your session is saved in `mcp-server/browser-profile/` (gitignored)

**Option B — Via the MCP server directly:**
```bash
python mcp-server/server.py
# Then call setup_session from your MCP client
```

Sessions expire after 7 days. Re-run `setup_session` when needed.

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

## Decision Log

| ADR | Decision | Status |
|-----|----------|--------|
| [ADR-001](decisions/ADR-001-linkedin-access-strategy.md) | How to access LinkedIn from Claude | Accepted |
| [ADR-002](decisions/ADR-002-chrome-integration-approach.md) | Which Chrome integration approach to use | Accepted |
| [ADR-003](decisions/ADR-003-poc-findings.md) | POC findings — WebFetch baseline & auth wall map | Accepted |
| [ADR-004](decisions/ADR-004-multi-persona-review.md) | Multi-persona review (SWE, QA, PM) | Accepted |
| [ADR-005](decisions/ADR-005-mcp-server-design.md) | MCP server design (FastMCP + Playwright) | Accepted |

## License

Personal use only. LinkedIn scraping is for individual job research — not for commercial use or bulk data collection.
