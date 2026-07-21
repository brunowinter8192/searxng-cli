#!/usr/bin/env python3
"""Brave Search go/no-go probe — empirically checks the 3-condition gate for browser-scrape viability:
real result rows + no PoW/CAPTCHA trigger + per-query wall latency consistently <= 5s, run one query
at a time the way the production asyncio.gather pool would run each engine (no special-casing).

Self-contained: does NOT import src/ (dev-script isolation) — the pydoll Chrome session setup below
is a copy of the shape used by src/search/browser.py, not a shared import.

Background: Brave was previously dropped — PoW CAPTCHA across an 8-combination pydoll stealth matrix
(best 10/30), Patchright-with-Chromium (slider CAPTCHA instead of PoW, 0/30), Camoufox/Firefox (7/30).
Decisive killer was latency (10-15s/query on any CAPTCHA path). The untested angle per the stealth
resume note was Patchright with a REAL Chrome binary (channel="chrome", headless) — tried here FIRST
(see inline exploration below the module docstring in process-docs, not in this script) and found to
still trigger a slider CAPTCHA in headless mode (title "Captcha - Brave Search") on the very first
query, while the SAME real-Chrome binary succeeds headed (no CAPTCHA) — i.e. headless-ness itself is
the dominant signal for Patchright+real-Chrome against Brave, not the Chromium-vs-Chrome binary
identity the resume note suspected. Headed is not a viable production mode (server pipeline, no
display), so that angle is closed without a production candidate.

This probe instead runs the SECOND angle from scope: the pydoll stealth stack already used by the
production engines (src/search/browser.py fingerprint patches), which in initial hand-testing reached
Brave's results page headless WITHOUT a CAPTCHA — the opposite of the Patchright-headless outcome.
That is the stack measured here across the full query set.
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

SEARCH_URL = "https://search.brave.com/search?q={}"
LATENCY_GATE_S = 5.0
MAX_WAIT_CYCLES = 20
WAIT_INTERVAL = 0.3

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

_JS_WAIT = "return document.querySelectorAll('div[data-type=\"web\"]').length"

_JS_PARSE = """
var _cs = document.querySelectorAll('div[data-type="web"]');
var _out = [];
for (var _i = 0; _i < _cs.length; _i++) {
    var _c = _cs[_i];
    var _a = _c.querySelector('a[href^="http"]');
    var _title = _c.querySelector('.search-snippet-title');
    var _snip = _c.querySelector('.snippet-content .content') || _c.querySelector('.generic-snippet .content');
    if (!_a || !_a.href) continue;
    _out.push({
        url: _a.href,
        title: _title ? _title.textContent.trim() : (_a.textContent || '').trim(),
        snippet: _snip ? _snip.textContent.trim() : ''
    });
}
return JSON.stringify(_out);
"""

_JS_DIAGNOSE = """
var body = document.body ? document.body.innerText.toLowerCase() : '';
var title = document.title.toLowerCase();
var powLink = document.querySelector('a[href*="pow-captcha"]');
var markers = ['captcha', 'schieberegler ziehen', 'drag the slider', 'proof of work', 'checking your browser'];
var hit = null;
for (var _i = 0; _i < markers.length; _i++) {
    if (body.indexOf(markers[_i]) !== -1 || title.indexOf(markers[_i]) !== -1) { hit = markers[_i]; break; }
}
return JSON.stringify({marker: hit, pow_link: !!powLink, title: document.title, url: window.location.href});
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
                f"  -> {record['status']} | {record['count']} results | {record['elapsed_ms']}ms | "
                f"pow={record['pow_triggered']}",
                file=sys.stderr,
            )
    finally:
        await close_browser()

    report_path = write_report(records)
    ok_count = sum(1 for r in records if r["status"] == "OK")
    pow_count = sum(1 for r in records if r["pow_triggered"])
    under_gate = sum(1 for r in records if r["elapsed_ms"] <= LATENCY_GATE_S * 1000)
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(
        f"Result: {ok_count}/{len(records)} OK, {pow_count}/{len(records)} PoW-triggered, "
        f"{under_gate}/{len(records)} <= {LATENCY_GATE_S}s",
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


# Query DOM for div[data-type="web"] containers and return result dicts
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


# Diagnose PoW/CAPTCHA trigger via title/body marker scan + pow-captcha help-link presence
async def _diagnose(tab) -> dict:
    raw = await tab.execute_script(_JS_DIAGNOSE)
    val = _extract_value(raw)
    diag = {"marker": None, "pow_link": False, "title": "", "url": ""}
    if val:
        try:
            diag.update(json.loads(val))
        except (json.JSONDecodeError, TypeError):
            pass
    return diag


# Run one query end-to-end (new tab -> go_to -> wait -> parse/diagnose -> kill tab), return a data record
async def run_query(query: str, axis: str) -> dict:
    record: dict = {
        "query": query, "axis": axis, "count": 0, "status": "EMPTY",
        "pow_triggered": False, "samples": [], "diag": None,
    }
    tab = await _new_tab()
    try:
        await tab.go_to(SEARCH_URL.format(query.replace(" ", "+")), timeout=10.0)
        await asyncio.sleep(1.5)
        diag = await _diagnose(tab)
        record["diag"] = diag
        if diag["marker"] or diag["pow_link"]:
            record["status"] = "POW_BLOCKED"
            record["pow_triggered"] = True
        elif await _wait_for_results(tab):
            results = await _parse_results(tab, max_results=10)
            record["count"] = len(results)
            record["status"] = "OK" if results else "EMPTY"
            record["samples"] = [
                {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("snippet", "")[:160]}
                for r in results[:5]
            ]
        else:
            record["status"] = "EMPTY"
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


# Write markdown data report and return path
def write_report(records: list[dict]) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"brave_probe_{ts}.md"

    ok_count = sum(1 for r in records if r["status"] == "OK")
    pow_count = sum(1 for r in records if r["pow_triggered"])
    error_count = sum(1 for r in records if r["status"] == "ERROR")
    under_gate = sum(1 for r in records if r["elapsed_ms"] <= LATENCY_GATE_S * 1000)
    lo, med, hi = _latency_stats(records) if records else (0, 0, 0)

    verdict = (
        "CANDIDATE — real results, no PoW, all queries <= 5s"
        if pow_count == 0 and under_gate == len(records) and ok_count == len(records)
        else "DROP — " + (
            f"PoW/CAPTCHA triggered on {pow_count}/{len(records)} queries" if pow_count > 0
            else f"latency gate failed on {len(records) - under_gate}/{len(records)} queries"
        )
    )

    lines = [
        f"# Brave Search Go/No-Go Probe — {ts}",
        "",
        "Dev-only probe: real result rows + no PoW/CAPTCHA + per-query wall latency <= 5s, "
        "run one query at a time (no gather-special-casing) via the pydoll stealth stack "
        "(src/search/browser.py shape, self-contained here).",
        "",
        "## Verdict",
        "",
        f"**{verdict}**",
        "",
        "## Headline",
        "",
        f"- **Queries:** {len(records)}",
        f"- **OK (results returned):** {ok_count}",
        f"- **PoW/CAPTCHA triggered:** {pow_count}",
        f"- **ERROR:** {error_count}",
        f"- **Latency <= {LATENCY_GATE_S}s:** {under_gate}/{len(records)}",
        f"- **Latency distribution (ms):** min={lo}, median={med}, max={hi}",
        "",
        "## Stack + Selectors",
        "",
        "- Stack used for this run: pydoll stealth stack (`src/search/browser.py` fingerprint "
        "patches — disable-blink-features=AutomationControlled, real Chrome UA, webrtc-leak-protection), "
        "headless, per-query fresh tab via new_tab()/kill_tab().",
        "- Also tried (see module docstring): Patchright with a real Chrome binary (`channel=\"chrome\"`, "
        "headless) — triggered a slider CAPTCHA (title `Captcha - Brave Search`, `Schieberegler ziehen` / "
        "link to `/help/pow-captcha`) on the very first query. The SAME real-Chrome binary succeeded "
        "headed (no CAPTCHA) — headless-ness itself, not the Chromium-vs-real-Chrome binary identity, "
        "is what triggers Brave's PoW for the Patchright stack. Headed is not viable in production "
        "(server pipeline, no display), so that angle is closed.",
        "- Search URL: `https://search.brave.com/search?q=<q>` (spaces as `+`), plain GET, no consent/cookie step observed.",
        "- Result container: `div[data-type=\"web\"]`. Title: `.search-snippet-title` inside the result anchor. "
        "URL: `a[href^=\"http\"]` (direct destination, no redirect wrapper). Snippet: `.snippet-content .content` "
        "(falls back to `.generic-snippet .content`).",
        "- Block/CAPTCHA detection: `document.title` containing 'captcha', or body text containing "
        "'schieberegler ziehen'/'drag the slider'/'proof of work', or presence of `a[href*=\"pow-captcha\"]`.",
        "",
        "## Per-Query Results",
        "",
        "| # | Query | Axis | Status | Count | PoW | Elapsed ms | <= 5s? |",
        "|---|-------|------|--------|-------|-----|------------|--------|",
    ]
    for i, r in enumerate(records, 1):
        query = r["query"][:45].replace("|", "\\|")
        gate = "yes" if r["elapsed_ms"] <= LATENCY_GATE_S * 1000 else "NO"
        lines.append(
            f"| {i} | {query} | {r['axis']} | {r['status']} | {r['count']} | "
            f"{r['pow_triggered']} | {r['elapsed_ms']} | {gate} |"
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


if __name__ == "__main__":
    asyncio.run(run_probe())
