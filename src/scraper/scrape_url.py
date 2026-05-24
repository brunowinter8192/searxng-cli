# INFRASTRUCTURE
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, UndetectedAdapter
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from mcp.types import TextContent
# From scrape_logger.py: per-URL JSONL log + sidecar content file
from src.scraper.scrape_logger import log_scrape, write_sidecar

logger = logging.getLogger(__name__)

_LINK_LINE_RE = re.compile(r'^\[.+\]\(.+\)$')

DEFAULT_MAX_CONTENT_LENGTH = 15000
MIN_CONTENT_THRESHOLD = 200
MD_FASTPATH_MIN_BYTES = 200
MD_FASTPATH_TIMEOUT = 5.0

CONSENT_WORDS = ["cookie", "consent", "einwilligung", "tracking", "akzeptieren", "datenschutz", "zweck"]
CONSENT_DENSITY_THRESHOLD = 5
CONSENT_SKIP_OFFSET = 300

COOKIE_CONSENT_SELECTOR = ", ".join([
    "[class*='cookie-banner']", "[id*='cookie-banner']",
    "[class*='cookie-consent']", "[id*='cookie-consent']",
    "[class*='cookie-notice']", "[id*='cookie-notice']",
    "[class*='cookie-law']", "[id*='cookie-law']",
    "[class*='cky-consent']", "[class*='cky-banner']", "[class*='cky-modal']",
    "[class*='onetrust']", "[id*='onetrust']",
    "[id*='CookiebotDialog']", "[class*='CookiebotWidget']",
    "[class*='cc-banner']", "[class*='cc-window']",
    "[class*='gdpr']", "[id*='gdpr']",
])

_GARBAGE_MESSAGES = {
    "minimal_content": "Page returned only whitespace or near-empty content",
    "cookie_wall": "Cookie/consent wall detected — page returns only GDPR consent text, not actual content",
    "login_wall": "Login/paywall detected — page requires authentication",
    "cloudflare": "Cloudflare protection — page requires browser verification",
    "http_error": "HTTP error page (404/403)",
    "nav_dump": "Navigation dump — page returned only links, no content",
    "crawl4ai_error": "Crawl4AI extraction error",
}


