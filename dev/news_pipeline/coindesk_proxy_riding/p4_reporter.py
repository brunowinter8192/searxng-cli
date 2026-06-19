# INFRASTRUCTURE

import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from p2_browser_rider import RiderState

_BACKFILL_TOTAL = 61_000


# ORCHESTRATOR

# Write job.md + three plots for a proxy-riding scrape run to job_dir.
def write_riding_report(state: RiderState, job_dir: Path, t_job_start: datetime) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    stats = _compute_stats(state, t_job_start)
    _write_cumulative_plot(job_dir, stats)
    _write_ride_length_plot(job_dir, stats)
    _write_regwall_position_plot(job_dir, stats)
    _write_md(job_dir, state, stats, t_job_start)


# FUNCTIONS

# Derive all metrics from RiderState and job start time.
def _compute_stats(state: RiderState, t_job_start: datetime) -> dict:
    jobs  = state.job_records
    rides = state.ride_records

    n_total_fetches   = len(jobs)
    n_ok              = sum(1 for j in jobs if j.status == "ok")
    n_regwall_fetches = sum(1 for j in jobs if j.status == "regwall")
    n_failed          = sum(1 for j in jobs if j.status in ("failed", "empty"))
    # connect_fail breaks before job_records.append() → use authoritative state counter
    n_connect_fail    = state.n_connect_fail

    elapsed_values = [j.elapsed_s for j in jobs if j.elapsed_s is not None]
    mean_s   = statistics.mean(elapsed_values)   if elapsed_values else None
    median_s = statistics.median(elapsed_values) if elapsed_values else None

    wall_s       = (datetime.now(timezone.utc) - t_job_start).total_seconds()
    urls_per_min = (n_ok / wall_s * 60)                    if wall_s > 0 and n_ok else None
    backfill_h   = (_BACKFILL_TOTAL / urls_per_min / 60)   if urls_per_min         else None

    ok_html_sizes = sorted(
        j.char_count for j in jobs if j.status == "ok" and j.char_count is not None
    )
    html_pct = _percentiles(ok_html_sizes)

    ok_md_lens = sorted(
        j.markdown_len for j in jobs
        if j.status == "ok" and getattr(j, "markdown_len", None) is not None
    )
    md_pct = _percentiles(ok_md_lens)

    ok_completion_s = sorted(
        (j.t_start - t_job_start).total_seconds() + (j.elapsed_s or 0)
        for j in jobs if j.status == "ok" and j.elapsed_s is not None
    )

    ride_lengths   = [r.n_urls_attempted for r in rides]
    ride_ok_counts = [r.n_ok             for r in rides]
    ride_len_stats = _distribution_stats(ride_lengths)

    n_proxies_burned     = len(rides)
    proxies_for_backfill = round(n_proxies_burned / max(n_ok, 1) * _BACKFILL_TOTAL)

    # Regwall rate by ride position (position = URL index within a proxy ride)
    rw_by_pos:    dict[int, int] = {}
    total_by_pos: dict[int, int] = {}
    for j in jobs:
        pos = j.ride_position
        total_by_pos[pos] = total_by_pos.get(pos, 0) + 1
        if j.status == "regwall":
            rw_by_pos[pos] = rw_by_pos.get(pos, 0) + 1
    max_pos = max(total_by_pos.keys()) if total_by_pos else 0
    regwall_rate_by_pos = {
        pos: rw_by_pos.get(pos, 0) / total_by_pos[pos]
        for pos in range(1, max_pos + 1)
        if total_by_pos.get(pos, 0) > 0
    }

    # Retry outcome: among URLs that saw at least one regwall, final status
    url_final: dict[str, str] = {}
    url_rw:    set[str]       = set()
    for j in jobs:
        url_final[j.url] = j.status
        if j.status == "regwall":
            url_rw.add(j.url)
    retried_ok     = sum(1 for u in url_rw if url_final[u] == "ok")
    retried_failed = len(url_rw) - retried_ok
    wasted_ratio   = n_regwall_fetches / max(n_total_fetches, 1)

    return {
        "n_ok": n_ok, "n_regwall_fetches": n_regwall_fetches,
        "n_failed": n_failed, "n_connect_fail": n_connect_fail,
        "n_total_fetches": n_total_fetches,
        "wall_s": wall_s, "mean_s": mean_s, "median_s": median_s,
        "urls_per_min": urls_per_min, "backfill_h": backfill_h,
        "html_pct": html_pct, "md_pct": md_pct,
        "ok_completion_s": ok_completion_s,
        "ride_lengths": ride_lengths, "ride_ok_counts": ride_ok_counts,
        "ride_len_stats": ride_len_stats,
        "n_proxies_burned": n_proxies_burned,
        "proxies_for_backfill": proxies_for_backfill,
        "regwall_rate_by_pos": regwall_rate_by_pos,
        "retried_ok": retried_ok, "retried_failed": retried_failed,
        "n_urls_with_regwall": len(url_rw),
        "wasted_ratio": wasted_ratio,
        "termination": state.termination,
    }


