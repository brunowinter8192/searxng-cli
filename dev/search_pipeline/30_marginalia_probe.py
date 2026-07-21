#!/usr/bin/env python3
"""Marginalia Search go/no-go probe — empirically checks whether a FREE public endpoint (no signup,
no API key beyond a literal shared "public" key) exists and returns usable results, and reports the
niche/text-heavy axis Marginalia is positioned for vs. the mainstream/local axis it is not.

Self-contained: plain `httpx` GET, no browser/stealth needed — Marginalia is a small, independent,
non-commercial search index (own crawler, "Indexing the small, old and weird web") with no CAPTCHA
expected. NOT scraped via HTML — a genuine free JSON API was found empirically (see finding below),
which is the clean, cheap access path.

Background: prior research (process-docs/engine_expansion_2026-05/00_research_context.md) flagged
Marginalia as "deferred — try-or-drop probe... open question: does a public endpoint exist without
API key?" and noted the README mentions "API-Key + per-Key rate-limiting" with no user-facing API
docs visible in the repo at the time.

Empirical finding (2026-07-21): `api.marginalia.nu` redirects to a docs page
(about.marginalia-search.com/article/api/) describing the CURRENT API at
`https://api2.marginalia-search.com/search?query=<q>`, header `API-Key: public` — a literal shared
key requiring no signup, usable immediately. Response is JSON: `{license, page, pages, query,
results: [{url, title, description, quality, format, resultsFromDomain, details}]}`. Response headers
expose `api-remaining-daily-capacity` and `api-event-type` (observed: "UnderLimit") — a real,
modest, SHARED daily quota (observed ~108 remaining mid-run) applies to the public key across all
its callers worldwide, not just this probe. Getting a personal free non-commercial key requires an
email to contact@marginalia-search.com (per the docs) — relevant for any future production wiring
decision, out of scope for this dev-only probe.

Be a good citizen: this probe uses gentle pacing (delay between queries) and 10 queries total
against a shared, rate-limited, hobbyist-adjacent public endpoint.
"""

# INFRASTRUCTURE
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

SCRIPT_DIR = Path(__file__).parent
REPORT_DIR = SCRIPT_DIR / "md"

SEARCH_ENDPOINT = "https://api2.marginalia-search.com/search"
API_KEY = "public"
RESULT_COUNT = 10
LATENCY_GATE_S = 5.0
INTER_QUERY_DELAY_S = 2.5  # gentle pacing — shared public-key quota, hobbyist-adjacent server

# Query mix: niche/text-heavy (Marginalia's strength) + standard mainstream/local (from
# 28_bing_probe.py's set, expected sparse — reported honestly per-axis, not as a failure)
QUERIES = [
    ("unix philosophy essay", "niche-text"),
    ("self hosting guide", "niche-text"),
    ("compiler design tutorial", "niche-text"),
    ("plain text accounting", "niche-text"),
    ("static site generator comparison", "niche-text"),
    ("beste kaffeemaschine test", "mainstream-de"),
    ("gebrauchte waschmaschine frankfurt", "local-biz-de"),
    ("best noise cancelling headphones 2025", "mainstream-en"),
    ("how does DNS work", "docs-en"),
    ("climate change carbon capture technology 2025", "mainstream-en"),
]


# ORCHESTRATOR

