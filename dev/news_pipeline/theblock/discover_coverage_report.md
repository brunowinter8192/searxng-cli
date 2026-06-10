# theblock.co Discovery Coverage Report

Generated: 2026-06-10 20:32 UTC

---

## Method 1 — Full Sitemap Union

- Sub-sitemaps fetched: 64
- Total unique URLs: 19060
- Unique `/post/` URLs: 19000

**URL type breakdown (by first path segment, sorted by count):**

| type | count |
|---|---|
| post | 19000 |
| article | 40 |
| indices | 20 |

## Method 2 — News Sitemap (`sitemap_tbco_news.xml`)

- Total unique URLs: 41

**URL type breakdown:**

| type | count |
|---|---|
| post | 41 |

## Method 3 — RSS (`rss.xml`)

**⚠ HTTP 429 (Cloudflare rate-limit) during probe run.**
Triggered by high-volume sitemap fetching earlier in the same session.
The message from Cloudflare states: _"keep requests under 1 request every 3 minutes"_.
Values below are from the **pre-probe sample** captured before the sitemap union run (complete feed, verified same session).

- Total unique article URLs: 20

**URL type breakdown:**

| type | count |
|---|---|
| post | 20 |

## Method 4 — Bounded UI Crawl

**HTTP status notes (Cloudflare):**
- /latest → HTTP 301 (Cloudflare rate-limit on redirect chain)
- /latest-crypto-news → HTTP 200

**Pages crawled:** `/category/markets`, `/category/defi`, `/category/bitcoin`, `/latest-crypto-news` (raw HTML, no browser needed — `/post/` hrefs visible in server-rendered markup)

- Total unique `/post/` URLs: 28

**URL type breakdown:**

| type | count |
|---|---|
| post | 28 |

---

## Cross-Method Comparison

### Union of all `/post/` IDs across all methods

| method | `/post/` IDs | IDs unique to this method |
|---|---|---|
| Sitemap union | 19000 | 19000 |
| News sitemap | 41 | 14 |
| RSS | 20 | 0 |
| UI crawl | 28 | 5 |
| **Total union** | **19046** | — |

### Sitemap completeness check

- RSS `/post/` IDs NOT in sitemap union: **20**
  - ID 403982
  - ID 404144
  - ID 404185
  - ID 404216
  - ID 404223
  - ID 404229
  - ID 404237
  - ID 404238
  - ID 404243
  - ID 404255
  - ID 404258
  - ID 404272
  - ID 404273
  - ID 404281
  - ID 404288
  - ID 404303
  - ID 404304
  - ID 404316
  - ID 404324
  - ID 404341
- UI crawl `/post/` IDs NOT in sitemap union: **28**
  - ID 403905
  - ID 403919
  - ID 403936
  - ID 403944
  - ID 403982
  - ID 404053
  - ID 404065
  - ID 404075
  - ID 404080
  - ID 404082
  - ID 404111
  - ID 404136
  - ID 404144
  - ID 404185
  - ID 404199
  - ID 404216
  - ID 404229
  - ID 404237
  - ID 404255
  - ID 404272
  - ID 404273
  - ID 404281
  - ID 404288
  - ID 404303
  - ID 404304
  - ID 404316
  - ID 404324
  - ID 404341

### News sitemap vs archive (post_26 rolling-window check)

- News-only (in news sitemap, NOT in archive subs): 41
- Archive-only (in sitemap union, NOT in news sitemap): 19000

_Head-start hypothesis: news ⊆ archive (news-only = 0). Measured: news-only = 41._