# Compute p10/p25/p50/p75/p90/p95 from a sorted list; return None if empty.
def _percentiles(sorted_values: list) -> dict | None:
    n = len(sorted_values)
    if n == 0:
        return None
    if n == 1:
        return {k: sorted_values[0] for k in ("p10", "p25", "p50", "p75", "p90", "p95")}
    qs = statistics.quantiles(sorted_values, n=100, method="inclusive")
    return {
        "p10": int(round(qs[9])),  "p25": int(round(qs[24])), "p50": int(round(qs[49])),
        "p75": int(round(qs[74])), "p90": int(round(qs[89])), "p95": int(round(qs[94])),
    }


# Compute mean/median/min/max of a list; return None-filled dict if empty.
def _distribution_stats(values: list) -> dict:
    if not values:
        return {"mean": None, "median": None, "min": None, "max": None}
    return {
        "mean":   round(statistics.mean(values),   2),
        "median": round(statistics.median(values), 2),
        "min":    min(values),
        "max":    max(values),
    }


# Step-plot of cumulative OK fetches vs elapsed seconds; save as cumulative.png.
def _write_cumulative_plot(job_dir: Path, stats: dict) -> None:
    import matplotlib.pyplot as plt

    xs = stats["ok_completion_s"]
    x  = [0.0] + xs if xs else [0.0]
    y  = list(range(len(x)))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.step(x, y, where="post", linewidth=1.5)
    ax.set_xlabel("Elapsed (s)")
    ax.set_ylabel("Cumulative OK fetches")
    ax.set_title("Cumulative OK fetches over time")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(job_dir / "cumulative.png", dpi=100)
    plt.close(fig)


# Histogram of n_urls_attempted per proxy ride; save as ride_lengths.png.
def _write_ride_length_plot(job_dir: Path, stats: dict) -> None:
    import matplotlib.pyplot as plt

    lengths = stats["ride_lengths"]
    fig, ax = plt.subplots(figsize=(8, 4))
    if lengths:
        bins = list(range(0, max(lengths) + 2))
        ax.hist(lengths, bins=bins, edgecolor="black", alpha=0.8)
    ax.set_xlabel("URLs attempted per proxy ride")
    ax.set_ylabel("Number of rides")
    ax.set_title("Proxy ride length distribution")
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(job_dir / "ride_lengths.png", dpi=100)
    plt.close(fig)


# Bar chart of regwall rate by ride position; save as regwall_position.png.
def _write_regwall_position_plot(job_dir: Path, stats: dict) -> None:
    import matplotlib.pyplot as plt

    rwp = stats["regwall_rate_by_pos"]
    fig, ax = plt.subplots(figsize=(8, 4))
    if rwp:
        positions = sorted(rwp.keys())
        rates     = [rwp[p] * 100 for p in positions]
        ax.bar(positions, rates, edgecolor="black", alpha=0.8)
    ax.set_xlabel("Ride position (URL index within proxy)")
    ax.set_ylabel("Regwall rate (%)")
    ax.set_title("Regwall rate vs ride position")
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(job_dir / "regwall_position.png", dpi=100)
    plt.close(fig)


