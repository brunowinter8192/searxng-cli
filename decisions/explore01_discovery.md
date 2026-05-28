# Explore Pipeline Step 1: Site Discovery

## Status Quo (IST)

**Code:** `src/crawler/explore_site.py` (URL discovery, CLI entry point); `src/crawler/crawl_site.py` (BFS + sitemap functions called by explore_site); `src/crawler/filter_urls.py` (shared `match_any()` helper + `filter_urls_workflow` CLI tool)
**Method:** Cascade discovery: sitemap → prefetch BFS fallback, with shallow-sitemap threshold and redirect resolution
**Config:**

```python
DEFAULT_MAX_PAGES = 200        # in explore_site.py
SITEMAP_MIN_THRESHOLD = 5      # in explore_site.py
```

**Discovery-Kaskade (`explore_site_workflow`):**
1. `resolve_redirect(url)` — HEAD request to resolve redirect chains before discovery. Returns `(final_url, final_domain)`. Fixes discovery for URLs that redirect to different domains (e.g. `docs.anthropic.com` → `platform.claude.com`).
2. `discover_urls_sitemap(domain, include_patterns)` — Crawl4AI `AsyncUrlSeeder` mit `source="sitemap"`. Filtered via `filter_sitemap_by_seed_path()` to match seed URL's path prefix. **If `exclude_patterns` is set, `match_any()` post-filter drops matching URLs immediately after** (both `strategy=sitemap` and `strategy=auto` sitemap sub-path, before the shallow-threshold check).
3. **Shallow-sitemap threshold:** If sitemap returns `< SITEMAP_MIN_THRESHOLD` (5) URLs, also run `discover_urls()` prefetch BFS and take the larger result set.
4. **No sitemap:** Fall through to `discover_urls()` prefetch BFS only.
5. Output: text file with one URL per line + console summary.

**Post-hoc filter (`filter_urls_workflow` in `filter_urls.py`):**
- `searxng-cli filter_urls <file> --exclude-patterns "<pat>,..."` — in-place trim of a URL list file after inspection.
- `--dry-run`: prints dropped URLs + kept count to stderr, file unchanged.
- Atomic write: tmpfile + `os.replace`.
- Shared helper: `match_any(url, patterns_str) -> bool` (fnmatch.fnmatchcase, comma-split, empty-token-safe). Imported by `explore_site.py` for the sitemap-path filter.

**BFS-Konfiguration (`discover_urls` in `crawl_site.py`):**
```python
BFSDeepCrawlStrategy(
    max_depth=depth,           # CLI arg, no named constant
    include_external=False,
    filter_chain=FilterChain([
        DomainFilter(allowed_domains=[domain]),
        ContentTypeFilter(allowed_types=["text/html"]),
        URLPatternFilter(...)  # optional include/exclude
    ]),
    max_pages=max_pages,       # CLI arg, default DEFAULT_MAX_PAGES
)

CrawlerRunConfig(
    cache_mode=CacheMode.BYPASS,
    wait_until="domcontentloaded",
    prefetch=True,
)
```

## Evidenz

### Sitemap als Discovery-Quelle
Sitemap-URLs sind die vollständigste Quelle für eine Site-Struktur — vom Site-Betreiber explizit gepflegt, keine Crawl-Limitierung. `AsyncUrlSeeder` mit `source="sitemap"` prüft `/sitemap.xml` und gängige Varianten automatisch.

### Shallow-Sitemap-Schwellwert (SITEMAP_MIN_THRESHOLD = 5)
Einige Sites liefern unvollständige Sitemaps: ReadTheDocs-Sitemaps enthalten oft nur die Versions-Root-URL, Cookiebot-Sitemaps geben nur die Homepage zurück. Schwellwert 5: Sitemap mit weniger als 5 URLs → prefetch BFS ergänzend durchführen und das größere Ergebnis verwenden.

