# searxng/

## Role

CLI-driven web research toolkit for Claude Code. Runs a parallel 9-engine search pipeline (5 pydoll Chrome + 4 httpx HTTP), a multi-phase scraper (httpx fastpath → Crawl4AI browser → stealth fallback) with garbage detection and per-URL logging, a BFS site-discovery crawler for offline doc indexing, and a multi-platform news ingestion pipeline (discover → dedup → scrape → clean → publish to a RAG collection). Search, scrape, and crawl are exposed via a single `cli.py` entry-point; news ingestion runs via `python -m src.news`. No MCP server in this repo.

## Entry Points

- `cli.py` → argparse dispatch for 4 CLI commands: `search_web`, `search_engine_drilldown`, `scrape_url`, `download_pdf`
- `python -m src.news --source <platform>` → news ingestion pipeline (separate entry point, not via `cli.py`)

## Directory Map

| Subdir | Role | LOC | Modules |
|---|---|---|---|
| `src/search/` | parallel search pipeline (fan-out, dedup, pool cache) | 2595 | 14 |
| `src/scraper/` | scrape + download (fastpath, browser, stealth, logging) | 859 | 6 |
| `src/crawler/` | BFS discovery + capture-pipe scrape step | 484 | 2 |
| `src/news/` | multi-platform news ingestion → RAG (discover, dedup, scrape, clean, publish) | 1132 | 11 |

## Root-Level Files

| File | LOC | Why at root |
|---|---|---|
| `cli.py` | 134 | CLI entry-point (argparse dispatch) |
| `README.md` | 97 | external-facing project overview |
| `requirements.txt` | 9 | Python dependencies |
| `.env.example` | 10 | env var reference (log paths, etc.) |

## Documentation Tree

- [src/DOCS.md](src/DOCS.md) — package overview + shared-state map
- [src/search/DOCS.md](src/search/DOCS.md) — search engines + workflows
- [src/scraper/DOCS.md](src/scraper/DOCS.md) — scrape pipeline modules
- [src/crawler/DOCS.md](src/crawler/DOCS.md) — discovery + crawl modules
- [src/news/DOCS.md](src/news/DOCS.md) — multi-platform news ingestion pipeline + platform extension seam
- [decisions/](decisions/) — pipeline decisions (7 IST files); history in `decisions/OldThemes/`
- [dev/DOCS.md](dev/DOCS.md) — dev suites (search pipeline, scrape pipeline evals)
