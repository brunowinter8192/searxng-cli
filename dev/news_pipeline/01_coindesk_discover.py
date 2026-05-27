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
REAL_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.7680.154 Safari/537.36"
)
MAX_CLICK_ROUNDS = 8   # safety cap: 8 × ~16 URLs/batch ≈ 128 URLs max
POLL_INTERVAL = 0.5
POLL_MAX = 40          # 20s max wait per click
PRE_TODAY_THRESHOLD = 3
DATE_RE = re.compile(r'/(\d{4})/(\d{2})/(\d{2})/')
OUTPUT_DIR = Path(__file__).parent / "01_output"

# Extract feed article URLs + title + nearest time label — excludes aside/nav/footer/sidebar noise
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


# ORCHESTRATOR
async def discover_workflow(headless: bool):
    session_dir = tempfile.mkdtemp(prefix="coindesk_discover_")
    today = datetime.now(timezone.utc).date()

    browser = Chrome(build_options(headless, session_dir))
    tab = await browser.start()
    try:
        print(f"Navigating to {TARGET_URL} …", file=sys.stderr)
        await tab.go_to(TARGET_URL, timeout=60)
        await asyncio.sleep(3.0)

        initial = await extract_articles(tab)
        all_urls: dict[str, dict] = {a["url"]: a for a in initial}
        print(f"Batch 0: {len(initial)} initial articles", file=sys.stderr)

        for click_n in range(1, MAX_CLICK_ROUNDS + 1):
            pre = count_pre_today(list(all_urls.values()), today)
            if pre >= PRE_TODAY_THRESHOLD:
                print(f"Coverage reached: {pre} pre-today articles (before click {click_n}).", file=sys.stderr)
                break

            prev_count = len(all_urls)
            clicked = await click_button(tab)
            if not clicked:
                print(f"Button gone at click {click_n} — end of feed.", file=sys.stderr)
                break

            await asyncio.sleep(2.0)
            await wait_for_new_articles(tab, prev_count)
            fresh = await extract_articles(tab)
            added = {a["url"]: a for a in fresh if a["url"] not in all_urls}
            all_urls.update(added)
            pre = count_pre_today(list(all_urls.values()), today)
            print(f"Batch {click_n}: +{len(added)} | total={len(all_urls)} | pre-today={pre}", file=sys.stderr)

            if pre >= PRE_TODAY_THRESHOLD:
                print(f"Coverage reached: {pre} pre-today articles after {click_n} click(s).", file=sys.stderr)
                break
        else:
            print(
                "WARNING: MAX_CLICK_ROUNDS reached without termination — coverage may be incomplete",
                file=sys.stderr,
            )

    finally:
        await tab.close()
        try:
            await browser.stop()
        except Exception as e:
            print(f"Browser stop (non-fatal): {e}", file=sys.stderr)

    entries = build_entries(all_urls)
    path = write_output(entries)
    print_summary(entries, path)


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


# Convert URL date to ISO-8601 string (UTC midnight); empty string if no date in URL
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


# Write JSON output, return path
def write_output(entries: list[dict]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUTPUT_DIR / f"discover_{ts}.json"
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# Print summary to stdout
def print_summary(entries: list[dict], output_path: Path):
    from collections import Counter
    section_counts = Counter(e["section"] for e in entries)
    print(f"Total discovered : {len(entries)} URLs")
    print(f"Output           : {output_path}")
    print("Section distribution:")
    for section, count in section_counts.most_common():
        print(f"  {section}: {count}")


def main():
    parser = argparse.ArgumentParser(
        description="CoinDesk /latest-crypto-news discovery via pydoll UI pagination (headed by default)"
    )
    parser.add_argument("--headless", action="store_true", default=False,
                        help="Run headless (default: headed, for visual inspection)")
    args = parser.parse_args()
    asyncio.run(discover_workflow(args.headless))


if __name__ == "__main__":
    main()
