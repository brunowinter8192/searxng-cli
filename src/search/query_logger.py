# INFRASTRUCTURE
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Record schema (per-query JSONL line):
# {
#   "ts": str (ISO-8601 UTC),
#   "query": str,
#   "language": str,
#   "engines_requested": [str],
#   "total_wall_ms": int,
#   "bottleneck_engine": str | null,
#   "engines": {
#     "<engine_name>": {
#       "rate_wait_ms": int, "search_ms": int, "result_count": int,
#       "status": str,       # OK | RATE_SKIP
#                            # EMPTY | EMPTY_NO_RESULTS | EMPTY_NO_CONTAINER | EMPTY_CONSENT | EMPTY_BLOCK | EMPTY_CONCURRENT_RACE
#                            # TIMEOUT | TIMEOUT_WATCHDOG | TIMEOUT_NONCOOP | TIMEOUT_HTTPX
#                            # ERROR | ERROR_BROWSER | ERROR_HTTP | ERROR_PARSE | ERROR_OTHER
#       "drop_reason": str | null
#     }
#   },
#   "preview": { "urls_attempted": int, "urls_succeeded": int, "url_timeouts": int, "total_ms": int }
# }
LOG_PATH = Path(__file__).parent.parent.parent / "src" / "logs" / "query_log.jsonl"


# FUNCTIONS

# Append one JSONL record per query; fail-soft on any write error
def log_query(record: dict) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning("query_log write failed: %s", e)
