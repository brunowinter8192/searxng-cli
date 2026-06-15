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

### dedup.py (50 LOC)

**Purpose:** Filter discover entries to those not yet in the RAG collection by checking filename existence.
**Reads:** entries list (in-memory), collection_dir (filesystem), source name, mode.
**Writes:** nothing (pure filter).
**Called by:** `pipeline.py:run_pipeline` (mode sourced via `getattr(platform, "dedup_mode", "pubdate")`).
**Calls out:** stdlib only.

Two modes via `mode` param (default `"pubdate"`):
- `"pubdate"`: exact match `{source}__{pubdate}__{hash}.md` — CoinDesk default.
- `"hash_only"`: glob `{source}__*__{hash}.md` — for platforms (e.g. The Block) where
  `publication_date` is not available at discover time (comes from fetched content post-scrape).

### publish.py (134 LOC)

**Purpose:** Copy cleaned MDs to RAG collection dir; write/merge URL manifest; optionally run `rag-cli index`.
**Reads:** clean_manifest (in-memory), clean_dir (filesystem), existing `{collection}__index.jsonl` if present.
**Writes:** `{source}__{pubdate}__{hash}.md` to collection_dir; `{collection_name}__index.jsonl` in collection_dir (one JSON line per article: `{hash, url, publication_date, filename}`; deduped by hash; written even when `skip_index=True`).
**Called by:** `pipeline.py:run_pipeline`.
**Calls out:** `rag-cli` (subprocess).

### proxy_pool/ (11 modules — see DOCS.md)

Generic proxy-rotation scrape engine. Active when `platform.scrape_engine == "proxy_pool"`.
Entry point: `scrape_entries_proxy()` in `proxy_pool/scrape.py`.

## Documentation Tree

- [proxy_pool/DOCS.md](proxy_pool/DOCS.md) — proxy-rotation engine (loop, fetch, cooldown, buffer, logger, janitor, box_lock, proxy_key, pool_loaders, monosans_loader, scrape)
