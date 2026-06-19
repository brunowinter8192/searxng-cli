# dev/news_pipeline/coindesk_proxy_riding/

## Role

Standalone dev suite for scraping CoinDesk article HTML at scale via rotating proxies.
Architecture: B Playwright browser processes (pool, default B=1); N concurrent rider tasks (default 20) distributed round-robin across the B browsers (slot i → browsers[i % B]). Each task pulls raw proxies directly from the pool (no pre-validation). Each URL fetch uses `CrawlerRunConfig(proxy_config=ProxyConfig(server=...))` → fresh Playwright BrowserContext per proxy via crawl4ai's config-signature mechanism + `session_id` + `kill_session()` (fresh cookies per URL, browser stays alive). Regwall detection on `result.markdown.raw_markdown` (not raw HTML — REGWALL_SIGNALS are hidden React components always present in HTML). A proxy is burned and rotated when cumulative regwall hits reach the burn threshold.

Self-contained: no imports from `src/`. `p0_pool.py` is a local copy of the proxy pool machinery.

## Usage

```bash
# From repo root (via worktree):
.claude/worktrees/coindesk-riding/venv/bin/python \
  dev/news_pipeline/coindesk_proxy_riding/run_coindesk_riding.py \
  --n-urls 500 --concurrency 20 --burn-threshold 2 \
  --output-dir data/news/coindesk/riding_output

# Quick smoke (10 URLs, 4 slots):
./venv/bin/python dev/news_pipeline/coindesk_proxy_riding/run_coindesk_riding.py \
  --n-urls 10 --concurrency 4 --output-dir /tmp/riding_smoke
```

## CLI Flags (run_coindesk_riding.py)

| Flag | Default | Description |
|---|---|---|
| `--n-urls` | 500 | URLs to scrape (sampled proportionally across 2017–2026; floor 5/year → actual minimum is 50) |
| `--concurrency` | 20 | Parallel browser slots |
| `--burn-threshold` | 2 | Cumulative regwall hits per proxy before rotation |
| `--output-dir` | `output` | Directory for raw HTML and report |
| `--page-timeout` | 8000 | Playwright page timeout ms (dead proxies hit this before rotating) |
| `--browsers` | 1 | Browser pool size — B separate Chromium processes, N slots spread across them (slot i → browsers[i % B]) |

## Expected Output

```
<output-dir>/
  raw/
    <12-char-sha256-hash>.html   # one per ok URL; full result.html (~300–600 KB)
  job.md                         # counts, throughput, char distributions, proxy stats
  cumulative.png                 # cumulative OK fetches over time
  ride_lengths.png               # histogram: URLs attempted per proxy ride
  regwall_position.png           # regwall rate vs ride position within a proxy
```

## Modules

### p0_pool.py (221 LOC)

**Purpose:** Local copy of proxy pool machinery — loaders, cooldown manager, retry helper.
**Exports:** `load_backfill_pool()`, `PersistentCooldownManager`, `proxy_key()`, `fetch_with_retry()`
**Why local:** hookify blocks `from src.` imports in dev/ scripts.

### p2_browser_rider.py (404 LOC)

**Purpose:** Core riding pool — B `AsyncWebCrawler` instances (browser pool, default B=1); N rider tasks distributed round-robin across browsers. Each task pulls raw proxies via `_next_proxy()` (atomic cursor over `eligible_candidates()`). Per-URL: `CrawlerRunConfig(proxy_config=ProxyConfig(server=pstr))` → fresh context per config-signature; `kill_session()` closes context after each fetch (fresh cookies). `page_timeout_ms` (CLI-configurable, default 8s) is the dead-proxy timeout lever.
**Status routing:** ok → write HTML; regwall → requeue URL, increment burn_count, rotate after `burn_threshold` hits; connect_fail → requeue URL, rotate proxy immediately; failed/empty → requeue URL, increment fail_count, rotate after `FAIL_THRESHOLD=2` hits (2-strike drop) — ride ends, `finally` calls `mark_burned()` → 60-min cooldown.
**Exports:** `run_riding_pool(n_browsers=1)`, `RiderState`, `RideRecord`, `JobRecord`, `FAIL_THRESHOLD`

---

### p3_url_sampler.py (129 LOC)

**Purpose:** Proportional 500-URL sampler from CoinDesk inventory shards (2017–2026); floor 5 URLs/year. Resolves `data/news/coindesk/inventory/` from main repo root via `git rev-parse --git-common-dir` (works inside worktrees).
**Exports:** `sample_urls(n_total, seed)`

---

### p4_reporter.py (344 LOC)

**Purpose:** Generates `job.md` + 3 plots from a completed `RiderState`.
**Metrics:** counts/throughput/61k-backfill projection; HTML size percentiles (`char_count = len(result.html)`); markdown length percentiles (`markdown_len` — body-level truncation signal); proxy churn + 61k estimate; ride-length distribution; regwall-position curve; retry outcomes; wasted-fetch ratio. Counts table includes `Browsers` and `Contexts/browser` (`n_slots // n_browsers`) for self-documenting runs.
**Exports:** `write_riding_report(state, job_dir, t_job_start)`

---

### run_coindesk_riding.py (113 LOC)

**Purpose:** CLI orchestrator — loads pool via `load_backfill_pool()`, wires `run_riding_pool` + `write_riding_report` end-to-end; raises `RLIMIT_NOFILE` at startup.
**Entry point:** `__main__` via `asyncio.run(_run(_parse_args()))`.
