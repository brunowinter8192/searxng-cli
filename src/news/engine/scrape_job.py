# INFRASTRUCTURE
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.news.platform import Platform
from src.news.engine.scrape import scrape_entries, RegwallGuardError
from src.news.engine.publish import publish_articles


# ORCHESTRATOR

# Process all scrape chunks: scrape→clean→publish per chunk, wipe ephemeral dirs after each.
# Crash-safety: each chunk is published before moving to the next; re-run MD-diff skips done articles.
# RegwallGuardError per chunk: log loudly + stop loop; already-published chunks stay durable.
# Returns (totals_dict, job_records, regwall_abort).
# job_records: [{t_chunk_start: datetime, ...manifest_entry}] — consumed by Stage-2b reporter.
async def scrape_chunks(
    chunks: list[list[dict]],
    job_scrape_base: Path,
    job_clean_base: Path,
    platform: Platform,
    collection_dir: Path,
    log: logging.Logger,
    skip_index: bool,
) -> tuple[dict, list[dict], bool]:
    totals = {"ok": 0, "regwall": 0, "empty": 0, "failed": 0}
    job_records: list[dict] = []
    regwall_abort = False
    for ci, chunk in enumerate(chunks):
        log.info(f"CHUNK {ci + 1}/{len(chunks)}: {len(chunk)} URLs …")
        chunk_scrape_dir = job_scrape_base / f"chunk_{ci:05d}"
        chunk_clean_dir  = job_clean_base  / f"chunk_{ci:05d}"
        chunk_scrape_dir.mkdir(parents=True, exist_ok=True)
        chunk_clean_dir.mkdir(parents=True, exist_ok=True)
        t_chunk_start = datetime.now(timezone.utc)
        manifest: list[dict] = []
        try:
            manifest = await scrape_entries(
                chunk, chunk_scrape_dir, platform.regwall_signals, platform.scrape_config
            )
        except RegwallGuardError as exc:
            n_rw = sum(1 for e in manifest if e["status"] == "regwall")
            log.error(
                f"RegwallGuardError chunk {ci + 1}: {exc} "
                f"(regwall rate {n_rw / max(len(chunk), 1):.1%} — stopping loop)"
            )
            regwall_abort = True
            shutil.rmtree(chunk_scrape_dir, ignore_errors=True)
            shutil.rmtree(chunk_clean_dir, ignore_errors=True)
            break
        counts = {s: sum(1 for e in manifest if e["status"] == s) for s in totals}
        for s, n in counts.items():
            totals[s] += n
        for e in manifest:
            job_records.append({"t_chunk_start": t_chunk_start, **e})
        discover_by_url = {e["url"]: e for e in chunk}
        chunk_clean = run_cleanup(manifest, chunk_scrape_dir, chunk_clean_dir, platform, log, discover_by_url)
        n_copied, _ = publish_articles(
            chunk_clean, chunk_clean_dir, collection_dir,
            platform.name, platform.collection, skip_index,
        )
        log.info(
            f"  chunk {ci + 1}: ok={counts['ok']} regwall={counts['regwall']}"
            f"({counts['regwall'] / max(len(chunk), 1):.0%}) "
            f"empty={counts['empty']} failed={counts['failed']} published={n_copied}"
        )
        shutil.rmtree(chunk_scrape_dir, ignore_errors=True)
        shutil.rmtree(chunk_clean_dir, ignore_errors=True)
    return totals, job_records, regwall_abort


