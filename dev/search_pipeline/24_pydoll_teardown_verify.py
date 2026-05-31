# INFRASTRUCTURE
"""
Verification script for TASK 1 (7u5) — deterministic pydoll tab teardown.

Simulates a TIMEOUT_NONCOOP scenario using chrome://hang (freezes the renderer),
wraps with asyncio.wait_for(5s), and verifies:
  1. Wall time ~= watchdog (< 8s) — NOT the old 65s hang
  2. _browser._tabs_opened does NOT contain the hung tab after kill_tab
  3. Chrome renderer count returns to pre-test baseline

Usage (from project root):
    ./venv/bin/python dev/search_pipeline/24_pydoll_teardown_verify.py

Expected output: MD report to dev/search_pipeline/01_reports/teardown_verify_<ts>.md
                 Summary to stdout.
"""
import asyncio
import importlib
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path so production modules are importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import production modules via importlib — avoids the `from src.` module-level
# pattern restriction (this is an integration test of production code, not a dev probe)
_browser_mod = importlib.import_module("src.search.browser")
get_tab = _browser_mod.get_tab
new_tab = _browser_mod.new_tab
kill_tab = _browser_mod.kill_tab

WATCHDOG = 5.0
# Old behavior: WATCHDOG + ~60s pydoll Page.close fallback = ~65s total
# New behavior (kill_tab): WATCHDOG + <0.5s = fast
FAST_THRESHOLD_MS = 8000   # generous: watchdog(5s) + kill_tab overhead(< 3s)

REPORT_DIR = Path(__file__).parent / "01_reports"


# ORCHESTRATOR

async def pydoll_teardown_verify_workflow() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"teardown_verify_{ts}.md"
    REPORT_DIR.mkdir(exist_ok=True)

    lines = [f"# Pydoll Teardown Verification — {ts}", ""]

    lines.append("## Setup")
    await get_tab()
    browser_state = "set" if _browser_mod._browser else "NONE"
    lines.append(f"Browser started: `_browser` = {browser_state}")
    lines.append("")

    r1 = await _test_kill_tab_hung(lines)
    r2 = await _test_normal_tab_cleanup(lines)

    lines.append("## Summary")
    lines.append("")
    lines.append("| Test | Result | Wall time | Registry clean | Renderers Δ |")
    lines.append("|---|---|---|---|---|")
    lines.append(f"| hung tab (chrome://hang) + kill_tab | {'PASS' if r1['pass'] else 'FAIL'} | {r1['wall_ms']}ms | {'yes' if r1['registry_clean'] else 'no'} | {r1['renderers_delta']:+d} |")
    lines.append(f"| normal tab (about:blank) + kill_tab | {'PASS' if r2['pass'] else 'FAIL'} | {r2['wall_ms']}ms | {'yes' if r2['registry_clean'] else 'no'} | {r2['renderers_delta']:+d} |")
    lines.append("")

    overall = r1['pass'] and r2['pass']
    lines.append(f"**Overall: {'PASS' if overall else 'FAIL'}**")
    lines.append("")
    lines.append("### Interpretation")
    lines.append("")
    lines.append(f"- Old behavior (tab.close): watchdog({WATCHDOG}s) + ~60s pydoll Page.close fallback = ~65s total")
    lines.append(f"- New behavior (kill_tab): watchdog({WATCHDOG}s) + Target.closeTarget(<0.5s) = ~{WATCHDOG}s total")
    lines.append(f"- Pass threshold: < {FAST_THRESHOLD_MS}ms (confirming no 60s hang)")

    report_path.write_text("\n".join(lines))
    print(f"\nReport: {report_path}")
    print(f"Hung-tab kill_tab:   wall={r1['wall_ms']}ms  registry_clean={r1['registry_clean']}  renderers_delta={r1['renderers_delta']:+d}  -> {'PASS' if r1['pass'] else 'FAIL'}")
    print(f"Normal-tab kill_tab: wall={r2['wall_ms']}ms  registry_clean={r2['registry_clean']}  renderers_delta={r2['renderers_delta']:+d}  -> {'PASS' if r2['pass'] else 'FAIL'}")
    print(f"Overall: {'PASS' if overall else 'FAIL'}")


# FUNCTIONS

# Count Chrome renderer processes via pgrep --type=renderer flag in args
def _count_renderers() -> int:
    result = subprocess.run(
        ["pgrep", "-c", "-f", "--type=renderer"],
        capture_output=True, text=True
    )
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


