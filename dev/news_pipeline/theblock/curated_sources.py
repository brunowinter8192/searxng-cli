#!/usr/bin/env python3
# Unified curated proxy source: monosans + proxifly, merged and deduped.
# Standalone eval source: TheSpeedX/PROXY-List (http/socks4/socks5 bare txt files).

# INFRASTRUCTURE

import httpx

from monosans_loader import load_monosans_proxies
from proxy_status_log import proxy_key

PROXIFLY_URL    = "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.json"
THESPEEDX_URLS  = {
    "http":   "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "socks4": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
    "socks5": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
}
FETCH_TIMEOUT   = 15.0

# ORCHESTRATOR

def load_curated_proxies() -> list[tuple[str, str]]:
    """Fetch monosans + proxifly, merge, dedup; return [(protocol, host:port)]."""
    monosans = load_monosans_proxies()
    proxifly = _fetch_proxifly()
    return _merge_dedup(monosans + proxifly)


def load_thespeedx_proxies() -> list[tuple[str, str]]:
    """Fetch TheSpeedX http/socks4/socks5 txt files; dedup; return [(protocol, host:port)]."""
    entries: list[tuple[str, str]] = []
    for proto, url in THESPEEDX_URLS.items():
        entries.extend(_fetch_thespeedx(proto, url))
    return _merge_dedup(entries)

# FUNCTIONS

def _fetch_proxifly() -> list[tuple[str, str]]:
    """Fetch proxifly all/data.json; return [(protocol, host:port)]."""
    resp = httpx.get(PROXIFLY_URL, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    return [(e["protocol"], f"{e['ip']}:{e['port']}") for e in resp.json()]


def _fetch_thespeedx(proto: str, url: str) -> list[tuple[str, str]]:
    """Fetch one TheSpeedX bare-host:port txt file; return [(proto, host:port)]."""
    resp = httpx.get(url, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    entries: list[tuple[str, str]] = []
    for line in resp.text.splitlines():
        line = line.strip()
        if line:
            entries.append((proto, line))
    return entries


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