# Raw-only chunked scrape: scrape directly into raw_dir, persist manifest.jsonl + blocked URL lists.
# No cleanup, no publish. Dedup on raw-file existence handled by caller before chunking.
# RegwallGuardError: ok files already written to raw_dir; recover via dir-scan, set regwall_abort, stop.
async def scrape_chunks_raw(
    chunks: list[list[dict]],
    raw_dir: Path,
    platform: "Platform",
    log: logging.Logger,
) -> tuple[dict, list[dict], bool]:
    totals = {"ok": 0, "regwall": 0, "empty": 0, "failed": 0}
    job_records: list[dict] = []
    regwall_abort = False
    raw_dir.mkdir(parents=True, exist_ok=True)
    for ci, chunk in enumerate(chunks):
        log.info(f"CHUNK {ci + 1}/{len(chunks)}: {len(chunk)} URLs …")
        t_chunk_start = datetime.now(timezone.utc)
        manifest: list[dict] = []
        aborted = False
        try:
            manifest = await scrape_entries(
                chunk, raw_dir, platform.regwall_signals, platform.scrape_config
            )
        except RegwallGuardError as exc:
            manifest = exc.manifest  # full manifest carried on exception; ok files already on disk
            n_rw = sum(1 for e in manifest if e.get("status") == "regwall")
            log.error(
                f"RegwallGuardError chunk {ci + 1}: {exc} "
                f"(regwall rate {n_rw / max(len(chunk), 1):.1%} — stopping loop)"
            )
            regwall_abort = True
            aborted = True

        counts = {s: sum(1 for e in manifest if e.get("status") == s) for s in totals}
        for s, n in counts.items():
            totals[s] += n
        for e in manifest:
            job_records.append({"t_chunk_start": t_chunk_start, **e})

        entries_by_url = {e["url"]: e for e in chunk}
        ok_manifest_entries = [
            {
                "hash": e["hash"],
                "url": e["url"],
                "publication_date": entries_by_url.get(e["url"], {}).get("publication_date", ""),
            }
            for e in manifest if e.get("status") == "ok"
        ]
        _append_to_raw_manifest(raw_dir, ok_manifest_entries)
        _update_blocked_urls(raw_dir, manifest, {"regwall": "regwall_urls.txt", "empty": "empty_urls.txt"})

        log.info(
            f"  chunk {ci + 1}: ok={counts['ok']} "
            f"regwall={counts['regwall']}({counts['regwall'] / max(len(chunk), 1):.0%}) "
            f"empty={counts['empty']} failed={counts['failed']}"
        )
        if aborted:
            break
    return totals, job_records, regwall_abort


# FUNCTIONS

# Append one JSONL line per ok entry to raw_dir/manifest.jsonl.
# Format: {hash, url, publication_date}. Append-only; caller ensures entries are deduplicated.
def _append_to_raw_manifest(raw_dir: Path, ok_entries: list[dict]) -> None:
    if not ok_entries:
        return
    manifest_path = raw_dir / "manifest.jsonl"
    with open(manifest_path, "a", encoding="utf-8") as f:
        for entry in ok_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# Read each blocked-URL file, union with new URLs from manifest, write back sorted.
# status_filenames: {manifest_status_value: filename}, e.g. {"regwall": "regwall_urls.txt"}.
def _update_blocked_urls(raw_dir: Path, manifest: list[dict], status_filenames: dict[str, str]) -> None:
    for status, filename in status_filenames.items():
        new_urls = {e["url"] for e in manifest if e.get("status") == status}
        if not new_urls:
            continue
        path = raw_dir / filename
        existing = set(path.read_text(encoding="utf-8").splitlines()) if path.exists() else set()
        merged = (existing | new_urls) - {""}
        path.write_text("\n".join(sorted(merged)) + "\n", encoding="utf-8")


# Read scraped body from scrape_dir, apply platform.cleanup, write pure content to clean_dir.
# publication_date: primary source is discover_by_url; fallback to entry (scrape manifest) for platforms
# where cleanup mutates entry["publication_date"] from fetched content (e.g. The Block JSON-LD).
# pub_date_str() in publish.py provides a URL-path fallback as a tertiary net.
def run_cleanup(
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
            "publication_date": discover_entry.get("publication_date") or entry.get("publication_date", ""),
        })
    return clean_manifest
