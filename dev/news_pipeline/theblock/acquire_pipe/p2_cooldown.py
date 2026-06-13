# INFRASTRUCTURE

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from proxy_status_log import proxy_key

COOLDOWN_S   = 3600  # 60 minutes
_PROTO_ORDER = {"socks4": 0, "socks5": 1, "http": 2}


# ORCHESTRATOR

class CooldownManager:
    """Per-run in-process cooldown state. No file I/O — resets each run."""

    def __init__(self, cooldown_s: int = COOLDOWN_S):
        self._cooldown_s = cooldown_s
        self._burned: dict[str, float] = {}  # proxy_key → monotonic burn timestamp

    def mark_burned(self, proto: str, host_port: str) -> None:
        """Record proxy as burned now."""
        self._burned[proxy_key(proto, host_port)] = time.monotonic()

    def is_eligible(self, proto: str, host_port: str) -> bool:
        """True if proxy has never burned OR cooldown has expired."""
        burned_at = self._burned.get(proxy_key(proto, host_port))
        if burned_at is None:
            return True
        return (time.monotonic() - burned_at) >= self._cooldown_s

    def eligible_candidates(self, pool: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Pool filtered to eligible proxies, socks4-first ordering."""
        eligible = [(p, hp) for p, hp in pool if self.is_eligible(p, hp)]
        return sorted(eligible, key=lambda x: _PROTO_ORDER.get(x[0], 99))

    def cooldown_count(self) -> int:
        """Count of proxies currently in active cooldown."""
        now = time.monotonic()
        return sum(1 for t in self._burned.values() if (now - t) < self._cooldown_s)
