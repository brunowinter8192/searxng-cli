#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from pydoll.browser import Chrome

TARGET_URL = "https://www.coindesk.com/latest-crypto-news"
OUTPUT_DIR = Path(__file__).parent / "03_output"

STAGE_A_CAP = 400        # bounded sanity run ceiling; None = uncapped Stage B
PLATEAU_TOLERANCE = 3    # consecutive no-growth clicks before declaring feed end
CHECKPOINT_EVERY = 50    # overwrite checkpoint_urls.json every N clicks
COINDESK_ORIGIN = date(2013, 9, 1)   # projection anchor

POLL_INTERVAL = 0.5
POLL_MAX = 40            # 20s max wait per click

REAL_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.7680.154 Safari/537.36"
)
DATE_RE = re.compile(r'/(\d{4})/(\d{2})/(\d{2})/')

# Extract feed article URLs + title; excludes aside/nav/footer/sidebar noise (mirrors discover.py)
_JS_EXTRACT = """
(function() {
    var dateRe = /\\/\\d{4}\\/\\d{2}\\/\\d{2}\\//;
    var skipTags = {ASIDE: 1, NAV: 1, FOOTER: 1, HEADER: 1};
    var skipCls = /related|recommendation|popular|trending|sidebar/i;
    var links = document.querySelectorAll('a[href]');
    var results = [];
    var seen = {};
    for (var i = 0; i < links.length; i++) {
        var a = links[i];
        var href = a.href;
        if (!dateRe.test(href) || seen[href]) continue;
        var skip = false;
        var node = a.parentElement;
        while (node && node !== document.body) {
            if (skipTags[node.tagName]) { skip = true; break; }
            if (node.className && skipCls.test(node.className)) { skip = true; break; }
            node = node.parentElement;
        }
        if (skip) continue;
        seen[href] = true;
        var timeLabel = '';
        node = a;
        for (var d = 0; d < 10; d++) {
            node = node.parentElement;
            if (!node) break;
            var te = node.querySelector('time');
            if (te) { timeLabel = te.getAttribute('datetime') || te.textContent.trim(); break; }
            var kids = node.querySelectorAll('span, p, div');
            for (var j = 0; j < kids.length; j++) {
                var t = kids[j].textContent.trim();
                if (t.length < 40 && /\\d+\\s*(min|hour|hr|day|h|m)\\s*(ago|s)?|just now/i.test(t)) {
                    timeLabel = t; break;
                }
            }
            if (timeLabel) break;
        }
        results.push({url: href, timeLabel: timeLabel, title: a.textContent.trim()});
    }
    return JSON.stringify(results);
})();
"""

# Count feed-scoped article URLs (fast poll)
_JS_COUNT = """
(function() {
    var dateRe = /\\/\\d{4}\\/\\d{2}\\/\\d{2}\\//;
    var skipTags = {ASIDE: 1, NAV: 1, FOOTER: 1, HEADER: 1};
    var skipCls = /related|recommendation|popular|trending|sidebar/i;
    var seen = {};
    var count = 0;
    document.querySelectorAll('a[href]').forEach(function(a) {
        if (!dateRe.test(a.href) || seen[a.href]) return;
        var skip = false;
        var node = a.parentElement;
        while (node && node !== document.body) {
            if (skipTags[node.tagName]) { skip = true; break; }
            if (node.className && skipCls.test(node.className)) { skip = true; break; }
            node = node.parentElement;
        }
        if (!skip) { seen[a.href] = true; count++; }
    });
    return count;
})();
"""

# Scroll "More stories" button into view and click it; return true if found
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

# Button state — returns JSON string {found, disabled} for pydoll CDP unwrapping via _extract_value
_JS_BTN_STATE_JSON = """
(function() {
    var candidates = Array.from(document.querySelectorAll('button, a[role="button"], [role="button"]'));
    for (var i = 0; i < candidates.length; i++) {
        var t = candidates[i].textContent.trim();
        if (/more\\s+stories|load\\s+more|show\\s+more/i.test(t)) {
            return JSON.stringify({found: true, disabled: candidates[i].disabled || false});
        }
    }
    return JSON.stringify({found: false, disabled: false});
})();
"""

