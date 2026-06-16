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
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx
from pydoll.browser import Chrome

TARGET_URL = "https://www.coindesk.com/latest-crypto-news"
TIMELINE_API_PATH = "/api/v1/articles/timeline"
TIMELINE_BASE = "https://www.coindesk.com/api/v1/articles/timeline"
COINDESK_BASE = "https://www.coindesk.com"
OUTPUT_DIR = Path(__file__).parent / "06_output"
URLS_DIR = OUTPUT_DIR / "urls"
CHECKPOINT_FILE = OUTPUT_DIR / "checkpoint.json"

STOP_DATE = "2017-01-01"        # stop when oldest article in batch < this date
CALL_DELAY = 0.3                # seconds between cursor calls
CHECKPOINT_EVERY = 50           # flush checkpoint JSON every N successful calls
REWARM_EVERY = 240.0            # proactive re-warm interval in seconds
CLICKS_WARMUP = 8               # clicks for initial warmup (SSR buffer clears at ~click 6)
CLICKS_REWARM = 7               # clicks for browser re-warm (slightly faster)
MAX_CURSOR_FALLBACKS = 3        # max articles to try as cursor anchor before declaring rewarm needed

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

# Full CoinDesk article discovery: browser warmup → httpx cursor loop → per-year URL files.
# Re-warm strategy: httpx feedpage GET tested first; falls back to browser if httpx is insufficient.
def full_discovery() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    URLS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = OUTPUT_DIR / f"progress_{ts}.log"

    with open(log_path, "w", encoding="utf-8", buffering=1) as log_fh:
        log(log_fh, f"=== CoinDesk Full Discovery start {ts} ===")
        log(log_fh, f"Stop date: {STOP_DATE} | Delay: {CALL_DELAY}s | Rewarm every: {REWARM_EVERY}s")

        log(log_fh, "Browser warmup …")
        headers, start_url, first_body = asyncio.run(browser_load_feed(CLICKS_WARMUP, log_fh))
        if first_body is None:
            log(log_fh, "FATAL: browser warmup failed — aborting.")
            return
        log(log_fh, f"Warmup done. First URL: {start_url}")

        results = cursor_loop(headers, start_url, first_body, log_fh)

        write_report(OUTPUT_DIR / f"discovery_{ts}.md", results, ts)
        log(log_fh, f"Report written.")
        log(log_fh, (
            f"=== DONE | calls={results['ok_calls']} articles={results['total_articles']}"
            f" oldest={results['oldest_date']} rewarms={results['rewarm_count']}"
            f" fallbacks={results['fallback_count']} ==="
        ))

    print(f"Log → {log_path}")


# FUNCTIONS

# Bind port 0 to get a free OS-assigned port
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
            with urllib.request.urlopen(url, timeout=2) as r:
                return json.loads(r.read())["webSocketDebuggerUrl"]
        except OSError:
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
            print(f"  click {i + 1}/{n_clicks}: {'OK' if _extract_value(raw) else 'miss'}", flush=True)
            await asyncio.sleep(2.5)
    for entry in capture.entries:
        if TIMELINE_API_PATH in entry["request"]["url"]:
            return entry
    return None


# Strip HTTP/2 pseudo-headers and client-managed headers
def filter_headers(raw: dict) -> dict:
    return {k: v for k, v in raw.items() if k.lower() not in SKIP_HEADERS}


# Launch Chrome, load feed, capture timeline headers + first API response body
async def browser_load_feed(n_clicks: int, log_fh=None) -> tuple:
    port = get_free_port()
    session_dir = tempfile.mkdtemp(prefix="coindesk_disc_")
    chrome = None
    tab = None
    try:
        launch_background_chrome(port, session_dir)
        ws_url = wait_for_ws_url(port)
        chrome = Chrome()
        tab = await chrome.connect(ws_url)

        await tab.go_to(TARGET_URL, timeout=60)
        await asyncio.sleep(3.0)
        await tab.execute_script(_JS_DISMISS_COOKIE)
        await asyncio.sleep(0.5)

        entry = await capture_timeline_request(tab, n_clicks)
        if entry is None:
            return {}, "", None

        api_url = entry["request"]["url"]
        raw_hdrs = {h["name"]: h["value"] for h in entry["request"]["headers"]}
        headers = filter_headers(raw_hdrs)

        resp = httpx.get(api_url, headers=headers, follow_redirects=True, timeout=30)
        if resp.status_code != 200:
            _log(log_fh, f"browser_load_feed: first replay → {resp.status_code}")
            return headers, api_url, None

        return headers, api_url, resp.content

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