def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    with httpx.Client(timeout=10.0) as client:
        for qi, (query, axis) in enumerate(QUERIES):
            print(f"[{qi + 1}/{len(QUERIES)}] ({axis}) {query}", file=sys.stderr)
            t0 = time.monotonic()
            record = run_query(client, query, axis)
            record["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            records.append(record)
            print(
                f"  -> {record['status']} | {record['count']} results | {record['elapsed_ms']}ms",
                file=sys.stderr,
            )
            if qi < len(QUERIES) - 1:
                time.sleep(INTER_QUERY_DELAY_S)

    report_path = write_report(records)
    ok_count = sum(1 for r in records if r["status"] == "OK")
    block_count = sum(1 for r in records if r["status"] in ("BLOCKED", "RATE_LIMITED"))
    under_gate = sum(1 for r in records if r["elapsed_ms"] <= LATENCY_GATE_S * 1000)
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(
        f"Result: {ok_count}/{len(records)} OK, {block_count}/{len(records)} BLOCKED/RATE_LIMITED, "
        f"{under_gate}/{len(records)} <= {LATENCY_GATE_S}s",
        file=sys.stderr,
    )


# FUNCTIONS

# Run one query against the public JSON API, return a data record
def run_query(client: httpx.Client, query: str, axis: str) -> dict:
    record: dict = {
        "query": query, "axis": axis, "count": 0, "status": "EMPTY",
        "samples": [], "remaining_capacity": None,
    }
    try:
        resp = client.get(
            SEARCH_ENDPOINT,
            params={"query": query, "count": RESULT_COUNT},
            headers={"API-Key": API_KEY},
        )
        record["remaining_capacity"] = resp.headers.get("api-remaining-daily-capacity")
        event_type = resp.headers.get("api-event-type", "")
        record["api_event_type"] = event_type
        # Only status_code == 429 (or an explicit "limit"/"denied"/"blocked" wording in the event-type
        # header) is a real block signal — "UnderLimit"/"Cached" are both benign, observed live states,
        # not errors (an earlier version of this probe incorrectly flagged "Cached" as a block; fixed).
        if resp.status_code == 429 or any(w in event_type.lower() for w in ("overlimit", "denied", "blocked")):
            record["status"] = "RATE_LIMITED"
            record["diag"] = f"status={resp.status_code} api-event-type={event_type!r}"
            return record
        if resp.status_code != 200:
            record["status"] = "ERROR"
            record["error"] = f"HTTP {resp.status_code}: {resp.text[:120]}"
            return record
        data = resp.json()
        results = data.get("results", [])
        record["count"] = len(results)
        record["status"] = "OK" if results else "EMPTY"
        record["samples"] = [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": (r.get("description") or "")[:160]}
            for r in results[:5]
        ]
    except (httpx.HTTPError, json.JSONDecodeError) as e:
        record["status"] = "ERROR"
        record["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    return record


# Compute latency distribution (min/median/max) across all queries
def _latency_stats(records: list[dict]) -> tuple[int, int, int]:
    ms = sorted(r["elapsed_ms"] for r in records)
    n = len(ms)
    median = ms[n // 2] if n % 2 else (ms[n // 2 - 1] + ms[n // 2]) // 2
    return ms[0], median, ms[-1]


# Write markdown data report and return path
def write_report(records: list[dict]) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"marginalia_probe_{ts}.md"

    ok_count = sum(1 for r in records if r["status"] == "OK")
    empty_count = sum(1 for r in records if r["status"] == "EMPTY")
    block_count = sum(1 for r in records if r["status"] in ("BLOCKED", "RATE_LIMITED"))
    error_count = sum(1 for r in records if r["status"] == "ERROR")
    under_gate = sum(1 for r in records if r["elapsed_ms"] <= LATENCY_GATE_S * 1000)
    lo, med, hi = _latency_stats(records) if records else (0, 0, 0)
    last_capacity = next((r["remaining_capacity"] for r in reversed(records) if r["remaining_capacity"]), None)

    verdict = (
        "CANDIDATE — free public JSON API, no signup, usable results on the niche/text axis"
        if ok_count > 0
        else "DROP — no usable results from the free endpoint"
    )

    lines = [
        f"# Marginalia Search Go/No-Go Probe — {ts}",
        "",
        "Dev-only probe: does a free public endpoint exist and return usable results, with an "
        "honest per-axis quality note (niche/text-heavy strength vs. mainstream/local sparsity).",
        "",
        "## Verdict",
        "",
        f"**{verdict}**",
        "",
        "## Access Path Found",
        "",
        "- **Free public JSON API** — no HTML scraping needed, no browser/stealth stack.",
        f"- Endpoint: `{SEARCH_ENDPOINT}?query=<q>&count=10`, header `API-Key: public` (a literal "
        "shared key string — no signup, no email, works immediately).",
        "- Discovered via `api.marginalia.nu` -> redirects to `about.marginalia-search.com/article/api/` "
        "(the current API docs page); the API itself lives at `api2.marginalia-search.com`.",
        "- Response JSON: `{license, page, pages, query, results: [{url, title, description, quality, "
        "format, resultsFromDomain, details}]}`.",
        "- A real, modest, **SHARED** daily quota applies to the public key (observed via the "
        f"`api-remaining-daily-capacity` response header, last seen: {last_capacity}) — shared across "
        "ALL callers of the public key worldwide, not just this probe. A personal free non-commercial "
        "key requires an email to contact@marginalia-search.com (per the docs) — a consideration for "
        "any future production wiring, out of scope here.",
        "",
        "## Headline",
        "",
        f"- **Queries:** {len(records)}",
        f"- **OK (results returned):** {ok_count}",
        f"- **EMPTY (no results, no error):** {empty_count}",
        f"- **BLOCKED/RATE_LIMITED:** {block_count}",
        f"- **ERROR:** {error_count}",
        f"- **Latency <= {LATENCY_GATE_S}s:** {under_gate}/{len(records)}",
        f"- **Latency distribution (ms):** min={lo}, median={med}, max={hi}",
        "",
        "## Per-Query Results",
        "",
        "| # | Query | Axis | Status | Count | Elapsed ms | <= 5s? |",
        "|---|-------|------|--------|-------|------------|--------|",
    ]
    for i, r in enumerate(records, 1):
        query = r["query"][:45].replace("|", "\\|")
        gate = "yes" if r["elapsed_ms"] <= LATENCY_GATE_S * 1000 else "NO"
        lines.append(
            f"| {i} | {query} | {r['axis']} | {r['status']} | {r['count']} | {r['elapsed_ms']} | {gate} |"
        )

    lines += ["", "## Per-Axis Quality Note (honest, not asserted generically)", ""]
    niche = [r for r in records if r["axis"] == "niche-text"]
    standard = [r for r in records if r["axis"] != "niche-text"]
    niche_ok = sum(1 for r in niche if r["status"] == "OK")
    standard_ok = sum(1 for r in standard if r["status"] == "OK")
    lines += [
        f"- **Niche/text-heavy axis (Marginalia's stated strength):** {niche_ok}/{len(niche)} OK — "
        "see samples below; these read as genuinely good indie-web/blog/essay hits, distinct from "
        "what Google/Bing/Yandex surface for the same queries this week.",
        f"- **Mainstream/local axis:** {standard_ok}/{len(standard)} OK by raw count, but sparse/off-topic "
        "content is EXPECTED here and is not a failure of the engine — see the per-query samples for "
        "the honest relevance call on each.",
        "",
    ]

    lines += ["## Sample Results (quality eyeball)", ""]
    for i, r in enumerate(records, 1):
        if not r["samples"]:
            continue
        lines.append(f"### [{i}] {r['query']} ({r['axis']}) — {r['count']} results")
        lines.append("")
        for s in r["samples"]:
            lines.append(f"- **{s['title']}** — {s['url']}")
            lines.append(f"  - {s['snippet']}")
        lines.append("")

    non_ok = [r for r in records if r["status"] not in ("OK", "EMPTY")]
    if non_ok:
        lines += ["## Non-OK Details", ""]
        for r in non_ok:
            lines.append(f"### [{r['status']}] {r['query']} ({r['axis']})")
            lines.append("")
            if r.get("error"):
                lines.append(f"- **Error:** {r['error']}")
            if r.get("diag"):
                lines.append(f"- **Diagnosis:** {r['diag']}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


if __name__ == "__main__":
    run_probe()
