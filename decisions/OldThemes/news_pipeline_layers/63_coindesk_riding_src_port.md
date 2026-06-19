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

## Stage 2 — pipeline wiring

Commit `3f95417` on branch `riding-wire`. Five files changed.

### Config pattern: getattr, not Protocol

`riding_scrape_config` is NOT added to the `Platform` Protocol. Adding it would require all platform
classes (TheBlock) to define the attr. Instead: `pipeline.py:run_scrape_only` consumes it via
`getattr(platform, "riding_scrape_config", None) or RidingScrapeConfig()`. Only CoinDesk defines the
attr. TheBlock is untouched. This differs from `proxy_scrape_config` (which IS in the Protocol) — the
tradeoff is fewer files changed vs type-checker visibility; the pattern is analogous to `timeframe`
and `uses_master_list` (also consumed via getattr).

### scrape.py signature tweak

`scrape_entries_riding` now returns `tuple[list[dict], RiderState]` (was `list[dict]`). Change: last
line becomes `return _build_manifest(entries, url_to_hash, state), state`. Required because
`pipeline.py` needs `RiderState` to call `write_riding_report` — without state, the only alternative
was `browser_reporter.write_scrape_report`, which crashes on riding manifests (see below).

### browser_reporter crash finding

`write_scrape_report` (`browser_reporter.py`) is incompatible with riding manifests. Its
`_compute_stats` builds `ok_completion_s` via `(r["t_chunk_start"] − t_job_start).total_seconds() +
r["elapsed_s"]` — riding manifest entries have neither `t_chunk_start` nor `elapsed_s`, so this
raises `TypeError`. The riding path routes to `write_riding_report(state, job_dir, t_job_start)`
from `proxy_riding/reporter.py` instead (full riding stats: browsers, contexts, ride-lengths,
regwall-by-position). The browser path retains `write_scrape_report` unchanged.

### run_scrape_only proxy_riding branch

In `pipeline.py:run_scrape_only`, after dedup:

```
if platform.scrape_engine == "proxy_riding":
    riding_cfg = getattr(platform, "riding_scrape_config", None) or RidingScrapeConfig()
    manifest, state = await scrape_entries_riding(new_entries, platform_dir, riding_cfg)
    _append_to_raw_manifest(raw_dir, ok_manifest_entries)
    write_riding_report(state, job_dir, t_job_start)
else:
    # browser path — byte-identical, indentation only
    chunks = scrape_chunks_raw(...)
    write_scrape_report(...)
```

Key design decisions:
- **Chunk bypass:** `scrape_chunks_raw` is NOT called. The riding engine manages its own concurrency,
  watchdog, and requeue loop. The full entry set is passed directly to `scrape_entries_riding`.
- **`platform_dir` vs `raw_dir` as output_dir:** `rider.py:_write_raw` writes to
  `output_dir / "raw" / f"{hash}.html"`. Pipeline passes `platform_dir = DATA_ROOT / platform.name`
  (not `raw_dir`) so HTML lands at `data/news/coindesk/raw/{hash}.html` — same path dedup checks.
  (During smoke, `raw_dir` was incorrectly passed first; files landed at `raw/raw/`; corrected before
  re-run.)
- **Manifest JSONL:** `_append_to_raw_manifest(raw_dir, ok_manifest_entries)` appends
  `{hash,url,publication_date}` for ok entries to `raw/manifest.jsonl` — same as browser path.

### CoinDesk wiring

`coindesk/__init__.py`:
- `scrape_engine = "proxy_riding"` (was `"browser"`)
- `riding_scrape_config = RidingScrapeConfig()` — production defaults (C=64, 4 browsers, 300s stall,
  burn=2, 8s page timeout) validated in OT61 Iterations 3+4. No custom values needed.

### Dedup raw_ext mechanism

`filter_new_entries` in `dedup.py` gains `raw_ext: str = ".md"` parameter. The `mode="raw"` branch:
`(collection_dir / f"{h}{raw_ext}").exists()`. All existing callers (both `run_pipeline` arms) pass
no `raw_ext` → default `.md` → byte-identical. `run_scrape_only` sets
`raw_ext = ".html" if platform.scrape_engine == "proxy_riding" else ".md"` before the dedup call.
This ensures the dedup correctly skips already-scraped CoinDesk `.html` files on re-run while leaving
browser `.md` dedup unchanged.

### _run_clean_pass scope

`_run_clean_pass` is called ONLY from `run_pipeline`'s `proxy_pool` branch (line 218). CoinDesk uses
`run_scrape_only` exclusively — `_run_clean_pass` is never reached in CoinDesk's prod path. OT63
(Stage 1) flagged it as a reconciliation item; confirmed out of scope for Stage 2. It would only
matter if CoinDesk gained a clean-pass step (not planned).

### Prod-path smoke result

Run: `python -m src.news --source coindesk --scrape-only --year 2024 --limit 5`

| Check | Result |
|---|---|
| Riding branch dispatched | `=== scrape-only done (proxy_riding): ok=5 failed=0 wall=311s ===` — no "chunked plan" line |
| Raw `.html` written | 5 files at `data/news/coindesk/raw/{hash}.html` |
| Riding job.md written | `scrape_jobs/20260619T200059Z/job.md` — Termination: `all-done`, OK: 5 |
| Re-run dedup-skips | `dedup → 5 total, 5 already in raw, 0 new` → `All already in raw — done.` |

Resumability confirmed: the `.html` dedup extension check skips already-scraped URLs on re-run.

### Port status

**COMPLETE.** Stage 1 (engine package) + Stage 2 (pipeline wiring) done.
Stage 3 = operator prod 500-run validation with full proxy pool.

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
