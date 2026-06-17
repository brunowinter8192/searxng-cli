# INFRASTRUCTURE
import json
import logging
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from src.news.platform import Platform
from src.news.engine.dedup import filter_new_entries
from src.news.engine.scrape import scrape_entries, RegwallGuardError
from src.news.engine.proxy_pool import box_lock
from src.news.engine.proxy_pool.janitor import Janitor
from src.news.engine.proxy_pool.logger import AcquireLogger
from src.news.engine.proxy_pool.scrape import scrape_entries_proxy
from src.news.engine.publish import publish_articles
from src.news.engine.scrape_job import scrape_chunks, run_cleanup

PROJECT_ROOT = Path(__file__).parent.parent.parent   # searxng-cli/

LOG_DIR = PROJECT_ROOT / "src" / "logs"
DATA_ROOT = PROJECT_ROOT / "data" / "news"

COLLECTION_BASE = Path(
    "/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/rag-cli"
    "/data/documents"
)
PRECONDITION_TIMEOUT = 10
SCRAPE_CHUNK_SIZE = 200   # URLs per scrape→clean→publish chunk; controls crash-loss window


# ORCHESTRATOR

# Discover + inventory-update only — no dedup/scrape/clean/publish. CoinDesk standalone job.
async def run_discover_only(platform: Platform) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = _setup_logging(platform.name)
    log.info(f"=== {platform.name} discover-only started ===")
    if not _check_internet(platform, log):
        log.error("Internet check failed — aborting.")
        sys.exit(1)
    entries = await platform.discover()
    log.info(f"discover → {len(entries)} entries")
    _write_marker(platform.name, log)
    log.info(f"=== {platform.name} discover-only complete ===")


# Date-filtered scrape job: inventory → MD-diff → chunked scrape→clean→publish.
# No _clear_working_dirs — published chunks are durable; re-run MD-diff resumes from last chunk.
# RegwallGuardError per chunk: log loudly, stop loop (already-published chunks stay durable).
# Accumulates job_records [{t_chunk_start, ...manifest_entry}] for Stage-2b reporter.
async def run_scrape_only(
    platform: Platform,
    year: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int | None = None,
    skip_index: bool = False,
) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = _setup_logging(platform.name)
    job_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filter_desc = (
        f"year={year}" if year
        else f"from={from_date} to={to_date}" if (from_date or to_date)
        else "all"
    )
    log.info(f"=== {platform.name} scrape-only started job_id={job_id} filter={filter_desc} ===")
    if not _check_preconditions(platform, log):
        log.error("Precondition check failed — aborting.")
        sys.exit(1)
    if not hasattr(platform, "load_scrape_entries"):
        log.error(f"--scrape-only not supported for {platform.name} (no load_scrape_entries)")
        sys.exit(1)

    entries = platform.load_scrape_entries(year=year, from_date=from_date, to_date=to_date, limit=limit)
    log.info(f"inventory → {len(entries)} candidate URL(s) after filter")
    if not entries:
        log.info("No entries in date range — done.")
        _write_marker(platform.name, log)
        return

    collection_dir = COLLECTION_BASE / platform.collection
    new_entries, n_skip = filter_new_entries(entries, collection_dir, platform.name, mode="pubdate")
    log.info(f"dedup → {len(entries)} total, {n_skip} already scraped, {len(new_entries)} new")
    if not new_entries:
        log.info("All already scraped — done.")
        _write_marker(platform.name, log)
        return

    platform_dir = DATA_ROOT / platform.name
    job_scrape_base = platform_dir / "scrape" / job_id
    job_clean_base  = platform_dir / "clean"  / job_id
    collection_dir.mkdir(parents=True, exist_ok=True)
    chunks = [new_entries[i:i + SCRAPE_CHUNK_SIZE] for i in range(0, len(new_entries), SCRAPE_CHUNK_SIZE)]
    log.info(f"chunked plan: {len(new_entries)} URLs → {len(chunks)} chunk(s) of {SCRAPE_CHUNK_SIZE}")

    t_job_start = datetime.now(timezone.utc)
    totals, job_records, regwall_abort = await scrape_chunks(
        chunks, job_scrape_base, job_clean_base, platform, collection_dir, log, skip_index
    )
    for d in (job_scrape_base, job_clean_base):
        if d.exists() and not any(d.iterdir()):
            d.rmdir()

    wall_s = (datetime.now(timezone.utc) - t_job_start).total_seconds()
    rw_rate = totals["regwall"] / max(sum(totals.values()), 1)
    log.info(
        f"=== scrape-only done: ok={totals['ok']} regwall={totals['regwall']}({rw_rate:.1%}) "
        f"empty={totals['empty']} failed={totals['failed']} wall={wall_s:.0f}s"
        + (" [REGWALL ABORT]" if regwall_abort else "") + " ==="
    )
    # Stage-2b hook: write_scrape_report(job_dir, job_records, t_job_start, len(new_entries), filter_desc, skip_index)
    _write_marker(platform.name, log)
    log.info(f"=== {platform.name} scrape-only complete job_id={job_id} ===")


