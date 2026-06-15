# dev/news_pipeline/theblock/acquire_pipe/

## Role
Production-candidate acquire pipeline for theblock.co content. Fetches a defined
TARGET (set of URLs) through a rotating proxy pool using curl_cffi chrome
impersonation. Every request is a productive fetch — no separate proxy-check stage.
Does NOT import from `src/`; self-contained dev implementation.

## Design (SUSTAINED)

**Sustained concurrent rotation loop with persistent cooldown.** (Full rationale: `decisions/OldThemes/news_pipeline_layers/32_sustained_loop.md`.)
- **Active buffer:** up to `buffer_size` (default 1280 = 10× concurrency) ELIGIBLE proxies pulled
  from the full pool (pool order), refilled as proxies burn out.
- **Batches:** fires up to `concurrency` (default 128) (proxy, URL) pairs concurrently. Working-set
  proxies (proven this session) fill Slot 1; fresh buffer candidates Slot 2.
- **2-strikes lifecycle:** a proxy rides across URLs while it succeeds. 2 CONSECUTIVE fails → burn;
  a success resets the per-proxy fail counter.
- **In-memory cooldown (clean slate per job):** on burn, `burned_at = now` stored in a dict keyed by
  proxy_key (`p2_cooldown.PersistentCooldownManager`). Eligibility = `now − burned_at ≥ 60min`. Pure
  in-memory — each job starts with an empty burn set (no file I/O, no cross-job state).
- **60-min pool refresh:** every `refresh_interval_s` (3600) the full pool is re-fetched via
  `pool_provider()` and the buffer rebuilt from the now-eligible set.
- **Wait-on-exhaustion:** when buffer + working-set are empty, the loop SLEEPS until the earlier of
  (next cooldown expiry, next 60-min tick); wakes to `build_active_buffer(pool_22k, cm)` using the
  existing pool (no `pool_provider()` call — that stays on the 60-min tick only) — then continues.
- **Termination:** loop runs until `queue` is empty — every URL resolves to `done` (content fetched)
  or `dead` (404/410 from origin); `gap` is always empty by construction.

## Two chained targets
| Target | Input | Output |
|---|---|---|
| DEV-RUN (done) | sitemap index → 64 sub-sitemap URLs | 44,041 unique URLs (26,003 `/post/`) |
| BACKFILL (next) | 26k `/post/` article URLs | article page content |

## Modules

### p1_fetch.py (46 LOC)
**Purpose:** curl_cffi chrome fetch primitive + XML/HTML content validators.
**Reads:** remote URLs via curl_cffi `Session(impersonate="chrome")`.
**Writes:** returns `(status: str, content: bytes)`.
  `status` values: `"ok"` (valid content), `"dead"` (origin returned 404/410 — URL permanently gone,
  proxy confirmed working), `"fail"` (connection error / timeout / CF block / non-200 other than
  404/410 / 200 with wrong content type). `_validate` classifies 404/410 before the marker check.
**Called by:** `p3_target._fetch_index_via_proxy`, `p4_loop.run_loop`.
**Calls out:** `curl_cffi`.

---

