# src/news/

## Role

Multi-platform news ingestion pipeline. Runs as `python -m src.news --source <platform>`.
Discovers articles, deduplicates against the raw corpus, scrapes raw markdown into
`data/news/{name}/raw/`. For The Block (proxy_pool engine), the pipeline also runs an in-pipe
clean-pass that writes cleaned articles directly to the RAG collection dir
(`rag-cli/data/documents/theblock/`). Indexing remains fully decoupled — no `rag-cli index`
call in any pipe path.

Touch this package when adding a new news source or changing pipeline orchestration.
Do NOT import from `src/crawler/` or `src/scraper/` — `src/news/` is self-contained.

## Entry Points

- `python -m src.news --source coindesk --discover-only [--timeframe 30|full]` — discover + inventory update only; no scrape
- `python -m src.news --source coindesk --scrape-only --year YYYY [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--limit N]` — date-filtered backfill: inventory → dedup(raw) → chunked scrape → raw persist → job report
- `python -m src.news --source coindesk` — full pipeline: discover → dedup(raw) → scrape → raw persist
- `python -m src.news --source theblock --discover-only [--timeframe full|sub:N|sub:A-B]` — discover → persist master list `data/news/theblock/discover/master_urls.txt`; no scrape
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
    scrape_engine: str          # "browser" | "proxy_pool" | "proxy_riding" — dispatch key in pipeline.py
    scrape_config: ScrapeConfig # browser engine params; ignored for proxy_pool/proxy_riding platforms
    proxy_scrape_config: ProxyScrapeConfig | None  # None for browser/proxy_riding platforms

    async def discover(self) -> list[dict]: ...         # [{url,lastmod,publication_date,title,section}]
    def cleanup(self, raw_html: str, entry: dict) -> str: ...   # -> clean Markdown; called by proxy_pool clean-pass (TheBlock only)

# ProxyScrapeConfig (platform.py) — required when scrape_engine == "proxy_pool"
@dataclass
class ProxyScrapeConfig:
    pool_provider: Callable[[], list[tuple[str, str]]]  # called on startup + 60-min refresh
    content_type: str = "html"                           # "html" | "xml" — fetch validation gate
    concurrency: int = 128                               # concurrent (proxy, url) pairs per batch
    buffer_size: int = 1280                              # active buffer depth (10× concurrency)
