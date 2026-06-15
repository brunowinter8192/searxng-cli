# INFRASTRUCTURE
import re
import sys
from datetime import datetime, timedelta, timezone

import httpx

from src.news.engine.proxy_pool.fetch import fetch_url
from src.news.engine.proxy_pool.pool_loaders import load_backfill_pool
from src.news.platforms.theblock.config import SITEMAP_INDEX, DIRECT_TIMEOUT

_INDEX_LOC_RE = re.compile(rb"<loc>(https?://[^<]+)</loc>")
_URL_BLOCK_RE = re.compile(rb"<url>(.*?)</url>", re.DOTALL)
_LOC_RE       = re.compile(rb"<loc>(https?://[^<]+)</loc>")
_MOD_RE       = re.compile(rb"<lastmod>([^<]+)</lastmod>")
_NUM_RE       = re.compile(r"_(\d+)\.xml$")
_RANGE_RE     = re.compile(r"^\d{4}-\d{2}-\d{2}:\d{4}-\d{2}-\d{2}$")
XML_MARKERS   = (b"<?xml", b"<sitemapindex", b"<urlset", b"<sitemap>")


# ORCHESTRATOR

# Fetch theblock sitemap index → post_type_post subs → select by timeframe → [{url, lastmod}].
# timeframe: "48h" (highest sub, lastmod >= now-48h) | "full" (all subs) | "YYYY-MM-DD:YYYY-MM-DD" (range).
# publication_date is NOT set here — comes from JSON-LD post-fetch in cleanup.
async def discover(timeframe: str = "48h") -> list[dict]:
    cutoff_start, cutoff_end = _parse_timeframe(timeframe)
    pool_cache: list = []  # lazy-loaded on first proxy fallback, shared across all fetches

    index_content = _fetch_xml(SITEMAP_INDEX, pool_cache)
    if index_content is None:
        raise RuntimeError("theblock sitemap index fetch failed (direct + proxy exhausted)")
    post_subs = _parse_post_sub_urls(index_content)
    if not post_subs:
        raise RuntimeError("No post_type_post sub-sitemaps found in theblock sitemap index")
    print(f"[theblock] {len(post_subs)} post_type_post sub-sitemaps", file=sys.stderr)

    if timeframe == "full" or (cutoff_start is not None and cutoff_end is not None):
        target_subs = post_subs
    else:
        target_subs = [_pick_highest_numbered(post_subs)]
    print(f"[theblock] Fetching {len(target_subs)} sub-sitemap(s) …", file=sys.stderr)

    entries = []
    for sub_url in target_subs:
        content = _fetch_xml(sub_url, pool_cache)
        if content is None:
            print(f"[theblock] Sub-sitemap failed, skipping: {sub_url.split('/')[-1]}", file=sys.stderr)
            continue
        for url, lastmod in _parse_url_blocks(content):
            if _in_window(lastmod, cutoff_start, cutoff_end):
                entries.append({"url": url, "lastmod": lastmod.isoformat()})

    print(f"[theblock] discover → {len(entries)} entries (timeframe={timeframe!r})", file=sys.stderr)
    return entries


# FUNCTIONS

# Return (cutoff_start, cutoff_end): both None = no filter; only start = 48h; both set = range.
def _parse_timeframe(timeframe: str) -> tuple[datetime | None, datetime | None]:
    if timeframe == "full":
        return None, None
    if _RANGE_RE.match(timeframe):
        a, b = timeframe.split(":")
        start = datetime.fromisoformat(a).replace(tzinfo=timezone.utc)
        end   = datetime.fromisoformat(b).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        return start, end
    return datetime.now(timezone.utc) - timedelta(hours=48), None


# Return True if lastmod falls within (cutoff_start, cutoff_end) window; both None = always True.
def _in_window(lastmod: datetime, cutoff_start: datetime | None, cutoff_end: datetime | None) -> bool:
    if cutoff_start is not None and lastmod < cutoff_start:
        return False
    if cutoff_end is not None and lastmod > cutoff_end:
        return False
    return True


# Try direct httpx first; on failure, load pool lazily and iterate proxies; return bytes or None.
def _fetch_xml(url: str, pool_cache: list) -> bytes | None:
    content = _fetch_direct(url)
    if content is not None:
        return content
    if not pool_cache:
        print("[theblock] Loading proxy pool for sitemap fallback …", file=sys.stderr)
        pool_cache.extend(load_backfill_pool())
    for proto, hp in pool_cache:
        status, content = fetch_url(proto, hp, url, "xml")
        if status == "ok":
            return content
    return None


# Direct httpx GET; return bytes if valid XML, else None.
def _fetch_direct(url: str) -> bytes | None:
    try:
        r = httpx.get(url, timeout=DIRECT_TIMEOUT, follow_redirects=True)
        head = r.content[:500]
        if r.status_code == 200 and any(m in head for m in XML_MARKERS):
            return r.content
        return None
    except Exception:
        return None


# Extract post_type_post sub-sitemap <loc> URLs from index bytes.
def _parse_post_sub_urls(content: bytes) -> list[str]:
    return [
        m.group(1).decode().strip()
        for m in _INDEX_LOC_RE.finditer(content)
        if b"post_type_post" in m.group(1)
    ]


# Return the sub-sitemap URL with the highest trailing integer (= newest page).
def _pick_highest_numbered(urls: list[str]) -> str:
    def _num(u: str) -> int:
        m = _NUM_RE.search(u)
        return int(m.group(1)) if m else -1
    return max(urls, key=_num)


# Parse <url> blocks from sub-sitemap XML; return (loc_url, lastmod_datetime) pairs.
def _parse_url_blocks(content: bytes) -> list[tuple[str, datetime]]:
    results = []
    for block in _URL_BLOCK_RE.finditer(content):
        body  = block.group(1)
        loc_m = _LOC_RE.search(body)
        mod_m = _MOD_RE.search(body)
        if not loc_m or not mod_m:
            continue
        url     = loc_m.group(1).decode().strip()
        mod_raw = mod_m.group(1).decode().strip().replace("Z", "+00:00")
        try:
            mod = datetime.fromisoformat(mod_raw)
            if mod.tzinfo is None:
                mod = mod.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        results.append((url, mod))
    return results
