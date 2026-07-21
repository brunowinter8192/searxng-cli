#!/usr/bin/env python3
"""Headed hard-engine lane probe (macOS) — Brave via headed-but-backgrounded Chrome.

Self-contained: does NOT import src/ (dev-script isolation) — the pydoll session setup below
follows the shape of src/search/browser.py, not a shared import.

Background: dev/search_pipeline/26_brave_probe.py established that headless (both pydoll-stealth
and Patchright+real-Chrome) trips Brave's PoW/CAPTCHA — pydoll-stealth got 4/10 clean before a
persistent block, Patchright+real-Chrome was blocked immediately headless but passed HEADED. Xvfb
is irrelevant here (Linux-only virtual-display trick; this Mac has a real screen). The lever tested
in this probe: run the system Google Chrome HEADED (a real window renders) but BACKGROUNDED via
macOS `open -g` so it never steals focus — pydoll connects to it over CDP exactly as if it had
launched it directly.

Launch mechanism (the actual novel piece of this probe):
- pydoll's BrowserProcessManager accepts a `process_creator` callback: a function taking the full
  launch command list (`[binary_location, "--remote-debugging-port=<port>", *other_args]`) and
  returning a subprocess.Popen. Chrome(options) does not expose this via its constructor, so the
  manager is swapped in AFTER construction, BEFORE start():
      browser = Chrome(options)
      browser._browser_process_manager = BrowserProcessManager(process_creator=_open_process_creator)
      tab = await browser.start()
- `_open_process_creator` drops the resolved binary_location (unused — `open -a` targets the app
  bundle directly) and re-launches via:
      open -g -n -a "Google Chrome" --args --remote-debugging-port=<port> --user-data-dir=<isolated dir> ...
  `-g` = no foreground activation (no focus steal). `-n` = force a new instance (belt-and-suspenders;
  the isolated --user-data-dir alone already forces a fresh process since Chrome's singleton check
  is a lock file inside the profile dir).
- `open -g` returns immediately, so the Popen handed back to pydoll is the short-lived `open`
  wrapper, not Chrome itself — pydoll's own stop_process() has nothing to reap. Teardown is CDP
  `browser.stop()` (Browser.close command — quits the whole isolated-profile Chrome instance since
  it's the only window in that profile) PLUS an explicit `pkill -f user-data-dir=<isolated dir>`
  safety net regardless of whether stop() succeeds.
"""

# INFRASTRUCTURE
import asyncio
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.managers import BrowserProcessManager

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

SCRIPT_DIR = Path(__file__).parent
REPORT_DIR = SCRIPT_DIR / "md"

# Dedicated, isolated profile — NOT the shared engine session dir (src/search/browser.py's
# SESSION_DIR) — for block-isolation from production engines and to force a fresh Chrome instance.
PROFILE_DIR = str(Path.home() / ".searxng-mcp" / "brave-headed-probe-session")

SEARCH_URL = "https://search.brave.com/search?q={}"
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
        await _start_headed_background_browser()
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
        await _stop_headed_background_browser()

    report_path = write_report(records)
    ok_count = sum(1 for r in records if r["status"] == "OK")
    pow_count = sum(1 for r in records if r["pow_triggered"])
    under_gate = sum(1 for r in records if r["elapsed_ms"] <= LATENCY_GATE_S * 1000)
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(
        f"Result: {ok_count}/{len(records)} OK, {pow_count}/{len(records)} PoW-triggered, "
        f"{under_gate}/{len(records)} <= {LATENCY_GATE_S}s, longest clean run = {_longest_clean_run(records)}",
        file=sys.stderr,
    )


# FUNCTIONS

