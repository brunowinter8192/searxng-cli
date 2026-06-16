# INFRASTRUCTURE

import json
from datetime import datetime, timezone
from pathlib import Path

from src.news.engine.proxy_pool.proxy_key import proxy_key


# ORCHESTRATOR

class AcquireLogger:
    """Streams fetch events to JSONL (line-buffered, kill-safe). close() seals the
    stream for janitor.end_job(); all stats derive from the JSONL there.
    """

    def __init__(self, total_urls: int, log_dir: Path):
        self._total      = total_urls
        log_dir.mkdir(parents=True, exist_ok=True)
        ts               = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self._jsonl_path = log_dir / f"acquire_events_{ts}.jsonl"
        self._jsonl_fh   = self._jsonl_path.open("a", encoding="utf-8", buffering=1)

    def record_attempt(self, proto: str, host_port: str, url: str, ok: bool) -> None:
        """Stream one fetch event to JSONL — {proxy_key, ts, url, result}."""
        event = {
            "proxy_key": proxy_key(proto, host_port),
            "ts":        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "url":       url,
            "result":    "ok" if ok else "fail",
        }
        self._jsonl_fh.write(json.dumps(event) + "\n")

    def record_pool_refresh(self, size: int) -> None:
        """Record pool-provider call result → JSONL pool_refresh event (read by janitor)."""
        event = {
            "event": "pool_refresh",
            "size":  size,
            "ts":    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self._jsonl_fh.write(json.dumps(event) + "\n")

    def record_pool_source(self, url: str, ok: bool, count: int) -> None:
        """Record one per-source fetch result → JSONL pool_source event (read by janitor)."""
        event = {
            "event": "pool_source",
            "url":   url,
            "ok":    ok,
            "count": count,
            "ts":    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self._jsonl_fh.write(json.dumps(event) + "\n")

    def close(self) -> None:
        """Close the JSONL stream. Call before janitor.end_job()."""
        self._jsonl_fh.close()
