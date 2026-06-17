#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import json
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
from curl_cffi import requests as curl_requests
from pydoll.browser import Chrome

TARGET_URL = "https://www.coindesk.com/latest-crypto-news"
TIMELINE_API_PATH = "/api/v1/articles/timeline"
OUTPUT_DIR = Path(__file__).parent / "04_output"

CLICKS_TO_TRIGGER = 8    # API fires ~click 6 (SSR buffer exhausted); 8 for safety
CURSOR_LOOP_CALLS = 3    # default chained cursor calls; overridden by --loop N
CALL_DELAY = 0.3         # seconds between cursor-loop HTTP calls
IMPERSONATE_TARGET = "chrome136"

# HTTP/2 pseudo-headers + client-managed headers — strip before replay
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

# Navigate to CoinDesk feed, click More-stories to trigger Timeline API,
# capture full request headers via HAR recorder, replay with httpx + curl_cffi,
# and if 200, chain cursor calls to verify pure HTTP pagination.
async def timeline_replay_workflow(loop: int = CURSOR_LOOP_CALLS, delay: float = CALL_DELAY, rate_test: bool = False) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = OUTPUT_DIR / f"report_{ts}.md"

    port = get_free_port()
    session_dir = tempfile.mkdtemp(prefix="coindesk_replay_")
    chrome = None
    tab = None

    try:
        print(f"Launching Chrome on port {port} …", file=sys.stderr)
        launch_background_chrome(port, session_dir)
        ws_url = wait_for_ws_url(port)
        print(f"Connected: {ws_url}", file=sys.stderr)

        chrome = Chrome()
        tab = await chrome.connect(ws_url)

        print(f"Navigating to {TARGET_URL} …", file=sys.stderr)
        await tab.go_to(TARGET_URL, timeout=60)
        await asyncio.sleep(3.0)

        raw = await tab.execute_script(_JS_DISMISS_COOKIE)
        print(f"Cookie consent: {_extract_value(raw)}", file=sys.stderr)
        await asyncio.sleep(0.5)

        print(f"HAR-recording {CLICKS_TO_TRIGGER} clicks to trigger Timeline API …", file=sys.stderr)
        timeline_entry = await capture_timeline_request(tab, CLICKS_TO_TRIGGER)

        if timeline_entry is None:
            print("ERROR: Timeline API not captured — no matching HAR entry.", file=sys.stderr)
            write_report(report_path, ts, None, {}, {}, {}, None, None)
            return

        api_url = timeline_entry["request"]["url"]
        raw_headers = {h["name"]: h["value"] for h in timeline_entry["request"]["headers"]}
        replay_headers = filter_replay_headers(raw_headers)
        print(f"Captured: {api_url}", file=sys.stderr)
        print(f"Headers: raw={len(raw_headers)} replay={len(replay_headers)}", file=sys.stderr)

        status_httpx, body_httpx, _, err_httpx = replay_httpx(api_url, replay_headers)
        status_curl, body_curl, _, err_curl = replay_curl_cffi(api_url, replay_headers)
        print(f"httpx → {status_httpx}  |  curl_cffi → {status_curl}", file=sys.stderr)

        body_200 = None
        if status_httpx == 200:
            body_200 = body_httpx
        elif status_curl == 200:
            body_200 = body_curl

        cursor_results = None
        cursor_results_rate = None
        first_json_sample = None
        if body_200 is not None:
            first_json_sample = extract_json_sample(body_200)
            print(f"Running cursor loop: {loop} calls, {delay}s delay …", file=sys.stderr)
            cursor_results = cursor_loop(api_url, replay_headers, body_200, n=loop, delay=delay)

            if rate_test and body_200 is not None:
                print("Rate-test: re-running loop with 2.0s delay …", file=sys.stderr)
                cursor_results_rate = cursor_loop(api_url, replay_headers, body_200, n=loop, delay=2.0)

        write_report(
            report_path, ts, api_url, raw_headers, replay_headers,
            {"httpx": (status_httpx, err_httpx), "curl_cffi": (status_curl, err_curl)},
            first_json_sample,
            cursor_results,
            cursor_results_rate,
        )
        print(f"Report → {report_path}")

    finally:
        if tab is not None:
            try:
                await tab.close()
            except Exception as e:
                print(f"tab.close (non-fatal): {e}", file=sys.stderr)
        if chrome is not None:
            try:
                await chrome.close()
            except Exception as e:
                print(f"chrome.close (non-fatal): {e}", file=sys.stderr)
        kill_chrome_on_port(port)
        shutil.rmtree(session_dir, ignore_errors=True)
        print("Cleanup complete.", file=sys.stderr)


