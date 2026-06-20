#!/usr/bin/env python3
"""
Deterministic tests for RidingCooldownManager (fixed + exp policies).
No browser or proxy infrastructure needed.

Tests:
  1  fixed_60min               — burned proxy ineligible at t+59min, eligible at t+61min
  2  fixed_default_equiv        — RidingCooldownManager() == policy='fixed' (60-min)
  3  exp_unproductive_bounds    — 3 consecutive ride_ok=0 burns; next_eligible bounded by
                                  base*2**n (n=0,1,2); proxy ineligible immediately after burn
  4  exp_cap                    — after enough unproductive burns bound capped at 3600s
  5  exp_reset_on_productive    — after 2 unproductive burns, ride_ok=1 resets counter;
                                  next backoff bounded by base (300s), not 1200s
  6  exp_eligible_after_backoff — proxy becomes eligible after next_eligible passes
  7  exp_cooldown_count         — cooldown_count()==N immediately after N unproductive burns,
                                  0 after next_eligible passes (A/B sampling correctness)
  8  fixed_cooldown_count       — cooldown_count() under fixed mirrors is_eligible

All src/ imports are lazy (inside function bodies) — satisfies dev/ top-level import constraint.

Usage:
    ./venv/bin/python dev/news_pipeline/coindesk_proxy_riding/test_cooldown_policy.py
"""

# INFRASTRUCTURE

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

_WORKTREE = Path(__file__).parents[3]
if str(_WORKTREE) not in sys.path:
    sys.path.insert(0, str(_WORKTREE))

_PROTO = "http"
_HP    = "proxy:8080"


# ORCHESTRATOR

def main() -> None:
    results = [
        _run("test_fixed_60min",               test_fixed_60min),
        _run("test_fixed_default_equiv",        test_fixed_default_equiv),
        _run("test_exp_unproductive_bounds",    test_exp_unproductive_bounds),
        _run("test_exp_cap",                    test_exp_cap),
        _run("test_exp_reset_on_productive",    test_exp_reset_on_productive),
        _run("test_exp_eligible_after_backoff", test_exp_eligible_after_backoff),
        _run("test_exp_cooldown_count",         test_exp_cooldown_count),
        _run("test_fixed_cooldown_count",       test_fixed_cooldown_count),
    ]
    passed = sum(results)
    print(f"\n{'='*55}")
    print(f"Results: {passed}/{len(results)} passed")
    if passed < len(results):
        sys.exit(1)


# FUNCTIONS

def _run(name: str, fn) -> bool:
    print(f"[test] {name} ...", end=" ", flush=True)
    try:
        fn()
        print("PASS")
        return True
    except AssertionError as exc:
        print(f"FAIL — {exc}")
        return False
    except Exception as exc:
        import traceback
        print(f"ERROR — {exc}")
        traceback.print_exc()
        return False


# Helpers: inject a fake burn time by patching _burned_at / _next_eligible directly.

def _burn_at_offset(mgr, proto, hp, offset_s: float, ride_ok: int = 0) -> None:
    """Burn and then back-date the recorded timestamp by offset_s seconds."""
    from src.news.engine.proxy_pool.proxy_key import proxy_key
    mgr.mark_burned(proto, hp, ride_ok=ride_ok)
    key = proxy_key(proto, hp)
    now = datetime.now(timezone.utc)
    if mgr._policy == "fixed":
        mgr._burned_at[key] = now - timedelta(seconds=offset_s)
    else:
        mgr._next_eligible[key] = now - timedelta(seconds=offset_s)


# 1 — fixed: burned proxy ineligible at t+59min, eligible at t+61min.
def test_fixed_60min() -> None:
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager
    mgr = RidingCooldownManager(policy="fixed")

    _burn_at_offset(mgr, _PROTO, _HP, offset_s=59 * 60)   # backdated 59min ago
    assert not mgr.is_eligible(_PROTO, _HP), "should still be in cooldown at t+59min"

    _burn_at_offset(mgr, _PROTO, _HP, offset_s=61 * 60)   # backdated 61min ago
    assert mgr.is_eligible(_PROTO, _HP),     "should be eligible after 60min cooldown"


# 2 — fixed default: no-arg constructor == policy='fixed' 60-min.
def test_fixed_default_equiv() -> None:
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager
    mgr = RidingCooldownManager()
    assert mgr._policy == "fixed", f"default policy should be 'fixed', got {mgr._policy!r}"
    _burn_at_offset(mgr, _PROTO, _HP, offset_s=59 * 60)
    assert not mgr.is_eligible(_PROTO, _HP), "default should enforce 60-min cooldown"


# 3 — exp unproductive: 3 consecutive ride_ok=0 burns; each next_eligible bounded by base*2**n.
def test_exp_unproductive_bounds() -> None:
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager, _exp_backoff
    from src.news.engine.proxy_pool.proxy_key import proxy_key

    mgr = RidingCooldownManager(policy="exp")
    BASE = 300.0

    for n in range(3):
        t_before = datetime.now(timezone.utc)
        mgr.mark_burned(_PROTO, _HP, ride_ok=0)
        t_after  = datetime.now(timezone.utc)

        key = proxy_key(_PROTO, _HP)
        nxt = mgr._next_eligible[key]

        # next_eligible must be in [t_before, t_before + base*2**n]
        upper = t_before + timedelta(seconds=_exp_backoff(n, base=BASE))
        assert nxt >= t_before,  f"burn {n}: next_eligible {nxt} before burn time {t_before}"
        assert nxt <= upper + timedelta(seconds=1),  \
            f"burn {n}: next_eligible exceeds upper bound base*2**{n}={_exp_backoff(n,base=BASE):.0f}s"

        # proxy must be ineligible immediately after burn
        assert not mgr.is_eligible(_PROTO, _HP), f"burn {n}: proxy should be in cooldown"