# Dismiss OneTrust cookie consent overlay so pointer events reach the feed
_JS_DISMISS_COOKIE = """
(function() {
    var btn = document.querySelector('#onetrust-accept-btn-handler');
    if (btn) { btn.click(); return 'clicked-accept'; }
    var sdk = document.getElementById('onetrust-consent-sdk');
    if (sdk) { sdk.remove(); return 'removed-sdk'; }
    return 'not-found';
})();
"""


# ORCHESTRATOR

# Paginate CoinDesk feed without date/round caps; write live log, periodic checkpoints, and final URL set.
async def backfill_workflow(stage_a_cap: int | None = STAGE_A_CAP) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    log_path = OUTPUT_DIR / f"progress_{ts}.log"
    checkpoint_path = OUTPUT_DIR / "checkpoint_urls.json"
    final_path = OUTPUT_DIR / f"urls_{ts}.json"
    report_path = OUTPUT_DIR / f"report_stage_a_{ts}.md"
    cap_label = str(stage_a_cap) if stage_a_cap is not None else "UNCAPPED"

    print(f"Log        → {log_path}", file=sys.stderr)
    print(f"Checkpoint → {checkpoint_path}  (every {CHECKPOINT_EVERY} clicks + on exit)", file=sys.stderr)
    print(f"Stage cap  : {cap_label} clicks", file=sys.stderr)

    run_start = time.monotonic()
    log_fh = open(log_path, "a", encoding="utf-8", buffering=1)
    write_log_header(log_fh, ts, cap_label)

    port = None
    session_dir = None
    chrome = None
    tab = None
    all_urls: dict[str, dict] = {}
    click_times: list[float] = []
    stop_reason = "interrupted"
    click_n = 0
    oldest = "(none)"

    try:
        port = get_free_port()
        session_dir = tempfile.mkdtemp(prefix="coindesk_backfill_")
        print(f"Launching Chrome on port {port} …", file=sys.stderr)
        launch_background_chrome(port, session_dir)
        ws_url = wait_for_ws_url(port)
        print(f"Connected: {ws_url}", file=sys.stderr)

        chrome = Chrome()
        tab = await chrome.connect(ws_url)

        print(f"Navigating to {TARGET_URL} …", file=sys.stderr)
        await tab.go_to(TARGET_URL, timeout=60)
        await asyncio.sleep(3.0)

        raw_cookie = await tab.execute_script(_JS_DISMISS_COOKIE)
        cookie_result = _extract_value(raw_cookie)
        print(f"Cookie consent: {cookie_result}", file=sys.stderr)
        await asyncio.sleep(0.5)

        initial = await extract_articles(tab)
        all_urls = {a["url"]: a for a in initial}
        oldest = compute_oldest(all_urls)
        print(f"Batch 0: {len(all_urls)} initial | oldest={oldest}", file=sys.stderr)
        write_log_line(log_fh, 0, len(all_urls), oldest, len(all_urls), "initial", 0.0)

        plateau_count = 0
        max_clicks = stage_a_cap if stage_a_cap is not None else 10_000_000

        for click_n in range(1, max_clicks + 1):
            cycle_start = time.monotonic()

            btn = await check_btn_state(tab)
            if not btn["found"]:
                stop_reason = "button GONE"
                write_log_line(log_fh, click_n, len(all_urls), oldest, 0, "GONE", 0.0)
                print(f"Click {click_n}: button GONE — end of feed", file=sys.stderr)
                break
            if btn["disabled"]:
                stop_reason = "button DISABLED"
                write_log_line(log_fh, click_n, len(all_urls), oldest, 0, "DISABLED", 0.0)
                print(f"Click {click_n}: button DISABLED — end of feed", file=sys.stderr)
                break

            prev_count = len(all_urls)
            clicked = await click_button(tab)
            if not clicked:
                stop_reason = "button GONE (mid-click)"
                write_log_line(log_fh, click_n, len(all_urls), oldest, 0, "GONE-MID", 0.0)
                print(f"Click {click_n}: button vanished mid-click", file=sys.stderr)
                break

            await asyncio.sleep(2.0)
            await wait_for_new_articles(tab, prev_count)

            fresh = await extract_articles(tab)
            added = {a["url"]: a for a in fresh if a["url"] not in all_urls}
            all_urls.update(added)
            oldest = compute_oldest(all_urls)
            new_this = len(added)

            cycle_elapsed = time.monotonic() - cycle_start
            click_times.append(cycle_elapsed)

            if new_this == 0:
                plateau_count += 1
                btn_label = f"plateau({plateau_count}/{PLATEAU_TOLERANCE})"
                if plateau_count >= PLATEAU_TOLERANCE:
                    stop_reason = f"plateau ({PLATEAU_TOLERANCE} consecutive no-growth clicks)"
                    write_log_line(log_fh, click_n, len(all_urls), oldest, 0, "PLATEAU-STOP", cycle_elapsed)
                    print(f"Click {click_n}: {stop_reason}", file=sys.stderr)
                    break
            else:
                plateau_count = 0
                btn_label = "active"

            write_log_line(log_fh, click_n, len(all_urls), oldest, new_this, btn_label, cycle_elapsed)

            if click_n % CHECKPOINT_EVERY == 0:
                save_checkpoint(all_urls, checkpoint_path)
                print(f"  [checkpoint] {len(all_urls)} URLs at click {click_n}", file=sys.stderr)
        else:
            if stage_a_cap is not None:
                stop_reason = f"stage-A cap ({stage_a_cap} clicks)"
            else:
                stop_reason = "loop exhausted (internal max reached)"

        print(f"Stop: {stop_reason} | total={len(all_urls)} | oldest={oldest}", file=sys.stderr)

    finally:
        if all_urls:
            save_checkpoint(all_urls, checkpoint_path)
            print(f"Final checkpoint: {len(all_urls)} URLs → {checkpoint_path}", file=sys.stderr)
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
        if port is not None:
            kill_chrome_on_port(port)
        if session_dir is not None:
            shutil.rmtree(session_dir, ignore_errors=True)
        print("Cleanup complete.", file=sys.stderr)
        log_fh.close()

    entries = build_entries(all_urls)
    entries, n_filtered = filter_live_blogs(entries)
    if n_filtered:
        print(f"Filtered {n_filtered} live-blog URLs", file=sys.stderr)
    final_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Final output → {final_path} ({len(entries)} entries)", file=sys.stderr)

    run_elapsed = time.monotonic() - run_start
    write_run_report(report_path, ts, run_elapsed, click_n, len(all_urls), oldest, stop_reason, click_times, stage_a_cap)
    print(f"Report → {report_path}")


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