# ORCHESTRATOR
async def scrape_url_workflow(url: str, max_content_length: int = DEFAULT_MAX_CONTENT_LENGTH) -> list[TextContent]:
    t_total = time.perf_counter()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    domain = (urlparse(url).hostname or "").removeprefix("www.")
    logger.info("Scraping: %s", url)

    phases_attempted: list[str] = []
    timings_ms: dict = {"fastpath": None, "browser_1a": None, "browser_1b": None, "browser_2_stealth": None, "filter": None}
    phase_used: str | None = None
    winning_meta: dict = {}
    last_garbage: str | None = None
    last_garbage_content: str | None = None

    t0 = time.perf_counter()
    md, fp_status, fp_ct, fp_miss = await fetch_markdown_fastpath(url)
    timings_ms["fastpath"] = round((time.perf_counter() - t0) * 1000)
    phases_attempted.append("fastpath")

    if md:
        logger.debug("Markdown fast-path hit: %s (%d chars)", url, len(md))
        phase_used = "fastpath"
        final = truncate_content(md, max_content_length)
        content_path = write_sidecar(url, ts, final, "ok", "filtered")
        log_scrape({
            "ts": ts, "url": url, "domain": domain, "mode": "filtered", "outcome": "ok",
            "phase_used": "fastpath", "phases_attempted": phases_attempted,
            "timings_ms": {**timings_ms, "total_wall": round((time.perf_counter() - t_total) * 1000)},
            "http_status": fp_status, "content_type": fp_ct,
            "bytes_returned": len(final.encode("utf-8")), "bytes_raw_markdown": len(md.encode("utf-8")),
            "fallback_to_raw": False, "truncated": len(md) > max_content_length,
            "consent_stripped": False, "garbage_type": None,
            "fastpath_hit": True, "fastpath_miss_reason": None, "content_path": content_path,
        })
        return [TextContent(type="text", text=f"# Content from: {url}\n\n{final}")]

    markdown_generator = DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.48)
    )
    normal_config = BrowserConfig(headless=True, verbose=False)

    t0 = time.perf_counter()
    phases_attempted.append("browser_1a")
    content, m1a = await try_scrape(normal_config, None, markdown_generator, url, "networkidle")
    timings_ms["browser_1a"] = round((time.perf_counter() - t0) * 1000)
    if content:
        phase_used = "browser_1a"
        winning_meta = m1a
    else:
        if m1a.get("garbage_type"):
            last_garbage = m1a["garbage_type"]
        if m1a.get("garbage_content"):
            last_garbage_content = m1a["garbage_content"]

    if not content:
        t0 = time.perf_counter()
        phases_attempted.append("browser_1b")
        c2, m1b = await try_scrape(normal_config, None, markdown_generator, url, "domcontentloaded")
        timings_ms["browser_1b"] = round((time.perf_counter() - t0) * 1000)
        if c2:
            content = c2
            phase_used = "browser_1b"
            winning_meta = m1b
        else:
            if m1b.get("garbage_type"):
                last_garbage = m1b["garbage_type"]
            if m1b.get("garbage_content"):
                last_garbage_content = m1b["garbage_content"]

    if not content:
        stealth_config = BrowserConfig(headless=True, verbose=False, enable_stealth=True)
        adapter = UndetectedAdapter()
        stealth_strategy = AsyncPlaywrightCrawlerStrategy(
            browser_config=stealth_config,
            browser_adapter=adapter
        )
        t0 = time.perf_counter()
        phases_attempted.append("browser_2_stealth")
        c3, m2 = await try_scrape(stealth_config, stealth_strategy, markdown_generator, url, "networkidle")
        timings_ms["browser_2_stealth"] = round((time.perf_counter() - t0) * 1000)
        if c3:
            content = c3
            phase_used = "browser_2_stealth"
            winning_meta = m2
        else:
            if m2.get("garbage_type"):
                last_garbage = m2["garbage_type"]
            if m2.get("garbage_content"):
                last_garbage_content = m2["garbage_content"]

    total_wall = round((time.perf_counter() - t_total) * 1000)

    if not content:
        log_scrape_failure(url, last_garbage, winning_meta.get("status_code"))
        outcome = last_garbage if last_garbage else "empty"
        content_path = write_sidecar(url, ts, last_garbage_content, outcome, "filtered")
        log_scrape({
            "ts": ts, "url": url, "domain": domain, "mode": "filtered", "outcome": outcome,
            "phase_used": None, "phases_attempted": phases_attempted,
            "timings_ms": {**timings_ms, "total_wall": total_wall},
            "http_status": None, "content_type": None,
            "bytes_returned": None, "bytes_raw_markdown": None,
            "fallback_to_raw": False, "truncated": False,
            "consent_stripped": False, "garbage_type": last_garbage,
            "fastpath_hit": False, "fastpath_miss_reason": fp_miss, "content_path": content_path,
        })
        hint = get_plugin_hint(url)
        reason = _GARBAGE_MESSAGES[last_garbage] if last_garbage else "No content extracted"
        msg = f"Error scraping {url}: {reason}"
        if hint:
            msg += f"\n\nHint: {hint}"
        return [TextContent(type="text", text=msg)]

    logger.info("Scrape complete: %s (%d chars)", url, len(content))
    final = truncate_content(content, max_content_length)
    content_path = write_sidecar(url, ts, final, "ok", "filtered")
    log_scrape({
        "ts": ts, "url": url, "domain": domain, "mode": "filtered", "outcome": "ok",
        "phase_used": phase_used, "phases_attempted": phases_attempted,
        "timings_ms": {**timings_ms, "total_wall": total_wall},
        "http_status": winning_meta.get("status_code"), "content_type": winning_meta.get("content_type"),
        "bytes_returned": len(final.encode("utf-8")),
        "bytes_raw_markdown": winning_meta.get("raw_markdown_bytes", len(content.encode("utf-8"))),
        "fallback_to_raw": winning_meta.get("fallback_to_raw", False),
        "truncated": len(content) > max_content_length,
        "consent_stripped": winning_meta.get("consent_stripped", False),
        "garbage_type": None,
        "fastpath_hit": False, "fastpath_miss_reason": fp_miss, "content_path": content_path,
    })
    return [TextContent(type="text", text=f"# Content from: {url}\n\n{final}")]


