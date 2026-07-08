#!/usr/bin/env python3
"""
Single-Query Pool Dump — capped pool vs Top-N for 4 configs (bead searxng-g82).

Sections: (1) per-engine raw  (2) full capped pool  (3) Top-N per config
          (4) comparison matrix (every pool URL × 4 configs → rank or —)

Hard-stop: google_count == 0 → exit. No fallback.
Services: embedding port 8084 (Qwen3-0.6B) / reranker port 8082 (Qwen3-0.6B)

Usage:
  ./venv/bin/python dev/search_pipeline/single_query_pool_dump.py [--query TEXT] [--output PATH]
"""

# INFRASTRUCTURE
import argparse
import asyncio
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SCRIPT_DIR   = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from bm25_sweep_smoke import _build_pool, _doc_repr
from rerank_probe_smoke import (
    EMBEDDING_URL,
    RERANKER_URL,
    embed_batch,
    cross_encoder_rerank,
    cosine_sim,
    _bm25_score,
    _verify_services,
    close_browser,
    _query_engines_concurrent,
    _select_engines,
)

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

REPORT_DIR    = SCRIPT_DIR / "md"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_QUERY = "postgresql index types btree gin gist performance"
BM25_REPR     = "title+snippet"
SNIPPET_CHARS = 200


# ORCHESTRATOR

async def run_probe(query: str, output_path: Path | None) -> None:
    _verify_services()

    now        = datetime.now()
    ts_slug    = now.strftime("%Y%m%d_%H%M%S")
    ts_display = now.strftime("%Y-%m-%d %H:%M:%S")
    slug       = query[:30].replace(" ", "_").replace("/", "_")
    report_path = output_path or (REPORT_DIR / f"single_query_pool_{slug}_{ts_slug}.md")

    selected, _ = _select_engines(None)
    print(f"Engines ({len(selected)}): {', '.join(sorted(selected.keys()))}", file=sys.stderr)
    print(f"Query:   {query}", file=sys.stderr)
    print(f"Report:  {report_path}", file=sys.stderr)
    print(file=sys.stderr)

    t_wall = time.perf_counter()
    try:
        raw_results, engine_stats = await _query_engines_concurrent(query, "en", 10, selected)
        fetch_ms = round((time.perf_counter() - t_wall) * 1000)
    finally:
        await close_browser()

    google_count = engine_stats.get("google", {}).get("result_count", 0)
    if google_count == 0:
        sys.exit(
            f"STOP: google_count == 0 for query '{query}'.\n"
            f"Engine results: { {n: s['result_count'] for n, s in engine_stats.items()} }"
        )

    url_engine_pos = _build_url_engine_pos(raw_results, google_count)
    pool            = _build_capped_pool(raw_results, google_count)

    raw_texts   = [_doc_repr(m, BM25_REPR) for m in pool]
    valid_pairs = [(m, t) for m, t in zip(pool, raw_texts) if t.strip()]
    pool_v      = [m for m, _ in valid_pairs]
    texts_v     = [t for _, t in valid_pairs]

    t0     = time.perf_counter()
    c1_top = _rank_c1(pool, google_count)
    c1_ms  = round((time.perf_counter() - t0) * 1000)

    t0        = time.perf_counter()
    c2_scored = _bm25_score(pool, query, google_count)
    c2_ms     = round((time.perf_counter() - t0) * 1000)

    t0        = time.perf_counter()
    c3_scored = _ce_top_scored(query, texts_v, pool_v, google_count)
    c3_ms     = round((time.perf_counter() - t0) * 1000)

    t0        = time.perf_counter()
    c4_scored = _embed_top_scored(query, texts_v, pool_v, google_count)
    c4_ms     = round((time.perf_counter() - t0) * 1000)

    wall_ms = round((time.perf_counter() - t_wall) * 1000)

    print(
        f"google_count={google_count}  pool={len(pool)}  fetch={fetch_ms}ms  "
        f"C1={c1_ms}ms  C2={c2_ms}ms  C3={c3_ms}ms  C4={c4_ms}ms  wall={wall_ms}ms",
        file=sys.stderr,
    )

    sections = [
        _section_header(query, ts_display, google_count, pool, engine_stats, wall_ms),
        _section_per_engine(raw_results, engine_stats, google_count),
        _section_pool(pool, url_engine_pos),
        _section_configs(
            query, google_count, pool,
            c1_top, c2_scored, c3_scored, c4_scored,
            c1_ms, c2_ms, c3_ms, c4_ms,
        ),
        _section_matrix(pool, google_count, c1_top, c2_scored, c3_scored, c4_scored),
    ]
    _write_report(sections, report_path)
    print(f"\nReport: {report_path}", file=sys.stderr)


# FUNCTIONS

# Filter raw_results to position <= google_count; dedup via _build_pool
def _build_capped_pool(raw_results: list, google_count: int) -> list[dict]:
    return _build_pool([r for r in raw_results if r.position <= google_count])


