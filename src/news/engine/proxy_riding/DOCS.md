# src/news/engine/proxy_riding/

## Role

Third scrape engine: browser + rotating proxies. Purpose: defeat CoinDesk's IP-rate regwall for the
61k article-body backfill. Each URL gets a fresh crawl4ai browser context bound to a distinct proxy;
the proxy is burned after `burn_threshold` regwall hits or `FAIL_THRESHOLD` (2) failed/empty strikes
and a new one is picked from the shuffled pool. A timer-based asyncio watchdog (`_watchdog`) runs
independently of the slot tasks and hard-aborts via `os._exit(1)` if no progress occurs for
`stall_timeout_s` seconds — immune to wedged Playwright I/O.

**Active as CoinDesk's `run_scrape_only` path.** `platform.scrape_engine == "proxy_riding"` dispatched
in `pipeline.py:run_scrape_only`; `RidingScrapeConfig` consumed via `getattr` (not in Protocol);
`filter_new_entries` raw_ext reconciliation done (`.html` for riding path).

Touch this package when changing proxy-riding engine behaviour. Do NOT touch `engine/scrape.py` or
`engine/proxy_pool/` — those engines are strictly independent.

## Public Interface

`__init__.py` is empty. Entry paths:

- `scrape_entries_riding(entries, output_dir, riding_cfg, job_dir)` in `scrape.py` — async; called by
  `pipeline.py:run_scrape_only`. Returns `tuple[list[dict], RiderState]`: manifest
  `[{url, hash, status, file, char_count, error}]` + full rider state (for `write_riding_report`).
  `job_dir` is threaded to the watchdog so stall-abort writes land in `scrape_jobs/{job_id}/` (same as
  normal completion), not the platform root.
- `RidingScrapeConfig` in `scrape.py` — dataclass with production defaults
  (`n_browsers=4, n_slots=64, stall_timeout_s=300.0, burn_threshold=2, page_timeout_ms=8_000`).
- `write_riding_report(state, job_dir, t_job_start)` in `reporter.py` — called by
  `pipeline.py:run_scrape_only` (normal completion) and by `_abort_stall` (late import, stall abort).
- `run_riding_pool(url_queue, proxy_pool, cooldown_mgr, output_dir, job_dir, target_urls, …)` in `rider.py` — async;
  called by `scrape_entries_riding`.

## Flow

1. `scrape_entries_riding` builds URL queue from entries, loads pool via `load_backfill_pool()`,
   filters to `{"http","socks5"}`, shuffles, constructs `PersistentCooldownManager`.
2. `run_riding_pool` spawns B `AsyncWebCrawler` instances + N slot tasks + 1 watchdog task.
3. Each slot draws a proxy from the shuffled pool (cursor-atomic under `proxy_lock`), rides URLs
   until burn_threshold regwall or FAIL_THRESHOLD failed/empty, then rotates to the next proxy.
   **Tail-race:** when `url_queue` is empty (unresolved URLs < n_slots), slots immediately race an
   open URL (`sorted(target_urls − done_urls)[slot_id % len]`) with their current proxy — no 10 s
   wait. `asyncio.QueueEmpty` → race path; `asyncio.Queue.get_nowait()` replaces `wait_for(…, 10s)`.
4. Ok fetches write `raw/{hash}.html` guarded by first-writer check (`done_urls`); dup-race arrivals
   are discarded without write or n_ok increment. State accumulates `job_records` + `ride_records`.
5. Termination: `all_resolved = len(done_urls) >= len(target_urls)` (not queue-empty + in_flight==0).
6. `scrape_entries_riding` maps `state.job_records` → manifest via `_build_manifest`.

## Modules

### rider.py (443 LOC)

**Purpose:** Browser-per-context proxy rider pool. Manages B `AsyncWebCrawler` instances, N slot
coroutines, per-URL proxy context (`CrawlerRunConfig.proxy_config`), burn/fail rotation, watchdog.
**Reads:** URL queue (asyncio.Queue), proxy pool list, `PersistentCooldownManager` (shared state).
**Writes:** `output_dir/raw/{hash}.html` for each ok URL; `state.job_dir/job.md` on stall abort
(via `_abort_stall` — same dir as normal-completion report).
**Called by:** `scrape.py:scrape_entries_riding` (via `run_riding_pool`).
**Calls out:** `crawl4ai` (AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, ProxyConfig,
DefaultMarkdownGenerator); `src.news.engine.proxy_pool.cooldown.PersistentCooldownManager` (import);
late import of `reporter.write_riding_report` inside `_abort_stall` (avoids circular).

Key dataclasses: `RiderState` (shared mutable job state — fields: `output_dir` raw writes,
`job_dir` report writes, `target_urls` frozenset of all distinct targets, `done_urls` set of written URLs,
`pool_samples` list of `(elapsed_s, n_eligible, n_cooldown)` tuples appended by `_watchdog` each poll;
`all_resolved = len(done_urls) >= len(target_urls)`), `JobRecord` (per-URL outcome),
`RideRecord` (per-proxy-ride summary). `FAIL_THRESHOLD = 2` (failed/empty strikes before drop).

