# Source Modules

Python packages for web search, scraping, crawling, and news ingestion. Utility script for spawning Claude Code workers.

## log_janitor.py

**Purpose:** 14-day log retention janitor. On-write trigger with 1h marker-throttled slow-path. Three public functions: `get_retention_days()` (env override), `maybe_prune_jsonl(log_path)` (ts-based JSONL filter + atomic rewrite), `maybe_prune_sidecars(sidecar_dir)` (mtime-based `.md` unlink). All failures logged as WARNING and swallowed. Called by `query_logger.py`, `scrape_logger.py`. `cli.py` imports `get_retention_days` for `TimedRotatingFileHandler` backupCount.
**Called by:** `src/search/query_logger.py`, `src/scraper/scrape_logger.py`, `cli.py`.

## tmux_spawn.sh

(from `src/spawn/`)

**Purpose:** Shell library for spawning Claude Code sessions in named tmux windows with an attached Ghostty terminal viewer. Supports both inline prompt and file-based prompt to avoid shell escaping issues.
**Input:** Sourced as a shell library (`source src/spawn/tmux_spawn.sh`), then called as functions.
**Output:** tmux pane ID on success; Ghostty window attached to the session.

### Functions

- `spawn_claude_worker SESSION NAME PROJECT_PATH MODEL TASK_PROMPT [EXTRA_FLAGS]` — Creates a new tmux window, waits for shell ready, launches `claude --model MODEL TASK_PROMPT` in the specified project directory, opens Ghostty viewer attached to the session. Returns pane ID.
- `spawn_claude_worker_from_file SESSION NAME PROJECT_PATH MODEL PROMPT_FILE [EXTRA_FLAGS]` — Like `spawn_claude_worker` but reads the task prompt from a file. Avoids shell escaping issues with complex multi-line prompts.
- `open_tmux_viewer SESSION [WINDOW_NAME]` — Opens a Ghostty window attached to a tmux session. Ghostty 1.3+: uses native AppleScript API. Ghostty 1.2.x: falls back to `open -na`.

### Usage

```bash
source src/spawn/tmux_spawn.sh
pane=$(spawn_claude_worker "workers" "my-task" "/path/to/project" "sonnet" "Fix the bug in foo.py")
pane=$(spawn_claude_worker_from_file "workers" "my-task" "/path/to/project" "opus" "/tmp/prompt.txt")
```

## Documentation Tree

- [search/DOCS.md](search/DOCS.md) — multi-engine search pipeline (10 active engines: Google, DuckDuckGo, Mojeek, Lobsters, Google Scholar, Semantic Scholar via pydoll; CrossRef, OpenAlex, Stack Exchange, Open Library via HTTP; parallel fanout, score-based snippet selection, slot-allocated 12 GENERAL / 6 ACADEMIC / 2 QA)
- [scraper/DOCS.md](scraper/DOCS.md) — URL scraping and site exploration tools
- [crawler/DOCS.md](crawler/DOCS.md) — BFS discovery (`crawl_site_workflow`) + capture-pipe scrape step (`pipe_scraper.py`)
- [news/DOCS.md](news/DOCS.md) — multi-platform news ingestion pipeline (discover → dedup → scrape → clean → publish to RAG); `python -m src.news` entry point
