# Plugin Routing

## Status Quo (IST)

**No domain blocking.** `scrape_url` and `scrape_url_raw` attempt to scrape any URL without restriction. `src/routing.py` and `check_plugin_routed()` have been deleted. The `elif blocked := check_plugin_routed(...)` guards in `cli.py` (scrape_url and scrape_url_raw handlers) have been removed. `get_plugin_hint()` in `src/scraper/scrape_url.py` returns `""` unconditionally.

**PDF routing is unchanged:** `should_download_as_pdf()` still routes `.pdf`-suffix and TIER1 academic domain URLs to `download_pdf`. See `decisions/scrape_pipeline.md`.

**Previously blocked domains** (github.com, raw.githubusercontent.com, reddit.com, arxiv.org, youtube.com, youtu.be) are now scraped like any other domain.

## Evidenz

**Root cause of removal:**

1. **docs.github.com wrongly blocked.** The `host.endswith(".github.com")` subdomain branch caught rendered documentation pages on `docs.github.com`. The GitHub plugin (`get_file_content`) is for raw repo-file access only — it cannot serve rendered HTML docs. Blocking docs.github.com left no valid access path.

2. **Plugin availability ≠ scrape incompatibility.** The existence of a plugin for github/reddit/arxiv does not mean scraping is broken. Workers should choose the best tool per URL shape; a hard CLI-level block prevents informed choice.

3. **Product decision:** unrestricted scraping is the correct default. Plugin tools remain available and are often superior for their specific use cases (structured data, auth, large files), but the scraper must not preempt the choice.

## Recommendation (SOLL)

Blocking removed, no change needed.

If a future need arises to guide tool selection for specific domains, the appropriate mechanism is SKILL.md guidance (prose recommendations, not CLI enforcement).

## Offene Fragen

None — prior questions about huggingface.co, gist.github.com, and paperswithcode.com routing are moot given unrestricted scraping.

## Quellen

- `decisions/scrape_pipeline.md` — PDF routing chain (unchanged)
