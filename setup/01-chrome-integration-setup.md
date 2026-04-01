# Setup Guide 01: Chrome Integration

Based on [ADR-002](../decisions/ADR-002-chrome-integration-approach.md).

## Prerequisites

| Requirement | Check |
|-------------|-------|
| Paid Anthropic plan (Pro/Max/Teams/Enterprise) | Required |
| Claude Code v2.0.73+ | `claude --version` |
| Google Chrome or Microsoft Edge | Not Brave/Arc |
| Logged into LinkedIn in Chrome | Manual check |

## Step 1 — Install the Chrome Extension

1. Go to the [Claude Chrome Extension](https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn) on the Chrome Web Store
2. Click **Add to Chrome**
3. Sign in with your **Claude account** (same account as your paid plan)
4. Pin the extension: click the puzzle piece icon → click the thumbtack next to "Claude"

## Step 2 — Enable in Claude Code Settings

1. Open Claude Code desktop app
2. Click your **initials** (bottom-left corner)
3. Go to **Settings**
4. Toggle the **Chrome connector** ON
5. Grant requested permissions

## Step 3 — Activate in a Session

Run either:
```bash
claude --chrome
```
or type `/chrome` inside a Claude Code session.

## Step 4 — Verify LinkedIn Access

Ask Claude:
> "Open LinkedIn and go to the Jobs page"

Claude should navigate to `https://www.linkedin.com/jobs/` using your existing session.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Extension not connecting | Sign out and back into extension with the same Claude account |
| "Chrome integration not available" | Update Claude Code: `npm update -g @anthropic-ai/claude-code` |
| LinkedIn shows login page | Make sure you're logged into LinkedIn in Chrome before activating `/chrome` |
| Works on Chrome but not Edge | Feature parity may lag — prefer Chrome |

## Next Steps

Once verified, see `scripts/` for reusable LinkedIn job search automations.