`_watchdog` captures `t0_mono = time.monotonic()` at start; each poll appends
`(elapsed_s, n_eligible, n_cooldown)` via `cooldown_mgr.eligible_candidates(proxy_pool)` +
`cooldown_mgr.cooldown_count()`. Sampling overhead: ~1–5 ms per poll on ~26k-proxy pool. Negligible.

### reporter.py (235 LOC)

**Purpose:** Job report writer — `job.md` (counts, throughput, proxy-riding stats, eligible-pool-over-time
table, regwall counts) + `cumulative.png` (step-plot of cumulative OK fetches over time).
**Reads:** `RiderState` (in-memory), `t_job_start` (datetime).
**Writes:** `{job_dir}/job.md`; `{job_dir}/cumulative.png`.
**Called by:** `pipeline.py:run_scrape_only` (normal completion, via `write_riding_report`);
`rider._abort_stall` (late import, stall abort path).
**Calls out:** `matplotlib` (lazy import inside `_write_cumulative_plot`); `statistics` (stdlib);
`src.news.engine.proxy_riding.rider` (RiderState, FAIL_THRESHOLD).

### scrape.py (108 LOC)

**Purpose:** Pipeline entry point + manifest adapter. Loads pool, shuffles, calls `run_riding_pool`,
maps `RiderState.job_records` → pipeline manifest.
**Reads:** entries list (in-memory), `RidingScrapeConfig`, proxy pool (network via `load_backfill_pool`).
**Writes:** delegates to `rider.py` (raw HTML writes to `output_dir/raw/{hash}.html`); writes nothing directly.
**Called by:** `pipeline.py:run_scrape_only` (proxy_riding dispatch arm).
**Calls out:** `src.news.engine.proxy_pool.pool_loaders.load_backfill_pool`;
`src.news.engine.proxy_pool.cooldown.PersistentCooldownManager`;
`src.news.engine.proxy_riding.rider.run_riding_pool`.

Returns `tuple[list[dict], RiderState]` — manifest + state. State is consumed by caller
(`pipeline.py`) to call `write_riding_report`; manifest is consumed to build `ok_manifest_entries`
for `_append_to_raw_manifest`. `output_dir` must be `platform_dir` (`data/news/{name}/`) so the
engine writes to `platform_dir/raw/{hash}.html` = the path dedup checks. `job_dir` must be
`platform_dir/"scrape_jobs"/{job_id}` (computed in `pipeline.py` before the call).

Status mapping in `_build_manifest`: if any `job_record` for a URL has `status == "ok"` (and a
written file) → manifest `"ok"`; all other outcomes (regwall, connect_fail, failed, empty, never
reached) → `"failed"`. No `"dead"` status (CoinDesk doesn't 404/410 through proxy; it regwalls).

## State

`RiderState` (defined in `rider.py`) is the shared mutable state across all slot coroutines and the
watchdog. Owned and mutated by `rider.py:run_riding_pool` and `rider.py:_run_slot`. Read by
`reporter.py:write_riding_report` and `scrape.py:_build_manifest` (read-only, after run completes).
`asyncio` single-threaded: `set.add/discard` on `in_flight_urls` and `int` increments on counters
are safe without explicit locking. `proxy_lock` (asyncio.Lock) guards `proxy_cursor` advancement.

## Gotchas

- `file` field in manifest points to `.html` (not `.md`). `dedup.py:filter_new_entries` mode `"raw"`
  now accepts `raw_ext` param — pass `".html"` for riding path (done in `pipeline.py:run_scrape_only`).
  `pipeline.py:_run_clean_pass` still hardcodes `{h}.md` but is NOT on CoinDesk's path (proxy_pool /
  TheBlock only) — out of scope unless CoinDesk gains a clean-pass step.
- `output_dir` passed to `scrape_entries_riding` must be `platform_dir` (`data/news/{name}/`), NOT
  `raw_dir`. The rider writes to `output_dir/raw/{hash}.html`; passing `raw_dir` puts files at
  `raw/raw/` (wrong), breaking dedup.
- `_abort_stall` calls `os._exit(1)` — no Python teardown, no atexit, no `browser.close()`. Raw
  files flushed before the call are durable; in-flight writes at the moment of abort are lost.
  `_abort_stall` writes to `state.job_dir` (= `scrape_jobs/{job_id}/`), NOT to `output_dir`; it
  creates the dir itself (`mkdir`) before the first write because the dir may not exist at stall time.
- Late import of `reporter.write_riding_report` inside `_abort_stall` is intentional: `reporter.py`
  imports from `rider.py` (RiderState); a top-level cross-import would be circular.
- Pool load (`load_backfill_pool`) is blocking network I/O, run via `run_in_executor` to avoid
  blocking the event loop during the async entry point.
