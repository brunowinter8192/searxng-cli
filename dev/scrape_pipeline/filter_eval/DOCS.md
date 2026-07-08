# dev/scrape_pipeline/filter_eval/

## Role
Crawl4AI content-filter configuration exploration — compares filter strategies (PruningFilter thresholds, BM25ContentFilter, raw), `content_source` parameter variants, and step-by-step pipeline instrumentation to find the best markdown extraction for downstream cleanup/RAG indexing.

## Modules

### 04_filtering.py (149 LOC)

**Purpose:** Tests multiple Crawl4AI content filter configurations (PruningFilter at various thresholds, BM25ContentFilter, raw) against test URLs. Saves raw and fit markdown for each config. Includes code block integrity check. URLs processed in parallel (PARALLEL_URLS=5, Semaphore); the 5 configs per URL run serially.
**Reads:** `domains.txt` (pipeline root) or a URL CLI arg.
**Writes:** `04_reports/<domain>_<config>_raw.md` / `_fit.md`.
**Called by:** CLI only.

### 05_filter_debug.py (382 LOC)

**Purpose:** Instruments the scraping pipeline step-by-step to show what each filter removes at each stage — node counts, character counts, percentage deltas, markdown previews of removed content. Used during active profile development.
**Reads:** `domains.txt` (pipeline root) or a URL CLI arg; `--profile`.
**Writes:** `md/<profile>/05_<domain>_<timestamp>.txt`.
**Called by:** CLI only. `--all` runs against all domains.

### 06_content_source.py (187 LOC)

**Purpose:** Tests Crawl4AI's `content_source` parameter across many URLs per domain. Scrapes each URL with 6 configurations in parallel (5 URLs concurrent, 6 configs per URL concurrent). Max 20 URLs per domain. Configs: `cleaned_html`/`cleaned_html_pruning`/`raw_html`/`raw_html_pruning`/`fit_html`/`fit_html_pruning` (PruningFilter 0.48 where `_pruning`; `fit_markdown` field for pruning configs, `raw_markdown` otherwise).
**Reads:** `dev/explore_pipeline/md/` JSON reports (created via `dev/explore_pipeline/01_discovery.py --all`).
**Writes:** `05_content_source/<domain>/<config>/<NN>_<slug>.md` — raw markdown output per URL for manual inspection.
**Called by:** CLI only. `--all` / `--domain <name>` / `--url <url>`.

## Gotchas
Workflow: 04 gives broad filter comparison, 05 gives step-by-step pipeline transparency for one profile at a time. 06 is a large-scale content_source × filter comparison, requires `dev/explore_pipeline/01_discovery.py --all` to have run first.