# Run extract JS + decode JSON response into list of article dicts
async def extract_articles(tab) -> list[dict]:
    raw = await tab.execute_script(_JS_EXTRACT)
    val = _extract_value(raw)
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


# Click "More stories" button via JS; return True if clicked
async def click_button(tab) -> bool:
    raw = await tab.execute_script(_JS_CLICK_BTN)
    return bool(_extract_value(raw))


# Poll feed-scoped count up to POLL_MAX × POLL_INTERVAL; return when it grows
async def wait_for_new_articles(tab, prev_count: int) -> int:
    for _ in range(POLL_MAX):
        await asyncio.sleep(POLL_INTERVAL)
        raw = await tab.execute_script(_JS_COUNT)
        count = _extract_value(raw)
        if count is not None and int(count) > prev_count:
            return int(count)
    return prev_count


# Query button presence and disabled state via CDP; return {found, disabled}
async def check_btn_state(tab) -> dict:
    raw = await tab.execute_script(_JS_BTN_STATE_JSON)
    val = _extract_value(raw)
    if not val:
        return {"found": False, "disabled": False}
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return {"found": False, "disabled": False}


# Parse date from CoinDesk URL path (/YYYY/MM/DD/) → UTC midnight datetime
def parse_url_date(url: str) -> datetime | None:
    m = DATE_RE.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    except ValueError:
        return None