# Parse all articles from response body; extract _id, storyType, pathname, displayDate
def parse_articles(body: bytes) -> list:
    try:
        data = json.loads(body)
    except Exception:
        return []
    articles = data if isinstance(data, list) else None
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                articles = v
                break
    if not articles:
        return []
    result = []
    for a in articles:
        ad = a.get("articleDates") or {}
        result.append({
            "_id": a.get("_id") or a.get("id"),
            "storyType": a.get("storyType"),
            "pathname": a.get("pathname"),
            "displayDate": (
                ad.get("displayDate") or ad.get("publishedAt")
                or a.get("displayDate") or a.get("publishedAt") or a.get("date")
            ),
        })
    return result


# Build pagination cursor URL from lastId + lastDisplayDate
def build_cursor_url(last_id: str, last_date: str) -> str:
    return f"{TIMELINE_BASE}?size=16&lastId={last_id}&lastDisplayDate={last_date}&lang=en"


# Fetch feed HTML page via plain httpx; return HTTP status code
def fetch_feedpage(headers: dict) -> int:
    feed_hdrs = {k: v for k, v in headers.items() if k.lower() in {"user-agent", "accept-language", "accept"}}
    try:
        resp = httpx.get(TARGET_URL, headers=feed_hdrs, follow_redirects=True, timeout=30)
        return resp.status_code
    except OSError as e:
        print(f"fetch_feedpage error: {e}", file=sys.stderr)
        return -1


# Write one article line to the appropriate per-year file; skip articles with no pathname
def write_article(a: dict, year_files: dict, seen_ids: set) -> bool:
    art_id = a.get("_id")
    pathname = a.get("pathname") or ""
    date_str = (a.get("displayDate") or "")[:10]
    if not art_id or not pathname or len(date_str) < 10:
        return False
    if art_id in seen_ids:
        return False
    seen_ids.add(art_id)
    year = date_str[:4]
    if year not in year_files:
        p = URLS_DIR / f"coindesk_{year}.txt"
        year_files[year] = open(p, "w", encoding="utf-8", buffering=1)
    year_files[year].write(f"{date_str}\t{COINDESK_BASE}{pathname}\n")
    return True


