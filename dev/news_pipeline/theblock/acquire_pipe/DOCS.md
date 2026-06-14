# dev/news_pipeline/theblock/acquire_pipe/

## Role
Production-candidate acquire pipeline for theblock.co content. Fetches a defined
TARGET (set of URLs) through a rotating proxy pool using curl_cffi chrome
impersonation. Every request is a productive fetch — no separate proxy-check stage.
Does NOT import from `src/`; self-contained dev implementation.

## Design (SUSTAINED)

**Sustained concurrent rotation loop with persistent cooldown.** (Full rationale: `decisions/OldThemes/news_pipeline_layers/32_sustained_loop.md`.)
- **Active buffer:** up to `buffer_size` (default 1280 = 10× concurrency) ELIGIBLE proxies pulled
  from the full pool (socks4-first), refilled as proxies burn out.
- **Batches:** fires up to `concurrency` (default 128) (proxy, URL) pairs concurrently. Working-set
  proxies (proven this session) fill Slot 1; fresh buffer candidates Slot 2.
- **2-strikes lifecycle:** a proxy rides across URLs while it succeeds. 2 CONSECUTIVE fails → burn;
  a success resets the per-proxy fail counter.
- **Persistent cooldown:** on burn, `cooled_at = now` is written to `proxy_status_log.json` (via
  `p2_cooldown.PersistentCooldownManager`). Eligibility = `now − cooled_at ≥ 60min`. Survives across
  runs — NOT in-process/per-run.
- **60-min pool refresh:** every `refresh_interval_s` (3600) the full pool is re-fetched via
  `pool_provider()` and the buffer rebuilt from the now-eligible set.
- **Wait-on-exhaustion:** when buffer + working-set are empty, the loop SLEEPS until the earlier of
  (next cooldown expiry, next refresh) instead of gapping — then continues.
- **Safety cap:** `max_wall_s` (default 12h) bounds the run; clean exit, unfinished URLs → gap.

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

