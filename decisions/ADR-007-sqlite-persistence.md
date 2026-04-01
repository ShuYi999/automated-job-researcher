# ADR-007: SQLite Persistence for Search Results

## Status
Accepted

## Date
2026-04-01

## Context

The Streamlit UI stored all data in `st.session_state`, which is lost on every browser
refresh or server restart. Users had to re-search, re-fetch job descriptions (slow,
rate-limited), and re-run LLM analysis (3–5 minutes) every time they reloaded the page.

## Decision

Add a **SQLite database** (`jobs.db`) to persist all search data locally.

### Schema (5 tables)

| Table | Purpose |
|-------|---------|
| `searches` | Each search prompt with location, experience, timestamp |
| `jobs` | Unique jobs (deduplicated by LinkedIn job ID) |
| `search_jobs` | Many-to-many link between searches and jobs |
| `job_details` | Full descriptions, salary, apply URL (expensive to fetch) |
| `ai_analyses` | LLM scores, strengths, gaps, experience fit per job |

### Behavior
- On search: save the search, jobs, and link them
- On detail fetch: cache the description so it's never re-fetched
- On LLM analysis: save all scores and reasoning
- On cold start (page refresh): load the latest search with all cached data

## Rationale

**Why SQLite over PostgreSQL/Redis?**
- Zero setup — no server process, just a file
- Ships with Python (no extra dependency)
- Perfect for single-user local tool
- WAL mode allows concurrent reads during writes

**Why not just use session_state?**
- Lost on refresh — the main pain point
- Can't build history over time
- No way to compare across searches

**Why cache job details specifically?**
- Fetching a job description takes ~5 seconds (Playwright + 3s rate limit)
- 15 jobs = ~75 seconds of fetching
- Once cached, descriptions load instantly from SQLite

## Consequences

- `jobs.db` is gitignored (contains personal search history)
- Database grows over time — not a concern for personal use (thousands of jobs = a few MB)
- Cold start loads the most recent search only (not full history)
- No migration system — schema changes require deleting `jobs.db` and starting fresh

## Revisit Condition

- If multi-user support is ever needed, migrate to PostgreSQL
- If search history browsing is added, build a history UI instead of just loading latest
