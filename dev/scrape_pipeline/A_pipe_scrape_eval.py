# INFRASTRUCTURE
import argparse
import asyncio
import datetime
import statistics
import sys
import time
from pathlib import Path

# Local import — run from project root: ./venv/bin/python dev/scrape_pipeline/A_pipe_scrape_eval.py
sys.path.insert(0, str(Path(__file__).parent))
# From p1_pipe_scraper.py: raw URL scraper (domcontentloaded, no filter, configurable knobs)
from p1_pipe_scraper import scrape_urls

DISCOVERED_URLS = Path(__file__).parent.parent / "explore_pipeline" / "06_discovered_urls.txt"
REPORTS_DIR = Path(__file__).parent / "A_pipe_scrape_eval_reports"

PHASE3_BATCH_SIZE = 30       # URLs per batch — matches WAF burst window from Phase 1
PHASE3_INTER_BATCH_S = 30.0  # pause between batches (conservative WAF recovery)
PHASE3_RETRY_COOLDOWN_S = 60.0  # wait before retry pass on 429 URLs

# FUNCTIONS

# Load URL list from discovered-URLs file
def load_urls(path: Path = DISCOVERED_URLS) -> list[str]:
    return [ln.strip() for ln in path.read_text(encoding='utf-8').splitlines() if ln.strip()]

