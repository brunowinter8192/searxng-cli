# src/news/

## Role

Multi-platform news ingestion pipeline. Runs as `python -m src.news --source <platform>`.
Discovers articles, deduplicates against the raw corpus, scrapes raw markdown, and persists to
`data/news/{name}/raw/`. **Cleanup and publish are fully decoupled** — neither `cleanup.py` nor
`publish.py` is called by any pipe path. The raw corpus is the durable asset; cleanup+index runs
as a separate ad-hoc skill against the full corpus when ready.

Touch this package when adding a new news source or changing pipeline orchestration.
Do NOT import from `src/crawler/` or `src/scraper/` — `src/news/` is self-contained.

## Entry Points

- `python -m src.news --source coindesk --discover-only [--timeframe 30|full]` — discover + inventory update only; no scrape
- `python -m src.news --source coindesk --scrape-only --year YYYY [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--limit N]` — date-filtered backfill: inventory → dedup(raw) → chunked scrape → raw persist → job report
- `python -m src.news --source coindesk` — full pipeline: discover → dedup(raw) → scrape → raw persist
- `python -m src.news --source theblock --discover-only [--timeframe full|sub:N|sub:A-B]` — discover → persist master list `data/news/theblock/master_urls.txt`; no scrape
- `python -m src.news --source theblock [--timeframe delta|full|sub:N]` — full pipeline (proxy_pool engine); also updates master list
- Direct: `asyncio.run(run_pipeline(platform))` or `asyncio.run(run_discover_only(platform))` or `asyncio.run(run_scrape_only(platform, year=..., limit=...))`

`--skip-index` is accepted for CLI compat but is a no-op — no indexing runs in any path.

## Platform Contract (Extension Seam)

To add a new platform:
1. Create `src/news/platforms/<name>/` with `__init__.py` that defines a class implementing `Platform`
   and calls `register(instance)` at import time.
2. Import the platform module in `__main__.py` for side-effect registration.

```python
# Platform Protocol (platform.py)
class Platform(Protocol):
    name: str                   # --source value AND filename prefix f"{name}__"
    collection: str             # target RAG collection name (reserved for future publish skill)
    precondition_url: str       # internet-check URL
    regwall_signals: list[str]  # precise strings; [] = guard disabled
    scrape_engine: str          # "browser" | "proxy_pool" — dispatch key in pipeline.py
    scrape_config: ScrapeConfig # browser engine params; ignored for proxy_pool platforms
    proxy_scrape_config: ProxyScrapeConfig | None  # None for browser platforms

    async def discover(self) -> list[dict]: ...         # [{url,lastmod,publication_date,title,section}]
    def cleanup(self, raw_markdown: str, entry: dict) -> str: ...   # -> pure body (not called by pipe)

# ProxyScrapeConfig (platform.py) — required when scrape_engine == "proxy_pool"
@dataclass
class ProxyScrapeConfig:
    pool_provider: Callable[[], list[tuple[str, str]]]  # called on startup + 60-min refresh
    content_type: str = "html"                           # "html" | "xml" — fetch validation gate
    concurrency: int = 128                               # concurrent (proxy, url) pairs per batch
    buffer_size: int = 1280                              # active buffer depth (10× concurrency)
```

Browser platforms set `scrape_engine = "browser"` and `proxy_scrape_config = None`.
Proxy platforms set `scrape_engine = "proxy_pool"` and provide a `ProxyScrapeConfig` with a
`pool_provider` callable (e.g. `load_backfill_pool` from `engine/proxy_pool/pool_loaders.py`).

**Optional platform attributes** (not in Protocol; consumed via `getattr` in `pipeline.py`):
- `timeframe: str` — discovery mode; set by `__main__` from `--timeframe`.
  CoinDesk: `"full"` (cursor to 2018-01-01) | integer string N (last N days) | `"delta"` = 30 days.
  TheBlock: `"delta"` (default, top-2 subs) | `"full"` (all subs) | `"sub:N"` | `"sub:A-B"`.
  When `--timeframe` is not `"delta"` AND `--discover-only` is not set, `__main__` auto-forces
  `skip_index=True` and prints `"After review, run: rag-cli index --collection <collection>"`.
