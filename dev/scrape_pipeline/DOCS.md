# Scrape Pipeline

Quality monitoring and configuration testing for the URL scraper module.

## Pipe-Scraper Eval Suite (`p1_` + `A_`, scrape_pipeline/ root)

Empirical eval of the GH REST API docs scrape pipeline — WAF boundary, content completeness, full-corpus capture.

### p1_pipe_scraper.py (97 LOC)

**Purpose:** Core scraper probe — `scrape_urls(urls, delay_s, page_timeout_ms, concurrency, output_dir)` → per-URL metrics dicts. Config locked to: browser, `wait_until="domcontentloaded"`, `delay_before_return_html`, hard `page_timeout`, `DefaultMarkdownGenerator()` raw, no `PruningContentFilter`, no garbage-drop. Saves `<!-- source: url -->\n\nraw_md` per URL when `output_dir` set.
**Calls out:** `crawl4ai` (AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, DefaultMarkdownGenerator)
**Called by:** `A_pipe_scrape_eval.py`

### A_pipe_scrape_eval.py (481 LOC)

**Purpose:** Eval harness — three phases via argparse: `phase1` (concurrency/WAF sweep), `phase2` (delay sweep, completeness proxy), `phase3` (full 316-URL run: WAF probe + batched pacing + position-tracked 429s + retry pass). Writes timestamped MD reports to `A_pipe_scrape_eval_reports/`; phase3 also saves raw markdown corpus.
**Calls out:** `p1_pipe_scraper.scrape_urls`
**Called by:** CLI only

```bash
# WAF/concurrency sweep (30 stratified URLs, delay=1.0s fixed)
./venv/bin/python dev/scrape_pipeline/A_pipe_scrape_eval.py phase1

# Delay sweep (30 stratified URLs, c=5 fixed)
./venv/bin/python dev/scrape_pipeline/A_pipe_scrape_eval.py phase2

# Full run (316 URLs, WAF probe → batched c=5 + 30s pauses → retry on 429s)
./venv/bin/python dev/scrape_pipeline/A_pipe_scrape_eval.py phase3 --delay 0.5
```

**Reports:**
- `A_pipe_scrape_eval_reports/concurrency_sweep_<ts>.md` — phase1
- `A_pipe_scrape_eval_reports/delay_sweep_<ts>.md` — phase2 (includes WAF-contamination note)
- `A_pipe_scrape_eval_reports/full_run_<ts>.md` — phase3 summary
- `A_pipe_scrape_eval_reports/full_run_<ts>/` — phase3 raw markdown corpus (one .md per URL)

---

## Top-Level Scripts

### 01_dual_mode_smoke.py

**Purpose:** A/B comparison harness — takes a search-results markdown report (e.g. `dev/search_pipeline/01_reports/pipeline_smoke_*.md`), parses URLs from a chosen query, scrapes each URL through BOTH production CLI modes in parallel via asyncio: Mode 1 (`scrape_url_raw`, raw markdown to file, no filter) and Mode 2 (`scrape_url`, PruningContentFilter@0.48, 15K char cap, in-memory). Produces a side-by-side comparison report with per-URL byte sizes, garbage detection, first content lines.

**Use case:** evaluate Mode 1 vs Mode 2 quality on the same URL set. Reusable for library A/B testing — replace the cli.py-subprocess invocation with another extraction library to compare.

**Input:** `--input <path-to-search-md>` (required), `--query <id-or-text>` (default 1), `--output-dir <path>` (default `01_dual_mode_outputs/<ts>/`).

**Output:** Per-mode subdirs (`mode1_raw/`, `mode2_filtered/`) with one .md per URL, plus `01_dual_mode_report.md` at parent level.

```bash
./venv/bin/python3 dev/scrape_pipeline/01_dual_mode_smoke.py --input dev/search_pipeline/01_reports/pipeline_smoke_<ts>.md --query 24
```

### 02_raw_smoke.py

