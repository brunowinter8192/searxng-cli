# src/news/

## Role

Multi-platform news ingestion pipeline. Runs as `python -m src.news --source <platform>`.
Discovers articles, deduplicates against the RAG collection, scrapes raw markdown, cleans to
pure body, and publishes to the RAG collection via `rag-cli index`.

Touch this package when adding a new news source or changing pipeline orchestration.
Do NOT import from `src/crawler/` or `src/scraper/` — `src/news/` is self-contained.

## Entry Points

- `python -m src.news --source coindesk [--skip-index]`
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
    scrape_config: ScrapeConfig

    async def discover(self) -> list[dict]: ...         # [{url,lastmod,publication_date,title,section}]
    def cleanup(self, raw_markdown: str, entry: dict) -> str: ...   # -> pure body
```

## Directory Map

| Path | Role | LOC |
|---|---|---|
| `platform.py` | ScrapeConfig dataclass + Platform Protocol | 25 |
| `registry.py` | name → Platform registry; register() / get() | 19 |
| `pipeline.py` | Async orchestrator; stages 1–5 in-process | 205 |
| `__main__.py` | argparse entry point; --source + --skip-index | 35 |
| `engine/` | Generic scrape / dedup / publish modules | — |
| `platforms/coindesk/` | CoinDesk platform implementation | — |

## Flow

1. **discover** — `platform.discover()` → entry list `[{url, lastmod, publication_date, title, section}]`; JSON snapshot written to `data/news/{name}/discover/`.
2. **dedup** — `filter_new_entries()` checks the external rag-cli collection dir (`COLLECTION_BASE` in `pipeline.py` — an absolute path into the rag-cli project, joined with `platform.collection`) for `{name}__{date}__{hash}.md`; drops already-indexed URLs.
3. **scrape** — `scrape_entries()` — fresh `AsyncWebCrawler` per URL, concurrent, Scrapy gate pacing. Writes raw body to `data/news/{name}/scrape/{hash}.md`. Raises `RegwallGuardError` if fraction regwalled ≥ 20%.
4. **cleanup** — `platform.cleanup(body, entry)` in-process for each status=ok entry. Writes pure content (NO frontmatter) to `data/news/{name}/clean/{hash}.md`.
5. **publish** — `publish_articles()` copies clean files to RAG collection dir as `{name}__{pubdate}__{hash}.md`; runs `rag-cli index --collection {collection}` unless `--skip-index`.

## Documentation Tree

- [engine/DOCS.md](engine/DOCS.md) — scrape / dedup / publish engine modules
- [platforms/coindesk/DOCS.md](platforms/coindesk/DOCS.md) — CoinDesk platform implementation
