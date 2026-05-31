# __NEXT_DATA__ Discovery — docs.github.com/de/rest

Date: 2026-05-31 02:53
Method: __NEXT_DATA__ nav-tree extraction (no browser, pure HTTP fetch)

## Recall

| Metric | Value |
|--------|-------|
| Found (union) | 776 |
| FPT sidebar | 256 |
| GHEC sidebar | 285 |
| GHES sidebar | 235 |
| Matched gold | 254 / 305 |
| Recall % | 83.3% |
| Missing | 51 |
| Noise | 522 |
| Wall-clock | 7.1s |

## Baseline Comparison

| Strategy | Recall % | Notes |
|----------|----------|-------|
| HTTP BFS Strategy C (Phase A) | 67.2% | crawl4ai BFSDeepCrawlStrategy |
| Playwright BFS 05 (Phase A) | 81.3% | 248/305, /de/rest/ filter |
| __NEXT_DATA__ union (this run) | 83.3% | Pure HTTP, ~7s |

## Discovery Log

## Step 1: __NEXT_DATA__ from seed page
Generic move: Next.js embeds full nav tree in initial HTML — no browser needed.
Found __NEXT_DATA__: 177645 chars  (2.2s)

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
GHEC sidebarTree: 285 URLs  (2.8s)
GHEC categories: 59
GHEC-only categories: ['announcement-banners', 'enterprise-admin', 'scim']

## Step 5: GHES sidebarTree (enterprise-server@3.21)
Site-specific: enterprise-server is a distinct deployment model.
GHES sidebarTree: 235 URLs  (2.1s)

## Step 6: union discovered URLs
Union total: 776 unique URLs
  FPT: 256
  GHEC: 285
  GHES: 235
Discovered URLs saved to: /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/searxng/.claude/worktrees/discover-experiment/dev/explore_pipeline/06_discovered_urls.txt

## Step 8: recall vs goldstandard
Gold: 305 URLs from docs_github_rest.txt
Matched: 254 / 305  (83.3%)
Missing: 51
Noise (extra): 522
Total wall-clock: 7.1s

Missing sample (up to 30):
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
  - https://docs.github.com/de/rest/enterprise-admin/enterprise-roles
  - https://docs.github.com/de/rest/enterprise-admin/enterprises
  - https://docs.github.com/de/rest/enterprise-admin/global-webhooks
  - https://docs.github.com/de/rest/enterprise-admin/ldap
  - https://docs.github.com/de/rest/enterprise-admin/licensing
  - https://docs.github.com/de/rest/enterprise-admin/manage-ghes
  - https://docs.github.com/de/rest/enterprise-admin/network-configurations
  - https://docs.github.com/de/rest/enterprise-admin/org-pre-receive-hooks
  - https://docs.github.com/de/rest/enterprise-admin/organization-installations
  - https://docs.github.com/de/rest/enterprise-admin/orgs
  - https://docs.github.com/de/rest/enterprise-admin/pre-receive-environments
  - https://docs.github.com/de/rest/enterprise-admin/pre-receive-hooks

Noise sample (up to 20):
  - https://docs.github.com/de/enterprise-cloud@latest/rest
  - https://docs.github.com/de/enterprise-cloud@latest/rest/about-the-rest-api
  - https://docs.github.com/de/enterprise-cloud@latest/rest/about-the-rest-api/about-the-openapi-description-for-the-rest-api
  - https://docs.github.com/de/enterprise-cloud@latest/rest/about-the-rest-api/about-the-rest-api
  - https://docs.github.com/de/enterprise-cloud@latest/rest/about-the-rest-api/api-versions
  - https://docs.github.com/de/enterprise-cloud@latest/rest/about-the-rest-api/breaking-changes
  - https://docs.github.com/de/enterprise-cloud@latest/rest/about-the-rest-api/comparing-githubs-rest-api-and-graphql-api
  - https://docs.github.com/de/enterprise-cloud@latest/rest/actions
  - https://docs.github.com/de/enterprise-cloud@latest/rest/actions/artifacts
  - https://docs.github.com/de/enterprise-cloud@latest/rest/actions/cache
  - https://docs.github.com/de/enterprise-cloud@latest/rest/actions/concurrency-groups
  - https://docs.github.com/de/enterprise-cloud@latest/rest/actions/hosted-runners
  - https://docs.github.com/de/enterprise-cloud@latest/rest/actions/oidc
  - https://docs.github.com/de/enterprise-cloud@latest/rest/actions/permissions
  - https://docs.github.com/de/enterprise-cloud@latest/rest/actions/secrets
  - https://docs.github.com/de/enterprise-cloud@latest/rest/actions/self-hosted-runner-groups
  - https://docs.github.com/de/enterprise-cloud@latest/rest/actions/self-hosted-runners
  - https://docs.github.com/de/enterprise-cloud@latest/rest/actions/variables
  - https://docs.github.com/de/enterprise-cloud@latest/rest/actions/workflow-jobs
  - https://docs.github.com/de/enterprise-cloud@latest/rest/actions/workflow-runs

## All Missing URLs (51)

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
- https://docs.github.com/de/rest/enterprise-admin/enterprise-roles
- https://docs.github.com/de/rest/enterprise-admin/enterprises
- https://docs.github.com/de/rest/enterprise-admin/global-webhooks
- https://docs.github.com/de/rest/enterprise-admin/ldap
- https://docs.github.com/de/rest/enterprise-admin/licensing
- https://docs.github.com/de/rest/enterprise-admin/manage-ghes
- https://docs.github.com/de/rest/enterprise-admin/network-configurations
- https://docs.github.com/de/rest/enterprise-admin/org-pre-receive-hooks
- https://docs.github.com/de/rest/enterprise-admin/organization-installations
- https://docs.github.com/de/rest/enterprise-admin/orgs
- https://docs.github.com/de/rest/enterprise-admin/pre-receive-environments
- https://docs.github.com/de/rest/enterprise-admin/pre-receive-hooks
- https://docs.github.com/de/rest/enterprise-admin/repo-pre-receive-hooks
- https://docs.github.com/de/rest/enterprise-admin/rules
- https://docs.github.com/de/rest/enterprise-admin/scim
- https://docs.github.com/de/rest/enterprise-admin/users
- https://docs.github.com/de/rest/oauth-authorizations
- https://docs.github.com/de/rest/oauth-authorizations/oauth-authorizations
- https://docs.github.com/de/rest/orgs/bypass-requests
- https://docs.github.com/de/rest/orgs/custom-properties-for-orgs
- https://docs.github.com/de/rest/orgs/custom-roles
- https://docs.github.com/de/rest/projects-classic
- https://docs.github.com/de/rest/projects-classic/cards
- https://docs.github.com/de/rest/projects-classic/collaborators
- https://docs.github.com/de/rest/projects-classic/columns
- https://docs.github.com/de/rest/projects-classic/projects
- https://docs.github.com/de/rest/repos/bypass-requests
- https://docs.github.com/de/rest/repos/lfs
- https://docs.github.com/de/rest/repos/tags
- https://docs.github.com/de/rest/secret-scanning/alert-dismissal-requests
- https://docs.github.com/de/rest/secret-scanning/delegated-bypass
- https://docs.github.com/de/rest/teams/external-groups
- https://docs.github.com/de/rest/teams/team-sync