# ADR-003: POC Findings — LinkedIn Access via WebFetch vs Chrome

## Status
Accepted

## Date
2026-03-30

## Context

Before committing to the Chrome integration setup (ADR-002), a POC was run using `WebFetch` (Claude Code's built-in unauthenticated fetcher) against LinkedIn to precisely map where the auth wall falls and what data is freely accessible. This establishes a clear baseline and validates why Chrome integration is needed.

---

## POC Results

### Test 1 — `/jobs/` homepage
- **URL:** `https://www.linkedin.com/jobs/`
- **Result:** Partial access. Shows job category links (Engineering, Finance, etc.) and LinkedIn Learning categories. No individual job listings.
- **Auth wall:** Soft — prompts to sign in but does not block browsing categories.

### Test 2 — Job search results page
- **URL:** `https://www.linkedin.com/jobs/search/?keywords=software+engineer&location=Remote`
- **Result:** **60 job listings visible** per page. Shows: job title, company, location, time posted, job count (e.g. "314,000+ results").
- **Not visible:** Job description, salary, requirements, skills, apply button.
- **Auth wall:** Hard wall on click-through to job detail or apply.

### Test 3 — Job search (last 24h filter)
- **URL:** `https://www.linkedin.com/jobs/search/?keywords=software+engineer&location=Remote&f_TPR=r86400`
- **Result:** Same 60 listings pattern. Rich filter metadata visible (job type counts, company counts, experience level counts). No description or salary.

### Test 4 — Personalized job collections
- **URL:** `https://www.linkedin.com/jobs/collections/recommended/`
- **Result:** Hard login wall. No content visible. Full redirect to sign-in page.

### Test 5 — Direct job view
- **URL:** `https://www.linkedin.com/jobs/view/<id>`
- **Result:** 404 / redirect. Not accessible without session.

---

## Data Accessibility Map

| Data Point | WebFetch (no auth) | Chrome (authenticated) |
|------------|-------------------|----------------------|
| Job title | Yes (60/page) | Yes (all) |
| Company name | Yes | Yes |
| Location | Yes | Yes |
| Posted date | Yes | Yes |
| Job description | No | Yes |
| Salary / compensation | No | Yes (when listed) |
| Required skills | No | Yes |
| Apply button / link | No | Yes |
| Saved jobs / recommendations | No | Yes |
| Easy Apply | No | Yes |

---

## Decision

Confirmed: **Chrome integration is required** for any meaningful job research automation. `WebFetch` alone is insufficient — it provides metadata only (title/company/location) and cannot access descriptions, requirements, or the apply flow.

However, `WebFetch` can be used as a **lightweight pre-filter** (e.g., bulk-fetch search results to get a list of job titles + companies) before handing off to Chrome for detail extraction. This hybrid approach reduces Chrome automation load.

## Consequences

- Chrome integration (ADR-002) is validated and must be completed before automation scripts can be built.
- A hybrid strategy is viable: `WebFetch` for search pagination, Chrome for job detail extraction.
- Scripts should expect a max of ~60 results per `WebFetch` page and paginate using LinkedIn's `&start=N` query param.

## Next Steps

- Complete Chrome integration setup (see `setup/01-chrome-integration-setup.md`)
- Build a script that combines WebFetch (list) + Chrome (detail) in `scripts/`
