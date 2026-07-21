#!/usr/bin/env python3
"""Yandex Search go/no-go probe — empirically checks scrapeability of yandex.com, one of the few
remaining INDEPENDENT web indexes (own crawler, distinct from Google/Bing) — a genuine new-coverage
candidate for the general axis, and a hard anti-bot target (Yandex SmartCaptcha), in the Brave league.

Self-contained: does NOT import src/ (dev-script isolation) — the pydoll Chrome session setup
below is a copy of the shape used by src/search/browser.py, not a shared import.

Decision criterion (relaxed, per task): DROP only if there is truly no way through — blocked from
the very first query, never a single usable result. A handful of clean hits before any eventual
block is a CANDIDATE (real usage is 3-4 queries every few days — comfortably inside any clean
window observed), same reasoning that landed Brave as a production candidate. Quality (relevance
of results, especially for German/Western queries against a Russia-based index) is tracked as a
SEPARATE axis from access/blocking.

Empirical finding: `https://yandex.com/search/?text=<q>` (yandex.com, NOT yandex.ru) redirects to
`&lr=<region_id>` (a region parameter, auto-detected from IP geolocation — no block, no consent
step) and renders full results immediately. The old `li.serp-item` container selector is STILL the
live shape (confirmed via direct DOM inspection) — title is `a.OrganicTitle-Link` (direct href, NO
URL-wrapping/redirect unlike Bing's ck/a), snippet is `.OrganicText .OrganicTextContentSpan`.
"""

# INFRASTRUCTURE
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.commands import TargetCommands

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

SCRIPT_DIR = Path(__file__).parent
REPORT_DIR = SCRIPT_DIR / "md"

SESSION_DIR = str(Path.home() / ".searxng-mcp" / "browser-session")
REAL_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.7680.154 Safari/537.36"
)

SEARCH_URL = "https://yandex.com/search/?text={}"
LATENCY_GATE_S = 5.0
MAX_WAIT_CYCLES = 20
WAIT_INTERVAL = 0.3

# Same query set as 26_brave_probe.py / 28_bing_probe.py (mixed axes, DE+EN)
QUERIES = [
    ("beste kaffeemaschine test", "mainstream-de"),
    ("python asyncio tutorial", "docs-en"),
    ("gebrauchte waschmaschine frankfurt", "local-biz-de"),
    ("hausgeräte händler frankfurt", "local-biz-de"),
    ("gebrauchtwagen ankauf frankfurt", "local-biz-de"),
    ("best noise cancelling headphones 2025", "mainstream-en"),
    ("how does DNS work", "docs-en"),
    ("fastapi websocket reconnect handler", "docs-en"),
    ("climate change carbon capture technology 2025", "mainstream-en"),
    ("Mietvertrag Kündigungsfrist gesetzliche Regelung", "docs-de"),
]

_JS_WAIT = "return document.querySelectorAll('li.serp-item').length"

_JS_PARSE = """
var _cs = document.querySelectorAll('li.serp-item');
var _out = [];
for (var _i = 0; _i < _cs.length; _i++) {
    var _c = _cs[_i];
    var _a = _c.querySelector('a.OrganicTitle-Link');
    var _snip = _c.querySelector('.OrganicText .OrganicTextContentSpan') || _c.querySelector('.OrganicText');
    if (!_a || !_a.href) continue;
    _out.push({
        url: _a.href,
        title: _a.textContent.trim(),
        snippet: _snip ? _snip.textContent.trim() : ''
    });
}
return JSON.stringify(_out);
"""

_JS_DIAGNOSE = """
var body = document.body ? document.body.innerText.toLowerCase() : '';
var title = document.title.toLowerCase();
var url = window.location.href.toLowerCase();
var markers = ['captcha', 'confirm you are not a robot', 'unusual activity',
               'smartcaptcha', 'подтвердите, что запросы', 'подозрительн', 'ты робот'];
var hit = null;
for (var _i = 0; _i < markers.length; _i++) {
    if (body.indexOf(markers[_i]) !== -1 || title.indexOf(markers[_i]) !== -1) { hit = markers[_i]; break; }
}
var urlBlock = url.indexOf('showcaptcha') !== -1 || url.indexOf('checkcaptcha') !== -1 || url.indexOf('/captcha') !== -1;
return JSON.stringify({marker: hit, url_block: urlBlock, url: window.location.href, ready_state: document.readyState});
"""

_browser = None


# ORCHESTRATOR

