# INFRASTRUCTURE
import argparse
import asyncio
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

DELAY_S = 0.5
PAGE_TIMEOUT_MS = 15000
CONCURRENCY = 5
BATCH_SIZE = 30
INTER_BATCH_SLEEP_S = 30.0
EMPTY_THRESHOLD_BYTES = 100

# ORCHESTRATOR

# Scrape URL list in batches, write per-URL md files + /tmp report. Prints short summary.
async def scrape_urls_workflow(
    urls: list[str],
    output_dir: Path,
    batch_size: int = BATCH_SIZE,
    inter_batch_sleep_s: float = INTER_BATCH_SLEEP_S,
) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    batches = [urls[i:i + batch_size] for i in range(0, len(urls), batch_size)]

    t0 = time.time()
    all_results: list[dict] = []
    for idx, batch in enumerate(batches):
        results = await _scrape_batch(batch, output_dir)
        all_results.extend(results)
        if idx < len(batches) - 1:
            await asyncio.sleep(inter_batch_sleep_s)

    wall_s = time.time() - t0
    _print_summary(all_results, wall_s)
    _write_tmp_report(_domain_from_urls(urls), all_results)
    return all_results


# FUNCTIONS

# Derive safe filename from URL
def _url_to_filename(url: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9]', '_', url.split('://')[-1])
    slug = re.sub(r'_+', '_', slug).strip('_')[:100]
    return f"{slug}.md"

# Scrape one URL inside an open crawler, return metrics dict
async def _scrape_one(
    crawler: AsyncWebCrawler,
    url: str,
    run_cfg: CrawlerRunConfig,
    sem: asyncio.Semaphore,
    output_dir: Path,
) -> dict:
    async with sem:
        t0 = time.time()
        try:
            result = await crawler.arun(url=url, config=run_cfg)
        except Exception:
            return {'url': url, 'wall_ms': int((time.time() - t0) * 1000),
                    'bytes': 0, 'status_code': None, 'outcome': 'error'}
        wall_ms = int((time.time() - t0) * 1000)

    raw_md = (result.markdown.raw_markdown if result.markdown else '') or ''
    status = getattr(result, 'status_code', None)
    byte_count = len(raw_md.encode('utf-8'))

    if status == 429:
        outcome = 'waf_429'
    elif status and status >= 400:
        outcome = 'http_error'
    elif byte_count < EMPTY_THRESHOLD_BYTES:
        outcome = 'empty'
    else:
        outcome = 'ok'

    if raw_md:
        fname = _url_to_filename(url)
        (output_dir / fname).write_text(f"<!-- source: {url} -->\n\n{raw_md}", encoding='utf-8')

    return {'url': url, 'wall_ms': wall_ms, 'bytes': byte_count,
            'status_code': status, 'outcome': outcome}

# Scrape one batch of URLs at configured concurrency
async def _scrape_batch(urls: list[str], output_dir: Path) -> list[dict]:
    browser_cfg = BrowserConfig(headless=True, verbose=False)
    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="domcontentloaded",
        delay_before_return_html=DELAY_S,
        page_timeout=PAGE_TIMEOUT_MS,
        markdown_generator=DefaultMarkdownGenerator(),
        verbose=False,
    )
    sem = asyncio.Semaphore(CONCURRENCY)
    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        raw = await asyncio.gather(
            *[_scrape_one(crawler, url, run_cfg, sem, output_dir) for url in urls],
            return_exceptions=True,
        )
    return [
        r if isinstance(r, dict)
        else {'url': urls[i], 'outcome': 'error', 'wall_ms': 0, 'bytes': 0, 'status_code': None}
        for i, r in enumerate(raw)
    ]

# Extract domain string from first URL (used for /tmp report filename)
def _domain_from_urls(urls: list[str]) -> str:
    if not urls:
        return 'unknown'
    return urlparse(urls[0]).netloc.replace('.', '_')

# Write per-URL report to /tmp/<domain>_scrape_report.md
def _write_tmp_report(domain: str, results: list[dict]) -> None:
    path = Path(f"/tmp/{domain}_scrape_report.md")
    lines = [
        f"# Scrape Report — {domain}",
        "",
        f"Total: {len(results)} URLs",
        "",
        "| outcome | status | bytes | wall_ms | url |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['outcome']} | {r.get('status_code') or '-'} | "
            f"{r['bytes']} | {r['wall_ms']} | {r['url']} |"
        )
    path.write_text('\n'.join(lines), encoding='utf-8')

# Print one-line console summary
def _print_summary(results: list[dict], wall_s: float) -> None:
    ok = sum(1 for r in results if r['outcome'] == 'ok')
    total = len(results)
    err = total - ok
    print(f"Scraped {ok}/{total} ok, {err} errors in {wall_s:.0f}s")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Pipe scraper — batch-crawl URL list to markdown')
    parser.add_argument('--url-file', required=True, help='Text file with URLs (one per line)')
    parser.add_argument('--output-dir', required=True, help='Directory to write per-URL markdown files')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE,
                        help=f'URLs per batch (default: {BATCH_SIZE})')
    parser.add_argument('--inter-batch-sleep', type=float, default=INTER_BATCH_SLEEP_S,
                        help=f'Seconds to pause between batches (default: {INTER_BATCH_SLEEP_S})')
    args = parser.parse_args()

    urls = [ln.strip() for ln in Path(args.url_file).read_text(encoding='utf-8').splitlines()
            if ln.strip()]
    asyncio.run(scrape_urls_workflow(
        urls, Path(args.output_dir), args.batch_size, args.inter_batch_sleep,
    ))
