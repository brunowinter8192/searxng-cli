#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
INPUT_DIR = Path(__file__).parent / "01_output"
OUTPUT_DIR = Path(__file__).parent / "02b_output"


# ORCHESTRATOR
async def scrape_workflow(input_path: Path):
    entries = load_entries(input_path)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Input : {input_path} ({len(entries)} URLs)", file=sys.stderr)
    print(f"Output: {OUTPUT_DIR}", file=sys.stderr)

    browser_config = BrowserConfig(headless=True, verbose=False, user_agent=USER_AGENT)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="networkidle",
        markdown_generator=DefaultMarkdownGenerator(),
        verbose=False,
    )
    run_config_fallback = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="domcontentloaded",
        markdown_generator=DefaultMarkdownGenerator(),
        verbose=False,
    )

    manifest = []
    t_start = time.perf_counter()

    # Fresh AsyncWebCrawler per URL — new Chrome process + clean BrowserContext per fetch.
    # Prevents crawl4ai's contexts_by_config cache from reusing the same Playwright context
    # (and its cookies) across URLs. See browser_manager.py:1662-1675.
    for i, entry in enumerate(entries, 1):
        url = entry["url"]
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
        print(f"[{i}/{len(entries)}] {url}", file=sys.stderr)

        result_entry = scrape_one(entry, url_hash)
        try:
            t0 = time.perf_counter()
            async with AsyncWebCrawler(config=browser_config) as crawler:
                content, wait_strategy = await fetch_with_fallback(
                    crawler, url, run_config, run_config_fallback
                )
            elapsed = time.perf_counter() - t0

            if content:
                status = "ok_fallback" if wait_strategy == "domcontentloaded" else "ok"
                file_path = write_article(entry, url_hash, content)
                result_entry.update({
                    "status": status,
                    "char_count": len(content),
                    "file": str(file_path.relative_to(Path.cwd()) if file_path.is_absolute() else file_path),
                    "elapsed_s": round(elapsed, 2),
                    "wait_strategy": wait_strategy,
                })
                label = "ok_fallback" if status == "ok_fallback" else "ok"
                print(f"  {label} — {len(content):,} chars in {elapsed:.1f}s [{wait_strategy}]", file=sys.stderr)
            else:
                result_entry.update({
                    "status": "empty",
                    "char_count": 0,
                    "elapsed_s": round(elapsed, 2),
                    "wait_strategy": wait_strategy,
                })
                print(f"  empty ({elapsed:.1f}s)", file=sys.stderr)
        except Exception as exc:
            result_entry.update({"status": "failed", "error": str(exc)})
            print(f"  FAILED: {exc}", file=sys.stderr)

        manifest.append(result_entry)
        await asyncio.sleep(1.0)

    write_manifest(manifest)
    print_summary(manifest, time.perf_counter() - t_start)


# FUNCTIONS

# Try networkidle first; fall back to domcontentloaded on empty content or timeout exception.
# Both attempts run inside the same crawler instance (shared browser context).
# Returns (content_str, wait_strategy_used).
async def fetch_with_fallback(crawler, url: str, run_config, run_config_fallback) -> tuple[str, str]:
    content = ""
    try:
        result = await crawler.arun(url=url, config=run_config)
        content = result.markdown.raw_markdown if result.markdown else ""
    except Exception as exc:
        if not _is_timeout(exc):
            raise
        print("  networkidle timeout — trying domcontentloaded", file=sys.stderr)

    if content:
        return content, "networkidle"

    # Empty or timeout: retry with domcontentloaded
    result = await crawler.arun(url=url, config=run_config_fallback)
    content = result.markdown.raw_markdown if result.markdown else ""
    return content, "domcontentloaded"


# Return True if exception is a timeout (by type name or message)
def _is_timeout(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    return "timeout" in name or "timeout" in msg


# Load entries from discover JSON
def load_entries(input_path: Path) -> list[dict]:
    return json.loads(input_path.read_text(encoding="utf-8"))


# Build a base manifest entry for a URL
def scrape_one(entry: dict, url_hash: str) -> dict:
    return {
        "url": entry["url"],
        "hash": url_hash,
        "file": None,
        "char_count": None,
        "status": None,
        "error": None,
        "wait_strategy": None,
    }


# Write YAML-frontmatter article file, return path
def write_article(entry: dict, url_hash: str, content: str) -> Path:
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    frontmatter = (
        "---\n"
        f"url: {entry['url']}\n"
        f"lastmod: {entry['lastmod']}\n"
        f"publication_date: {entry['publication_date']}\n"
        f"title: {entry['title']}\n"
        f"section: {entry['section']}\n"
        f"scraped_at: {scraped_at}\n"
        "---\n\n"
    )
    file_path = OUTPUT_DIR / f"{url_hash}.md"
    file_path.write_text(frontmatter + content, encoding="utf-8")
    return file_path


# Write manifest JSON after all URLs processed
def write_manifest(manifest: list[dict]):
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest: {manifest_path}", file=sys.stderr)


# Print run summary to stdout
def print_summary(manifest: list[dict], total_s: float):
    ok = [e for e in manifest if e["status"] == "ok"]
    ok_fb = [e for e in manifest if e["status"] == "ok_fallback"]
    failed = [e for e in manifest if e["status"] == "failed"]
    empty = [e for e in manifest if e["status"] == "empty"]
    all_ok = ok + ok_fb
    total_chars = sum(e["char_count"] or 0 for e in all_ok)
    slowest = max(all_ok, key=lambda e: e.get("elapsed_s", 0), default=None)

    print(f"\nDone in {total_s:.0f}s")
    print(f"  ok      : {len(ok) + len(ok_fb)} ({len(ok_fb)} via fallback)")
    print(f"  empty   : {len(empty)}")
    print(f"  failed  : {len(failed)}")
    print(f"  total chars: {total_chars:,}")
    if slowest:
        print(f"  slowest : {slowest['url']} ({slowest.get('elapsed_s', '?')}s)")


# Auto-pick newest discover_*.json from 01_output/
def pick_latest_input() -> Path:
    candidates = sorted(INPUT_DIR.glob("discover_*.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"No discover_*.json found in {INPUT_DIR}")
    return candidates[-1]


def main():
    parser = argparse.ArgumentParser(
        description="CoinDesk raw scrape (fresh context) — fresh AsyncWebCrawler per URL, no shared cookie state."
    )
    parser.add_argument(
        "--input", default=None,
        help="Path to discover_*.json (default: newest in 01_output/)"
    )
    args = parser.parse_args()
    input_path = Path(args.input) if args.input else pick_latest_input()
    asyncio.run(scrape_workflow(input_path))


if __name__ == "__main__":
    main()
