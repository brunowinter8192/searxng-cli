# INFRASTRUCTURE

from datetime import datetime, timedelta, timezone

from src.news.engine.proxy_pool.proxy_key import proxy_key

COOLDOWN_S = 3600  # 60 minutes


# ORCHESTRATOR

class PersistentCooldownManager:
    """In-memory cooldown tracking — per-job fresh state, no file I/O.

    Each new instance starts with an empty burn dict → each job is a clean slate.
    """

    def __init__(self, cooldown_s: int = COOLDOWN_S):
        self._cooldown_td = timedelta(seconds=cooldown_s)
        self._burned_utc: dict[str, datetime] = {}

    def mark_burned(self, proto: str, host_port: str) -> None:
        """Record proxy as burned now (in-memory only)."""
        key = proxy_key(proto, host_port)
        self._burned_utc[key] = datetime.now(timezone.utc)

    def is_eligible(self, proto: str, host_port: str) -> bool:
        """True if proxy has never burned OR cooldown has expired."""
        burned_at = self._burned_utc.get(proxy_key(proto, host_port))
        if burned_at is None:
            return True
        return (datetime.now(timezone.utc) - burned_at) >= self._cooldown_td

    def eligible_candidates(self, pool: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Pool filtered to eligible proxies in pool order."""
        return [(p, hp) for p, hp in pool if self.is_eligible(p, hp)]

    def cooldown_count(self) -> int:
        """Count of proxies currently in active cooldown (in-memory)."""
        now = datetime.now(timezone.utc)
        return sum(1 for dt in self._burned_utc.values() if (now - dt) < self._cooldown_td)

    def earliest_eligible_at(self) -> "datetime | None":
        """UTC datetime when the next cooled proxy becomes eligible. None if none cooling."""
        if not self._burned_utc:
            return None
        return min(self._burned_utc.values()) + self._cooldown_td
