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
from src.news.engine.publish import publish_articles

PROJECT_ROOT = Path(__file__).parent.parent.parent   # searxng-cli/
LOG_DIR = PROJECT_ROOT / "src" / "logs"
DATA_ROOT = PROJECT_ROOT / "data" / "news"

COLLECTION_BASE = Path(
    "/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/rag-cli"
    "/data/documents"
)
PRECONDITION_TIMEOUT = 10


# ORCHESTRATOR

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

    # Stage 1 — discover
    log.info("STAGE discover …")
    entries = await platform.discover()
    if not entries:
        log.error("discover returned 0 articles — aborting.")
        _write_marker(platform.name, log)
        return
    discover_snapshot = _write_discover_snapshot(entries, discover_dir)
    log.info(f"discover → {len(entries)} articles → {discover_snapshot.name}")

    # Stage 2 — dedup
    log.info("STAGE dedup …")
    new_entries, n_skip = filter_new_entries(entries, collection_dir, platform.name)
    log.info(f"dedup → {len(entries)} total, {n_skip} already indexed, {len(new_entries)} new")
    if not new_entries:
        log.info("Nothing new to scrape — pipeline complete.")
        _write_marker(platform.name, log)
        return

    # Stage 3 — scrape
    log.info(f"STAGE scrape ({len(new_entries)} URLs) …")
    try:
        if platform.scrape_engine == "proxy_pool":
            raise NotImplementedError("proxy_pool engine not yet wired — complete A3")
        else:
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

    # Stage 4 — cleanup (in-process)
    log.info("STAGE cleanup …")
    discover_by_url = {e["url"]: e for e in new_entries}
    clean_manifest = _run_cleanup(manifest, scrape_dir, clean_dir, platform, log, discover_by_url)
    log.info(f"cleanup → {len(clean_manifest)} files cleaned")

    # Stage 5 — publish
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


# Check (a) internet reachable via platform.precondition_url, (b) rag-cli callable
def _check_preconditions(platform: Platform, log: logging.Logger) -> bool:
    log.info("Checking preconditions …")
    try:
        with urllib.request.urlopen(platform.precondition_url, timeout=PRECONDITION_TIMEOUT):
            log.info(f"  [OK] Internet reachable ({platform.precondition_url})")
    except Exception as e:
        log.error(f"  [FAIL] Internet unreachable: {e}")
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


# In-process cleanup: read body from scrape_dir, apply platform.cleanup, write pure content to clean_dir.
# publication_date is sourced from discover_by_url (discover entries carry it; scrape manifest does not).
# pub_date_str() in publish.py provides a URL-path fallback as a secondary net.
def _run_cleanup(
    manifest: list[dict],
    scrape_dir: Path,
    clean_dir: Path,
    platform: Platform,
    log: logging.Logger,
    discover_by_url: dict[str, dict],
) -> list[dict]:
    clean_manifest = []
    for entry in manifest:
        if entry.get("status") != "ok":
            continue
        h = entry["hash"]
        src_file = scrape_dir / f"{h}.md"
        if not src_file.exists():
            log.warning(f"cleanup: source not found: {src_file.name}")
            continue
        raw_body = src_file.read_text(encoding="utf-8")
        cleaned = platform.cleanup(raw_body, entry)
        dest = clean_dir / f"{h}.md"
        dest.write_text(cleaned, encoding="utf-8")
        discover_entry = discover_by_url.get(entry["url"], {})
        clean_manifest.append({
            "url": entry["url"],
            "hash": h,
            "publication_date": discover_entry.get("publication_date", ""),
        })
    return clean_manifest


# Write timestamp to last-run marker file
def _write_marker(name: str, log: logging.Logger) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    marker = LOG_DIR / f"news_{name}_last_run.txt"
    marker.write_text(ts + "\n", encoding="utf-8")
    log.info(f"Last run marker: {ts}")
