# INFRASTRUCTURE

import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
from proxy_status_log import proxy_key


# ORCHESTRATOR

class AcquireLogger:
    """Streams events to JSONL on every attempt; in-memory only for small counters.

    JSONL is written incrementally (line-buffered) so a kill at any point leaves
    all recorded events on disk. finalize() closes the stream and writes the MD
    summary; all surfaces including throughput-over-time derive from the JSONL.
    """

    def __init__(self, total_urls: int, log_dir: Path):
        self._total    = total_urls
        self._t0       = time.monotonic()

        # Surface 1 — progress (in-memory scalars, small)
        self._done     = 0
        self._attempts = 0

        # Surface 2 — B-per-proxy distribution (in-memory, max ~pool-size entries)
        self._b_dist: list[int] = []

        # Surface 3 — working-set snapshots (in-memory, one per batch)
        self._ws_snapshots: list[tuple[float, int]] = []

        # Surface 4 — derived from _done/_attempts at finalize

        # Surface 5+6 — streamed to JSONL immediately on each record_attempt()
        self._proxy_successes: dict[str, int] = {}   # proxy_key → running ok count
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self._ts         = ts
        self._jsonl_path = log_dir / f"acquire_events_{ts}.jsonl"
        self._jsonl_fh   = self._jsonl_path.open("a", encoding="utf-8", buffering=1)

    def record_attempt(self, proto: str, host_port: str, url: str, ok: bool) -> None:
        """Stream one fetch event to JSONL — drives surfaces 1, 4, 5, 6."""
        self._attempts += 1
        key = proxy_key(proto, host_port)
        if ok:
            self._done += 1
            self._proxy_successes[key] = self._proxy_successes.get(key, 0) + 1
        event = {
            "proxy_key":           key,
            "ts":                  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "url":                 url,
            "result":              "ok" if ok else "fail",
            "proxy_success_count": self._proxy_successes.get(key, 0),
        }
        self._jsonl_fh.write(json.dumps(event) + "\n")

    def record_burn(self, proto: str, host_port: str, b_count: int) -> None:
        """Record proxy retirement — drives surface 2 (B-per-proxy distribution)."""
        self._b_dist.append(b_count)

    def record_working_set(self, eligible_count: int) -> None:
        """Snapshot eligible-candidate count — drives surface 3."""
        self._ws_snapshots.append((time.monotonic() - self._t0, eligible_count))

    def record_pool_refresh(self, size: int) -> None:
        """Record pool-provider call result (size) → JSONL pool_refresh event."""
        event = {
            "event": "pool_refresh",
            "size":  size,
            "ts":    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self._jsonl_fh.write(json.dumps(event) + "\n")

    def close(self) -> None:
        """Close the JSONL stream without writing per-run MD. Use before janitor.end_job()."""
        self._jsonl_fh.close()

    def finalize(self, report_dir: Path) -> Path:
        """Close JSONL stream; write MD summary from in-memory counters + JSONL. Return MD path."""
        self._jsonl_fh.close()
        report_dir.mkdir(parents=True, exist_ok=True)
        buckets  = _throughput_buckets(self._jsonl_path)
        md_path  = _write_summary(report_dir, self._ts, self, buckets)
        return md_path


# FUNCTIONS

# Derive per-minute ok-fetch counts from JSONL; t0 = min ts across all events
def _throughput_buckets(jsonl_path: Path) -> dict[int, int]:
    events: list[dict] = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    if not events:
        return {}
    t0 = min(
        datetime.strptime(e["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        for e in events
    )
    buckets: dict[int, int] = {}
    for e in events:
        if e.get("result") != "ok":
            continue
        ts  = datetime.strptime(e["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        minute = int((ts - t0).total_seconds() // 60)
        buckets[minute] = buckets.get(minute, 0) + 1
    return buckets


# Write MD summary covering all 6 surfaces; return path
def _write_summary(report_dir: Path, ts: str, lg: AcquireLogger, buckets: dict[int, int]) -> Path:
    elapsed    = time.monotonic() - lg._t0
    done       = lg._done
    total      = lg._total
    attempts   = lg._attempts
    fails      = attempts - done
    rate_pct   = done / total * 100 if total else 0.0
    fetch_rate = done / elapsed * 60 if elapsed else 0.0

    lines = [
        f"# Acquire-pipe run — {ts}",
        "",
        "## Surface 1 — Fetch progress",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Target URLs | {total} |",
        f"| Completed | {done} ({rate_pct:.1f}%) |",
        f"| Total attempts | {attempts} |",
        f"| Elapsed | {elapsed:.0f}s |",
        f"| Fetch rate | {fetch_rate:.1f} URLs/min |",
        "",
        "## Surface 2 — B-per-proxy distribution (requests before burn)",
        "",
    ]

    if lg._b_dist:
        b_counter = Counter(lg._b_dist)
        lines += [
            "| B (requests) | Count |",
            "|---|---|",
        ]
        for b in sorted(b_counter):
            lines.append(f"| {b} | {b_counter[b]} |")
        lines += [
            "",
            f"- Proxies retired: {len(lg._b_dist)}",
            f"- Mean B: {sum(lg._b_dist)/len(lg._b_dist):.2f}",
            f"- Max B: {max(lg._b_dist)}",
        ]
    else:
        lines.append("No proxy retirements recorded.")

    lines += [
        "",
        "## Surface 3 — Working-set size over time",
        "",
    ]
    if lg._ws_snapshots:
        lines += [
            "| Elapsed (s) | Eligible candidates |",
            "|---|---|",
        ]
        for elapsed_s, count in lg._ws_snapshots:
            lines.append(f"| {elapsed_s:.0f} | {count} |")
    else:
        lines.append("No working-set snapshots recorded.")

    lines += [
        "",
        "## Surface 4 — Failed attempts per successful fetch",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Successful fetches | {done} |",
        f"| Failed attempts | {fails} |",
        (f"| Ratio (fails/success) | {fails/done:.2f} |" if done else "| Ratio | — (no successes) |"),
        "",
        "## Surface 5 — Per-proxy event log",
        "",
        f"JSONL: `{lg._jsonl_path}`",
        f"Events recorded: {attempts}",
        "",
        "## Surface 6 — Throughput over time (ok fetches per minute)",
        "",
    ]

    if buckets:
        lines += [
            "| Minute | OK fetches |",
            "|---|---|",
        ]
        for minute in sorted(buckets):
            lines.append(f"| {minute} | {buckets[minute]} |")
        total_ok  = sum(buckets.values())
        max_min   = max(buckets, key=buckets.get)
        lines += [
            "",
            f"- Peak minute: {max_min} ({buckets[max_min]} ok)",
            f"- Total ok from JSONL: {total_ok}",
        ]
    else:
        lines.append("No ok events recorded.")

    path = report_dir / f"acquire_run_{ts}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