**Purpose:** Dev-only Mode 1 raw scrape — Crawl4AI direct via `arun_many`, no prod imports, no `cli.py` subprocess. Parses Q24 URLs from a search smoke report, scrapes all in parallel, writes `<slug>_<6-char-md5>.md` per URL plus `02_raw_report.md` triage table. Slug includes full-URL md5 hash to prevent query-string collisions (HN `?id=N` URLs both preserved).

**Output:** `02_raw_outputs/<ts>/` — 20 .md files + report. Status `empty` includes optional annotation `(PDF)` or `(plugin-domain: github)`. NO fallback chain (single Crawl4AI config), NO garbage detection, NO cookie strip — fail fast, see what's actually there.

**Use case:** clean baseline for downstream cleanup work + comparison against filter outputs.

```bash
./venv/bin/python dev/scrape_pipeline/02_raw_smoke.py --input dev/search_pipeline/01_reports/pipeline_smoke_<ts>.md --query 24
```

## Tests

### test_pdf_chain.py + conftest.py

**Purpose:** Pytest test suite for `src/scraper/pdf_chain.py` and `download_pdf_workflow`. Two layers: (a) **Unit tests** (no network) covering pure-function regression guards on `apply_tier1_transform`, `is_blacklisted`, `is_github_blob`, `should_download_as_pdf`, `parse_citation_pdf_url` — 52 trivial-but-meaningful asserts. (b) **Integration tests** marked `@pytest.mark.network`, gated by the `--network` flag — exercise `download_pdf_workflow` end-to-end against real arxiv/aclanthology/openreview URLs, assert real PDF bytes land in tmp_path. Plus blacklist + GitHub-blob error-path assertions.

`conftest.py` registers the `network` marker and adds the `--network` CLI option.

**Why this layering:** unit tests catch regressions if anyone refactors the constants/regexes; integration tests catch real-world contract failures (e.g. the TIER1 bypass bug from session 2026-05-07 where arxiv `/pdf/<id>` had no `.pdf` suffix and was wrongly routed to citation_pdf_url extraction).

```bash
# Unit tests only (default — no network)
./venv/bin/python -m pytest dev/scrape_pipeline/test_pdf_chain.py

# All including network integration tests
./venv/bin/python -m pytest dev/scrape_pipeline/test_pdf_chain.py --network
```

## Shared Config (pipeline root)

### domains.txt

Test URLs for scripts in browser_eval/ and filter_eval/. One URL per line, comments with `#`.

### failures.jsonl

**Purpose:** Persistent failure log from production `scrape_url` runs. Every URL where all 3 scrape attempts are exhausted (normal networkidle, normal domcontentloaded, stealth networkidle) gets appended as one JSONL line.

**Written by:** `log_scrape_failure()` in `src/scraper/scrape_url.py` — called automatically at the final failure exit in `scrape_url_workflow()`.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `ts` | ISO 8601 UTC string | Timestamp of the failure |
| `url` | string | URL that failed to scrape |
| `garbage_type` | string \| null | Last detected garbage type (`http_error`, `cookie_wall`, `login_wall`, `cloudflare`, `nav_dump`, `crawl4ai_error`) or null if no content was returned |
| `status_code` | int \| null | HTTP status code from the last attempt that returned one, or null if not available |

**Usage:**

```bash
# Show all failures
cat dev/scrape_pipeline/failures.jsonl | jq .

# Count by garbage_type
cat dev/scrape_pipeline/failures.jsonl | jq -r '.garbage_type // "none"' | sort | uniq -c | sort -rn

# Find all 404s
cat dev/scrape_pipeline/failures.jsonl | jq 'select(.status_code == 404)'

# Recent failures
tail -20 dev/scrape_pipeline/failures.jsonl | jq .
```

The file is gitignored — it accumulates across production MCP tool calls and is for local analysis only.

## 03_cleanup/ → skills/scrape-cleanup

### clean.py

**Purpose:** URL-spanning cleanup of raw scraped markdown for RAG indexing. Reads files from `02_raw_outputs/<ts>/`, applies pattern set (pre-h1 chrome strip, skip-link strip, sphinx anchor strip, tail chrome strip, blank-line collapse) plus site-specific handlers (GitHub issue title anchor, HN top-nav strip), writes cleaned files to `cleaned_outputs/<ts>/`.

