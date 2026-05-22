#!/usr/bin/env python3
"""Full pipeline smoke -- search_web_workflow per query, timings + snippet source + slot-position labels."""

# INFRASTRUCTURE
import argparse
import asyncio
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.search.browser import close_browser
from src.search.cache import cache_key, cache_read
from src.search.search_web import search_web_workflow

SCRIPT_DIR   = Path(__file__).parent
QUERIES_FILE = SCRIPT_DIR / "queries.txt"
REPORT_DIR   = SCRIPT_DIR / "01_reports"

TARGET_GENERAL  = 12
TARGET_ACADEMIC = 6
TARGET_QA       = 2
TARGET_TOTAL    = 20


# ORCHESTRATOR

# Run search_web_workflow per query (with timings), read structured cache data, write report
async def run_pipeline_smoke(max_queries: int | None, language: str, engine_timeout: float | None = None, report_prefix: str = "pipeline_smoke") -> None:
    queries = _load_queries(QUERIES_FILE, max_queries)
    print(f"Pipeline smoke | Queries: {len(queries)} | Language: {language}", file=sys.stderr)
    records = []
    checkpoints: list[dict] = []
    t_run_start = time.perf_counter()
    prev_qi = 0
    prev_elapsed = 0.0
    try:
        for qi, query in enumerate(queries, 1):
            _, timings = await search_web_workflow(query, language, None, None, _with_timings=True, engine_timeout=engine_timeout)
            key  = cache_key(query, language, None, None)
            hit  = cache_read(key)
            urls = hit.get("urls", []) if hit else []
            slot_counts = (hit.get("slot_counts") or {}) if hit else {}
            record = _build_record(query, urls, slot_counts, timings)
            records.append(record)
            s = record["slots"]
            print(
                f"[{qi}/{len(queries)}] {query!r} -> urls={len(urls)} "
                f"G={s['GENERAL']} A={s['ACADEMIC']} Q={s['QA']} "
                f"total_ms={timings['total_ms']}",
                file=sys.stderr,
            )
            if qi in {4, 8, 12, 16, 20}:
                elapsed = round(time.perf_counter() - t_run_start, 1)
                seg_records = records[prev_qi:qi]
                seg_s = elapsed - prev_elapsed
                avg_per_q = round(seg_s / len(seg_records), 1)
                ok_count = 0
                rs_count = 0
                for rec in seg_records:
                    for info in (rec["timings"] or {}).get("engine_details", {}).values():
                        st = info.get("status", "")
                        if st == "OK":
                            ok_count += 1
                        elif st == "RATE_SKIP":
                            rs_count += 1
                cp = {
                    "milestone": f"Q{qi}",
                    "cumulative_s": elapsed,
                    "avg_per_q_s": avg_per_q,
                    "engines_ok": ok_count,
                    "engines_rate_skip": rs_count,
                }
                checkpoints.append(cp)
                print(
                    f"[CHECKPOINT Q{qi}] cumulative={elapsed}s avg/q={avg_per_q}s "
                    f"ok={ok_count} rate_skip={rs_count}",
                    file=sys.stderr,
                )
                prev_qi = qi
                prev_elapsed = elapsed
    finally:
        await close_browser()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = _write_report(records, language, checkpoints, report_prefix)
    ok = sum(1 for r in records if r["total_urls"] > 0)
    print(f"\nReport: {path}", file=sys.stderr)
    print(f"Done: {ok}/{len(records)} queries with results", file=sys.stderr)


# FUNCTIONS

# Load queries from file, one per line, skip blanks, honour max_queries limit
def _load_queries(path: Path, max_queries: int | None) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    qs = [ln.strip() for ln in lines if ln.strip()]
    return qs[:max_queries] if max_queries else qs


# Assign slot-position label from slot_counts boundaries (position-based, not engine-deduced)
def _slot_label(idx: int, slot_counts: dict) -> str:
    n_gen = slot_counts.get("general", 0)
    n_ac  = slot_counts.get("academic", 0)
    n_qa  = slot_counts.get("qa", 0)
    if idx < n_gen:
        return "GENERAL"
    if idx < n_gen + n_ac:
        return "ACADEMIC"
    if idx < n_gen + n_ac + n_qa:
        return "QA"
    return "OVERFLOW"  # should not occur in v3; kept as safety label for cache-paginated entries


