# dev/news_pipeline/coindesk_proxy_riding/

## Role

Standalone dev suite for scraping CoinDesk article HTML at scale via rotating proxies.
Architecture: 128-wide `curl_cffi` alive-feeder continuously validates proxies against CoinDesk → feeds browser-eligible ones (http/socks5) to a pool of up to 20 Playwright browser slots. Each slot binds one proxy and rides the URL queue; a fresh Playwright BrowserContext is forced per URL via `session_id` + `kill_session()` (proxy and browser process stay alive). Regwall detection runs on `result.markdown.raw_markdown` (not raw HTML — REGWALL_SIGNALS are hidden React components always present in HTML). A proxy is burned and rotated when cumulative regwall hits reach the burn threshold.

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

---

### p1_alive_feeder.py (283 LOC)

**Purpose:** Background asyncio task: validates proxies 128-wide via `curl_cffi` HTTP-200 check against rotating CoinDesk test URLs; feeds browser-eligible (http/socks5) proxies into an `asyncio.Queue`.
**Key constants:** `ALIVE_CONCURRENCY=128`, `FEEDER_QUEUE_MAXSIZE=40`, `BROWSER_ELIGIBLE_PROTOS={"http","socks5"}` (socks4 excluded — Playwright unreliable).
**Alive-check note:** HTTP 200 only; no regwall check — REGWALL_SIGNALS fire on ALL CoinDesk pages in raw HTML.
**Exports:** `AliveFeeder`, `FEEDER_QUEUE_MAXSIZE`, `FeederStats`

---

### p2_browser_rider.py (395 LOC)

**Purpose:** Core riding pool — `n_slots` asyncio tasks each bind one proxy, fetch URLs via crawl4ai/Playwright, detect regwall on rendered markdown, write raw HTML to disk.
**Key:** `session_id` + `kill_session()` per URL → fresh BrowserContext (cookies reset) while browser process and proxy stay alive. `page_timeout=12_000ms` is the dead-proxy timeout lever.
**Status routing:** ok → write HTML; regwall → requeue URL (up to `MAX_URL_RETRIES=3`), increment burn_count; connect_fail → requeue URL, rotate proxy immediately; failed/empty → drop.
**Exports:** `run_riding_pool()`, `RiderState`, `RideRecord`, `JobRecord`

---

### p3_url_sampler.py (129 LOC)

**Purpose:** Proportional 500-URL sampler from CoinDesk inventory shards (2017–2026); floor 5 URLs/year. Resolves `data/news/coindesk/inventory/` from main repo root via `git rev-parse --git-common-dir` (works inside worktrees).
**Exports:** `sample_urls(n_total, seed)`

---

### p4_reporter.py (339 LOC)

**Purpose:** Generates `job.md` + 3 plots from a completed `RiderState`.
**Metrics:** counts/throughput/61k-backfill projection; HTML size percentiles (`char_count = len(result.html)`); markdown length percentiles (`markdown_len` — body-level truncation signal); proxy churn + 61k estimate; ride-length distribution; regwall-position curve; retry outcomes; wasted-fetch ratio.
**Exports:** `write_riding_report(state, job_dir, t_job_start)`

---

### run_coindesk_riding.py (82 LOC)

**Purpose:** CLI orchestrator — wires `AliveFeeder` + `run_riding_pool` + `write_riding_report` end-to-end; handles feeder teardown on completion.
**Entry point:** `__main__` via `asyncio.run(_run(_parse_args()))`.