# Build url → {engine: position} lookup for Section 2 engine-position annotations
def _build_url_engine_pos(raw_results: list, google_count: int) -> dict[str, dict[str, int]]:
    lookup: dict[str, dict[str, int]] = {}
    for r in raw_results:
        if r.position <= google_count:
            if r.url not in lookup:
                lookup[r.url] = {}
            lookup[r.url][r.engine] = r.position
    return lookup


# C1: sort pool by (-n_engines, min_position); return top_n
def _rank_c1(pool: list[dict], top_n: int) -> list[dict]:
    return sorted(pool, key=lambda m: (-len(m["engines"]), m["min_position"]))[:top_n]


# C3 cross-encoder rerank; returns [(doc, score), ...], one retry on API error
def _ce_top_scored(
    query: str, texts_v: list[str], pool_v: list[dict], top_n: int
) -> list[tuple[dict, float]]:
    if not texts_v:
        return []
    for attempt in range(2):
        try:
            pairs = cross_encoder_rerank(query, texts_v)
            return [(pool_v[idx], score) for idx, score in sorted(pairs, key=lambda x: -x[1])[:top_n]]
        except Exception as exc:
            print(f"  C3 API error attempt {attempt + 1}: {exc}", file=sys.stderr)
            if attempt == 0:
                time.sleep(2)
    return []


# C4 embedding-cosine rerank; returns [(doc, score), ...], one retry on API error
def _embed_top_scored(
    query: str, texts_v: list[str], pool_v: list[dict], top_n: int
) -> list[tuple[dict, float]]:
    if not texts_v:
        return []
    for attempt in range(2):
        try:
            embs       = embed_batch([query] + texts_v)
            cos_scores = [cosine_sim(embs[0], e) for e in embs[1:]]
            ranked     = sorted(range(len(pool_v)), key=lambda i: -cos_scores[i])[:top_n]
            return [(pool_v[i], cos_scores[i]) for i in ranked]
        except Exception as exc:
            print(f"  C4 API error attempt {attempt + 1}: {exc}", file=sys.stderr)
            if attempt == 0:
                time.sleep(2)
    return []


# Strip + truncate text to n chars, collapse newlines
def _fmt_snippet(text: str, n: int = SNIPPET_CHARS) -> str:
    return (text or "").strip().replace("\n", " ")[:n]


# Report header block
def _section_header(
    query: str,
    ts_display: str,
    google_count: int,
    pool: list[dict],
    engine_stats: dict,
    wall_ms: int,
) -> str:
    fired = ", ".join(
        f"{n} → {s['result_count']}"
        for n, s in sorted(engine_stats.items())
        if s["result_count"] > 0
    )
    n_engines = len(engine_stats)
    return "\n".join([
        "# Single-Query Pool Dump",
        "",
        f"**Query:** {query}  ",
        f"**Date:** {ts_display}  ",
        f"**google_count:** {google_count}  ",
        f"**Capped pool size:** {len(pool)} (after dedup across {n_engines} engines)  ",
        f"**Engines that fired:** {fired}  ",
        f"**Total wallclock:** {wall_ms}ms  ",
    ])


# Section 1: per-engine raw results in engine-rank order (capped to google_count)
def _section_per_engine(
    raw_results: list,
    engine_stats: dict,
    google_count: int,
) -> str:
    by_engine: dict[str, list] = defaultdict(list)
    for r in raw_results:
        by_engine[r.engine].append(r)
    for eng in by_engine:
        by_engine[eng].sort(key=lambda r: r.position)

    lines = ["## Section 1 — Per-Engine Raw (capped to top-google_count per engine)", ""]
    for eng in sorted(by_engine.keys()):
        results = [r for r in by_engine[eng] if r.position <= google_count]
        note    = f"{len(results)} of {google_count}"
        if len(results) < google_count:
            note += f" (engine returned only {len(results)})"
        lines.append(f"### {eng} ({note})")
        lines.append("")
        for i, r in enumerate(results, 1):
            title   = (r.title or "").strip().replace("\n", " ")[:100]
            snippet = _fmt_snippet(r.snippet or "")
            lines.append(f"{i}. {r.url}")
            lines.append(f"   Title: {title}")
            lines.append(f"   Snippet: {snippet}")
        lines.append("")
    return "\n".join(lines)


# Section 2: full capped pool sorted by (-engine_count, min_position)
def _section_pool(pool: list[dict], url_engine_pos: dict[str, dict[str, int]]) -> str:
    sorted_pool = sorted(pool, key=lambda m: (-len(m["engines"]), m["min_position"]))
    lines = [f"## Section 2 — Capped Pool ({len(pool)} unique URLs after dedup)", ""]
    for i, m in enumerate(sorted_pool, 1):
        title   = (m.get("title") or "").strip().replace("\n", " ")[:100]
        snippet = _fmt_snippet(m.get("snippet") or "")
        ep      = url_engine_pos.get(m["url"], {})
        eng_str = ", ".join(
            f"{eng} (pos {ep.get(eng, '?')})"
            for eng in sorted(m["engines"])
        )
        lines.append(f"{i}. {m['url']}")
        lines.append(f"   Title: {title}")
        lines.append(f"   Snippet: {snippet}")
        lines.append(f"   engines: [{eng_str}]")
        lines.append(f"   min_position: {m['min_position']} | engine_count: {len(m['engines'])}")
        lines.append("")
    return "\n".join(lines)


