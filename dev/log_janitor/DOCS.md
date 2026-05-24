# dev/log_janitor/

## Purpose

Test suite for the log_janitor algorithm (mirrors `src/log_janitor.py`). Verifies 14-day retention logic under synthetic conditions: JSONL ts-based filtering, sidecar mtime-based deletion, fast-path marker skip (marker recent → no-op), and stale-marker slow-path re-fire.

## Scripts

### p1_log_janitor.py (83 LOC)

**Purpose:** Dev-isolated mirror of `src/log_janitor.py`. Stdlib-only. Provides `maybe_prune_jsonl`, `maybe_prune_sidecars`, `get_retention_days`. Imported by `01_prune_test.py`.

### 01_prune_test.py (97 LOC)

**Purpose:** Self-contained synthetic prune test. Creates a temp dir, writes 5 JSONL entries (2 × 20d-old, 3 × 2d-recent) + 3 sidecar files (2 × mtime 20d-ago, 1 recent), runs three scenarios, asserts outcomes, exits 0 on all-pass / 1 on any failure.

**Scenarios:**
1. Slow-path fires (no marker): 2 old JSONL entries dropped, 2 old sidecars deleted, markers created.
2. Fast-path skip: injected 20d-old line survives because marker is < 1h old.
3. Stale marker (`os.utime` to 3700s ago): slow-path re-fires, injected old line pruned.

**Usage:**

```bash
cd <project_root>
./venv/bin/python dev/log_janitor/01_prune_test.py
```

**Expected output:**

```
=== log_janitor prune test ===

-- Scenario 1: slow-path fires (no marker) --
  [PASS] JSONL: 3 recent lines kept
  [PASS] JSONL: no old entries remain
  [PASS] Sidecar: 1 file remains
  [PASS] Sidecar: recent.md kept
  [PASS] JSONL marker created
  [PASS] Sidecar marker created

-- Scenario 2: fast-path skip (marker recent) --
  [PASS] Fast-path: injected old line NOT pruned (marker recent)

-- Scenario 3: stale marker → slow-path re-fires --
  [PASS] Stale marker: injected old line pruned (slow-path re-fired)

RESULT: all assertions PASSED
```
