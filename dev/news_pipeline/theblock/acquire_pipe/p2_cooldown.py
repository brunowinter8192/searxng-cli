# INFRASTRUCTURE

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from proxy_status_log import load_cooled_at, mark_cooled_batch, proxy_key

COOLDOWN_S   = 3600  # 60 minutes
_PROTO_ORDER = {"socks4": 0, "socks5": 1, "http": 2}
_TS_FMT      = "%Y-%m-%dT%H:%M:%SZ"


# ORCHESTRATOR

class PersistentCooldownManager:
    """Cooldown state backed by proxy_status_log.json (cooled_at field).

    Loads all cooled_at timestamps from the log on init — survives process restarts.
    mark_burned() updates the in-memory cache + dirty set (no file I/O per call).
    flush() batch-writes all dirty entries in one load+save — one I/O per batch.
    """

    def __init__(self, cooldown_s: int = COOLDOWN_S):
        self._cooldown_td = timedelta(seconds=cooldown_s)
        raw = load_cooled_at()   # {proxy_key: iso_ts | None}
        self._burned_utc: dict[str, datetime] = {}
        for key, iso_ts in raw.items():
            if iso_ts:
                self._burned_utc[key] = datetime.strptime(iso_ts, _TS_FMT).replace(tzinfo=timezone.utc)
        self._dirty: set[str] = set()

    def mark_burned(self, proto: str, host_port: str) -> None:
        """Record proxy as burned now (in-memory only; flush() persists to log)."""
        key = proxy_key(proto, host_port)
        self._burned_utc[key] = datetime.now(timezone.utc)
        self._dirty.add(key)

    def flush(self) -> None:
        """Batch-write all dirty burns to proxy_status_log.json (one I/O call)."""
        if not self._dirty:
            return
        burns = {
            key: self._burned_utc[key].strftime(_TS_FMT)
            for key in self._dirty
        }
        mark_cooled_batch(burns)
        self._dirty.clear()

    def is_eligible(self, proto: str, host_port: str) -> bool:
        """True if proxy has never burned OR cooled_at has expired."""
        burned_at = self._burned_utc.get(proxy_key(proto, host_port))
        if burned_at is None:
            return True
        return (datetime.now(timezone.utc) - burned_at) >= self._cooldown_td

    def eligible_candidates(self, pool: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Pool filtered to eligible proxies, socks4-first ordering."""
        eligible = [(p, hp) for p, hp in pool if self.is_eligible(p, hp)]
        return sorted(eligible, key=lambda x: _PROTO_ORDER.get(x[0], 99))

    def cooldown_count(self) -> int:
        """Count of proxies currently in active cooldown (in-memory)."""
        now = datetime.now(timezone.utc)
        return sum(1 for dt in self._burned_utc.values() if (now - dt) < self._cooldown_td)

    def earliest_eligible_at(self) -> "datetime | None":
        """UTC datetime when the next cooled proxy becomes eligible. None if none cooling."""
        if not self._burned_utc:
            return None
        return min(self._burned_utc.values()) + self._cooldown_td


# Backward-compat alias — p4_loop.py imports CooldownManager by name (unchanged until Stage 3)
CooldownManager = PersistentCooldownManager