# FUNCTIONS

# Try Accept: text/markdown fast-path; return (content, status_code, content_type, miss_reason)
# On hit: (body, 200, ct, None). On miss: (None, status_code_or_None, ct_or_None, reason_str).
# miss_reason values: "http_error" | "wrong_content_type" | "sub_threshold" | "network_error"
async def fetch_markdown_fastpath(url: str) -> tuple[str | None, int | None, str | None, str | None]:
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=MD_FASTPATH_TIMEOUT) as client:
            resp = await client.get(url, headers={"Accept": "text/markdown, text/html"})
        ct = resp.headers.get("content-type", "") or ""
        if resp.status_code != 200:
            logger.debug("Markdown fast-path miss (HTTP %d): %s", resp.status_code, url)
            return None, resp.status_code, None, "http_error"
        if "text/markdown" not in ct:
            logger.debug("Markdown fast-path miss (ct=%s): %s", ct.split(";")[0].strip(), url)
            return None, resp.status_code, ct, "wrong_content_type"
        body = resp.text
        if len(body) < MD_FASTPATH_MIN_BYTES:
            logger.debug("Markdown fast-path sub-threshold (%d bytes): %s", len(body), url)
            return None, resp.status_code, ct, "sub_threshold"
        return body, resp.status_code, ct, None
    except Exception as exc:
        logger.debug("Markdown fast-path error for %s: %s", url, exc)
        return None, None, None, "network_error"


# Attempt scrape with given wait strategy; return (content, meta) where meta is a dict with:
# garbage_type, status_code, content_type, fallback_to_raw, consent_stripped,
# garbage_content (content that triggered garbage detection, for sidecar logging),
# raw_markdown_bytes (raw_markdown length before filter/fallback, for bytes_raw_markdown field)
async def try_scrape(browser_config, crawler_strategy, markdown_generator, url: str, wait_until: str) -> tuple[str, dict]:
    logger.debug("Trying %s wait strategy", wait_until)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until=wait_until,
        excluded_selector=COOKIE_CONSENT_SELECTOR,
        markdown_generator=markdown_generator,
        verbose=False,
    )
    _empty_meta: dict = {
        "garbage_type": None, "status_code": None, "content_type": None,
        "fallback_to_raw": False, "consent_stripped": False,
        "garbage_content": None, "raw_markdown_bytes": 0,
    }
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
        meta: dict = {**_empty_meta, "status_code": status_code, "content_type": ct}
        if status_code and status_code >= 400:
            logger.warning("HTTP %d detected: %s", status_code, url)
            return "", {**meta, "garbage_type": "http_error"}
        if not result.markdown:
            return "", meta
        raw_md = result.markdown.raw_markdown or ""
        meta["raw_markdown_bytes"] = len(raw_md.encode("utf-8"))
        content = result.markdown.fit_markdown or ""
        fallback_to_raw = False
        if len(content) < MIN_CONTENT_THRESHOLD and raw_md:
            content = raw_md
            fallback_to_raw = True
        meta["fallback_to_raw"] = fallback_to_raw
        garbage_type = is_garbage_content(content)
        if garbage_type == "cookie_wall":
            stripped = strip_consent_prefix(content)
            if stripped != content and is_garbage_content(stripped) is None:
                logger.debug("Consent prefix stripped: %s (%d chars removed)", url, len(content) - len(stripped))
                return stripped, {**meta, "consent_stripped": True}
        if garbage_type:
            logger.warning("Garbage detected [%s]: %s", garbage_type, url)
            return "", {**meta, "garbage_type": garbage_type, "garbage_content": content}
        return content, meta
    except Exception as e:
        logger.warning("Failed to scrape %s: %s", url, e)
        return "", dict(_empty_meta)


