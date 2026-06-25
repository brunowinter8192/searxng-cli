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
  `pipeline.py:run_scrape_only` (normal completion) and by `_abort_stall` / `_abort_done` /
  `_abort_interrupted` (late import, abort paths).
- `run_riding_pool(url_queue, proxy_pool, cooldown_mgr, output_dir, job_dir, target_urls, …)` in `rider.py` — async;
  called by `scrape_entries_riding`.

## Flow

1. `scrape_entries_riding` builds URL queue from entries, loads pool via `load_backfill_pool()`,
   filters to `{"http","socks5"}`, shuffles, constructs `RidingCooldownManager(policy=riding_cfg.cooldown_policy)`.
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

### cooldown.py (95 LOC)

**Purpose:** Riding-specific proxy cooldown manager (`RidingCooldownManager`). Isolated from the
theblock-shared `proxy_pool/cooldown.py` (`PersistentCooldownManager`) — the theblock path is
untouched. Supports two policies selectable per-run via `RidingScrapeConfig.cooldown_policy`:
`"fixed"` (60-min flat cooldown, byte-identical to current production control arm) and `"exp"`
(exponential backoff with full jitter, ported from scrapy-rotating-proxies: base=300s, cap=3600s;
reset-on-productive-ride: if `ride_ok >= 1` the `failed_attempts` counter resets before computing
the backoff, so a proxy that delivered a successful fetch re-enters the eligible pool quickly).
`cooldown_count()` correct under both policies — counts proxies with `now < next_eligible` (exp) or
`now - burned_at < 3600s` (fixed), used by the watchdog's `pool_samples` A/B telemetry.
Read-only `.policy` property exposes the active policy string for the reporter.
**Reads:** `_burned_at` / `_next_eligible` / `_failed_attempts` (in-memory dicts keyed by `proxy_key`).
**Writes:** same dicts on `mark_burned(proto, hp, ride_ok=0)`.
**Called by:** `rider.py:_run_slot` (via `state.cooldown_mgr.mark_burned`);
`rider.py:_next_proxy` (via `state.cooldown_mgr.eligible_candidates`);
`rider.py:_watchdog` (via `state.cooldown_mgr.eligible_candidates` + `cooldown_count`);
`scrape.py:scrape_entries_riding` (instantiation: `RidingCooldownManager(policy=riding_cfg.cooldown_policy)`);
`reporter.py:_write_md` (via `state.cooldown_mgr.policy`).
**Calls out:** `src.news.engine.proxy_pool.proxy_key.proxy_key`.

---

### rider.py (574 LOC)

**Purpose:** Browser-per-context proxy rider pool. Manages B `AsyncWebCrawler` instances, N slot
coroutines, per-URL proxy context (`CrawlerRunConfig.proxy_config`), burn/fail rotation, watchdog,
30-min pool refresh. Installs SIGINT/SIGTERM handlers so manual aborts also produce a report.
**Reads:** URL queue (asyncio.Queue), proxy pool list, `RidingCooldownManager` (shared state).
**Writes:** `output_dir/raw/{hash}.html` for each ok URL; `state.job_dir/job.md` + `cumulative.png`
on stall abort, wedge-after-done, or manual abort (via `_abort_stall` / `_abort_done` /
`_abort_interrupted` — same dir as normal-completion report).
**Called by:** `scrape.py:scrape_entries_riding` (via `run_riding_pool`).
**Calls out:** `crawl4ai` (AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, ProxyConfig,
DefaultMarkdownGenerator); `src.news.engine.proxy_riding.cooldown.RidingCooldownManager` (import);
late import of `reporter.write_riding_report` inside `_abort_stall` / `_abort_done` /
`_abort_interrupted` (avoids circular).

