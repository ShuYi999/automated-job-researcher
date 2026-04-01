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
- **ToS:** LinkedIn automation is for personal use only
- **Rate limiting:** Always enforce delays between automated requests (2–5s minimum)
- **Extraction:** Use semantic/text-based extraction — avoid brittle CSS selectors
- **Scripts:** Keep single-file, readable, and documented with inline comments

---

## Directory Structure

```
decisions/    ADR documents — one file per decision
setup/        Step-by-step setup guides
scripts/      Reusable automation scripts
```
