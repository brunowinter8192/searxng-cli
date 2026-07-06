# Scrape Pipeline — Content Extraction

*Snapshot as of 2026-06 — historical process record; the live current state is the source code, not this file.*

## Browser Strategy

### Current State

**Code:** `src/scraper/scrape_url.py` — `scrape_url_workflow`, `try_scrape`

**Method:** Single crawl4ai browser call with native anti-bot baseline

**Config (`try_scrape`):**
- `BrowserConfig(headless=True, verbose=False, enable_stealth=True)`
- `UndetectedAdapter()` wired via `AsyncPlaywrightCrawlerStrategy(browser_config=..., browser_adapter=...)`
- `CrawlerRunConfig(magic=True, wait_until="load", page_timeout=60000, max_retries=0, cache_mode=CacheMode.BYPASS, markdown_generator=DefaultMarkdownGenerator(content_filter=PruningContentFilter(threshold=0.48)), excluded_selector=COOKIE_CONSENT_SELECTOR)`

**Parameter derivation:**
- `enable_stealth=True` + `magic=True` — no-blocking: `enable_stealth` keeps WebGL active (no `--disable-gpu`), `magic` handles overlays/popups automatically
- `wait_until="load"` — completeness: full page load, less hang-prone than `networkidle` (no 500ms idle wait), earlier than `networkidle` on tracker-heavy sites
- `page_timeout=60000` — determinism: hard navigation limit, worst case ~64s/URL
- `UndetectedAdapter` — Patchright as primary anti-bot evasion (replaces the weaker playwright-stealth path)
- `max_retries=0` — no internal retry (no-op, matches default), determinism
- `cache_mode=CacheMode.BYPASS` — no cache, every request hits the network

### Evidence

Process narrative, iteration history and alternatives evaluation covered networkidle timeout costs, hamster-wheel risk, and enable_stealth/#1959 analysis (2026-05/06).

Crawl4AI 0.8.6 API verification:
- All `CrawlerRunConfig` parameters (`magic`, `wait_until`, `page_timeout`, `max_retries`) present in `async_configs.py:1399–1519`
- `page_timeout` confirmed as navigation timeout: `async_crawler_strategy.py:762–763` — `page.goto(url, wait_until=config.wait_until, timeout=config.page_timeout)`
- `UndetectedAdapter` + `AsyncPlaywrightCrawlerStrategy(browser_adapter=...)` API: `async_crawler_strategy.py:76`

### Open Questions

- Session reuse: could a persistent browser across multiple scrapes reduce overhead — risk: state pollution between independent requests
- `wait_until="load"` vs. a short `js_code` wait for sites that load content after `load` (true JS SPAs)

---

## Content Filtering

### Current State

**Code:** `src/scraper/scrape_url.py` — `scrape_url_workflow`, `truncate_content`

**Method:** PruningContentFilter with fit_markdown fallback to raw_markdown

**Config:**
- `scrape_url_workflow`: `PruningContentFilter(threshold=0.48)` + `fit_markdown`
  - Fallback to `raw_markdown` when `fit_markdown < MIN_CONTENT_THRESHOLD` (200 chars)
  - `DEFAULT_MAX_CONTENT_LENGTH = 15000` chars (fixed, no CLI param)
  - Truncation at paragraph boundary (`\n\n`) when `last_newline > max_length * 0.8`
- `COOKIE_CONSENT_SELECTOR`: CSS selector list for DOM elements removed before the crawl
  - CookieYes: `cky-consent`, `cky-banner`, `cky-modal`
  - OneTrust: `onetrust-*`
  - Cookiebot: `CookiebotDialog`, `CookiebotWidget`
  - Generic: `cc-banner`, `cc-window`, `gdpr`, `cookie-banner/consent/notice/law`

`PruningContentFilter` removes low-information blocks (navigation, footer, ads) via a scoring algorithm. `fit_markdown` is the filtered result, `raw_markdown` the unfiltered HTML-to-markdown output.

