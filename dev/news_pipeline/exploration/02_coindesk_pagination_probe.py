#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import asyncio
import base64 as _base64
import gzip as _gzip
import re  # DATE_RE
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

TARGET_URL = "https://www.coindesk.com/latest-crypto-news"
OUTPUT_DIR = Path(__file__).parent / "02_output"
REAL_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.7680.154 Safari/537.36"
)
MAX_CLICKS = 5         # quick mode
DEPTH_CAP = 150        # depth mode safety cap
POLL_INTERVAL = 0.5
POLL_MAX = 40          # 20s max wait per click

DATE_RE = re.compile(r'/(\d{4})/(\d{2})/(\d{2})/')

# Extract feed article URLs — excludes aside/nav/footer/sidebar noise (mirrored from discover.py)
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
        results.push(href);
    }
    return results;
})();
"""

# Dismiss OneTrust cookie consent overlay (removes the DOM node so pointer events are unblocked)
_JS_DISMISS_COOKIE = """
(function() {
    var btn = document.querySelector('#onetrust-accept-btn-handler');
    if (btn) { btn.click(); return 'clicked-accept'; }
    var sdk = document.getElementById('onetrust-consent-sdk');
    if (sdk) { sdk.remove(); return 'removed-sdk'; }
    return 'not-found';
})();
"""

# Scroll "More stories" button into view and JS-click it; return true if found + clicked
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

# Return descriptor of "More stories" button: {found, disabled, text} or {found: false}
_JS_BTN_STATE = """
(function() {
    var candidates = Array.from(document.querySelectorAll('button, a[role="button"], [role="button"]'));
    for (var i = 0; i < candidates.length; i++) {
        var t = candidates[i].textContent.trim();
        if (/more\\s+stories|load\\s+more|show\\s+more/i.test(t)) {
            return {found: true, disabled: candidates[i].disabled || false, text: t.slice(0, 60)};
        }
    }
    return {found: false};
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


# ORCHESTRATOR

# Read POST body synchronously from Playwright impl object; handle gzip-compressed bodies via magic-byte check
def _read_post_data_sync(request) -> str | None:
    raw_b64 = request._impl_obj._initializer.get("postData")
    if not raw_b64:
        return None
    raw_bytes = _base64.b64decode(raw_b64)
    if raw_bytes[:2] == b'\x1f\x8b':
        return _gzip.decompress(raw_bytes).decode("utf-8", errors="replace")
    return raw_bytes.decode("utf-8", errors="replace")


async def probe_workflow():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    har_path = OUTPUT_DIR / "session.har"
    report_path = OUTPUT_DIR / f"report_{ts}.md"

    print(f"HAR → {har_path}", file=sys.stderr)
    print(f"Report → {report_path}", file=sys.stderr)

    # Accumulated network candidates — populated by on_response handler
    network_log: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True)
        context = await browser.new_context(
            record_har_path=str(har_path),
            record_har_mode="full",
            user_agent=REAL_UA,
        )
        page = await context.new_page()

        # Live response logger — synchronous handler on every network response
        def on_response(response):
            url = response.url
            method = response.request.method
            status = response.status
            # Skip static assets
            if any(url.endswith(ext) for ext in (".js", ".css", ".png", ".woff", ".woff2", ".svg", ".ico", ".gif", ".webp")):
                return
            headers = response.request.headers
            next_action = headers.get("next-action", "")
            has_rsc = "_rsc" in url
            is_candidate = method == "POST" or has_rsc or next_action or "coindesk.com" in url
            if not is_candidate:
                return
            # post_data is synchronously available — no await needed
            post_data = _read_post_data_sync(response.request) if method == "POST" else None
            network_log.append({
                "url": url,
                "method": method,
                "status": status,
                "next_action": next_action,
                "has_rsc": has_rsc,
                "post_data": post_data,
                "click_n": None,  # assigned by click loop
            })

        page.on("response", on_response)

        # Navigate + settle
        print(f"Navigating to {TARGET_URL} …", file=sys.stderr)
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3.0)

        # Dismiss OneTrust cookie consent overlay so pointer events reach the feed
        cookie_result = await page.evaluate(_JS_DISMISS_COOKIE)
        print(f"Cookie consent: {cookie_result}", file=sys.stderr)
        await asyncio.sleep(0.5)

        # Initial extraction
        all_urls: set[str] = set(await extract_articles(page))
        print(f"Batch 0: {len(all_urls)} initial articles", file=sys.stderr)

        # Mark all pre-click network entries as click_n=0
        for entry in network_log:
            if entry["click_n"] is None:
                entry["click_n"] = 0

        batches = []
        oldest_date = compute_oldest(all_urls)
        batches.append(build_batch_row(0, len(all_urls), 0, oldest_date, "initial"))

        # Click loop — JS-based click bypasses pointer-event overlay interception
        for click_n in range(1, MAX_CLICKS + 1):
            btn_state_pre = await page.evaluate(_JS_BTN_STATE)
            if not btn_state_pre.get("found"):
                print(f"Click {click_n}: button gone — end of feed", file=sys.stderr)
                batches.append(build_batch_row(click_n, len(all_urls), 0, oldest_date, "GONE"))
                break
            if btn_state_pre.get("disabled"):
                print(f"Click {click_n}: button disabled — end of feed", file=sys.stderr)
                batches.append(build_batch_row(click_n, len(all_urls), 0, oldest_date, "DISABLED"))
                break

            prev_count = len(all_urls)
            pre_net_idx = len(network_log)

            clicked = await page.evaluate(_JS_CLICK_BTN)
            if not clicked:
                print(f"Click {click_n}: JS click returned false — button vanished mid-click", file=sys.stderr)
                batches.append(build_batch_row(click_n, len(all_urls), 0, oldest_date, "GONE"))
                break
            await asyncio.sleep(0.5)

            new_dom_count = await wait_for_new_articles(page, prev_count)
            print(f"Click {click_n}: feed grew from {prev_count} → {new_dom_count}", file=sys.stderr)

            # Assign click ownership to network entries that appeared after the click
            for entry in network_log[pre_net_idx:]:
                entry["click_n"] = click_n

            fresh_urls = set(await extract_articles(page))
            new_this_click = fresh_urls - all_urls
            all_urls.update(fresh_urls)
            oldest_date = compute_oldest(all_urls)

            btn_state_post = await page.evaluate(_JS_BTN_STATE)
            if not btn_state_post.get("found"):
                btn_state = "GONE"
            elif btn_state_post.get("disabled"):
                btn_state = "DISABLED"
            else:
                btn_state = "active"

            print(f"  +{len(new_this_click)} new | total={len(all_urls)} | oldest={oldest_date} | btn={btn_state}", file=sys.stderr)
            batches.append(build_batch_row(click_n, len(all_urls), len(new_this_click), oldest_date, btn_state))

        # Final button state
        final_btn_info = await page.evaluate(_JS_BTN_STATE)
        if not final_btn_info.get("found"):
            final_btn_state = "GONE"
        elif final_btn_info.get("disabled"):
            final_btn_state = "DISABLED"
        else:
            final_btn_state = "active"

        # Close → flushes HAR
        await context.close()
        await browser.close()

    # Partition network log by click number for diff analysis
    click_nets: dict[int, list[dict]] = {}
    for entry in network_log:
        cn = entry["click_n"] if entry["click_n"] is not None else 0
        click_nets.setdefault(cn, []).append(entry)

    write_report(report_path, batches, oldest_date, final_btn_state, click_nets, har_path)
    print(f"\nReport: {report_path}")
    print(f"HAR:    {har_path}")


