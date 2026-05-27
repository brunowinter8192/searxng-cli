#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import asyncio
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions

TARGET_URL = "https://www.coindesk.com/latest-crypto-news"
SCREENSHOT_PATH = str(Path.home() / "tmp" / "coindesk_button_pos.png")
OUTPUT_DIR = Path(__file__).parent / "01_output"
DATE_RE = re.compile(r'/(\d{4})/(\d{2})/(\d{2})/')
REAL_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.7680.154 Safari/537.36"
)
MAX_CLICK_ROUNDS = 20
POLL_INTERVAL = 0.5
POLL_MAX = 40   # 20s max wait per click
PRE_TODAY_THRESHOLD = 3  # stop when this many feed articles from before today

# Dump container selector counts + first 3 article-card ancestor chains
_JS_INSPECT = """
(function() {
    var dateRe = /\\/\\d{4}\\/\\d{2}\\/\\d{2}\\//;
    var scopes = [
        {name: 'global', sel: 'a[href]'},
        {name: 'main a', sel: 'main a[href]'},
        {name: 'article a', sel: 'article a[href]'},
        {name: 'aside a', sel: 'aside a[href]'},
        {name: 'nav a', sel: 'nav a[href]'},
        {name: 'footer a', sel: 'footer a[href]'},
    ];
    var counts = {};
    scopes.forEach(function(s) {
        counts[s.name] = Array.from(document.querySelectorAll(s.sel)).filter(function(a) {
            return dateRe.test(a.href);
        }).length;
    });
    var chains = [];
    var seen = {};
    var mains = document.querySelectorAll('main a[href]');
    for (var i = 0; i < mains.length && chains.length < 3; i++) {
        var href = mains[i].href;
        if (!dateRe.test(href) || seen[href]) continue;
        seen[href] = true;
        var chain = [];
        var node = mains[i];
        for (var d = 0; d < 6; d++) {
            node = node.parentElement;
            if (!node || node === document.body) break;
            var cls = node.className ? node.className.trim().split(/\\s+/).slice(0, 2).join('.') : '';
            chain.push(node.tagName + (cls ? '.' + cls : ''));
        }
        chains.push({url: href.slice(22, 90), chain: chain});
    }
    return JSON.stringify({counts: counts, sample_chains: chains});
})();
"""

