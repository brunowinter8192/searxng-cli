# searxng/

## Role

CLI-driven web research toolkit for Claude Code. Runs a parallel 9-engine search pipeline (5 pydoll Chrome + 4 httpx HTTP), a multi-phase scraper (httpx fastpath → Crawl4AI browser → stealth fallback) with garbage detection and per-URL logging, and a sitemap/BFS site-discovery crawler. Plugin-routed domains (arxiv, github, reddit, youtube) are blocked at scrape-call level and delegated to external MCP plugins. All capabilities exposed via a single `cli.py` entry-point; no MCP server in this repo.

## Entry Points

- `cli.py` → argparse dispatch for 7 CLI commands: `search_web`, `search_engine_drilldown`, `scrape_url`, `scrape_url_raw`, `download_pdf`, `explore_site`, `filter_urls`

## Directory Map

| Subdir | Role | LOC | Modules |
|---|---|---|---|
| `src/search/` | parallel search pipeline (fan-out, dedup, pool cache) | 2595 | 14 |
| `src/scraper/` | scrape + download (fastpath, browser, stealth, logging) | 1101 | 7 |
| `src/crawler/` | sitemap + BFS discovery, URL filtering | 551 | 4 |

## Root-Level Files

| File | LOC | Why at root |
|---|---|---|
| `cli.py` | 227 | CLI entry-point (argparse dispatch) |
| `README.md` | 97 | external-facing project overview |
| `requirements.txt` | 9 | Python dependencies |
| `.env.example` | 10 | env var reference (log paths, etc.) |

## Documentation Tree

- [src/DOCS.md](src/DOCS.md) — package overview + shared-state map
- [src/search/DOCS.md](src/search/DOCS.md) — search engines + workflows
- [src/scraper/DOCS.md](src/scraper/DOCS.md) — scrape pipeline modules
- [src/crawler/DOCS.md](src/crawler/DOCS.md) — discovery + crawl modules
- [decisions/](decisions/) — pipeline decisions (7 IST files); history in `decisions/OldThemes/`
- [dev/DOCS.md](dev/DOCS.md) — dev suites (search pipeline, scrape pipeline evals)
