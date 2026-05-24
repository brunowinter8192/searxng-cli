#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Ensure src.* imports resolve regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging

# Central logging config — FileHandler only, no StreamHandler.
# Placed before src.* imports: module-load-time log calls route to file, not stderr.
# basicConfig with explicit handlers= never installs the default StreamHandler.
_log_path = Path(__file__).parent / "src" / "logs" / "cli.log"
_log_path.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
    handlers=[logging.FileHandler(_log_path, mode="a", encoding="utf-8")],
)
logger = logging.getLogger(__name__)

import argparse
import asyncio
import atexit
from urllib.parse import urlparse

from src.routing import check_plugin_routed
from src.search.search_web import search_web_workflow, search_batch_workflow
from src.search.browser import close_browser, kill_stale_chrome
from src.search.cache import cache_key, cache_read, format_engine_pool
from src.scraper.scrape_url import scrape_url_workflow
from src.scraper.scrape_url_raw import scrape_url_raw_workflow
from src.crawler.explore_site import explore_site_workflow
from src.scraper.download_pdf import download_pdf_workflow
from src.scraper.pdf_chain import should_download_as_pdf
from mcp.types import TextContent

atexit.register(kill_stale_chrome)


def main():
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="SearXNG Web Research CLI — search, scrape, explore, download PDF."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # ── search_web ────────────────────────────────────────────────────────────
    p = sub.add_parser(
        "search_web",
        help="Search across 9 engines. Returns engine breakdown table — use search_engine_drilldown to see URLs per engine."
    )
    p.add_argument("query", help="Search query (2-5 keywords)")
    p.add_argument("--language", default="en", help="ISO language code (e.g. 'de')")
    p.add_argument("--time-range", dest="time_range", choices=["day", "month", "year"], default=None)
    p.add_argument("--engines", default=None,
                   help="Comma-separated engine list (e.g. 'google,duckduckgo,openalex')")
    mode_sw = p.add_mutually_exclusive_group()
    mode_sw.add_argument("--books", action="store_true",
                   help="Restrict to book-domain whitelist (+book modifier). Mutually exclusive with --pdf / --docs")
    mode_sw.add_argument("--pdf", action="store_true",
                   help="Restrict to PDF-domain whitelist (+pdf modifier). Mutually exclusive with --books / --docs")
    mode_sw.add_argument("--docs", action="store_true",
                   help="Noise-blacklist filter (+documentation modifier). Mutually exclusive with --books / --pdf")

    # ── search_batch ──────────────────────────────────────────────────────────
    p = sub.add_parser(
        "search_batch",
        help="Search multiple queries in one warm-Chrome session. Returns engine breakdown per query."
    )
    p.add_argument("queries", nargs="+", help="One or more search queries")
    p.add_argument("--language", default="en", help="ISO language code (e.g. 'de')")
    p.add_argument("--time-range", dest="time_range", choices=["day", "month", "year"], default=None)
    p.add_argument("--engines", default=None,
                   help="Comma-separated engine list (e.g. 'google,duckduckgo')")
    mode_sb = p.add_mutually_exclusive_group()
    mode_sb.add_argument("--books", action="store_true",
                   help="Restrict to book-domain whitelist (+book modifier). Mutually exclusive with --pdf / --docs")
    mode_sb.add_argument("--pdf", action="store_true",
                   help="Restrict to PDF-domain whitelist (+pdf modifier). Mutually exclusive with --books / --docs")
    mode_sb.add_argument("--docs", action="store_true",
                   help="Noise-blacklist filter (+documentation modifier). Mutually exclusive with --books / --pdf")

    # ── search_engine_drilldown ───────────────────────────────────────────────
    p = sub.add_parser(
        "search_engine_drilldown",
        help="Show URL list for a specific engine from cached search results (or re-runs search on cache miss)."
    )
    p.add_argument("query", help="Search query (must match a prior search_web call)")
    p.add_argument("--engine", required=True,
                   help="Engine name: google, duckduckgo, mojeek, lobsters, semantic_scholar, "
                        "openalex, crossref, stack_exchange, open_library")
    p.add_argument("--language", default="en")
    p.add_argument("--engines", default=None,
                   help="Must match original search_web call (part of cache key)")
    p.add_argument("--time-range", dest="time_range", choices=["day", "month", "year"], default=None)
    mode_edd = p.add_mutually_exclusive_group()
    mode_edd.add_argument("--books", action="store_true",
                   help="Must match original search_web call (part of cache key)")
    mode_edd.add_argument("--pdf", action="store_true",
                   help="Must match original search_web call (part of cache key)")
    mode_edd.add_argument("--docs", action="store_true",
                   help="Must match original search_web call (part of cache key)")

    # ── scrape_url ────────────────────────────────────────────────────────────
    p = sub.add_parser("scrape_url", help="Scrape URL to filtered markdown (PruningContentFilter).")
    p.add_argument("url", help="URL to scrape")
    p.add_argument("--max-content-length", dest="max_content_length", type=int, default=15000)

    # ── scrape_url_raw ────────────────────────────────────────────────────────
    p = sub.add_parser("scrape_url_raw", help="Scrape URL to raw markdown file (for RAG indexing).")
    p.add_argument("url", help="URL to scrape")
    p.add_argument("output_dir", help="Directory to save the .md file (created if not exists)")

    # ── explore_site ──────────────────────────────────────────────────────────
    p = sub.add_parser("explore_site", help="Discover URLs via sitemap + BFS, write to file + print summary.")
    p.add_argument("url", help="Root URL to explore")
    p.add_argument("--strategy", choices=["auto", "sitemap", "prefetch"], default="auto")
    p.add_argument("--max-pages", dest="max_pages", type=int, default=200)
    p.add_argument("--output", type=str, default=None,
                   help="Output file path (default: /tmp/explore_<domain>_urls.txt)")
    p.add_argument("--depth", type=int, default=10)
    p.add_argument("--include-patterns", dest="include_patterns", type=str, default=None)
    p.add_argument("--exclude-patterns", dest="exclude_patterns", type=str, default=None)
    p.add_argument("--append", action="store_true")

    # ── download_pdf ──────────────────────────────────────────────────────────
    p = sub.add_parser("download_pdf", help="Download PDF file from URL.")
    p.add_argument("url", help="URL of the PDF to download")
    p.add_argument("--output-dir", dest="output_dir", default=str(Path.home() / "Downloads"),
                   help="Directory to save the PDF (default: ~/Downloads)")

    # ── Dispatch ──────────────────────────────────────────────────────────────
    args = parser.parse_args()

    if args.cmd == "search_web":
        result = asyncio.run(search_web_workflow(
            args.query, args.language, args.time_range, args.engines,
            books=args.books, pdf=args.pdf, docs=args.docs,
        ))

    elif args.cmd == "search_batch":
        results = asyncio.run(search_batch_workflow(
            args.queries, args.language, args.time_range, args.engines,
            books=args.books, pdf=args.pdf, docs=args.docs,
        ))
        print("\n---\n".join(r[0].text for r in results))
        return

    elif args.cmd == "search_engine_drilldown":
        mode = "books" if args.books else ("pdf" if args.pdf else ("docs" if args.docs else None))
        key = cache_key(args.query, args.language, args.engines, args.time_range, modifier_id=mode)
        hit = cache_read(key)
        if hit is None:
            asyncio.run(search_web_workflow(
                args.query, args.language, args.time_range, args.engines,
                books=args.books, pdf=args.pdf, docs=args.docs,
            ))
            hit = cache_read(key)
        if hit is None:
            print(f'# search_engine_drilldown: cache write failed for "{args.query}"')
            return
        pools = hit.get("pools", {})
        if args.engine not in pools:
            avail = ", ".join(sorted(pools.keys())) or "(none)"
            print(f"Engine '{args.engine}' not in cached pools. Available: {avail}")
            return
        print(format_engine_pool(pools[args.engine], args.engine, args.query))
        return

    elif args.cmd == "scrape_url":
        if should_download_as_pdf(args.url):
            result = download_pdf_workflow(args.url, str(Path.home() / "Downloads"))
        elif blocked := check_plugin_routed(args.url):
            result = blocked
        else:
            result = asyncio.run(scrape_url_workflow(args.url, args.max_content_length))

    elif args.cmd == "scrape_url_raw":
        if should_download_as_pdf(args.url):
            result = download_pdf_workflow(args.url, str(Path.home() / "Downloads"))
        elif blocked := check_plugin_routed(args.url):
            result = blocked
        else:
            result = asyncio.run(scrape_url_raw_workflow(args.url, args.output_dir))

    elif args.cmd == "explore_site":
        urls, strategy_used, output_path = asyncio.run(explore_site_workflow(
            args.url, args.strategy, args.max_pages, args.output,
            args.depth, args.include_patterns, args.exclude_patterns, args.append
        ))
        domain = urlparse(args.url).netloc
        logger.info("explore_site complete: strategy=%s domain=%s urls=%d output=%s",
                    strategy_used, domain, len(urls), output_path)
        result = [TextContent(type="text", text=f"Discovered {len(urls)} URLs → {output_path}")]

    elif args.cmd == "download_pdf":
        result = download_pdf_workflow(args.url, args.output_dir)

    else:
        parser.error(f"Unknown command: {args.cmd}")

    print(result[0].text)


if __name__ == "__main__":
    main()