# Save checkpoint JSON with current cursor position and progress counts
def save_checkpoint(call_num: int, last_id: str, last_date: str, year_counts: dict, total: int) -> None:
    data = {
        "call_num": call_num,
        "last_id": last_id,
        "last_date": last_date,
        "year_counts": dict(year_counts),
        "total_articles": total,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    CHECKPOINT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


# Write a log line to both stdout and the open log file
def log(log_fh, msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    log_fh.write(line + "\n")
    log_fh.flush()


# Write a log line to file only (no stdout echo)
def _log(log_fh, msg: str) -> None:
    if log_fh is None:
        return
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    log_fh.write(f"[{ts}] {msg}\n")
    log_fh.flush()


# Attempt re-warm: httpx feedpage first (cheap), then browser re-warm as fallback.
# Returns (headers, body_bytes_or_None, method_str).
def try_rewarm(failing_url: str, headers: dict, log_fh) -> tuple:
    log(log_fh, "[rewarm] Attempting httpx feedpage re-warm …")
    fp_status = fetch_feedpage(headers)
    log(log_fh, f"[rewarm] httpx feedpage GET → {fp_status}")
    time.sleep(1.0)

    resp = httpx.get(failing_url, headers=headers, follow_redirects=True, timeout=30)
    if resp.status_code == 200:
        log(log_fh, "[rewarm] httpx feedpage re-warm SUCCESS ✅")
        return headers, resp.content, "httpx"

    log(log_fh, f"[rewarm] httpx re-warm failed ({resp.status_code}) → browser re-warm …")
    new_headers, _, _ = asyncio.run(browser_load_feed(CLICKS_REWARM, log_fh))
    if not new_headers:
        log(log_fh, "[rewarm] browser re-warm produced no headers — fatal")
        return headers, None, "fatal"

    resp2 = httpx.get(failing_url, headers=new_headers, follow_redirects=True, timeout=30)
    if resp2.status_code == 200:
        log(log_fh, "[rewarm] browser re-warm SUCCESS ✅ (httpx feedpage was insufficient)")
        return new_headers, resp2.content, "browser"

    log(log_fh, f"[rewarm] browser re-warm also failed ({resp2.status_code}) — fatal")
    return headers, None, "fatal"


# Main cursor loop: pages backward to STOP_DATE, writing all article URLs to per-year files
def cursor_loop(headers: dict, start_url: str, first_body: bytes, log_fh) -> dict:
    year_files: dict = {}
    seen_ids: set = set()
    year_counts: defaultdict = defaultdict(int)
    total_articles = 0
    ok_calls = 0
    fallback_count = 0
    rewarm_count = 0
    httpx_rewarm_confirmed: bool | None = None
    oldest_date: str | None = None
    last_rewarm_t = time.monotonic()
    body = first_body
    last_id = last_date = ""
    t_start = time.monotonic()
    elapsed_vals: list = []

    try:
        while True:
            articles = parse_articles(body)
            if not articles:
                log(log_fh, "Empty response — reached API bottom or parse failure. Stopping.")
                break

            # Write articles from this batch to per-year files
            for a in articles:
                if write_article(a, year_files, seen_ids):
                    d = (a.get("displayDate") or "")[:10]
                    year_counts[d[:4]] += 1
                    total_articles += 1
                    if d and (oldest_date is None or d < oldest_date):
                        oldest_date = d

            # Termination: oldest article in batch older than STOP_DATE
            oldest_in_batch = (articles[-1].get("displayDate") or "")[:10]
            if oldest_in_batch and oldest_in_batch < STOP_DATE:
                log(log_fh, f"Reached stop date floor at {oldest_in_batch}. Stopping.")
                break

            # Proactive re-warm every REWARM_EVERY seconds (only after httpx method confirmed)
            if httpx_rewarm_confirmed and time.monotonic() - last_rewarm_t >= REWARM_EVERY:
                fp = fetch_feedpage(headers)
                log(log_fh, f"[proactive rewarm] httpx feedpage → {fp}")
                last_rewarm_t = time.monotonic()
                rewarm_count += 1

            # Build next cursor; fall back to N-1, N-2 articles on 403
            next_body = None
            next_url = ""
            for fb in range(min(MAX_CURSOR_FALLBACKS, len(articles))):
                anchor = articles[-(1 + fb)]
                last_id = anchor.get("_id") or ""
                last_date = anchor.get("displayDate") or ""
                if not last_id or not last_date:
                    continue
                next_url = build_cursor_url(last_id, last_date)

                time.sleep(CALL_DELAY)
                t0 = time.monotonic()
                resp = httpx.get(next_url, headers=headers, follow_redirects=True, timeout=30)
                elapsed = round(time.monotonic() - t0, 2)

                if resp.status_code == 200:
                    if fb > 0:
                        fallback_count += 1
                        log(log_fh, f"  call {ok_calls + 1}: 200 FALLBACK-{fb} anchor={last_id[:8]} pivot={last_date[:10]}")
                    next_body = resp.content
                    ok_calls += 1
                    elapsed_vals.append(elapsed)
                    break

                snippet = resp.content[:80].decode("utf-8", errors="replace")
                print(f"  call {ok_calls + 1}: {resp.status_code} fb={fb} pivot={last_date[:10]} {snippet}", flush=True)

            if next_body is None and next_url:
                # All cursor fallbacks exhausted → try re-warm
                new_headers, rewarm_body, method = try_rewarm(next_url, headers, log_fh)
                if method == "fatal" or rewarm_body is None:
                    log(log_fh, "FATAL: re-warm failed. Stopping.")
                    break
                headers = new_headers
                next_body = rewarm_body
                rewarm_count += 1
                last_rewarm_t = time.monotonic()
                ok_calls += 1
                if method == "httpx" and httpx_rewarm_confirmed is None:
                    httpx_rewarm_confirmed = True
                elif method == "browser" and httpx_rewarm_confirmed is None:
                    httpx_rewarm_confirmed = False

            if next_body is None:
                log(log_fh, "Cursor exhausted with no body. Stopping.")
                break

            body = next_body

            # Checkpoint log every CHECKPOINT_EVERY calls
            if ok_calls % CHECKPOINT_EVERY == 0:
                wall = int(time.monotonic() - t_start)
                avg_el = round(sum(elapsed_vals[-50:]) / max(1, len(elapsed_vals[-50:])), 3)
                log(log_fh, (
                    f"checkpoint call={ok_calls} articles={total_articles}"
                    f" oldest={oldest_date} pivot={last_date[:10]}"
                    f" wall={wall}s avg_elapsed={avg_el}s"
                    f" rewarms={rewarm_count} fallbacks={fallback_count}"
                ))
                save_checkpoint(ok_calls, last_id, last_date, year_counts, total_articles)

    finally:
        for fh in year_files.values():
            try:
                fh.close()
            except OSError as e:
                print(f"year file close error (non-fatal): {e}", file=sys.stderr)
        save_checkpoint(ok_calls, last_id, last_date, year_counts, total_articles)

    avg_elapsed = round(sum(elapsed_vals) / len(elapsed_vals), 3) if elapsed_vals else None
    return {
        "ok_calls": ok_calls,
        "total_articles": total_articles,
        "year_counts": dict(year_counts),
        "oldest_date": oldest_date,
        "fallback_count": fallback_count,
        "rewarm_count": rewarm_count,
        "httpx_rewarm_confirmed": httpx_rewarm_confirmed,
        "avg_elapsed": avg_elapsed,
        "wall_seconds": round(time.monotonic() - t_start, 0),
    }


# Write final discovery report (MD)
def write_report(path: Path, results: dict, ts: str) -> None:
    lines = ["# CoinDesk Full Discovery Report"]
    lines.append(f"\n**Run:** {ts} | **Stop date:** {STOP_DATE}\n")
    lines.append("## Summary\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Successful cursor calls | {results['ok_calls']} |")
    lines.append(f"| Total articles written | {results['total_articles']} |")
    lines.append(f"| Oldest date reached | {results['oldest_date']} |")
    lines.append(f"| Avg elapsed / call | {results['avg_elapsed']}s |")
    wall = int(results.get("wall_seconds", 0))
    lines.append(f"| Wall-clock | {wall // 60}m {wall % 60}s |")
    lines.append(f"| Re-warm events | {results['rewarm_count']} |")
    lines.append(f"| Fallback-cursor activations | {results['fallback_count']} |")
    rewarm_method = (
        "httpx feedpage GET ✅" if results.get("httpx_rewarm_confirmed") is True
        else "browser required ❌ (httpx insufficient)" if results.get("httpx_rewarm_confirmed") is False
        else "not triggered (no warmth-related 403 encountered)"
    )
    lines.append(f"| Re-warm method determination | {rewarm_method} |\n")

    lines.append("## Per-Year Article Counts\n")
    lines.append("| Year | Articles | File |")
    lines.append("|------|----------|------|")
    for year in sorted(results["year_counts"].keys(), reverse=True):
        cnt = results["year_counts"][year]
        lines.append(f"| {year} | {cnt} | `urls/coindesk_{year}.txt` |")

    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    full_discovery()