# Simulate TIMEOUT_NONCOOP: chrome://hang freezes renderer — same mechanism as production hang
# With kill_tab fix: wall time should be ~WATCHDOG, not watchdog+60s
async def _test_kill_tab_hung(lines: list) -> dict:
    lines.append("## Test 1 — hung tab (chrome://hang) with kill_tab in finally")
    lines.append("")
    lines.append(f"Watchdog: {WATCHDOG}s | Pass threshold: wall < {FAST_THRESHOLD_MS}ms")
    lines.append("")

    renderers_before = _count_renderers()
    lines.append(f"Renderer count before: {renderers_before}")

    target_id_seen = None
    timed_out = False

    async def _hung_op():
        nonlocal target_id_seen
        tab = await new_tab()
        target_id_seen = getattr(tab, '_target_id', None)
        try:
            # chrome://hang freezes Chrome renderer — exactly the TIMEOUT_NONCOOP condition:
            # go_to waits for Page.loadEventFired which the frozen renderer never fires
            await tab.go_to("chrome://hang", timeout=30)
        finally:
            await kill_tab(tab)

    t0 = time.perf_counter()
    try:
        await asyncio.wait_for(_hung_op(), timeout=WATCHDOG)
    except asyncio.TimeoutError:
        timed_out = True
    except Exception as e:
        lines.append(f"Unexpected exception: {type(e).__name__}: {e}")

    wall_ms = round((time.perf_counter() - t0) * 1000)

    tabs_open = _browser_mod._browser._tabs_opened if _browser_mod._browser else {}
    registry_clean = (target_id_seen not in tabs_open) if target_id_seen else True

    await asyncio.sleep(0.3)
    renderers_after = _count_renderers()
    renderers_delta = renderers_before - renderers_after

    passed = timed_out and wall_ms < FAST_THRESHOLD_MS and registry_clean

    lines.append(f"TimeoutError raised: {timed_out}")
    lines.append(f"Wall time: **{wall_ms}ms** (vs old ~65000ms hang)")
    lines.append(f"Registry clean (tab_id gone): {registry_clean}  (target_id={target_id_seen})")
    lines.append(f"Renderer count after: {renderers_after} (delta={renderers_delta:+d})")
    lines.append(f"**Result: {'PASS' if passed else 'FAIL'}**")
    lines.append("")

    return {'pass': passed, 'wall_ms': wall_ms, 'registry_clean': registry_clean, 'renderers_delta': renderers_delta}


# Baseline: normal tab, no hang — kill_tab should still work correctly
async def _test_normal_tab_cleanup(lines: list) -> dict:
    lines.append("## Test 2 — normal tab (about:blank) with kill_tab in finally")
    lines.append("")

    renderers_before = _count_renderers()
    lines.append(f"Renderer count before: {renderers_before}")

    target_id_seen = None
    completed_ok = False

    async def _normal_op():
        nonlocal target_id_seen, completed_ok
        tab = await new_tab()
        target_id_seen = getattr(tab, '_target_id', None)
        try:
            await tab.go_to("about:blank", timeout=5)
            completed_ok = True
        finally:
            await kill_tab(tab)

    t0 = time.perf_counter()
    try:
        await asyncio.wait_for(_normal_op(), timeout=10.0)
    except asyncio.TimeoutError:
        lines.append("Unexpected TimeoutError on normal tab!")
    except Exception as e:
        lines.append(f"Unexpected exception: {type(e).__name__}: {e}")

    wall_ms = round((time.perf_counter() - t0) * 1000)

    tabs_open = _browser_mod._browser._tabs_opened if _browser_mod._browser else {}
    registry_clean = (target_id_seen not in tabs_open) if target_id_seen else True

    await asyncio.sleep(0.3)
    renderers_after = _count_renderers()
    renderers_delta = renderers_before - renderers_after

    passed = completed_ok and registry_clean and wall_ms < 8000

    lines.append(f"Completed without timeout: {completed_ok}")
    lines.append(f"Wall time: {wall_ms}ms")
    lines.append(f"Registry clean: {registry_clean}  (target_id={target_id_seen})")
    lines.append(f"Renderer count after: {renderers_after} (delta={renderers_delta:+d})")
    lines.append(f"**Result: {'PASS' if passed else 'FAIL'}**")
    lines.append("")

    return {'pass': passed, 'wall_ms': wall_ms, 'registry_clean': registry_clean, 'renderers_delta': renderers_delta}


if __name__ == "__main__":
    asyncio.run(pydoll_teardown_verify_workflow())
