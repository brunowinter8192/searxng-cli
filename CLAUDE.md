# SearXNG Plugin

Web search and scraping CLI plugin. Note: the plugin keeps the 'searxng' name for historical reasons — the SearXNG Docker wrapper was replaced by a custom pydoll implementation in the engine-cut refactor 2026-04-15.

## Sources

See [sources/sources.md](sources/sources.md).

## Pipeline Components

### Search Pipeline (`src/search/`, mixed browser + HTTP API)

| Component | Implementation | Config |
|-----------|---------------|--------|
| **Engines (active)** | Google, Google Scholar, DuckDuckGo, Mojeek, Lobsters, Semantic Scholar (pydoll); CrossRef, OpenAlex, Stack Exchange, Open Library (HTTP) | 10-engine set; HN dropped 2026-05-04 (rate-limit-cascade-hostile); Bing dropped 2026-05-04 (DOM-drift, replaced by DDG which uses the Bing index); SE added 2026-05-04; Semantic Scholar added 2026-05-07 (bead searxng-10y Step 1; browser-based, API tier 429s instantly); Open Library added 2026-05-08 (bead 10y, books-mode pool widening, HTTP-only, no key) |
| **Engines (plugin)** | ArXiv, GitHub, Reddit | discovery-only, content via MCP plugins |
| **Browser** | pydoll Chrome (stealth fingerprint patches, per-engine JS selectors) | `src/search/browser.py`, `src/search/engines/`, `dev/search_pipeline/` smokes |
| **Rate Limiting** | Token-bucket per engine, uniform 4 req/min; backoff only on CAPTCHA/HTTP-429/exception (not on EMPTY) | `src/search/rate_limiter.py` |
| **Orchestration** | `asyncio.gather` parallel fetch across engines (rate-limiter token acquired at workflow level via `get_limiter(engine.name).acquire()`), merged-and-ranked via `_merge_and_rank` (overlap-counted within general engines, hard slot allocation 12 general / 6 academic / 2 Q&A → 20 URLs, no overflow). Class-filter flags `--general` / `--academic` / `--qa` restrict allocation to selected classes. Filter-flag trio `--books` / `--pdf` / `--docs` (added 2026-05-07, beads gpk/x4f/8gc closed): each restricts engine set + applies query modifier (+book / +pdf / +documentation) + post-merge URL filter via `book_whitelist.py` / `pdf_filter.py` / `docs_filter.py`. cache_key extended with `modifier_id` for cross-flag cache separation. CLI mutex enforced via `add_mutually_exclusive_group()` on search_web/search_batch (search_more keeps separate flags for cache-key matching). Underfill on filter modes is accepted; pooling-rethink in bead g82. Preview-fetched, snippet-selected per source-priority chain producing `snippet_source` label per URL, formatted as TextContent. `search_web_workflow` for single query; `search_batch_workflow` for N queries sequentially in one warm-Chrome session. Disk cache (`~/.cache/searxng/<key>.json`, 1h TTL) stores `snippet_source`, `og`, `meta`, `snippet_display`, and `slot_counts` per URL alongside core fields, backs the `search_more` pagination subcommand. | `src/search/search_web.py`, `src/search/cache.py`, `src/search/{book_whitelist,pdf_filter,docs_filter}.py`, `decisions/search07_ranking_format.md` |
| **Preview** | httpx + lxml fetch of og:description / meta:description for top-20 results, async parallel (concurrency=8, timeout=3.6s via httpx + asyncio.wait_for), returns `(results, stats)` tuple — stats fed into query log | `src/search/preview.py`, see `decisions/search06_preview.md` |
| **Query Log** | Append-only JSONL log written after every `search_web_workflow` call — per-engine `{rate_wait_ms, search_ms, status, result_count, drop_reason}` + preview stats + total_wall_ms + bottleneck_engine. Gitignored. | `src/search/query_logger.py` → `src/logs/query_log.jsonl`; inspect via `dev/search_pipeline/inspect_query_log.py` |
| **Parked** | Brave (PoW CAPTCHA incompatible with parallel architecture); Bing (dropped — DDG uses Bing index, no added value) | See `decisions/stealth.md` |

### Scrape Pipeline (Crawl4AI)

| Component | Implementation | Config |
|-----------|---------------|--------|
| **Browser** | Normal → Stealth fallback chain | networkidle → domcontentloaded → stealth |
| **Filtering** | PruningContentFilter (scrape_url) / Raw (scrape_url_raw) | threshold=0.48, MIN_CONTENT=200 |
| **Garbage Detection** | is_garbage_content() → str\|None | 6 types: crawl4ai_error, http_error, nav_dump, cookie_wall, login_wall, cloudflare |

### Explore Pipeline (Crawl4AI BFS)

| Component | Implementation | Config |
|-----------|---------------|--------|
| **Discovery** | Sitemap → BFS Prefetch cascade | MAX_DEPTH=10, MAX_PAGES=50, TIMEOUT=120s |

### Delivery

