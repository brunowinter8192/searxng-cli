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
        "Then write `decisions/pipe_scraper.md` (NEW file, separate from scrape_pipeline.md).",
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
async def main(phase: str) -> None:
    urls = load_urls()
    print(f"Loaded {len(urls)} URLs from {DISCOVERED_URLS}")

    if phase == 'smoke':
        await smoke_test(urls)
    elif phase == 'phase1':
        await phase1_concurrency_sweep(urls)
    else:
        raise ValueError(f"Unknown phase: {phase!r}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Pipe-scraper eval harness')
    parser.add_argument('phase', choices=['smoke', 'phase1'],
                        help='smoke: 1-URL sanity check | phase1: concurrency/WAF sweep')
    args = parser.parse_args()
    asyncio.run(main(args.phase))