### p2_cooldown.py (76 LOC)
**Purpose:** PERSISTENT cooldown state backed by `proxy_status_log.json` (`cooled_at` field).
`PersistentCooldownManager` loads all `cooled_at` timestamps on init (UTC datetime) — survives
process restarts. `mark_burned()` updates an in-memory cache + dirty set (no I/O); `flush()`
batch-writes dirty burns in one load+save (one I/O per batch). `is_eligible()` uses wall-clock
UTC (`now − cooled_at ≥ 60min`). `earliest_eligible_at()` returns the next re-eligibility moment
(for the loop's wait-on-exhaustion). socks4-first ordering. `CooldownManager` = alias.
**Reads:** `load_cooled_at()` from `proxy_status_log` on init.
**Writes:** `proxy_status_log.json` `cooled_at` via `mark_cooled_batch()` (on `flush()`).
**Called by:** `p4_loop.run_loop`, `p6_buffer`, `acquire_pipe.py`.
**Calls out:** `proxy_status_log.{load_cooled_at, mark_cooled_batch, proxy_key}`.

---

### p3_target.py (68 LOC)
**Purpose:** Sitemap target builder. Fetches theblock index → parses 64 sub-sitemap
`<loc>` URLs. Direct httpx GET first; falls back to proxy rotation on non-XML response
(403, CF challenge, error).
**Reads:** `THEBLOCK_INDEX` via httpx (direct) or `p1_fetch.fetch_url` (proxy fallback).
**Writes:** returns `list[str]` of 64 sub-sitemap URLs.
**Called by:** `acquire_pipe.py`.
**Calls out:** `httpx`, `p1_fetch`, `p2_cooldown`, `curated_sources`.

---

### p4_loop.py (187 LOC)
**Purpose:** SUSTAINED concurrent rotation loop. Outer time-loop wraps the inner batch loop:
calls `pool_provider()` on start + every `refresh_interval_s` (3600) tick → `build_active_buffer`;
inner loop draws batches from the active buffer (Slot 1 working-set, Slot 2 buffer), 2-strikes
lifecycle (2 consecutive fails → `cm.mark_burned` + remove from buf/wset; success resets counter),
`cm.flush()` once per batch. On buffer+working-set exhaustion → `_compute_sleep` (min of next
cooldown expiry via `cm.earliest_eligible_at()` and next refresh, clamped to cap) → sleep → refresh
→ continue (no gap). `max_wall_s` safety cap. `_sleep` module attr (mockable in tests).
**Reads:** `pool_provider()` (callback) + target URL list.
**Writes:** delegates all state to `AcquireLogger` + `cm`; returns `(done, gap)`.
**Called by:** `acquire_pipe.py`.
**Calls out:** `p1_fetch`, `p2_cooldown`, `p5_logger`, `p6_buffer`.
**content_handler hook:** optional `content_handler: Callable[[str, bytes], None]` fires at the
`if ok:` success branch — persist/parse fetched bytes at the fetch site.

---

### p5_logger.py (203 LOC)
**Purpose:** Streams fetch events to JSONL on every attempt (kill-safe); in-memory
only for small counters. `finalize()` closes the stream and writes an MD summary.
**Reads:** events fed by `run_loop` via `record_attempt / record_burn / record_working_set`.
**Writes:** `acquire_pipe_logs/acquire_events_<ts>.jsonl` (streamed, line-buffered) +
`acquire_pipe_reports/acquire_run_<ts>.md` (at `finalize()`).
**Called by:** `p4_loop.run_loop`, `acquire_pipe.py`.
**Calls out:** `proxy_status_log.proxy_key`.

**Streaming design:** `record_attempt()` writes each event as `json.dumps(event)+"\n"`
to an open file handle (`buffering=1`, line-buffered). No in-memory event list.
A kill at any point leaves all recorded events on disk. `finalize()` reconstructs
Surface 6 from the JSONL via `_throughput_buckets(jsonl_path)` — `t0 = min(ts)` across
all events, so the function works on any partial JSONL without runtime context.

**6 surfaces:**
1. Fetch progress — URLs done/total + rate (URLs/min)
2. B-per-proxy distribution — requests-before-burn histogram
3. Working-set size over time — eligible candidate count per round
4. Failed attempts per successful fetch — churn ratio
5. Per-proxy event JSONL — `proxy_key`, `ts`, `url`, `result`, `proxy_success_count`
6. Throughput over time — ok fetches per minute (bursty vs linear)

---

### p6_buffer.py (52 LOC)
**Purpose:** Active-buffer helpers for the sustained loop. `build_active_buffer(pool, cm, max_size)`
returns up to `max_size` eligible proxies (delegates eligibility + socks4-first ordering entirely to
`cm.eligible_candidates()`). `refill_buffer(buf, pool, cm, target_size)` tops an existing buffer up to
`target_size` from the eligible set (immutable — returns a new list; set-membership dedup; no-op when
already full). Holds `BUFFER_SIZE = 1280` and `DEFAULT_CONCURRENCY = 128`.
**Reads:** proxy pool + `cm` eligibility.
**Writes:** returns new buffer lists (pure).
**Called by:** `p4_loop.run_loop`, `acquire_pipe.py` (constants).
**Calls out:** `p2_cooldown.PersistentCooldownManager`.

---

### acquire_pipe.py (116 LOC)
**Purpose:** Sustained orchestrator. Instantiates `PersistentCooldownManager`, picks `pool_fn`
(curated/backfill) → `build_sitemap_target` (64 sub-sitemap URLs) → sustained `run_loop` with
`content_handler` (persist raw XML + parse `<loc>` bytes) → dedup article URLs → write
`theblock_article_urls.txt` → `logger.finalize`.
**Reads:** proxy pool (curated or backfill) + theblock sitemap index (via p3_target).
**Writes:** `acquire_pipe_output/<slug>.xml` (raw sub-sitemaps, gitignored) +
`acquire_pipe_output/theblock_article_urls.txt` (tracked) + `proxy_status_log.json` `cooled_at` (via cm).
**Called by:** CLI — `python acquire_pipe.py [--concurrency N] [--buffer_size N] [--max_hours H] [--pool {curated,backfill}]`.
**Calls out:** `p2_cooldown`, `p3_target`, `p4_loop`, `p5_logger`, `p6_buffer`, `curated_sources`.
**CLI flags:**
- `--concurrency N` — concurrent (proxy, URL) pairs per batch (default 128)
- `--buffer_size N` — active eligible-proxy buffer depth (default 1280)
- `--max_hours H` — hard wall-time safety cap in hours (default 12)
- `--pool {curated,backfill}` — proxy pool (default `curated`):
  `curated` = monosans+proxifly ~3.5k; `backfill` = top-13 repos ~22.7k unique

NOTE: the default target is still the 64 sub-sitemaps (sitemap dev-run). The actual article-content
backfill points the same machine at the 26k `/post/` URLs — a later run.

---

## Status

**Machine: SUSTAINED (built, merged on dev).** The single-pass loop was replaced by the sustained
multi-cycle machine (persistent cooldown + active buffer + 2-strikes + 60-min refresh + wait-on-
exhaustion). Built in 5 sequential sub-stages, each committed + reviewed:

| Sub-stage | Commit | What |
|---|---|---|
| 1 | 5ee905b | persistent cooldown store (`cooled_at` in proxy_status_log; PersistentCooldownManager) |
| 2 | aab6eb4 | active buffer (`p6_buffer`: build + refill from 22k eligible) |
| 3 | 91582db | 2-strikes lifecycle, persistent burn→cooldown, buffer-draw loop |
| 4 | 3e9a97c | outer time-loop: 60-min refresh + wait-on-exhaustion + safety cap |
| 5 | e93f33c | acquire_pipe wiring (pool_provider, cm, `--buffer_size/--max_hours/--pool`) |

**Validation:** per-stage unit tests (no network, prod log untouched) + an end-to-end smoke (real
network, temp log, 36s cap): 5 `/post/` URLs → 5/5 done in 34.3s, 6 burns all written to the log with
`cooled_at` (persistent cooldown verified). NOT yet validated: the real multi-hour sustained behavior
(refresh tick + wait across a real cooldown window) — only mocked-time unit-tested.

**Prior sitemap dev-run** (single-pass machine, superseded): 59/64, 44k URLs (26,003 `/post/`).
Full analysis: `decisions/OldThemes/news_pipeline_layers/29_sitemap_devrun.md` (run) +
`30_streaming_logger_economics.md` (economics) + `32_sustained_loop.md` (the sustained rebuild).

## Gotchas
- Home IP is CF-blocked for direct theblock GETs (403) — p3_target proxy fallback handles this.
- Cooldown is now PERSISTENT in `proxy_status_log.json` (`cooled_at`) — survives runs. A run inherits
  the cooldown state left by the previous run (intended).
- `cm.flush()` rewrites the whole `proxy_status_log.json` once per batch; at ~22k entries over a
  multi-hour run this is I/O-heavy → revisit (flush-every-N-seconds) if it bottlenecks.
- 2-strikes = 2 CONSECUTIVE fails (a success resets the counter) — a single transient fail does NOT burn.
- Failed URLs go to the BACK of the queue (not front) to avoid hammering one URL with dead proxies.
- Default target is still the 64 sub-sitemaps; the 26k article backfill is a later run on the same machine.
