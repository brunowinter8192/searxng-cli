#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import asyncio
import json
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
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

# Extract all article URLs + nearest time label
_JS_EXTRACT = """
(function() {
    var links = document.querySelectorAll('a[href]');
    var results = [];
    var seen = {};
    var dateRe = /\\/\\d{4}\\/\\d{2}\\/\\d{2}\\//;
    for (var i = 0; i < links.length; i++) {
        var href = links[i].href;
        if (!dateRe.test(href) || seen[href]) continue;
        seen[href] = true;
        var timeLabel = '';
        var node = links[i];
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

# Count unique article URLs (fast poll)
_JS_COUNT = """
(function() {
    var seen = {};
    var count = 0;
    var dateRe = /\\/\\d{4}\\/\\d{2}\\/\\d{2}\\//;
    document.querySelectorAll('a[href]').forEach(function(a) {
        if (dateRe.test(a.href) && !seen[a.href]) { seen[a.href] = true; count++; }
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
            Array.from(el.attributes).filter(a => a.name.startsWith('data-')).forEach(a => { attrs[a.name] = a.value; });
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

    options = build_options(headless, session_dir)
    report = {
        "url": TARGET_URL,
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "headless": headless,
        "button": None,
        "batches": [],
        "summary": {},
    }

    # Explicit start/stop — async with __aexit__ tries to restore Preferences.backup
    # which doesn't exist in a fresh temp session dir (pydoll bug with ephemeral profiles).
    browser = Chrome(options)
    tab = await browser.start()
    try:
            # Navigate + initial render wait
            print(f"Navigating to {TARGET_URL} …", file=sys.stderr)
            await tab.go_to(TARGET_URL, timeout=30)
            await asyncio.sleep(3.0)

            # Snapshot 0 — initial visible articles
            initial = await extract_articles(tab)
            all_urls = {a["url"]: a for a in initial}
            report["batches"].append({"batch": 0, "new_urls": [a["url"] for a in initial], "labels": {a["url"]: a["timeLabel"] for a in initial}})
            print(f"Snapshot 0: {len(initial)} initial articles", file=sys.stderr)

            # Find + describe button, then screenshot
            btn = await find_button(tab)
            report["button"] = btn
            if btn and btn.get("found"):
                print(f"Button found: '{btn['text']}' | tag={btn['tagName']} | id='{btn['id']}' | class='{btn['className']}'", file=sys.stderr)
                print(f"  rect={btn['rect']} scrollY={btn['scrollY']}", file=sys.stderr)
                print(f"  dataAttrs={btn['dataAttrs']}", file=sys.stderr)
                await asyncio.sleep(0.5)
                await tab.take_screenshot(path=SCREENSHOT_PATH)
                print(f"Screenshot saved: {SCREENSHOT_PATH}", file=sys.stderr)
            else:
                print("Button NOT found in initial render — will retry after scroll", file=sys.stderr)

            # Click + wait cycle
            prev_count = len(all_urls)
            for click_n in range(1, MAX_CLICK_ROUNDS + 1):
                clicked = await click_button(tab)
                if not clicked:
                    print(f"Round {click_n}: button not clickable — end of feed or DOM change", file=sys.stderr)
                    report["summary"]["button_disappeared_at_round"] = click_n
                    break

                new_count = await wait_for_new_articles(tab, prev_count)
                new_articles = await extract_articles(tab)
                new_set = {a["url"]: a for a in new_articles}
                added = {u: v for u, v in new_set.items() if u not in all_urls}
                all_urls.update(new_set)

                # Re-find button after DOM update (it may scroll)
                if not report["button"] or not report["button"].get("found"):
                    btn = await find_button(tab)
                    if btn and btn.get("found"):
                        report["button"] = btn

                oldest_h = oldest_age_hours(list(all_urls.values()))
                print(f"Round {click_n}: +{len(added)} new URLs | total={len(all_urls)} | oldest≈{oldest_h:.1f}h ago", file=sys.stderr)

                report["batches"].append({
                    "batch": click_n,
                    "new_urls": list(added.keys()),
                    "labels": {u: v["timeLabel"] for u, v in added.items()},
                    "total_after": len(all_urls),
                    "oldest_hours_approx": round(oldest_h, 1) if oldest_h is not None else None,
                })
                prev_count = len(all_urls)

                if oldest_h is not None and oldest_h >= 24.0:
                    print(f"Reached 24h coverage after {click_n} click(s).", file=sys.stderr)
                    report["summary"]["clicks_for_24h_coverage"] = click_n
                    break

    finally:
        await tab.close()
        await browser.stop()

    # Build final summary
    all_article_list = list(all_urls.values())
    oldest_h = oldest_age_hours(all_article_list)
    sample_sorted = _sample_by_age(all_article_list)
    report["summary"].update({
        "total_unique_urls": len(all_urls),
        "oldest_hours_approx": round(oldest_h, 1) if oldest_h is not None else None,
        "sample_labels": sample_sorted,
        "screenshot": SCREENSHOT_PATH,
    })

    path = write_output(report)
    _print_summary(report)
    print(f"\nJSON output: {path}", file=sys.stderr)


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


# Run JS + decode JSON response into list of article dicts
async def extract_articles(tab) -> list[dict]:
    raw = await tab.execute_script(_JS_EXTRACT)
    val = _extract_value(raw)
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


# Poll article count up to POLL_MAX × POLL_INTERVAL, return new count when it grows
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


# Compute hours since oldest article date (URL-based, conservative — midnight)
def oldest_age_hours(articles: list[dict]) -> float | None:
    dates = [parse_url_date(a["url"]) for a in articles]
    dates = [d for d in dates if d is not None]
    if not dates:
        return None
    oldest = min(dates)
    return (datetime.now(timezone.utc) - oldest).total_seconds() / 3600


# Return sample {url: label} for youngest, middle, oldest article
def _sample_by_age(articles: list[dict]) -> list[dict]:
    with_date = [(parse_url_date(a["url"]), a) for a in articles]
    with_date = [(d, a) for d, a in with_date if d is not None]
    if not with_date:
        return []
    with_date.sort(key=lambda x: x[0])
    indices = [0, len(with_date) // 2, len(with_date) - 1] if len(with_date) >= 3 else list(range(len(with_date)))
    seen = set()
    result = []
    for i in indices:
        if i not in seen:
            seen.add(i)
            _, a = with_date[i]
            result.append({"url": a["url"], "timeLabel": a["timeLabel"]})
    return result


# Write probe JSON output
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
    print(f"Total unique URLs  : {s.get('total_unique_urls', '?')}")
    print(f"Oldest age (approx): {s.get('oldest_hours_approx', '?')}h")
    print(f"Clicks for 24h     : {s.get('clicks_for_24h_coverage', 'not reached within rounds')}")
    print(f"Button text        : {btn.get('text', 'NOT FOUND')}")
    print(f"Button tag/class   : {btn.get('tagName', '?')} / {btn.get('className', '?')}")
    print(f"Button data-attrs  : {btn.get('dataAttrs', {})}")
    print(f"Screenshot         : {s.get('screenshot', '?')}")
    print("Sample articles (oldest→newest):")
    for item in reversed(s.get("sample_labels", [])):
        print(f"  {item['timeLabel'] or '(no label)':<20}  {item['url']}")


def main():
    parser = argparse.ArgumentParser(description="CoinDesk /latest-crypto-news UI probe via pydoll")
    parser.add_argument("--headless", action="store_true", default=False, help="Run headless (default: headed)")
    args = parser.parse_args()
    asyncio.run(probe_workflow(args.headless))


if __name__ == "__main__":
    main()
