# Scraper Module

URL scraping and site exploration tools powered by Crawl4AI for SearXNG MCP server.

## scrape_logger.py

**Purpose:** Per-URL structured logging for scrape_url and scrape_url_raw. Two outputs per scrape call: (1) one JSONL record appended to `src/logs/scrape_log.jsonl`, (2) one sidecar `.md` file under the `scrape_content/` subdir of the log dir (gitignored) containing the exact content the caller received. No sidecar on error/timeout/empty outcomes; sidecar IS written on garbage outcome (content that triggered classification is preserved for inspection).
**Public interface:** `log_scrape(record: dict)`, `write_sidecar(url, ts, content, outcome, mode) -> str | None`.
**Reads:** `SEARXNG_SCRAPE_LOG_PATH` env var (fallback `src/logs/scrape_log.jsonl`). Sidecar dir = `<log_dir>/scrape_content/`.
**Writes:** `src/logs/scrape_log.jsonl` (one line per call), `<log_dir>/scrape_content/<ts>_<slug>.md` (per-call content sidecar). Both gitignored.
**Called by:** `scrape_url.py` (end of `scrape_url_workflow`), `scrape_url_raw.py` (end of `scrape_url_raw_workflow`).
**Calls out:** `src/log_janitor.py` (`maybe_prune_jsonl`, `maybe_prune_sidecars`).

## scrape_url.py

**Purpose:** URL scraping orchestrator. Uses Crawl4AI's AsyncWebCrawler with PruningContentFilter to extract clean page content as markdown. Two-phase browser strategy: normal browser first, stealth fallback for anti-bot sites.
**Input:** URL string and optional maximum content length (default 15000).
**Output:** Filtered markdown content wrapped in TextContent, or error message on failure. Side effect: writes one JSONL record to `scrape_log.jsonl` + one sidecar `.md` via `scrape_logger`.

### scrape_url_workflow()

Main orchestrator. Three-phase approach:

1. **Phase 0: HTTP markdown fast-path** — `fetch_markdown_fastpath()` probes the URL with `Accept: text/markdown, text/html` via httpx. If the host serves text/markdown directly (Cloudflare-fronted zones with Markdown-for-Agents enabled, Vercel's own edge implementation, others), the markdown body is returned and Crawl4AI is skipped entirely. See `decisions/scrape_pipeline.md`.
2. **Phase 1: Normal browser** — Standard Crawl4AI without stealth patches. Works for most sites (Wikipedia, docs, blogs). Tries `networkidle` first, falls back to `domcontentloaded`.
3. **Phase 2: Stealth browser** — Only if Phase 1 returns empty. Uses `enable_stealth=True` + `UndetectedAdapter` + `AsyncPlaywrightCrawlerStrategy` (Level 3 anti-bot evasion). For sites with bot detection (e.g. TDS, some news sites).

Noise removal via `excluded_selector=COOKIE_CONSENT_SELECTOR` — CSS selectors matching common cookie consent frameworks. `remove_overlay_elements` is NOT used (destroys Wikipedia content by misclassifying DOM elements as overlays).

On empty result, returns error message.

### fetch_markdown_fastpath()

HTTP probe for server-side markdown availability (Phase 0). Sends `Accept: text/markdown, text/html` via `httpx.AsyncClient` with `follow_redirects=True` and `MD_FASTPATH_TIMEOUT` (5.0s). Returns `(content, status_code, content_type, miss_reason)` 4-tuple. On hit: `(body, 200, ct, None)`. On miss: `(None, status_code_or_None, ct_or_None, reason)` where reason ∈ `{"http_error", "wrong_content_type", "sub_threshold", "network_error"}`. Hit conditions: HTTP 200 + `text/markdown` content-type + body ≥ `MD_FASTPATH_MIN_BYTES` (200 bytes). Logs at info-level on hit; debug-level on miss/error. Imported by `scrape_url_raw.py` for reuse.

The 200-byte threshold guards against redirect-stub responses (anomaly observed at docs.anthropic.com returning 12 bytes during the 2026-05-07 adoption probe). The 5s timeout is generous enough for cold-edge CDN routing while still being tighter than the typical Crawl4AI browser-launch path, so the probe never delays the fallback meaningfully.

### try_scrape()

Attempts a single scrape with given browser config, optional crawler strategy, and wait strategy. Returns `(content, meta)` where `meta` is a dict with keys: `garbage_type`, `status_code`, `content_type`, `fallback_to_raw`, `consent_stripped`, `garbage_content` (content that triggered garbage detection — written to sidecar on garbage outcome), `raw_markdown_bytes` (raw_markdown length before filter/fallback — used for `bytes_raw_markdown` log field). Checks `result.status_code` first — if >= 400, returns `("", meta_with_garbage_type="http_error")`. Content selection: `fit_markdown` if >= 200 chars (MIN_CONTENT_THRESHOLD), otherwise falls back to `raw_markdown` (`fallback_to_raw=True`). Checks content via `is_garbage_content()` — if `cookie_wall` is detected, attempts `strip_consent_prefix()` first: if stripping yields different content that passes garbage detection, returns stripped content with `consent_stripped=True`. All other garbage types (and cookie_wall when stripping fails) return empty string with `garbage_content` populated for sidecar logging.

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

Called by both `try_scrape()` and `try_scrape_raw()` after content extraction.

### strip_consent_prefix()

Attempts to recover content from a cookie-wall page by stripping the leading consent block. Counts keyword density (CONSENT_WORDS: cookie, consent, einwilligung, tracking, akzeptieren, datenschutz, zweck) in the first 3000 chars. If density > CONSENT_DENSITY_THRESHOLD (5), searches for the first `#` or `##` heading after CONSENT_SKIP_OFFSET (300 chars) and returns content from that heading onward. Returns original content unchanged if density is low (baseline pages) or no heading is found after the offset.

### truncate_content()

Truncates content if exceeding maximum length. Attempts to break at paragraph boundary for clean truncation. Appends truncation notice when content is cut.

### log_scrape_failure()

Appends one JSONL failure record to `dev/scrape_pipeline/failures.jsonl`. Called at the final failure exit in `scrape_url_workflow()` when all 3 attempts are exhausted. Fields: `ts` (ISO 8601 UTC), `url`, `garbage_type`, `status_code`. Requires `SEARXNG_PROJECT_ROOT` env variable — silently skips if not set. Silent fail on any I/O error.

### get_plugin_hint()

Stub — always returns `""`. Domain blocking removed; no plugin-routing hint is applicable.

### Constants

- `COOKIE_CONSENT_SELECTOR` — CSS selector string matching common cookie consent frameworks: CookieYes (cky-consent, cky-banner, cky-modal), OneTrust, Cookiebot, cc-banner, GDPR, cookie-banner, cookie-consent, cookie-notice, cookie-law. Note: `cky-modal` is critical — CookieYes stores the full Consent Preferences dialog (12K+ chars of cookie descriptions) in this container. Without it, only the small banner (236 chars) is removed.
- `DEFAULT_MAX_CONTENT_LENGTH` — 15000 chars
- `MIN_CONTENT_THRESHOLD` — 200 chars. fit_markdown below this triggers raw_markdown fallback.
- `MD_FASTPATH_MIN_BYTES` — 200 bytes. Phase 0 markdown response below this is treated as stub/redirect noise and rejected (fall through to Crawl4AI).
- `MD_FASTPATH_TIMEOUT` — 5.0s. Phase 0 httpx timeout — generous for cold-edge routing, tight against fallback delay.
- `CONSENT_WORDS` — keyword list for consent density scoring: cookie, consent, einwilligung, tracking, akzeptieren, datenschutz, zweck
- `CONSENT_DENSITY_THRESHOLD` — 5. Sum of CONSENT_WORDS occurrences in first 3000 chars must exceed this to trigger stripping.
- `CONSENT_SKIP_OFFSET` — 300 chars. Heading search starts at this offset to skip banner fragments before the actual content starts.

## scrape_url_raw.py

**Purpose:** Raw markdown scraping orchestrator for RAG indexing. Same two-phase browser strategy as `scrape_url.py` (normal → stealth fallback) but uses `DefaultMarkdownGenerator()` without PruningContentFilter and saves `raw_markdown` output to a .md file with `<!-- source: URL -->` header. Generates safe filename from URL (domain + path, max 120 chars).
**Input:** URL string and output directory path.
**Output:** TextContent with file path and char count on success, or error message on failure (Cloudflare-specific message when CF-protected). Side effect: writes one JSONL record to `scrape_log.jsonl` + one sidecar `.md` via `scrape_logger`. Sidecar content = same raw markdown saved to `output_dir`. Raw-mode fields `fallback_to_raw`, `truncated`, `consent_stripped` are null (not applicable).

## pdf_chain.py

**Purpose:** PDF URL chain resolution. Utility module used by `download_pdf.py`, `cli.py`, and `dev/search_pipeline/16_search_to_pdf_probe.py`. No I/O except `extract_citation_pdf_url` (sync HTTP hop via requests).
**Input/Output:** Pure functions (sync); no MCP types.

### Constants

- `HARD_BLACKLIST` — `frozenset[str]` of 11 domains that never yield PDFs (validated in probe 14). Includes `semanticscholar.org` / `openalex.org` (Tier-2 pending engine fix) and `scribd.com` / `nature.com` with caveats documented in module.
- `TIER1_DOMAINS` — `frozenset[str]`: `arxiv.org`, `aclanthology.org`, `openreview.net`. 100% transform success in probe 14.
- `CITATION_PDF_RE` — compiled regex matching both attribute orderings of `<meta name="citation_pdf_url" ...>`.

### Functions

- `apply_tier1_transform(url) → str | None` — arxiv `/abs|html/` → `/pdf/`; aclanthology strip-slash+`.pdf`; openreview `/forum` → `/pdf`. Returns transformed URL or None if no transform applies.
- `is_blacklisted(url) → bool` — True if bare domain is in HARD_BLACKLIST. Strips `www.`.
- `is_github_blob(url) → bool` — True if `github.com/<owner>/<repo>/blob/` path pattern. GitHub blob viewer returns HTML, not PDF bytes.
- `should_download_as_pdf(url) → bool` — routing predicate for `cli.py`. True for TIER1 domains or direct `.pdf` suffix URLs (excluding GitHub blob and BLACKLIST). MULTI_STEP candidates → False (scrape_url handles them from CLI; download_pdf_workflow handles them when explicitly invoked).
- `parse_citation_pdf_url(body) → str | None` — regex search on HTML body string, returns citation_pdf_url value or None.
- `extract_citation_pdf_url(url) → str | None` — Hop 1: sync `requests.get` with 32KB read cap + 10s timeout, calls `parse_citation_pdf_url`. Returns URL or None on any failure.

## download_logger.py

**Purpose:** Per-URL structured logging for `download_pdf_workflow`. Emits one JSONL record to `src/logs/download_log.jsonl` per call — chain resolution stages attempted, per-stage timings, outcome, http_status, bytes_downloaded. No sidecar files (the PDF is already on disk at `output_path`).
**Public interface:** `log_download(record: dict)`.
**Reads:** `SEARXNG_DOWNLOAD_LOG_PATH` env var (fallback `src/logs/download_log.jsonl`).
**Writes:** `src/logs/download_log.jsonl` (one line per call, gitignored).
**Called by:** `download_pdf.py` (`download_pdf_workflow` — once per call at every return path).
**Calls out:** `src/log_janitor.py` (`maybe_prune_jsonl`).

## download_pdf.py

**Purpose:** PDF file download. Uses `requests.get()` with streaming. Chain-resolves the URL via `pdf_chain.py` before downloading: BLACKLIST check → GitHub blob check → TIER1 transform → DIRECT `.pdf` path → MULTI_STEP `citation_pdf_url` two-hop. Also called automatically by `cli.py` when `scrape_url` or `scrape_url_raw` detects a TIER1 domain or direct `.pdf` URL (`should_download_as_pdf()`).
**Input:** URL string and optional output directory (default `~/Downloads/`).
**Output:** TextContent with file path and human-readable file size on success, or error message on failure (blocked domain, GitHub blob, no PDF path, HTTP error). Side effect: writes one JSONL record to `download_log.jsonl` via `download_logger` at every return path.

## Architecture

Content extraction is delegated entirely to Crawl4AI (v0.8.0):
- **Browser strategy:** Normal browser first, Stealth (Level 3) as fallback. UndetectedAdapter breaks some sites (Wikipedia) by patching the browser too aggressively.
- **Cookie removal:** CSS selector exclusion via `excluded_selector`. Specific selectors per framework (CookieYes, OneTrust, Cookiebot, GDPR etc.). `remove_overlay_elements` is NOT used — it removes legitimate content on some sites.
- **Content filtering:** PruningContentFilter(0.48) + fit_markdown for relevance assessment. raw_markdown fallback when filtered content < 200 chars (table-heavy pages).
- **Markdown generation:** Three modes:
  - **scrape_url (MCP tool):** PruningContentFilter + fit_markdown — noise-filtered, for in-conversation reading
  - **scrape_url_raw (MCP tool):** DefaultMarkdownGenerator + raw_markdown — full fidelity, saves to file for RAG indexing
  - **crawl_site (export script):** DefaultMarkdownGenerator + raw_markdown — full fidelity, batch crawl, noise handled by downstream RAG cleanup agent
- **Known issue:** Crawl4AI captures stdout — always write debug output to files, not print()
- **Cookie-Wall debugging:** Inject JS to enumerate `[class*='cky']` elements and check textLen per element. The largest container is usually the unmissed consent dialog. Add its class to COOKIE_CONSENT_SELECTOR.
