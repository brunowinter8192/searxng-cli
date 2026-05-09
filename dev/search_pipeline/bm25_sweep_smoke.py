#!/usr/bin/env python3
"""
BM25 Sweep Probe vs Hard-Slot Baseline.

Ranks the same deduplicated URL pool per query using:
  A) Hard-Slot: _merge_and_rank from src.search.merge (12/6/2 class slots)
  B) BM25 sweep: 16-config main grid (b x stopwords x doc_repr, k1 fixed at 1.2)
               + 4-config k1 sensitivity sweep at default-other-knobs

IDF handling: uniform IDF=1.0 per user design (query-word relevance is user-defined,
not corpus-derived; stopword filter replaces IDF discrimination). Reduces BM25 to
TF + length-normalization only.

Implementation choice: BM25Uniform subclasses rank_bm25.BM25Okapi and overrides
_calc_idf to set self.idf[word]=1.0 for all terms. Preferred over a custom 30-LOC
implementation because _calc_idf is an explicit extension point in BM25Okapi and
the override is 5 LOC. Library (rank_bm25) already in venv; k1/b tunable via
constructor.

Stopword list: ~45-word inline English set (determiners, prepositions, auxiliaries).
NLTK (~180 words) not used — no dependency, and for short title+snippet text the
marginal coverage gain of 180 vs 45 words is small.

Output: dev/search_pipeline/01_reports/bm25_sweep_<ts>.md
"""

# INFRASTRUCTURE
import asyncio
import re
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.browser import close_browser
from src.search.merge import ACADEMIC, GENERAL, QA, _merge_and_rank
from src.search.result import SearchResult
from src.search.search_web import _query_engines_concurrent, _select_engines

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

REPORT_DIR = SCRIPT_DIR / "01_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

QUERIES = [
    "transformer attention mechanism",
    "best espresso machine 2026",
    "python asyncio context manager",
    "kubernetes service mesh comparison",
]

TOP_N = 20
VANILLA_K1 = 1.2
VANILLA_KEY = (0.75, True, "title+snippet")  # (b, sw, repr) — identifies vanilla in main grid

STOPWORDS = frozenset({
    "the", "of", "in", "and", "a", "an", "is", "to", "for", "or", "on", "at",
    "by", "with", "why", "how", "what", "when", "where", "are", "be", "as",
    "from", "that", "this", "it", "was", "not", "has", "but", "have", "been",
    "its", "their", "they", "which", "about", "into", "than", "over", "do",
    "does", "did", "will", "would",
})

# Main grid: 16 configs = 4 b x 2 sw x 2 doc_repr (k1 fixed at VANILLA_K1)
BM25_MAIN_GRID = [
    {"b": b, "sw": sw, "repr": dr}
    for b  in [0.0, 0.5, 0.75, 1.0]
    for sw in [True, False]
    for dr in ["title+snippet", "title3x"]
]

# k1 sensitivity: 4 configs at b=0.75, sw=on, repr=title+snippet
BM25_K1_SWEEP = [{"k1": k1} for k1 in [0.5, 1.2, 2.0, 3.0]]


# BM25 with uniform IDF=1.0; reduces to TF + length-normalization
class BM25Uniform(BM25Okapi):
    def _calc_idf(self, nd):
        for word in nd:
            self.idf[word] = 1.0
        self.average_idf = 1.0


# ORCHESTRATOR

