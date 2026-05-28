# Plugin Routing

## Status Quo (IST)

**Code:** `skills/web-research/SKILL.md` (Plugin Routing section), `src/routing.py` (`check_plugin_routed()` — enforced at CLI level)

**Routing table** (applied to all search results before scraping):

| Domain | Action | Plugin |
|--------|--------|--------|
| arxiv.org | Report: "USE RAG PLUGIN" | `mcp__rag__search_hybrid` or `/rag:pdf-convert` |
| github.com | Report: "USE GITHUB PLUGIN" | `github__get_file_content` |
| raw.githubusercontent.com | Report: "USE GITHUB PLUGIN" | `github__get_file_content` |
| reddit.com | Report: "USE REDDIT PLUGIN" | `reddit__search_posts` |
| youtube.com | SKIP entirely | — (video content not scrapable) |
| youtu.be | SKIP entirely | — (video content not scrapable) |

**Routing logic:** URL-domain matching only. No content-based routing. No subdomain handling documented.

**Worker output:** When a `searxng-cli scrape_url <url>` call hits a routed domain, `check_plugin_routed()` returns a blocking TextContent with the routing message. The worker reports these in the "Plugin-Routed URLs" section of its output.

**PDF routing:** PDF URLs (`.pdf` suffix or TIER1 academic domains) are routed to `download_pdf` via `should_download_as_pdf()`. See `decisions/scrape_pipeline.md` for the chain logic.

## Evidenz

Routing logic is enforced at every CLI scrape call via `check_plugin_routed()`. The function returns a blocking TextContent (consumed by CLI) when the host matches a routed domain (host equality OR subdomain match via `host.endswith`).

## Recommendation (SOLL)

Plugin routing is the best-functioning part of the agent pipeline. No change needed.

The routing table is correct: arxiv/github/reddit all have dedicated plugins that provide better access than scraping (structured metadata, full content, no auth issues). youtube skip is correct (no scraping value).

One gap: no routing for `huggingface.co` (model cards, papers with code — frequently appears in ML research). Currently scraped like any other domain; scraper may hit rate limits or return incomplete model card content.

## Offene Fragen

- Should `huggingface.co` be added to the routing table? HF has no dedicated plugin currently, so it would need to either: (a) be scraped as normal, (b) be skipped, or (c) be noted for future plugin development.
- What about `paperswithcode.com`? Frequently surfaces in ML benchmarks. No dedicated plugin, but content is structured and scrapable.
- Subdomain handling: does `gist.github.com` match the `github.com` routing rule? If not, gists get scraped instead of plugin-routed.
- ~~Should the routing table be duplicated in `agents/web-research.md`?~~ → Resolved: `agents/web-research.md` removed. Canonical: `skills/web-research/SKILL.md`. `src/routing.py` enforces at runtime.

## Quellen

- `skills/web-research/SKILL.md` — Plugin Routing section (canonical reference)
- `src/routing.py` — `check_plugin_routed()` implementation
- HuggingFace API Docs — Model Card, Datasets API: https://huggingface.co/docs/hub/api
- arxiv API Docs — Bulk metadata access: https://info.arxiv.org/help/api/index.html
