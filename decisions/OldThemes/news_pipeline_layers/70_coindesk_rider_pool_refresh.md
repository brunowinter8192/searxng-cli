# 70 — CoinDesk rider: 60-min pool refresh

**Branch:** `riding-report-trim`.
Cross-reference: OT65 (`65_coindesk_rider_tail_race.md`) — initial pool load + scrape.py structure.
OT68 (`68_coindesk_jobmd_reshape.md`) — eligible-pool-over-time metric added to job.md; the refresh
will now appear as eligible-pool jumps in the 10-min window table.

## Problem

`scrape_entries_riding` (`scrape.py`) loads the pool once at job start via `load_backfill_pool()`,
filters to `BROWSER_ELIGIBLE_PROTOS = {"http","socks5"}`, shuffles. The pool snapshot is static for
the entire run.

The risk over a multi-hour backfill (~74 h projected) is NOT hard exhaustion. The 60-min cooldown
recycles burned proxies, so the eligible set reaches a steady state (~`burn_rate × cooldown_window`
in cooldown at any moment) and never hits zero. Measured: the 2251 s / ~500-URL run burned 9559
proxies ≈ **255/min** (NOT 64 — 64 is `n_slots`, not a rate), and eligible bottomed at ~16k of ~26k —
no exhaustion in that window.

The real risk is **live-fraction decay**. The static snapshot's live proxies die over the hours, while
the source lists rotate in new live proxies the rider can never pull in. Cooldown recycling only
re-tries the SAME (increasingly dead) proxies — it adds no fresh supply. So over a long run the live
fraction of the eligible set monotonically drops → more wasted fetches on dead proxies → throughput
degrades. A 60-min re-fetch re-aligns the pool with the current live source-list state (drops proxies
that died and fell off the lists, adds new ones), holding the live fraction up. The eligible-pool
metric (OT68) makes this visible: each refresh shows as an eligible jump in the 10-min window table.

TheBlock's `proxy_pool` engine refreshes every 60 min via `pool_provider()` in `run_loop` (OT reference:
`src/news/engine/proxy_pool/loop.py`, `REFRESH_INTERVAL_S = 3600`). The rider had no equivalent.

## Mechanism

### Import structure — pool_provider callable

`rider.py` cannot import from `scrape.py` (circular: `scrape.py` → `rider.py` at top level). Instead,
`scrape.py` defines a shared async helper `_pool_provider()` and passes it as a callable to
`run_riding_pool`. The rider watchdog calls `await state.pool_provider()` at refresh time — no import
of `scrape.py` from `rider.py` at any level.

### `_pool_provider()` — `scrape.py`

```python
async def _pool_provider() -> list[tuple[str, str]]:
    loop        = asyncio.get_running_loop()
    raw_pool, _ = await loop.run_in_executor(None, load_backfill_pool)
    pool        = [(p, hp) for p, hp in raw_pool if p in BROWSER_ELIGIBLE_PROTOS]
    random.shuffle(pool)
    return pool
```

Used for BOTH initial load (`proxy_pool = await _pool_provider()` at scrape start) AND as the
`pool_provider` arg to `run_riding_pool`. Single code path — init and refresh stay in sync on filter
and shuffle without any duplication.

### `RiderState` + `run_riding_pool` — `rider.py`

`RiderState` gains `pool_provider: object = None` (optional, default None = static pool — backward
compatible). `run_riding_pool` gains `pool_provider=None` param threaded to state. `POOL_REFRESH_INTERVAL_S = 3600.0` constant in INFRASTRUCTURE (mirrors `loop.py`'s `REFRESH_INTERVAL_S`).

### Refresh in `_watchdog` — poll loop order

```
await asyncio.sleep(interval)
1. append pool sample
2. if pool_provider and monotonic() - _last_refresh_mono >= POOL_REFRESH_INTERVAL_S:
       new_pool = await state.pool_provider()
       if new_pool:
           state.proxy_pool = new_pool          ← atomic single assignment
           _last_refresh_mono = time.monotonic()
           log("pool refresh: {old_n} → {new_n} proxies")
       else:
           log("pool refresh returned empty — keeping current pool")
3. if all_resolved: (clean return or _abort_done)
4. if idle > stall_timeout_s: _abort_stall
```

`_last_refresh_mono = time.monotonic()` captured before the `while True` loop — at watchdog start,
which is approximately job start (constructed immediately after `run_riding_pool` begins).

**Atomic replace safety:** `state.proxy_pool = new_pool` is a single STORE_ATTR bytecode. asyncio is
single-threaded and cooperative: while `await state.pool_provider()` suspends the watchdog, slot tasks
run and read the OLD `state.proxy_pool` through `_next_proxy` / `eligible_candidates`. After the await
returns, the assignment executes without interruption before any slot resumes. `proxy_cursor` uses
`% len(eligible)` (from `eligible_candidates` on the new pool) — wraps naturally. No `proxy_lock`
needed: the lock guards cursor advancement only, not the pool reference.

**`cooldown_mgr` persistence:** not reset on refresh. A burned proxy that reappears in the new list
stays excluded by `eligible_candidates` until its 60-min cooldown expires. This is correct — a proxy
burned in this job was unreliable; its slot in the new source list doesn't undo that.

**`run_in_executor` cadence:** `load_backfill_pool()` takes ~1 s (multi-source HTTP fetches run in a
thread via `run_in_executor(None, …)`). During that 1 s the watchdog coroutine is suspended; slot tasks
run normally. Stall detection is time-based — a 1 s delay in one poll iteration is immaterial.

**Empty pool guard:** `if new_pool:` — if all sources fail (network outage), skip assignment, log
warning, keep current pool. Prevents a failed refresh from clearing the pool.

### Eligible-pool metric (OT68)

`state.pool_samples` is appended BEFORE the refresh check (step 1). The pre-refresh eligible count
is recorded; the new count appears in the NEXT poll sample. In the 10-min window table the refresh
shows as a jump in `avg_eligible` / `min_eligible` — exactly the intended signal.

## Test

`test_7_watchdog_pool_refresh` added to `dev/news_pipeline/coindesk_proxy_riding/test_tail_race.py`:

- `pool_a` (2 entries) → initial `state.proxy_pool`.
- `mock_provider` async callable → returns `pool_b` (3 entries); `refresh_count[0]` incremented.
- `POOL_REFRESH_INTERVAL_S` patched to `0.0` → first poll always satisfies the interval check.
- `state.done_urls = {url_done}`, `all_resolved=True`, `in_flight=0` → watchdog returns cleanly after refresh.
- `poll_interval=0.05 s` → test completes in ~50 ms.
- Assertions: `refresh_count[0] >= 1`; `state.proxy_pool is pool_b` (identity — same object returned by provider).
- Result: PASS (7/7 total).