async def run_probe() -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"bm25_sweep_{ts}.md"

    selected, _ = _select_engines(None)
    engine_names = sorted(selected.keys())
    print(f"Engines ({len(selected)}): {', '.join(engine_names)}", file=sys.stderr)
    print(f"Queries:  {len(QUERIES)}", file=sys.stderr)
    print(f"Report:   {report_path}", file=sys.stderr)
    print(file=sys.stderr)

    query_sections: list[str] = []
    summaries: list[dict] = []
    t_total = time.perf_counter()
    try:
        for qi, query in enumerate(QUERIES):
            print(f"[{qi + 1}/{len(QUERIES)}] {query}", file=sys.stderr)

            t0 = time.perf_counter()
            raw_results, engine_stats = await _query_engines_concurrent(query, "en", 10, selected)
            fetch_ms = round((time.perf_counter() - t0) * 1000)

            t0 = time.perf_counter()
            hard_slot_ranked, slot_counts = _merge_and_rank(raw_results)
            hard_slot_top = hard_slot_ranked[:TOP_N]
            hardslot_ms = round((time.perf_counter() - t0) * 1000)

            pool = _build_pool(raw_results)

            t0 = time.perf_counter()
            grid_results = _run_main_grid(pool, query)
            k1_results   = _run_k1_sweep(pool, query)
            bm25_total_ms = round((time.perf_counter() - t0) * 1000)

            ok_count = sum(1 for s in engine_stats.values() if s["result_count"] > 0)
            print(
                f"  raw={len(raw_results)}, unique={len(pool)}, ok_engines={ok_count}, "
                f"fetch={fetch_ms}ms, bm25={bm25_total_ms}ms",
                file=sys.stderr,
            )

            section, summary = _build_query_section(
                query, pool, hard_slot_top, slot_counts,
                grid_results, k1_results, engine_stats,
                len(raw_results), fetch_ms, hardslot_ms, bm25_total_ms,
            )
            query_sections.append(section)
            summaries.append(summary)
    finally:
        await close_browser()

    total_ms = round((time.perf_counter() - t_total) * 1000)
    _write_report(query_sections, summaries, report_path, total_ms)
    print(f"\nReport:     {report_path}", file=sys.stderr)
    print(f"Total wall: {total_ms}ms", file=sys.stderr)


# FUNCTIONS

# Merge raw results by URL — Step 1 of _merge_and_rank extracted to avoid slot allocation
def _build_pool(raw_results: list[SearchResult]) -> list[dict]:
    merged: dict[str, dict] = {}
    for r in raw_results:
        if r.url not in merged:
            merged[r.url] = {
                "url":          r.url,
                "title":        r.title or "",
                "snippet":      r.snippet or "",
                "engines":      [r.engine],
                "snippets":     {r.engine: r.snippet} if r.snippet else {},
                "min_position": r.position,
            }
        else:
            m = merged[r.url]
            if r.engine not in m["engines"]:
                m["engines"].append(r.engine)
            if r.snippet:
                m["snippets"][r.engine] = r.snippet
            m["min_position"] = min(m["min_position"], r.position)
            if not m["title"] and r.title:
                m["title"] = r.title
    return list(merged.values())


# Lowercase word-boundary tokenize; optionally strip stopwords
def _tokenize(text: str, use_sw: bool) -> list[str]:
    tokens = re.findall(r"\b\w+\b", text.lower())
    return [t for t in tokens if t not in STOPWORDS] if use_sw else tokens


# Build document text for BM25: title+snippet or title repeated 3x + snippet
def _doc_repr(m: dict, style: str) -> str:
    t, s = m["title"], m["snippet"]
    return f"{t} {t} {t} {s}" if style == "title3x" else f"{t} {s}"


# BM25 rank pool by query; return top-N as [(pool_dict, score), ...]
def _bm25_rank(
    pool: list[dict], query: str, k1: float, b: float, use_sw: bool, repr_style: str
) -> list[tuple[dict, float]]:
    if not pool:
        return []
    corpus = [_tokenize(_doc_repr(m, repr_style), use_sw) for m in pool]
    qtoks  = _tokenize(query, use_sw)
    bm25   = BM25Uniform(corpus, k1=k1, b=b)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        scores = bm25.get_scores(qtoks)
    scores = np.nan_to_num(scores, nan=0.0)  # b=1.0 + empty-doc edge case
    ranked = sorted(range(len(pool)), key=lambda i: -float(scores[i]))
    return [(pool[i], float(scores[i])) for i in ranked[:TOP_N]]


# Run 16-config main grid (k1 fixed at VANILLA_K1)
def _run_main_grid(pool: list[dict], query: str) -> list[dict]:
    results = []
    for cfg in BM25_MAIN_GRID:
        top20 = _bm25_rank(pool, query, k1=VANILLA_K1, b=cfg["b"], use_sw=cfg["sw"], repr_style=cfg["repr"])
        results.append({"cfg": cfg, "top20": top20})
    return results


