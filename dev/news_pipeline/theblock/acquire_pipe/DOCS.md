# dev/news_pipeline/theblock/acquire_pipe/

## Role
Production-candidate acquire pipeline for theblock.co content. Fetches a defined
TARGET (set of URLs) through a rotating proxy pool using curl_cffi chrome
impersonation. Every request is a productive fetch — no separate proxy-check stage.
Does NOT import from `src/`; self-contained dev implementation.

## Design (RACE)

**Continuous 128-worker dispatch race.** (Full rationale: `decisions/OldThemes/news_pipeline_layers/36_race_loop.md`.)
- **Workers:** `concurrency` (default 128) persistent worker threads. Each loops: pull next
  unfinished URL (round-robin, skip-done) → pull next proxy (shuffled pool, sequential cursor) →
  fetch → on success mark URL done (first-success-per-URL test-and-set).
- **Tail-race (emergent):** while many URLs pending, round-robin hands each worker a distinct URL.
  When fewer pending URLs than free workers remain, the same remaining URL is served to multiple
  workers → they race it with different proxies; first success wins. No straggler tail.
- **Each proxy used once:** sequential cursor through the shuffled pool. No cooldown, no burn, no
  working-set, no refresh. Pool exhausted before all URLs done → unfetched URLs → `gap`.
- **Supersedes** the sustained machine (OT32-33): cooldown / buffer / 60-min refresh /
  wait-on-exhaustion / safety-cap removed — unnecessary for a minutes-long discovery run.

## Two chained targets
| Target | Input | Output |
|---|---|---|
| DEV-RUN (done) | sitemap index → 64 sub-sitemap URLs | 44,041 unique URLs (26,003 `/post/`) |
| BACKFILL (next) | 26k `/post/` article URLs | article page content |

## Modules

### p1_fetch.py (41 LOC)
**Purpose:** curl_cffi chrome fetch primitive + XML/HTML content validators.
**Reads:** remote URLs via curl_cffi `Session(impersonate="chrome")`.
**Writes:** returns `(ok: bool, content: bytes)`.
**Called by:** `p3_target._fetch_index_via_proxy`, `p4_loop.run_loop`.
**Calls out:** `curl_cffi`.

---