# Run the full news pipeline for the given platform in-process.
async def run_pipeline(platform: Platform, skip_index: bool = False) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = _setup_logging(platform.name)
    log.info(f"=== {platform.name} pipeline started ===")

    if not _check_preconditions(platform, log):
        log.error("Precondition check failed — aborting.")
        sys.exit(1)

    platform_dir = DATA_ROOT / platform.name
    discover_dir = platform_dir / "discover"
    scrape_dir   = platform_dir / "scrape"
    clean_dir    = platform_dir / "clean"
    collection_dir = COLLECTION_BASE / platform.collection

    _clear_working_dirs(scrape_dir, clean_dir, log)
    discover_dir.mkdir(parents=True, exist_ok=True)
    scrape_dir.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)

    if platform.scrape_engine == "proxy_pool":
        # Proxy-pool path: unified job lifecycle spans discover + dedup + scrape.
        # start_job BEFORE AcquireLogger so Janitor wipes log_dir before the JSONL is opened.
        log_dir    = platform_dir / "proxy_pool_logs"
        report_dir = platform_dir / "proxy_pool_reports"
        jobs_dir   = platform_dir / "proxy_pool_jobs"
        job_id     = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        with box_lock.acquire(job_id, f"{platform.name} discover+scrape"):
            j      = Janitor(jobs_dir, log_dir, report_dir)
            j.start_job(job_id)
            logger = AcquireLogger(total_urls=0, log_dir=log_dir)
            new_entries: list[dict] = []
            n_ok = 0
            try:
                # Stage 1 — discover (proxy_pool)
                log.info("STAGE discover …")
                entries = await platform.discover(logger=logger)
                if not entries:
                    log.error("discover returned 0 articles — aborting.")
                    _write_marker(platform.name, log)
                    return
                discover_snapshot = _write_discover_snapshot(entries, discover_dir)
                log.info(f"discover → {len(entries)} articles → {discover_snapshot.name}")

                # Stage 2 — dedup (proxy_pool)
                log.info("STAGE dedup …")
                dedup_mode = getattr(platform, "dedup_mode", "pubdate")
                new_entries, n_skip = filter_new_entries(entries, collection_dir, platform.name, mode=dedup_mode)
                log.info(f"dedup → {len(entries)} total, {n_skip} already indexed, {len(new_entries)} new")
                if not new_entries:
                    log.info("Nothing new to scrape — pipeline complete.")
                    _write_marker(platform.name, log)
                    return

                # Stage 3 — scrape (proxy_pool)
                log.info(f"STAGE scrape ({len(new_entries)} URLs) …")
                manifest = scrape_entries_proxy(new_entries, scrape_dir, platform.proxy_scrape_config, logger)
                n_ok = sum(1 for e in manifest if e["status"] == "ok")
                n_failed = sum(1 for e in manifest if e["status"] == "failed")
                log.info(f"scrape → {n_ok} ok, {n_failed} failed")
                if n_ok == 0:
                    log.warning("scrape produced 0 successful pages — skipping cleanup + publish.")
                    _write_marker(platform.name, log)
                    return

            finally:
                logger.close()
                j.end_job(job_id, logger._jsonl_path, len(new_entries), n_ok)

    else:
        # Browser path: stages 1-3 unchanged
        log.info("STAGE discover …")
        entries = await platform.discover()
        if not entries:
            log.error("discover returned 0 articles — aborting.")
            _write_marker(platform.name, log)
            return
        discover_snapshot = _write_discover_snapshot(entries, discover_dir)
        log.info(f"discover → {len(entries)} articles → {discover_snapshot.name}")

        log.info("STAGE dedup …")
        dedup_mode = getattr(platform, "dedup_mode", "pubdate")
        new_entries, n_skip = filter_new_entries(entries, collection_dir, platform.name, mode=dedup_mode)
        log.info(f"dedup → {len(entries)} total, {n_skip} already indexed, {len(new_entries)} new")
        if not new_entries:
            log.info("Nothing new to scrape — pipeline complete.")
            _write_marker(platform.name, log)
            return

        log.info(f"STAGE scrape ({len(new_entries)} URLs) …")
        try:
            manifest = await scrape_entries(
                new_entries, scrape_dir, platform.regwall_signals, platform.scrape_config
            )
        except RegwallGuardError as exc:
            log.error(f"STAGE scrape aborted — RegwallGuardError: {exc}")
            _write_marker(platform.name, log)
            return

        n_ok = sum(1 for e in manifest if e["status"] == "ok")
        n_failed = sum(1 for e in manifest if e["status"] == "failed")
        log.info(f"scrape → {n_ok} ok, {n_failed} failed")
        if n_ok == 0:
            log.warning("scrape produced 0 successful pages — skipping cleanup + publish.")
            _write_marker(platform.name, log)
            return

    # Stage 4 — cleanup (shared)
    log.info("STAGE cleanup …")
    discover_by_url = {e["url"]: e for e in new_entries}
    clean_manifest = run_cleanup(manifest, scrape_dir, clean_dir, platform, log, discover_by_url)
    log.info(f"cleanup → {len(clean_manifest)} files cleaned")

    # Stage 5 — publish (shared)
    log.info("STAGE publish …")
    n_copied, n_chunks = publish_articles(
        clean_manifest, clean_dir, collection_dir,
        platform.name, platform.collection, skip_index,
    )
    log.info(f"publish → {n_copied} copied, {n_chunks} chunks indexed")

    log.info(f"=== {platform.name} pipeline complete ===")
    _write_marker(platform.name, log)


