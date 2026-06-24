# Scraper Module

URL scraping tools powered by Crawl4AI for SearXNG MCP server.

## scrape_logger.py (88 LOC)

**Purpose:** Per-URL structured logging for `scrape_url`. Two outputs per call: (1) one JSONL record appended to `src/logs/scrape_log.jsonl`, (2) one sidecar `.md` file under `scrape_content/` subdir containing the exact content the caller received. No sidecar on empty outcome; sidecar IS written on garbage outcome (content that triggered classification is preserved for inspection).
**Public interface:** `log_scrape(record: dict)`, `write_sidecar(url, ts, content, outcome, mode) -> str | None`.
**Reads:** `SEARXNG_SCRAPE_LOG_PATH` env var (fallback `src/logs/scrape_log.jsonl`). Sidecar dir = `<log_dir>/scrape_content/`.
**Writes:** `src/logs/scrape_log.jsonl` (one line per call), `<log_dir>/scrape_content/<ts>_<slug>.md` (per-call content sidecar). Both gitignored.
**Called by:** `scrape_url.py` (end of `scrape_url_workflow`).
**Calls out:** `src/log_janitor.py` (`maybe_prune_jsonl`, `maybe_prune_sidecars`).

## scrape_url.py (235 LOC)

**Purpose:** URL scraping orchestrator. Single crawl4ai-Browser-Call with native anti-bot baseline (`enable_stealth=True` + `UndetectedAdapter` + `magic=True` + `wait_until="load"`). Extracts clean page content as markdown via PruningContentFilter.
**Input:** URL string and optional maximum content length (default 15000).
**Output:** Filtered markdown content wrapped in TextContent, or error message on failure. Side effect: writes one JSONL record to `scrape_log.jsonl` + one sidecar `.md` via `scrape_logger`.

### scrape_url_workflow()

Main orchestrator. Single-call approach: invokes `try_scrape(url)`, then logs result and returns content or error message. Noise removal via `excluded_selector=COOKIE_CONSENT_SELECTOR` (inside `try_scrape` via `CrawlerRunConfig`). `remove_overlay_elements` is NOT used (destroys Wikipedia content by misclassifying DOM elements as overlays).

On empty/garbage result, returns error message with `garbage_type` from `_GARBAGE_MESSAGES`. No retry across phases.

### try_scrape(url)

Signature: `try_scrape(url: str) -> tuple[str, dict]`. Builds all config internally. Config:
- `BrowserConfig(headless=True, verbose=False, enable_stealth=True)` + `UndetectedAdapter()` via `AsyncPlaywrightCrawlerStrategy`
- `CrawlerRunConfig(magic=True, wait_until="load", page_timeout=60000, max_retries=0, cache_mode=CacheMode.BYPASS, markdown_generator=DefaultMarkdownGenerator(PruningContentFilter(0.48)), excluded_selector=COOKIE_CONSENT_SELECTOR)`

Returns `(content, meta)` where `meta` is a dict with keys: `garbage_type`, `status_code`, `content_type`, `fallback_to_raw`, `consent_stripped`, `garbage_content` (content that triggered garbage detection — written to sidecar on garbage outcome), `raw_markdown_bytes` (raw_markdown length before filter/fallback — used for `bytes_raw_markdown` log field). Checks `result.status_code` first — if >= 400, returns `("", meta_with_garbage_type="http_error")`. Content selection: `fit_markdown` if >= 200 chars (MIN_CONTENT_THRESHOLD), otherwise falls back to `raw_markdown` (`fallback_to_raw=True`). Checks content via `is_garbage_content()` — if `cookie_wall` is detected, attempts `strip_consent_prefix()` first: if stripping yields different content that passes garbage detection, returns stripped content with `consent_stripped=True`. All other garbage types (and cookie_wall when stripping fails) return empty string with `garbage_content` populated for sidecar logging. `is_garbage_content()` on this path is classification-only — no retry phases.

### is_garbage_content()

