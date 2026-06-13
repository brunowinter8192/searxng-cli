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
    """Accumulates all 5 logging surfaces; no I/O until finalize()."""

    def __init__(self, total_urls: int, log_dir: Path):
        self._total     = total_urls
        self._log_dir   = log_dir
        self._t0        = time.monotonic()

        # Surface 1 — progress
        self._done      = 0   # target URLs completed (ok fetches)
        self._attempts  = 0   # total fetch attempts

        # Surface 2 — B-per-proxy distribution (requests-before-burn)
        self._b_dist: list[int] = []

        # Surface 3 — working-set snapshots: [(elapsed_s, eligible_count)]
        self._ws_snapshots: list[tuple[float, int]] = []

        # Surface 4 — failed attempts per success (derived from 1 at finalize)
        # stored inline: _attempts - _done = total fails

        # Surface 5 — per-proxy event log
        self._proxy_successes: dict[str, int] = {}   # proxy_key → running ok count
        self._events: list[dict] = []

    def record_attempt(self, proto: str, host_port: str, url: str, ok: bool) -> None:
        """Record one fetch attempt — drives surfaces 1, 4, 5."""
        self._attempts += 1
        key = proxy_key(proto, host_port)
        if ok:
            self._done += 1
            self._proxy_successes[key] = self._proxy_successes.get(key, 0) + 1
        self._events.append({
            "proxy_key":           key,
            "ts":                  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "url":                 url,
            "result":              "ok" if ok else "fail",
            "proxy_success_count": self._proxy_successes.get(key, 0),
        })

    def record_burn(self, proto: str, host_port: str, b_count: int) -> None:
        """Record proxy retirement — drives surface 2 (B-per-proxy distribution)."""
        self._b_dist.append(b_count)

    def record_working_set(self, eligible_count: int) -> None:
        """Snapshot eligible-candidate count — drives surface 3."""
        self._ws_snapshots.append((time.monotonic() - self._t0, eligible_count))

    def finalize(self, report_dir: Path) -> Path:
        """Write JSONL event log + MD summary. Return MD path."""
        self._log_dir.mkdir(parents=True, exist_ok=True)
        report_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        jsonl_path = _write_event_log(self._log_dir, ts, self._events)
        md_path    = _write_summary(report_dir, ts, self, jsonl_path)
        return md_path


# FUNCTIONS

# Write per-proxy event log as JSONL; return path
def _write_event_log(log_dir: Path, ts: str, events: list[dict]) -> Path:
    path = log_dir / f"acquire_events_{ts}.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return path


# Write MD summary covering all 5 surfaces; return path
def _write_summary(report_dir: Path, ts: str, lg: AcquireLogger, jsonl_path: Path) -> Path:
    elapsed    = time.monotonic() - lg._t0
    done       = lg._done
    total      = lg._total
    attempts   = lg._attempts
    fails      = attempts - done
    rate_pct   = done / total * 100 if total else 0.0
    fetch_rate = done / elapsed * 60 if elapsed else 0.0   # URLs/min

    lines = [
        f"# Acquire-pipe run — {ts}",
        "",
        "## Surface 1 — Fetch progress",
        "",
        f"| Metric | Value |",
        f"|---|---|",
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
            f"| B (requests) | Count |",
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
        f"| Metric | Value |",
        "|---|---|",
        f"| Successful fetches | {done} |",
        f"| Failed attempts | {fails} |",
        f"| Ratio (fails/success) | {fails/done:.2f} |" if done else "| Ratio | — (no successes) |",
        "",
        "## Surface 5 — Per-proxy event log",
        "",
        f"JSONL: `{jsonl_path}`",
        f"Events recorded: {len(lg._events)}",
        "",
    ]

    path = report_dir / f"acquire_run_{ts}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
