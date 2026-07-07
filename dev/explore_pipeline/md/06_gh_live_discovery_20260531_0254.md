# __NEXT_DATA__ Discovery — docs.github.com/de/rest

Date: 2026-05-31 02:54
Method: __NEXT_DATA__ nav-tree extraction (no browser, pure HTTP fetch)

## Recall

| Metric | Value |
|--------|-------|
| Found (normalized union) | 305 |
| FPT sidebar (raw) | 256 |
| GHEC sidebar (raw) | 285 → 36 net additions after normalize |
| GHES sidebar (raw) | 235 |
| Matched gold | 299 / 305 |
| Recall % | 98.0% |
| Missing | 6 |
| Noise | 6 |
| Wall-clock | 0.6s |

## Baseline Comparison

| Strategy | Recall % | Notes |
|----------|----------|-------|
| HTTP BFS Strategy C (Phase A) | 67.2% | crawl4ai BFSDeepCrawlStrategy |
| Playwright BFS 05 (Phase A) | 81.3% | 248/305, /de/rest/ filter |
| __NEXT_DATA__ union (this run) | 98.0% | Pure HTTP, ~1s |

## Discovery Log

## Step 1: __NEXT_DATA__ from seed page
Generic move: Next.js embeds full nav tree in initial HTML — no browser needed.
Found __NEXT_DATA__: 177645 chars  (0.2s)

## Step 2: parse sidebarTree (free-pro-team@latest)
Generic move: sidebarTree in mainContext contains full product nav.
FPT sidebarTree: 256 URLs matching /rest
FPT categories: 58

## Step 3: detect versions via allVersions
Generic move: allVersions lists all content variants — check each for extra nav entries.
Versions found: ['free-pro-team@latest', 'enterprise-cloud@latest', 'enterprise-server@3.21', 'enterprise-server@3.20', 'enterprise-server@3.19', 'enterprise-server@3.18', 'enterprise-server@3.17', 'enterprise-server@3.16']

## Step 4: GHEC sidebarTree (enterprise-cloud@latest)
Partially generic: for any versioned doc site, fetch each version's nav and union.
Site-specific: knowing that enterprise-cloud prefix is /de/enterprise-cloud@latest/.
GHEC sidebarTree: 285 URLs  (0.2s)
GHEC categories: 59
GHEC-only categories: ['announcement-banners', 'enterprise-admin', 'scim']
GHEC normalized to /de/rest/: 285 URLs
GHEC-only pages (not in FPT): 36

## Step 5: GHES sidebarTree (enterprise-server@3.21)
Site-specific: enterprise-server is a distinct deployment model.
GHES sidebarTree: 235 URLs  (0.2s)
GHES-only (not in FPT or GHEC): 13

## Step 6: union discovered URLs (all normalized to /de/rest/...)
Generic move: strip version prefix to collapse all variant URLs to canonical form.
Union normalized: 305 unique /de/rest/... URLs
  FPT raw: 256
  GHEC raw: 285  →  normalized unique additions: 36
  GHES raw: 235  →  normalized unique additions: 13
Discovered URLs saved to: /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/searxng/.claude/worktrees/discover-experiment/dev/explore_pipeline/06_discovered_urls.txt

## Step 8: recall vs goldstandard
Gold: 305 URLs from docs_github_rest.txt
Matched: 299 / 305  (98.0%)
Missing: 6
Noise (extra): 6
Total wall-clock: 0.6s

Missing sample (up to 30):
  - https://docs.github.com/de/rest/projects-classic
  - https://docs.github.com/de/rest/projects-classic/cards
  - https://docs.github.com/de/rest/projects-classic/collaborators
  - https://docs.github.com/de/rest/projects-classic/columns
  - https://docs.github.com/de/rest/projects-classic/projects
  - https://docs.github.com/de/rest/repos/tags

Noise sample (up to 20):
  - https://docs.github.com/de/enterprise-cloud@latest/rest
  - https://docs.github.com/de/enterprise-server@3.21/rest
  - https://docs.github.com/de/rest
  - https://docs.github.com/de/rest/quickstart
  - https://docs.github.com/de/rest/scim
  - https://docs.github.com/de/rest/scim/scim

## All Missing URLs (6)

- https://docs.github.com/de/rest/projects-classic
- https://docs.github.com/de/rest/projects-classic/cards
- https://docs.github.com/de/rest/projects-classic/collaborators
- https://docs.github.com/de/rest/projects-classic/columns
- https://docs.github.com/de/rest/projects-classic/projects
- https://docs.github.com/de/rest/repos/tags