# FUNCTIONS

# Evaluate _JS_EXTRACT; return list of article href strings
async def extract_articles(page) -> list[str]:
    result = await page.evaluate(_JS_EXTRACT)
    return result if isinstance(result, list) else []


# Poll feed-scoped count until it grows past prev_count; return new count
async def wait_for_new_articles(page, prev_count: int) -> int:
    for _ in range(POLL_MAX):
        await asyncio.sleep(POLL_INTERVAL)
        count = await page.evaluate(_JS_COUNT)
        if isinstance(count, int) and count > prev_count:
            return count
    return prev_count


# Parse oldest date string (YYYY-MM-DD) from a collection of CoinDesk article URLs
def compute_oldest(urls) -> str:
    dates = []
    for url in urls:
        m = DATE_RE.search(url)
        if m:
            dates.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    if not dates:
        return "(none)"
    y, mo, d = min(dates)
    return f"{y:04d}-{mo:02d}-{d:02d}"


# Build one per-click trajectory row dict
def build_batch_row(click_n: int, cumulative: int, new_this: int, oldest: str, btn_state: str) -> dict:
    return {
        "click_n": click_n,
        "cumulative_unique": cumulative,
        "new_this_click": new_this,
        "oldest_date": oldest,
        "btn_state": btn_state,
    }