Key dataclasses: `RiderState` (shared mutable job state — fields: `output_dir` raw writes,
`job_dir` report writes, `target_urls` frozenset of all distinct targets, `done_urls` set of written URLs,
`pool_samples` list of `(elapsed_s, n_eligible, n_cooldown)` tuples appended by `_watchdog` each poll,
`pool_provider` async callable `() -> list[tuple[str,str]]` for 30-min refresh (None = static pool);
`all_resolved = len(done_urls) >= len(target_urls)`), `JobRecord` (per-URL outcome),
`RideRecord` (per-proxy-ride summary). `FAIL_THRESHOLD = 2` (failed/empty strikes before drop).

`JobRecord` fields: standard per-URL fields + `load_s: float | None` — navigation load time for OK
fetches only, computed as `max(0, elapsed_s − DELAY_BEFORE_HTML)`. crawl4ai's `CrawlResult` exposes
no dedicated nav-timing field; subtracting the fixed 0.5 s post-load delay approximates the
navigation phase (shifts the curve right by ~constant context-setup overhead, reads the timeout
conservatively). Non-OK fetches leave `load_s = None`.

`RiderState` additional field: `connect_fail_records: list` — list of `(elapsed_s: float, subtype: str)`
tuples, one per connect_fail fetch, appended in `_run_slot` BEFORE the `break` that exits the proxy
ride (connect_fail was previously discarded: `break` skips the `job_records.append`). Populated even
on stall/abort — available in every `write_riding_report` call path.

`_classify_connect_fail(err)` — helper returning one of four subtypes from the raw error string:
`'page_timeout'` (`"ms exceeded"` — Playwright nav timeout, any value of N in "Timeout Nms exceeded");
`'net_timed_out'` (`"net::err_timed_out"` — TCP-level timeout, distinct from Playwright cap);
`'proxy_connect'` (`"err_proxy"` / `"err_tunnel"` / `"socks"` — handshake failure);
`'other'` — catch-all (ERR_CONNECTION_REFUSED, ERR_CONNECTION_CLOSED, ERR_EMPTY_RESPONSE, etc.).

`run_riding_pool` signal handler lifecycle: after `state` is constructed, installs
`loop.add_signal_handler(SIGINT/SIGTERM, _abort_interrupted, state, signum)`. Removed in the
`finally` block (before `watchdog.cancel()`) so they don't fire during the normal-completion
`write_riding_report` call in `pipeline.py`.

`_watchdog` poll loop (every `min(30, stall_timeout_s/4)` s), in order:
1. Append pool sample `(elapsed_s, n_eligible, n_cooldown)`.
2. **Pool refresh** (if `pool_provider` set and `POOL_REFRESH_INTERVAL_S = 1800` elapsed): `await
   state.pool_provider()` via `run_in_executor` thread; guard against empty result; atomic assign
   `state.proxy_pool = new_pool`; `cooldown_mgr` persists unchanged.
3. `all_resolved AND in_flight == 0` → `return` (clean drain).
4. `all_resolved AND in_flight > 0` → `_abort_done(state)`: report + `os._exit(0)` (wedge-after-done).
5. `idle > stall_timeout_s` → `_abort_stall(state, idle)`: report + `os._exit(1)` (genuine stall).

`_abort_interrupted(state, signum)`: SIGINT/SIGTERM handler. Sets `termination="interrupted"`,
calls `write_riding_report`, `os._exit(130)` for SIGINT / `os._exit(143)` for SIGTERM. Same
structure and late-import pattern as `_abort_stall` / `_abort_done`.

### reporter.py (383 LOC)

