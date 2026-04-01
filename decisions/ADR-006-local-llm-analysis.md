# ADR-006: Local LLM for Job-Profile Analysis

## Status
Accepted

## Date
2026-03-31

## Context

The Streamlit UI originally used keyword matching to score jobs against a user's GitHub profile.
This produced shallow results — it could match terms like "Python" or "RAG" but couldn't assess
nuance like "this role says 1–3 years but your project portfolio compensates" or identify
non-obvious skill gaps.

Claude Code produces excellent analysis via conversation, but that analysis lives in the chat
and doesn't flow back into the Streamlit UI automatically. We needed AI-quality analysis
inside the app itself.

## Decision

Use **Ollama + Qwen 2.5 14B** as the primary local LLM for job-profile analysis,
with the **Claude API as a fallback** if Ollama is unavailable.

### Why Qwen 2.5 14B?
- 9 GB model that runs on CPU with 16+ GB RAM (no GPU required)
- Strong instruction-following and JSON output compliance
- Good reasoning for scoring/comparison tasks
- ~15–30 seconds per job on CPU — acceptable for batch analysis of 10 jobs

### Analysis pipeline
1. Fetch the user's GitHub profile and pinned repos
2. For each job with a full description, send a structured prompt asking for:
   score (1–10), why, strengths, gaps, experience_fit
3. Parse the JSON response with multiple fallback strategies (regex extraction, partial JSON repair)
4. Display results in an "AI Analysis" tab sorted best-to-worst

### Fallback chain
1. **Ollama** (local, free, private) → primary
2. **Claude API** (remote, paid, requires `ANTHROPIC_API_KEY`) → fallback if Ollama fails
3. **Keyword matching** (no LLM) → always available in the "LinkedIn Search" tab

## Rationale

**Why not always use Claude API?**
- Costs money per call — not ideal for a personal tool used frequently
- Requires an API key, adding setup friction for new users
- Sends job descriptions + GitHub data to an external service

**Why not a smaller model (7B)?**
- Tested reasoning quality: 14B reliably produces structured JSON with nuanced scoring.
  7B models often hallucinate scores or produce malformed JSON.

**Why not a larger model (70B)?**
- Requires 40+ GB RAM or a GPU. The target user (fresh grad) likely has a consumer laptop.

## Consequences

- Users must install Ollama and pull a 9 GB model — documented in README
- First analysis run is slow on CPU (~3–5 minutes for 10 jobs)
- Analysis quality is good but not as nuanced as Claude Opus
- The app works fully offline once Ollama is set up

## Revisit Condition

- If a strong 7B model emerges that reliably outputs structured JSON, switch to reduce RAM requirements
- If Ollama adds GPU acceleration that makes 14B fast enough for real-time use, consider analyzing all jobs instead of top 10
