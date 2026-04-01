# ADR-002: Chrome Integration Approach

## Status
Accepted

## Date
2026-03-30

## Context

Having decided to use Chrome-based access (ADR-001), two concrete implementation options were evaluated:

| Option | Tool | Mechanism |
|--------|------|-----------|
| 1 | Claude Code built-in `/chrome` | Official Anthropic Chrome extension + Native Messaging API |
| 2 | `chrome-devtools-mcp` (community) | MCP server attaching via Chrome remote debugging port |

## Decision

**Use Option 1 — Claude Code's built-in `/chrome` integration.**

## Rationale

| Criteria | Option 1 (`/chrome`) | Option 2 (`chrome-devtools-mcp`) |
|----------|----------------------|----------------------------------|
| Maintenance | Anthropic-maintained | Community-maintained |
| Stability | Beta but stable | Known bug with Claude Code plugin ([#1149](https://github.com/ChromeDevTools/chrome-devtools-mcp/issues/1149)) |
| Setup complexity | Low (toggle + extension) | Medium (config file + Chrome flags) |
| Paid plan required | Yes | No |
| Browser support | Chrome, Edge | Any Chromium |
| Session access | Yes (existing sessions) | Yes (all tabs + cookies) |

Option 2's `--autoConnect` has an open issue with the Claude Code plugin as of March 2026. Option 1 is the official path and better supported long-term.

## Consequences

- Requires a **paid Anthropic plan** (Pro, Max, Teams, or Enterprise).
- Only works with **Google Chrome or Microsoft Edge** (not Brave, Arc, etc.).
- Requires Claude Code **v2.0.73+** and Chrome extension **v1.0.36+**.
- Setup is a one-time operation; once configured it persists.

## Revisit Condition

If the `/chrome` integration proves too limiting (e.g., cannot control specific tabs, lacks DevTools access), revisit Option 2 once issue [#1149](https://github.com/ChromeDevTools/chrome-devtools-mcp/issues/1149) is resolved.