# Run 4-config k1 sensitivity sweep at default-other-knobs
def _run_k1_sweep(pool: list[dict], query: str) -> list[dict]:
    results = []
    for cfg in BM25_K1_SWEEP:
        top20 = _bm25_rank(pool, query, k1=cfg["k1"], b=0.75, use_sw=True, repr_style="title+snippet")
        results.append({"cfg": cfg, "top20": top20})
    return results


# Classify URL by contributing engines: ACADEMIC > QA > GENERAL
def _classify(engines: list[str]) -> str:
    eng = set(engines)
    if eng & ACADEMIC:
        return "academic"
    if eng & QA:
        return "qa"
    return "general"


# Count URL overlap between two URL sets
def _overlap(a: set, b: set) -> int:
    return len(a & b)


# Build markdown section + summary dict for one query
def _build_query_section(
    query: str,
    pool: list[dict],
    hard_slot_top: list[SearchResult],
    slot_counts: dict,
    grid_results: list[dict],
    k1_results: list[dict],
    engine_stats: dict,
    total_raw: int,
    fetch_ms: int,
    hardslot_ms: int,
    bm25_total_ms: int,
) -> tuple[str, dict]:
    # Locate vanilla config in grid
    vanilla_entry = next(
        r for r in grid_results
        if (r["cfg"]["b"], r["cfg"]["sw"], r["cfg"]["repr"]) == VANILLA_KEY
    )
    vanilla_urls = {doc["url"] for doc, _ in vanilla_entry["top20"]}
    hs_urls      = {r.url for r in hard_slot_top}

    # Stability: URLs in Top-20 of ALL 16 configs
    all_url_sets = [{doc["url"] for doc, _ in r["top20"]} for r in grid_results]
    stable_urls  = set.intersection(*all_url_sets) if all_url_sets else set()

    ok_engines  = [(n, s["result_count"]) for n, s in sorted(engine_stats.items()) if s["result_count"] > 0]
    engine_line = ", ".join(f"{n}={c}" for n, c in ok_engines)

    lines = [
        f"## {query}",
        "",
        f"**Raw results:** {total_raw}  ",
        f"**Unique URLs after dedup:** {len(pool)}  ",
        f"**Engines with results ({len(ok_engines)}):** {engine_line}  ",
        f"**Timing:** fetch={fetch_ms}ms, hardslot={hardslot_ms}ms, bm25_total={bm25_total_ms}ms  ",
        f"**Hard-Slot slot counts:** general={slot_counts.get('general', 0)}, "
        f"academic={slot_counts.get('academic', 0)}, qa={slot_counts.get('qa', 0)}",
        "",
    ]

    # Section 1 — Hard-Slot table
    lines += [
        "### 1. Hard-Slot Baseline (12 General / 6 Academic / 2 QA)",
        "",
        "| # | Class | Engines | URL |",
        "|---|-------|---------|-----|",
    ]
    for i, r in enumerate(hard_slot_top, 1):
        engs = r.engines if r.engines else [r.engine]
        lines.append(f"| {i} | {_classify(engs)} | {', '.join(engs)} | {r.url[:90]} |")
    lines.append("")

    # Section 2 — Vanilla BM25 table
    lines += [
        "### 2. Vanilla BM25 (k1=1.2, b=0.75, stopwords=on, doc_repr=title+snippet)",
        "",
        "| # | Score | Engines | URL |",
        "|---|-------|---------|-----|",
    ]
    for i, (doc, score) in enumerate(vanilla_entry["top20"], 1):
        lines.append(f"| {i} | {score:.4f} | {', '.join(doc['engines'])} | {doc['url'][:90]} |")
    lines.append("")

    # Section 3 — Main-grid sensitivity table
    lines += [
        "### 3. Main-Grid Sensitivity (16 configs)",
        "",
        "| b | stopwords | doc_repr | Overlap w/ Vanilla | Overlap w/ Hard-Slot |",
        "|---|-----------|----------|-------------------|---------------------|",
    ]
    for r in grid_results:
        cfg      = r["cfg"]
        top_urls = {doc["url"] for doc, _ in r["top20"]}
        ov_v     = _overlap(top_urls, vanilla_urls)
        ov_hs    = _overlap(top_urls, hs_urls)
        sw_lbl   = "on" if cfg["sw"] else "off"
        lines.append(f"| {cfg['b']} | {sw_lbl} | {cfg['repr']} | {ov_v}/20 | {ov_hs}/20 |")
    lines.append("")

    # Section 4 — k1 sensitivity table
    lines += [
        "### 4. k1 Sensitivity (b=0.75, sw=on, repr=title+snippet)",
        "",
        "| k1 | Top-20 Overlap with Vanilla |",
        "|----|----------------------------|",
    ]
    for r in k1_results:
        top_urls = {doc["url"] for doc, _ in r["top20"]}
        lines.append(f"| {r['cfg']['k1']} | {_overlap(top_urls, vanilla_urls)}/20 |")
    lines.append("")

    # Section 5 — Stability
    lines += [
        "### 5. Top-20 Stability across 16 Main-Grid Configs",
        "",
        f"URLs in Top-20 of **all** 16 configs: **{len(stable_urls)}/20**",
        "",
    ]

    # Section 6 — Differences Hard-Slot vs Vanilla BM25
    only_hs      = hs_urls - vanilla_urls
    only_vanilla = vanilla_urls - hs_urls
    overlap_hv   = _overlap(hs_urls, vanilla_urls)

    lines += [
        "### 6. Differences: Hard-Slot vs Vanilla BM25",
        "",
        f"**Overlap:** {overlap_hv}/20  ",
        "",
    ]
    if only_hs:
        lines.append(f"**Only in Hard-Slot ({len(only_hs)}):**")
        for url in sorted(only_hs):
            lines.append(f"- {url[:100]}")
        lines.append("")
    if only_vanilla:
        lines.append(f"**Only in Vanilla BM25 ({len(only_vanilla)}):**")
        for url in sorted(only_vanilla):
            lines.append(f"- {url[:100]}")
        lines.append("")
    if not only_hs and not only_vanilla:
        lines.append("_Lists are identical._")
        lines.append("")

    grid_overlaps_v = [_overlap({doc["url"] for doc, _ in r["top20"]}, vanilla_urls) for r in grid_results]
    k1_overlaps_v   = [_overlap({doc["url"] for doc, _ in r["top20"]}, vanilla_urls) for r in k1_results]

    summary = {
        "query":              query,
        "raw":                total_raw,
        "unique":             len(pool),
        "stability":          len(stable_urls),
        "overlap_vanilla_hs": overlap_hv,
        "min_grid_v":         min(grid_overlaps_v),
        "max_grid_v":         max(grid_overlaps_v),
        "min_k1_v":           min(k1_overlaps_v),
        "max_k1_v":           max(k1_overlaps_v),
    }
    return "\n".join(lines), summary


