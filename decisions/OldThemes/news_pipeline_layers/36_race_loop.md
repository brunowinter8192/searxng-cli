# 36 — Race loop: sustained batch → continuous 128-worker dispatch

## Problem

The sustained batch loop (`p4_loop.run_loop`, OT32-33) had a **straggler tail**. Two coupled causes:

1. **Batch-synchronous.** Each round built a batch of ≤128 `(proxy, URL)` pairs, fired them via
   `ThreadPoolExecutor`, then waited (`as_completed`) for **all** of them before the next round. One
   proxy hitting the 15s timeout held up the whole round.
2. **One proxy per URL per round.** A failed URL re-queued and got exactly one new proxy in the next
   round. At the tail, when only 1-2 sub-sitemaps remained, the batch was 1-2 — only 1-2 of 128 slots
   used, the rest idle. A stubborn sub-sitemap got one proxy per ≤15s round, strictly sequential.

On the 64er run this manifested as the bulk completing fast (~8 min) and the last few `/post/`
sitemaps dragging the total to ~18.6 min.

## Decision

Replace `run_loop` with `run_race` (`p4_race.py`): **continuous 128-worker dispatch.**

- `concurrency` (128) persistent worker threads. Each worker loops: pull the next unfinished URL
  (round-robin, skip-done) → pull the next proxy (shuffled pool, sequential cursor) → fetch → on
  success mark the URL done (first-success-per-URL test-and-set).
- **Tail-race falls out for free.** While many URLs are pending, the round-robin hands each worker a
  distinct URL (one proxy each). When fewer pending URLs than free workers remain, the round-robin
  hands the same remaining URL to multiple workers → they race it with different proxies; first
  success wins, the rest skip it on their next pull.
- **Each proxy used at most once** (sequential cursor through the shuffled pool). No cooldown, no
  burn, no working-set. Pool exhausted before all URLs done → those URLs go to `gap`.

### Why the sustained machinery is gone

Cooldown / 60-min refresh / wait-on-exhaustion / safety-cap were built for a long sustained drain.
A 64-target discovery run finishes in minutes against an ~18k pool — none of it is needed. Removed
from `acquire_pipe.py`: `PersistentCooldownManager`, the `_pool_provider` closure, `--buffer_size`,
`--max_hours`. The pool is eager-loaded once; `record_pool_refresh(len(pool))` is emitted once.

### Origin

The per-URL parallel race was first proven in the article probe
(`probe_48h_article_fetch.py._fetch_parallel` — fire N proxies at one URL, first success wins, walk
the pool in waves). `run_race` generalizes that to multi-URL continuous dispatch.

## Thread-safety

All shared mutable state is locked:
- URL cursor + `done_set` + `done` list → `_lock`.
- Proxy cursor → `_proxy_lock`.
- `content_handler` fires OUTSIDE the lock, exactly once per URL (the `newly` test-and-set guard),
  writing a unique per-URL XML file + GIL-atomic `loc_urls.append`.

**`p5_logger` is untouched, and that is correct.** Two reasons:
1. `record_attempt` writes `json.dumps(event)+"\n"` to a line-buffered file handle. CPython's
   `BufferedWriter` holds an internal lock per `write()` — concurrent writes from the 128 workers do
   not interleave, JSONL lines stay valid.
2. The in-memory counters (`_attempts`, `_done`, `_proxy_successes`) have benign races but are
   **never read** in the wired flow: `acquire_pipe` calls `logger.close()` (not `finalize()`), and
   `p7_janitor.end_job` reads the JSONL file directly, not the counters.

## Supersession

- `p4_loop.run_loop` — DORMANT. No caller after this change. Kept on disk (not deleted) pending a
  decision on whether the future article-content backfill reuses it or the race model.
- `p6_buffer` — `build_active_buffer` / `refill_buffer` DORMANT (only `run_loop` used them). The
  `DEFAULT_CONCURRENCY` / `BUFFER_SIZE` constants stay live (imported by `acquire_pipe` / `p4_race`).
- `p2_cooldown` — STILL LIVE via `p3_target._fetch_index_via_proxy` (index-fetch proxy fallback).
- OT32-33 (sustained loop + box/janitor) describe the superseded fetch mechanic; box_lock + janitor
  + logger are unchanged and still in use.

## Open

- The 27k article-content backfill (the second chained target) is not built. When it is, decide
  whether it uses `run_race` (likely — same race benefit) or needs the sustained machinery back.
- Validation: the race run on the 64 sub-sitemaps is built + reviewed, not yet run at scale on dev.
