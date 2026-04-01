# ADR-005: MCP Server Design

## Status
Accepted

## Date
2026-03-30

## Context

The job research automation system needed to be exposed as a queryable MCP server
so it can be invoked directly from Claude Code without manual script execution.

## Decision

Build a **Python FastMCP server** (`mcp` package) with four tools:

| Tool | Backend | Auth needed |
|------|---------|-------------|
| `search_jobs` | httpx (public HTTP) | No |
| `get_job_detail` | Playwright (persistent profile) | Yes |
| `setup_session` | Playwright (visible window) | No (initiates it) |
| `session_status` | Playwright (headless check) | No |

## Rationale

**Why FastMCP over raw MCP SDK?**
FastMCP (`mcp.server.fastmcp.FastMCP`) is the high-level Python interface —
it handles the MCP protocol, tool registration, and server lifecycle automatically
via `@mcp.tool()` decorators. No boilerplate JSON schema definitions needed.

**Why split into two backends (httpx + Playwright)?**
As found in ADR-003: search results (title/company/location) are publicly accessible.
Using httpx for search is faster, lighter, and doesn't consume the Playwright session.
Playwright is reserved for full job detail extraction which requires auth.

**Why a persistent `browser-profile/` directory?**
Playwright's `launch_persistent_context(user_data_dir=...)` saves all cookies/sessions
to disk. The user logs in once via `setup_session` and all subsequent `get_job_detail`
calls reuse the saved session — no re-login needed.

**Why rate limit Playwright calls at 3s?**
ADR-004 SWE recommendation: LinkedIn detects rapid automated requests and temporarily
bans the session. 3s delay is a conservative safe value for personal research use.

## Consequences

- User must run `setup_session` once before `get_job_detail` works.
- Session will occasionally expire (LinkedIn sessions last weeks-months); re-run `setup_session`.
- The `browser-profile/` directory contains sensitive session cookies — do not commit it to git.
- `search_jobs` is always available (no auth dependency) and can be used for bulk listing.

## Revisit Condition

If LinkedIn implements stricter bot detection that blocks persistent-profile Playwright,
revisit using a real browser extension approach (ADR-002 Option 1: `/chrome` integration).
