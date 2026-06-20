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
| `--stall-timeout` | 3600 | Stall watchdog threshold in seconds — watchdog fires `os._exit(1)` after this many seconds with no new raw file written; set small (e.g. 25) for smoke tests |

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

### p2_browser_rider.py (498 LOC)

**Purpose:** Core riding pool — B `AsyncWebCrawler` instances (browser pool, default B=1); N rider tasks distributed round-robin across browsers. Each task pulls raw proxies via `_next_proxy()` (atomic cursor over `eligible_candidates()`). Per-URL: `CrawlerRunConfig(proxy_config=ProxyConfig(server=pstr))` → fresh context per config-signature; `kill_session()` closes context after each fetch (fresh cookies). `page_timeout_ms` (CLI-configurable, default 8s) is the dead-proxy timeout lever.
**Status routing:** ok → write HTML; regwall → requeue URL, increment burn_count, rotate after `burn_threshold` hits; connect_fail → requeue URL, rotate proxy immediately; failed/empty → requeue URL, increment fail_count, rotate after `FAIL_THRESHOLD=2` hits (2-strike drop) — ride ends, `finally` calls `mark_burned()` → 60-min cooldown.
**Watchdog:** `_watchdog(state, output_dir)` asyncio task created in `run_riding_pool`, cancelled when slots return normally. Polls via `asyncio.sleep(min(30, stall_timeout_s/4))` — timer-based, fires regardless of wedged slot I/O. On `60min` (configurable via `stall_timeout_s`) with no new raw written → `_abort_stall`: drain queue + `in_flight_urls` → `remaining_urls.txt` (two sections: `# never attempted (queue)` / `# in-flight / wedged at abort`) + `job.md` via reporter → `os._exit(1)` (bypasses async teardown so wedged Chrome processes cannot re-hang shutdown).
**`RiderState.in_flight_urls`:** set tracking currently-fetching URLs. `add(url)` immediately after `in_flight += 1`; `discard(url)` immediately after `in_flight -= 1`. NOT in try/finally — wedged slots never reach the discard, keeping the wedged URL in the set until abort (the diagnostically valuable capture).
**`RiderState.t_job_start`:** `datetime` field (default factory `datetime.now(utc)`), used by `_abort_stall` when calling the reporter without access to the outer scope start time.
**Exports:** `run_riding_pool(n_browsers=1, stall_timeout_s=3600)`, `RiderState`, `RideRecord`, `JobRecord`, `FAIL_THRESHOLD`, `_watchdog`, `_abort_stall`

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

### run_coindesk_riding.py (115 LOC)

**Purpose:** CLI orchestrator — loads pool via `load_backfill_pool()`, wires `run_riding_pool` + `write_riding_report` end-to-end; raises `RLIMIT_NOFILE` at startup.
**Entry point:** `__main__` via `asyncio.run(_run(_parse_args()))`.

---

### analyze_write_times.py (258 LOC)

**Purpose:** Reconstructs proxy-riding throughput from `raw/*.html` file mtimes. Used when
`job.md`/`cumulative.png` are missing (manual abort before fix, or any crash that skips the report
write). Reads mtime of every `.html` in `--raw-dir`, optionally filters to a `--since` cutoff
(needed when `raw/` is a cumulative dedup corpus spanning multiple runs), then plots cumulative OK
fetches over time (top) and per-bin rate + rolling mean + 30-min pool-refresh markers (bottom).

**Usage:**
```bash
# All files in default raw dir (cumulative corpus):
./venv/bin/python dev/news_pipeline/coindesk_proxy_riding/analyze_write_times.py

# Isolate a single run by local start time (recommended when raw/ spans multiple runs):
./venv/bin/python dev/news_pipeline/coindesk_proxy_riding/analyze_write_times.py \
    --since '2026-06-20 03:45'

# Custom bin width and smoothing:
./venv/bin/python dev/news_pipeline/coindesk_proxy_riding/analyze_write_times.py \
    --since '2026-06-20 03:45' --bin-minutes 2 --rolling 10
```

**CLI Flags:**

| Flag | Default | Description |
|---|---|---|
| `--raw-dir` | `data/news/coindesk/raw` | Directory of `*.html` files (resolved from repo root via `git rev-parse --git-common-dir`) |
| `--bin-minutes` | `1` | Bin width for the rate histogram in minutes |
| `--rolling` | `5` | Rolling-mean window in bins (overlaid on rate bars) |
| `--since` | `None` | Local timestamp `'YYYY-MM-DD HH:MM'` — exclude mtimes before this cutoff; use to isolate one run from a shared raw/ corpus |

**Output:**
- PNG → `dev/news_pipeline/coindesk_proxy_riding/01_reports/raw_write_times_<YYYYMMDD>[_since<stamp>].png`
- Stdout: filter summary (files before/after cutoff), Files, Span (local timezone), Mean rate, Median rate (non-zero bins only), Longest gap between consecutive writes.

---

### test_watchdog.py (159 LOC)

**Purpose:** Deterministic watchdog verification — no browser or proxy infrastructure needed.
**Tests:**
- `test_watchdog_task_fires_and_writes_files`: constructs `RiderState` with `last_progress_mono` aged 200 s past a 1 s threshold + 2 queued + 1 in-flight URL; patches `os._exit` → `SystemExit(code)`; runs `_watchdog(poll_interval=0.1)`; asserts `os._exit(1)` called, `remaining_urls.txt` has both section headers + all 3 URLs, `job.md` exists with `stall`.
- `test_abort_stall_directly`: same assertions via direct `_abort_stall(idle_s=999.0)` call; also checks `"999"` in the header line.

**Usage:**
```bash
./venv/bin/python dev/news_pipeline/coindesk_proxy_riding/test_watchdog.py
```