**Purpose:** Job report writer — `job.md` (counts, throughput, proxy-riding stats, eligible-pool-over-time
table, regwall counts, connect-fail breakdown, success load-time distribution) + `cumulative.png`
(step-plot of cumulative OK fetches over time) + `success_load_hist.png` (histogram of OK-fetch load
times) + `connect_fail_hist.png` (histogram of connect-fail elapsed times).
**Reads:** `RiderState` (in-memory), `t_job_start` (datetime).
**Writes:** `{job_dir}/job.md`; `{job_dir}/cumulative.png`;
`{job_dir}/success_load_hist.png` (only when ≥2 OK `load_s` values);
`{job_dir}/connect_fail_hist.png` (only when ≥2 `connect_fail_records`).
All histograms: 0.25 s bins, x-axis auto-ranges to data max, page_timeout_s red vertical line.
**Called by:** `pipeline.py:run_scrape_only` (normal completion, via `write_riding_report`);
`rider._abort_stall` (late import, stall abort); `rider._abort_done` (late import, wedge-after-done);
`rider._abort_interrupted` (late import, SIGINT/SIGTERM abort).
**Calls out:** `matplotlib` (lazy import inside plot functions); `statistics` (stdlib, incl.
`statistics.quantiles` with `method='inclusive'` — bounds p-values within observed [min, max]);
`math` (stdlib, bin count); `src.news.engine.proxy_riding.rider` (RiderState, FAIL_THRESHOLD).

`_compute_stats` additions:
- `load_times` / `load_perc` — OK-fetch load times + inclusive percentiles (None when <2 samples)
- `cf_times` / `cf_perc` — connect-fail elapsed times + inclusive percentiles (None when <2 samples)
- `cf_subtype_counts` — dict of subtype → count (`page_timeout`, `net_timed_out`, `proxy_connect`, `other`)
- `page_timeout_s` — from `state.page_timeout_ms / 1000`, shared axis reference for both histograms

job.md section **"Connect-fail breakdown"** (between Regwall and Success load-time): percentile table
(p50/p90/p95/p99/max, n=count) + subtype table (count + share) computed over `connect_fail_records`.
Subtypes shown in fixed order (page_timeout, net_timed_out, proxy_connect, other) for cross-run
comparability. `_Fewer than 2 connect-fail records_` note + no histogram when <2 samples.

job.md section **"Success load-time distribution"**: percentile table computed over OK fetches only.
`_Fewer than 2 OK fetches_` note when unavailable.

### scrape.py (113 LOC)

**Purpose:** Pipeline entry point + manifest adapter. Loads pool, shuffles, calls `run_riding_pool`,
maps `RiderState.job_records` → pipeline manifest.
**Reads:** entries list (in-memory), `RidingScrapeConfig`, proxy pool (network via `load_backfill_pool`).
**Writes:** delegates to `rider.py` (raw HTML writes to `output_dir/raw/{hash}.html`); writes nothing directly.
**Called by:** `pipeline.py:run_scrape_only` (proxy_riding dispatch arm).
**Calls out:** `src.news.engine.proxy_pool.pool_loaders.load_backfill_pool`;
`src.news.engine.proxy_riding.cooldown.RidingCooldownManager`;
`src.news.engine.proxy_riding.rider.run_riding_pool`.

`_pool_provider()` — shared async helper used for BOTH initial pool load (at `scrape_entries_riding`
start) AND as the `pool_provider` callable threaded into `RiderState` for 30-min watchdog refresh.
Runs `load_backfill_pool()` in `run_in_executor` (blocking network I/O), filters to
`BROWSER_ELIGIBLE_PROTOS = {"http","socks5"}`, shuffles. Single source of truth — no separate
init-vs-refresh code paths.

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
- All three abort functions (`_abort_stall`, `_abort_done`, `_abort_interrupted`) call `os._exit`
  — no Python teardown, no atexit, no `browser.close()`. Raw files flushed before the call are
  durable; in-flight writes at the moment of abort are lost. All write to `state.job_dir`
  (= `scrape_jobs/{job_id}/`), NOT to `output_dir`; each creates the dir itself (`mkdir`) before
  the first write because the dir may not exist at abort time.
- Late import of `reporter.write_riding_report` inside all abort functions is intentional:
  `reporter.py` imports from `rider.py` (RiderState); a top-level cross-import would be circular.
- Pool load (`load_backfill_pool`) is blocking network I/O, run via `run_in_executor` to avoid
  blocking the event loop during the async entry point.
