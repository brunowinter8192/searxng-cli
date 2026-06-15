# INFRASTRUCTURE

from src.news.engine.proxy_pool.cooldown import PersistentCooldownManager

BUFFER_SIZE         = 1280   # active buffer target depth (10× concurrency)
DEFAULT_CONCURRENCY = 128    # concurrent (proxy, URL) pairs per batch


# FUNCTIONS

# Build fresh active buffer: up to max_size eligible proxies from pool in pool order
def build_active_buffer(
    pool: list[tuple[str, str]],
    cm: PersistentCooldownManager,
    max_size: int = BUFFER_SIZE,
) -> list[tuple[str, str]]:
    """Return up to max_size eligible proxies from pool in pool order.

    Eligibility is delegated entirely to cm.eligible_candidates() which applies
    the wall-clock UTC cooldown check.
    """
    eligible = cm.eligible_candidates(pool)
    return eligible[:max_size]


# Top up an existing buffer with eligible proxies not already present
def refill_buffer(
    buf: list[tuple[str, str]],
    pool: list[tuple[str, str]],
    cm: PersistentCooldownManager,
    target_size: int = BUFFER_SIZE,
) -> list[tuple[str, str]]:
    """Return a new list with buf topped up to target_size from eligible pool.

    Proxies already in buf are skipped (set-membership check).
    Returns buf unchanged if already at or above target_size.
    New additions are appended in pool order.
    """
    if len(buf) >= target_size:
        return buf
    in_buf    = set(buf)
    eligible  = cm.eligible_candidates(pool)
    additions = [p for p in eligible if p not in in_buf]
    needed    = target_size - len(buf)
    return buf + additions[:needed]
