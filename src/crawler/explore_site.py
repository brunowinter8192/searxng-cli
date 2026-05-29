# INFRASTRUCTURE
import argparse
import asyncio
import logging
import time
from urllib.parse import urlparse

import requests
from src.crawler.crawl_site import (discover_urls_playwright,
                                    DEFAULT_DELAY_S, DEFAULT_PAGE_TIMEOUT_MS,
                                    DEFAULT_DISCOVER_CONCURRENCY)
from src.crawler.filter_urls import match_any

logger = logging.getLogger(__name__)

DEFAULT_MAX_PAGES = 200


# ORCHESTRATOR
async def explore_site_workflow(url: str, max_pages: int, output: str,
                                depth: int, include_patterns: str, exclude_patterns: str,
                                append: bool = False, delay_s: float = DEFAULT_DELAY_S,
                                page_timeout_ms: int = DEFAULT_PAGE_TIMEOUT_MS,
                                concurrency: int = DEFAULT_DISCOVER_CONCURRENCY,
                                stealth: bool = False):
    domain = urlparse(url).netloc

    if output is None:
        output = f"/tmp/explore_{domain}_urls.txt"

    resolved_url, resolved_domain = resolve_redirect(url)
    if resolved_domain != domain:
        logger.info("Redirect detected: %s -> %s (domain: %s -> %s)",
                    url, resolved_url, domain, resolved_domain)
        url = resolved_url
        domain = resolved_domain

    logger.info("Exploring %s (max_pages=%d, depth=%d, concurrency=%d)",
                url, max_pages, depth, concurrency)

    start = time.time()
    urls, stats = await discover_urls_playwright(
        url, include_patterns, exclude_patterns, max_pages, depth,
        delay_s, page_timeout_ms, concurrency, stealth,
    )
    duration = time.time() - start

    logger.info("Discovery: %d URLs in %.1fs — stop_reason=%s, 429s=%d",
                len(urls), duration, stats["stop_reason"], stats["four_two_nine_count"])

    if append:
        existing = load_existing_urls(output)
        new_urls = [u for u in urls if u not in existing]
        logger.debug("New URLs: %d (filtered %d duplicates)", len(new_urls), len(urls) - len(new_urls))
        urls = new_urls

    print_url_samples(urls)
    save_url_list(urls, output, append=append)
    logger.info("Saved %d URLs to %s", len(urls), output)

    if stats["stop_reason"] == "max_pages_reached":
        logger.info("Hit max_pages limit (%d). Run again with --max-pages %d --append to discover more.",
                    max_pages, max_pages * 2)

    return urls, stats["stop_reason"], stats["four_two_nine_count"], output


# FUNCTIONS

# Resolve HTTP redirects to get final URL and domain
def resolve_redirect(url: str) -> tuple[str, str]:
    try:
        resp = requests.head(url, allow_redirects=True, timeout=10)
        final_url = resp.url
        final_domain = urlparse(final_url).netloc
        return final_url, final_domain
    except Exception as e:
        logger.warning("Redirect resolution failed for %s: %s", url, e)
        return url, urlparse(url).netloc


# Print URL samples for noise pattern identification
def print_url_samples(urls: list[str], max_samples: int = 15) -> None:
    if not urls:
        return
    total = len(urls)
    indices = set()
    for i in range(min(5, total)):
        indices.add(i)
    for i in range(max(0, total - 5), total):
        indices.add(i)
    if total > 10:
        step = total // 5
        for i in range(5):
            indices.add(min(i * step, total - 1))
    sorted_indices = sorted(indices)[:max_samples]
    logger.debug("=== URL Samples (%d of %d) ===", len(sorted_indices), total)
    for i in sorted_indices:
        logger.debug("[%4d] %s", i + 1, urls[i])


# Load existing URLs from file (for dedup on append)
def load_existing_urls(path: str) -> set[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        return set()


# Save URL list to text file (one URL per line)
def save_url_list(urls: list[str], output_path: str, append: bool = False) -> None:
    mode = "a" if append else "w"
    with open(output_path, mode, encoding="utf-8") as f:
        for url in urls:
            f.write(url + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Discover all URLs of a website via Playwright-per-page BFS and save to a file"
    )
    parser.add_argument("--url", required=True, help="Seed URL to explore")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES,
                        help=f"Max pages to discover (default: {DEFAULT_MAX_PAGES})")
    parser.add_argument("--output", type=str, default=None,
                        help="Output file path (default: /tmp/explore_<domain>_urls.txt)")
    parser.add_argument("--depth", type=int, default=10,
                        help="Max BFS depth (default: 10)")
    parser.add_argument("--include-patterns", type=str, default=None,
                        help="Comma-separated URL substrings to include (e.g. '/docs/,/api/')")
    parser.add_argument("--exclude-patterns", type=str, default=None,
                        help="Comma-separated URL substrings to exclude (e.g. '/genindex,/search')")
    parser.add_argument("--append", action="store_true",
                        help="Append to output file instead of overwrite (for continuation runs)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_S,
                        help=f"Render delay in seconds after domcontentloaded (default: {DEFAULT_DELAY_S})")
    parser.add_argument("--page-timeout", type=int, default=DEFAULT_PAGE_TIMEOUT_MS,
                        help=f"Page load timeout in ms (default: {DEFAULT_PAGE_TIMEOUT_MS})")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_DISCOVER_CONCURRENCY,
                        help=f"Concurrent discovery requests (default: {DEFAULT_DISCOVER_CONCURRENCY}; "
                             f">1 risks Cloudflare WAF 429, max recommended: 10)")
    parser.add_argument("--stealth", action="store_true",
                        help="Enable stealth mode (enable_stealth + UndetectedAdapter) to reduce 429s")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(explore_site_workflow(
        args.url, args.max_pages, args.output, args.depth,
        args.include_patterns, args.exclude_patterns, args.append,
        args.delay, args.page_timeout, args.concurrency, args.stealth,
    ))
