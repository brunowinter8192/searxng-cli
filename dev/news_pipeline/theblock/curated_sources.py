#!/usr/bin/env python3
# Unified curated proxy source: monosans + proxifly, merged and deduped.

# INFRASTRUCTURE

import httpx

from monosans_loader import load_monosans_proxies
from proxy_status_log import proxy_key

PROXIFLY_URL  = "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.json"
FETCH_TIMEOUT = 15.0

# ORCHESTRATOR

def load_curated_proxies() -> list[tuple[str, str]]:
    """Fetch monosans + proxifly, merge, dedup; return [(protocol, host:port)]."""
    monosans = load_monosans_proxies()
    proxifly = _fetch_proxifly()
    return _merge_dedup(monosans + proxifly)

# FUNCTIONS

def _fetch_proxifly() -> list[tuple[str, str]]:
    """Fetch proxifly all/data.json; return [(protocol, host:port)]."""
    resp = httpx.get(PROXIFLY_URL, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    return [(e["protocol"], f"{e['ip']}:{e['port']}") for e in resp.json()]


def _merge_dedup(entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Deduplicate entries by canonical proxy_key; first occurrence wins."""
    seen:   set[str]              = set()
    result: list[tuple[str, str]] = []
    for proto, host_port in entries:
        key = proxy_key(proto, host_port)
        if key not in seen:
            seen.add(key)
            result.append((proto, host_port))
    return result
