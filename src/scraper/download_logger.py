# INFRASTRUCTURE
import json
import logging
import os
from pathlib import Path

# From src/log_janitor.py: lazy 14-day prune on write
from src.log_janitor import maybe_prune_jsonl

logger = logging.getLogger(__name__)

DEFAULT_LOG_PATH = Path(__file__).parent.parent.parent / "src" / "logs" / "download_log.jsonl"

# Record schema (one record per download_pdf_workflow call):
# {
#   "ts": str (ISO-8601 UTC, millisecond precision),
#   "url": str,
#   "domain": str,
#   "output_dir": str,
#   "output_path": str | null,
#   "outcome": "ok" | "blacklisted" | "github_blob" | "no_pdf_path" | "http_error" | "network_error" | "io_error",
#   "chain_resolution": "tier1" | "direct" | "multi_step" | null,
#   "chain_attempted": [str],
#   "final_pdf_url": str | null,
#   "http_status": int | null,
#   "content_type": str | null,
#   "bytes_downloaded": int | null,
#   "timings_ms": {
#     "blacklist_check": int | null, "github_blob_check": int | null,
#     "tier1_transform": int | null, "direct_pdf_check": int | null,
#     "citation_pdf_url_hop1": int | null, "download": int | null,
#     "total_wall": int
#   },
#   "error_message": str | null
# }
#
# Log path: SEARXNG_DOWNLOAD_LOG_PATH env var → DEFAULT_LOG_PATH fallback.


# FUNCTIONS

# Append one JSONL record; path from SEARXNG_DOWNLOAD_LOG_PATH env var; fail-soft
def log_download(record: dict) -> None:
    env = os.environ.get("SEARXNG_DOWNLOAD_LOG_PATH")
    log_path = Path(env) if env else DEFAULT_LOG_PATH
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        maybe_prune_jsonl(log_path)
    except Exception as e:
        logger.warning("download_log write failed: %s", e)