- `uses_master_list: bool` — if `True`, `pipeline.py` writes a single `data/news/{name}/master_urls.txt`
  (format `YYYY-MM-DD\t<url>`, sorted+deduped, set-union append) instead of timestamped JSON snapshots
  or per-year inventory shards. Both `run_discover_only()` and `run_pipeline()` proxy_pool path honour it.
  Currently `True` only for TheBlock. CoinDesk: attribute absent (defaults `False`) → unchanged behaviour.

## Directory Map

| Path | Role | LOC |
|---|---|---|
| `platform.py` | ScrapeConfig + ProxyScrapeConfig + Platform Protocol | 35 |
| `registry.py` | name → Platform registry; register() / get() | 19 |
| `pipeline.py` | Async orchestrator; raw-only stages 1–3; run_discover_only(); run_scrape_only(); _persist_master_list() | 321 |
| `__main__.py` | argparse entry point; --source + --skip-index + --timeframe + --discover-only | 102 |
| `engine/` | Generic scrape engines (browser + proxy_pool) + dedup | — |
| `platforms/coindesk/` | CoinDesk platform implementation | — |
| `platforms/theblock/` | The Block platform — proxy_pool, hash-dedup, JSON-LD cleanup | — |

## Flow (run_pipeline — both engines)

1. **discover** — `platform.discover()` → entry list.
   - TheBlock (`uses_master_list=True`): `_persist_master_list()` → `data/news/theblock/master_urls.txt` (YYYY-MM-DD\t{url}, sorted+deduped, set-union append). No snapshot JSON.
   - Other platforms (browser/CoinDesk path): JSON snapshot written to `data/news/{name}/discover/`.
2. **dedup** — `filter_new_entries(entries, raw_dir, name, mode="raw")` against `data/news/{name}/raw/` (existence of `{hash}.md`). Always `mode="raw"` — no collection check.
3. **scrape** — dispatch on `platform.scrape_engine`:
   - `"browser"` → `scrape_entries()` — fresh `AsyncWebCrawler` per URL, Scrapy gate pacing. Writes raw body to `raw/{hash}.md`. On `RegwallGuardError`: `exc.manifest` recovered, ok files preserved, persist continues.
   - `"proxy_pool"` → `scrape_entries_proxy()` — sustained proxy rotation via `run_loop`. Writes raw body to `raw/{hash}.md`. Janitor lifecycle (box_lock, start_job/end_job, AcquireLogger) preserved.
4. **raw persist** — `_append_to_raw_manifest(raw_dir, ok_entries)` writes `raw/manifest.jsonl` ({hash,url,publication_date}). `_update_blocked_urls()` updates:
   - browser: `regwall_urls.txt` + `empty_urls.txt`
   - proxy_pool: `dead_urls.txt` + `failed_urls.txt`

No Stage 4 (cleanup) or Stage 5 (publish). `cleanup.py` and `publish.py` remain on disk but are not called.

## Scrape-Job Flow (run_scrape_only — CoinDesk `--scrape-only`)

CoinDesk-specific decoupled backfill path — no browser warmup or discover stage.

1. **inventory** — `platform.load_scrape_entries(year, from_date, to_date, limit)` reads per-year shards `data/news/coindesk/inventory/coindesk_{year}.txt` (format `YYYY-MM-DD\t<url>`), applies date filter, returns `[{url, publication_date}]`.
2. **raw-diff** — `filter_new_entries(entries, raw_dir, name, mode="raw")` skips URLs already present as `{hash}.md` in `data/news/coindesk/raw/`. Resumable: re-run picks up from where the previous run ended.
3. **chunked scrape → raw persist** — `scrape_chunks_raw()` in `engine/scrape_job.py` processes 200-URL chunks. Each chunk: scrape into raw_dir → `_append_to_raw_manifest()` → `_update_blocked_urls()`. `RegwallGuardError` stops the loop; already-written raw files + manifest entries are durable.
4. **report** — `write_scrape_report()` writes `data/news/{name}/scrape_jobs/{job_id}/job.md` (counts, regwall rate, throughput, backfill projection, char-count percentiles p10–p95) and `cumulative.png`.

## Documentation Tree

- [engine/DOCS.md](engine/DOCS.md) — scrape / dedup / engine modules
- [platforms/coindesk/DOCS.md](platforms/coindesk/DOCS.md) — CoinDesk platform implementation
- [platforms/theblock/DOCS.md](platforms/theblock/DOCS.md) — The Block platform implementation
