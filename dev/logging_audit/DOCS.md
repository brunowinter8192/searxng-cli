# dev/logging_audit/

## Role
AST-based audit tool over `src/` logger call-sites — surfaces every `logger.X()` / `logging.X()` call with its current level, for identifying misclassified log levels (e.g. structural-duplicate events filed at WARNING instead of DEBUG).

## Modules

### 01_audit.py (130 LOC)

**Purpose:** AST walker over `src/`; emits one row per `logger.X()` / `logging.X()` call with file:line, logger object name, current level, and message template (truncated to 120 chars).
**Reads:** `src/**/*.py` source files.
**Writes:** MD report to `md/01_audit_<ts>.md`. Prints report path to stdout; scan progress to stderr.
**Called by:** CLI only. Run: `./venv/bin/python dev/logging_audit/01_audit.py`.

## Gotchas
Re-run after a call-site relevel pass to verify target categories (e.g. "engine empty") moved off WARNING — compare successive `md/01_audit_<ts>.md` reports.
