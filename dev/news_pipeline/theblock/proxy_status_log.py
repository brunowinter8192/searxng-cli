#!/usr/bin/env python3
# Cumulative proxy-status log — keyed by "protocol://host:port", bounded by unique proxies (not run count).

# INFRASTRUCTURE

import json
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
LOG_PATH   = SCRIPT_DIR / "logs" / "proxy_status_log.json"

# ORCHESTRATOR

# Load cooled_at timestamps for all proxies in the log
def load_cooled_at() -> dict[str, str | None]:
    """Return {proxy_key: cooled_at_iso} for every log entry; value is None if field absent."""
    data = _load_log()
    return {key: entry.get("cooled_at") for key, entry in data.items()}


# Batch-write cooled_at for every key in burns; create minimal entry if key absent
def mark_cooled_batch(burns: dict[str, str]) -> None:
    """Upsert cooled_at (UTC ISO) for each proxy_key in burns.

    One load + one save per call regardless of how many keys are in burns.
    Creates a minimal log entry for proxies not yet seen by record_run().
    """
    data   = _load_log()
    ts_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for key, iso_ts in burns.items():
        if key in data:
            data[key]["cooled_at"] = iso_ts
        else:
            proto, host, port = _parse_proxy_key(key)
            data[key] = {
                "protocol":    proto,
                "host":        host,
                "port":        port,
                "checks":      0,
                "alive":       0,
                "dead":        0,
                "last_status": "",
                "first_seen":  ts_now,
                "last_seen":   ts_now,
                "cooled_at":   iso_ts,
            }
    _save_log(data)


def record_run(results: list[dict], source_label: str) -> None:
    """Upsert every result (alive + dead) into the cumulative proxy-status log."""
    ts   = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = _load_log()

    for r in results:
        key = proxy_key(r["proto"], r["host_port"])
        host, port = _parse_host_port(r["host_port"])

        if key not in data:
            data[key] = {
                "protocol":   r["proto"],
                "host":       host,
                "port":       port,
                "checks":     0,
                "alive":      0,
                "dead":       0,
                "last_status": "",
                "first_seen": ts,
                "last_seen":  ts,
            }

        entry = data[key]
        entry["checks"]     += 1
        entry["last_seen"]   = ts
        entry["last_status"] = "alive" if r["alive"] else "dead"
        if r["alive"]:
            entry["alive"] += 1
        else:
            entry["dead"] += 1

    _save_log(data)
    alive = sum(1 for r in results if r["alive"])
    print(f"proxy_status_log: {len(results)} results ({alive} alive) folded → {len(data)} unique proxies on record  [{LOG_PATH}]")

# FUNCTIONS

def _load_log() -> dict:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        return {}
    return json.loads(LOG_PATH.read_text(encoding="utf-8"))


def _save_log(data: dict) -> None:
    LOG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# Partition loaded monosans entries into (to_check, skipped_fresh)
def partition_fresh(
    entries: list[tuple[str, str]],
    window_s: int,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (to_check, skipped_fresh).

    to_check:      key absent from log  OR  last_seen age >= window_s
    skipped_fresh: key present in log  AND  last_seen age < window_s
    """
    data = _load_log()
    now  = datetime.now(timezone.utc)
    to_check: list[tuple[str, str]]      = []
    skipped_fresh: list[tuple[str, str]] = []
    for proto, host_port in entries:
        key   = proxy_key(proto, host_port)
        entry = data.get(key)
        if entry is None:
            to_check.append((proto, host_port))
            continue
        last_seen_dt = datetime.strptime(entry["last_seen"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        age_s        = (now - last_seen_dt).total_seconds()
        if age_s >= window_s:
            to_check.append((proto, host_port))
        else:
            skipped_fresh.append((proto, host_port))
    return to_check, skipped_fresh


def proxy_key(proto: str, host_port: str) -> str:
    """Build canonical key: protocol://host:port (auth stripped if present)."""
    host, port = _parse_host_port(host_port)
    return f"{proto}://{host}:{port}"


def _parse_proxy_key(key: str) -> tuple[str, str, int]:
    """Parse canonical key 'proto://host:port' → (proto, host, port_int)."""
    proto, rest  = key.split("://", 1)
    host, port_s = rest.rsplit(":", 1)
    return proto, host, int(port_s)


def _parse_host_port(host_port: str) -> tuple[str, int]:
    """Return (host, port) from 'host:port' or 'user:pass@host:port'."""
    clean        = host_port.split("@")[-1]
    host, port_s = clean.rsplit(":", 1)
    return host, int(port_s)
