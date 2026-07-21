#!/usr/bin/env python3
"""Bing Search go/no-go probe — empirically checks scrapeability of bing.com for a SECOND,
independent access path to the Bing web index (redundant to DuckDuckGo, which already surrogates
the same index) — symmetric to google(direct)+startpage(surrogate).

Self-contained: does NOT import src/ (dev-script isolation) — the pydoll Chrome session setup
below is a copy of the shape used by src/search/browser.py, not a shared import.

Historical note: Bing was dropped 2026-05-04 on COVERAGE grounds (DDG already IS Bing's index —
no new URLs) and its old selector `#b_results .b_algo` had drifted. This probe answers a DIFFERENT
question — scrapeability + latency for redundancy, not coverage — and re-derives the CURRENT DOM
from scratch rather than trusting the old selector.

Empirical finding: `#b_results .b_algo` had NOT actually drifted in the way the drop note implied —
`li.b_algo` containers are still present and populated (10/page). What DID change/needs handling:
Bing wraps every organic result href in a `bing.com/ck/a?...&u=<prefixed-base64>&...` tracking
redirect (not present historically at prior evaluation, or not documented) — the destination URL
must be unwrapped: parse the `u` query param, strip its 2-char prefix (observed as `a1`), then
base64-urlsafe-decode (with padding) to get the real URL. A cookie/consent banner ("Microsoft und
unsere Drittanbieter verwenden Cookies...") is present in the DOM but is NON-BLOCKING for scraping —
it renders as an overlay alongside full results, not a gate (unlike Google's consent redirect or
Startpage's homepage-token flow); no click/accept step is needed to read `li.b_algo` content.
"""

# INFRASTRUCTURE
import asyncio
import base64
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

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

SEARCH_URL = "https://www.bing.com/search?q={}"
LATENCY_GATE_S = 5.0
MAX_WAIT_CYCLES = 20
WAIT_INTERVAL = 0.3

# Same query set as 26_brave_probe.py (mixed axes, DE+EN)
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

_JS_WAIT = "return document.querySelectorAll('li.b_algo').length"

_JS_PARSE = """
var _cs = document.querySelectorAll('li.b_algo');
var _out = [];
for (var _i = 0; _i < _cs.length; _i++) {
    var _c = _cs[_i];
    var _h2a = _c.querySelector('h2 a');
    var _cap = _c.querySelector('.b_caption p') || _c.querySelector('.b_caption');
    if (!_h2a || !_h2a.href) continue;
    _out.push({
        url: _h2a.href,
        title: _h2a.textContent.trim(),
        snippet: _cap ? _cap.textContent.trim() : ''
    });
}
return JSON.stringify(_out);
"""