# Build per-query record: annotated top-20 urls, slot counts, timings
def _build_record(query: str, urls: list[dict], slot_counts: dict, timings: dict) -> dict:
    allocated = slot_counts.get("general", 0) + slot_counts.get("academic", 0) + slot_counts.get("qa", 0)
    top20 = urls[:min(TARGET_TOTAL, allocated)]
    annotated = []
    for idx, entry in enumerate(top20):
        annotated.append({
            "url":             entry["url"],
            "title":           entry.get("title", ""),
            "engines":         entry.get("engines", []),
            "snippet":         entry.get("snippet", ""),
            "snippet_source":  entry.get("snippet_source") or "",
            "snippet_display": entry.get("snippet_display") or "",
            "og":              entry.get("og") or "",
            "meta":            entry.get("meta") or "",
            "snippets":        entry.get("snippets") or {},
            "class":           _slot_label(idx, slot_counts),
        })
    slots: dict[str, int] = {"GENERAL": 0, "ACADEMIC": 0, "QA": 0}
    for a in annotated:
        label = a["class"]
        if label in slots:
            slots[label] += 1
    return {
        "query":       query,
        "urls":        annotated,
        "total_urls":  len(annotated),
        "slots":       slots,
        "slot_counts": slot_counts,
        "timings":     timings,
    }


# Render pipeline smoke report header (title, language, query counts)
def _render_header(records: list[dict], language: str, ts: str) -> list[str]:
    return [
        f"# Pipeline Smoke Report -- {ts}",
        "",
        f"**Language:** {language}  ",
        f"**Queries:** {len(records)}  ",
        f"**Queries with results:** {sum(1 for r in records if r['total_urls'] > 0)}",
        "",
    ]


# Render static engine class definitions table and notes block
def _render_class_defs() -> list[str]:
    return [
        "## Engine Class Definitions",
        "",
        "| Class    | Engines                               | Output slots |",
        "|----------|---------------------------------------|-------------|",
        "| GENERAL  | google, duckduckgo, mojeek            | 12 |",
        "| ACADEMIC | google_scholar, openalex, crossref    |  6 |",
        "| QA       | stack_exchange, lobsters              |  2 |",
        "",
        "> Slot position labels are derived from `slot_counts` in the cache entry (position-based),",
        "> not deduced from the `engines` field. Total target: 20. Underflow = output < 20 when",
        "> a class has insufficient supply. No overflow slots — v3 hard allocation.",
        "",
        "---",
        "",
    ]


# Render summary table header and one row per query record
def _render_summary(records: list[dict]) -> list[str]:
    L: list[str] = [
        "## Summary",
        "",
        "| # | Query | Total | GENERAL | ACADEMIC | QA |",
        "|---|-------|-------|---------|----------|----|",
    ]
    for i, r in enumerate(records, 1):
        q = r["query"][:55].replace("|", "\\|")
        s = r["slots"]
        L.append(
            f"| {i} | {q} | {r['total_urls']} "
            f"| {s['GENERAL']} | {s['ACADEMIC']} | {s['QA']} |"
        )
    return L


# Render per-query URL block with slot-fill, engine timing footer and separator
def _render_query_block(r: dict, qi: int) -> list[str]:
    L: list[str] = [f"## Q{qi}: {r['query']}", ""]
    if not r["urls"]:
        return L + ["*No results returned.*", "", "---", ""]
    sc = r["slot_counts"]
    t  = r["timings"]
    for idx, a in enumerate(r["urls"], 1):
        title       = a["title"] if a["title"] else "(no title)"
        engines_str = ", ".join(a["engines"])
        src         = a["snippet_source"] or "—"
        display     = (a["snippet_display"] or "")[:400].replace("\n", " ")
        og_val      = (a["og"]   or "—")[:300].replace("\n", " ")
        meta_val    = (a["meta"] or "—")[:300].replace("\n", " ")
        L += [
            f"{idx}. **[{a['class']}]** {title}",
            f"   URL: {a['url']}",
            f"   Engines: {engines_str}",
            f"   source: {src} | display: {display!r}",
            f"   og: {og_val} | meta: {meta_val}",
        ]
        for eng, snip in sorted(a["snippets"].items()):
            L.append(f"   {eng}: {snip[:300].replace(chr(10), ' ')!r}")
        L.append("")
    gen_target = sc.get("general", TARGET_GENERAL)
    ac_target  = sc.get("academic", TARGET_ACADEMIC)
    qa_target  = sc.get("qa", TARGET_QA)
    L.append(
        f"Slot fill: GENERAL {gen_target}/{TARGET_GENERAL}, "
        f"ACADEMIC {ac_target}/{TARGET_ACADEMIC}, "
        f"QA {qa_target}/{TARGET_QA}, "
        f"total {r['total_urls']}/{TARGET_TOTAL}"
    )
    engine_details = t.get("engine_details", {})
    if engine_details:
        parts = [f"{name}={d['status']}/{d['ms']}ms" for name, d in engine_details.items()]
        L.append(f"Engines: {' '.join(parts)}")
    L += [
        "",
        f"Timing: total={t.get('total_ms')}ms  fanout={t.get('engine_fanout_ms')}ms  "
        f"merge={t.get('merge_rank_ms')}ms  preview={t.get('preview_ms')}ms  "
        f"snippet_select={t.get('select_snippet_ms')}ms  cache_write={t.get('cache_write_ms')}ms",
        "",
        "---",
        "",
    ]
    return L