**Note:** This script is the **iterative-discovery artifact** from the session that produced the scrape-cleanup skill — kept as reference for which patterns work on which shapes. Do NOT copy to prod.

**Output:** `cleaned_outputs/<ts>/<slug>_<hash>.md` per URL + `_summary.md` with byte deltas.

```bash
./venv/bin/python dev/scrape_pipeline/03_cleanup/clean.py
```

## 04_overview_sweep/

### sweep.py + analyze.py + sweep_config.yml

**Purpose:** Empirical sweep of Crawl4AI filter dimensions (PruningContentFilter at thresholds 0.30/0.48/0.60/0.75 + BM25ContentFilter, content_source ∈ {cleaned_html, fit_html, raw_html}, excluded_selector ∈ {cookies, cookies+sphinx}) against the Q24 URL set. Total: 36 configs × 20 URLs = 720 outputs.

`sweep.py` writes `sweep_outputs/<ts>/<config_name>/<slug>_<hash>.md` per URL + `_run_metadata.json` with timing/sizes. `analyze.py` diffs each candidate against the clean-raw baseline (latest `cleaned_outputs/`), computes line-set recall/precision/F1 per (config, URL), aggregates per config (median + per-shape), generates `_analysis.md` with cross-config ranking + per-shape breakdown + unified_diff drill-down for top-3 configs.

**Caveat:** F1 is symmetric — chrome retention and content loss reduce it equally. For asymmetric preferences (e.g. "strip more chrome at cost of detail"), look at `precision` column separately and read the actual diffs in the drill-down section.

```bash
./venv/bin/python dev/scrape_pipeline/04_overview_sweep/sweep.py
./venv/bin/python dev/scrape_pipeline/04_overview_sweep/analyze.py
```

## 05_paper_mode/ → direct PDF download prototype

### download.py

**Purpose:** Standalone PDF downloader — no prod imports, no Crawl4AI. Takes `.pdf` URLs via positional args or `--input <smoke.md>` (parses all `.pdf` URLs across all queries). Downloads each via `requests.get(stream=True)` with Content-Type check, writes to `~/Downloads/`. Filename: Content-Disposition → URL basename → `download_<ts>.pdf`. Per-URL status table printed to stdout.

**Failures observed (12-URL test run 2026-05-06):** Springer (paywall → HTML redirect, not PDF); Academia.edu (HTTP 403). 10/12 ok.

```bash
# From a smoke report (all queries, .pdf filter)
./venv/bin/python dev/scrape_pipeline/05_paper_mode/download.py --input dev/search_pipeline/01_reports/pipeline_smoke_<ts>.md

# Direct URLs
./venv/bin/python dev/scrape_pipeline/05_paper_mode/download.py https://example.com/paper.pdf

# Re-download existing files
./venv/bin/python dev/scrape_pipeline/05_paper_mode/download.py --overwrite --input <smoke.md>
```

### pdf_test_urls.md

12-URL test inventory extracted from `pipeline_smoke_20260506_003915.md`. Columns: Q-Nr, URL, Status (filled after test run).

## 06_cloudflare_md_adoption/

### 06_cloudflare_md_adoption.py

**Purpose:** Adoption probe for the `Accept: text/markdown` server-side markdown convention (Cloudflare Markdown-for-Agents, Vercel edge, others). Probes a curated 29-URL set across three categories (Cloudflare-owned positive controls, likely-CF-fronted candidate sites, non-CF negative controls) with the markdown Accept header via httpx async (Semaphore concurrency 10, 15s timeout). For URLs that respond with `text/markdown`, fetches a baseline HTML GET to compute byte-reduction. Outputs a tabular markdown report.

**Use case:** baseline measurement of Phase-0-fast-path adoption (`fetch_markdown_fastpath` in production). Re-run periodically to track adoption growth — the script is the artifact, each run produces a separate timestamped report.

**Output:** `06_reports/cf_md_adoption_<YYYYMMDD_HHMMSS>.md` — per-URL table (URL, CF-fronted, MD-served, status, content-type, x-md-tokens, HTML-bytes, MD-bytes, byte-reduction, response-ms) plus summary section (counts, mean/median byte-reduction on positives, positive-case URL list for run-to-run comparison, server header distribution among CF-fronted hits).