_JS_DIAGNOSE = """
var body = document.body ? document.body.innerText.toLowerCase() : '';
var title = document.title.toLowerCase();
var markers = ['captcha', 'unusual traffic', 'verify you are human', 'are you a robot',
               'access denied', 'automated queries', 'ungewöhnlichen datenverkehr',
               'roboter', 'bestätigen sie, dass sie ein mensch'];
var hit = null;
for (var _i = 0; _i < markers.length; _i++) {
    if (body.indexOf(markers[_i]) !== -1 || title.indexOf(markers[_i]) !== -1) { hit = markers[_i]; break; }
}
return JSON.stringify({marker: hit, url: window.location.href, ready_state: document.readyState});
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


# Unwrap Bing's `bing.com/ck/a?...&u=<prefixed-base64>&...` tracking redirect to the real
# destination URL — the `u` param is base64url-encoded with a 2-char prefix (observed: "a1")
def _clean_url(href: str) -> str:
    if not href:
        return ""
    parsed = urlparse(href)
    qs = parse_qs(parsed.query)
    u = qs.get("u", [None])[0]
    if not u:
        return href
    payload = u[2:] if len(u) > 2 else u
    padded = payload + "=" * (-len(payload) % 4)
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
    except Exception:
        return href


# Poll for result containers up to MAX_WAIT_CYCLES x WAIT_INTERVAL seconds, return True when found
async def _wait_for_results(tab) -> bool:
    for _ in range(MAX_WAIT_CYCLES):
        raw = await tab.execute_script(_JS_WAIT)
        count = _extract_value(raw)
        if count and int(count) > 0:
            return True
        await asyncio.sleep(WAIT_INTERVAL)
    return False


# Query DOM for li.b_algo containers and return result dicts with unwrapped URLs
async def _parse_results(tab, max_results: int = 10) -> list[dict]:
    raw = await tab.execute_script(_JS_PARSE)
    value = _extract_value(raw)
    if not value:
        return []
    try:
        items = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
    out = []
    for item in items[:max_results]:
        url = _clean_url(item.get("url", ""))
        if not url:
            continue
        out.append({"url": url, "title": item.get("title", ""), "snippet": item.get("snippet", "")})
    return out


# Diagnose block/CAPTCHA trigger via title/body marker scan (EN + DE phrasing)
async def _diagnose(tab) -> dict:
    raw = await tab.execute_script(_JS_DIAGNOSE)
    val = _extract_value(raw)
    diag = {"marker": None, "url": "", "ready_state": ""}
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
            record["status"] = "BLOCKED" if diag["marker"] else "EMPTY"
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
    path = REPORT_DIR / f"bing_probe_{ts}.md"

    ok_count = sum(1 for r in records if r["status"] == "OK")
    blocked_count = sum(1 for r in records if r["status"] == "BLOCKED")
    empty_count = sum(1 for r in records if r["status"] == "EMPTY")
    error_count = sum(1 for r in records if r["status"] == "ERROR")
    under_gate = sum(1 for r in records if r["elapsed_ms"] <= LATENCY_GATE_S * 1000)
    lo, med, hi = _latency_stats(records) if records else (0, 0, 0)

    verdict = (
        "CANDIDATE — real results, no persistent block, usable latency"
        if ok_count == len(records) and under_gate == len(records)
        else "DROP — " + (
            f"blocked on {blocked_count}/{len(records)} queries" if blocked_count > 0
            else f"latency gate failed on {len(records) - under_gate}/{len(records)} queries"
            if under_gate < len(records)
            else f"only {ok_count}/{len(records)} returned results"
        )
    )

    lines = [
        f"# Bing Scrapeability Probe — {ts}",
        "",
        "Go/no-go data probe (dev-only) for bing.com as a second, independent access path to the "
        "Bing web index (redundant to DuckDuckGo) — question is SCRAPEABILITY + LATENCY, not "
        "coverage (overlap with DDG is expected and fine by design).",
        "",
        "## Verdict",
        "",
        f"**{verdict}**",
        "",
        "## Headline",
        "",
        f"- **Queries:** {len(records)}",
        f"- **OK (results returned):** {ok_count}",
        f"- **BLOCKED (explicit marker):** {blocked_count}",
        f"- **EMPTY (no results, no marker):** {empty_count}",
        f"- **ERROR:** {error_count}",
        f"- **Latency <= {LATENCY_GATE_S}s:** {under_gate}/{len(records)}",
        f"- **Latency distribution (ms):** min={lo}, median={med}, max={hi}",
        "",
        "## URL / Selector Findings",
        "",
        "- Search URL: `https://www.bing.com/search?q=<q>` (spaces as `+`), plain GET, no consent/form step required.",
        "- Old selector `#b_results .b_algo` had NOT actually drifted structurally — "
        "`li.b_algo` inside `#b_results` is still the live result container (10/page).",
        "- Title + href: `h2 a` inside each `li.b_algo`. Snippet: `.b_caption p` (falls back to `.b_caption`).",
        "- **New since the old evaluation:** every organic href is wrapped in a "
        "`bing.com/ck/a?...&u=<prefixed-base64>&...` tracking redirect — unwrapped by parsing the "
        "`u` query param, stripping its 2-char prefix (observed: `a1`), then base64url-decoding "
        "(with padding) to recover the real destination URL.",
        "- A Microsoft cookie/consent banner is present in the DOM (`Microsoft und unsere "
        "Drittanbieter verwenden Cookies...`) but does NOT gate result rendering — `li.b_algo` "
        "content is fully present in the DOM alongside it; no click/accept step needed for scraping.",
        "- Block detection: title/body scan for EN + DE bot-check phrasing "
        "(`captcha`, `unusual traffic`, `verify you are human`, `ungewöhnlichen datenverkehr`, etc.).",
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


if __name__ == "__main__":
    asyncio.run(run_probe())