# FUNCTIONS

# Bind to port 0 to get a free OS-assigned port
def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# Launch Chrome in background via open -gna (new instance, no foreground)
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
            with urllib.request.urlopen(url, timeout=2) as resp:
                data = json.loads(resp.read())
                return data["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.5)
    raise TimeoutError(f"Chrome did not start on port {port} within {timeout}s")


# Kill the Chrome process bound to this debug port
def kill_chrome_on_port(port: int) -> None:
    try:
        subprocess.run(["pkill", "-f", f"remote-debugging-port={port}"], check=False)
    except Exception as e:
        print(f"pkill (non-fatal): {e}", file=sys.stderr)


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
            print(f"  click {i + 1}/{n_clicks}: {'OK' if clicked else 'no-button'}", file=sys.stderr)
            await asyncio.sleep(2.5)

    for entry in capture.entries:
        if TIMELINE_API_PATH in entry["request"]["url"]:
            return entry
    return None


# Strip HTTP/2 pseudo-headers and client-managed headers; preserve the rest exactly
def filter_replay_headers(raw: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in raw.items() if k.lower() not in SKIP_HEADERS}


# Replay URL with httpx plain; return (status_code, body_bytes, resp_headers, error_str)
def replay_httpx(url: str, headers: dict[str, str]) -> tuple[int, bytes | None, dict, str | None]:
    try:
        resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
        return resp.status_code, resp.content, dict(resp.headers), None
    except Exception as e:
        return -1, None, {}, str(e)


# Replay URL with curl_cffi Chrome impersonation; return (status_code, body_bytes, resp_headers, error_str)
def replay_curl_cffi(url: str, headers: dict[str, str]) -> tuple[int, bytes | None, dict, str | None]:
    try:
        resp = curl_requests.get(
            url, headers=headers, impersonate=IMPERSONATE_TARGET, timeout=30
        )
        return resp.status_code, resp.content, dict(resp.headers), None
    except Exception as e:
        return -1, None, {}, str(e)


# Parse response body JSON; return (last_article_id, last_article_display_date) for cursor chaining
def extract_cursor(body: bytes) -> tuple[str | None, str | None]:
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return None, None

    articles = None
    if isinstance(data, list):
        articles = data
    elif isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                articles = v
                break

    if not articles:
        return None, None

    last = articles[-1]
    last_id = last.get("_id") or last.get("id") or last.get("slug")
    article_dates = last.get("articleDates") or {}
    last_date = (
        article_dates.get("displayDate") or article_dates.get("publishedAt")
        or last.get("displayDate") or last.get("publishedAt") or last.get("date")
    )
    return str(last_id) if last_id else None, str(last_date) if last_date else None


# Build next cursor URL from lastId + lastDisplayDate (lang=en required)
def build_cursor_url(last_id: str, last_date: str) -> str:
    return (
        f"https://www.coindesk.com/api/v1/articles/timeline"
        f"?size=16&lastId={last_id}&lastDisplayDate={last_date}&lang=en"
    )


# Count articles in JSON response body
def count_articles(body: bytes) -> int:
    try:
        data = json.loads(body)
    except Exception:
        return 0
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                return len(v)
    return 0


# Extract first/last article summary from response for structure inspection
def extract_json_sample(body: bytes) -> dict | None:
    try:
        data = json.loads(body)
    except Exception:
        return None

    articles = data if isinstance(data, list) else None
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                articles = v
                break

    if not articles:
        return {"raw_keys": list(data.keys()) if isinstance(data, dict) else type(data).__name__}

    first, last = articles[0], articles[-1]
    return {
        "total_in_response": len(articles),
        "first_article_keys": list(first.keys()),
        "last_article_id": last.get("id") or last.get("slug"),
        "last_article_display_date": last.get("displayDate") or last.get("publishedAt") or last.get("date"),
        "first_article_title": first.get("title") or first.get("headline") or "(unknown key)",
    }


# Chain n cursor-based HTTP calls from the first 200 response; return per-call stats + summary.
# On first 403: capture full diagnostics (URL, body, resp-headers, cursor-source article)
# and immediately run a recoverability test (10s + 30s retry).
def cursor_loop(
    first_url: str,
    headers: dict[str, str],
    first_body: bytes,
    n: int,
    delay: float = CALL_DELAY,
) -> list[dict]:
    results = []
    body = first_body
    prev_body = first_body   # body from the call before the current one
    url = first_url
    total_articles = 0
    oldest_date = None

    for i in range(n):
        last_id, last_date = extract_cursor(body)
        if not last_id or not last_date:
            results.append({"call": i + 1, "error": f"cursor extraction failed — url={url}"})
            break

        next_url = build_cursor_url(last_id, last_date)
        print(f"  call {i + 1}: {next_url}", file=sys.stderr)

        if i > 0:
            time.sleep(delay)

        t0 = time.monotonic()
        status_h, next_body_h, resp_hdrs_h, err_h = replay_httpx(next_url, headers)
        elapsed = time.monotonic() - t0

        status_c, next_body_c, resp_hdrs_c, err_c = None, None, {}, None
        if status_h != 200:
            t0c = time.monotonic()
            status_c, next_body_c, resp_hdrs_c, err_c = replay_curl_cffi(next_url, headers)
            elapsed_c = time.monotonic() - t0c

        if status_h == 200:
            status, next_body, err = status_h, next_body_h, err_h
        elif status_c == 200:
            status, next_body, err, elapsed = status_c, next_body_c, err_c, elapsed_c
        else:
            # First 403/non-200: capture full diagnostics
            diag = diagnose_403(
                next_url, headers, prev_body,
                status_h, next_body_h, resp_hdrs_h,
                status_c, next_body_c, resp_hdrs_c,
            )
            results.append({
                "call": i + 1, "url": next_url,
                "status_httpx": status_h, "status_curl": status_c,
                "elapsed": round(elapsed, 2), "error": err_h or err_c,
            })
            results.append({"call": "DIAG_403", **diag})
            break

        n_arts = count_articles(next_body) if next_body else 0
        total_articles += n_arts

        if last_date and (oldest_date is None or last_date < oldest_date):
            oldest_date = last_date

        results.append({
            "call": i + 1,
            "url": next_url,
            "status": status,
            "articles": n_arts,
            "elapsed": round(elapsed, 2),
            "oldest_so_far": last_date[:10] if last_date else None,
            "error": err,
        })

        if not next_body:
            break
        prev_body = body
        body = next_body
        url = next_url

    # Summary sentinel
    if results:
        ok_rows = [r for r in results if r.get("status") == 200]
        elapsed_vals = [r["elapsed"] for r in ok_rows if "elapsed" in r]
        avg_elapsed = round(sum(elapsed_vals) / len(elapsed_vals), 3) if elapsed_vals else None
        results.append({
            "call": "SUMMARY",
            "total_calls": len(ok_rows),
            "total_articles": total_articles,
            "oldest_date": oldest_date[:10] if oldest_date else None,
            "avg_elapsed": avg_elapsed,
            "non_200": len([r for r in results
                            if isinstance(r.get("call"), int)
                            and r.get("status") not in (200,)
                            and "status_httpx" in r]),
        })

    return results


# On first non-200: capture URL, body snippet, resp-headers, cursor-source article;
# then run recoverability test (retry at +10s and +30s).
def diagnose_403(
    url: str,
    req_headers: dict,
    prev_body: bytes,
    status_h: int, body_h: bytes | None, resp_hdrs_h: dict,
    status_c: int | None, body_c: bytes | None, resp_hdrs_c: dict,
) -> dict:
    print(f"  [DIAG] 403 on {url} — running recoverability test …", file=sys.stderr)

    # Inspect cursor-source article (last article of previous successful response)
    cursor_source = inspect_cursor_source(prev_body)

    # Response header signals
    def flag_headers(hdrs: dict) -> dict:
        keys = {k.lower() for k in hdrs}
        return {
            "retry_after": hdrs.get("retry-after") or hdrs.get("Retry-After"),
            "x_ratelimit": {k: v for k, v in hdrs.items() if k.lower().startswith("x-ratelimit")},
            "server": hdrs.get("server") or hdrs.get("Server"),
            "cf_ray": hdrs.get("cf-ray") or hdrs.get("CF-Ray"),
            "cf_cache_status": hdrs.get("cf-cache-status"),
            "x_cache": hdrs.get("x-cache") or hdrs.get("X-Cache"),
            "via": hdrs.get("via") or hdrs.get("Via"),
            "all_header_names": sorted(hdrs.keys()),
        }

    body_snippet_h = (body_h or b"")[:300].decode("utf-8", errors="replace")
    body_snippet_c = (body_c or b"")[:300].decode("utf-8", errors="replace")

    # Recoverability: wait 10s, retry; wait 30s more, retry
    print("  [DIAG] sleeping 10s, retrying …", file=sys.stderr)
    time.sleep(10)
    s10, _, hdrs10, _ = replay_httpx(url, req_headers)
    print(f"  [DIAG] +10s → httpx {s10}", file=sys.stderr)

    print("  [DIAG] sleeping 30s, retrying …", file=sys.stderr)
    time.sleep(30)
    s40, _, hdrs40, _ = replay_httpx(url, req_headers)
    print(f"  [DIAG] +40s → httpx {s40}", file=sys.stderr)

    return {
        "failing_url": url,
        "status_httpx": status_h,
        "status_curl": status_c,
        "resp_headers_httpx": flag_headers(resp_hdrs_h),
        "resp_headers_curl": flag_headers(resp_hdrs_c),
        "body_snippet_httpx": body_snippet_h,
        "body_snippet_curl": body_snippet_c,
        "cursor_source_article": cursor_source,
        "recoverability": {
            "retry_at_10s": s10,
            "retry_at_40s": s40,
        },
    }


# Extract metadata of the last article from a response body (the article that generated the cursor)
def inspect_cursor_source(body: bytes) -> dict:
    try:
        data = json.loads(body)
    except Exception:
        return {"error": "body not JSON"}

    articles = data if isinstance(data, list) else None
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                articles = v
                break

    if not articles:
        return {"error": "no articles array found"}

    last = articles[-1]
    return {
        "_id": last.get("_id"),
        "storyType": last.get("storyType"),
        "articleDates": last.get("articleDates"),
        "pathname": last.get("pathname"),
        "title": last.get("title"),
    }


# Write MD report with captured headers, replay status codes, cursor-loop results, and rate-test
def write_report(
    path: Path,
    ts: str,
    api_url: str | None,
    raw_headers: dict,
    replay_headers: dict,
    replay_results: dict,
    first_json_sample: dict | None,
    cursor_results: list | None,
    cursor_results_rate: list | None = None,
) -> None:
    lines = ["# CoinDesk Timeline API — HTTP Replay Probe"]
    lines.append(f"\n**Run:** {ts}\n")

    if api_url is None:
        lines.append("## Result: CAPTURE FAILED\n")
        lines.append(f"Timeline API (`{TIMELINE_API_PATH}`) did not appear in HAR entries after {CLICKS_TO_TRIGGER} clicks.")
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    lines.append("## Captured Request\n")
    lines.append(f"**URL:** `{api_url}`\n")

    lines.append("## Request Headers (replay set)\n")
    lines.append(f"Raw headers from HAR: **{len(raw_headers)}** | After pseudo-header strip: **{len(replay_headers)}**\n")
    lines.append("| Header | Value |")
    lines.append("|--------|-------|")
    for k in sorted(replay_headers.keys()):
        v = replay_headers[k]
        v_disp = (v[:100] + "…") if len(v) > 100 else v
        lines.append(f"| `{k}` | `{v_disp}` |")

    stripped = sorted(set(raw_headers.keys()) - set(replay_headers.keys()))
    if stripped:
        lines.append(f"\n**Stripped:** `{', '.join(stripped)}`\n")

    lines.append("\n## Replay Results\n")
    lines.append("| Client | Status | Error |")
    lines.append("|--------|--------|-------|")
    for client, (status, err) in replay_results.items():
        err_disp = (str(err)[:80] + "…") if err and len(str(err)) > 80 else (str(err) if err else "—")
        lines.append(f"| {client} | **{status}** | {err_disp} |")

    if first_json_sample:
        lines.append("\n## Response JSON Structure (first 200 response)\n")
        lines.append("```json")
        lines.append(json.dumps(first_json_sample, indent=2, ensure_ascii=False))
        lines.append("```\n")

    if cursor_results is not None:
        lines.append("\n## Cursor Loop Results\n")
        if not cursor_results:
            lines.append("_(no results — cursor extraction failed before first call)_\n")
        else:
            summary = next((r for r in cursor_results if r.get("call") == "SUMMARY"), None)
            call_rows = [r for r in cursor_results if r.get("call") != "SUMMARY"]
            if summary:
                lines.append("### Summary\n")
                lines.append("| Metric | Value |")
                lines.append("|--------|-------|")
                lines.append(f"| Successful calls | {summary['total_calls']} |")
                lines.append(f"| Total articles fetched | {summary['total_articles']} |")
                lines.append(f"| Oldest date reached | {summary['oldest_date']} |")
                lines.append(f"| Avg elapsed per call | {summary['avg_elapsed']}s |")
                lines.append(f"| Non-200 responses | {summary['non_200']} |\n")
            # 403 diagnostics block (if present)
            diag = next((r for r in cursor_results if r.get("call") == "DIAG_403"), None)
            if diag:
                lines.append("\n### 403 Diagnostics\n")
                lines.append(f"**Failing URL:** `{diag.get('failing_url', '?')}`\n")
                lines.append(f"**Status:** httpx={diag.get('status_httpx')} curl_cffi={diag.get('status_curl')}\n")
                rec = diag.get("recoverability", {})
                lines.append("**Recoverability:**\n")
                lines.append(f"- Retry at +10s → `{rec.get('retry_at_10s')}`")
                lines.append(f"- Retry at +40s → `{rec.get('retry_at_40s')}`\n")
                lines.append("**Cursor-source article (last of previous call):**\n")
                lines.append("```json")
                lines.append(json.dumps(diag.get("cursor_source_article", {}), indent=2, ensure_ascii=False))
                lines.append("```\n")
                lines.append("**Response body snippet (httpx):**\n")
                lines.append("```")
                lines.append(diag.get("body_snippet_httpx", "(empty)"))
                lines.append("```\n")
                h_httpx = diag.get("resp_headers_httpx", {})
                lines.append("**Response headers — signals (httpx):**\n")
                lines.append("```json")
                lines.append(json.dumps(h_httpx, indent=2, ensure_ascii=False))
                lines.append("```\n")

            lines.append("### Per-Call Log\n")
            lines.append("| Call | Status | Articles | Oldest-so-far | Elapsed | Error |")
            lines.append("|------|--------|----------|---------------|---------|-------|")
            call_rows_plain = [r for r in cursor_results
                               if isinstance(r.get("call"), int)]
            for r in call_rows_plain:
                s = r.get("status") or f"httpx={r.get('status_httpx')} curl={r.get('status_curl')}"
                lines.append(
                    f"| {r['call']} | {s} | {r.get('articles', '—')} | "
                    f"{r.get('oldest_so_far', '—')} | "
                    f"{r.get('elapsed', '—')}s | {r.get('error') or '—'} |"
                )

    if cursor_results_rate is not None:
        lines.append("\n## Rate-Test Results (2s delay)\n")
        summary_r = next((r for r in cursor_results_rate if r.get("call") == "SUMMARY"), None)
        if summary_r:
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Successful calls | {summary_r['total_calls']} |")
            lines.append(f"| Non-200 | {summary_r['non_200']} |")
            lines.append(f"| Oldest date | {summary_r['oldest_date']} |")
            lines.append(f"| Avg elapsed | {summary_r['avg_elapsed']}s |\n")
        diag_r = next((r for r in cursor_results_rate if r.get("call") == "DIAG_403"), None)
        if diag_r:
            rec_r = diag_r.get("recoverability", {})
            lines.append(f"**403 still hit at 2s delay** — retry_at_10s={rec_r.get('retry_at_10s')} retry_at_40s={rec_r.get('retry_at_40s')}\n")
        else:
            lines.append("**No 403 encountered at 2s delay — rate-limit confirmed (time-based).**\n")

    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CoinDesk Timeline API HTTP replay probe")
    parser.add_argument("--loop", type=int, default=CURSOR_LOOP_CALLS, metavar="N",
                        help=f"cursor-loop calls after initial capture (default: {CURSOR_LOOP_CALLS})")
    parser.add_argument("--delay", type=float, default=CALL_DELAY, metavar="S",
                        help=f"seconds between cursor calls (default: {CALL_DELAY})")
    parser.add_argument("--rate-test", action="store_true",
                        help="after the main loop, rerun with 2s delay to distinguish time- vs count-limit")
    args = parser.parse_args()
    asyncio.run(timeline_replay_workflow(loop=args.loop, delay=args.delay, rate_test=args.rate_test))
