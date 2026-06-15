# src/news/

## Role

Multi-platform news ingestion pipeline. Runs as `python -m src.news --source <platform>`.
Discovers articles, deduplicates against the RAG collection, scrapes raw markdown, cleans to
pure body, and publishes to the RAG collection via `rag-cli index`.

Touch this package when adding a new news source or changing pipeline orchestration.
Do NOT import from `src/crawler/` or `src/scraper/` — `src/news/` is self-contained.

## Entry Points

- `python -m src.news --source coindesk [--skip-index]`
- `python -m src.news --source theblock [--timeframe 48h|full|YYYY-MM-DD:YYYY-MM-DD] [--skip-index]`
- Direct: `asyncio.run(run_pipeline(platform, skip_index=...))` after importing a platform

## Platform Contract (Extension Seam)

To add a new platform:
1. Create `src/news/platforms/<name>/` with `__init__.py` that defines a class implementing `Platform`
   and calls `register(instance)` at import time.
2. Import the platform module in `__main__.py` for side-effect registration.

```python
# Platform Protocol (platform.py)
class Platform(Protocol):
    name: str                   # --source value AND filename prefix f"{name}__"
    collection: str             # target RAG collection name
    precondition_url: str       # internet-check URL
    regwall_signals: list[str]  # precise strings; [] = guard disabled
    scrape_engine: str          # "browser" | "proxy_pool" — dispatch key in pipeline.py
    scrape_config: ScrapeConfig # browser engine params; ignored for proxy_pool platforms
    proxy_scrape_config: ProxyScrapeConfig | None  # None for browser platforms

    async def discover(self) -> list[dict]: ...         # [{url,lastmod,publication_date,title,section}]
    def cleanup(self, raw_markdown: str, entry: dict) -> str: ...   # -> pure body

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
- `dedup_mode: str` — `"pubdate"` (default, CoinDesk) | `"hash_only"` (The Block).
  `"hash_only"` globs `{source}__*__{hash}.md` instead of exact pubdate match; needed when
  `publication_date` is not available at discover time.
- `timeframe: str` — discovery window; set by `__main__` from `--timeframe` (default `"48h"`).
  Only meaningful for platforms whose `discover()` reads `self.timeframe` (e.g. The Block).

## Directory Map

| Path | Role | LOC |
|---|---|---|
| `platform.py` | ScrapeConfig + ProxyScrapeConfig + Platform Protocol | 35 |
| `registry.py` | name → Platform registry; register() / get() | 19 |
| `pipeline.py` | Async orchestrator; stages 1–5 in-process; scrape dispatch | 213 |
| `__main__.py` | argparse entry point; --source + --skip-index + --timeframe | 43 |
| `engine/` | Generic scrape engines (browser + proxy_pool) + dedup + publish | — |
| `platforms/coindesk/` | CoinDesk platform implementation | — |
| `platforms/theblock/` | The Block platform — proxy_pool, hash-dedup, JSON-LD cleanup | — |

## Flow

1. **discover** — `platform.discover()` → entry list `[{url, lastmod, publication_date, title, section}]`; JSON snapshot written to `data/news/{name}/discover/`.
2. **dedup** — `dedup_mode = getattr(platform, "dedup_mode", "pubdate")`; `filter_new_entries()` checks the external rag-cli collection dir (`COLLECTION_BASE` in `pipeline.py` — an absolute path into the rag-cli project, joined with `platform.collection`):
   - `"pubdate"` (default, CoinDesk): exact match `{name}__{pubdate}__{hash}.md`.
   - `"hash_only"` (The Block): glob `{name}__*__{hash}.md` — skips pubdate since it's not known at discover time.
3. **scrape** — dispatch on `platform.scrape_engine`:
   - `"browser"` → `scrape_entries()` — fresh `AsyncWebCrawler` per URL, Scrapy gate pacing. Writes raw body to `data/news/{name}/scrape/{hash}.md`. Raises `RegwallGuardError` if fraction regwalled ≥ 20%.
   - `"proxy_pool"` → `scrape_entries_proxy()` — sustained proxy rotation via `run_loop`, curl_cffi chrome impersonation. Box-locked (one job at a time). Writes raw body to `data/news/{name}/scrape/{hash}.md`.
4. **cleanup** — `platform.cleanup(body, entry)` in-process for each status=ok entry. Writes pure content (NO frontmatter) to `data/news/{name}/clean/{hash}.md`. `entry` is the scrape manifest dict; platforms that cannot set `publication_date` at discover time (e.g. The Block) mutate `entry["publication_date"]` here. `_run_cleanup` picks it up as fallback: `discover_entry.get("publication_date") or entry.get("publication_date", "")`.
5. **publish** — `publish_articles()` copies clean files to RAG collection dir as `{name}__{pubdate}__{hash}.md`; runs `rag-cli index --collection {collection}` unless `--skip-index`.

## Documentation Tree

- [engine/DOCS.md](engine/DOCS.md) — scrape / dedup / publish engine modules
- [platforms/coindesk/DOCS.md](platforms/coindesk/DOCS.md) — CoinDesk platform implementation
- [platforms/theblock/DOCS.md](platforms/theblock/DOCS.md) — The Block platform implementation