### p2_cooldown.py (53 LOC)
**Purpose:** In-memory cooldown tracking — per-job clean slate, no file I/O.
`PersistentCooldownManager.__init__` starts with `self._burned_utc = {}` — fresh per process.
`mark_burned()` records `now` into the dict. `is_eligible()`: `now − burned_at ≥ 60min`.
`earliest_eligible_at()`: next re-eligibility moment (for the loop's wait-on-exhaustion).
`eligible_candidates()`: pool filtered to eligible proxies, socks4-first. `cooldown_count()`: count
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

### p4_loop.py (189 LOC) — DORMANT (superseded by p4_race.py, OT36)
**Purpose:** SUSTAINED concurrent rotation loop. NO LONGER CALLED — `acquire_pipe` uses `run_race`
(p4_race.py) since OT36; kept on disk pending the article-backfill decision. Outer time-loop wraps the inner batch loop:
calls `pool_provider()` on start + every `refresh_interval_s` (3600) tick → `build_active_buffer`;
records pool size via `logger.record_pool_refresh(len(pool_22k))` after each call (3 sites: startup,
60-min refresh, exhaustion-wakeup). Inner loop draws batches from the active buffer (Slot 1
working-set, Slot 2 buffer), 2-strikes lifecycle (2 consecutive fails → `cm.mark_burned` + remove
from buf/wset; success resets counter). On exhaustion → `_compute_sleep` (min of next cooldown
expiry via `cm.earliest_eligible_at()` and next refresh, clamped to cap) → sleep → refresh →
continue (no gap). `max_wall_s` safety cap. `_sleep` module attr (mockable in tests).
**Reads:** `pool_provider()` (callback) + target URL list.
**Writes:** delegates all state to `AcquireLogger` + `cm`; returns `(done, gap)`.
**Called by:** `acquire_pipe.py`.
**Calls out:** `p1_fetch`, `p2_cooldown`, `p5_logger`, `p6_buffer`.
**content_handler hook:** optional `content_handler: Callable[[str, bytes], None]` fires at the
`if ok:` success branch — persist/parse fetched bytes at the fetch site.

---

### p4_race.py (99 LOC)
**Purpose:** RACE fetch loop — replaces `run_loop`. `concurrency` (128) persistent worker threads;
each pulls next unfinished URL (round-robin via `_next_url`, skip-done, under `_lock`) + next proxy
(shuffled pool, sequential cursor via `_next_proxy`, under `_proxy_lock`), fetches, `record_attempt`,
on ok `_mark_done` (test-and-set on `done_set`; progress print `[race] M/N done` + `content_handler`
outside the lock, once per URL). Tail-race emergent (round-robin re-serves the same pending URL to
free workers). Each proxy used once; no cooldown/buffer/refresh/cap. Returns `(done, gap)`.
**Reads:** proxy pool (list) + target URL list.
**Writes:** delegates events to `AcquireLogger.record_attempt`; returns `(done, gap)`.
**Called by:** `acquire_pipe.py`.
**Calls out:** `p1_fetch.fetch_url`, `p5_logger`, `p6_buffer` (DEFAULT_CONCURRENCY const).
**Thread-safety:** shared state (URL cursor, proxy cursor, done_set) locked; logger JSONL writes
serialized by the file-object lock + counters never read (close() not finalize()) → p5_logger untouched.

---

### p5_logger.py (216 LOC)
**Purpose:** Streams fetch events to JSONL on every attempt (kill-safe); in-memory only for small
counters. `close()` closes the stream without writing MD (use before `janitor.end_job`). `finalize()`
closes and also writes per-run MD (standalone use only, not called in wired flow).
**Reads:** events fed by `run_race` (`record_attempt`, from 128 worker threads) + `acquire_pipe` (`record_pool_refresh`). `record_burn`/`record_working_set` unused since OT36.
**Writes:** `acquire_pipe_logs/acquire_events_<ts>.jsonl` (streamed, line-buffered).
**Called by:** `p4_race.run_race`, `acquire_pipe.py` (`p4_loop.run_loop` dormant).
**Concurrency:** `record_attempt` is called from 128 worker threads. Safe untouched — CPython's
`BufferedWriter` serializes each `write()` (no line interleave); in-memory counters race but are
never read in the wired flow (`close()` not `finalize()`; janitor reads the JSONL directly).
**Calls out:** `proxy_status_log.proxy_key`.

**Streaming design:** `record_attempt()` writes each event as `json.dumps(event)+"\n"`
to an open file handle (`buffering=1`, line-buffered). No in-memory event list.
A kill at any point leaves all recorded events on disk. `record_pool_refresh(size)` writes
`{"event":"pool_refresh","size":N,"ts":...}` — consumed by `p7_janitor` for job.md pool field.
`finalize()` reconstructs Surface 6 via `_throughput_buckets(jsonl_path)` — `t0 = min(ts)` across
all events, so the function works on any partial JSONL without runtime context.

**6 surfaces:**
1. Fetch progress — URLs done/total + rate (URLs/min)
2. B-per-proxy distribution — requests-before-burn histogram
3. Working-set size over time — eligible candidate count per round
4. Failed attempts per successful fetch — churn ratio
5. Per-proxy event JSONL — `proxy_key`, `ts`, `url`, `result`, `proxy_success_count`
6. Throughput over time — ok fetches per minute (bursty vs linear)

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
**Purpose:** Active-buffer helpers for the sustained loop — `build_active_buffer`/`refill_buffer`
DORMANT since OT36 (only `run_loop` used them); the `DEFAULT_CONCURRENCY`/`BUFFER_SIZE` constants stay live (imported by `acquire_pipe` + `p4_race`). `build_active_buffer(pool, cm, max_size)`
returns up to `max_size` eligible proxies (delegates eligibility + socks4-first ordering entirely to
`cm.eligible_candidates()`). `refill_buffer(buf, pool, cm, target_size)` tops an existing buffer up to
`target_size` from the eligible set (immutable — returns a new list; set-membership dedup; no-op when
already full). Holds `BUFFER_SIZE = 1280` and `DEFAULT_CONCURRENCY = 128`.
**Reads:** proxy pool + `cm` eligibility.
**Writes:** returns new buffer lists (pure).
**Called by:** `p4_loop.run_loop` (dormant); constants imported by `acquire_pipe.py` + `p4_race.py`.
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

### acquire_pipe.py (114 LOC)
**Purpose:** Job orchestrator. Eager-loads chosen pool (+ stdout print) → `build_sitemap_target`
(64 sub-sitemap URLs, same pool) → `job_id` → `box_lock.acquire` (`LockBusyError` → print+exit(1))
→ `janitor.start_job` → `logger.record_pool_refresh(len(pool))` (once) → `run_race` (p4_race,
continuous 128-worker dispatch) → `content_handler` (persist raw XML + parse `<loc>` bytes) →
dedup article URLs → `theblock_article_urls.txt` → `logger.close()` → `janitor.end_job`
(job.md + plot + wipe transient).
**Reads:** proxy pool (curated or backfill) + theblock sitemap index (via p3_target).
**Writes:** `acquire_pipe_output/<slug>.xml` (raw sub-sitemaps, gitignored) +
`acquire_pipe_output/theblock_article_urls.txt` (tracked) +
`acquire_pipe_jobs/<job_id>/job.md` + `cumulative_hits.png` (persistent, via janitor).
**Called by:** CLI — `python acquire_pipe.py [--concurrency N] [--pool {curated,backfill}]`.
**Calls out:** `box_lock`, `p7_janitor`, `p3_target`, `p4_race`, `p5_logger`, `p6_buffer` (const), `curated_sources`.
**CLI flags:**
- `--concurrency N` — concurrent worker threads (default 128)
- `--pool {curated,backfill}` — proxy pool (default `backfill`):
  `curated` = monosans+proxifly ~3.5k; `backfill` = top-13 repos ~22.7k unique

---

## Status

**Machine: RACE + BOX/JANITOR (built, reviewed on dev; not yet run at scale).** OT36 replaced the
sustained loop with the continuous 128-worker race (`p4_race.run_race`) — see
`decisions/OldThemes/news_pipeline_layers/36_race_loop.md`. Box-lock, janitor, logger unchanged.

**Superseded — sustained machine (dormant):** OldThemes 32 built the sustained
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
- RACE loop (p4_race): each proxy used at most ONCE per job; no cooldown/burn/reuse. Pool exhausted
  before all URLs done → unfetched URLs → `gap`. At the tail, many workers race the same remaining URL
  — redundant successes are possible (bounded waste), the deliberate price of killing the straggler tail.
- `box_lock`: SIGTERM kills Python before `finally` runs → sidecar stays; kernel releases flock.
  Next `acquire()` recovers via `cleanup_stale()` (dead-PID detection). Not a problem in practice.
- `p7_janitor._write_plot` imports `matplotlib.pyplot` lazily — first call builds font cache (~1s one-time).
- `acquire_pipe_jobs/` is the ONLY persistent output. `acquire_pipe_logs/` and `acquire_pipe_reports/`
  are wiped at job start and end — do not inspect them after a job completes.
