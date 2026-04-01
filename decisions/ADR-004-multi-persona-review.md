# ADR-004: Multi-Persona Review — POC & Architecture

## Status
Accepted

## Date
2026-03-30

## Context

After completing the POC (ADR-003), the architecture and findings were reviewed by three personas — SWE, QA, and PM — to stress-test assumptions, identify gaps, and align on next steps before building automation scripts.

---

## Persona Reviews

---

### SWE (Software Engineer)

**Verdict: Proceed with Chrome integration — but design the hybrid architecture carefully.**

**What works well:**
- The hybrid WebFetch + Chrome approach is architecturally sound. WebFetch for pagination is cheap and stateless; Chrome for detail extraction is expensive and stateful. Separating these concerns is the right call.
- Using `&start=N` for LinkedIn search pagination is reliable and well-documented behavior.
- No scraping infrastructure needed — we're piggybacking on the user's existing authenticated session, which is the lowest-friction path.

**Concerns:**
- **Rate limiting / bot detection:** LinkedIn actively detects automation. Even with a real authenticated session, rapid sequential requests to job detail pages will trigger throttling or temporary bans. The scripts must include deliberate delays (e.g., 2–5s between requests) and should not run in tight loops.
- **DOM instability:** LinkedIn's frontend is a React SPA with frequent A/B tests. CSS selectors and DOM structure will break. Extraction logic should rely on semantic content (job title text, description text) rather than brittle class names.
- **Session expiry:** Chrome sessions expire. The system must gracefully handle re-auth prompts rather than silently returning empty data.
- **No official API:** This entire approach is against LinkedIn's ToS for automated scraping. It's fine for personal research use but cannot be productionized or run at scale.

**Recommendations:**
- Build a rate-limited job detail fetcher with configurable delay.
- Use text-based extraction prompts to Claude (not CSS selectors) — more resilient to DOM changes.
- Add a session health check at the start of each automation run.

---

### QA (Quality Assurance Engineer)

**Verdict: The POC is valid but the test coverage has gaps — define acceptance criteria before scripting.**

**What the POC tested well:**
- Confirmed the exact auth wall boundary (search results = partial, collections/detail = full wall). This is a useful, reproducible finding.
- The data accessibility map in ADR-003 is a good test matrix — it can directly become a test checklist.

**Gaps identified:**

| Gap | Risk | Priority |
|-----|------|----------|
| No test for LinkedIn login session expiry handling | Silent failure returns no data | High |
| No test for LinkedIn's "sign in to see more" mid-scroll wall | Truncated results without error | High |
| No test for jobs with no salary listed | Automation assumes salary field exists | Medium |
| No test for Easy Apply vs external apply flows | Different DOM structure breaks extraction | Medium |
| No test for multi-page search pagination | May miss jobs after page 1 | Medium |
| No negative test (invalid search terms) | Unhandled edge case | Low |

**Recommendations:**
- Define a test fixture: a known stable job listing (posted by a large company unlikely to close) to use as a regression anchor.
- Add an assertion layer: before returning results, validate that key fields (title, company, description) are non-empty.
- Log raw HTML snapshots on failure so bugs can be reproduced without re-running Chrome.
- Smoke test: a single job detail fetch that confirms the Chrome session is alive and authenticated.

---

### PM (Product Manager)

**Verdict: Strong foundation — but define the user workflow before building more infrastructure.**

**What's working:**
- The decision trail (ADR-001 through ADR-004) is excellent. Anyone picking this up later can understand every tradeoff made and why. This is rare and valuable.
- The hybrid WebFetch + Chrome approach optimizes for cost (Chrome automation is slower/heavier) — good instinct.
- Personal use scope is clear and appropriate. No ToS overreach.

**Questions the team should answer before next sprint:**

1. **What is the actual job research workflow?**
   - Are we searching by keyword + location? By company? By job type?
   - Do we want to save jobs to a local file, score them, or compare against a resume?

2. **What does "done" look like for this POC phase?**
   - Suggested definition: "Claude can fetch 10 job listings with full descriptions and output a structured JSON file."

3. **What's the north star?**
   - Possible: "Given my resume, find and rank the top 10 matching jobs posted in the last 24 hours."
   - This shapes what fields we actually need to extract and whether salary/skills matter.

4. **Maintenance ownership:**
   - LinkedIn UI changes regularly. Who will update extraction logic when it breaks?
   - Recommend: treat this as a personal tool, not a product — keep it simple, single-file scripts.

**Recommendations:**
- Write a one-paragraph "user story" in the README before building scripts.
- Timebox the Chrome integration setup to 1 session — if it doesn't work in an hour, fall back to copy-paste workflow.
- Define v1 scope: search → list → detail for 1 job. Everything else is v2.

---

## Synthesis & Decisions

| Theme | Decision |
|-------|----------|
| Architecture | Proceed with WebFetch (list) + Chrome (detail) hybrid |
| Rate limiting | Enforce 2–5s delay between Chrome detail fetches |
| Extraction method | Use Claude text prompts on page content, not CSS selectors |
| Error handling | Add session health check + non-empty field assertions |
| Scope | v1 = search → list → fetch 1 job detail → structured output |
| ToS | Personal research use only — no scale, no automation loop |

## Consequences

- The `scripts/` folder will contain a rate-limited, text-extraction-based job fetcher.
- A `tests/` or `fixtures/` directory should be added with a known stable job for regression.
- The README should be updated with a user story before scripting begins.