```

Browser platforms set `scrape_engine = "browser"` and `proxy_scrape_config = None`.
Proxy-pool platforms set `scrape_engine = "proxy_pool"` and provide a `ProxyScrapeConfig`.
Proxy-riding platforms set `scrape_engine = "proxy_riding"` and `proxy_scrape_config = None`.

**Optional platform attributes** (not in Protocol; consumed via `getattr` in `pipeline.py`):
- `riding_scrape_config: RidingScrapeConfig | None` — config for the `proxy_riding` engine; consumed
  via `getattr(platform, "riding_scrape_config", None) or RidingScrapeConfig()` in `run_scrape_only`.
  Only CoinDesk defines this attr. NOT in Protocol (avoids requiring all platforms to declare it).
- `timeframe: str` — discovery mode; set by `__main__` from `--timeframe`.
  CoinDesk: `"full"` (cursor to 2018-01-01) | integer string N (last N days) | `"delta"` = 30 days.
  TheBlock: `"delta"` (default, top-2 subs) | `"full"` (all subs) | `"sub:N"` | `"sub:A-B"`.
  When `--timeframe` is not `"delta"` AND `--discover-only` is not set, `__main__` auto-forces
  `skip_index=True` and prints `"After review, run: rag-cli index --collection <collection>"`.
- `uses_master_list: bool` — if `True`, `pipeline.py` writes a single `data/news/{name}/discover/master_urls.txt`
  (format `YYYY-MM-DD\t<url>`, sorted+deduped, set-union append) instead of timestamped JSON snapshots
  or per-year inventory shards. Both `run_discover_only()` and `run_pipeline()` proxy_pool path honour it.
  Currently `True` only for TheBlock. CoinDesk: attribute absent (defaults `False`) → unchanged behaviour.

## Directory Map

| Path | Role | LOC |
|---|---|---|
| `platform.py` | ScrapeConfig + ProxyScrapeConfig + Platform Protocol | 35 |
| `registry.py` | name → Platform registry; register() / get() | 19 |
| `pipeline.py` | Async orchestrator; stages 1–4 for proxy_pool (TheBlock); raw-only for browser/proxy_riding; run_discover_only(); run_scrape_only(); _persist_master_list(); _run_clean_pass() | 420 |
| `__main__.py` | argparse entry point; --source + --skip-index + --timeframe + --discover-only | 102 |
| `engine/` | Generic scrape engines (browser + proxy_pool + proxy_riding) + dedup. All three engines wired. | — |
| `platforms/coindesk/` | CoinDesk platform implementation | — |
| `platforms/theblock/` | The Block platform — proxy_pool, hash-dedup, JSON-LD cleanup | — |

## Flow (run_pipeline — proxy_pool / TheBlock)

1. **discover** — `platform.discover()` → entry list. `_persist_master_list()` → `data/news/theblock/discover/master_urls.txt` (YYYY-MM-DD\t{url}, sorted+deduped, set-union append). No snapshot JSON written alongside it.
2. **dedup** — `filter_new_entries(entries, raw_dir, name, mode="raw", exclude_urls=failure_urls)` against `data/news/{name}/raw/`. Subtracts two disjoint sets: `{hash}.md` already exists in raw (n_skip_raw), and URL in `dead_urls.txt` + `failed_urls.txt` (n_excluded — known-dead/failed, permanently excluded, no retry). Both files loaded from `discover_dir/` before the call; absent on first run = empty exclusion. Log: `dedup → {total} total, {n_skip_raw} already in raw, {n_excluded} known-failures excluded, {n_new} new`.
3. **scrape** — `scrape_entries_proxy()` — sustained proxy rotation via `run_loop`. Writes raw body to `raw/{hash}.md`. Janitor lifecycle (box_lock, start_job/end_job, AcquireLogger) preserved.
4. **raw persist** — `_append_to_raw_manifest(raw_dir, ok_entries)` → `raw/manifest.jsonl`. `_update_blocked_urls()` → `discover/dead_urls.txt` + `discover/failed_urls.txt`.
5. **clean-pass** — `_run_clean_pass()`: for each ok entry, reads `raw/{hash}.md`, calls `platform.cleanup()` (JSON-LD parse + Markdown + `_post_clean()`), writes `theblock__{pubdate}__{hash}.md` to `rag-cli/data/documents/theblock/`. Body-less articles (empty `articleBody` or no `NewsArticle` JSON-LD) → URL appended to `data/news/theblock/clean/bodyless_urls.txt` (set-union, sorted; `clean/` created on first write). Raw files never modified. Progress logged every 200 entries. Indexing NOT triggered — `rag-cli index` remains a separate manual step.

## Flow (run_pipeline — browser / CoinDesk)

1. **discover** — `platform.discover()` → entry list. JSON snapshot written to `data/news/{name}/discover/`.
2. **dedup** — same as proxy_pool path.
3. **scrape** — `scrape_entries()` — fresh `AsyncWebCrawler` per URL, Scrapy gate pacing. Writes raw body to `raw/{hash}.md`. On `RegwallGuardError`: `exc.manifest` recovered, ok files preserved.
4. **raw persist** — `_append_to_raw_manifest()` + `_update_blocked_urls()` → `regwall_urls.txt` + `empty_urls.txt`.

No clean-pass or publish in the browser path. `publish.py` remains on disk but is not called.

## Scrape-Job Flow (run_scrape_only — CoinDesk `--scrape-only`)

CoinDesk-specific decoupled backfill path — no browser warmup or discover stage.
Dispatches on `platform.scrape_engine`: `"proxy_riding"` (current CoinDesk) or `"browser"` (legacy).

1. **inventory** — `platform.load_scrape_entries(year, from_date, to_date, limit)` reads per-year shards `data/news/coindesk/inventory/coindesk_{year}.txt` (format `YYYY-MM-DD\t<url>`), applies date filter, returns `[{url, publication_date}]`.
2. **raw-diff** — `filter_new_entries(entries, raw_dir, name, mode="raw", raw_ext=ext)` where `ext=".html"` for `proxy_riding`, `".md"` for `browser`. Skips URLs whose raw file already exists. Resumable: re-run picks up where the previous run ended.

**proxy_riding path (CoinDesk current):**

3. **scrape** — `scrape_entries_riding(new_entries, platform_dir, riding_cfg, job_dir)` processes the **full entry set at once** (no chunking). The engine manages its own concurrency (64 slots × 4 browsers), watchdog, and requeue loop. Returns `(manifest, state)`. Raw HTML written to `data/news/coindesk/raw/{hash}.html` by the engine (`platform_dir/raw/{hash}.html`). `job_dir` is passed so the stall-watchdog abort path writes its report to the same location as normal completion (see report step below).
4. **raw persist** — `_append_to_raw_manifest(raw_dir, ok_entries)` appends ok entries to `raw/manifest.jsonl`.
5. **report** — `write_riding_report(state, job_dir, t_job_start)` writes `data/news/{name}/scrape_jobs/{job_id}/job.md` (counts, throughput, HTML-size percentiles, ride-length histogram, regwall-by-position) + three plots. Note: `write_scrape_report` (browser reporter) is NOT used — it requires `t_chunk_start`/`elapsed_s` fields absent from riding manifests and would crash. **Stall-abort path writes to the identical `scrape_jobs/{job_id}/` dir** — `_abort_stall` uses `state.job_dir` (= `job_dir`) for `remaining_urls.txt`, `job.md`, and the three plots; the platform root is never written to by either path.

**browser path (legacy):**

3. **chunked scrape → raw persist** — `scrape_chunks_raw()` processes 200-URL chunks. Each chunk: scrape into raw_dir → `_append_to_raw_manifest()` → `_update_blocked_urls()`. Writes `{hash}.md`. `RegwallGuardError` stops the loop; already-written raw files + manifest entries are durable.
4. **report** — `write_scrape_report()` writes `job.md` (counts, regwall rate, throughput, backfill projection, char-count percentiles p10–p95) and `cumulative.png`.

## Documentation Tree

- [engine/DOCS.md](engine/DOCS.md) — scrape / dedup / engine modules
- [platforms/coindesk/DOCS.md](platforms/coindesk/DOCS.md) — CoinDesk platform implementation
- [platforms/theblock/DOCS.md](platforms/theblock/DOCS.md) — The Block platform implementation
