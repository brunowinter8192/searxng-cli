#!/usr/bin/env python3
# INFRASTRUCTURE
import html
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

SITEMAP_URL = "https://www.coindesk.com/arc/outboundfeeds/news-sitemap-index"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
NS_SITEMAP = "http://www.sitemaps.org/schemas/sitemap/0.9"
NS_NEWS = "http://www.google.com/schemas/sitemap-news/0.9"
OUTPUT_DIR = Path(__file__).parent / "01_output"


# ORCHESTRATOR
def discover_workflow():
    xml_bytes = fetch_sitemap()
    entries = parse_sitemap(xml_bytes)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    kept = filter_and_sort(entries, cutoff)
    output_path = write_output(kept)
    print_summary(entries, kept, output_path)


# FUNCTIONS

# Fetch sitemap XML bytes with Mozilla UA
def fetch_sitemap() -> bytes:
    req = Request(SITEMAP_URL, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=15) as resp:
        return resp.read()


# Parse XML into list of entry dicts
def parse_sitemap(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    entries = []
    for url_el in root.findall(f"{{{NS_SITEMAP}}}url"):
        loc = _text(url_el, f"{{{NS_SITEMAP}}}loc")
        lastmod = _text(url_el, f"{{{NS_SITEMAP}}}lastmod")
        news_el = url_el.find(f"{{{NS_NEWS}}}news")
        if news_el is None:
            continue
        pub_date = _text(news_el, f"{{{NS_NEWS}}}publication_date")
        raw_title = _text(news_el, f"{{{NS_NEWS}}}title")
        title = _clean_title(raw_title)
        section = _extract_section(loc)
        entries.append({
            "url": loc,
            "lastmod": lastmod,
            "publication_date": pub_date,
            "title": title,
            "section": section,
        })
    return entries


# Keep entries within 24h window, sort by lastmod descending
def filter_and_sort(entries: list[dict], cutoff: datetime) -> list[dict]:
    kept = []
    for e in entries:
        try:
            dt = datetime.fromisoformat(e["lastmod"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if dt >= cutoff:
            kept.append(e)
    return sorted(kept, key=lambda e: e["lastmod"], reverse=True)


# Write JSON output, return path
def write_output(entries: list[dict]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUTPUT_DIR / f"discover_{ts}.json"
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# Print summary to stdout
def print_summary(all_entries: list[dict], kept: list[dict], output_path: Path):
    section_counts = Counter(e["section"] for e in kept)
    print(f"Sitemap total : {len(all_entries)} URLs")
    print(f"Last 24h kept : {len(kept)} URLs")
    print(f"Output        : {output_path}")
    print("Section distribution:")
    for section, count in section_counts.most_common():
        print(f"  {section}: {count}")


# Extract first path segment as section (e.g. /markets/2026/... → markets)
def _extract_section(url: str) -> str:
    try:
        path = url.split("coindesk.com", 1)[1]
        return path.strip("/").split("/")[0]
    except (IndexError, ValueError):
        return "unknown"


# Strip entity-encoded CDATA markers and unescape HTML entities
def _clean_title(raw: str) -> str:
    if not raw:
        return ""
    s = raw.strip()
    if s.startswith("<![CDATA["):
        s = s[9:]
    if s.endswith("]]>"):
        s = s[:-3]
    return html.unescape(s.strip())


# Safe text extraction from an XML element
def _text(parent: ET.Element, tag: str) -> str:
    el = parent.find(tag)
    return (el.text or "").strip() if el is not None else ""


if __name__ == "__main__":
    discover_workflow()
