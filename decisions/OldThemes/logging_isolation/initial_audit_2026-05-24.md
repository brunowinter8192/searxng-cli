# Logging Isolation — Initial Audit 2026-05-24

## Symptom

`searxng-cli search_web "X"` emitted warning lines to stderr before the breakdown table. Claude Code's Bash tool merges stdout+stderr into tool_result, so the agent received:

```
STACK_EXCHANGE_API_KEY not set — anonymous quota (300 req/day)
Lobsters empty (EMPTY_NO_CONTAINER) for: X
<breakdown table>
```

Hard constraint: prod stdout must contain ONLY structured data. Zero logger output to caller.

## Root Causes (both present simultaneously)

**RC1 — Semantic misclassification:** "engine empty" events filed as WARNING. Per-engine empty results are already captured structurally in `query_log.jsonl` via `engine_run` records with `status` + `drop_reason`. The WARNING text is a redundant, lossy copy.

**RC2 — Missing logging config:** no `logging.basicConfig()` in `cli.py`. Python's `lastResort` handler fires at WARNING+ to stderr for any log call that reaches the root logger without a configured handler.

## Options Evaluated

**Option A — Wrapper redirect (stderr → /dev/null at CLI wrapper level):**
`searxng-cli` wrapper already lives at `~/.local/bin/searxng-cli`. Could add `2>/dev/null` or redirect stderr to a file there. Rejected: suppresses ALL stderr including genuine Python crash tracebacks (uncaught exceptions). Makes debugging production failures harder. Also hides genuine WARNINGs during dev runs.

**Option B — Central Python logging config (FileHandler-only):**
`logging.basicConfig(handlers=[FileHandler(...)])` before any `src.*` imports in `cli.py`. Installs a FileHandler on the root logger; Python never installs the default StreamHandler when `handlers=` is provided explicitly. All logger output (DEBUG through CRITICAL) routes to `src/logs/cli.log`. Uncaught-exception tracebacks still go to stderr (Python's default `sys.excepthook` — not the logging system). Selected.

**Option C — Demote misclassified calls only (no config change):**
Fix the 5 WARNING→DEBUG engine-empty calls and the config-state calls. At DEBUG level, Python's lastResort handler (threshold WARNING) would suppress them. But: any future `logger.warning()` that's semantically wrong re-creates the leak. Defense-in-depth argument for B+C combined: fix both the config route AND the level taxonomy.

**Option D — ERROR-threshold StreamHandler:**
Install a StreamHandler at ERROR level so genuine errors still surface to stderr. Rejected by user: constraint is ZERO stderr from the logging system. Genuine errors visible via cli.log (file-based post-mortem). Uncaught Python exceptions still hit stderr via excepthook — that's the correct path for catastrophic failures.

## Decision

**B + C combined:** FileHandler-only config (Option B) plus semantic relevel of misclassified calls (Option C). Rationale: B alone fixes the immediate symptom but leaves misclassified calls as latent violations. C alone fixes semantics but is fragile (one new mileveled call recreates the problem). Together they address both root causes.

## Options Rejected (with rationale)

| Option | Rejected because |
|---|---|
| JSON-structured Python logging (`python-json-logger`) | Overkill — flat text is sufficient for human post-mortem; structured analytics already in JSONL analytics logs |
| ERROR-threshold StreamHandler | User hard constraint: zero stderr from logger |
| Wrapper-level stderr redirect | Suppresses genuine crash tracebacks; hides all stderr not just logger output |
| `logging.disable(WARNING)` global | Disables WARNING system-wide including legitimate WARNINGs like CAPTCHA detections, cache I/O failures |

## Call-Site Changes (Phase B)

22 changes total (21 level + 1 config insertion):
- `cli.py` — FileHandler config block (1 insertion)
- 5 WARNING→DEBUG: engine-empty in duckduckgo, google, lobsters, mojeek, semantic_scholar
- 3 WARNING→INFO: stack_exchange API key notice, filter_modes precedence notices (×2)
- 13 INFO→DEBUG: verbose crawler progress (crawl_site ×5, explore_site ×3), scraper chain traces (download_pdf ×2), scraper fast-path traces (scrape_url ×2, scrape_url_raw ×1)

## Future Considerations

MCP-server entry-point: if a `server.py` (MCP transport mode) is ever added, it would need the same FileHandler-only `basicConfig` at its startup path. The current config in `cli.py` covers only the CLI invocation path. `crawl_site.py` and `explore_site.py` standalone modes have their own `basicConfig(INFO, "%(message)s")` in `if __name__ == "__main__"` guards — these are intentional (standalone use, not CLI-routed) and unaffected.