# 4 — exp cap: after many unproductive burns backoff is capped at 3600s.
def test_exp_cap() -> None:
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager, _exp_backoff
    from src.news.engine.proxy_pool.proxy_key import proxy_key

    mgr = RidingCooldownManager(policy="exp")
    CAP = 3600.0

    for _ in range(20):
        mgr.mark_burned(_PROTO, _HP, ride_ok=0)

    key = proxy_key(_PROTO, _HP)
    nxt = mgr._next_eligible[key]
    now = datetime.now(timezone.utc)
    gap_s = (nxt - now).total_seconds()
    assert gap_s <= CAP + 1, f"backoff {gap_s:.0f}s exceeds cap {CAP}s"


# 5 — exp reset: after 2 unproductive burns, ride_ok=1 resets counter → backoff bounded by base.
def test_exp_reset_on_productive() -> None:
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager, _exp_backoff
    from src.news.engine.proxy_pool.proxy_key import proxy_key

    mgr  = RidingCooldownManager(policy="exp")
    BASE = 300.0
    key  = proxy_key(_PROTO, _HP)

    mgr.mark_burned(_PROTO, _HP, ride_ok=0)   # attempt 0 → bound 300
    mgr.mark_burned(_PROTO, _HP, ride_ok=0)   # attempt 1 → bound 600
    # Without reset, next burn (attempt 2) would be bounded by 1200s.
    # With ride_ok=1 reset, attempt resets to 0 → bound 300.
    t_before = datetime.now(timezone.utc)
    mgr.mark_burned(_PROTO, _HP, ride_ok=1)
    upper = t_before + timedelta(seconds=_exp_backoff(0, base=BASE))   # 300s
    nxt   = mgr._next_eligible[key]
    assert nxt <= upper + timedelta(seconds=1), \
        f"reset not applied: next_eligible gap {(nxt - t_before).total_seconds():.0f}s > base {BASE}s"

    # failed_attempts after the productive burn should be 1 (reset to 0, then +1)
    assert mgr._failed_attempts[key] == 1, \
        f"expected failed_attempts=1 after reset+burn, got {mgr._failed_attempts[key]}"


# 6 — exp: proxy becomes eligible once next_eligible passes.
def test_exp_eligible_after_backoff() -> None:
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager
    from src.news.engine.proxy_pool.proxy_key import proxy_key

    mgr = RidingCooldownManager(policy="exp")
    mgr.mark_burned(_PROTO, _HP, ride_ok=0)

    key = proxy_key(_PROTO, _HP)
    assert not mgr.is_eligible(_PROTO, _HP), "should be in cooldown immediately after burn"

    # Back-date next_eligible to 1s ago → now eligible
    mgr._next_eligible[key] = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert mgr.is_eligible(_PROTO, _HP), "should be eligible once next_eligible has passed"


# 7 — exp cooldown_count: N after N burns; 0 after next_eligible backdated past.
def test_exp_cooldown_count() -> None:
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager
    from src.news.engine.proxy_pool.proxy_key import proxy_key

    N    = 4
    mgr  = RidingCooldownManager(policy="exp")
    pool = [(_PROTO, f"proxy:{i}") for i in range(N)]

    for proto, hp in pool:
        mgr.mark_burned(proto, hp, ride_ok=0)

    assert mgr.cooldown_count() == N, \
        f"expected cooldown_count={N} after {N} burns, got {mgr.cooldown_count()}"
    assert len(mgr.eligible_candidates(pool)) == 0, \
        "all proxies should be ineligible immediately after burn"

    # Back-date all next_eligible to past → all eligible, count = 0
    now = datetime.now(timezone.utc)
    for proto, hp in pool:
        mgr._next_eligible[proxy_key(proto, hp)] = now - timedelta(seconds=1)

    assert mgr.cooldown_count() == 0, \
        f"expected cooldown_count=0 after backdating, got {mgr.cooldown_count()}"
    assert len(mgr.eligible_candidates(pool)) == N, \
        f"expected all {N} eligible after backdating"


# 8 — fixed cooldown_count mirrors is_eligible.
def test_fixed_cooldown_count() -> None:
    from src.news.engine.proxy_riding.cooldown import RidingCooldownManager

    mgr  = RidingCooldownManager(policy="fixed")
    pool = [(_PROTO, f"proxy:{i}") for i in range(3)]

    for proto, hp in pool:
        mgr.mark_burned(proto, hp)

    assert mgr.cooldown_count() == 3, \
        f"expected 3 in cooldown immediately after burns, got {mgr.cooldown_count()}"
    assert len(mgr.eligible_candidates(pool)) == 0, "all should be in cooldown"

    # Back-date two of them past 3600s → count drops to 1
    _burn_at_offset(mgr, _PROTO, "proxy:0", offset_s=3601)
    _burn_at_offset(mgr, _PROTO, "proxy:1", offset_s=3601)

    assert mgr.cooldown_count() == 1, \
        f"expected 1 in cooldown after backdating two, got {mgr.cooldown_count()}"
    assert len(mgr.eligible_candidates(pool)) == 2, \
        f"expected 2 eligible after backdating two"


if __name__ == "__main__":
    main()