# Render and write the findings report MD
def write_report(
    path: Path,
    batches: list[dict],
    oldest_date: str,
    final_btn_state: str,
    click_nets: dict,
    har_path: Path,
) -> None:
    lines: list[str] = []
    lines.append("# CoinDesk Pagination Probe — Findings Report")
    lines.append(f"\n**Run:** {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"**HAR:** `{har_path}`\n")

    # Per-click trajectory table
    lines.append("## Per-Click Trajectory\n")
    lines.append("| Click# | Cumulative Unique | New This Click | Oldest Date | Button State |")
    lines.append("|--------|------------------|----------------|-------------|--------------|")
    for row in batches:
        lines.append(
            f"| {row['click_n']} | {row['cumulative_unique']} | {row['new_this_click']} "
            f"| {row['oldest_date']} | {row['btn_state']} |"
        )

    # Final summary
    lines.append(f"\n**Final total unique URLs:** {batches[-1]['cumulative_unique']}")
    lines.append(f"**Oldest date reached:** {oldest_date}")
    lines.append(f"**Button end-state:** {final_btn_state}\n")

    # Network candidates per click
    lines.append("## Network Candidates (non-static, per click)\n")
    for cn in sorted(click_nets.keys()):
        entries = click_nets[cn]
        label = "Initial page load" if cn == 0 else f"Click {cn}"
        lines.append(f"### {label} ({len(entries)} candidates)\n")
        for e in entries:
            lines.append(f"**{e['method']} {e['url']}**")
            lines.append(f"- Status: {e['status']}")
            if e["next_action"]:
                lines.append(f"- `Next-Action`: `{e['next_action']}`")
            if e["has_rsc"]:
                lines.append("- Contains `_rsc` query parameter: YES")
            if e["post_data"]:
                pd = e["post_data"]
                if len(pd) > 600:
                    pd = pd[:600] + "…"
                lines.append(f"- POST body: `{pd}`")
            lines.append("")

    # Click-1 vs Click-2 diff — identifies the pagination cursor/offset
    lines.append("## Click-1 vs Click-2 Request Diff\n")
    lines.append("*(What changes between the first and second pagination calls — reveals the cursor/offset parameter)*\n")
    c1_entries = click_nets.get(1, [])
    c2_entries = click_nets.get(2, [])

    if not c1_entries and not c2_entries:
        lines.append("No candidates captured for clicks 1 or 2.\n")
    else:
        c1_posts = [e for e in c1_entries if e["method"] == "POST" or e["has_rsc"]]
        c2_posts = [e for e in c2_entries if e["method"] == "POST" or e["has_rsc"]]

        lines.append(f"**Click 1 — POST / _rsc candidates ({len(c1_posts)}):**")
        for e in c1_posts:
            lines.append(f"- `{e['method']} {e['url']}`")
            if e["next_action"]:
                lines.append(f"  - Next-Action: `{e['next_action']}`")
            if e["post_data"]:
                pd = e["post_data"]
                if len(pd) > 400:
                    pd = pd[:400] + "…"
                lines.append(f"  - POST body: `{pd}`")
        lines.append("")

        lines.append(f"**Click 2 — POST / _rsc candidates ({len(c2_posts)}):**")
        for e in c2_posts:
            lines.append(f"- `{e['method']} {e['url']}`")
            if e["next_action"]:
                lines.append(f"  - Next-Action: `{e['next_action']}`")
            if e["post_data"]:
                pd = e["post_data"]
                if len(pd) > 400:
                    pd = pd[:400] + "…"
                lines.append(f"  - POST body: `{pd}`")
        lines.append("")

        # Find shared base URLs and diff their query strings
        c1_urls = [e["url"] for e in c1_posts]
        c2_urls = [e["url"] for e in c2_posts]
        shared_bases: list[str] = []
        for u1 in c1_urls:
            base1 = u1.split("?")[0]
            for u2 in c2_urls:
                if u2.split("?")[0] == base1 and base1 not in shared_bases:
                    shared_bases.append(base1)

        if shared_bases:
            lines.append("**Shared base URLs — query string diff reveals pagination param:**")
            for base in shared_bases:
                u1_match = next((u for u in c1_urls if u.split("?")[0] == base), None)
                u2_match = next((u for u in c2_urls if u.split("?")[0] == base), None)
                q1 = ("?" + u1_match.split("?")[1]) if u1_match and "?" in u1_match else "(none)"
                q2 = ("?" + u2_match.split("?")[1]) if u2_match and "?" in u2_match else "(none)"
                lines.append(f"- Base: `{base}`")
                lines.append(f"  - Click 1 query: `{q1}`")
                lines.append(f"  - Click 2 query: `{q2}`")
        else:
            lines.append(
                "No shared base URLs between click-1 and click-2 POST/_rsc candidates — "
                "pagination may use POST body parameters (see body diff above) rather than query strings."
            )

    lines.append(f"\n## HAR\n\n`{har_path}`")
    lines.append("\nFull network session including response bodies captured above.")

    path.write_text("\n".join(lines), encoding="utf-8")


async def depth_workflow():
    """Find the ceiling: click until disabled/gone/plateau/cap. No HAR. Coindesk-only net log."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = OUTPUT_DIR / f"depth_report_{ts}.md"
    print(f"Report → {report_path}", file=sys.stderr)

    # Lightweight log: only www.coindesk.com non-image, non-static responses
    coindesk_log: list[dict] = []
    _SKIP_EXT = (".js", ".css", ".woff", ".woff2", ".otf", ".png", ".jpg", ".jpeg",
                 ".gif", ".webp", ".svg", ".ico", ".map")
    _SKIP_PATH = ("/_next/static/", "/_next/image", "/api/cdn-fonts")

    def on_response(response):
        url = response.url
        if "www.coindesk.com" not in url and "coindesk.com" not in url:
            return
        if any(url.endswith(ext) for ext in _SKIP_EXT):
            return
        if any(seg in url for seg in _SKIP_PATH):
            return
        coindesk_log.append({
            "url": url,
            "method": response.request.method,
            "status": response.status,
        })

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True)
        context = await browser.new_context(user_agent=REAL_UA)
        page = await context.new_page()
        page.on("response", on_response)

        print(f"Navigating to {TARGET_URL} …", file=sys.stderr)
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3.0)

        cookie_result = await page.evaluate(_JS_DISMISS_COOKIE)
        print(f"Cookie consent: {cookie_result}", file=sys.stderr)
        await asyncio.sleep(0.5)

        all_urls: set[str] = set(await extract_articles(page))
        oldest_date = compute_oldest(all_urls)
        print(f"Batch 0: {len(all_urls)} initial | oldest={oldest_date}", file=sys.stderr)

        stop_reason = f"cap ({DEPTH_CAP} clicks)"
        milestone_rows: list[str] = []
        prev_count = len(all_urls)

        for click_n in range(1, DEPTH_CAP + 1):
            btn_state_pre = await page.evaluate(_JS_BTN_STATE)
            if not btn_state_pre.get("found"):
                stop_reason = "button GONE"
                break
            if btn_state_pre.get("disabled"):
                stop_reason = "button DISABLED"
                break

            clicked = await page.evaluate(_JS_CLICK_BTN)
            if not clicked:
                stop_reason = "JS click returned false (button vanished)"
                break
            await asyncio.sleep(0.5)

            new_dom_count = await wait_for_new_articles(page, prev_count)

            fresh_urls = set(await extract_articles(page))
            new_this = fresh_urls - all_urls
            if not new_this:
                stop_reason = f"plateau (no new URLs after click {click_n})"
                break

            all_urls.update(fresh_urls)
            oldest_date = compute_oldest(all_urls)
            prev_count = len(all_urls)

            if click_n % 10 == 0 or click_n <= 5:
                row = f"  click {click_n:>3}: total={len(all_urls):>4} | +{len(new_this):>3} | oldest={oldest_date}"
                print(row, file=sys.stderr)
                milestone_rows.append(row.strip())

        # Final button state
        final_btn_info = await page.evaluate(_JS_BTN_STATE)
        final_btn_state = (
            "GONE" if not final_btn_info.get("found")
            else "DISABLED" if final_btn_info.get("disabled")
            else "active"
        )

        await context.close()
        await browser.close()

    content_fetches = [e for e in coindesk_log if e["url"] != TARGET_URL
                       and "latest-crypto-news" not in e["url"]
                       or "_rsc" in e["url"] or "next-action" in e.get("method", "").lower()]
    any_content_fetch = bool([e for e in coindesk_log
                               if "_rsc" in e["url"]
                               or e["method"] == "POST"
                               or ("coindesk.com" in e["url"]
                                   and "latest-crypto-news" not in e["url"]
                                   and "metrics." not in e["url"]
                                   and "downloads." not in e["url"]
                                   and e["url"] != TARGET_URL)])

    write_depth_report(report_path, len(all_urls), oldest_date, stop_reason,
                       final_btn_state, milestone_rows, coindesk_log, any_content_fetch)

    print(f"\n=== DEPTH RESULT ===", file=sys.stderr)
    print(f"Max unique URLs : {len(all_urls)}", file=sys.stderr)
    print(f"Oldest date     : {oldest_date}", file=sys.stderr)
    print(f"Stop reason     : {stop_reason}", file=sys.stderr)
    print(f"CoinDesk content fetch ever fired: {any_content_fetch}", file=sys.stderr)
    print(f"Report: {report_path}")


# Write depth-mode ceiling report
def write_depth_report(
    path: Path,
    max_unique: int,
    oldest_date: str,
    stop_reason: str,
    final_btn_state: str,
    milestone_rows: list[str],
    coindesk_log: list[dict],
    any_content_fetch: bool,
) -> None:
    lines: list[str] = []
    lines.append("# CoinDesk Pagination Depth Report — Ceiling Probe")
    lines.append(f"\n**Run:** {datetime.now(timezone.utc).isoformat()}\n")

    lines.append("## Result\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Max unique feed URLs | **{max_unique}** |")
    lines.append(f"| Oldest date reached | **{oldest_date}** |")
    lines.append(f"| Stop reason | **{stop_reason}** |")
    lines.append(f"| Button end-state | {final_btn_state} |")
    lines.append(f"| CoinDesk content fetch fired | {'YES — see log below' if any_content_fetch else 'NO — pure client-side'} |\n")

    lines.append("## Milestone Progress (every 10 clicks + first 5)\n")
    lines.append("```")
    lines.extend(milestone_rows)
    lines.append("```\n")

    lines.append("## CoinDesk Network Log (non-static, non-metrics)\n")
    filtered = [e for e in coindesk_log
                if "metrics.coindesk.com" not in e["url"]
                and "downloads.coindesk.com" not in e["url"]]
    if filtered:
        lines.append("| Method | URL | Status |")
        lines.append("|--------|-----|--------|")
        seen_urls: set[str] = set()
        for e in filtered:
            url_short = e["url"][:120] + ("…" if len(e["url"]) > 120 else "")
            if url_short not in seen_urls:
                seen_urls.add(url_short)
                lines.append(f"| {e['method']} | `{url_short}` | {e['status']} |")
    else:
        lines.append("_(none — all coindesk.com traffic was metrics or static assets)_")

    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CoinDesk pagination probe — quick (5 clicks + HAR) or depth (ceiling finder)"
    )
    parser.add_argument(
        "--depth", action="store_true",
        help="Run ceiling-finder loop (up to 150 clicks, no HAR, coindesk-only net log)"
    )
    args = parser.parse_args()
    if args.depth:
        asyncio.run(depth_workflow())
    else:
        asyncio.run(probe_workflow())