# Launch the system Google Chrome headed-but-backgrounded via macOS `open -g` — the actual novel
# launch mechanism this probe tests (see module docstring for the full rationale)
def _open_process_creator(command: list[str]) -> subprocess.Popen:
    args = command[1:]  # drop resolved binary_location; `open -a` targets the app bundle directly
    open_cmd = ["open", "-g", "-n", "-a", "Google Chrome", "--args", *args]
    logging.info("Headed-background launch: %s", open_cmd)
    return subprocess.Popen(open_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# Kill any stale Chrome process pinned to the isolated probe profile
def _kill_stale_chrome() -> None:
    subprocess.run(["pkill", "-f", f"user-data-dir={PROFILE_DIR}"], capture_output=True)


# Start one shared headed-background Chrome instance (isolated profile) for the whole run
async def _start_headed_background_browser() -> None:
    global _browser
    _kill_stale_chrome()
    await asyncio.sleep(0.5)
    options = ChromiumOptions()
    options.add_argument(f"--user-data-dir={PROFILE_DIR}")
    options.block_popups = True
    options.block_notifications = True
    # options.headless left at its default False — headed is the whole point of this probe
    _browser = Chrome(options)
    _browser._browser_process_manager = BrowserProcessManager(process_creator=_open_process_creator)
    await _browser.start()


# Stop the browser via CDP Browser.close, then a pkill safety net regardless of outcome — the
# process_creator's Popen (the short-lived `open` wrapper) gives pydoll's own stop_process() nothing
# real to reap, so the pkill is not optional cleanup, it's the actual teardown guarantee.
async def _stop_headed_background_browser() -> None:
    global _browser
    if _browser is not None:
        try:
            await _browser.stop()
        except Exception as e:
            logging.warning("browser.stop() failed (expected to fall through to pkill): %s", e)
        _browser = None
    _kill_stale_chrome()


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


# Run one query end-to-end (new tab -> go_to -> diagnose/parse -> close tab), return a data record
async def run_query(query: str, axis: str) -> dict:
    record: dict = {
        "query": query, "axis": axis, "count": 0, "status": "EMPTY",
        "pow_triggered": False, "samples": [], "diag": None,
    }
    tab = await _browser.new_tab()
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
        await tab.close()
    return record


# Compute latency distribution (min/median/max) across all queries
def _latency_stats(records: list[dict]) -> tuple[int, int, int]:
    ms = sorted(r["elapsed_ms"] for r in records)
    n = len(ms)
    median = ms[n // 2] if n % 2 else (ms[n // 2 - 1] + ms[n // 2]) // 2
    return ms[0], median, ms[-1]


# Longest run of consecutive OK (non-PoW, non-error) queries in original run order
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
    path = REPORT_DIR / f"brave_headed_lane_probe_{ts}.md"

    ok_count = sum(1 for r in records if r["status"] == "OK")
    pow_count = sum(1 for r in records if r["pow_triggered"])
    error_count = sum(1 for r in records if r["status"] == "ERROR")
    under_gate = sum(1 for r in records if r["elapsed_ms"] <= LATENCY_GATE_S * 1000)
    lo, med, hi = _latency_stats(records) if records else (0, 0, 0)
    clean_run = _longest_clean_run(records)

    verdict = (
        "CANDIDATE — real results, <=5s, usable run of consecutive clean queries"
        if clean_run >= 3 and under_gate == len(records) and pow_count < len(records)
        else "DROP — " + (
            f"PoW/CAPTCHA triggered on {pow_count}/{len(records)} queries, longest clean run only {clean_run}"
            if pow_count > 0 else f"latency gate failed on {len(records) - under_gate}/{len(records)} queries"
        )
    )

    lines = [
        f"# Brave Headed-Background Lane Probe — {ts}",
        "",
        "Dev-only probe: headed-but-backgrounded Chrome (macOS `open -g`, isolated profile) against "
        "Brave Search, one query at a time. Gate: real results, <=5s per query, and a usable run of "
        "3-4+ consecutive clean (no-PoW) queries (relaxed bar — does not need to be block-free forever).",
        "",
        "## Verdict",
        "",
        f"**{verdict}**",
        "",
        "## Launch Mechanism",
        "",
        "- `Chrome(options)` constructed normally, then `browser._browser_process_manager` is "
        "swapped for `BrowserProcessManager(process_creator=_open_process_creator)` BEFORE "
        "`await browser.start()` (`Chrome.__init__` does not expose `process_creator`).",
        "- `_open_process_creator(command)` drops `command[0]` (resolved binary_location, unused) "
        "and runs `open -g -n -a \"Google Chrome\" --args --remote-debugging-port=<port> "
        "--user-data-dir=<isolated dir> ...` — `-g` = no focus steal, `-n` = force new instance.",
        "- Isolated profile: `~/.searxng-mcp/brave-headed-probe-session` (NOT the shared engine "
        "session dir) — block-isolation + forces a genuinely fresh Chrome process.",
        "- Teardown: CDP `browser.stop()` (works — it's a real `Browser.close` CDP command against "
        "the real Chrome instance) PLUS an unconditional `pkill -f user-data-dir=<isolated dir>` "
        "safety net, because `open -g` returns immediately so pydoll's own `stop_process()` only "
        "ever had the short-lived `open` wrapper process to reap, not Chrome itself.",
        "",
        "## Headline",
        "",
        f"- **Queries:** {len(records)}",
        f"- **OK (results returned):** {ok_count}",
        f"- **PoW/CAPTCHA triggered:** {pow_count}",
        f"- **ERROR:** {error_count}",
        f"- **Latency <= {LATENCY_GATE_S}s:** {under_gate}/{len(records)}",
        f"- **Latency distribution (ms):** min={lo}, median={med}, max={hi}",
        f"- **Longest consecutive clean (no-PoW) run:** {clean_run}",
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
