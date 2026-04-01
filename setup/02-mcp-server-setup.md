# Setup Guide 02: LinkedIn MCP Server

Based on [ADR-005](../decisions/ADR-005-mcp-server-design.md).

## Prerequisites

- Python 3.12+
- pip3

## Step 1 — Install dependencies

```bash
cd <path-to-repo>/mcp-server
pip3 install -r requirements.txt
playwright install chromium
```

## Step 2 — Test the server starts

```bash
python3 server.py
```

Expected output: `Uvicorn running on ...` or `Serving MCP server ...`
Press Ctrl+C to stop.

## Step 3 — Register the MCP server in Claude Code

The `.mcp.json` at the project root is already configured.
To load it in Claude Code, run from this directory:

```bash
cd <path-to-repo>
claude mcp add linkedin-job-research python3 mcp-server/server.py
```

Or manually verify it's active:
```bash
claude mcp list
```

## Step 4 — Authenticate LinkedIn (one-time)

In a Claude Code session with the MCP loaded, ask:

> "Run the setup_session tool"

A visible Chrome window will open. Log into LinkedIn normally. The session is
saved to `mcp-server/browser-profile/` and reused on all future calls.

## Step 5 — Verify session

> "Run the session_status tool"

Expected: `"authenticated": true`

## Step 6 — Run your first query

> "Search for Python software engineer jobs in Remote posted in the last 24 hours"

> "Get the full details for the first job in the results"

---

## Available Tools

| Tool | Auth | Description |
|------|------|-------------|
| `search_jobs` | No | Search by keyword/location/filters. Returns title, company, location, URL |
| `get_job_detail` | Yes | Full description, salary, requirements, apply URL |
| `setup_session` | No | One-time browser login flow |
| `session_status` | No | Check if LinkedIn session is still active |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `playwright not installed` | `pip3 install playwright && playwright install chromium` |
| `get_job_detail` returns auth error | Run `setup_session` tool again |
| `search_jobs` returns empty list | LinkedIn may be rate-limiting — wait 60s and retry |
| Session expired after days | Re-run `setup_session` |
| MCP server not found in Claude | Verify `.mcp.json` path matches actual server location |
