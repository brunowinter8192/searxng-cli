# 63 — CoinDesk proxy-riding engine: src/ port (Stage 1)

Cross-reference: OT61 (`61_coindesk_browser_proxy_riding.md`) — the dev engine that is ported here.
All design decisions (per-context proxy, multi-browser pool, fail-rotation, watchdog) were resolved in
OT61. This file covers ONLY the src/ port mechanics.

## Decision

Port `dev/news_pipeline/coindesk_proxy_riding/` to `src/news/engine/proxy_riding/` as a third, **strictly
additive** scrape engine. `engine/scrape.py` (browser) and `engine/proxy_pool/` (TheBlock) are untouched;
`pipeline.py`, `coindesk/__init__.py`, and `platform.py` are untouched. Stage 1 = engine package only.
Stage 2 = pipeline wiring (`"proxy_riding"` dispatch arm + `RidingScrapeConfig` in `platform.py` +
`.html` reconciliation).

## Package Layout

```
src/news/engine/proxy_riding/
    __init__.py      — empty
    rider.py         — from p2_browser_rider.py  (437 LOC)
    reporter.py      — from p4_reporter.py        (341 LOC)
    scrape.py        — NEW: entry point + adapter  (105 LOC)
```

Not ported (dev-only artefacts):
- `p3_url_sampler.py` — dev measurement helper; prod URLs come from pipeline
- `run_coindesk_riding.py` — dev CLI; prod orchestration is `pipeline.py`
- `p0_pool.py` — duplicate of src/ loader; see pool-loader decision below

## Pool-Loader Decision: REUSE

`dev/p0_pool.py` is a self-contained copy of `src/news/engine/proxy_pool/pool_loaders.py`. Comparison:

| Symbol | dev (p0_pool.py) | src/ |
|---|---|---|
| `load_backfill_pool()` | identical 13-source orchestrator | `pool_loaders.py` — same |
| `proxy_key()` | inline | `proxy_key.py` — same |
| `PersistentCooldownManager` | inline | `cooldown.py` — same (+ `earliest_eligible_at`) |
| `fetch_with_retry()` | inline | `pool_retry.py` — same logic, `_sleep` patchable |
| `_try_source`, `_merge_dedup`, `_fetch_bare_txt`, `_fetch_roosterkid` | inline | same in `pool_loaders.py` |

Decision: **REUSE** — `proxy_riding/` imports `load_backfill_pool` from
`src.news.engine.proxy_pool.pool_loaders` and `PersistentCooldownManager` from
`src.news.engine.proxy_pool.cooldown`. `p0_pool.py` not ported; no duplication introduced.

## Import Fixes (3)

The dev modules used `sys.path.insert(0, str(Path(__file__).parent))` + bare-name imports. All
three fixes are logic-preserving; no behaviour change.

| File | Dev form | Fixed form |
|---|---|---|
| `rider.py` top | `sys.path.insert(…)` + `from p0_pool import PersistentCooldownManager` | removed; `from src.news.engine.proxy_pool.cooldown import PersistentCooldownManager` |
| `rider.py` `_abort_stall` (late import) | `from p4_reporter import write_riding_report` | `from src.news.engine.proxy_riding.reporter import write_riding_report` |
| `reporter.py` top | `sys.path.insert(…)` + `from p2_browser_rider import RiderState, FAIL_THRESHOLD` | removed; `from src.news.engine.proxy_riding.rider import RiderState, FAIL_THRESHOLD` |

Late import in `_abort_stall` is intentional and preserved: `reporter.py` imports from `rider.py`
(RiderState); a top-level cross-import would be circular.

Dev `__main__` smoke block (`if __name__ == "__main__": …`) removed from `rider.py` — prod module,
not a CLI runner.

## scrape_entries_riding — Manifest Adapter + Status Mapping

`scrape_entries_riding(entries, output_dir, riding_cfg) → list[dict]` is the pipeline-facing entry
point. It mirrors the calling convention of `scrape_entries_proxy` (proxy_pool) and `scrape_entries`
(browser):

**Adapter steps:**
1. Build asyncio URL queue from `entries`.
2. `load_backfill_pool()` in executor (blocking network I/O).
3. Filter to `BROWSER_ELIGIBLE_PROTOS = {"http","socks5"}` (socks4 → Playwright instant connect-fail).
4. `random.shuffle(proxy_pool)` — randomise across repos before consumption.
5. `run_riding_pool(…)` → `RiderState`.
6. `_build_manifest(entries, url_to_hash, state)` → manifest.

