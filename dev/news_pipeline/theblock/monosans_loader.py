#!/usr/bin/env python3
# Fetch monosans/proxy-list JSON and return (protocol, host:port) tuples.

# INFRASTRUCTURE

from pathlib import Path  # noqa: F401 — kept for consistency with sibling modules

import httpx

MONOSANS_URL = "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies.json"
FETCH_TIMEOUT = 15.0

# ORCHESTRATOR

def load_monosans_proxies() -> list[tuple[str, str]]:
    """Fetch monosans proxies.json; return [(protocol, host:port)] in source order."""
    raw = _fetch_json(MONOSANS_URL)
    return [_build_entry(e) for e in raw]

# FUNCTIONS

def _fetch_json(url: str) -> list[dict]:
    resp = httpx.get(url, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _build_entry(entry: dict) -> tuple[str, str]:
    """Build (protocol, host_port) from one proxies.json entry."""
    proto    = entry["protocol"]
    host     = entry["host"]
    port     = entry["port"]
    username = entry.get("username")
    password = entry.get("password")
    if username and password:
        host_port = f"{username}:{password}@{host}:{port}"
    else:
        host_port = f"{host}:{port}"
    return (proto, host_port)