# Return YYYY-MM-DD of oldest article URL in all_urls; "(none)" if no parseable dates
def compute_oldest(all_urls: dict) -> str:
    dates = []
    for url in all_urls:
        dt = parse_url_date(url)
        if dt:
            dates.append(dt.date())
    if not dates:
        return "(none)"
    return min(dates).strftime("%Y-%m-%d")


# Convert URL date to ISO-8601 string (UTC midnight)
def _url_to_iso(url: str) -> str:
    dt = parse_url_date(url)
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


# Extract first path segment as section (e.g. /markets/2026/... → markets)
def _extract_section(url: str) -> str:
    try:
        path = url.split("coindesk.com", 1)[1]
        return path.strip("/").split("/")[0]
    except (IndexError, ValueError):
        return "unknown"


# Build sorted output entry list from all_urls dict
def build_entries(all_urls: dict) -> list[dict]:
    entries = []
    for url, article in all_urls.items():
        iso = _url_to_iso(url)
        entries.append({
            "url": url,
            "lastmod": iso,
            "publication_date": iso,
            "title": article.get("title", ""),
            "section": _extract_section(url),
        })
    entries.sort(key=lambda e: e["lastmod"], reverse=True)
    return entries


# Return True if URL is a CoinDesk live-blog (slug starts with "live-")
def _is_live_blog(url: str) -> bool:
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    return slug.startswith("live-")


# Remove live-blog URLs; return (filtered_list, count_removed)
def filter_live_blogs(entries: list[dict]) -> tuple[list[dict], int]:
    kept = [e for e in entries if not _is_live_blog(e["url"])]
    return kept, len(entries) - len(kept)


# Build live-blog-filtered entry list and overwrite path (crash-safe periodic save)
def save_checkpoint(all_urls: dict, path: Path) -> None:
    entries = build_entries(all_urls)
    entries, _ = filter_live_blogs(entries)
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


# Write log file header with run metadata and column labels
def write_log_header(log_fh, ts: str, cap_label: str) -> None:
    log_fh.write(f"# CoinDesk backfill — started {ts} — cap={cap_label}\n")
    log_fh.write("# timestamp                | click | total  | oldest     |  +new | btn            |    t(s)\n")
    log_fh.flush()


# Append one progress line and flush immediately for tail -f visibility
def write_log_line(
    log_fh, click_n: int, total: int, oldest: str,
    new_this: int, btn_state: str, elapsed: float,
) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    line = (
        f"{ts} | click={click_n:5d} | total={total:6d} | oldest={oldest}"
        f" | +{new_this:4d} | {btn_state:<14} | {elapsed:6.1f}s\n"
    )
    log_fh.write(line)
    log_fh.flush()


