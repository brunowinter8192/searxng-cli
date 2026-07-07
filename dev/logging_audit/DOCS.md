# dev/logging_audit/

## Problem

`searxng-cli search_web` emitted Python `logger.warning()` output to stderr, which Claude Code's Bash tool merges with stdout into the tool_result. Observed noise before the result table:

```
STACK_EXCHANGE_API_KEY not set — anonymous quota (300 req/day)
Lobsters empty (EMPTY_NO_CONTAINER) for: <query>
```

Root causes: (1) per-engine-empty events misclassified as WARNING — they are already captured structurally in `query_log.jsonl`; (2) no FileHandler-only config — Python's default lastResort handler emits WARNING+ to stderr.

Production code fix: `cli.py` logging config + call-site relevel.

## Investigation

### Code Analysis

- `src/search/engines/*.py`: all "Engine empty" calls used `logger.warning()` — misclassified. `query_log.jsonl` already holds per-engine `{status, drop_reason}` records via `query_logger.py`, making the text warning redundant.
- `src/search/engines/stack_exchange.py`: `STACK_EXCHANGE_API_KEY not set` was WARNING — correctly reclassified to INFO (config state, not a problem).
- `cli.py`: no `logging.basicConfig()` call → Python's `lastResort` handler at WARNING threshold → stderr emission.
- `src/crawler/crawl_site.py:305`: has own `logging.basicConfig()` inside `if __name__ == "__main__"` guard — only fires in standalone mode, not via `cli.py`.

### Scripts

**`01_audit.py`** — AST walker over `src/`; emits one row per `logger.X()` / `logging.X()` call with file:line, logger object name, current level, and message template (truncated to 120 chars). Outputs MD report to `md/` (`01_audit_<ts>.md`).

Usage (from repo root):
```bash
./venv/bin/python dev/logging_audit/01_audit.py
# prints report path to stdout; stderr shows scan progress
```

Re-run after Phase B to verify all "engine empty" entries are DEBUG, not WARNING.