# Write full markdown report: header + global summary + per-query sections
def _write_report(
    sections: list[str], summaries: list[dict], path: Path, total_ms: int
) -> None:
    ts = path.stem.replace("bm25_sweep_", "")

    header = "\n".join([
        f"# BM25 Sweep Probe vs Hard-Slot Baseline — {ts}",
        "",
        f"**Queries:** {len(sections)}  ",
        f"**Engines:** 9 default (Scholar dormant)  ",
        f"**BM25 configs:** 16 main grid (b x stopwords x doc_repr, k1=1.2) + 4 k1 sensitivity  ",
        f"**IDF:** uniform 1.0 (TF + length-norm only, uniform IDF via BM25Uniform subclass)  ",
        f"**Vanilla BM25:** k1=1.2, b=0.75, stopwords=on, doc_repr=title+snippet  ",
        f"**Top-N:** {TOP_N}  ",
        f"**Total wallclock:** {total_ms}ms",
    ])

    summary_lines = [
        "## Global Summary",
        "",
        "| Query | Raw | Unique | Stability (all-16) | Vanilla↔HS | Grid↔Van (min/max) | k1↔Van (min/max) |",
        "|-------|-----|--------|--------------------|-----------|-------------------|-----------------|",
    ]
    for s in summaries:
        q_short = s["query"][:38]
        summary_lines.append(
            f"| {q_short} | {s['raw']} | {s['unique']} | {s['stability']}/20 | "
            f"{s['overlap_vanilla_hs']}/20 | {s['min_grid_v']}-{s['max_grid_v']}/20 | "
            f"{s['min_k1_v']}-{s['max_k1_v']}/20 |"
        )

    all_parts = [header, "\n".join(summary_lines)] + sections
    path.write_text("\n\n---\n\n".join(all_parts), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(run_probe())
