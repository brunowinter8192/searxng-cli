# INFRASTRUCTURE
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, UndetectedAdapter
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from mcp.types import TextContent

# From scrape_url.py: Shared scraping utilities
from src.scraper.scrape_url import is_garbage_content, COOKIE_CONSENT_SELECTOR, MIN_CONTENT_THRESHOLD, get_plugin_hint, fetch_markdown_fastpath
# From scrape_logger.py: per-URL JSONL log + sidecar content file
from src.scraper.scrape_logger import log_scrape, write_sidecar

logger = logging.getLogger(__name__)

CLOUDFLARE_SENTINEL = "__cloudflare__"


# ORCHESTRATOR
async def scrape_url_raw_workflow(url: str, output_dir: str) -> list[TextContent]:
    t_total = time.perf_counter()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    domain = (urlparse(url).hostname or "").removeprefix("www.")
    logger.info("Scraping raw: %s", url)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    phases_attempted: list[str] = []
    timings_ms: dict = {"fastpath": None, "browser_1a": None, "browser_1b": None, "browser_2_stealth": None, "filter": None}
    phase_used: str | None = None
    win_status: int | None = None
    win_ct: str | None = None

    t0 = time.perf_counter()
    md, fp_status, fp_ct, fp_miss = await fetch_markdown_fastpath(url)
    timings_ms["fastpath"] = round((time.perf_counter() - t0) * 1000)
    phases_attempted.append("fastpath")

    if md:
        logger.info("Markdown fast-path hit: %s (%d chars)", url, len(md))
        parsed = urlparse(url)
        path = parsed.netloc + parsed.path
        safe_name = re.sub(r'[^\w\-.]', '_', path).strip('_')[:120] + ".md"
        filepath = output_path / safe_name
        filepath.write_text(f"<!-- source: {url} -->\n\n{md}")
        bytes_val = len(md.encode("utf-8"))
        content_path = write_sidecar(url, ts, md, "ok", "raw")
        log_scrape({
            "ts": ts, "url": url, "domain": domain, "mode": "raw", "outcome": "ok",
            "phase_used": "fastpath", "phases_attempted": phases_attempted,
            "timings_ms": {**timings_ms, "total_wall": round((time.perf_counter() - t_total) * 1000)},
            "http_status": fp_status, "content_type": fp_ct,
            "bytes_returned": bytes_val, "bytes_raw_markdown": bytes_val,
            "fallback_to_raw": None, "truncated": None, "consent_stripped": None, "garbage_type": None,
            "fastpath_hit": True, "fastpath_miss_reason": None, "content_path": content_path,
        })
        return [TextContent(type="text", text=f"Saved: {filepath} ({len(md):,} chars)")]

    markdown_generator = DefaultMarkdownGenerator()
    normal_config = BrowserConfig(headless=True, verbose=False)

    t0 = time.perf_counter()
    phases_attempted.append("browser_1a")
    content, s1, ct1 = await try_scrape_raw(normal_config, None, markdown_generator, url, "networkidle")
    timings_ms["browser_1a"] = round((time.perf_counter() - t0) * 1000)
    if content and content != CLOUDFLARE_SENTINEL:
        phase_used = "browser_1a"
        win_status, win_ct = s1, ct1

    if content == CLOUDFLARE_SENTINEL:
        total_wall = round((time.perf_counter() - t_total) * 1000)
        log_scrape({
            "ts": ts, "url": url, "domain": domain, "mode": "raw", "outcome": "error",
            "phase_used": None, "phases_attempted": phases_attempted,
            "timings_ms": {**timings_ms, "total_wall": total_wall},
            "http_status": s1, "content_type": ct1,
            "bytes_returned": None, "bytes_raw_markdown": None,
            "fallback_to_raw": None, "truncated": None, "consent_stripped": None, "garbage_type": None,
            "fastpath_hit": False, "fastpath_miss_reason": fp_miss, "content_path": None,
        })
        return [TextContent(type="text", text=f"Error scraping {url}: Cloudflare-protected page. Find an alternative source.")]

    if not content:
        t0 = time.perf_counter()
        phases_attempted.append("browser_1b")
        c2, s2, ct2 = await try_scrape_raw(normal_config, None, markdown_generator, url, "domcontentloaded")
        timings_ms["browser_1b"] = round((time.perf_counter() - t0) * 1000)
        if c2 and c2 != CLOUDFLARE_SENTINEL:
            content = c2
            phase_used = "browser_1b"
            win_status, win_ct = s2, ct2
        elif c2 == CLOUDFLARE_SENTINEL:
            content = c2

    if content == CLOUDFLARE_SENTINEL:
        total_wall = round((time.perf_counter() - t_total) * 1000)
        log_scrape({
            "ts": ts, "url": url, "domain": domain, "mode": "raw", "outcome": "error",
            "phase_used": None, "phases_attempted": phases_attempted,
            "timings_ms": {**timings_ms, "total_wall": total_wall},
            "http_status": None, "content_type": None,
            "bytes_returned": None, "bytes_raw_markdown": None,
            "fallback_to_raw": None, "truncated": None, "consent_stripped": None, "garbage_type": None,
            "fastpath_hit": False, "fastpath_miss_reason": fp_miss, "content_path": None,
        })
        return [TextContent(type="text", text=f"Error scraping {url}: Cloudflare-protected page. Find an alternative source.")]

    if not content:
        stealth_config = BrowserConfig(headless=True, verbose=False, enable_stealth=True)
        adapter = UndetectedAdapter()
        stealth_strategy = AsyncPlaywrightCrawlerStrategy(
            browser_config=stealth_config,
            browser_adapter=adapter
        )
        t0 = time.perf_counter()
        phases_attempted.append("browser_2_stealth")
        c3, s3, ct3 = await try_scrape_raw(stealth_config, stealth_strategy, markdown_generator, url, "networkidle")
        timings_ms["browser_2_stealth"] = round((time.perf_counter() - t0) * 1000)
        if c3 and c3 != CLOUDFLARE_SENTINEL:
            content = c3
            phase_used = "browser_2_stealth"
            win_status, win_ct = s3, ct3
        elif c3 == CLOUDFLARE_SENTINEL:
            content = c3

    if content == CLOUDFLARE_SENTINEL:
        total_wall = round((time.perf_counter() - t_total) * 1000)
        log_scrape({
            "ts": ts, "url": url, "domain": domain, "mode": "raw", "outcome": "error",
            "phase_used": None, "phases_attempted": phases_attempted,
            "timings_ms": {**timings_ms, "total_wall": total_wall},
            "http_status": None, "content_type": None,
            "bytes_returned": None, "bytes_raw_markdown": None,
            "fallback_to_raw": None, "truncated": None, "consent_stripped": None, "garbage_type": None,
            "fastpath_hit": False, "fastpath_miss_reason": fp_miss, "content_path": None,
        })
        return [TextContent(type="text", text=f"Error scraping {url}: Cloudflare-protected page. Find an alternative source.")]

    total_wall = round((time.perf_counter() - t_total) * 1000)

    if not content:
        log_scrape({
            "ts": ts, "url": url, "domain": domain, "mode": "raw", "outcome": "empty",
            "phase_used": None, "phases_attempted": phases_attempted,
            "timings_ms": {**timings_ms, "total_wall": total_wall},
            "http_status": None, "content_type": None,
            "bytes_returned": None, "bytes_raw_markdown": None,
            "fallback_to_raw": None, "truncated": None, "consent_stripped": None, "garbage_type": None,
            "fastpath_hit": False, "fastpath_miss_reason": fp_miss, "content_path": None,
        })
        hint = get_plugin_hint(url)
        msg = f"Error scraping {url}: No content extracted"
        if hint:
            msg += f"\n\nHint: {hint}"
        return [TextContent(type="text", text=msg)]

    parsed = urlparse(url)
    path = parsed.netloc + parsed.path
    safe_name = re.sub(r'[^\w\-.]', '_', path).strip('_')[:120] + ".md"
    filepath = output_path / safe_name
    filepath.write_text(f"<!-- source: {url} -->\n\n{content}")

    logger.info("Scrape complete: %s → %s (%d chars)", url, filepath, len(content))
    bytes_val = len(content.encode("utf-8"))
    content_path = write_sidecar(url, ts, content, "ok", "raw")
    log_scrape({
        "ts": ts, "url": url, "domain": domain, "mode": "raw", "outcome": "ok",
        "phase_used": phase_used, "phases_attempted": phases_attempted,
        "timings_ms": {**timings_ms, "total_wall": total_wall},
        "http_status": win_status, "content_type": win_ct,
        "bytes_returned": bytes_val, "bytes_raw_markdown": bytes_val,
        "fallback_to_raw": None, "truncated": None, "consent_stripped": None, "garbage_type": None,
        "fastpath_hit": False, "fastpath_miss_reason": fp_miss, "content_path": content_path,
    })
    return [TextContent(type="text", text=f"Saved: {filepath} ({len(content):,} chars)")]


