# ADR-008: Job Scoring Strategy

## Status
Accepted

## Date
2026-03-31

## Context

The original scoring was binary — jobs either matched all keywords (10/10) or none (0/10).
This made the results useless for prioritization. We needed a scoring system that could:

1. Rank jobs meaningfully from best to worst fit
2. Work with limited information (job title only) AND full descriptions
3. Account for role relevance, not just keyword overlap

## Decision

Implement a **two-tier scoring system**:

### Tier 1: Keyword Heuristic (always available, no LLM needed)

Used in the "LinkedIn Search" tab. Two scoring modes:

**Card mode** (title + company only):
- Role signal score (0–5): weighted matching against role-relevant terms
  - High weight (2.5): "generative ai", "gen ai", "llm engineer"
  - Medium weight (2.0): "ai", "machine learning", "data scientist"
  - Low weight (1.0): "software engineer", "developer", "data engineer"
- Keyword overlap score (0–5): user's skills matched against title text
- Final score: role signal + keyword overlap, capped at 10

**Full description mode** (when description is cached):
- Same approach but matches against the full job description text
- Much more accurate since descriptions contain tech stacks, requirements, etc.

### Tier 2: LLM Analysis (Ollama/Qwen, when available)

Used in the "AI Analysis" tab. The LLM receives:
- Full job description
- User's GitHub profile (repos, languages, README content)
- Structured prompt asking for score (1–10), why, strengths, gaps, experience_fit

The LLM can assess nuance that keywords cannot:
- "Open to fresh grads" vs "requires 3+ years"
- Project portfolio compensating for lack of work experience
- Adjacent skills that transfer (e.g., FastAPI experience for a Django role)

### Query Generation

Search prompts are parsed into **compound queries with synonym expansion**:
- "AI engineer" stays as one phrase (not split into "AI" + "engineer")
- Synonyms added: "AI engineer" → also search "machine learning engineer", "ML engineer"
- Location terms extracted separately
- This prevents irrelevant results like "Customer Service Engineer"

## Rationale

**Why two tiers instead of just LLM?**
- LLM analysis takes 3–5 minutes for 10 jobs — users want instant feedback
- Keyword scores show immediately while LLM analysis runs
- Works without Ollama installed (graceful degradation)

**Why weighted role signals?**
- A job titled "AI Engineer" is inherently more relevant than "Software Engineer" for an AI-focused search, even if both mention Python
- Without weights, a "Software Engineer" posting that lists many technologies would score higher than a focused "AI Engineer" posting

**Why compound queries?**
- Splitting "AI engineer" into separate "AI" and "engineer" searches returned jobs like "Agent - Ocean Export Customer Service" (matches "agent") and "Civil Engineer" (matches "engineer")
- Compound phrases produce dramatically better search results

## Consequences

- Keyword scores are approximate — useful for ranking but not definitive
- LLM scores depend on model quality (Qwen 14B is good but not perfect)
- Two tabs can show different rankings for the same jobs (keyword vs LLM) — this is expected and useful
- Adding new role synonyms requires code changes (no config file)

## Revisit Condition

- If users report irrelevant results, expand the synonym dictionary
- If a fast enough LLM becomes available (~1s per job), merge the two tiers into one