### Evidence

#### Session findings (2026-03)
- `cky-modal` was initially missing from `COOKIE_CONSENT_SELECTOR` — led to ~12K chars of CookieYes consent wall as content
- TDS (Towards Data Science) cookie wall was not fully eliminated by the selector — `is_garbage_content()` caught it as second line of defense
- `fit_markdown` fallback to `raw_markdown` saves short pages (e.g. simple API docs, one-pagers)

#### Crawl4AI docs
- `PruningContentFilter(threshold=0.48)`: blocks below the score are removed. Higher threshold = more aggressive filtering
- Known limitation: PruningFilter can destroy code blocks when classified as "low-density" (little natural language)
- `DefaultMarkdownGenerator()` without filter: full HTML→Markdown, no scoring — more useful for dev suites than for live research
- `content_source` option in `CrawlerRunConfig`: alternative source (e.g. `fit_html`, `cleaned_html`) instead of the markdown pipeline

#### Truncation logic
- 15000 chars ≈ ~3750 words — sufficient for most articles, avoids context-window overflow
- Paragraph-boundary truncation (`\n\n` when > 80% of the limit) prevents mid-sentence cuts

#### Empirical Sweep (2026-05)

`dev/scrape_pipeline/04_overview_sweep/` — 36 configs × 20 URLs (Q24 search-result set across 5 page shapes: Blog / Paper-Landing / Forum-Thread / Repo-Heavy-Chrome / Index-Aggregator). Diff against clean-raw baseline (raw scrape + dev-only cleanup script).

Asymmetric preference frame: chrome retention is much worse than content loss. Quality > quantity. Filter must strip noise even at cost of some content detail, as long as title + general message preserved.

Per-config median F1 across 17 analyzed URLs (PDF stubs + scrape-failures excluded):

| Filter / source | F1 | Note |
|---|---|---|
| `none + cleaned_html` | 0.98 | quasi identical to clean-raw, no size reduction |
| `prune_030 + cleaned_html` | 0.89 | lenient, residual chrome (Skip-link visible on some sites) |
| **`prune_048 + cleaned_html`** (current prod) | **0.75** | **empirically optimal for asymmetric preference** |
| `prune_060 + cleaned_html` | 0.60 | aggressive, drops title text on short-title pages (e.g. webscraping.fyi shows `# ` empty header) |
| `prune_075 + cleaned_html` | 0.47 | title text gone, only body prose remains |
| `bm25 + *` | 0.05 | unusable for general overview — query-snippet extractor only |
| `* + fit_html` | 0.44 (constant) | anomaly: `fit_html` source is always-pre-filtered regardless of additional filter, not a useful tuning knob |

Per-shape break: `none + cleaned_html` wins on Blog/Forum/Index, `prune_030+` wins on Paper-Landing + Repo-Heavy-Chrome. Single-config trade-off: prune_048 most consistent across shapes for the noise-removal preference.

Cookies vs cookies+sphinx selectors: no measurable difference on this URL set (≤ 0.01 F1 delta).

**Closes 3 of 5 open questions:**
- threshold validation: prune_048 confirmed empirically optimal (asymmetric metric: precision over recall)
- content_source="fit_html": NOT useful (always-pre-filtered anomaly)
- 0.48 vs alternatives: 0.30 retains chrome, 0.60+ damages titles → 0.48 is sweetspot

### Open Questions