```bash
./venv/bin/python dev/scrape_pipeline/06_cloudflare_md_adoption.py
./venv/bin/python dev/scrape_pipeline/06_cloudflare_md_adoption.py --output-dir /tmp/cf_probe/
```

**Initial measurement (2026-05-07, 29 URLs):** 16/29 CF-fronted by cf-ray header, 7/29 actually serve markdown (5/5 Cloudflare-owned positive controls + 1 false-positive Anthropic stub of 12 bytes + Vercel via own edge). Mean byte-reduction 92.3%, median 97.0%. Adoption among non-Cloudflare-owned CF-customers: ≈0% in May 2026, 3 months after Beta launch.

## browser_eval/

### 01_baseline.py

**Purpose:** Scrapes all test domains using the production `scrape_url_workflow` and saves results as numbered iterations with metadata (char count, word count, timestamp).
**Input:** `domains.txt` (pipeline root)
**Output:** `01_baselines/<domain>/iteration_<N>.md` + `metadata_<N>.json`

```bash
./venv/bin/python dev/scrape_pipeline/browser_eval/01_baseline.py
```

### 02_regression.py

**Purpose:** Compares the last two iterations per domain to detect regressions. Generates unified diffs and classifies changes by magnitude (IDENTICAL, MINOR_CHANGE, MODERATE_CHANGE, MAJOR_CHANGE).
**Input:** `01_baselines/`
**Output:** `02_reports/diff_report_<timestamp>.txt`

```bash
./venv/bin/python dev/scrape_pipeline/browser_eval/02_regression.py
```

### 03_browser.py

**Purpose:** Tests multiple Crawl4AI browser configurations for JS-heavy sites that fail with default settings. Compares content yield (char count, word count) across configs with different wait strategies: domcontentloaded baseline, networkidle, extended delay, CSS selector wait, and full page scan.
**Output:** `03_reports/<domain>_<slug>_<config>.md`

```bash
./venv/bin/python dev/scrape_pipeline/browser_eval/03_browser.py
./venv/bin/python dev/scrape_pipeline/browser_eval/03_browser.py https://docs.trychroma.com/docs/overview/telemetry
```

## filter_eval/

### 04_filtering.py

**Purpose:** Tests multiple Crawl4AI content filter configurations (PruningFilter at various thresholds, BM25ContentFilter, raw) against test URLs. Saves raw and fit markdown for each config. Includes code block integrity check.
**Input:** `domains.txt` (pipeline root)
**Output:** `04_reports/<domain>_<config>_raw.md` / `_fit.md`

URLs are processed in parallel (PARALLEL_URLS=5, Semaphore). The 5 configs per URL run serially (fast, no benefit from parallelism).

```bash
./venv/bin/python dev/scrape_pipeline/filter_eval/04_filtering.py
./venv/bin/python dev/scrape_pipeline/filter_eval/04_filtering.py https://example.com
```

### 05_filter_debug.py

**Purpose:** Instruments the scraping pipeline step-by-step to show what each filter removes at each stage. Reports include node counts, character counts, percentage deltas, and markdown previews of removed content. Used during active profile development.
**Input:** `domains.txt` (pipeline root)
**Output:** `05_reports/<profile>/<domain>_<timestamp>.txt`

```bash
./venv/bin/python dev/scrape_pipeline/filter_eval/05_filter_debug.py https://de.wikipedia.org/wiki/Biber
./venv/bin/python dev/scrape_pipeline/filter_eval/05_filter_debug.py --profile wiki
./venv/bin/python dev/scrape_pipeline/filter_eval/05_filter_debug.py --all
```

### 06_content_source.py

**Purpose:** Tests Crawl4AI's `content_source` parameter across many URLs per domain. Scrapes each URL with 6 configurations in parallel (5 URLs concurrent, 6 configs per URL concurrent) and saves the raw markdown output as individual .md files for manual inspection. Max 20 URLs per domain.
**Input:** Explore pipeline reports (JSON) from dev/explore_pipeline/01_reports/ — created by running `dev/explore_pipeline/01_discovery.py --all`
**Output:** `05_content_source/<domain>/<config>/<NN>_<slug>.md`

