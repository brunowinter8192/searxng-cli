# Explore Pipeline Step 1: Site Discovery

## Status Quo (IST)

**Code:** `src/crawler/explore_site.py` (URL discovery, CLI entry point); `src/crawler/crawl_site.py` (BFS engine + content crawl functions called by explore_site); `src/crawler/filter_urls.py` (shared `match_any()` helper + `filter_urls_workflow` CLI tool)

**Method:** Single discovery method — `discover_urls_playwright()` in `crawl_site.py`. Manual BFS: `crawler.arun()` per frontier URL in a real Playwright browser; links extracted from `result.links.internal` (post-JS rendered DOM). No sitemap cascade, no prefetch BFS, no `BFSDeepCrawlStrategy`.

**Config:**
```python
DEFAULT_DELAY_S = 3.0            # delay_before_return_html
DEFAULT_PAGE_TIMEOUT_MS = 15000  # page_timeout per page
DEFAULT_DISCOVER_CONCURRENCY = 1 # sequential, WAF-safe default
wait_until = "domcontentloaded"  # fixed, not configurable
```

**Discovery flow (`discover_urls_playwright`):**
1. Normalize seed URL → init frontier deque + visited set.
2. Open one `AsyncWebCrawler` context for the full BFS.
3. Per batch (size = concurrency): `crawler.arun(url, config=run_cfg)` → extract `result.links.internal` → filter by domain + include/exclude substrings → enqueue new URLs.
4. **429 policy:** if a batch returns 429 → back off 5s (once); if second consecutive batch also 429 → stop, set `stop_reason="429_persistent"`. No retry loops.
5. **Stop reason** (D7 saturation signal) on exit:
   - `"frontier_exhausted"` — ran out of reachable links before hitting max_pages
   - `"max_pages_reached"` — capped; more pages likely exist → raise `--max-pages` + `--append`
   - `"429_persistent"` — WAF stopped the run; retry with `--stealth` or after cooldown

**`explore_site_workflow`** wraps `discover_urls_playwright` with: `resolve_redirect()` (HEAD-based redirect resolution, kept), `--append` dedup, `print_url_samples`, `save_url_list`. Returns `(urls, stop_reason, four_two_nine_count, output_path)`. `cli.py` embeds both `stop_reason` and `four_two_nine_count` (when >0) in the visible `TextContent` summary printed to stdout — e.g. `Discovered 248 URLs → /tmp/... (stop_reason=frontier_exhausted)` or `(stop_reason=429_persistent, 3×429)`. Not logger-only.

**Stealth toggle:** `--stealth` enables `BrowserConfig(enable_stealth=True)` + `UndetectedAdapter` + `AsyncPlaywrightCrawlerStrategy` — mirrors Phase-2 in `src/scraper/scrape_url.py`. Off by default.

**Post-hoc filter (`filter_urls_workflow` in `filter_urls.py`):** unchanged. `match_any(url, patterns_str)` (fnmatch) remains the shared glob-match helper for `filter_urls` CLI use.

## Evidenz

### Playwright-per-page BFS vs HTTP BFS — Phase B recall probe

Script: `dev/explore_pipeline/05_playwright_bfs.py`
Report: `dev/explore_pipeline/05_reports/docs_github_rest_20260529.md`
Dataset: `dev/explore_pipeline/goldstandard/docs_github_rest.txt` (305 URLs, docs.github.com/de/rest)

| Strategy | Recall % | Matched | Time | ms/page | 429 |
|----------|----------|---------|------|---------|-----|
| HTTP BFS — crawl4ai BFSDeepCrawlStrategy (Phase A baseline) | 67.2% | 205/305 | 59.2s | 180ms | 0 |
| Playwright-per-page BFS — concurrency=1 (Phase B) | 81.3% | 248/305 | 1094.5s | 4112ms | 0 |

**+14.1pp recall** over HTTP BFS. Sequential concurrency (1) survived Cloudflare WAF without any 429.

### Mechanism verified

Single-page check: `https://docs.github.com/de/rest/agent-tasks` rendered with `wait_until=domcontentloaded` + `delay=3.0s` → `result.links.internal` contains `/de/rest/agent-tasks/agent-tasks` (46 internal links, React sidebar fully rendered). The rendering mechanism is correct.

### Navigation topology ceiling (81.3%)

Post-run diagnostic on seed page `/de/rest`: only 35 `/de/rest/*` links in rendered DOM. `agent-tasks`, `enterprise-admin`, `announcement-banners` not present. Sidebar is section-scoped: categories only appear in navigation when the user is within that section. The 18.7% gap is a navigation topology constraint, not a rendering failure. Knowingly accepted; tracked as open point (see SOLL).

### HTTP BFS is always HTTP-speed regardless of wait_until

Phase A proof: `BFSDeepCrawlStrategy` with `wait_until="networkidle"` or `prefetch=False` still ran at 0.18s/page (HTTP speed). Changing wait_until in the old code has zero effect on link extraction. Prefetch BFS: parallel HTTP requests → Cloudflare 429 after ~100 reqs/session.

### Redirect resolution (kept)

HEAD-request before BFS. Fixes domain-mismatch for redirect chains (e.g. `docs.anthropic.com` → `platform.claude.com`). Still required since `discover_urls_playwright`'s domain filter uses the resolved domain.

## Recommendation (SOLL)

Keep — shipped. Current config is the validated production state.

**Two tracked open points (do NOT fix here):**
1. **Coverage gap (18.7%):** section-scoped navigation topology on docs.github.com means some categories are unreachable from a single seed. Mitigation options: additive sitemap union (if sitemap exists), multi-seed BFS, or repo-tree API. Evaluated when needed per site.
2. **Runtime:** ~4s/page × N pages (sequential). Concurrency knob available (`--concurrency`, max 10) for speed-vs-WAF tuning. Concurrent WAF behavior (D5 from OldThemes) not yet measured — treat concurrency >1 as experimental.

## Offene Fragen

- Concurrency >1 WAF behavior: does `--concurrency 3` or `--concurrency 10` on docs.github.com trigger 429? Stealth needed?
- Does docs.github.com have a usable sitemap for the missing 18.7%? (`/sitemap.xml` returns 404 on `de/rest` sub-path — not tested globally.)

## Quellen

- `dev/explore_pipeline/05_playwright_bfs.py` — Phase B probe implementation
- `dev/explore_pipeline/05_reports/docs_github_rest_20260529.md` — Phase B run report
- `dev/explore_pipeline/04_render_recall.py` — Phase A HTTP BFS baseline
- `decisions/OldThemes/crawler_js_render_discovery/` — full investigation arc (A_recall_probe.md, B_playwright_bfs_probe.md, 00_design_decisions_and_levers.md)
- Crawl4AI issue #1665 — BFSDeepCrawlStrategy captures page before JavaScript loads
