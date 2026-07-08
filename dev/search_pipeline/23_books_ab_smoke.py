#!/usr/bin/env python3
"""A/B pool-widening smoke — measures Open Library's additive contribution to --books mode.

Design: OL URLs (openlibrary.org/works/*) are structurally unique — web engines (Google/DDG/Mojeek)
do not index /works/ catalog pages. Therefore OL result count = unique-to-OL count directly.
No Chrome needed; runs OL engine standalone.
"""

# INFRASTRUCTURE
import asyncio
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from src.search.engines.open_library import OpenLibraryEngine

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

REPORT_DIR = SCRIPT_DIR / "md"

# Book-affine queries covering diverse genres and subjects
BOOK_QUERIES = [
    "introduction to information retrieval",
    "kafka prozess",
    "tolkien",
    "harry potter",
    "cooking italian",
    "machine learning textbook",
    "design patterns",
    "algorithm cormen",
    "history of rome",
    "philosophy nietzsche",
]

# Current --books pool per web engine is roughly 10 URLs (DDG/Mojeek) to 30 (Google).
# General slot target is 12; treat queries where OL adds ≥3 URLs as "meaningful widening".
MEANINGFUL_WIDENING_THRESHOLD = 3


# ORCHESTRATOR

async def run_ab_smoke() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    engine = OpenLibraryEngine()
    records = []

    for qi, query in enumerate(BOOK_QUERIES):
        print(f"[{qi + 1}/{len(BOOK_QUERIES)}] {query}", file=sys.stderr)
        t0 = time.monotonic()
        record = await run_query(engine, query)
        elapsed = time.monotonic() - t0
        record["elapsed_ms"] = int(elapsed * 1000)
        records.append(record)
        print(
            f"  → {record['status']} | OL unique URLs: {record['ol_count']} | {elapsed:.1f}s",
            file=sys.stderr,
        )

    report_path = write_report(records, REPORT_DIR)
    ok = [r for r in records if r["status"] == "OK"]
    avg_ol = sum(r["ol_count"] for r in ok) / len(ok) if ok else 0
    wide = sum(1 for r in ok if r["ol_count"] >= MEANINGFUL_WIDENING_THRESHOLD)
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(
        f"Completed: {len(ok)}/{len(records)} queries | "
        f"Avg OL URLs: {avg_ol:.1f} | "
        f"Meaningful widening (≥{MEANINGFUL_WIDENING_THRESHOLD}): {wide}/{len(ok)}",
        file=sys.stderr,
    )


# FUNCTIONS

# Run one query against OL engine, return record dict with pool-widening metrics
async def run_query(engine: OpenLibraryEngine, query: str) -> dict:
    record: dict = {
        "query": query,
        "ol_count": 0,
        "sample_titles": [],
        "sample_snippets": [],
        "ebook_access": {},
        "status": "EMPTY",
        "elapsed_ms": 0,
    }
    try:
        results = await engine.search(query, max_results=100)
        record["ol_count"] = len(results)
        record["sample_titles"] = [r.title for r in results[:5]]
        record["sample_snippets"] = [r.snippet for r in results[:3]]
        record["ebook_access"] = _ebook_distribution(results)
        record["status"] = "OK" if results else "EMPTY"
    except Exception as e:
        record["status"] = "TIMEOUT" if "timeout" in str(e).lower() else "ERROR"
        record["error"] = f"{type(e).__name__}: {str(e)[:80]}"
    return record


# Count ebook_access values across results by extracting from snippet
def _ebook_distribution(results) -> dict:
    dist: dict[str, int] = {}
    for r in results:
        if not r.snippet:
            continue
        # snippet ends with "ebook: <value>" — extract last token after "ebook: "
        if "ebook: " in r.snippet:
            val = r.snippet.split("ebook: ")[-1].strip()
            dist[val] = dist.get(val, 0) + 1
    return dist


# Write markdown A/B report and return path
def write_report(records: list[dict], report_dir: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"openlibrary_ab_{ts}.md"

    ok = [r for r in records if r["status"] == "OK"]
    avg_ol = sum(r["ol_count"] for r in ok) / len(ok) if ok else 0
    wide = sum(1 for r in ok if r["ol_count"] >= MEANINGFUL_WIDENING_THRESHOLD)
    total_ebook = _aggregate_ebook(ok)
    ebook_available = sum(v for k, v in total_ebook.items() if k not in ("no_ebook", "unknown"))
    ebook_total = sum(total_ebook.values())
    ebook_rate = ebook_available / ebook_total if ebook_total else 0

    lines = [
        f"# Open Library A/B Pool-Widening Report — {ts}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Queries run | {len(records)} |",
        f"| Completed (OK) | {len(ok)} |",
        f"| Avg OL unique URLs (completed) | {avg_ol:.1f} |",
        f"| Meaningful widening (≥{MEANINGFUL_WIDENING_THRESHOLD} URLs) | {wide}/{len(ok)} |",
        f"| Ebook availability rate | {ebook_rate:.0%} ({ebook_available}/{ebook_total} docs) |",
        "",
        "**Note:** OL URLs (openlibrary.org/works/*) are structurally unique — web engines do not",
        "index /works/ catalog pages. OL result count = unique-to-OL additive contribution.",
        "",
        "## Per-Query Results",
        "",
        "| # | Query | Status | OL URLs | Widening | Elapsed ms |",
        "|---|-------|--------|---------|---------|------------|",
    ]

    for i, r in enumerate(records, 1):
        query = r["query"][:45].replace("|", "\\|")
        widening = "✅" if r["ol_count"] >= MEANINGFUL_WIDENING_THRESHOLD else ("⚠️" if r["ol_count"] > 0 else "❌")
        lines.append(
            f"| {i} | {query} | {r['status']} | {r['ol_count']} | {widening} | {r['elapsed_ms']} |"
        )

    lines += ["", "## Sample Titles per Query", ""]
    for r in records:
        lines.append(f"### {r['query']}")
        lines.append("")
        if r["sample_titles"]:
            for t in r["sample_titles"]:
                lines.append(f"- {t}")
        else:
            lines.append(f"- *{r['status']}*")
        if r.get("sample_snippets"):
            lines.append("")
            lines.append("**Sample snippets:**")
            for s in r["sample_snippets"]:
                lines.append(f"- `{s}`")
        lines.append("")

    if total_ebook:
        lines += ["## Aggregate Ebook Access Distribution", ""]
        lines += ["| Access | Count |", "|--------|-------|"]
        for k, v in sorted(total_ebook.items(), key=lambda x: -x[1]):
            lines.append(f"| {k} | {v} |")
        lines.append("")

    non_ok = [r for r in records if r["status"] != "OK"]
    if non_ok:
        lines += ["## Non-OK Details", ""]
        for r in non_ok:
            lines.append(f"- **{r['status']}** `{r['query']}` — {r.get('error', 'no results')}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# Aggregate ebook_access distribution across all OK records
def _aggregate_ebook(ok_records: list[dict]) -> dict:
    agg: dict[str, int] = {}
    for r in ok_records:
        for k, v in r.get("ebook_access", {}).items():
            agg[k] = agg.get(k, 0) + v
    return agg


if __name__ == "__main__":
    asyncio.run(run_ab_smoke())