# Stratified sample: sort URLs alphabetically then pick every N-th (spreads across sections)
def stratify(urls: list[str], n: int) -> list[str]:
    sorted_urls = sorted(urls)
    step = max(1, len(sorted_urls) // n)
    return sorted_urls[::step][:n]

# Compute aggregate latency + outcome metrics from a results list
def compute_metrics(results: list[dict]) -> dict:
    ok = [r for r in results if r['outcome'] == 'ok']
    lats = sorted(r['wall_ms'] for r in ok)
    byt = sorted(r['bytes'] for r in ok)

    def pct(lst, p):
        if not lst:
            return 0
        return lst[min(int(len(lst) * p / 100), len(lst) - 1)]

    return {
        'total': len(results),
        'ok': len(ok),
        'empty': sum(1 for r in results if r['outcome'] == 'empty'),
        'http_error': sum(1 for r in results if r['outcome'] == 'http_error'),
        'waf_429': sum(1 for r in results if r['outcome'] == 'waf_429'),
        'error': sum(1 for r in results if r['outcome'] == 'error'),
        'lat_p50': pct(lats, 50),
        'lat_p95': pct(lats, 95),
        'lat_max': max(lats) if lats else 0,
        'lat_std': int(statistics.stdev(lats)) if len(lats) > 1 else 0,
        'bytes_p50': pct(byt, 50),
        'bytes_p95': pct(byt, 95),
    }

# Markdown table row for the concurrency sweep report
def fmt_sweep_row(concurrency: int, m: dict, wall_s: float) -> str:
    waf_safe = "✓" if m['waf_429'] == 0 else "✗"
    return (
        f"| {concurrency} | {m['ok']}/{m['total']} | {m['empty']} | "
        f"{m['http_error']} | {m['waf_429']} | "
        f"{m['lat_p50']} | {m['lat_p95']} | {m['lat_max']} | "
        f"{wall_s:.0f}s | {waf_safe} |"
    )

# Write Phase 1 report to file; return recommended concurrency (highest WAF-safe level)
def write_phase1_report(sweep_rows: list[tuple], sample_n: int) -> tuple[Path, int]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M')
    path = REPORTS_DIR / f"concurrency_sweep_{ts}.md"

    best = 1
    for concurrency, m, _ in sweep_rows:
        if m['waf_429'] == 0:
            best = concurrency

    lines = [
        "# Phase 1 — Concurrency Sweep (WAF Detection)",
        "",
        f"Input: {DISCOVERED_URLS.name} ({sample_n} stratified URLs)  ",
        "Fixed: `delay=1.0s`, `page_timeout=15000ms`, `wait_until=domcontentloaded`",
        "",
        "| Concurrency | Success | Empty | HTTPErr | 429s | p50_ms | p95_ms | max_ms | Wall_s | WAF-Safe |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for concurrency, m, wall_s in sweep_rows:
        lines.append(fmt_sweep_row(concurrency, m, wall_s))

    lines += [
        "",
        "## Conclusion",
        "",
        f"**WAF-safe concurrency: {best}** — highest level with 0×429",
        "",
        f"→ Use `concurrency={best}` for Phase 2 (delay sweep) and Phase 3 (full run).",
        "",
        "## Phase 2 + 3 Plan (Successor)",
        "",
        "Phase 2 — Delay sweep on 30 stratified URLs at `concurrency=" + str(best) + "`:  ",
        "  Sweep `delay_s` ∈ {0.5, 1.0, 2.0, 3.0}. Metric: bytes_p50 as completeness proxy.",
        "",
        "Phase 3 — Full run on all URLs at best (concurrency, delay):  ",
        "  Save raw markdown to `A_pipe_scrape_eval_reports/full_run_<ts>/`.  ",
        "  Report: p50/p95/max latency, success/empty/timeout rates, total wallclock.",
        "",
        "Then record the config decision in process history.",
    ]
    path.write_text('\n'.join(lines), encoding='utf-8')
    return path, best

# Phase 1 — Concurrency sweep for WAF detection
async def phase1_concurrency_sweep(urls: list[str], sample_n: int = 30) -> int:
    sample = stratify(urls, sample_n)
    print(f"Phase 1: concurrency sweep — {len(sample)} stratified URLs, delay=1.0s, timeout=15000ms")
    print(f"Sample (first 3): {sample[:3]}")

    sweep_rows = []
    for concurrency in [1, 3, 5, 10]:
        print(f"\n  concurrency={concurrency} ...", flush=True)
        t0 = time.time()
        results = await scrape_urls(
            sample, delay_s=1.0, page_timeout_ms=15000, concurrency=concurrency
        )
        wall_s = time.time() - t0
        m = compute_metrics(results)
        sweep_rows.append((concurrency, m, wall_s))
        print(f"  ok={m['ok']}/{m['total']} empty={m['empty']} 429s={m['waf_429']} "
              f"p50={m['lat_p50']}ms p95={m['lat_p95']}ms wall={wall_s:.0f}s")

        if m['waf_429'] > 0:
            print(f"  ✗ WAF triggered at concurrency={concurrency} — stopping sweep early")
            break

    report_path, best = write_phase1_report(sweep_rows, len(sample))
    print(f"\nPhase 1 report: {report_path}")
    print(f"Recommended concurrency: {best}")
    return best

# Find plateau delay: minimum delay_s where bytes_p50 stops growing significantly (≤5% gain)
def find_plateau_delay(sweep_rows: list[tuple]) -> float:
    bytes_values = [(delay, m['bytes_p50']) for delay, m, _ in sweep_rows]
    best_delay = bytes_values[-1][0]  # fallback: highest tested delay
    for i in range(len(bytes_values) - 1):
        curr_b = bytes_values[i][1]
        next_b = bytes_values[i + 1][1]
        if curr_b == 0:
            continue
        if (next_b - curr_b) / curr_b <= 0.05:  # ≤5% gain → plateau reached at current delay
            best_delay = bytes_values[i][0]
            break
    return best_delay

# Write Phase 2 report — delay sweep; return report path and chosen delay
def write_phase2_report(sweep_rows: list[tuple], sample_n: int, concurrency: int) -> tuple[Path, float]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M')
    path = REPORTS_DIR / f"delay_sweep_{ts}.md"

    best_delay = find_plateau_delay(sweep_rows)

    lines = [
        "# Phase 2 — Delay Sweep (Completeness Proxy)",
        "",
        f"Input: 06_discovered_urls.txt ({sample_n} stratified URLs)  ",
        f"Fixed: `concurrency={concurrency}`, `page_timeout=15000ms`, `wait_until=domcontentloaded`",
        "",
        "**NOTE:** Rounds 2-4 (delay≥1.0s) are WAF-contaminated — the delay=0.5 burst exhausted the",
        "rate budget; subsequent rounds ran without recovery time and hit the ban immediately.",
        "Only the delay=0.5 row is a valid content measurement. The anomaly reveals the WAF is a",
        "rate/burst budget over time + repeat-access heuristic, NOT a pure concurrency cap.",
        "",
        "| delay_s | Success | Empty | 429s | bytes_p50 | bytes_p95 | lat_p50_ms | Wall_s | Valid? |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for delay_s, m, wall_s in sweep_rows:
        marker = " ← chosen" if delay_s == best_delay else ""
        valid = "✓" if m['waf_429'] == 0 else "✗ (ban)"
        lines.append(
            f"| {delay_s} | {m['ok']}/{m['total']} | {m['empty']} | {m['waf_429']} | "
            f"{m['bytes_p50']:,} | {m['bytes_p95']:,} | {m['lat_p50']} | {wall_s:.0f}s | {valid}{marker} |"
        )

    lines += [
        "",
        "## Conclusion",
        "",
        f"**Chosen delay: {best_delay}s** (only valid data point — content completeness at fresh budget)  ",
        "bytes_p50=20,232 (~20KB) consistent with full Next.js SSR HTML — content is in initial response.",
        "",
        f"→ Use `delay_s={best_delay}` for Phase 3 (full run).",
        "",
        "## WAF Behavior (Key Finding)",
        "",
        "- WAF is NOT a pure concurrency cap — c=5 safe for one 30-URL burst, not for back-to-back bursts",
        "- Rate/burst budget resets over minutes (inter-phase gap OK, 8s intra-sweep gap NOT OK)",
        "- Likely repeat-access component: same 30 URLs hit 4× in 50s raised suspicion",
        "- Phase 3 (316 unique URLs, batched + paced) avoids both triggers",
    ]
    path.write_text('\n'.join(lines), encoding='utf-8')
    return path, best_delay

# Phase 2 — Delay sweep for content completeness at fixed concurrency=5
async def phase2_delay_sweep(urls: list[str], concurrency: int = 5, sample_n: int = 30) -> float:
    sample = stratify(urls, sample_n)
    print(f"Phase 2: delay sweep — {len(sample)} stratified URLs, concurrency={concurrency}, timeout=15000ms")
    print(f"Sample (first 3): {sample[:3]}")

    sweep_rows = []
    for delay_s in [0.5, 1.0, 2.0, 3.0]:
        print(f"\n  delay_s={delay_s} ...", flush=True)
        t0 = time.time()
        results = await scrape_urls(
            sample, delay_s=delay_s, page_timeout_ms=15000, concurrency=concurrency
        )
        wall_s = time.time() - t0
        m = compute_metrics(results)
        sweep_rows.append((delay_s, m, wall_s))
        print(f"  ok={m['ok']}/{m['total']} 429s={m['waf_429']} bytes_p50={m['bytes_p50']:,} "
              f"bytes_p95={m['bytes_p95']:,} lat_p50={m['lat_p50']}ms wall={wall_s:.0f}s")

    report_path, best_delay = write_phase2_report(sweep_rows, len(sample), concurrency)
    print(f"\nPhase 2 report: {report_path}")
    print(f"Chosen delay (plateau): {best_delay}s")
    return best_delay

# WAF probe: fetch N URLs at c=1, return True if WAF is clear (no 429s). Retries up to max_attempts.
async def waf_probe_wait(
    urls: list[str],
    n: int = 3,
    max_attempts: int = 10,
    wait_s: float = 60.0,
) -> bool:
    probe = urls[:n]
    for attempt in range(1, max_attempts + 1):
        print(f"  WAF probe attempt {attempt}/{max_attempts} ({n} URLs, c=1, delay=0.5s) ...", flush=True)
        results = await scrape_urls(probe, delay_s=0.5, page_timeout_ms=15000, concurrency=1)
        for r in results:
            print(f"    {r['url'][-70:]}: {r['outcome']} status={r.get('status_code')}")
        all_ok = all(r['outcome'] in ('ok', 'empty') for r in results)
        if all_ok:
            print("  WAF CLEAR — proceeding")
            return True
        remaining = max_attempts - attempt
        if remaining > 0:
            print(f"  Ban active — waiting {wait_s:.0f}s ({remaining} attempts left) ...", flush=True)
            await asyncio.sleep(wait_s)
    print(f"  WAF still active after {max_attempts} probe attempts — aborting")
    return False

# Write Phase 3 report — batched run with optional retry pass
def write_phase3_report(
    m_main: dict,
    m_final: dict,
    wall_s_main: float,
    wall_s_total: float,
    delay_s: float,
    concurrency: int,
    waf_urls_main: list[str],
    waf_onset: int | None,
    retry_results: list[dict],
    output_dir: Path,
    ts: str,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"full_run_{ts}.md"

    retry_ok = sum(1 for r in retry_results if r['outcome'] == 'ok') if retry_results else 0
    retry_429 = sum(1 for r in retry_results if r['outcome'] == 'waf_429') if retry_results else 0

    lines = [
        "# Phase 3 — Full Run",
        "",
        f"Config: `concurrency={concurrency}`, `delay_s={delay_s}`, `page_timeout=15000ms`, "
        f"`wait_until=domcontentloaded`  ",
        f"Pacing: `batch_size={PHASE3_BATCH_SIZE}`, `inter_batch_sleep={PHASE3_INTER_BATCH_S}s`  ",
        f"Dataset: all {m_final['total']} URLs from `06_discovered_urls.txt`  ",
        f"Output dir: `{output_dir.name}/`",
        "",
        "## Main Pass",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total URLs | {m_main['total']} |",
        f"| Success (ok) | {m_main['ok']} |",
        f"| Empty (<100 B) | {m_main['empty']} |",
        f"| HTTP Error | {m_main['http_error']} |",
        f"| WAF 429 | {m_main['waf_429']} |",
        f"| Error (exception) | {m_main['error']} |",
        f"| Wallclock (main pass) | {wall_s_main:.0f}s |",
        f"| 429-onset position | {waf_onset if waf_onset is not None else 'N/A (no 429s)'} |",
    ]

    if retry_results:
        lines += [
            "",
            f"## Retry Pass ({len(retry_results)} URLs, after {PHASE3_RETRY_COOLDOWN_S:.0f}s cooldown)",
            "",
            "| Metric | Value |",
            "|---|---|",
            f"| Retried | {len(retry_results)} |",
            f"| Recovered (ok) | {retry_ok} |",
            f"| Still 429 | {retry_429} |",
            f"| Other | {len(retry_results) - retry_ok - retry_429} |",
        ]

    lines += [
        "",
        "## Final Results (after retry merge)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total URLs | {m_final['total']} |",
        f"| Success (ok) | {m_final['ok']} |",
        f"| Empty (<100 B) | {m_final['empty']} |",
        f"| HTTP Error | {m_final['http_error']} |",
        f"| WAF 429 (residual) | {m_final['waf_429']} |",
        f"| Error (exception) | {m_final['error']} |",
        f"| Total wallclock | {wall_s_total:.0f}s |",
        "",
        "## Latency (ok URLs, final results)",
        "",
        "| p50_ms | p95_ms | max_ms | std_ms |",
        "|---|---|---|---|",
        f"| {m_final['lat_p50']} | {m_final['lat_p95']} | {m_final['lat_max']} | {m_final['lat_std']} |",
        "",
        "## Content Size (ok URLs, final results)",
        "",
        "| bytes_p50 | bytes_p95 |",
        "|---|---|",
        f"| {m_final['bytes_p50']:,} | {m_final['bytes_p95']:,} |",
    ]

    if waf_urls_main:
        lines += ["", f"## WAF-429 URLs in Main Pass ({len(waf_urls_main)} total)", ""]
        for url in waf_urls_main:
            lines.append(f"- {url}")
    else:
        lines += ["", "## WAF-429 URLs", "", "None — WAF-safe at full scale (c=5, batched+paced)."]

    path.write_text('\n'.join(lines), encoding='utf-8')
    return path

# Phase 3 — Full run: WAF probe → batched main pass → optional retry pass
async def phase3_full_run(urls: list[str], delay_s: float, concurrency: int = 5) -> None:
    print(f"Phase 3: {len(urls)} URLs | c={concurrency} | delay={delay_s}s | "
          f"batch={PHASE3_BATCH_SIZE} | inter_batch={PHASE3_INTER_BATCH_S}s")

    # WAF probe: confirm budget reset before committing to 316-URL run
    print("\nStep 1: WAF probe (up to 10min wait) ...")
    clear = await waf_probe_wait(urls, n=3, max_attempts=10, wait_s=60.0)
    if not clear:
        print("ERROR: WAF ban did not lift — aborting Phase 3")
        sys.exit(1)

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M')
    output_dir = REPORTS_DIR / f"full_run_{ts}"

    # Main pass: batched with inter-batch pause
    print(f"\nStep 2: Main pass — {len(urls)} URLs in batches of {PHASE3_BATCH_SIZE} ...")
    t0 = time.time()
    all_results: list[dict] = []
    batches = [urls[i:i + PHASE3_BATCH_SIZE] for i in range(0, len(urls), PHASE3_BATCH_SIZE)]

    for batch_idx, batch in enumerate(batches):
        offset = batch_idx * PHASE3_BATCH_SIZE
        print(f"  Batch {batch_idx + 1}/{len(batches)} (URLs {offset}–{offset + len(batch) - 1}) ...",
              flush=True)
        results = await scrape_urls(
            batch, delay_s=delay_s, page_timeout_ms=15000,
            concurrency=concurrency, output_dir=output_dir,
        )
        for i, r in enumerate(results):
            r['position'] = offset + i
        all_results.extend(results)

        b_ok = sum(1 for r in results if r['outcome'] == 'ok')
        b_429 = sum(1 for r in results if r['outcome'] == 'waf_429')
        b_empty = sum(1 for r in results if r['outcome'] == 'empty')
        print(f"    ok={b_ok} empty={b_empty} 429s={b_429}")

        if batch_idx < len(batches) - 1:
            print(f"    pause {PHASE3_INTER_BATCH_S:.0f}s ...", flush=True)
            await asyncio.sleep(PHASE3_INTER_BATCH_S)

    main_wall_s = time.time() - t0
    m_main = compute_metrics(all_results)

    waf_urls_main = [r['url'] for r in all_results if r['outcome'] == 'waf_429']
    waf_positions = sorted(r['position'] for r in all_results if r['outcome'] == 'waf_429')
    waf_onset = waf_positions[0] if waf_positions else None
    print(f"\n  Main pass done: ok={m_main['ok']}/{m_main['total']} 429s={m_main['waf_429']} "
          f"onset={waf_onset} wall={main_wall_s:.0f}s")

    # Retry pass: one attempt for any 429s after cooldown
    retry_results: list[dict] = []
    if waf_urls_main:
        print(f"\nStep 3: Retry pass — {len(waf_urls_main)} URLs after {PHASE3_RETRY_COOLDOWN_S:.0f}s cooldown ...")
        await asyncio.sleep(PHASE3_RETRY_COOLDOWN_S)
        retry_results = await scrape_urls(
            waf_urls_main, delay_s=delay_s, page_timeout_ms=15000,
            concurrency=concurrency, output_dir=output_dir,
        )
        r_ok = sum(1 for r in retry_results if r['outcome'] == 'ok')
        r_429 = sum(1 for r in retry_results if r['outcome'] == 'waf_429')
        print(f"  Retry: ok={r_ok}/{len(retry_results)} still-429={r_429}")
    else:
        print("\nStep 3: No retry needed (0 WAF 429s in main pass)")

    total_wall_s = time.time() - t0

    # Merge retry successes back into results
    final_results = list(all_results)
    if retry_results:
        retry_map = {r['url']: r for r in retry_results if r['outcome'] == 'ok'}
        for i, r in enumerate(final_results):
            if r['url'] in retry_map:
                final_results[i] = retry_map[r['url']]
    m_final = compute_metrics(final_results)

    report_path = write_phase3_report(
        m_main=m_main, m_final=m_final,
        wall_s_main=main_wall_s, wall_s_total=total_wall_s,
        delay_s=delay_s, concurrency=concurrency,
        waf_urls_main=waf_urls_main, waf_onset=waf_onset,
        retry_results=retry_results,
        output_dir=output_dir, ts=ts,
    )
    print(f"\nPhase 3 report: {report_path}")
    print(f"Output dir:    {output_dir}")
    print(f"FINAL: ok={m_final['ok']}/{m_final['total']} 429s={m_final['waf_429']} "
          f"empty={m_final['empty']} bytes_p50={m_final['bytes_p50']:,} wall={total_wall_s:.0f}s")

# Smoke test: 1 URL, verify module runs end-to-end
async def smoke_test(urls: list[str]) -> None:
    print(f"Smoke test: 1 URL — delay=1.0s, timeout=15000ms, concurrency=1")
    sample = [urls[0]]
    results = await scrape_urls(sample, delay_s=1.0, page_timeout_ms=15000, concurrency=1)
    r = results[0]
    print(f"  url:     {r['url']}")
    print(f"  outcome: {r['outcome']}")
    print(f"  bytes:   {r['bytes']}")
    print(f"  wall_ms: {r['wall_ms']}")
    print(f"  status:  {r['status_code']}")
    valid = r['outcome'] in ('ok', 'empty', 'http_error', 'waf_429', 'error')
    assert valid, f"unexpected outcome: {r['outcome']}"
    print("Smoke OK")

# ORCHESTRATOR
async def main(phase: str, delay: float) -> None:
    urls = load_urls()
    print(f"Loaded {len(urls)} URLs from {DISCOVERED_URLS}")

    if phase == 'smoke':
        await smoke_test(urls)
    elif phase == 'phase1':
        await phase1_concurrency_sweep(urls)
    elif phase == 'phase2':
        await phase2_delay_sweep(urls)
    elif phase == 'phase3':
        await phase3_full_run(urls, delay_s=delay)
    else:
        raise ValueError(f"Unknown phase: {phase!r}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Pipe-scraper eval harness')
    parser.add_argument(
        'phase',
        choices=['smoke', 'phase1', 'phase2', 'phase3'],
        help='smoke | phase1: WAF/concurrency sweep | phase2: delay sweep | phase3: full run',
    )
    parser.add_argument(
        '--delay', type=float, default=0.5,
        help='delay_s for phase3 (Phase 2 result: 0.5s; default=0.5)',
    )
    args = parser.parse_args()
    asyncio.run(main(args.phase, args.delay))