# Render timing section — per-query table and aggregate stats
def _render_timing_section(records: list[dict]) -> list[str]:
    all_total_ms = [r["timings"]["total_ms"] for r in records if r["timings"]]
    L: list[str] = [
        "## Timing",
        "",
        "### Per-Query",
        "",
        "| # | Query | total_ms | fanout_ms | merge_ms | preview_ms | snippet_ms | cache_ms |",
        "|---|-------|----------|-----------|----------|------------|------------|----------|",
    ]
    for i, r in enumerate(records, 1):
        t = r["timings"]
        q = r["query"][:40].replace("|", "\\|")
        L.append(
            f"| {i} | {q} | {t.get('total_ms', '—')} | {t.get('engine_fanout_ms', '—')} "
            f"| {t.get('merge_rank_ms', '—')} | {t.get('preview_ms', '—')} "
            f"| {t.get('select_snippet_ms', '—')} | {t.get('cache_write_ms', '—')} |"
        )
    if all_total_ms:
        L += [
            "",
            "### Aggregate (total_ms across all queries)",
            "",
            f"| min | median | mean | max |",
            f"|-----|--------|------|-----|",
            f"| {min(all_total_ms)} | {round(statistics.median(all_total_ms))} "
            f"| {round(statistics.mean(all_total_ms))} | {max(all_total_ms)} |",
        ]
    return L


# Render cumulative-wallclock checkpoint table at Q4/Q8/Q12/Q16/Q20 milestones
def _render_timing_checkpoints(checkpoints: list[dict]) -> list[str]:
    if not checkpoints:
        return []
    L: list[str] = [
        "",
        "## Timing Checkpoints",
        "",
        "| Milestone | Cumulative wall (s) | Avg/query in segment (s) | Engines OK | Engines RATE_SKIP |",
        "|-----------|--------------------:|-------------------------:|-----------:|------------------:|",
    ]
    for cp in checkpoints:
        L.append(
            f"| {cp['milestone']} | {cp['cumulative_s']} | {cp['avg_per_q_s']} "
            f"| {cp['engines_ok']} | {cp['engines_rate_skip']} |"
        )
    return L


# Render per-engine status aggregate section across all queries
def _render_engine_status(records: list[dict]) -> list[str]:
    status_counts: dict[str, dict[str, int]] = {}
    for r in records:
        det = (r["timings"] or {}).get("engine_details", {})
        for eng, info in det.items():
            if eng not in status_counts:
                status_counts[eng] = {"OK": 0, "EMPTY": 0, "TIMEOUT": 0, "ERROR": 0}
            status_counts[eng][info["status"]] = status_counts[eng].get(info["status"], 0) + 1
    if not status_counts:
        return []
    L: list[str] = [
        "",
        "## Per-Engine Status Aggregate",
        "",
        "| Engine | OK | EMPTY | TIMEOUT | ERROR |",
        "|--------|----|-------|---------|-------|",
    ]
    for eng in sorted(status_counts):
        c = status_counts[eng]
        L.append(
            f"| {eng} | {c.get('OK', 0)} | {c.get('EMPTY', 0)} | {c.get('TIMEOUT', 0)} | {c.get('ERROR', 0)} |"
        )
    return L