### p2_cooldown.py (51 LOC)
**Purpose:** In-memory cooldown tracking — per-job clean slate, no file I/O.
`PersistentCooldownManager.__init__` starts with `self._burned_utc = {}` — fresh per process.
`mark_burned()` records `now` into the dict. `is_eligible()`: `now − burned_at ≥ 60min`.
`earliest_eligible_at()`: next re-eligibility moment (for the loop's wait-on-exhaustion).
`eligible_candidates()`: pool filtered to eligible proxies, in pool order (plain passthrough). `cooldown_count()`: count
of proxies currently in the cooldown window.
**Reads:** nothing (in-memory only).
**Writes:** nothing.
**Called by:** `p4_loop.run_loop`, `p6_buffer`, `p3_target`, `acquire_pipe.py`.
**Calls out:** `proxy_status_log.proxy_key`.

---

### p3_target.py (64 LOC)
**Purpose:** Sitemap target builder. Fetches theblock index → parses 64 sub-sitemap
`<loc>` URLs. Direct httpx GET first; falls back to proxy rotation on non-XML response
(403, CF challenge, error). Proxy pool is caller-supplied (no internal pool load).
**Reads:** `THEBLOCK_INDEX` via httpx (direct) or `p1_fetch.fetch_url` (proxy fallback).
**Writes:** returns `list[str]` of 64 sub-sitemap URLs.
**Called by:** `acquire_pipe.py`.
**Calls out:** `httpx`, `p1_fetch`, `p2_cooldown`.

---

### p4_loop.py (214 LOC)
**Purpose:** SUSTAINED concurrent rotation loop. Startup: calls `pool_provider()` once →
`build_active_buffer`. 60-min tick: every `refresh_interval_s` (3600 s) calls `pool_provider()`
again → rebuilds buffer (2 pool-fetch sites: startup + tick; `logger.record_pool_refresh` at both).
On exhaustion (buf + wset empty) → `_compute_sleep` (min of next cooldown expiry via
`cm.earliest_eligible_at()` and next 60-min tick) → sleep → `build_active_buffer(pool_22k, cm)`
using existing `pool_22k` (no `pool_provider()` call, no `_last_refresh` reset on exhaustion wakeup).
`_sleep` module attr (patchable in tests).
**3-branch fetch result (`status, content = fut.result()`):**
- `"ok"` — content valid: `batch_done` guard → `content_handler` + `done.append` + `wset.add` +
  `psuccess++` + `_consec_fail.pop`.
- `"dead"` — origin returned 404/410 (proxy confirmed working): `batch_done` guard →
  `dead.append`; proxy preserved (`wset.add` + `_consec_fail.pop`). NOT burned, NOT re-queued.
- `"fail"` — connection/timeout/CF/wrong format: `batch_failed.add` + 2-strikes lifecycle
  (2 consecutive fails → `cm.mark_burned` + remove from buf/wset; success resets counter).
**Tail-race (`_build_batch` Phase 2):** when pending URLs < available proxy slots (url_iter exhausted
before filling all concurrency slots), surplus proxies race the same remaining URLs round-robin
(wset-first, skipping already-assigned). Multiple proxies contest each leftover URL; first success
wins. `n_urls_consumed = len({url …})` ensures only the distinct-URL count is popleft'd from queue.
**First-success-wins / re-queue dedup:** `batch_done: set[str]` guards `content_handler` +
`done.append` — only the first successful racer per URL records a result. `batch_failed: set[str]`
(set → at-most-one per URL) collects failures in-loop; post-loop pass re-queues only URLs not in
`batch_done`, eliminating the fail-before-success ordering hazard of `as_completed`.
**Reads:** `pool_provider()` (callback) + target URL list.
**Writes:** delegates all state to `AcquireLogger` + `cm`; returns `(done, dead, gap)`.
**Called by:** `acquire_pipe.py`.
**Calls out:** `p1_fetch`, `p2_cooldown`, `p5_logger`, `p6_buffer`.
**content_handler hook:** optional `content_handler: Callable[[str, bytes], None]` fires at the
`if status == "ok":` branch (guarded by `batch_done`) — persist/parse fetched bytes at the fetch site.

---

### p5_logger.py (47 LOC)
**Purpose:** Streams fetch events to JSONL (line-buffered, kill-safe). No in-memory counters.
`close()` seals the stream; all stats derive from the JSONL inside `p7_janitor.end_job()`.
**Reads:** events pushed by `run_loop` via `record_attempt` / `record_pool_refresh`.
**Writes:** `acquire_pipe_logs/acquire_events_<ts>.jsonl` (streamed, line-buffered).
**Called by:** `p4_loop.run_loop`, `acquire_pipe.py`.
**Calls out:** `proxy_status_log.proxy_key`.

**Methods (3):**
- `record_attempt(proto, hp, url, ok)` — writes `{proxy_key, ts, url, result}` per fetch.
- `record_pool_refresh(size)` — writes `{event:"pool_refresh", size, ts}` (janitor reads `size`).
- `close()` — closes JSONL file handle. Call before `janitor.end_job(logger._jsonl_path, ...)`.

**JSONL schema per fetch event:** `{proxy_key, ts, url, result}` (`result`: `"ok"` or `"fail"`).

---

### box_lock.py (102 LOC)
**Purpose:** Global single-job flock — one acquire-pipe job at a time, system-wide.
Fixed lock paths: `~/.searxng-cli-locks/acquire_pipe.flock` (flock vessel) +
`~/.searxng-cli-locks/acquire_pipe.lock` (JSON sidecar `{pid, job, target, started_at, status}`).
`job`/`target` are sidecar metadata for the busy message — NOT in filenames.
`cleanup_stale()`: reads PID → `os.kill(pid,0)` → `ProcessLookupError` → unlink sidecar
(`PermissionError` → treat as held). `acquire(job, target)` contextmanager: `mkdir` →
`cleanup_stale` → open flock file → `fcntl.LOCK_EX|LOCK_NB` → `BlockingIOError` →
`LockBusyError(pid+job+elapsed from sidecar)`; on success: write sidecar atomically
(`mkstemp`+`os.rename`) → `yield` → `finally`: unlink sidecar + `LOCK_UN` + close.
Crash-safe: kernel releases flock on process death; stale sidecar cleaned on next `acquire()`.
**Reads:** `~/.searxng-cli-locks/acquire_pipe.lock` (in `cleanup_stale` + busy message).
**Writes:** `~/.searxng-cli-locks/acquire_pipe.{flock,lock}`.
**Called by:** `acquire_pipe.py`.
**Calls out:** `fcntl`, `os` (stdlib only).

---

### p6_buffer.py (52 LOC)
**Purpose:** Active-buffer helpers for the sustained loop. `build_active_buffer(pool, cm, max_size)`
returns up to `max_size` eligible proxies (delegates eligibility to `cm.eligible_candidates()`;
pool order preserved — no socks4-first sort). `refill_buffer(buf, pool, cm, target_size)` tops an existing buffer up to
`target_size` from the eligible set (immutable — returns a new list; set-membership dedup; no-op when
already full). Holds `BUFFER_SIZE = 1280` and `DEFAULT_CONCURRENCY = 128`.
**Reads:** proxy pool + `cm` eligibility.
**Writes:** returns new buffer lists (pure).
**Called by:** `p4_loop.run_loop`, `acquire_pipe.py` (constants).
**Calls out:** `p2_cooldown.PersistentCooldownManager`.

---

### p7_janitor.py (150 LOC)
**Purpose:** Job lifecycle — wipe transient artifacts at start, derive persistent record at end.
`start_job(job_id)`: wipes `acquire_pipe_logs/` + `acquire_pipe_reports/` contents.
`end_job(job_id, jsonl_path, target_count, done_count)`: reads JSONL → `_compute_stats`
(ok-event inter-hit deltas → mean/median, total wall time `max(ts)-min(ts)`, pool sizes from
`pool_refresh` events; `t0=min(ts)`) → `_write_plot` (matplotlib step chart, `cumulative_hits.png`,
x=elapsed s, y=cumul ok, `where="post"`) → `_write_md` (lean job.md — exactly 5 fields) →
unlink JSONL → wipe `acquire_pipe_logs/` + `acquire_pipe_reports/`.
Only `acquire_pipe_jobs/<job_id>/` survives after `end_job`.
**Reads:** streaming JSONL (via `jsonl_path`).
**Writes:** `acquire_pipe_jobs/<job_id>/job.md` + `cumulative_hits.png` (persistent).
**Called by:** `acquire_pipe.py`.
**Calls out:** `matplotlib.pyplot` (lazy import in `_write_plot`), `statistics` (stdlib).

---

### acquire_pipe.py (125 LOC)
**Purpose:** Job orchestrator. Eager-loads full backfill pool via `load_backfill_pool()` (~22k proxies,
stdout print) → `build_sitemap_target` (64 sub-sitemap URLs, same pool) → `job_id` →
`box_lock.acquire` (`LockBusyError` → print+exit(1)) → `janitor.start_job` →
`PersistentCooldownManager` (in-memory, fresh per job) → sustained `run_loop` via `_pool_provider`
closure (returns eager pool on first call, re-fetches via `load_backfill_pool()` on 60-min tick) →
`content_handler` (persist raw XML + parse `<loc>` bytes) → dedup article URLs →
`theblock_article_urls.txt` → dead-count print → `logger.close()` → `janitor.end_job` (job.md +
plot + wipe transient).
**Reads:** `load_backfill_pool()` (always full ~22k pool — no curated/pool flag) + theblock sitemap
index (via p3_target).
**Writes:** `acquire_pipe_output/<slug>.xml` (raw sub-sitemaps, gitignored) +
`acquire_pipe_output/theblock_article_urls.txt` (tracked) +
`acquire_pipe_jobs/<job_id>/job.md` + `cumulative_hits.png` (persistent, via janitor).
**Called by:** CLI — `python acquire_pipe.py [--concurrency N] [--buffer_size N]`.
**Calls out:** `box_lock`, `p7_janitor`, `p2_cooldown`, `p3_target`, `p4_loop`, `p5_logger`, `p6_buffer`, `curated_sources`.
**CLI flags:**
- `--concurrency N` — concurrent (proxy, URL) pairs per batch (default 128)
- `--buffer_size N` — active eligible-proxy buffer depth (default 1280)

---

## Status

**Machine: SUSTAINED + BOX/JANITOR (built, validated on dev).** OldThemes 32 built the sustained
loop; OldThemes 33 added job/box/janitor (clean-slate cooldown, global lock, persistent job record).
Full rationale: `decisions/OldThemes/news_pipeline_layers/33_box_janitor.md`.

| Stage | Commit | What |
|---|---|---|
| OT32-1 | 5ee905b | persistent cooldown store (superseded by OT33-A) |
| OT32-2 | aab6eb4 | active buffer (`p6_buffer`) |
| OT32-3 | 91582db | 2-strikes lifecycle + buffer-draw loop |
| OT32-4 | 3e9a97c | 60-min refresh + wait-on-exhaustion + safety cap |
| OT32-5 | e93f33c | acquire_pipe wiring |
| OT33-A | fedc151 | cooldown → in-memory (revert OT32-1 persistence) |
| OT33-B | d04dbf2 | box_lock.py (global single-job flock, Mineru pattern) |
| OT33-C | 9934b7c | p7_janitor + pool-size logging + matplotlib plot |
| OT33-E | 1d7c166 | wiring (box_lock + janitor in acquire_pipe.py) |

**Validated run:** 20260614T190143Z — 64/64 sub-sitemaps, 47128 unique article URLs, ~18.6min,
pool 3396 curated. Persistent output at `acquire_pipe_jobs/20260614T190143Z/`.

**Prior sitemap dev-run** (single-pass machine, superseded): 59/64, 44k URLs (26,003 `/post/`).
Full analysis: `decisions/OldThemes/news_pipeline_layers/29_sitemap_devrun.md` (run) +
`30_streaming_logger_economics.md` (economics) + `32_sustained_loop.md` (the sustained rebuild).

## Gotchas
- Home IP is CF-blocked for direct theblock GETs (403) — p3_target proxy fallback handles this.
- Cooldown is IN-MEMORY only — does NOT survive process restarts. Each job starts with a fully fresh
  burn set (intended: clean slate per job). No cross-job cooldown inheritance.
- 2-strikes = 2 CONSECUTIVE fails (a success resets the counter) — a single transient fail does NOT burn.
- Failed URLs go to the BACK of the queue (not front) to avoid hammering one URL with dead proxies.
- `box_lock`: SIGTERM kills Python before `finally` runs → sidecar stays; kernel releases flock.
  Next `acquire()` recovers via `cleanup_stale()` (dead-PID detection). Not a problem in practice.
- `p7_janitor._write_plot` imports `matplotlib.pyplot` lazily — first call builds font cache (~1s one-time).
- `acquire_pipe_jobs/` is the ONLY persistent output. `acquire_pipe_logs/` and `acquire_pipe_reports/`
  are wiped at job start and end — do not inspect them after a job completes.
