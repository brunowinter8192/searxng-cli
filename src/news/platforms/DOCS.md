# src/news/platforms/

## Role

Namespace package holding one subdirectory per news source, each implementing the `Platform` Protocol (defined in `src/news/platform.py`). No logic lives directly at this level — this directory only groups platform packages. Touch this level only when adding a brand-new platform directory; touch the platform subdirectory itself to change that platform's discovery/cleanup behavior.

## Public Interface

`__init__.py` is empty (0 LOC). Entry is via `src.news.platforms.<name>` — each platform subpackage's own `__init__.py` registers its `Platform` implementation into the registry as a side effect of being imported by `src/news/__main__.py`.

## Directory Structure

- `coindesk/` — CoinDesk platform implementation (own `DOCS.md`).
- `theblock/` — The Block platform implementation (own `DOCS.md`).

## Flow

`__main__.py` imports a platform subpackage for its registration side-effect → subpackage's `__init__.py` instantiates its `Platform` class and calls `register(instance)` → `src/news/pipeline.py` looks up the platform by `--source` name via the registry and drives discover → dedup → scrape → (clean-pass, if `proxy_pool` engine) → publish.