# Write run summary: timing stats, DOM growth trend, Stage B projection
def write_run_report(
    path: Path,
    ts: str,
    run_elapsed: float,
    clicks_done: int,
    total_urls: int,
    oldest_date: str,
    stop_reason: str,
    click_times: list[float],
    stage_a_cap: int | None,
) -> None:
    cap_label = str(stage_a_cap) if stage_a_cap is not None else "UNCAPPED"
    h, rem = divmod(int(run_elapsed), 3600)
    m, s = divmod(rem, 60)
    elapsed_str = f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

    lines: list[str] = []
    lines.append("# CoinDesk Backfill — Stage A Sanity Report")
    lines.append(f"\n**Run:** {ts}  |  **Cap:** {cap_label}\n")

    lines.append("## Summary\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Clicks done | {clicks_done} |")
    lines.append(f"| Distinct URLs collected | {total_urls} |")
    lines.append(f"| Oldest date reached | {oldest_date} |")
    lines.append(f"| Stop reason | {stop_reason} |")
    lines.append(f"| Total wall-clock time | {elapsed_str} ({run_elapsed:.0f}s) |\n")

    if not click_times:
        lines.append("_(No click timing data — 0 clicks completed)_")
        path.write_text("\n".join(lines), encoding="utf-8")
        return

    avg_t = sum(click_times) / len(click_times)
    min_t = min(click_times)
    max_t = max(click_times)
    n10 = min(10, len(click_times))
    first10_avg = sum(click_times[:n10]) / n10
    last10_avg = sum(click_times[-n10:]) / n10
    trend = last10_avg - first10_avg

    lines.append("## Per-Click Timing\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Average | {avg_t:.2f}s |")
    lines.append(f"| Min | {min_t:.2f}s |")
    lines.append(f"| Max | {max_t:.2f}s |")
    lines.append(f"| First-10 avg | {first10_avg:.2f}s |")
    lines.append(f"| Last-10 avg | {last10_avg:.2f}s |")
    trend_label = f"+{trend:.2f}s (slowdown)" if trend > 0.3 else f"{trend:+.2f}s (stable)"
    lines.append(f"| Trend (last10 − first10) | {trend_label} |\n")

    lines.append("## DOM Growth Assessment\n")
    if trend > 0.5:
        lines.append(f"**Significant slowdown detected: +{trend:.2f}s first→last.**")
        lines.append("At this trajectory Stage B will stall badly at high depth.")
        lines.append("Recommendation: drop `timeLabel` DOM walk from `_JS_EXTRACT` and switch to delta extraction.")
    elif trend > 0.3:
        lines.append(f"**Moderate slowdown: +{trend:.2f}s.** Monitor early in Stage B; delta extraction may be needed above ~1 000 clicks.")
    else:
        lines.append(f"Per-click time is stable ({trend:+.2f}s first→last trend). Full DOM re-scan acceptable for Stage B.\n")

    lines.append("\n## Stage B Projection\n")
    if oldest_date != "(none)" and clicks_done > 0:
        try:
            today = datetime.now(timezone.utc).date()
            oldest_dt = datetime.strptime(oldest_date, "%Y-%m-%d").date()
            days_covered = max(1, (today - oldest_dt).days)
            days_remaining = max(0, (oldest_dt - COINDESK_ORIGIN).days)
            rate = days_covered / clicks_done
            extra_clicks = int(days_remaining / rate) if rate > 0 else 0
            extra_secs = avg_t * extra_clicks
            total_clicks = clicks_done + extra_clicks
            total_secs = run_elapsed + extra_secs
            h2, r2 = divmod(int(total_secs), 3600)
            m2, _ = divmod(r2, 60)
            total_time_str = f"{h2}h {m2}m" if h2 else f"{m2}m"
            lines.append(f"- Stage A: **{clicks_done} clicks** → **{days_covered} days** back to `{oldest_date}` in {elapsed_str}")
            lines.append(f"- Rate: **{rate:.1f} days of history per click** at {avg_t:.1f}s/click")
            lines.append(f"- Remaining to CoinDesk founding ({COINDESK_ORIGIN}): **~{days_remaining} days**")
            lines.append(f"- Estimated additional clicks: **~{extra_clicks:,}**")
            lines.append(f"- Estimated additional time at current pace: **~{extra_secs / 3600:.1f}h**")
            lines.append(f"- **Total full-run estimate: ~{total_clicks:,} clicks / ~{total_time_str}**")
            lines.append(f"\n*(Linear projection — actual floor unknown; feed may end before founding date.)*")
        except Exception as e:
            lines.append(f"_(Projection error: {e})_")
    else:
        lines.append("_(Insufficient data for projection)_")

    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CoinDesk backfill traversal — stage A (capped) or stage B (uncapped)")
    parser.add_argument("--full", action="store_true", help="Stage B: uncapped run (no click limit)")
    args = parser.parse_args()
    cap = None if args.full else STAGE_A_CAP
    asyncio.run(backfill_workflow(stage_a_cap=cap))