Configs tested:

| Config | content_source | Filter | Markdown Field |
|--------|---------------|--------|----------------|
| cleaned_html | cleaned_html | none | raw_markdown |
| cleaned_html_pruning | cleaned_html | PruningFilter 0.48 | fit_markdown |
| raw_html | raw_html | none | raw_markdown |
| raw_html_pruning | raw_html | PruningFilter 0.48 | fit_markdown |
| fit_html | fit_html | none | raw_markdown |
| fit_html_pruning | fit_html | PruningFilter 0.48 | fit_markdown |

```bash
./venv/bin/python dev/scrape_pipeline/filter_eval/06_content_source.py --all
./venv/bin/python dev/scrape_pipeline/filter_eval/06_content_source.py --domain searxng_docs
./venv/bin/python dev/scrape_pipeline/filter_eval/06_content_source.py --url https://example.com
```

## garbage_eval/

### 07_result_inspect.py

**Purpose:** Inspects the full Crawl4AI `CrawlResult` object to discover available metadata fields. Scrapes 3 URLs (normal, 404, consent-heavy) and enumerates all result attributes with types and values. Key finding: `result.status_code` is available and reliable (404 for error pages, 200 for good pages). `result.success` is always True and unreliable.
**Output:** `07_reports/result_inspect_<timestamp>.md`

```bash
./venv/bin/python dev/scrape_pipeline/garbage_eval/07_result_inspect.py
```

### 08_garbage_edge_cases.py

**Purpose:** Tests `is_garbage_content()` against known edge case URLs (consent-prefix sites, padded 404 pages) and baseline URLs. Scrapes raw and filtered content, runs garbage detection on both, and tests header-zone (first 500 chars) detection for padded 404s.
**Output:** `08_reports/garbage_edge_cases_<timestamp>.md`

```bash
./venv/bin/python dev/scrape_pipeline/garbage_eval/08_garbage_edge_cases.py
```

### 09_garbage_fix_prototype.py

**Purpose:** Prototypes and validates garbage detection improvements. Tests two fixes: (1) status_code based 404 detection, (2) consent prefix stripping. Validates against edge case and baseline URLs to confirm no false positives.
**Output:** `09_reports/garbage_fix_prototype_<timestamp>.md`

```bash
./venv/bin/python dev/scrape_pipeline/garbage_eval/09_garbage_fix_prototype.py
```

### 10_live_garbage_test.py

**Purpose:** Live integration test for garbage detection. Two modes: `--search QUERY` fires a live SearXNG search, scrapes the top 10 results, and runs garbage detection on each. `--edge-cases` scrapes known problem URLs (consent-prefix, padded 404, paywall). Results logged to `failures.jsonl` and saved as report.
**Input:** Live SearXNG search or hardcoded edge-case URLs
**Output:** `10_reports/live_garbage_test_<timestamp>.md`

```bash
./venv/bin/python dev/scrape_pipeline/garbage_eval/10_live_garbage_test.py --search "cookie policy GDPR compliance"
./venv/bin/python dev/scrape_pipeline/garbage_eval/10_live_garbage_test.py --edge-cases
```

## Workflows

### Regression (browser_eval 01 → 02)

Standard workflow when changing the production scraper. Run baseline, then compare with previous iteration.

### Browser Debug (browser_eval 03)

For JS-heavy sites that fail with default settings. Compare wait strategies to find what works.

### Filter Exploration (filter_eval 04 → 05)

Explore filter configurations. 04 gives broad comparison, 05 gives step-by-step pipeline transparency.

### Content Source (filter_eval 06)

Large-scale comparison of which HTML source + filter combination produces the best markdown for downstream cleanup agents. Requires explore_pipeline/01_reports as input. Output is raw .md files for manual review.

### Garbage Investigation (garbage_eval 07 → 08 → 09)

Investigate edge cases in garbage detection. 07 discovers available metadata. 08 reproduces failures. 09 prototypes and validates fixes before production code changes.
