# ADR-009: Legal Scope & Personal Use Only

## Status
Accepted

## Date
2026-04-08

## Context

This project uses web scraping (via Playwright and httpx) to automate LinkedIn job search and detail fetching. Before expanding the project (e.g., adding Glassdoor scraping, distributing it commercially), we need to explicitly document the legal scope and acceptable use cases.

**Key Questions:**
- Is LinkedIn scraping legal?
- Can we add Glassdoor or other company-review scraping?
- What are the risks and who bears them?
- What disclaimers do we need?

## Decision

**This project is for personal research use only. It must not be used for:**
- Commercial job listing aggregation or resale
- Bulk data extraction for third parties
- Competitive analysis or market research
- Any use that violates the Terms of Service of LinkedIn, Glassdoor, or other platforms

**Scraping Scope:**
1. **LinkedIn (Accepted)** — Job search and detail fetching for personal use
   - Justified: Personal job research is standard practice; bot detection and rate limiting make it respectful
   - Risk: Account suspension (low probability for individual researchers)
   - Mitigation: 3s rate limiting, small batch sizes (~15 jobs/search), session auto-expiry

2. **Glassdoor (Rejected)** — Do NOT add Glassdoor company rating scraping
   - Reason: Adds legal risk without proportional benefit (LLM analysis already scores job fit)
   - Alternative: Use legal third-party APIs if company ratings become critical

3. **Future Platforms** — Any additional scraping must be approved via ADR
   - Evaluate: Terms of Service, legal precedent, rate limiting feasibility, scope creep

## Rationale

### Why LinkedIn is Acceptable for Personal Use
- **Criminal law:** US courts (Ninth Circuit) have ruled that scraping publicly accessible data does not violate the CFAA
- **ToS vs. Law:** LinkedIn's Terms of Service prohibit scraping, but violating ToS is not criminal — it risks account suspension
- **Industry norm:** Job researchers, recruiters, and developers routinely automate job searches for personal use
- **Scale & intent:** This tool is small-scale (1 user, ~15-20 jobs/search), not bulk harvesting
- **Respectful:** 3s rate limiting and session reuse demonstrate intent to minimize server load

### Why Glassdoor is Rejected
- **Redundant benefit:** Job fit is already scored via LLM analysis; company rating adds marginal value
- **Higher risk:** Glassdoor's enforcement is less predictable; blocks IPs more aggressively
- **Scope creep:** Accepting Glassdoor opens door to "why not Indeed, G2, etc.?"
- **Legal safer path:** Third-party APIs (Crunchbase, G2) are legal alternatives if needed later

### Multi-Persona Review

| Persona | Perspective | Decision |
|---------|-------------|----------|
| **SWE** | Feasible? Maintainable? | Yes, current architecture is clean. Adding Glassdoor increases complexity unnecessarily. |
| **QA** | Coverage? Failure modes? | Current test gaps: session expiry, rate limit edge cases. Glassdoor adds more unknowns (IP blocking, DOM changes). |
| **PM** | Scope? User need? | Personal research tool ≠ production service. Company ratings are nice-to-have; not worth legal risk. Users can check Glassdoor manually if needed. |

**Synthesis:** Keep LinkedIn, skip Glassdoor. Document scope clearly so users understand limitations.

## Consequences

**Allowed:**
- ✓ Using this tool for personal job research
- ✓ Sharing the code on GitHub (for others to use for personal research)
- ✓ Discussing how it works in interviews/portfolios
- ✓ Contributing improvements (within personal use scope)

**Not Allowed:**
- ✗ Selling job data extracted via this tool
- ✗ Bulk-scraping for commercial aggregation sites
- ✗ Distributing aggregated LinkedIn/Glassdoor data
- ✗ Using this tool in a commercial SaaS product without explicit API access
- ✗ Circumventing LinkedIn's bot detection to scale beyond personal use

**Enforcement:**
- Users are responsible for their own account and legal compliance
- This project is provided "as-is"; misuse is user's responsibility
- Account bans from LinkedIn are possible; this tool does not guarantee protection

## Revisit Condition

Reconsider this decision if:
1. **LinkedIn's API becomes accessible** — Switch to official API (legal, official, scalable)
2. **Company ratings become critical feature** — Evaluate legal third-party APIs instead of scraping
3. **Legal landscape changes** — Monitor US court precedents on CFAA and scraping; GDPR/CCPA impact
4. **User demand shifts to commercial use** — Require architectural redesign to use only official APIs

## References

- [LinkedIn Service Terms](https://www.linkedin.com/legal/l/service-terms)
- [LinkedIn Help: Prohibited Software](https://www.linkedin.com/help/linkedin/answer/a1341387/prohibited-software-and-extensions?lang=en)
- [Glassdoor Terms of Use](https://www.glassdoor.com/about/terms/)
- [Is Web Scraping Legal? 2026 Compliance Guide](https://sociavault.com/blog/is-web-scraping-legal-compliance-guide)
- [US CFAA & Web Scraping: Ninth Circuit Ruling](https://en.blog.mantiks.io/is-job-scraping-legal/)