**Status mapping:**

| Rider job_record status | Condition | Manifest status |
|---|---|---|
| `ok` | file written to `raw/{hash}.html` | `"ok"` |
| `regwall` | re-queued; if never became ok by job end | `"failed"` |
| `connect_fail` | re-queued; if never became ok | `"failed"` |
| `failed` / `empty` | re-queued; if never became ok | `"failed"` |
| (never reached — pool exhausted before URL) | no job_record | `"failed"` |

No `"dead"` status — CoinDesk doesn't 404/410 through proxy; it regwalls. `_build_manifest` iterates
`entries` order (preserving pipeline input order), looks up any `job_record` for that URL with
`status == "ok"` and a written file.

**Manifest contract match** (`{url, hash, status, file, char_count, error}`):
- `url` / `hash` (`sha256[:12]`) — same algorithm as browser and proxy_pool engines
- `status` — `"ok"` or `"failed"` (no `"dead"`)
- `file` — path to `output_dir/raw/{hash}.html` for ok, `None` for failed
- `char_count` — `len(html)` for ok (from `job.char_count`), `None` for failed
- `error` — `None` for ok; last `job.error` or `"not fetched"` for failed

## Random Shuffle at Pool-Load

`random.shuffle(proxy_pool)` applied in `scrape_entries_riding()` after filter, before
`run_riding_pool`. Randomises proxy consumption across repos (raw pool is ordered by source:
monosans → roosterkid → databay → …). **TheBlock unaffected** — TheBlock's `loop.py` calls
`pool_provider()` (= `load_backfill_pool`) directly; `pool_loaders.py` is NOT modified.

## RidingScrapeConfig Defaults

Production-validated values from OT61 Iteration 3 + 4 runs:

| Param | Default | Rationale |
|---|---|---|
| `n_browsers` | 4 | Validated multi-browser pool design (OT61); keeps per-browser C well under 82 renderer ceiling |
| `n_slots` | 64 | 4 browsers × 16 contexts; below single-browser deadlock threshold (128 hangs, 20 works) |
| `stall_timeout_s` | 300.0 | 5 min; tighter than OT61 dev default (3600s) — catches wedge faster |
| `burn_threshold` | 2 | Regwall hits before proxy rotate; validated in OT61 |
| `page_timeout_ms` | 8_000 | Validated in OT61 Iteration 3 runs |

## Known Stage-2 Reconciliation Items

Two hardcoded `.md` paths in `pipeline.py` must be updated before this engine can run through the
full pipeline:

1. `pipeline.py:_run_clean_pass` (line ~359): `raw_path = raw_dir / f"{h}.md"` — needs `.html`
   handling for `proxy_riding` (or dynamic extension from manifest `entry["file"]`).
2. `dedup.py:filter_new_entries` mode `"raw"`: checks `{hash}.md` existence in raw_dir — needs
   `.html` awareness so already-scraped CoinDesk riding files are recognised as deduped.

These are explicit design holes, not bugs. The proxy_riding engine's output is HTML; the existing
engines output markdown. Stage 2 must choose: convert in-engine (write `.md` from crawl4ai markdown
alongside `.html`) or extend the pipeline to handle `.html` natively.

## Stage-1 Smoke Result

Script: `dev/news_pipeline/coindesk_proxy_riding/smoke_stage1.py`
Run: `cd searxng-cli && ./venv/bin/python .claude/worktrees/riding-port/dev/…/smoke_stage1.py`

| Section | Result |
|---|---|
| Import check | PASS — all symbols resolve; defaults verified; no `sys.path` hacks; late import path correct |
| Watchdog deterministic | PASS — pre-aged state + patched `os._exit` → fired, `remaining_urls.txt` (both sections), `job.md` written |
| Live run (10 URLs, 2 slots, 1 browser, 300s stall) | PASS — manifest shape ok (10 entries, all 6 keys, statuses in `{"ok","failed"}`); pool 19,630 browser-eligible; shuffle confirmed; elapsed 305s |

Live run: `ok=0, failed=10` — all free proxies dead at time of run with only 2 slots. Expected at
this scale (free proxies are unreliable; validated throughput in OT61 used 20×6 = 120 slots). Not a
bug; the manifest shape, watchdog, and shuffle are the acceptance criteria, not individual ok counts.