### Redirect-Auflösung vor Discovery
HEAD-Request mit `allow_redirects=True` bevor BFS-DomainFilter gesetzt wird. Ohne Redirect-Auflösung sperrt der DomainFilter alle Links auf der Redirect-Zielseite (domain mismatch). Getestet: `docs.anthropic.com` → `platform.claude.com`, `api.search.brave.com` → `api-dashboard.search.brave.com`.

### Seed-Path-Filter auf Sitemap-URLs
`filter_sitemap_by_seed_path()` filtert Sitemap-URLs auf den Pfad-Prefix der Seed-URL. Fix: `playwright.dev/python/docs` seed → Sitemap liefert `/docs/` (JS-Docs) statt `/python/docs/` → Filter hält nur URLs die den Seed-Pfad enthalten.

### Prefetch = True
`prefetch=True` in `CrawlerRunConfig` aktiviert den Crawl4AI-Prefetch-Modus: Seiten werden gecrawlt um Links zu extrahieren, ohne Full-Rendering oder Content-Extraktion. Deutlich schneller als normaler Crawl, ausreichend für Discovery-Zweck (URL-Struktur, nicht Content).

### CacheMode.BYPASS
Discovery soll aktuelle Site-Struktur zeigen, nicht gecachte Versionen. `BYPASS` stellt sicher dass jede Seite frisch gecrawlt wird.

### wait_until="domcontentloaded"
Schnellster sinnvoller Trigger — wartet auf DOM-Parse ohne JavaScript-Execution. Für reine Link-Extraktion ausreichend. JS-schwere Sites (SPAs) finden Prefetch meist nur 1 Seite → `crawl_site.py` BFS mit Full-Rendering als Fallback (strategy=bfs).

### DEFAULT_MAX_PAGES = 200
Balanciert Discovery-Vollständigkeit gegen Crawl-Zeit. 200 Seiten mit Prefetch sind in ~2-4 Minuten erreichbar. Kein Hard-Timeout im Workflow — Crawl läuft bis `max_pages` oder bis keine neuen URLs mehr gefunden werden.

## Recommendation (SOLL)

Cascade-Architektur (sitemap-first, BFS-fallback) wurde beibehalten, aber erweitert:
- Shallow-sitemap threshold: verhindert dass unvollständige Sitemaps die BFS-Discovery unterbinden
- Redirect-Auflösung: fix für häufige Redirect-Chains bei Docs-Seiten
- Seed-Path-Filter: fix für Sitemaps die mehr URLs als die Seed-Section enthalten

## Offene Fragen

- `wait_until="domcontentloaded"` reicht nicht für SPAs (React/Vue/Angular). Bei SPAs findet Prefetch meist nur 1 Seite → Strategy "bfs" korrekt, aber BFS ohne `networkidle` hilft auch nicht.
- URLPatternFilter ist optional — bei Sites mit vielen Noise-URLs (Pagination, Query-Parameter) empfehlenswert aber nicht automatisch gesetzt.
- `include_external=False` ist korrekt für Discovery, schließt aber CDN-gehostete Docs aus (z.B. assets.example.com).

## Quellen

- `src/crawler/explore_site.py` — vollständige Implementation
- `src/crawler/filter_urls.py` — `filter_urls_workflow` + `match_any()` helper
- `src/crawler/crawl_site.py` — BFS + Sitemap Discovery-Funktionen
- Crawl4AI Docs (RAG Collection: Crawl4AIDocs) — BFSDeepCrawlStrategy, CrawlerRunConfig, prefetch, AsyncUrlSeeder
- `src/crawler/DOCS.md` — Crawler-Übersicht
- Crawl4AI Deep Crawl Docs — BFS Strategy, FilterChain, max_depth: https://docs.crawl4ai.com/core/deep-crawl
- Crawl4AI GitHub Issues "sitemap" — AsyncUrlSeeder Bugs, dict-vs-string: https://github.com/unclecode/crawl4ai/issues?q=sitemap
- Sitemap Protocol Spec — XML Sitemap Format, Sitemap Index: https://www.sitemaps.org/protocol.html