# Write job.md with all metrics, tables, failure lists, and plot links.
def _write_md(
    job_dir: Path, state: RiderState, stats: dict, t_job_start: datetime,
) -> None:
    def _fmt(v, spec="", unit="") -> str:
        return f"{format(v, spec)}{unit}" if v is not None else "—"

    job_id   = t_job_start.strftime("%Y%m%dT%H%M%SZ")
    rw_rate  = stats["n_regwall_fetches"] / max(stats["n_total_fetches"], 1)
    rls      = stats["ride_len_stats"]

    lines = [
        f"# CoinDesk riding job — {job_id}",
        "",
        "## Counts",
        "",
        "| Status | Count |",
        "|---|---|",
        f"| Target URLs | {state.total_urls} |",
        f"| Browsers | {state.n_browsers} |",
        f"| Contexts/browser | {state.n_slots // max(state.n_browsers, 1)} |",
        f"| OK | {stats['n_ok']} |",
        f"| Regwall fetches | {stats['n_regwall_fetches']} |",
        f"| Failed / Empty | {stats['n_failed']} |",
        f"| Connect-fail fetches | {stats['n_connect_fail']} |",
        f"| Total fetches | {stats['n_total_fetches']} |",
        f"| Termination | `{stats['termination']}` |",
        "",
        "## Throughput",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Wall-clock | {_fmt(stats['wall_s'], '.0f', 's')} |",
        f"| Mean s/fetch | {_fmt(stats['mean_s'], '.2f', 's')} |",
        f"| Median s/fetch | {_fmt(stats['median_s'], '.2f', 's')} |",
        f"| OK URLs/min | {_fmt(stats['urls_per_min'], '.1f')} |",
        f"| Backfill projection (61k) | {_fmt(stats['backfill_h'], '.1f', 'h')} |",
        "",
        "## HTML size distribution (ok URLs)",
        "",
        "> char_count = len(result.html) — full rendered HTML, typically 300–600 KB.",
        "> Low p50 (< 50k) would indicate truncation or near-empty pages.",
        "",
    ]

    p = stats["html_pct"]
    if p:
        lines += [
            "| Percentile | Chars |",
            "|---|---|",
            f"| p10 | {p['p10']:,} |",
            f"| p25 | {p['p25']:,} |",
            f"| p50 | {p['p50']:,} |",
            f"| p75 | {p['p75']:,} |",
            f"| p90 | {p['p90']:,} |",
            f"| p95 | {p['p95']:,} |",
            "",
        ]
    else:
        lines += ["No ok URLs — skipped.", ""]

    mp = stats["md_pct"]
    if mp:
        lines += [
            "## Markdown length distribution (ok URLs — body-level signal)",
            "",
            "> markdown_len = len(result.markdown.raw_markdown) — visible rendered text.",
            "> Low p50 (< 5k) despite ok HTML = likely silent regwall or empty body.",
            "",
            "| Percentile | Chars |",
            "|---|---|",
            f"| p10 | {mp['p10']:,} |",
            f"| p25 | {mp['p25']:,} |",
            f"| p50 | {mp['p50']:,} |",
            f"| p75 | {mp['p75']:,} |",
            f"| p90 | {mp['p90']:,} |",
            f"| p95 | {mp['p95']:,} |",
            "",
        ]

    lines += [
        "## Proxy riding",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Proxies burned | {stats['n_proxies_burned']} |",
        f"| Rides with ≥1 ok | {sum(1 for c in stats['ride_ok_counts'] if c > 0)} |",
        f"| 61k proxy estimate | {stats['proxies_for_backfill']:,} |",
        "",
        "### Ride length (URLs attempted per proxy)",
        "",
        f"mean={_fmt(rls['mean'], '.1f')}  "
        f"median={_fmt(rls['median'], '.1f')}  "
        f"min={_fmt(rls['min'])}  "
        f"max={_fmt(rls['max'])}",
        "",
        "## Regwall",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Regwall fetches | {stats['n_regwall_fetches']} |",
        f"| Wasted-fetch ratio | {rw_rate:.1%} |",
        f"| URLs with ≥1 regwall | {stats['n_urls_with_regwall']} |",
        f"| → eventually OK | {stats['retried_ok']} |",
        f"| → stayed failed | {stats['retried_failed']} |",
        "",
    ]

    failures = [j for j in state.job_records if j.status == "failed"]
    if failures:
        lines += ["## Failed URLs", "", "| URL | Error |", "|---|---|"]
        for j in failures[:20]:
            err = (j.error or "").replace("|", "\\|")[:120]
            lines.append(f"| {j.url[:80]} | {err} |")
        if len(failures) > 20:
            lines.append(f"| … ({len(failures) - 20} more) | |")
        lines.append("")

    rw_entries = [j for j in state.job_records if j.status == "regwall"]
    if rw_entries:
        seen_urls: set[str] = set()
        distinct_rw = [j for j in rw_entries if not (j.url in seen_urls or seen_urls.add(j.url))]
        lines += ["## Regwall URLs (distinct)", "", "| URL |", "|---|"]
        for j in distinct_rw[:50]:
            lines.append(f"| {j.url[:100]} |")
        if len(distinct_rw) > 50:
            lines.append(f"| … ({len(distinct_rw) - 50} more) |")
        lines.append("")

    lines += [
        "## Plots",
        "",
        "![Cumulative OK](cumulative.png)",
        "",
        "![Ride length distribution](ride_lengths.png)",
        "",
        "![Regwall rate vs position](regwall_position.png)",
        "",
    ]

    (job_dir / "job.md").write_text("\n".join(lines), encoding="utf-8")
