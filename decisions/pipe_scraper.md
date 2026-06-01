# decisions/pipe_scraper.md — Pipe-Scraper Configuration

Covers `src/crawler/pipe_scraper.py` — the production capture-pipeline scrape step.  
Separate from `decisions/scrape_pipeline.md` (filter/garbage/browser config for the ad-hoc CLI scraper).

**Note:** `crawl_urls()` in `src/crawler/crawl_site.py` is out of scope here — it serves the BFS-discovery workflow (`crawl_site_workflow`) and is unchanged.

## Status Quo (IST)

`scrape_urls_workflow()` in `src/crawler/pipe_scraper.py`:

Pacing model based on Scrapy (`scrapy/core/downloader`: per-domain delay-gate + RANDOMIZE_DOWNLOAD_DELAY jitter + CONCURRENT_REQUESTS_PER_DOMAIN cap — Scrapy config keys, not local symbols), retry/backoff disabled for determinism. `DOWNLOAD_DELAY=1.0s` → ~1 req/s start rate per domain = proven-safe (old batch config averaged ~1 req/s, 0×429).

| Parameter | Value |
|---|---|
| `wait_until` | `"domcontentloaded"` |
| `delay_before_return_html` | `0.5s` (`DELAY_BEFORE_RETURN_HTML`) |
| `page_timeout` | `15000ms` (`PAGE_TIMEOUT_MS`) |
| `DOWNLOAD_DELAY` | `1.0s` base; actual jitter = `random.uniform(0.5×, 1.5×)` per request |
| `CONCURRENCY_PER_DOMAIN` | `8` (per-domain in-flight cap; dormant at ~1s gate — ~2 in flight at p50 latency 1.8s) |
| markdown | `DefaultMarkdownGenerator()` raw (no `PruningContentFilter`) |
| garbage-drop | none — saves every page (content completeness is scraper's job) |
| retry / backoff / autothrottle | OFF — determinism constraint |

Pacing gate (Scrapy-equivalent, per domain, in `_gate_domain`):
- `lastseen` = timestamp when last request to that domain was **started** (not completed)
- Next request may start only when `now - lastseen >= jitter`; if not, sleeps remainder
- `asyncio.Lock()` per domain serializes starts; `asyncio.Semaphore(8)` per domain caps in-flight
- `domain` key = `urlparse(url).netloc` → mixed-domain lists pace each host independently

Output contract:
- Per-URL raw markdown → `--output-dir`, each file with `<!-- source: URL -->` header
- Short console line: `Scraped N/M ok, K errors in Xs`
- Full per-URL report → `/tmp/<domain>_scrape_report.md` (outcome / status / bytes / wall_ms per URL)
- Runnable as `python -m src.crawler.pipe_scraper --url-file <list> --output-dir <dir>`
- CLI flags `--download-delay` / `--concurrency-per-domain` allow WAF-rate tuning without code changes

`scrape_urls_workflow()` also importable — capture-and-index skill Phase 2 calls it directly.

## Evidenz

### Phase 1–3 — Concurrency, Delay, Full-Run Sweeps (old batch/sleep config)

See `decisions/OldThemes/pipe_scraper_time_levers.md` — historical eval establishing WAF characterization and the ~1 req/s safe rate. Batch pacing (batch_size=30, inter_batch_sleep=30s) superseded by Scrapy-style gate.

### Validation — Scrapy-style gate on 316 URLs

Dataset: `dev/explore_pipeline/06_discovered_urls.txt` (316 `docs.github.com/de/rest` URLs)  
Script: `python -m src.crawler.pipe_scraper --url-file dev/explore_pipeline/06_discovered_urls.txt --output-dir /tmp/pipe_scrapy_verify`  
Config: `DOWNLOAD_DELAY=1.0`, `CONCURRENCY_PER_DOMAIN=8`, `delay_before_return_html=0.5s`, `page_timeout=15000ms`

| Metric | Value |
|---|---|
| Success (ok) | 316/316 |
| WAF 429 | 0 |
| Empty | 0 |
| Errors | 0 |
| Wallclock | 319s |
| vs. old batch config (438s) | −119s (−27%) |

**Finding:** Scrapy-style gate holds 100% capture, 0 WAF hits, and is 27% faster than the old batch-stop-and-go (no dead 30s pauses). Gate rate (~1 req/s start) matches the rate the old config achieved, but evenly paced instead of burst+pause.

### WAF characterization (from Phase 1+2 sweeps)

The WAF is NOT a pure concurrency cap. It is a rate/burst budget over time with a likely repeat-access heuristic:
- One 30-URL burst at c=5 in ~8s (3.75 req/s) exhausts the budget
- Budget recovery requires minutes, not seconds
- c=10 → 20×429, c=5 = WAF-safe ceiling
- ~1 req/s sustained = fully safe

## Recommendation (SOLL)

**Keep** — IST = SOLL. Scrapy-style gate validated at full scale (316/316, 0×429, 319s).

## Offene Fragen

- Is `delay_s=0.5` (delay_before_return_html) sufficient for client-side-rendered (CSR) sites? Proven for Next.js SSR; heavy CSR may need more.
- What pacing parameters are appropriate for other target hosts (SearXNG result sites vary in WAF aggressiveness)?

## Quellen

- `decisions/OldThemes/pipe_scraper_time_levers.md` — Phase 1/2/3 sweep history + old batch config
- Scrapy source reference: `scrapy/core/downloader/__init__.py` (per-domain slot, delay gate, RANDOMIZE_DOWNLOAD_DELAY, CONCURRENT_REQUESTS_PER_DOMAIN)
