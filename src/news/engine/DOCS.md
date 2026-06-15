# src/news/engine/

## Role

Generic, platform-agnostic pipeline engine modules. Called by `pipeline.py`; no platform-specific
logic lives here. All modules accept platform parameters explicitly (no hardcoded source names or
collection paths except in `publish.py`'s `rag-cli` invocation).

`pipeline.py` dispatches Stage 3 on `platform.scrape_engine`: `"browser"` → `scrape.py`;
`"proxy_pool"` → `proxy_pool/scrape.py`.

## Modules

### scrape.py (194 LOC)

**Purpose:** Browser-engine scraper — fresh `AsyncWebCrawler` per URL, Scrapy gate pacing, regwall guard. Active when `platform.scrape_engine == "browser"`.
**Reads:** entries list (in-memory), ScrapeConfig, regwall_signals list.
**Writes:** `{hash}.md` (BODY ONLY, no frontmatter) to output_dir.
**Called by:** `pipeline.py:run_pipeline` (browser dispatch arm).
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

### proxy_pool/ (11 modules — see DOCS.md)

Generic proxy-rotation scrape engine. Active when `platform.scrape_engine == "proxy_pool"`.
Entry point: `scrape_entries_proxy()` in `proxy_pool/scrape.py`.

## Documentation Tree

- [proxy_pool/DOCS.md](proxy_pool/DOCS.md) — proxy-rotation engine (loop, fetch, cooldown, buffer, logger, janitor, box_lock, proxy_key, pool_loaders, monosans_loader, scrape)
