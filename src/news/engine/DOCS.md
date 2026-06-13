# src/news/engine/

## Role

Generic, platform-agnostic pipeline engine modules. Called by `pipeline.py`; no platform-specific
logic lives here. All three modules accept platform parameters explicitly (no hardcoded source names
or collection paths except in `publish.py`'s `rag-cli` invocation).

## Modules

### scrape.py (194 LOC)

**Purpose:** Concurrent async scraper — fresh `AsyncWebCrawler` per URL, Scrapy gate pacing, regwall guard.
**Reads:** entries list (in-memory), ScrapeConfig, regwall_signals list.
**Writes:** `{hash}.md` (BODY ONLY, no frontmatter) to output_dir.
**Called by:** `pipeline.py:_run_cleanup` (reads output), `pipeline.py:run_pipeline` (calls `scrape_entries`).
**Calls out:** `crawl4ai` (AsyncWebCrawler, BrowserConfig, CrawlerRunConfig).

Key: `RegwallGuardError` is raised (not sys.exit) when regwall fraction ≥ `REGWALL_FAIL_THRESHOLD` (0.20).

### dedup.py (44 LOC)

**Purpose:** Filter discover entries to those not yet in the RAG collection by checking filename existence.
**Reads:** entries list (in-memory), collection_dir (filesystem), source name.
**Writes:** nothing (pure filter).
**Called by:** `pipeline.py:run_pipeline`.
**Calls out:** stdlib only.

Filename key: `{source}__{pubdate}__{url_hash}.md` — matches publish convention.

### publish.py (101 LOC)

**Purpose:** Copy cleaned MDs to RAG collection dir; optionally run `rag-cli index`.
**Reads:** clean_manifest (in-memory), clean_dir (filesystem).
**Writes:** `{source}__{pubdate}__{hash}.md` to collection_dir.
**Called by:** `pipeline.py:run_pipeline`.
**Calls out:** `rag-cli` (subprocess).
