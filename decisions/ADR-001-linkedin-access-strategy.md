# ADR-001: LinkedIn Access Strategy

## Status
Accepted

## Date
2026-03-30

## Context

We need Claude Code to access LinkedIn job pages to automate job research.
LinkedIn requires authentication — it does not expose public job data without login.

The following options were evaluated:

| Option | Description |
|--------|-------------|
| A | `WebFetch` tool (built into Claude Code) |
| B | Community LinkedIn MCP server (e.g. `stickerdaniel/linkedin-mcp-server`) |
| C | Chrome-based MCP (use existing logged-in browser session) |

## Decision

**Use Chrome-based access (Option C)** — leverage the user's existing, authenticated Chrome browser session rather than re-authenticating via a separate tool.

## Rationale

- `WebFetch` (Option A) **fails on authenticated URLs** by design — LinkedIn requires login, so this is a non-starter.
- LinkedIn MCP servers (Option B) use browser automation under the hood anyway, require separate setup, and introduce another dependency to maintain.
- Chrome-based access (Option C) **reuses the existing login session** — no re-authentication, no API keys, no scraping bans from a fresh session. It also works for any other authenticated site in the future (not just LinkedIn).

## Consequences

- Claude Code must have access to a running Chrome instance.
- User must already be logged into LinkedIn in Chrome.
- This approach generalizes to any authenticated web service, making it reusable beyond LinkedIn.

## Alternatives Considered

### LinkedIn Official API
Rejected — requires LinkedIn partner approval, is heavily rate-limited, and does not expose job search in the same way the UI does.

### Playwright/Puppeteer headless browser
Rejected — creates a new browser session (not authenticated), harder to maintain, prone to bot detection.
