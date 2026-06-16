#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import httpx
from pydoll.browser import Chrome

TARGET_URL = "https://www.coindesk.com/latest-crypto-news"
TIMELINE_API_PATH = "/api/v1/articles/timeline"
OUTPUT_DIR = Path(__file__).parent / "05b_output"
STATE_FILE = OUTPUT_DIR / "state.json"

# Cumulative seconds after Chrome closes at which to retry the same API URL
WARMTH_INTERVALS = [0, 10, 20, 30, 60, 120, 180, 300]

CLICKS_TO_TRIGGER = 8

SKIP_HEADERS = frozenset({
    ":authority", ":method", ":path", ":scheme",
    "host", "content-length", "content-encoding", "transfer-encoding",
})

REAL_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.7680.154 Safari/537.36"
)

_JS_DISMISS_COOKIE = """
(function() {
    var btn = document.querySelector('#onetrust-accept-btn-handler');
    if (btn) { btn.click(); return 'clicked-accept'; }
    var sdk = document.getElementById('onetrust-consent-sdk');
    if (sdk) { sdk.remove(); return 'removed-sdk'; }
    return 'not-found';
})();
"""

_JS_CLICK_BTN = """
(function() {
    var candidates = Array.from(document.querySelectorAll('button, a[role="button"], [role="button"]'));
    for (var i = 0; i < candidates.length; i++) {
        var t = candidates[i].textContent.trim();
        if (/more\\s+stories|load\\s+more|show\\s+more/i.test(t)) {
            candidates[i].scrollIntoView({block: 'center', behavior: 'smooth'});
            candidates[i].click();
            return true;
        }
    }
    return false;
})();
"""


# ORCHESTRATOR

# Phase W: browser warmup → save state (URL + headers) → close Chrome → replay same URL at
# increasing intervals to measure warmth duration.
# Phase C: at first 403 → httpx feedpage GET → retry → feedpage rewarm test.
#          subprocess cold test to verify process-vs-IP.
async def warmth_probe_workflow() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = OUTPUT_DIR / f"warmth_{ts}.md"

    test_url = None
    test_headers = None
    baseline_status = None

    port = get_free_port()
    session_dir = tempfile.mkdtemp(prefix="coindesk_warmth_")
    chrome = None
    tab = None

    try:
        print("Phase W: launching Chrome …", file=sys.stderr)
        launch_background_chrome(port, session_dir)
        ws_url = wait_for_ws_url(port)
        chrome = Chrome()
        tab = await chrome.connect(ws_url)

        print(f"Phase W: navigating to {TARGET_URL} …", file=sys.stderr)
        await tab.go_to(TARGET_URL, timeout=60)
        await asyncio.sleep(3.0)

        raw = await tab.execute_script(_JS_DISMISS_COOKIE)
        print(f"Phase W: cookie consent: {_extract_value(raw)}", file=sys.stderr)
        await asyncio.sleep(0.5)

        print(f"Phase W: capturing timeline request ({CLICKS_TO_TRIGGER} clicks) …", file=sys.stderr)
        timeline_entry = await capture_timeline_request(tab, CLICKS_TO_TRIGGER)

        if timeline_entry is None:
            print("ERROR: Timeline API not found in HAR.", file=sys.stderr)
            return

        test_url = timeline_entry["request"]["url"]
        raw_hdrs = {h["name"]: h["value"] for h in timeline_entry["request"]["headers"]}
        test_headers = filter_headers(raw_hdrs)
        print(f"Phase W: captured URL: {test_url}", file=sys.stderr)

        # Baseline: verify URL works while Chrome is still open (warm)
        baseline = httpx.get(test_url, headers=test_headers, follow_redirects=True, timeout=30)
        baseline_status = baseline.status_code
        print(f"Phase W: baseline (Chrome open) → {baseline_status}", file=sys.stderr)

        # Save state to disk (subprocess cold test reads this)
        state = {"url": test_url, "headers": test_headers}
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
        print(f"Phase W: state saved → {STATE_FILE}", file=sys.stderr)

    finally:
        if tab:
            try:
                await tab.close()
            except Exception as e:
                print(f"tab.close (non-fatal): {e}", file=sys.stderr)
        if chrome:
            try:
                await chrome.close()
            except Exception as e:
                print(f"chrome.close (non-fatal): {e}", file=sys.stderr)
        kill_chrome_on_port(port)
        shutil.rmtree(session_dir, ignore_errors=True)
        print("Phase W: Chrome closed — timing ladder starts now.", file=sys.stderr)

    if test_url is None or test_headers is None:
        print("ERROR: State not captured — aborting.", file=sys.stderr)
        return

    # Phase W continued: timing ladder
    ladder_results = run_warmth_ladder(test_url, test_headers, WARMTH_INTERVALS)

    # Phase C: feedpage rewarm + subprocess cold test (only if ladder hit a 403)
    feedpage_result = None
    subprocess_result = None

    first_403 = next((r for r in ladder_results if r["status"] != 200), None)
    if first_403 is not None:
        print("Phase C: feedpage rewarm test …", file=sys.stderr)
        feedpage_status, feedpage_bytes = fetch_feedpage(test_headers)
        print(f"Phase C: feedpage GET → {feedpage_status} ({feedpage_bytes} bytes)", file=sys.stderr)

        time.sleep(1.0)
        rewarm = httpx.get(test_url, headers=test_headers, follow_redirects=True, timeout=30)
        print(f"Phase C: API after feedpage GET → {rewarm.status_code}", file=sys.stderr)
        feedpage_result = {
            "feedpage_status": feedpage_status,
            "feedpage_bytes": feedpage_bytes,
            "api_after_feedpage": rewarm.status_code,
            "api_after_feedpage_snippet": rewarm.content[:200].decode("utf-8", errors="replace")
            if rewarm.status_code != 200 else None,
        }

        print("Phase C: subprocess cold test …", file=sys.stderr)
        subprocess_result = subprocess_cold_test(STATE_FILE)
        print(f"Phase C: subprocess result: {subprocess_result}", file=sys.stderr)
    else:
        print(
            f"Phase C: skipped — no 403 in {WARMTH_INTERVALS[-1]}s ladder.",
            file=sys.stderr,
        )

    write_warmth_report(
        report_path, ts, test_url, baseline_status,
        WARMTH_INTERVALS, ladder_results, feedpage_result, subprocess_result,
    )
    print(f"Warmth report → {report_path}")