# Append one JSONL failure record to dev/scrape_pipeline/failures.jsonl
def log_scrape_failure(url: str, garbage_type: str | None, status_code: int | None) -> None:
    project_root = os.environ.get("SEARXNG_PROJECT_ROOT")
    if not project_root:
        return
    try:
        log_path = Path(project_root) / "dev" / "scrape_pipeline" / "failures.jsonl"
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "url": url,
            "garbage_type": garbage_type,
            "status_code": status_code,
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.warning("Failed to log scrape failure: %s", e)


# Detect garbage content: error pages, cookie walls, login walls, navigation dumps
def is_garbage_content(content: str) -> str | None:
    if not content or len(content.strip()) < 50:
        return "minimal_content"
    lower = content.lower()

    crawl4ai_errors = ["crawl4ai error:", "document is empty", "page is not fully supported"]
    if any(p in lower for p in crawl4ai_errors):
        return "crawl4ai_error"

    if len(content) < 1000:
        error_keywords = ["not_found", "404", "403", "forbidden", "access denied", "page not found"]
        if any(k in lower for k in error_keywords):
            return "http_error"

    lines = [l.strip() for l in content.splitlines() if l.strip()]
    if len(lines) >= 20:
        link_lines = sum(1 for l in lines if _LINK_LINE_RE.match(l))
        if link_lines / len(lines) > 0.6:
            return "nav_dump"

    sample = lower[:5000]
    cookie_signals = sample.count("cookie") + sample.count("consent") + sample.count("duration")
    cookie_wall_signals = ("consent preferences" in sample or "cookieyes" in sample or "cookie preferences" in sample)
    if cookie_signals > 15 and cookie_wall_signals:
        return "cookie_wall"

    if len(content) < 2000:
        login_patterns = [
            "sign in", "log in", "login", "subscribe to continue", "create account",
            "create an account", "premium content", "paywall", "members only", "subscriber only",
        ]
        if any(p in lower for p in login_patterns):
            return "login_wall"

    if len(content) < 500:
        if "checking your browser" in lower or "enable javascript and cookies" in lower:
            return "cloudflare"

    if "just a moment" in lower and "cloudflare" in lower:
        return "cloudflare"

    return None


# Strip leading consent block: detect by keyword density, cut before first heading after offset
def strip_consent_prefix(content: str) -> str:
    if not content:
        return content
    sample = content[:3000].lower()
    density = sum(sample.count(w) for w in CONSENT_WORDS)
    if density <= CONSENT_DENSITY_THRESHOLD:
        return content
    match = re.search(r'\n(#{1,2} )', content[CONSENT_SKIP_OFFSET:])
    if match:
        pos = CONSENT_SKIP_OFFSET + match.start() + 1
        return content[pos:]
    return content


# Truncate content at paragraph boundary if too long
def truncate_content(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    truncated = text[:max_length]
    last_newline = truncated.rfind('\n\n')
    if last_newline > max_length * 0.8:
        truncated = truncated[:last_newline]
    return truncated + "\n\n[Content truncated...]"


# Return plugin hint for domains with dedicated MCP plugins, empty string otherwise
def get_plugin_hint(url: str) -> str:
    from urllib.parse import urlparse
    from src.routing import PLUGIN_ROUTED_DOMAINS
    try:
        host = (urlparse(url).hostname or "").removeprefix("www.")
    except Exception:
        return ""
    for domain in PLUGIN_ROUTED_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return f"This domain has a dedicated MCP plugin. Use the appropriate plugin tool instead of scrape_url."
    return ""
