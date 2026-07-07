# Playwright-per-page BFS — docs.github.com/de/rest

Seed: https://docs.github.com/de/rest  |  Gold: 305 URLs
Date: 2026-05-29 21:41
Config: wait=domcontentloaded, delay=3.0s, timeout=15000ms, concurrency=1, stealth=False

## Recall Results

| Metric | Value |
|--------|-------|
| Found (unique) | 266 |
| Matched gold | 248 / 305 |
| Recall % | 81.3% |
| Missing | 57 |
| Noise (extra) | 18 |
| Total time | 1094.5s |
| Pages fetched | 266 |
| Avg latency | 4112ms |
| Min / Max latency | 3395ms / 5615ms |
| 429 incidents | 0 |
| Stop reason | completed |

## Key URL Check

- `agent-tasks/agent-tasks`: **MISSING ✗**

## Baseline Comparison

| Strategy | Recall % | Notes |
|----------|----------|-------|
| HTTP BFS — Strategy C (Phase A) | 67.2% | crawl4ai BFSDeepCrawlStrategy, HTTP-based |
| Playwright-per-page BFS (this run) | 81.3% | domcontentloaded + 3.0s delay, concurrency=1 |

## Root Cause: Section-Scoped Sidebar Navigation

Post-run diagnostic: the seed page `/de/rest` was re-rendered to inspect its `links.internal` directly.

| Category | In seed's rendered links? |
|----------|--------------------------|
| agent-tasks | ✗ not present |
| announcement-banners | ✗ not present |
| enterprise-admin | ✗ not present |
| copilot/copilot-custom-agents | ✗ not present |
| billing/* | partial — only `billing/budgets` |

The seed page exposes only 35 `/de/rest/*` links in its rendered DOM (3s delay). The missing categories
are not reachable from the seed at all. The GitHub docs sidebar is **section-scoped**: categories
only appear in the sidebar when the user is already inside that section's pages. Since BFS never
reaches those sections (they aren't linked from the seed or from any transitively reachable page),
it cannot discover their children.

**The rendering mechanism is correct** — the single-page check on `/de/rest/agent-tasks` directly
proved that 3s delay + `domcontentloaded` exposes `agent-tasks/agent-tasks` (46 links, all sidebar
items rendered). The recall ceiling is a **navigation topology** constraint, not a rendering one.

## Still Missing (sample of 57 total)

- https://docs.github.com/de/rest/agent-tasks
- https://docs.github.com/de/rest/agent-tasks/agent-tasks
- https://docs.github.com/de/rest/announcement-banners
- https://docs.github.com/de/rest/announcement-banners/enterprises
- https://docs.github.com/de/rest/announcement-banners/organizations
- https://docs.github.com/de/rest/billing/billing
- https://docs.github.com/de/rest/billing/cost-centers
- https://docs.github.com/de/rest/billing/usage-reports
- https://docs.github.com/de/rest/code-scanning/alert-dismissal-requests
- https://docs.github.com/de/rest/copilot/copilot-custom-agents
- https://docs.github.com/de/rest/dependabot/alert-dismissal-requests
- https://docs.github.com/de/rest/enterprise-admin
- https://docs.github.com/de/rest/enterprise-admin/admin-stats
- https://docs.github.com/de/rest/enterprise-admin/announcement
- https://docs.github.com/de/rest/enterprise-admin/audit-log
- https://docs.github.com/de/rest/enterprise-admin/bypass-requests
- https://docs.github.com/de/rest/enterprise-admin/code-security-and-analysis
- https://docs.github.com/de/rest/enterprise-admin/credential-authorizations
- https://docs.github.com/de/rest/enterprise-admin/custom-properties
- https://docs.github.com/de/rest/enterprise-admin/custom-properties-for-orgs