- Code pages (GitHub, Docs): PruningFilter destructive for code blocks — raw mode (DefaultMarkdownGenerator via crawl_site) as indexing path; no raw-mode equivalent for ad-hoc CLI scraping (scrape_url_raw removed)
- Cookie consent via `excluded_selector` removes the DOM node, but sometimes an overlay backdrop remains — JS-based dismissal would be more robust
- `MIN_CONTENT_THRESHOLD` (200 chars) possibly too low — 200 chars can also be valid error text
- Per-shape filter dispatch? — sweep showed Blog/Forum/Index benefit from less filtering (none/prune_030), Paper-Landing/Repo benefit from prune_048+. Single-config = trade-off. Per-shape dispatch would be more consistent but needs its own shape-detection logic before the filter (complexity vs Crawl4AI's built-in filter alone)

---

## Garbage Detection

### Current State

**Code:** `src/scraper/scrape_url.py` — `is_garbage_content`, `_GARBAGE_MESSAGES`, `get_plugin_hint`

**Method:** Rule-based garbage detection in 6 typed categories + differentiated error messages + logging

**Return type:** `is_garbage_content()` returns `str | None` (None = not garbage, str = garbage type identifier)

**Config:**
- `crawl4ai_error` — Crawl4AI error messages as content:
  - Trigger: `"crawl4ai error:"`, `"document is empty"`, `"page is not fully supported"`
  - Condition: pattern in `content.lower()`
- `http_error` — HTTP error pages (two checks):
  - **Primary (status_code):** `result.status_code >= 400` in `try_scrape()` — directly after `crawler.arun()`, BEFORE content analysis. Catches padded 404 pages regardless of content length.
  - **Secondary (content heuristic):** `len(content) < 1000` AND one of `"not_found"`, `"404"`, `"403"`, `"forbidden"`, `"access denied"`, `"page not found"` — fallback when status_code is unavailable
- `nav_dump` — navigation dumps:
  - Trigger: `len(lines) >= 20` AND `link_lines / len(lines) > 0.6`
  - Condition: more than 60% of lines are pure markdown links
- `cookie_wall` — cookie consent walls:
  - Trigger: `count("cookie") + count("consent") + count("duration") > 15` in first 5000 chars
  - AND `"consent preferences"` or `"cookieyes"` or `"cookie preferences"` in the sample
- `login_wall` — login/paywall pages:
  - Trigger: `len(content) < 2000` AND one of `"sign in"`, `"log in"`, `"login"`, `"subscribe to continue"`, `"create account"`, `"create an account"`, `"premium content"`, `"paywall"`, `"members only"`, `"subscriber only"`
- `cloudflare` — Cloudflare protection:
  - Trigger: `len(content) < 500` AND `"checking your browser"` or `"enable javascript and cookies"`
  - OR: `"just a moment"` AND `"cloudflare"` (no length limit)

**Error Messages:** `_GARBAGE_MESSAGES` dict maps each category to a human-readable error message. `scrape_url_workflow()` returns a differentiated message based on the `garbage_type` from `try_scrape` meta.

**Role:** `is_garbage_content()` serves solely for classification — for logging (`garbage_type` in the JSONL record) and error messaging to the caller. On detected garbage without recovery (cookie_wall stripping failed or another type), the scrape fails and is logged as `garbage_type`. No retry across further phases — a single call.

**Logging:** `logger.warning("Garbage detected [%s]: %s", garbage_type, url)` on every garbage detection in `try_scrape()`.

**PDF URLs:** `scrape_url` returns `"PDF must be downloaded by the user: <url>"` when the URL path ends in `.pdf`. The user downloads PDFs themselves — no scrape attempt is made.

**`PLUGIN_HINTS`:** generic hint via `get_plugin_hint()` (stub — always returns `""`), appended to the error message when a scrape fails.

**Consent-Prefix Stripping (added 2026-04):** `strip_consent_prefix()` in `src/scraper/scrape_url.py` — recovery for `cookie_wall` pages. When `is_garbage_content()` returns `cookie_wall`, `try_scrape()` attempts to strip the leading consent block and recover actual page content instead of immediately discarding. Only triggers on `cookie_wall`; all other garbage types still discarded immediately.

Algorithm:
1. Count CONSENT_WORDS (`cookie`, `consent`, `einwilligung`, `tracking`, `akzeptieren`, `datenschutz`, `zweck`) in first 3000 chars
2. If density ≤ 5 (CONSENT_DENSITY_THRESHOLD): return original unchanged (baseline pages safe)
3. Search for first `#` or `##` heading after offset 300 (CONSENT_SKIP_OFFSET)
4. If heading found: return content from that heading onward
5. If no heading: return original unchanged

Recovery condition: stripped content must (a) differ from original and (b) pass `is_garbage_content()` returning None; otherwise falls through to normal garbage discard. Prototype source: `dev/scrape_pipeline/garbage_eval/09_garbage_fix_prototype.py`. `cookie_wall` threshold calibration (>15 cookie-signals) remains open — see Open Questions.

### Evidence

#### Session findings (2026-03)
- CookieYes wall (cky-modal missing from selector): `is_garbage_content()` correctly caught it as second line of defense and returned `""` — fallback to Phase 2 (stealth) helped
- TDS (Towards Data Science): cookie consent density check triggered
- LanceDB 404 page: category 2 (short + "404" in text) fired correctly
- `"duration"` as cookie signal: CookieYes walls typically contain cookie durations ("Duration: 1 year") — raises the signal score

#### Weakness of the current approach
- `http_error`: the 1000-char limit is arbitrary — a short, valid one-pager could be wrongly classified as garbage if it happens to contain "403" in text (e.g. an article about HTTP status codes)
- `cookie_wall`: threshold 15 not systematically calibrated — a legitimate cookie-policy article could be wrongly triggered
- `login_wall`: 2000-char limit + generic patterns ("log in", "sign in") could false-positive on short login-tutorial pages

#### PLUGIN_HINTS logic
- Hints are only shown when ALL phases return garbage/empty
- Two fixed domain mappings — not configurable without a code change

### Open Questions

- `http_error`: false-positive risk on short legitimate pages with numbers like "403" in body text
- `cookie_wall`: threshold calibration (15 cookie-signals) not validated against test data
- `login_wall`: false-positive risk on short login-tutorial pages — 2000-char limit + generic patterns
- `PLUGIN_HINTS` is hardcoded — a configurable map in `config.py` would be more flexible

---

## Sources

**Code:**
- `src/scraper/scrape_url.py` (code inspection — Browser Strategy, Content Filtering, Garbage Detection)
- `venv/lib/python3.14/site-packages/crawl4ai/async_configs.py:1399–1519` (CrawlerRunConfig 0.8.6 constructor signature)
- `venv/lib/python3.14/site-packages/crawl4ai/async_crawler_strategy.py:76,117,762–763` (UndetectedAdapter wiring, page_timeout effect)
- `venv/lib/python3.14/site-packages/crawl4ai/browser_manager.py:95,763` (enable_stealth GPU flags + StealthAdapter condition)

**Session findings:**
- CookieYes cky-modal fix, TDS cookie wall, LanceDB 404, truncation logic (2026-03)
- Phase-escalation analysis, networkidle timeout costs, ship-and-observe decision (2026-05/06)

**To index (for systematic improvement):**
- Crawl4AI GitHub Issues "stealth" — UndetectedAdapter bugs, browser detection: https://github.com/unclecode/crawl4ai/issues?q=stealth+undetected
- Crawl4AI Page Interaction Docs — js_code, wait_for, session_id: https://docs.crawl4ai.com/core/page-interaction
- Crawl4AI GitHub Issues "PruningContentFilter" — threshold tuning, code-block destruction: https://github.com/unclecode/crawl4ai/issues?q=pruning+filter
- CookieYes Developer Docs — DOM structure, class conventions: https://www.cookieyes.com/documentation/
- OneTrust Developer Docs — cookie-banner DOM structure: https://developer.onetrust.com/
- Cookiebot Developer Docs — dialog classes: https://www.cookiebot.com/en/developer/
