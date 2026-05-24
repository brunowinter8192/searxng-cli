# INFRASTRUCTURE
import json
import logging
import os
import re
from pathlib import Path

# From src/log_janitor.py: lazy 14-day prune on write
from src.log_janitor import maybe_prune_jsonl, maybe_prune_sidecars

logger = logging.getLogger(__name__)

DEFAULT_LOG_PATH = Path(__file__).parent.parent.parent / "src" / "logs" / "scrape_log.jsonl"

# Record schema (one record per scrape_url / scrape_url_raw call):
# {
#   "ts": str (ISO-8601 UTC, millisecond precision),
#   "url": str,
#   "domain": str,
#   "mode": "filtered" | "raw",
#   "outcome": "ok" | "garbage" | "empty" | "timeout" | "error",
#   "phase_used": "fastpath" | "browser_1a" | "browser_1b" | "browser_2_stealth" | null,
#   "phases_attempted": [str],
#   "timings_ms": {
#     "fastpath": int | null, "browser_1a": int | null, "browser_1b": int | null,
#     "browser_2_stealth": int | null, "filter": null, "total_wall": int
#   },
#   "http_status": int | null,
#   "content_type": str | null,
#   "bytes_returned": int | null,
#   "bytes_raw_markdown": int | null,
#   "fallback_to_raw": bool | null,      # null for raw mode
#   "truncated": bool | null,             # null for raw mode
#   "consent_stripped": bool | null,      # null for raw mode
#   "garbage_type": str | null,
#   "fastpath_hit": bool,
#   "fastpath_miss_reason": "wrong_content_type" | "sub_threshold" | "http_error" | "network_error" | null,
#   "content_path": str | null            # relative path under log dir, e.g. "scrape_content/<file>.md"
# }
#
# Log path: SEARXNG_SCRAPE_LOG_PATH env var → DEFAULT_LOG_PATH fallback.
# Sidecar path: <log_dir>/scrape_content/<ts_safe>_<url_slug>.md


# FUNCTIONS

# Sanitize ISO timestamp for filesystem: replace `:` with `-`
def _sanitize_ts(ts: str) -> str:
    return ts.replace(":", "-")


# Derive URL slug: strip protocol, replace non-alphanumeric with `-`, collapse runs, cap 80 chars
def _url_slug(url: str) -> str:
    slug = re.sub(r'^https?://', '', url)
    slug = re.sub(r'[^a-zA-Z0-9]', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')[:80]


# Write sidecar .md to <log_dir>/scrape_content/; return relative path or None on empty/error
def write_sidecar(url: str, ts: str, content: str, outcome: str, mode: str) -> str | None:
    if not content:
        return None
    env = os.environ.get("SEARXNG_SCRAPE_LOG_PATH")
    log_path = Path(env) if env else DEFAULT_LOG_PATH
    sidecar_dir = log_path.parent / "scrape_content"
    filename = f"{_sanitize_ts(ts)}_{_url_slug(url)}.md"
    header = (
        f"<!-- url: {url} -->\n"
        f"<!-- ts: {ts} -->\n"
        f"<!-- outcome: {outcome} -->\n"
        f"<!-- bytes: {len(content.encode('utf-8'))} -->\n"
        f"<!-- mode: {mode} -->\n"
    )
    try:
        sidecar_dir.mkdir(parents=True, exist_ok=True)
        (sidecar_dir / filename).write_text(header + "\n" + content, encoding="utf-8")
        maybe_prune_sidecars(sidecar_dir)
        return f"scrape_content/{filename}"
    except Exception as e:
        logger.warning("scrape_logger sidecar write failed: %s", e)
        return None


# Append one JSONL record; path from SEARXNG_SCRAPE_LOG_PATH env var; fail-soft
def log_scrape(record: dict) -> None:
    env = os.environ.get("SEARXNG_SCRAPE_LOG_PATH")
    log_path = Path(env) if env else DEFAULT_LOG_PATH
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        maybe_prune_jsonl(log_path)
    except Exception as e:
        logger.warning("scrape_log write failed: %s", e)