| Component | Implementation | Config |
|-----------|---------------|--------|
| **CLI** | `cli.py` via argparse + `~/.local/bin/searxng-cli` wrapper | 7 tools (search_web, search_batch, search_more, scrape_url, scrape_url_raw, explore_site, download_pdf). `scrape_url` and `scrape_url_raw` auto-route TIER1 domains (arxiv, aclanthology, openreview) + direct `.pdf` URLs (excl. GitHub blob) to `download_pdf` via `should_download_as_pdf()`. `download_pdf_workflow` resolves the full chain: HARD_BLACKLIST skip → GitHub blob skip → TIER1 URL transform → DIRECT `.pdf` download → MULTI_STEP `citation_pdf_url` two-hop (57% success on eligible domains). Chain logic in `src/scraper/pdf_chain.py`. |

### Key Files

| File | Component |
|------|-----------|
| `src/search/search_web.py` | Search orchestrator (parallel engine fetch + merge-and-rank + slot-allocate + snippet-select + preview + cache-write) |
| `src/search/preview.py` | URL preview fetcher (og/meta via httpx + lxml, top-20) |
| `src/search/cache.py` | Disk cache for search results (sha256 key, 1h TTL, atomic write) |
| `src/search/browser.py` | pydoll Chrome lifecycle (shared singleton) |
| `src/search/rate_limiter.py` | Per-engine token bucket |
| `src/search/engines/` | Per-engine parsers: `google.py`, `scholar.py`, `crossref.py`, `duckduckgo.py`, `mojeek.py`, `lobsters.py`, `openalex.py`, `stack_exchange.py`, `semantic_scholar.py`, `open_library.py` |
| `src/scraper/scrape_url.py` | URL scraping (filtered) |
| `src/scraper/scrape_url_raw.py` | Raw URL scraping (for RAG indexing) |
| `src/scraper/pdf_chain.py` | PDF URL chain resolution (blacklist, TIER1 transforms, citation_pdf_url multi-step) |
| `src/scraper/download_pdf.py` | PDF file download (uses pdf_chain.py for URL resolution) |
| `src/routing.py` | Plugin domain routing |
| `src/crawler/crawl_site.py` | Full website crawl with markdown export |
| `src/crawler/explore_site.py` | URL discovery — backend for `searxng-cli explore_site` + /crawl-site pipeline |
| `cli.py` | CLI dispatch |

## Project Structure

```
searxng/
├── cli.py                          → CLI dispatch (7 commands incl. search_batch warm-Chrome multi-query + search_more cache-backed pagination)
├── .env.example                    → Template for SEARXNG_PROJECT_ROOT
├── requirements.txt
├── README.md                       → [Setup & External Docs](README.md)
├── DOCS.md                         → [Root Module Docs](DOCS.md)
├── decisions/                      → Pipeline decisions & evidence per step
│   ├── search01_engines.md
│   ├── search02_routing.md
│   ├── search03_ranking.md
│   ├── search04_weights.md
│   ├── search05_engine_expansion.md
│   ├── search06_preview.md
│   ├── search07_ranking_format.md
│   ├── scrape01_browser.md
│   ├── scrape02_filtering.md
│   ├── scrape03_garbage.md
│   ├── scrape04_cloudflare_fastpath.md
│   ├── explore01_discovery.md
│   ├── plugin_routing.md
│   ├── stealth.md
│   └── OldThemes/                  → deferred/historical entries
├── src/                            → [DOCS.md](src/DOCS.md)
│   ├── routing.py                  → Plugin domain routing
│   ├── search/                     → [DOCS.md](src/search/DOCS.md) — search engines (10 active: 6 browser + 4 API)
│   │   └── engines/                → Per-engine parsers (google, scholar, duckduckgo, mojeek, lobsters, crossref, openalex, stack_exchange, semantic_scholar, open_library)
│   ├── scraper/                    → [DOCS.md](src/scraper/DOCS.md)
│   ├── crawler/                    → [DOCS.md](src/crawler/DOCS.md) — CLI-only (`/crawl-site` pipeline)
│   └── spawn/                      → Worker spawn utilities (in src/DOCS.md)
├── dev/                            → [DOCS.md](dev/DOCS.md)
│   ├── search_pipeline/            → [DOCS.md](dev/search_pipeline/DOCS.md) — Per-engine smoke stack (01_google_smoke, 02_burst_smoke, 04_ddg_smoke, 05_search_smoke, 06_mojeek_smoke, 07_lobsters_smoke, 08_scholar_smoke, 09_openalex_smoke, 10_stack_exchange_smoke, config.yml) + full-pipeline smoke (11_pipeline_smoke) + diagnostic scripts (empty_classify_se, empty_classify_lobsters, snippet_quality_analysis) + 01_reports/
│   ├── scrape_pipeline/            → [DOCS.md](dev/scrape_pipeline/DOCS.md) — top-level dual-mode A/B harness (01_dual_mode_smoke) + sub-suites:
│   │   ├── browser_eval/           → scrape01_browser
│   │   ├── filter_eval/            → scrape02_filtering
│   │   └── garbage_eval/           → scrape03_garbage
│   ├── explore_pipeline/           → [DOCS.md](dev/explore_pipeline/DOCS.md)
│   └── cleanup/                    → [DOCS.md](dev/cleanup/DOCS.md)
```
