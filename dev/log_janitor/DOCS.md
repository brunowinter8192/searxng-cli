# dev/log_janitor/

## Role
Test suite for the log_janitor algorithm (mirrors `src/log_janitor.py`). Verifies 14-day retention logic under synthetic conditions: JSONL ts-based filtering, sidecar mtime-based deletion, fast-path marker skip (marker recent → no-op), and stale-marker slow-path re-fire.

## Modules

### p1_log_janitor.py (88 LOC)

**Purpose:** Dev-isolated mirror of `src/log_janitor.py`. Stdlib-only. Provides `maybe_prune_jsonl`, `maybe_prune_sidecars`, `get_retention_days`.
**Reads:** JSONL log files, sidecar files, marker file mtimes (via caller).
**Writes:** Pruned JSONL files, deleted sidecar files, marker files (returned to caller, not written directly).
**Called by:** `01_prune_test.py`.

### 01_prune_test.py (119 LOC)

**Purpose:** Self-contained synthetic prune test. Creates a temp dir, writes 5 JSONL entries (2 × 20d-old, 3 × 2d-recent) + 3 sidecar files (2 × mtime 20d-ago, 1 recent), runs three scenarios (slow-path fires without marker; fast-path skip with recent marker; stale marker re-fires slow-path), asserts outcomes, exits 0 on all-pass / 1 on any failure.
**Reads:** Synthetic temp-dir fixtures it creates itself.
**Writes:** stdout PASS/FAIL lines, exit code.
**Called by:** CLI only. Run: `./venv/bin/python dev/log_janitor/01_prune_test.py`.