# Per-engine reliability baseline: full status breakdown, mean/p95 search_ms for OK entries
def _render_engine_reliability(records: list[dict]) -> list[str]:
    # Collect per-engine: status counts, OK search_ms list
    STATUS_KEYS = [
        "OK",
        "EMPTY_NO_RESULTS", "EMPTY_NO_CONTAINER", "EMPTY_CONSENT",
        "EMPTY_BLOCK", "EMPTY_CONCURRENT_RACE",
        "TIMEOUT_WATCHDOG", "TIMEOUT_NONCOOP", "TIMEOUT_HTTPX",
        "ERROR_BROWSER", "ERROR_HTTP", "ERROR_PARSE", "ERROR_OTHER",
        "RATE_SKIP",
    ]
    engine_data: dict[str, dict[str, Any]] = {}
    for r in records:
        det = (r["timings"] or {}).get("engine_details", {})
        for eng, info in det.items():
            if eng not in engine_data:
                engine_data[eng] = {"counts": {k: 0 for k in STATUS_KEYS}, "ok_ms": []}
            st = info.get("status", "ERROR_OTHER")
            key = st if st in engine_data[eng]["counts"] else "ERROR_OTHER"
            engine_data[eng]["counts"][key] += 1
            if st == "OK":
                engine_data[eng]["ok_ms"].append(info.get("ms", 0))
    if not engine_data:
        return []

    # Header
    cols = [
        "Engine", "n",
        "OK%", "NO_RES%", "NO_CONT%", "CONSENT%", "BLOCK%", "RACE%",
        "T_WD%", "T_NC%", "T_HX%",
        "E_BR%", "E_HT%", "E_PA%", "E_OT%",
        "RS%", "mean_ms(OK)", "p95_ms",
    ]
    sep = "|" + "|".join(["---"] * len(cols)) + "|"
    header = "|" + "|".join(cols) + "|"
    L: list[str] = [
        "",
        "## Per-Engine Reliability Baseline",
        "",
        "> Source: `records[i]['timings']['engine_details']` (in-memory, identical to query_log.jsonl).",
        "> Percentages = count / n_queries × 100. mean_ms and p95_ms computed on OK entries only.",
        "",
        header,
        sep,
    ]

    # Bottleneck tracking
    bottleneck_counts: dict[str, int] = {}

    for eng in sorted(engine_data):
        d = engine_data[eng]
        c = d["counts"]
        n = sum(c.values())
        if n == 0:
            continue

        def pct(k: str) -> str:
            v = c.get(k, 0)
            return f"{round(v / n * 100)}" if v else "0"

        ok_ms = d["ok_ms"]
        if ok_ms:
            mean_ms = round(statistics.mean(ok_ms))
            p95_ms = round(statistics.quantiles(ok_ms, n=20)[18]) if len(ok_ms) >= 2 else ok_ms[0]
        else:
            mean_ms = "—"
            p95_ms = "—"

        L.append(
            f"| {eng} | {n} "
            f"| {pct('OK')} | {pct('EMPTY_NO_RESULTS')} | {pct('EMPTY_NO_CONTAINER')} "
            f"| {pct('EMPTY_CONSENT')} | {pct('EMPTY_BLOCK')} | {pct('EMPTY_CONCURRENT_RACE')} "
            f"| {pct('TIMEOUT_WATCHDOG')} | {pct('TIMEOUT_NONCOOP')} | {pct('TIMEOUT_HTTPX')} "
            f"| {pct('ERROR_BROWSER')} | {pct('ERROR_HTTP')} | {pct('ERROR_PARSE')} | {pct('ERROR_OTHER')} "
            f"| {pct('RATE_SKIP')} | {mean_ms} | {p95_ms} |"
        )

    # Top-3 bottleneck engines: which engine had highest search_ms most often per query
    for r in records:
        det = (r["timings"] or {}).get("engine_details", {})
        if not det:
            continue
        slowest = max(det, key=lambda e: det[e].get("ms", 0))
        bottleneck_counts[slowest] = bottleneck_counts.get(slowest, 0) + 1
    top3 = sorted(bottleneck_counts, key=lambda e: bottleneck_counts[e], reverse=True)[:3]
    top3_str = ", ".join(f"{e} ({bottleneck_counts[e]}×)" for e in top3) if top3 else "—"

    L += [
        "",
        f"**Top-3 bottleneck engines** (most queries where this engine had highest search_ms): {top3_str}",
        "",
    ]
    return L


# Write markdown report to 01_reports/<prefix>_<ts>.md, return path
def _write_report(records: list[dict], language: str, checkpoints: list[dict], prefix: str = "pipeline_smoke") -> Path:
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"{prefix}_{ts}.md"
    lines = (
        _render_header(records, language, ts)
        + _render_class_defs()
        + _render_summary(records)
        + _render_timing_checkpoints(checkpoints)
        + ["", "---", ""]
    )
    for qi, r in enumerate(records, 1):
        lines += _render_query_block(r, qi)
    lines += _render_timing_section(records)
    lines += _render_engine_status(records)
    lines += _render_engine_reliability(records)
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Full pipeline smoke: search_web_workflow per query, timings + snippet source + slot labels."
    )
    parser.add_argument(
        "--max-queries",
        dest="max_queries",
        type=int,
        default=None,
        help="Limit to first N queries from queries.txt (default: all)",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="ISO language code (default: en)",
    )
    parser.add_argument(
        "--engine-timeout",
        dest="engine_timeout",
        type=float,
        default=None,
        help="Hard timeout per engine call in seconds, e.g. 8.0 (default: None = no timeout)",
    )
    parser.add_argument(
        "--report-prefix",
        dest="report_prefix",
        default="pipeline_smoke",
        help="Report filename prefix (default: pipeline_smoke → pipeline_smoke_<ts>.md)",
    )
    args = parser.parse_args()
    asyncio.run(run_pipeline_smoke(args.max_queries, args.language, args.engine_timeout, args.report_prefix))
