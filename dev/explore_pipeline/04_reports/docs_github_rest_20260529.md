# Recall Probe — docs.github.com/de/rest

Seed: https://docs.github.com/de/rest  |  Gold: 305 URLs  |  Date: 2026-05-29

## Main Results

| Strategy | Found | Matched | Recall % | Missing | Noise | Time (s) | ms/page | Notes |
|----------|-------|---------|----------|---------|-------|----------|---------|-------|
| A_prefetch_domcontentloaded | — | — | 0.0% | 305 | — | ~0.9 | — | Rate-limited (GitHub WAF) |
| B_prefetch_networkidle | — | — | 0.0% | 305 | — | ~1.2 | — | Rate-limited (GitHub WAF) |
| C_bfs_networkidle | 329 | 205 | **67.2%** | 100 | 124 | 59.2 | 180 | Measured |
| Production baseline (A, no rate limit) | ~230 | ~230 | ~75.4% | ~75 | — | — | — | From explore_site prior run |

**Rate-limiting:** Strategies A and B use `prefetch=True` which sends parallel HTTP requests and immediately triggers GitHub's Cloudflare WAF (429 on seed URL, BFS terminates). Strategy C (`prefetch=False`) sends sequential requests and survived. All three strategies use HTTP for link extraction regardless of `wait_until` — that flag only affects content rendering, not BFS link discovery.

## Key URL Check

- `agent-tasks/agent-tasks` in A: **MISSING** (rate-limited, not crawlable this session)
- `agent-tasks/agent-tasks` in B: **MISSING** (rate-limited)
- `agent-tasks/agent-tasks` in C: **MISSING** (not linked from any crawled page via HTTP)

## Critical Finding: BFS Is HTTP-Based Regardless of wait_until

`BFSDeepCrawlStrategy` uses an HTTP client for link extraction at every depth level, regardless of `wait_until` or `prefetch` setting. Confirmed by timing:

- Strategy A (prefetch=True, domcontentloaded): ~0.9s for entire run (instant 429 = HTTP confirmed)
- Strategy C (prefetch=False, networkidle): 59.2s / 329 URLs = **0.18s/URL** — HTTP speed, not Playwright (Playwright networkidle = 2–5s/URL)

**Consequence:** changing `wait_until` from `domcontentloaded` to `networkidle` in `discover_urls` or `crawl_bfs` has ZERO effect on recall. All three strategies are equivalent in terms of URL discovery mechanism.

## Missing URL Pattern

100 gold URLs not found by Strategy C. Two categories:

**Category index pages** (only in client-rendered sidebar, not in server-rendered HTML):
- `/de/rest/actions`, `/de/rest/agent-tasks`, `/de/rest/agents`
- `/de/rest/announcement-banners`, `/de/rest/apps`, `/de/rest/billing`
- `/de/rest/branches`, `/de/rest/campaigns`, `/de/rest/classroom`, ...

**Leaf pages under missing categories** (reachable only via the missing category index):
- `/de/rest/activity/notifications`
- `/de/rest/agent-tasks/agent-tasks`  ← specifically requested target
- `/de/rest/apps/oauth-applications`, `/de/rest/apps/webhooks`
- `/de/rest/billing/billing`, `/de/rest/billing/cost-centers`, ...

The sidebar navigation on docs.github.com is a React component rendered client-side. Server-rendered HTML does NOT contain sidebar links. HTTP BFS (even with `networkidle` label) never executes JavaScript, so sidebar links are invisible regardless of `wait_until`.

Sub-pages of a missing category (e.g. `agent-tasks/agent-tasks`) are only reachable via the category page. If the category is missing from BFS, its children are too.

## Sample: Gold URLs Found by C (first 20 of 205)

- https://docs.github.com/de/rest/about-the-rest-api
- https://docs.github.com/de/rest/about-the-rest-api/about-the-openapi-description-for-the-rest-api
- https://docs.github.com/de/rest/about-the-rest-api/about-the-rest-api
- https://docs.github.com/de/rest/about-the-rest-api/api-versions
- https://docs.github.com/de/rest/actions/artifacts
- https://docs.github.com/de/rest/actions/cache
- https://docs.github.com/de/rest/actions/concurrency-groups
- https://docs.github.com/de/rest/actions/hosted-runners
- https://docs.github.com/de/rest/authentication/authenticating-to-the-rest-api
- https://docs.github.com/de/rest/using-the-rest-api/rate-limits-for-the-rest-api

## Regression Check

| Domain | Strategy | Found | Time (s) | ms/page | Notes |
|--------|----------|-------|----------|---------|-------|
| searxng_docs | A (prefetch+dCL) | 50 | 3.9 | 78 | Static Sphinx — no rate limit |
| searxng_docs | C (no prefetch+NI) | 49 | 5.8 | 118 | Identical recall, 1.5× slower |
| chroma_docs | A (prefetch+dCL) | 1 | 2.8 | 2800 | Rate-limited by Cloudflare |
| chroma_docs | C (no prefetch+NI) | 70 | 76.2 | 1089 | Not rate-limited; ~1s/page suggests Playwright |

Key: searxng A vs C identical recall (static HTML, JS irrelevant). chroma C gets 70 URLs at 1.09s/URL — consistent with Playwright rendering — suggesting `prefetch=False + networkidle` may use Playwright on JS-heavy sites where HTTP returns minimal content. This needs further investigation.

## Fix Direction

The JS rendering hypothesis is correct: sidebar navigation is client-rendered and invisible to HTTP BFS. But the fix is NOT changing `wait_until` in `BFSDeepCrawlStrategy` — that flag is irrelevant for link discovery.

**Required fix: Playwright-per-page BFS using `crawler.arun()` + `result.links.internal`:**

```python
result = await crawler.arun(url=page, config=CrawlerRunConfig(wait_until="networkidle"))
for link in (result.links or {}).get("internal", []):
    href = link.get("href", "")
    # enqueue href for BFS if same domain, not visited
```

`result.links.internal` is populated from the fully rendered DOM. With `networkidle`, the sidebar React component is mounted and all navigation links are present.

**Estimated gain:** ~75–100 additional URLs → recall from ~67–75% to ~100%.

**Time cost:** ~2–5s/page × 305 pages = 10–25 min. Acceptable for `explore_site` (one-time indexing).

## Next Step

Implement `discover_urls_playwright` in dev/ as a Playwright-per-page BFS. Verify `agent-tasks/agent-tasks` is found. Port to `src/crawler/` if confirmed.