# FUNCTIONS

# Bind port 0 to get a free OS-assigned port
def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# Launch Chrome in background via open -gna
def launch_background_chrome(port: int, session_dir: str) -> None:
    subprocess.run(
        [
            "open", "-gna", "Google Chrome", "--args",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={session_dir}",
            f"--user-agent={REAL_UA}",
            "--window-size=1920,1080",
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        check=True,
    )


# Poll /json/version until Chrome responds; return webSocketDebuggerUrl
def wait_for_ws_url(port: int, timeout: float = 30.0) -> str:
    url = f"http://localhost:{port}/json/version"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                return json.loads(r.read())["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.5)
    raise TimeoutError(f"Chrome not ready on port {port}")


# Kill Chrome process bound to this debug port
def kill_chrome_on_port(port: int) -> None:
    subprocess.run(["pkill", "-f", f"remote-debugging-port={port}"], check=False)


# Unpack CDP execute_script result dict
def _extract_value(raw):
    try:
        return raw["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None


# Click More-stories n times under HAR record; return first HAR entry matching TIMELINE_API_PATH
async def capture_timeline_request(tab, n_clicks: int) -> dict | None:
    async with tab.request.record() as capture:
        for i in range(n_clicks):
            raw = await tab.execute_script(_JS_CLICK_BTN)
            clicked = bool(_extract_value(raw))
            print(f"  click {i + 1}/{n_clicks}: {'OK' if clicked else 'miss'}", file=sys.stderr)
            await asyncio.sleep(2.5)
    for entry in capture.entries:
        if TIMELINE_API_PATH in entry["request"]["url"]:
            return entry
    return None


# Strip HTTP/2 pseudo-headers and client-managed headers
def filter_headers(raw: dict) -> dict:
    return {k: v for k, v in raw.items() if k.lower() not in SKIP_HEADERS}


# Replay the same API URL at cumulative intervals (seconds) after Chrome close
def run_warmth_ladder(url: str, headers: dict, intervals: list) -> list:
    results = []
    elapsed_total = 0.0

    for target_t in intervals:
        delta = target_t - elapsed_total
        if delta > 0.5:
            print(f"  sleeping {round(delta, 1)}s → T={target_t}s …", file=sys.stderr)
            time.sleep(delta)
        elapsed_total = target_t

        t0 = time.monotonic()
        try:
            resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
            call_elapsed = round(time.monotonic() - t0, 2)
            elapsed_total += call_elapsed
            results.append({
                "t_seconds": target_t,
                "status": resp.status_code,
                "call_elapsed": call_elapsed,
                "body_snippet": resp.content[:200].decode("utf-8", errors="replace")
                if resp.status_code != 200 else None,
            })
        except Exception as e:
            call_elapsed = round(time.monotonic() - t0, 2)
            elapsed_total += call_elapsed
            results.append({"t_seconds": target_t, "status": -1, "error": str(e)})

        print(f"  T={target_t}s → {results[-1]['status']}", file=sys.stderr)

    return results


# Fetch feed HTML page via plain httpx (no browser); return (status, byte_count)
def fetch_feedpage(api_headers: dict) -> tuple:
    feed_headers = {
        k: v for k, v in api_headers.items()
        if k.lower() in {"user-agent", "accept-language", "accept"}
    }
    try:
        resp = httpx.get(TARGET_URL, headers=feed_headers, follow_redirects=True, timeout=30)
        return resp.status_code, len(resp.content)
    except Exception as e:
        return -1, 0


# Run API call in a fresh subprocess; no prior coindesk connection in that process
def subprocess_cold_test(state_file: Path) -> dict:
    script_lines = [
        "import json, httpx, sys",
        f"state = json.loads(open({json.dumps(str(state_file))}).read())",
        "try:",
        "    r = httpx.get(state['url'], headers=state['headers'], follow_redirects=True, timeout=30)",
        "    print(r.status_code)",
        "except Exception as e:",
        "    print(f'ERROR:{e}', file=sys.stderr)",
        "    print(-1)",
    ]
    script = "\n".join(script_lines)

    tmp_script = None
    try:
        fd, tmp_script = tempfile.mkstemp(suffix=".py", prefix="cd_cold_")
        os.close(fd)
        Path(tmp_script).write_text(script, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, tmp_script],
            capture_output=True, text=True, timeout=60,
        )
        return {
            "status": proc.stdout.strip(),
            "stderr": proc.stderr.strip()[:300],
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "status": "?"}
    except Exception as e:
        return {"error": str(e), "status": "?"}
    finally:
        if tmp_script and os.path.exists(tmp_script):
            os.unlink(tmp_script)


# Write warmth probe report (MD)
def write_warmth_report(
    path: Path,
    ts: str,
    test_url: str,
    baseline_status: int | None,
    intervals: list,
    ladder_results: list,
    feedpage_result: dict | None,
    subprocess_result: dict | None,
) -> None:
    lines = ["# CoinDesk IP Warmth Probe Report"]
    lines.append(f"\n**Run:** {ts}\n")
    lines.append(f"**Test URL (fixed for all calls):** `{test_url}`\n")
    lines.append(f"**Baseline (Chrome still open):** `{baseline_status}`\n")

    lines.append("## Phase W — Warmth Timing Ladder\n")
    lines.append("Same URL replayed at cumulative T seconds after Chrome closes.\n")
    lines.append("| T (s after close) | Status | Call elapsed | Notes |")
    lines.append("|-------------------|--------|--------------|-------|")
    for r in ladder_results:
        snippet = r.get("body_snippet") or ""
        notes = f"`{snippet[:60]}`" if snippet else "—"
        lines.append(
            f"| {r['t_seconds']} | **{r['status']}** |"
            f" {r.get('call_elapsed', r.get('error', '?'))}s | {notes} |"
        )

    first_403 = next((r for r in ladder_results if r["status"] != 200), None)
    last_200_idx = max(
        (i for i, r in enumerate(ladder_results) if r["status"] == 200), default=-1
    )

    if first_403 is None:
        lines.append(f"\n✅ **No 403 in {intervals[-1]}s** — warmth lasts at least {intervals[-1]}s.\n")
    else:
        last_200_t = ladder_results[last_200_idx]["t_seconds"] if last_200_idx >= 0 else "?"
        lines.append(
            f"\n**Warmth window:** last 200 at T={last_200_t}s,"
            f" first non-200 at T={first_403['t_seconds']}s.\n"
        )

    if feedpage_result is not None:
        lines.append("## Phase C-1 — Feedpage Rewarm Test\n")
        lines.append(
            "Plain `httpx.get` of the feed HTML page (no browser) after warmth expired:\n"
        )
        lines.append(
            f"- `httpx.get(\"{TARGET_URL}\")` → HTTP {feedpage_result['feedpage_status']}"
            f" ({feedpage_result['feedpage_bytes']} bytes)"
        )
        api_after = feedpage_result["api_after_feedpage"]
        lines.append(f"- API call immediately after → **{api_after}**\n")
        if api_after == 200:
            lines.append("✅ **httpx feedpage GET IS sufficient to re-warm the IP.**\n")
        else:
            snip = feedpage_result.get("api_after_feedpage_snippet") or ""
            lines.append(f"❌ **httpx feedpage GET does NOT re-warm** — browser required.")
            if snip:
                lines.append(f"\nAPI body snippet: `{snip[:100]}`\n")

    if subprocess_result is not None:
        lines.append("## Phase C-2 — Subprocess Cold Test\n")
        lines.append(
            "Fresh `python` subprocess loads `state.json` (URL + headers),"
            " calls the API with NO prior coindesk connection in that process.\n"
        )
        sub_status = subprocess_result.get("status", "?")
        lines.append(f"- Subprocess → **{sub_status}**")
        if subprocess_result.get("stderr"):
            lines.append(f"- stderr: `{subprocess_result['stderr'][:200]}`\n")
        if sub_status == "200":
            lines.append("\nSubprocess → 200: warmth is **IP-level** (not process-level).\n")
        elif sub_status and sub_status.startswith(("4", "5")):
            lines.append(
                f"\nSubprocess → {sub_status}: consistent with IP warmth expired"
                f" (both parent + subprocess cold — IP-level check).\n"
            )
        else:
            lines.append(f"\nSubprocess result ambiguous: `{subprocess_result}`\n")

    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(warmth_probe_workflow())