# FUNCTIONS

# Configure file + stderr logging; return logger
def _setup_logging(name: str) -> logging.Logger:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    log_file = LOG_DIR / f"news_{name}_{today}.log"
    fmt = "[%(asctime)s] %(levelname)s %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )
    log = logging.getLogger(f"news.{name}")
    log.info(f"Log file: {log_file}")
    return log


# Check internet reachability via platform.precondition_url
def _check_internet(platform: Platform, log: logging.Logger) -> bool:
    try:
        with urllib.request.urlopen(platform.precondition_url, timeout=PRECONDITION_TIMEOUT):
            log.info(f"  [OK] Internet reachable ({platform.precondition_url})")
            return True
    except Exception as e:
        log.error(f"  [FAIL] Internet unreachable: {e}")
        return False


# Check (a) internet reachable via platform.precondition_url, (b) rag-cli callable
def _check_preconditions(platform: Platform, log: logging.Logger) -> bool:
    log.info("Checking preconditions …")
    if not _check_internet(platform, log):
        return False

    result = subprocess.run(
        ["rag-cli", "list_collections"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log.error(f"  [FAIL] rag-cli not callable: {result.stderr.strip()}")
        return False
    log.info("  [OK] rag-cli callable")
    return True


# Remove stale scrape + clean files so publish only indexes current-run articles
def _clear_working_dirs(scrape_dir: Path, clean_dir: Path, log: logging.Logger) -> None:
    for d in (scrape_dir, clean_dir):
        if d.exists():
            shutil.rmtree(d)
            log.info(f"Cleared: {d.relative_to(d.parent.parent.parent)}")


# Write discover snapshot JSON; return path
def _write_discover_snapshot(entries: list[dict], discover_dir: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = discover_dir / f"discover_{ts}.json"
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# Write timestamp to last-run marker file
def _write_marker(name: str, log: logging.Logger) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    marker = LOG_DIR / f"news_{name}_last_run.txt"
    marker.write_text(ts + "\n", encoding="utf-8")
    log.info(f"Last run marker: {ts}")