# Extract feed article URLs + nearest time label — excludes aside/nav/footer/sidebar noise
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
        results.push({url: href, timeLabel: timeLabel});
    }
    return JSON.stringify(results);
})();
"""

# Count feed-scoped article URLs (same exclusions as _JS_EXTRACT, fast poll)
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

# Locate "More stories" button and return its descriptor
_JS_FIND_BTN = """
(function() {
    var candidates = Array.from(document.querySelectorAll('button, a[role="button"], [role="button"]'));
    for (var i = 0; i < candidates.length; i++) {
        var el = candidates[i];
        var t = el.textContent.trim();
        if (/more\\s+stories|load\\s+more|show\\s+more/i.test(t)) {
            var r = el.getBoundingClientRect();
            var attrs = {};
            Array.from(el.attributes).filter(function(a) { return a.name.startsWith('data-'); })
                .forEach(function(a) { attrs[a.name] = a.value; });
            return JSON.stringify({
                found: true,
                text: t.slice(0, 80),
                tagName: el.tagName,
                id: el.id,
                className: el.className.trim().split(/\\s+/).slice(0, 5).join(' '),
                dataAttrs: attrs,
                rect: {top: Math.round(r.top), left: Math.round(r.left), w: Math.round(r.width), h: Math.round(r.height)},
                scrollY: Math.round(window.scrollY)
            });
        }
    }
    return JSON.stringify({found: false});
})();
"""

# Scroll button into view and click it; return true if found
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
async def probe_workflow(headless: bool):
    session_dir = tempfile.mkdtemp(prefix="coindesk_probe_")
    print(f"Browser session: {session_dir}", file=sys.stderr)
    Path(Path.home() / "tmp").mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).date()
    report = {
        "url": TARGET_URL,
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "headless": headless,
        "today_date": str(today),
        "container_inspection": None,
        "button": None,
        "batches": [],
        "summary": {},
    }

    # Explicit start/stop — async with __aexit__ tries to restore Preferences.backup
    # which doesn't exist in a fresh temp session dir (pydoll bug with ephemeral profiles).
    browser = Chrome(build_options(headless, session_dir))
    tab = await browser.start()
    try:
        print(f"Navigating to {TARGET_URL} …", file=sys.stderr)
        await tab.go_to(TARGET_URL, timeout=60)
        await asyncio.sleep(3.0)

        # DOM inspection — log container counts + article-card ancestor chains
        inspection = await inspect_containers(tab)
        report["container_inspection"] = inspection
        print("Container counts:", {k: v for k, v in inspection["counts"].items()}, file=sys.stderr)
        print("Sample ancestor chains:", file=sys.stderr)
        for c in inspection.get("sample_chains", [])[:3]:
            print(f"  {c['url'][:55]} → {' > '.join(c['chain'][:4])}", file=sys.stderr)

        # Snapshot 0 — initial feed articles (scoped, no sidebar)
        initial = await extract_articles(tab)
        all_urls = {a["url"]: a for a in initial}
        dates_0 = _date_span(list(all_urls.keys()))
        report["batches"].append({
            "batch": 0, "new_urls": [a["url"] for a in initial],
            "labels": {a["url"]: a["timeLabel"] for a in initial},
            "total_after": len(all_urls), "date_span": dates_0,
        })
        print(f"Batch 0: {len(initial)} initial | span {dates_0} | pre-today={count_pre_today(list(all_urls.values()), today)}", file=sys.stderr)

        # Find + describe button, then screenshot
        btn = await find_button(tab)
        report["button"] = btn
        if btn and btn.get("found"):
            print(f"Button: '{btn['text']}' | {btn['tagName']} | class='{btn['className']}'", file=sys.stderr)
            await asyncio.sleep(0.5)
            await tab.take_screenshot(path=SCREENSHOT_PATH)
            print(f"Screenshot: {SCREENSHOT_PATH}", file=sys.stderr)
        else:
            print("Button NOT found on initial render", file=sys.stderr)

        # Click + wait cycle — stop when ≥PRE_TODAY_THRESHOLD feed articles from before today
        prev_count = len(all_urls)
        for click_n in range(1, MAX_CLICK_ROUNDS + 1):
            clicked = await click_button(tab)
            if not clicked:
                print(f"Batch {click_n}: button gone — end of feed", file=sys.stderr)
                report["summary"]["button_disappeared_at_batch"] = click_n
                break

            await asyncio.sleep(2.0)
            await wait_for_new_articles(tab, prev_count)
            new_articles = await extract_articles(tab)
            new_set = {a["url"]: a for a in new_articles}
            added = {u: v for u, v in new_set.items() if u not in all_urls}
            all_urls.update(new_set)

            span = _date_span(list(added.keys()))
            pre = count_pre_today(list(all_urls.values()), today)
            print(f"Batch {click_n}: +{len(added)} | total={len(all_urls)} | span {span} | pre-today={pre}", file=sys.stderr)

            report["batches"].append({
                "batch": click_n,
                "new_urls": list(added.keys()),
                "labels": {u: v["timeLabel"] for u, v in added.items()},
                "total_after": len(all_urls),
                "date_span": span,
                "pre_today_cumulative": pre,
            })
            prev_count = len(all_urls)

            if pre >= PRE_TODAY_THRESHOLD:
                print(f"24h coverage reached: {pre} pre-today articles after {click_n} click(s).", file=sys.stderr)
                report["summary"]["clicks_for_24h_coverage"] = click_n
                break

    finally:
        await tab.close()
        try:
            await browser.stop()
        except Exception as e:
            print(f"Browser stop (non-fatal): {e}", file=sys.stderr)

    # Final summary
    all_list = list(all_urls.values())
    by_date = _group_by_date(all_list)
    report["summary"].update({
        "total_unique_urls": len(all_urls),
        "date_breakdown": {str(k): v for k, v in sorted(by_date.items(), reverse=True)},
        "sample_labels": _sample_by_age(all_list),
        "screenshot": SCREENSHOT_PATH,
    })

    path = write_output(report)
    _print_summary(report)
    print(f"\nJSON output: {path}")


# FUNCTIONS

# Build pydoll ChromiumOptions with UA + anti-detection flags
def build_options(headless: bool, session_dir: str) -> ChromiumOptions:
    opts = ChromiumOptions()
    opts.headless = headless
    opts.add_argument(f"--user-data-dir={session_dir}")
    opts.add_argument(f"--user-agent={REAL_UA}")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.block_popups = True
    opts.block_notifications = True
    return opts


# Unpack CDP execute_script result dict
def _extract_value(raw):
    try:
        return raw["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None


# Run DOM inspection JS, return parsed dict
async def inspect_containers(tab) -> dict:
    raw = await tab.execute_script(_JS_INSPECT)
    val = _extract_value(raw)
    if not val:
        return {}
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return {}


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


# Poll feed-scoped count up to POLL_MAX × POLL_INTERVAL; return when it grows
async def wait_for_new_articles(tab, prev_count: int) -> int:
    for _ in range(POLL_MAX):
        await asyncio.sleep(POLL_INTERVAL)
        raw = await tab.execute_script(_JS_COUNT)
        count = _extract_value(raw)
        if count is not None and int(count) > prev_count:
            return int(count)
    return prev_count


# Run JS button finder, return parsed dict or None
async def find_button(tab) -> dict | None:
    raw = await tab.execute_script(_JS_FIND_BTN)
    val = _extract_value(raw)
    if not val:
        return None
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return None


# Click "More stories" button via JS; return True if clicked
async def click_button(tab) -> bool:
    raw = await tab.execute_script(_JS_CLICK_BTN)
    return bool(_extract_value(raw))


# Parse date from CoinDesk URL path (/YYYY/MM/DD/) → UTC midnight datetime
def parse_url_date(url: str) -> datetime | None:
    m = DATE_RE.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    except ValueError:
        return None


# Count articles whose URL date is before today
def count_pre_today(articles: list[dict], today) -> int:
    return sum(1 for a in articles if (d := parse_url_date(a["url"])) and d.date() < today)


# Return date span string [earliest..latest] for a list of URLs
def _date_span(urls: list[str]) -> str:
    dates = [parse_url_date(u) for u in urls]
    dates = [d for d in dates if d is not None]
    if not dates:
        return "(none)"
    lo = min(dates).strftime("%m-%d")
    hi = max(dates).strftime("%m-%d")
    return f"[{lo}..{hi}]" if lo != hi else f"[{lo}]"


# Group articles by URL date → {date: count}
def _group_by_date(articles: list[dict]) -> dict:
    groups: dict = {}
    for a in articles:
        d = parse_url_date(a["url"])
        if d:
            key = d.date()
            groups[key] = groups.get(key, 0) + 1
    return groups


# Return sample list [{url, timeLabel}] for oldest, middle, newest
def _sample_by_age(articles: list[dict]) -> list[dict]:
    with_date = [(parse_url_date(a["url"]), a) for a in articles]
    with_date = [(d, a) for d, a in with_date if d is not None]
    if not with_date:
        return []
    with_date.sort(key=lambda x: x[0])
    n = len(with_date)
    indices = sorted({0, n // 2, n - 1})
    return [{"url": with_date[i][1]["url"], "timeLabel": with_date[i][1]["timeLabel"]} for i in indices]


# Write probe JSON output, return path
def write_output(data: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUTPUT_DIR / f"probe_{ts}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# Print human-readable summary to stdout
def _print_summary(report: dict):
    s = report["summary"]
    btn = report["button"] or {}
    print("\n=== CoinDesk UI Probe Summary ===")
    print(f"Total unique feed URLs : {s.get('total_unique_urls', '?')}")
    print(f"Clicks for 24h coverage: {s.get('clicks_for_24h_coverage', 'not reached')}")
    print(f"Button                 : '{btn.get('text', 'NOT FOUND')}' | {btn.get('tagName', '?')} | class='{btn.get('className', '?')}'")
    print(f"Screenshot             : {s.get('screenshot', '?')}")
    print("Date breakdown:")
    for date_str, count in s.get("date_breakdown", {}).items():
        print(f"  {date_str}: {count} articles")
    print("Sample labels (oldest→newest):")
    for item in s.get("sample_labels", []):
        print(f"  {(item['timeLabel'] or '(no label)'):<25}  {item['url'][22:90]}")


def main():
    parser = argparse.ArgumentParser(description="CoinDesk /latest-crypto-news UI probe via pydoll (headed by default)")
    parser.add_argument("--headless", action="store_true", default=False, help="Run headless (default: headed)")
    args = parser.parse_args()
    asyncio.run(probe_workflow(args.headless))


if __name__ == "__main__":
    main()