async def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    try:
        for qi, (query, axis) in enumerate(QUERIES):
            print(f"[{qi + 1}/{len(QUERIES)}] ({axis}) {query}", file=sys.stderr)
            t0 = time.monotonic()
            record = await run_query(query, axis)
            record["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            records.append(record)
            print(
                f"  -> {record['status']} | {record['count']} results | {record['elapsed_ms']}ms",
                file=sys.stderr,
            )
    finally:
        await close_browser()

    report_path = write_report(records)
    ok_count = sum(1 for r in records if r["status"] == "OK")
    block_count = sum(1 for r in records if r["status"] == "BLOCKED")
    under_gate = sum(1 for r in records if r["elapsed_ms"] <= LATENCY_GATE_S * 1000)
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(
        f"Result: {ok_count}/{len(records)} OK, {block_count}/{len(records)} BLOCKED, "
        f"{under_gate}/{len(records)} <= {LATENCY_GATE_S}s, longest clean run = {_longest_clean_run(records)}",
        file=sys.stderr,
    )


# FUNCTIONS

# Kill stale Chrome processes using our session dir
def _kill_stale_chrome() -> None:
    subprocess.run(["pkill", "-f", f"user-data-dir={SESSION_DIR}"], capture_output=True)


# Build Chrome options matching the production stealth-browser shape
def _build_options() -> ChromiumOptions:
    options = ChromiumOptions()
    options.headless = not os.environ.get("SEARXNG_HEADED")
    options.add_argument(f"--user-data-dir={SESSION_DIR}")
    options.block_popups = True
    options.block_notifications = True
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.webrtc_leak_protection = True
    options.add_argument(f"--user-agent={REAL_USER_AGENT}")
    options.add_argument("--window-size=1920,1080")
    return options


# Get or create the shared browser + a fresh tab per query
async def _new_tab():
    global _browser
    if _browser is None:
        _kill_stale_chrome()
        _browser = Chrome(_build_options())
        await _browser.start()
    return await _browser.new_tab()


# Close a tab via browser-level Target.closeTarget
async def _kill_tab(tab) -> None:
    global _browser
    target_id = getattr(tab, "_target_id", None)
    if _browser is None or target_id is None:
        return
    try:
        await asyncio.wait_for(
            _browser._execute_command(TargetCommands.close_target(target_id)), timeout=5.0
        )
    except Exception as e:
        logging.warning("kill_tab failed (target_id=%s): %s", target_id, e)
    finally:
        _browser._tabs_opened.pop(target_id, None)


# Cleanup browser on shutdown
async def close_browser() -> None:
    global _browser
    if _browser is not None:
        await _browser.stop()
        _browser = None


# Extract primitive value from CDP execute_script result dict
def _extract_value(result):
    try:
        return result["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None


# Poll for result containers up to MAX_WAIT_CYCLES x WAIT_INTERVAL seconds, return True when found
async def _wait_for_results(tab) -> bool:
    for _ in range(MAX_WAIT_CYCLES):
        raw = await tab.execute_script(_JS_WAIT)
        count = _extract_value(raw)
        if count and int(count) > 0:
            return True
        await asyncio.sleep(WAIT_INTERVAL)
    return False


# Query DOM for li.serp-item containers and return result dicts (direct hrefs, no unwrap needed)
async def _parse_results(tab, max_results: int = 10) -> list[dict]:
    raw = await tab.execute_script(_JS_PARSE)
    value = _extract_value(raw)
    if not value:
        return []
    try:
        items = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
    return [item for item in items[:max_results] if item.get("url")]


# Diagnose CAPTCHA/block trigger via title/body marker scan (EN + RU phrasing) + URL path check
async def _diagnose(tab) -> dict:
    raw = await tab.execute_script(_JS_DIAGNOSE)
    val = _extract_value(raw)
    diag = {"marker": None, "url_block": False, "url": "", "ready_state": ""}
    if val:
        try:
            diag.update(json.loads(val))
        except (json.JSONDecodeError, TypeError):
            pass
    return diag


# Run one query end-to-end (new tab -> go_to -> wait/diagnose -> kill tab), return a data record
async def run_query(query: str, axis: str) -> dict:
    record: dict = {
        "query": query, "axis": axis, "count": 0, "status": "EMPTY",
        "samples": [], "diag": None,
    }
    tab = await _new_tab()
    try:
        await tab.go_to(SEARCH_URL.format(query.replace(" ", "+")), timeout=10.0)
        if await _wait_for_results(tab):
            results = await _parse_results(tab, max_results=10)
            record["count"] = len(results)
            record["status"] = "OK" if results else "EMPTY"
            record["samples"] = [
                {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("snippet", "")[:160]}
                for r in results[:5]
            ]
        else:
            diag = await _diagnose(tab)
            record["diag"] = diag
            record["status"] = "BLOCKED" if (diag["marker"] or diag["url_block"]) else "EMPTY"
    except Exception as e:
        record["status"] = "ERROR"
        record["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        await _kill_tab(tab)
    return record


# Compute latency distribution (min/median/max) across all queries
def _latency_stats(records: list[dict]) -> tuple[int, int, int]:
    ms = sorted(r["elapsed_ms"] for r in records)
    n = len(ms)
    median = ms[n // 2] if n % 2 else (ms[n // 2 - 1] + ms[n // 2]) // 2
    return ms[0], median, ms[-1]


# Longest run of consecutive OK (non-block, non-error) queries in original run order
def _longest_clean_run(records: list[dict]) -> int:
    best = cur = 0
    for r in records:
        if r["status"] == "OK":
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


# Write markdown data report and return path
def write_report(records: list[dict]) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"yandex_probe_{ts}.md"

    ok_count = sum(1 for r in records if r["status"] == "OK")
    blocked_count = sum(1 for r in records if r["status"] == "BLOCKED")
    empty_count = sum(1 for r in records if r["status"] == "EMPTY")
    error_count = sum(1 for r in records if r["status"] == "ERROR")
    under_gate = sum(1 for r in records if r["elapsed_ms"] <= LATENCY_GATE_S * 1000)
    lo, med, hi = _latency_stats(records) if records else (0, 0, 0)
    clean_run = _longest_clean_run(records)

    verdict = (
        "DROP — blocked from the very first query, zero usable results at any point"
        if ok_count == 0
        else f"CANDIDATE — {ok_count}/{len(records)} usable hits (longest clean run {clean_run}); "
             f"{'no block observed' if blocked_count == 0 else f'{blocked_count} blocked after clean hits — graceful-empty territory, like Brave'}"
    )

    lines = [
        f"# Yandex Scrapeability Probe — {ts}",
        "",
        "Go/no-go data probe (dev-only) for yandex.com — one of the few remaining INDEPENDENT web "
        "indexes (own crawler, not a Google/Bing frontend). Relaxed decision criterion: DROP only "
        "if there is truly no way through from query 1; a handful of clean hits before any "
        "eventual block is a CANDIDATE (real usage is low-volume, like Brave's).",
        "",
        "## Verdict",
        "",
        f"**{verdict}**",
        "",
        "## Quality Axis (separate from access)",
        "",
        _quality_note(records),
        "",
        "## Headline",
        "",
        f"- **Queries:** {len(records)}",
        f"- **OK (results returned):** {ok_count}",
        f"- **BLOCKED (explicit CAPTCHA/marker):** {blocked_count}",
        f"- **EMPTY (no results, no marker):** {empty_count}",
        f"- **ERROR:** {error_count}",
        f"- **Latency <= {LATENCY_GATE_S}s:** {under_gate}/{len(records)}",
        f"- **Latency distribution (ms):** min={lo}, median={med}, max={hi}",
        f"- **Longest consecutive clean (OK) run:** {clean_run}",
        "",
        "## URL / Selector Findings",
        "",
        "- Search URL: `https://yandex.com/search/?text=<q>` (international domain, NOT yandex.ru; "
        "spaces as `+`). Yandex auto-appends `&lr=<region_id>` (region param, IP-geolocation-based) "
        "on redirect — no consent step, no block.",
        "- Old selector `li.serp-item` is STILL the live result container shape.",
        "- Title + href: `a.OrganicTitle-Link` inside each `li.serp-item` — href is the DIRECT "
        "destination URL, no tracking-redirect wrapper (unlike Bing's `ck/a`).",
        "- Snippet: `.OrganicText .OrganicTextContentSpan` (falls back to `.OrganicText`).",
        "- Block detection: title/body scan for EN + RU CAPTCHA/bot-check phrasing, plus a URL-path "
        "check for `showcaptcha`/`checkcaptcha`/`/captcha` substrings.",
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

    lines += ["", "## Sample Results (quality eyeball)", ""]
    for i, r in enumerate(records, 1):
        if not r["samples"]:
            continue
        lines.append(f"### [{i}] {r['query']} ({r['axis']}) — {r['count']} results")
        lines.append("")
        for s in r["samples"]:
            lines.append(f"- **{s['title']}** — {s['url']}")
            lines.append(f"  - {s['snippet']}")
        lines.append("")

    non_ok = [r for r in records if r["status"] != "OK"]
    if non_ok:
        lines += ["## Non-OK Details", ""]
        for r in non_ok:
            lines.append(f"### [{r['status']}] {r['query']} ({r['axis']})")
            lines.append("")
            if r.get("error"):
                lines.append(f"- **Error:** {r['error']}")
            if r.get("diag"):
                lines.append(f"- **Diagnosis:** `{json.dumps(r['diag'])}`")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# Build an honest quality-axis note from the German-query subset of the run
def _quality_note(records: list[dict]) -> str:
    de_records = [r for r in records if r["axis"].endswith("-de") and r["status"] == "OK"]
    if not de_records:
        return "No successful German-axis queries to assess relevance from this run."
    domains = []
    for r in de_records:
        for s in r["samples"][:3]:
            domains.append(s["url"])
    return (
        f"{len(de_records)} German-axis queries returned usable results. See the sample titles/urls "
        "below per query for a direct relevance read — the honest call belongs in the completion "
        "report after eyeballing them, not asserted generically here."
    )


if __name__ == "__main__":
    asyncio.run(run_probe())