Returns `str | None` — garbage type identifier or None if content is valid. Detects seven categories:
1. **`minimal_content`:** Empty content OR `len(content.strip()) < 50`. Checked FIRST before all others. Catches whitespace-only pages (gdpr.eu 1 char, PDF whitespace 87 bytes treated as HTML by Crawl4AI).
2. **`crawl4ai_error`:** "Crawl4AI Error:", "Document is empty", "page is not fully supported"
3. **`http_error`:** Short content (<1000 chars) with 404/403/NOT_FOUND/Access Denied keywords
4. **`nav_dump`:** ≥20 non-empty lines AND >60% are standalone markdown link lines (`[text](url)` on their own line). Catches large pages that are pure navigation with no content (e.g. 162KB AWS announcement pages).
5. **`cookie_wall`:** High density of cookie-related terms (>15 occurrences of "cookie"/"consent"/"duration" in first 5000 chars + "consent preferences" or "cookieyes" or "cookie preferences" present). Note: Amazon uses "cookie preferences" instead of "consent preferences".
6. **`login_wall`:** Short content (<2000 chars) with login/paywall patterns ("sign in", "log in", "login", "subscribe to continue", "create account", "premium content", "paywall", "members only", "subscriber only").
7. **`cloudflare`:** Short content (<500 chars) containing "checking your browser" or "enable javascript and cookies", OR "just a moment" + "cloudflare" anywhere.

`_GARBAGE_MESSAGES` dict maps each type to a human-readable error message for the caller. `try_scrape()` logs garbage type on every detection.

Called by `try_scrape()` after content extraction, and by `src.crawler.crawl_site.save_markdown` for batch crawl garbage filtering.

### strip_consent_prefix()

Attempts to recover content from a cookie-wall page by stripping the leading consent block. Counts keyword density (CONSENT_WORDS: cookie, consent, einwilligung, tracking, akzeptieren, datenschutz, zweck) in the first 3000 chars. If density > CONSENT_DENSITY_THRESHOLD (5), searches for the first `#` or `##` heading after CONSENT_SKIP_OFFSET (300 chars) and returns content from that heading onward. Returns original content unchanged if density is low (baseline pages) or no heading is found after the offset.

### truncate_content()

Truncates content if exceeding maximum length. Attempts to break at paragraph boundary for clean truncation. Appends truncation notice when content is cut.

### get_plugin_hint()

Stub — always returns `""`. Domain blocking removed; no plugin-routing hint is applicable.

### Constants

- `COOKIE_CONSENT_SELECTOR` — CSS selector string matching common cookie consent frameworks: CookieYes (cky-consent, cky-banner, cky-modal), OneTrust, Cookiebot, cc-banner, GDPR, cookie-banner, cookie-consent, cookie-notice, cookie-law. Note: `cky-modal` is critical — CookieYes stores the full Consent Preferences dialog (12K+ chars of cookie descriptions) in this container. Without it, only the small banner (236 chars) is removed.
- `DEFAULT_MAX_CONTENT_LENGTH` — 15000 chars
- `MIN_CONTENT_THRESHOLD` — 200 chars. fit_markdown below this triggers raw_markdown fallback.
- `CONSENT_WORDS` — keyword list for consent density scoring: cookie, consent, einwilligung, tracking, akzeptieren, datenschutz, zweck
- `CONSENT_DENSITY_THRESHOLD` — 5. Sum of CONSENT_WORDS occurrences in first 3000 chars must exceed this to trigger stripping.
- `CONSENT_SKIP_OFFSET` — 300 chars. Heading search starts at this offset to skip banner fragments before the actual content starts.

## Architecture

Content extraction is delegated entirely to Crawl4AI (v0.8.6):
- **Browser strategy:** Single call — `enable_stealth=True` + `UndetectedAdapter` (Patchright) + `magic=True` + `wait_until="load"` + `page_timeout=60000`. No phase escalation. See `decisions/scrape_pipeline.md`.
- **Cookie removal:** CSS selector exclusion via `excluded_selector=COOKIE_CONSENT_SELECTOR`. Specific selectors per framework (CookieYes, OneTrust, Cookiebot, GDPR etc.). `remove_overlay_elements` is NOT used — it removes legitimate content on some sites.
- **Content filtering:** PruningContentFilter(0.48) + fit_markdown for relevance assessment. raw_markdown fallback when filtered content < 200 chars (table-heavy pages).
- **Markdown generation:** Two modes:
  - **scrape_url (CLI tool):** PruningContentFilter + fit_markdown — noise-filtered, for in-conversation reading
  - **crawl_site (pipe script):** DefaultMarkdownGenerator + raw_markdown — full fidelity, batch crawl, noise handled by downstream RAG cleanup agent
- **Known issue:** Crawl4AI captures stdout — always write debug output to files, not print()
- **Cookie-Wall debugging:** Inject JS to enumerate `[class*='cky']` elements and check textLen per element. The largest container is usually the unmissed consent dialog. Add its class to COOKIE_CONSENT_SELECTOR.
