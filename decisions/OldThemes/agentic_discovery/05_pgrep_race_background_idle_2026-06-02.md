# pgrep-Race → background+idle Orchestration (2026-06-02)

Continuation of `04_first_capture_run_analysis_2026-06-01.md`. Triggered by the GitHub GraphQL-docs capture run (Mode web-md, collection `gh-cli-reference`).

## Problem observed

Capture skill Phase 2 (Scrape) — and identically Index-Final + PDF-Convert — detected completion via a poll-loop:

```bash
... pipe_scraper ... &
( while pgrep -f 'pipe_scraper' > /dev/null 2>&1; do sleep 15; done; echo SCRAPE_DONE ) &
wait
```

On the GraphQL run the `pgrep -f 'pipe_scraper'` stopped matching while the scraper was still running (crawl4ai drives a headless browser as a separate process tree; the matchable launcher was not continuously visible). Effect: the completion signal fired early / `wait` returned early → worker mis-reported "Still alive at 33/42, wait returning early" repeatedly → confused manual PID-poll loop → wasted turns.

**No data harm.** The scrape actually completed (`/tmp/..._scrape.log`: `Scraped 42/42 ok, 0 errors`); the index content is clean + complete (verified: 0 site-chrome files, `deleteIssue`/`DeleteIssueInput`/`clientMutationId` present). Only the worker's STATUS reporting was garbled — the pipeline output was correct.

## Decision

Remove the pgrep poll-loop everywhere (scrape, index, pdf-convert). New model:

- **Worker self-wake:** launch the long task as a background Bash call (`run_in_background=true`), go idle. CC's background-completion notification wakes the WORKER's own session; it reads the log ONCE and continues autonomously to the next phase. No pgrep, no name-poll, no `wait`-loop.
- **Opus 2-touch-points (web-research skill):** Opus intervenes at exactly two points — (1) hand the culled `/tmp` URL list + go (Phase 1b cull), (2) receive the final funnel report. Between them Opus does NOTHING: no log-checking, no `rag-cli status` polling, no waking the worker. The worker owns Scrape → Cleanup → Index end-to-end.

Rationale: polling a process *name* is fragile for a browser-driving scraper; the worker's own background-completion notification is the reliable signal, and Opus has no business monitoring mid-pipeline.

## Also fixed this session

Stale absolute paths in both skills (the `MCP/*` tree does not exist on this machine):
- indexer `MCP/RAG/workflow.py` → `cli/rag-cli/workflow.py`
- scraper `MCP/searxng` → `cli/searxng-cli`

## Open / untested

The background+idle model is NOT yet run end-to-end. This session's GraphQL capture used the OLD poll-loop skill (the one that hit the race). A fresh capture run on the new model is needed to confirm CC's background-completion reliably wakes the worker between every phase (Scrape→Cleanup→Index) without Opus involvement.