# FUNCTIONS

# Detect Cloudflare / JS challenge interstitial pages
def is_cloudflare_content(content: str) -> bool:
    lower = content.lower()
    if len(content) < 500:
        if "checking your browser" in lower or "enable javascript and cookies" in lower:
            return True
    if "just a moment" in lower and "cloudflare" in lower:
        return True
    return False


# Attempt raw scrape (no content filter); return (content_or_sentinel, status_code, content_type)
# content_or_sentinel: raw markdown string | CLOUDFLARE_SENTINEL | ""
async def try_scrape_raw(browser_config, crawler_strategy, markdown_generator, url: str, wait_until: str) -> tuple[str, int | None, str | None]:
    logger.debug("Trying %s wait strategy", wait_until)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until=wait_until,
        excluded_selector=COOKIE_CONSENT_SELECTOR,
        markdown_generator=markdown_generator,
    )
    try:
        kwargs = {"config": browser_config}
        if crawler_strategy:
            kwargs["crawler_strategy"] = crawler_strategy
        async with AsyncWebCrawler(**kwargs) as crawler:
            result = await crawler.arun(url=url, config=run_config)
        status_code = result.status_code if hasattr(result, "status_code") else None
        ct = None
        if hasattr(result, "headers") and result.headers:
            ct = result.headers.get("content-type") or result.headers.get("Content-Type")
        if not result.markdown:
            return "", status_code, ct
        content = result.markdown.raw_markdown
        if not content:
            return "", status_code, ct
        if is_cloudflare_content(content):
            return CLOUDFLARE_SENTINEL, status_code, ct
        if len(content) < MIN_CONTENT_THRESHOLD:
            return "", status_code, ct
        if is_garbage_content(content):
            logger.warning("Garbage content detected for %s", url)
            return "", status_code, ct
        return content, status_code, ct
    except Exception as e:
        logger.warning("Failed to scrape %s: %s", url, e)
        return "", None, None
