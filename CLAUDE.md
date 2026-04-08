# Agent Instructions

This file is agent-agnostic. It applies to Claude Code, Cursor, Copilot, or any AI agent working in this project.

---

## Decision Making: ADR Format

All non-trivial decisions in this project are documented as **Architecture Decision Records (ADRs)** in the `decisions/` directory.

### When to write an ADR
- Choosing between two or more implementation approaches
- Accepting a known limitation or tradeoff
- Changing a previously accepted decision
- Any decision that would be confusing to a future reader without context

### ADR file naming
```
decisions/ADR-NNN-short-title.md
```
Where `NNN` is zero-padded (001, 002, ...).

### ADR template

```markdown
# ADR-NNN: Title

## Status
[Proposed | Accepted | Deprecated | Superseded by ADR-NNN]

## Date
YYYY-MM-DD

## Context
What is the situation? What forces are at play?

## Decision
What was decided?

## Rationale
Why this option over the alternatives?

## Consequences
What becomes easier or harder as a result?

## Revisit Condition (optional)
Under what circumstances should this decision be reconsidered?
```

### ADR index
Keep `README.md` updated with a Decision Log table linking to each ADR.

---

## Multi-Persona Review

Before committing to a significant implementation, run a **3-persona review** documented as an ADR:

| Persona | Focus |
|---------|-------|
| **SWE** | Technical correctness, edge cases, maintainability, failure modes |
| **QA** | Test coverage gaps, acceptance criteria, regression anchors |
| **PM** | Scope creep, user workflow, definition of done, tradeoffs |

Document the synthesis (agreed decisions) at the bottom of the review ADR.

---

## Project Conventions

- **Language:** English
- **Scope:** Personal research tool — not for production or scale
- **Legal:** Personal use only. See [ADR-009](decisions/ADR-009-legal-scraping-scope.md) for full scope and legal analysis
  - ✓ Allowed: Individual job research, GitHub sharing, portfolio discussion
  - ✗ Not allowed: Commercial aggregation, bulk scraping, data resale
- **ToS:** LinkedIn automation violates their ToS but is acceptable for personal use at this scale
- **Rate limiting:** Always enforce delays between automated requests (3–5s minimum for Playwright, 1s minimum for httpx pagination)
- **Extraction:** Use semantic/text-based extraction — avoid brittle CSS selectors (LinkedIn changes DOM frequently)
- **Scripts:** Keep single-file, readable, and documented with inline comments

### Before Adding New Features

Before adding new data sources (Glassdoor, Indeed, etc.) or expanding scope:
1. **Check Terms of Service** — Is scraping prohibited?
2. **Assess legal risk** — Criminal vs. ToS violation? Account ban risk?
3. **Document in ADR** — Why add it? What are the tradeoffs?
4. **Consider alternatives** — Is there a legal API we could use instead?

**Default answer to expansion:** No. Personal use scope is intentional. Justify new features in an ADR.

---

## Directory Structure

```
decisions/    ADR documents — one file per decision
setup/        Step-by-step setup guides
scripts/      Reusable automation scripts
```
