# First Capture Run — Analysis & Skill-Hardening Mapping (2026-06-01)

Roadmap step 2 (first end-to-end capture) executed: `docs.github.com/en/rest` (+ all enterprise versions) → collection `gh_reference` (307 files / 7146 chunks). Run succeeded but surfaced 2 bugs + 1 design gap + 1 worker-discipline issue. This file = analysis + concrete change mapping. Implementation pending (no skill edited yet).

## Run Result
- 309 discovered, 307 scraped, 2 thin dropped, 307 indexed, 7146 chunks, 51.8% nav-chrome stripped. Scrape 313s. Total ~150min (embedding-bound) — `index-dir` blocked RAG **globally for all projects** the whole time.
- Worker proxy log: `Monitor_CC/src/logs/api_requests_worker_3f66c773_capture-gh_reference_1780340723.jsonl`.
- Transcript tool (NEW, this session): `Monitor_CC/dev/tool_use_analysis/extract_transcript.py` → `/tmp/worker_transcript.md`. 60 tool_use (58 Bash, 1 Write, 1 Skill), 5 errors.

## Call-Count Analysis (fault-class reframe)
Ideal golden run ≈ **12–15 calls**; actual **60**. Split by class (legitimate-exploration vs methodology vs gross-blunder):
- **~15 calls induced by OUR bugs** (skill-load recovery 8 + venv hunt 7) — NOT worker fault.
- **~10 calls legitimate exploration** (3× `__NEXT_DATA__` key-path discovery — skill says "discover by inspection"; cleanup shape-diagnosis) — NOT fault.
- **~8–10 genuine worker faults:** polling-after-`& wait` (methodology, in scrape + index phases), run-before-write (Call 13 — no hook, runtime fail), Write-before-Read (Call 14 — caught by CC built-in Write guard).
Polling blunders already caught by `block_polling_loop.py` (Monitor_CC), purpose-built for this anti-pattern. Hook works; blocks post-hoc (costs a turn). True prevention = skill guidance, not a new hook.

## Root Causes
1. **Skill-load failure** — `Skill(skill="capture-and-index")` → "Unknown skill" in the worker's worktree session. REFUTED: not plugin-scope (searxng `@brunowinter-plugins: true` in `~/.claude/settings.json` enabledPlugins; both searxng skills load in main github session), not version (worker + main both CC 2.1.149, confirmed). Worktree-launch-specific. **ROOT CAUSE = MUST-FIX** — fresh-worker test then real fix. NO fallback (user directive 2026-06-01): the skill MUST load; a "read SKILL.md from cache" fallback is explicitly rejected (papering over the bug). W1 below is therefore DROPPED.
2. **Scrape-step venv path (BUG)** — `capture-and-index` skill Phase 2 (~line 97): `./venv/bin/python -m src.crawler.pipe_scraper` is plugin-relative. Plugin cache has NO venv; `./` resolves to the worktree cwd → fails. Source venv `/Users/.../MCP/searxng/venv/bin/python3` exists. Caused the ~7-call venv hunt (Calls 19–28). Stale note "finalized when src/ port lands" — port HAS landed: `src/crawler/pipe_scraper.py` (183 LOC, validated 316/316).
3. **No Opus-reviewed cull (DESIGN GAP)** — the prior worker post-crawl *content*-drop design (drops only empty/redirect/nav pages). Cannot cull "irrelevant-but-non-empty" pages (enterprise-admin / scim / actions vs our search / contents / git-trees focus) — that needs USER-CONTEXT the worker lacks. Result: 0 URLs dropped pre-scrape, 307 indexed incl. bloat → longer scrape+index, 2.5h global RAG block, diluted retrieval.

## Change Mapping

### capture-and-index skill (worker-side)
| # | Change | Class |
|---|---|---|
| C1 | Phase 2 scrape invocation: plugin-relative `./venv/bin/python` → absolute source venv. Either `cd /Users/.../MCP/searxng && ./venv/bin/python -m src.crawler.pipe_scraper ...` or `/Users/.../MCP/searxng/venv/bin/python -m src.crawler.pipe_scraper ...`. Delete stale "finalized when src/ port lands" note (port landed). | BUG |
| C2 | NEW cull-checkpoint between Phase 1 (pattern-noise cull, as today) and Phase 2 (Scrape): worker writes URL list, reports list name + /tmp path + **per-section counts**, STOPS. **Opus edits the shared `/tmp` list directly** (its own bash — cull patterns are domain-specific; the worker does NOT rewrite the list). Worker re-reads the shortened file and scrapes. Worker retains ONLY its autonomous post-scrape drop of small-byte noise/blocked MDs. | DESIGN FIX |
| C3 | Phase 2 + Index `& wait` blocks: add explicit "after `& wait` returns the process is DONE — do NOT add manual sleep/tail/ps/poll calls; the environment polling-loop hook blocks them and wastes turns." | DISCIPLINE FIX |
| C4 | Block-detection (cookie/paywall/JS-wall/captcha): fold a BROAD high-recall signature scan into the EXISTING Phase 3 diagnose pass (~0 extra calls). Phrase list deliberately OVER-catches — block text is fuzzy across domains, so a precise/evidence-based list wouldn't generalize anyway; the model is over-catch + verify, NOT precise-list. Phrase-match + small-byte-size = candidate. The diagnose script PRINTS the head (~15 lines) of each candidate in its own output → worker confirms real-block vs false-positive (docs page merely mentioning 'cookies'/'subscribe') from the already-returned output — no extra call unless the candidate set is large (= systemic block, itself the signal). Worker REPORTS confirmed-block count + examples to Opus. A confirmed block page is garbage → DELETE it (same as a thin page); NO content-strip script — a block is deleted, not stripped. Patterns are guidance in the skill, folded into the worker's diagnose script — NOT a separate module (standalone `block_detect.py` was built then reverted 2026-06-01, wrong placement). | DETECTION + REPORT, fold-in |

### web-research skill (Opus-side — Permanent Capture Workflow)
| # | Change | Class |
|---|---|---|
| ~~W1~~ | **DROPPED** — fallback to read the skill from cache REJECTED (user 2026-06-01: skill must load, no fallbacks). Skill-load fixed at root, not mitigated. | — |
| W2 | Document the Opus cull-review step at the checkpoint (review URL list vs user-need, return cull). Update worker prompt to instruct stop-after-discovery + report list path + per-section counts. | DESIGN FIX |

### Scripts
NO code changes NOW. `src/crawler/pipe_scraper.py` validated and fine. `block_polling_loop.py` covers the polling class — no new hook. The skill invocation path = C1 (a doc fix).
Block-detection is fold-in (worker's diagnose pass, phrases from the skill) — NO `src/` module and NO content-strip script. A confirmed block MD is deleted like a thin page. (`block_detect.py` was created 2026-06-01 then reverted — wrong placement; fold-in is the design.)

## Pending (not yet in mapping)
- Skill-load root cause (worktree launch) — fresh-worker test. W1 mitigates regardless of outcome.
- `gh_reference` re-capture leaner after the cull-checkpoint exists — user decision (re-index = another global RAG block).

## Evidence Sources
- Transcript: `Monitor_CC/dev/tool_use_analysis/extract_transcript.py` → `/tmp/worker_transcript.md`.
- Hook: `Monitor_CC/src/hooks/block_polling_loop.py`.
- Scraper: `searxng src/crawler/pipe_scraper.py`.
- Plugin enablement: `~/.claude/settings.json` enabledPlugins (`searxng@brunowinter-plugins: true`).
- Prior design: post-crawl content-drop decision (roadmap step 2 = this run).