# Render one config block: heading + numbered URL list with per-entry score line
def _config_entries(label: str, ms: int, entries: list[tuple[dict, str]]) -> list[str]:
    lines = [f"### {label} — {ms}ms", ""]
    for i, (m, score_line) in enumerate(entries, 1):
        title   = (m.get("title") or "").strip().replace("\n", " ")[:100]
        snippet = _fmt_snippet(m.get("snippet") or "")
        engines = ", ".join(m.get("engines", []))
        lines += [
            f"{i}. {m['url']}",
            f"   Title: {title}",
            f"   Snippet: {snippet}",
            f"   engines: [{engines}]",
            score_line,
            "",
        ]
    return lines


# Section 3: four config sub-sections with scores and per-config latencies
def _section_configs(
    query: str,
    google_count: int,
    pool: list[dict],
    c1_top: list[dict],
    c2_scored: list[tuple[dict, float]],
    c3_scored: list[tuple[dict, float]],
    c4_scored: list[tuple[dict, float]],
    c1_ms: int,
    c2_ms: int,
    c3_ms: int,
    c4_ms: int,
) -> str:
    c1_entries = [(m, f"   engine_count: {len(m.get('engines', []))}") for m in c1_top]
    c2_entries = [(m, f"   bm25_score: {s:.4f}") for m, s in c2_scored]
    c3_entries = [(m, f"   rerank_score: {s:.4f}") for m, s in c3_scored]
    c4_entries = [(m, f"   cosine_sim: {s:.4f}") for m, s in c4_scored]

    lines = [f"## Section 3 — Top-{google_count} per Config", ""]
    lines += _config_entries("C1 — Overlap-Count (−n_engines, min_position)", c1_ms, c1_entries)
    lines += _config_entries("C2 — BM25 (k1=1.2, b=0.75, sw=on, title+snippet)", c2_ms, c2_entries)
    lines += _config_entries("C3 — Cross-Encoder (Qwen3-Reranker-0.6B, port 8082)", c3_ms, c3_entries)
    lines += _config_entries("C4 — Embedding-Cosine (Qwen3-Embedding-0.6B, port 8084)", c4_ms, c4_entries)
    return "\n".join(lines)


# Section 4: pool URL × 4 configs comparison matrix
def _section_matrix(
    pool: list[dict],
    google_count: int,
    c1_top: list[dict],
    c2_scored: list[tuple[dict, float]],
    c3_scored: list[tuple[dict, float]],
    c4_scored: list[tuple[dict, float]],
) -> str:
    c1_rank = {m["url"]: i for i, m in enumerate(c1_top, 1)}
    c2_rank = {m["url"]: i for i, (m, _) in enumerate(c2_scored, 1)}
    c3_rank = {m["url"]: i for i, (m, _) in enumerate(c3_scored, 1)}
    c4_rank = {m["url"]: i for i, (m, _) in enumerate(c4_scored, 1)}

    all_top_n = (c1_rank, c2_rank, c3_rank, c4_rank)

    def rank_cell(d: dict, url: str) -> str:
        v = d.get(url)
        return str(v) if v is not None else "—"

    # Pool order: same as Section 2 — (-engine_count, min_position)
    sorted_pool = sorted(pool, key=lambda m: (-len(m["engines"]), m["min_position"]))

    in_topn     = [m for m in sorted_pool if any(m["url"] in d for d in all_top_n)]
    not_in_topn = [m for m in sorted_pool if all(m["url"] not in d for d in all_top_n)]

    zero_configs = len(not_in_topn)
    consensus    = sum(
        1 for m in pool
        if all(m["url"] in d for d in all_top_n)
    )

    lines = [
        "## Section 4 — Comparison Matrix",
        "",
        f"Top-{google_count} per config. `—` = not in Top-{google_count} for that config.  ",
        f"Pool URLs in at least one Top-N: {len(in_topn)} | missed by all configs: {zero_configs} | in all 4 configs: {consensus}",
        "",
        "| URL (short) | engines | C1 rank | C2 rank | C3 rank | C4 rank |",
        "|---|---|---|---|---|---|",
    ]
    for m in in_topn + not_in_topn:
        url       = m["url"]
        url_short = (url[:50] + "…") if len(url) > 50 else url
        engines   = ",".join(sorted(m["engines"]))
        lines.append(
            f"| {url_short} | {engines} | {rank_cell(c1_rank, url)} "
            f"| {rank_cell(c2_rank, url)} | {rank_cell(c3_rank, url)} | {rank_cell(c4_rank, url)} |"
        )

    return "\n".join(lines)


# Join sections with separator and write to path
def _write_report(sections: list[str], path: Path) -> None:
    path.write_text("\n\n---\n\n".join(sections), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Single-query pool dump — capped pool vs 4 config Top-N side-by-side"
    )
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Query string to run (default: Q14)")
    parser.add_argument("--output", default=None, help="Custom report output path")
    args   = parser.parse_args()
    output = Path(args.output) if args.output else None
    asyncio.run(run_probe(args.query, output))
