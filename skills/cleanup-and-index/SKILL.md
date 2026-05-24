---
name: cleanup-and-index
description: Worker-side skill — clean raw markdown from web crawls or PDF conversions, then index into RAG. Two modes (web-md, pdf), three phases (Acquisition, Cleanup, Index).
---

# Cleanup-and-Index — Skill

Activated by a worker after Opus's web-research setup has produced four inputs: MODE (web-md or pdf), INPUT (URL list `.txt` or PDF path), COLLECTION (RAG collection name), and OUTPUT_DIR. Workflow: pick MODE, run Phase 0 → Phase 1 → Phase 2 in order.

Inputs are produced by Opus before spawning — see web-research SKILL § Permanent Capture Workflow → Setup for how INPUT, COLLECTION, and OUTPUT_DIR are determined.

---

### Mode 1: Web-MD Capture (search → crawl → clean → index)

Input: absolute path to a URL list `.txt` (one URL per line) OR a directory of pre-crawled `*.md` files.

- If URL list: Phase 0 crawls all URLs via Crawl4AI.
- If pre-crawled directory: skip Phase 0.

Pipeline: [optional crawl] → block-level chrome cleanup (5-shape + Sphinx-specifics) → index.

#### Phase 0 — Acquisition

```bash
mkdir -p $OUTPUT_DIR
cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/searxng && \
./venv/bin/python -m src.crawler.crawl_site \
    --url-file $INPUT \
    --output-dir $OUTPUT_DIR \
    --concurrency 10
```

Report: `N URLs crawled, M succeeded, K failed`. List failed URLs.

If `>50%` failed → STOP, report to Opus, do not proceed.

If INPUT is a directory of `.md` files: skip Phase 0, set `OUTPUT_DIR=INPUT`.

#### Phase 1 — Cleanup

Diagnose first. Don't write cleanup regex before classifying shape.

##### Diagnose Pass

Build a small script that scans ALL `.md` files in OUTPUT_DIR, extracts per-file fingerprints (h1 count, h2 count, prose density, table presence, source domain from `<!-- source: URL -->` comment, total LOC). Cluster by fingerprint similarity to identify 4-5 shape groups. ~50 LOC, ~5s runtime.

##### The Five Shapes

1. **Blog-Shape** — one h1 in first 20%, prose-heavy, h2 sections, footer markers (Continue reading / Comments / Copyright / breadcrumb).
   - Strip pre-h1 chrome + footer from earliest tail-marker.
   - Keep: source comment, h1 title, posted/updated metadata, ToC, body content.

2. **Paper-Landing-Shape** — academic title h1/h2, author list, abstract, metadata table (Subjects, DOI). Short overall.
   - Strip site nav, sidebar forms, "View PDF/HTML" link clusters, license footer.
   - Keep title, authors, abstract, subject table, DOI.
   - Variant: ACL Anthology uses `## [Title]` not `# Title` — anchor on first `## ` h2 if no h1.

3. **Forum-Thread-Shape** — markdown-table layout, top-nav row, story/comment rows.
   - Site-specific (HN: anchor on first `vote?id=` link, strip everything before).
   - Keep story title row + comment threads. Markdown-table syntax stays (embedding handles it).

4. **Repo-Heavy-Chrome-Shape** — very long pre-content chrome (>100 lines), many h1 chrome lines (search box, feedback, sponsor, repo headers), real title appears late.
   - GitHub issue/PR: extract `#<N>` from URL, find `^# .+ #<N>` line, strip everything before.
   - GitHub repo home: anchor on README's first h1 or file-tree end-marker.

5. **Index-Aggregator-Shape** — page is mostly link list, no real prose. Wikipedia category pages, blog index pages, doc TOC pages.
   - Flag as low-content. Optionally exclude from indexing (skip the file).

##### Web-Specific: Sphinx Documentation

Sphinx-generated docs (SearXNG, ReadTheDocs, many Python project docs) have a distinctive pattern. Header avg 10.7 lines, footer avg 52.6 lines, total noise ~37% of chars (verified on 278 files).

Header (top of file, before first `# ` heading):
- `### Navigation` block with index/modules/next/previous links
- Breadcrumb trail with `»` separators
- Strip: everything between `<!-- source:` line and first `# ` heading

Footer (after last content line):
- Logo image line: `[ ![Logo of ...](...) ](...)` — RELIABLE content-end marker
- `### [Table of Contents]`, `### Project Links`, second `### Navigation`, `### Quick search`, `### This Page`, `© Copyright`
- Strip: everything from `^\[ !\[Logo of ` to EOF

Inline noise (`_modules_*` files only): `[docs][](URL)` markers before class/function defs. Regex: `\[docs\]\[]\(https://[^)]*\)`.

##### Per-Shape Cleaner Pattern

For each detected shape, write ONE small script in `/tmp/clean_<shape>_<COLLECTION_lower>.py` (~20-30 LOC each). NOT one big function with N patterns.

##### Script Safety Rules (CRITICAL — previous runs failed here)

- Every `while` loop MUST increment in ALL code paths (skip/continue/break/normal — all)
- Test on 1 file FIRST, then run on all
- ALWAYS `python3` (not `python`)
- Use `Path(__file__).parent` — NEVER hardcode absolute paths like `/Users/...`
- Preserve `<!-- source: URL -->` comments in every file (they are crawl metadata)
- Overwrite originals in-place

##### Edge Cases

- Files with no `# ` heading (auto-generated redirect pages) → keep content between source comment and logo line
- Files nearly empty after cleanup (<5 lines) → still output, don't delete
- `user_None.md` / `user_{}.md` files = crawled error pages, minimal content expected

---

### Mode 2: PDF Capture (search → download → convert → clean → index)

Input: absolute path to a single PDF file OR a directory of `*.pdf` files.

Pipeline: MinerU convert → OCR/LaTeX cleanup → index.

#### Phase 0 — Acquisition

If INPUT is a single PDF file:

```bash
mkdir -p $OUTPUT_DIR
STEM="<derive descriptive PascalCase name from filename or first page>"
cd /Users/brunowinter2000/Documents/ai/Mineru && \
./venv/bin/python workflow.py convert \
    --input "$INPUT" \
    --output "$OUTPUT_DIR/$STEM.md"
```

If INPUT is a directory: loop over `*.pdf`, derive STEM per file (read first page or arxiv abstract if filename is cryptic), run convert per file. Report progress: `[N/M] <STEM>: phase 0 done`.

**Concrete loop template — use exactly this shape, including both guards:**

```bash
for PDF in "$PDF_DIR"/*.pdf; do
    STEM="<derive descriptive PascalCase name — see Note below>"
    # GUARD 1 — empty STEM means "$OUTPUT_DIR/.md" which silently overwrites every iteration
    [ -z "$STEM" ] && { echo "BUG: empty STEM for $PDF — abort batch"; exit 1; }
    cd /Users/brunowinter2000/Documents/ai/Mineru && \
        ./venv/bin/python workflow.py convert \
            --input "$PDF" \
            --output "$OUTPUT_DIR/$STEM.md"
    # GUARD 2 — convert may exit 0 but produce empty/missing output
    [ -s "$OUTPUT_DIR/$STEM.md" ] || { echo "WARNING: empty or missing output for $STEM"; }
done
```

Note on STEM derivation: cannot be `basename "$PDF" .pdf` mechanically — original filenames are often hashes, ISBN-strings, library-uploader patterns. Derive a descriptive PascalCase name per file: read the first page header / title metadata, condense to ~30 chars (e.g. `AslamMontague2001MetasearchModels`, `ManningRaghavanSchutze2008IRTextbook`). Filename collisions inside one batch must be avoided — append year or first-author-initial when needed.

**STEM character constraints (hard rules):** alphanumeric + underscore ONLY. NEVER include brackets `[ ]`, parentheses `( )`, dots `.` (other than the trailing `.md` extension), commas, spaces, or any glob metachar. MinerU's internal `find_output_md` uses the stem as a glob pattern; characters like `[10.1007_978-3-642-14267-3]` from DOI-style filenames get interpreted as character classes and produce zero matches. The `glob.escape()` patch in MinerU `workflow.py` (2026-05-08) covers this defensively, but the cleanest preventive is sanitizing the stem at derivation time.

**Why both guards matter:** an empty `$STEM` at line 4 produces output path `$OUTPUT_DIR/.md`. MinerU happily writes to it, exits 0, and the next iteration overwrites the same file. Without GUARD 1, ten papers collapse into one `.md` and the bug is invisible until the directory is listed. GUARD 2 catches the rarer case where MinerU silently produces an empty file — index-time would skip it without explanation.

**ZSH trap to know about — bash assoc-arrays don't transfer.** A natural-looking pattern is `declare -A STEMS; STEMS["MyFile.pdf"]="MyStem"; for f in *.pdf; do stem="${STEMS[$f]}"; ...; done`. This works in bash. In zsh (default macOS shell, default in worker tmux sessions) `${STEMS[$f]}` does NOT expand when the key contains `.` or `-` — `$stem` silently becomes empty, GUARD 1 fires, and the batch aborts. Two safer patterns:

1. **Python script for any batch >3 files** (recommended): zero shell-quoting risk, easy to add per-file timing/error handling, single tool-call per batch. Build a small `subprocess.run([...])` loop over a `dict[str, str]` of `pdf_basename → stem` mappings.
2. **Bash-only loop with literal stems** (small batches): write the STEM literally inside the loop body per file, avoid associative arrays entirely.

Do NOT carry a bash assoc-array pattern into a zsh worker session expecting it to work — the GUARD will catch it but the whole batch is wasted.

If MinerU fails for any PDF: log + skip + continue. Report failed PDFs at end.

##### Background-Polling for Phase 0 Convert

Use this pattern whenever **any** of the following is true:
- Input PDF is >50 MB
- Batch over all PDFs in a directory (loop template above)
- Single PDF and wallclock is expected to exceed 60 s (rule of thumb: any academic paper >10 MB, any book PDF)

```bash
# Run as Bash(run_in_background=true)
( while pgrep -f 'workflow.py convert' > /dev/null 2>&1; do sleep 15; done; echo CONVERT_DONE ) &
wait
```

The `sleep 15` *inside* the loop is normal blocking sleep — it does NOT trigger CC tool-completion events. CC sees ONE backgrounded call, ONE completion when MinerU is truly gone. Zero cascade. Mirror of the Phase 2 indexing pattern.

##### Post-Convert Verify

After every convert (single file or end of batch loop), verify the output is non-empty and substantial:

```bash
[ -s "$OUTPUT_DIR/$STEM.md" ] && wc -w "$OUTPUT_DIR/$STEM.md"
```

Threshold: **≥ 100 words** = meaningful conversion. Below threshold:
- Log `WARNING: $STEM.md has <N> words — expected ≥100`
- Retry: add `--timeout 300` (or higher) to the `workflow.py convert` call
- If retry also fails: skip file, add to failed list, continue batch

##### Why Background-Polling for Convert

Claude Code auto-backgrounds any Bash call whose wallclock exceeds ~60 s AND whose output stream has been idle for >30 s. MinerU convert on large PDFs routinely meets both conditions — it's CPU-bound and silent during the OCR/LaTeX extraction phase.

**What happens without the polling pattern:**

1. Worker fires `Bash(workflow.py convert --input paper.pdf --output out.md)` with output redirected to a log file.
2. CC sees process running, output stream quiet → auto-backgrounds the call.
3. Bash tool-result returns immediately with exit code 0 (CC's backgrounding exit, NOT MinerU's exit).
4. Worker reads exit=0 → assumes convert succeeded, moves to Phase 1 cleanup.
5. MinerU is still running in the background (or was killed by CC). The `.md` output file is empty or partially written.
6. GUARD 2 in the batch loop (`[ -s "$OUTPUT_DIR/$STEM.md" ]`) fires — but only if the worker revisits the file. If the worker already reported "Phase 0 done" and moved on, the empty file silently enters Phase 1.

**What the polling pattern does:** CC sees ONE backgrounded Bash call. `wait` blocks until `pgrep -f 'workflow.py convert'` finds no process. Only then does `echo CONVERT_DONE` fire. Worker receives ONE completion notification after MinerU is truly gone, then runs the post-convert verify.

#### Phase 1 — Cleanup

PDFs come from MinerU as Markdown. Cleanup focuses on inline OCR artifacts, not block chrome.

##### Pre-cleanup: Backup + Word Count Baseline

```bash
cp "$OUTPUT_DIR/$STEM.md" "/tmp/backup_$STEM.md"
wc -w "$OUTPUT_DIR/$STEM.md"
```

##### Artifacts to Detect and Fix

- **LaTeX spaced** — `\ f r a c`, `\ s u m`, `\ m a t h r m` → `\frac`, `\sum`, `\mathrm`
- **Broken images** — `! [ ] ( ... )` with spaces between chars → `![](...)`
- **Split words** — "mod els", "alg orithm" — fix conservatively via dictionary check (`/usr/share/dict/words` or in-document vocabulary)
- **HTML entities** — `&amp;`, `&#39;` → unescape
- **Encoding artifacts** — UTF-8 mojibake (Ã©, Ã¤) → re-encode
- **Hyphenated line-end splits** — `comput-\ner` → `computer` (only when both halves are dictionary words)
- **Run-on duplicate headers** — Line N is garbage run-on, Line N+1 is correct → DELETE the garbage line

##### Per-Issue Script Pattern

For each issue type, create `/tmp/fix_<issue>_<STEM>.py`. Run, verify count reaches 0 for that issue, move to next. NOT one mega-script.

##### Validation (MANDATORY after each fix)

- Word count must be stable (+/- 1%)
- Check for run-on words (iscentral, tothe, ofthe) — must remain 0
- If word count drops >2% OR run-on words appear: ABORT, restore from backup, report

##### Stop Criteria — "Good Enough"

The pipeline downstream is: convert → clean (this phase) → embedding/index. Embedding handles small residual noise. Don't over-engineer.

Stop when:
- All known issue categories have 0 remaining matches in the file
- Word count is stable
- Spot-check 10-15 lines from the middle reads as natural text

---

### Phase 2 — Index (both modes)

Identical for both modes. Run as background job with `PYTHONUNBUFFERED=1` so the worker stays responsive (foreground would block on the long-running embed phase) and the log fills line-by-line for post-mortem if needed.

#### Skip-Logik (since 2026-05-08)

`workflow.py index-dir` is **skip-by-default**. Per file the SHA256 of the content is compared against the `indexed_files` tracking table:

- **skipped** — hash matches an existing entry → no work, no GPU touch
- **adopted** — file not in `indexed_files`, but a complete chunk set exists in `documents` (COUNT == MAX(total_chunks)) → register hash without re-embed (one-time bootstrap for collections that pre-date hash tracking)
- **indexed** — missing, partial, or hash-changed → chunk + embed + insert + register hash

Concretely: re-running `index-dir` on a directory where 14 of 168 files are new now indexes the 14, registers hashes for the 154 unchanged ones, and exits in seconds — not the previous full re-embed of all 168.

GPU servers are only started when there is real work to embed.

#### Pre-run: detect partial chunks from prior killed runs

A killed run can still leave partial chunks (e.g. abort happened mid-document insert). The skip-logic does NOT catch this case — partial documents are detected via the `total_chunks` mismatch, but the hash entry was never written for the killed file, so on re-run it lands in the **indexed** bucket and gets cleanly re-done. So the only scenario that needs manual intervention is a partial document whose hash was somehow already registered.

Check first:

```bash
rag-cli progress "$COLLECTION"
```

Any document showing `done < total` was interrupted mid-write. If you see one AND its hash is in `indexed_files`, delete the partial chunks so the re-run treats it as missing:

```bash
rag-cli delete --collection "$COLLECTION" --document "<doc>.md"
```

Don't pass `--remove-source` — the `.md` is fine, only the partial DB rows need to go. The next `index-dir` will treat the file as missing and re-index from scratch.

#### Run indexing

For multiple files (typical case — directory with N new + M existing):

```bash
cd ~/Documents/ai/Meta/ClaudeCode/MCP/RAG && \
PYTHONUNBUFFERED=1 ./venv/bin/python workflow.py index-dir \
    --input "$OUTPUT_DIR" --collection "$COLLECTION" \
    > /tmp/${COLLECTION}_index.log 2>&1 &
```

Skip-logic handles "only re-index new/changed files" automatically.

For an explicit single-file workflow (e.g. recovery of one specific document, or scripted per-file loops):

```bash
./venv/bin/python workflow.py index-file \
    --input "$OUTPUT_DIR/specific_paper.md" --collection "$COLLECTION"
```

`--force` is available on both subcommands and bypasses the skip — use only when the embedding model or chunker config changed and the entire collection genuinely needs re-embedding. Routine indexing should never need `--force`.

This handles: server health check → start if needed → classify (skip/adopt/index) → chunk + embed only the indexed bucket → summary.

#### Wait for indexing to finish — match timer duration to expected wallclock

**Lock awareness**: The indexer holds a global RAG lock for its full duration (written to `~/.rag-locks/rag.lock`). Any `rag-cli` command other than `status` will fail with "rag busy" while the lock is held. **Do NOT call `rag-cli progress` while the indexer is running** — it would hit a DB query blocked by indexer DDL/write locks and hang (this was the root cause of the zombie-process bug). Use `rag-cli status` instead to check mid-run progress — it reads the lockfile directly, no DB query.

Indexing takes 30–90 minutes for typical book-sized collections. The default polling pattern `sleep 60 && rag-cli progress` is the single most expensive anti-pattern in worker orchestration: each `Bash(run_in_background=true)` completion arriving while an API stream is open fires a new REQ, cancels the in-flight stream client-side, and gets billed input + cache-read. A 60-minute index with 60s polls = ~60 cascade events. **Never** set a short timer for a long-running job.

Two correct patterns, depending on whether anything follows the indexer:

**A) Indexing is the last work step before the completion checklist** — wait passively. ONE backgrounded bash fires ONE completion when the indexer is gone:

```bash
# Run as Bash(run_in_background=true)
( while pgrep -f 'workflow.py index-dir' > /dev/null 2>&1; do sleep 30; done; echo INDEXING_DONE ) &
wait
```

The `sleep 30` *inside* the loop is normal blocking sleep — it does NOT trigger CC tool-completion events. CC sees ONE backgrounded call, ONE completion at the very end. Zero cascade.

**B) More steps follow after the indexer (e.g. sample-query verification, cleanup pass on an output dir)** — set ONE timer that approximates the expected remaining wallclock. **The timer duration must match the work, not a default like 60–120s.** For a 29-minute remaining run, set the timer to ~25 minutes. ONE completion fires, then check `rag-cli status` (lock free = done; still held = still running + shows progress). If more time needed, set another sized-to-remaining timer. Never fire 14 short timers for a single long run.

If the user asks "how far?" at any moment, do ONE manual `rag-cli status` in foreground — shows document progress from the lockfile with no DB query. The anti-pattern is *automated repeated short polling*, not a single user-triggered status read.

After indexing completes (lock released, `rag-cli status` shows FREE), run the post-checks:

```bash
rag-cli progress "$COLLECTION"          # all docs must show done == total (safe: lock is free)
tail -30 /tmp/${COLLECTION}_index.log    # confirm "Done: N files indexed (X chunks), Y skipped, Z adopted"
```

**Output shape of `rag-cli progress`:**

```
Indexing Progress: <COLLECTION>

  Document                  Done / Total       %  Status
  doc_a.md                   579 / 579    100.0%  done
  doc_b.md                  1248 / 1390    89.8%  in-progress
  doc_c.md                     0 / 0        0.0%  ...   (not yet started — won't appear)
```

A document is currently being indexed when its row shows `done < total`. Documents not yet started don't appear in the table at all. Documents with `done == total` are committed.

#### Failure check (after indexing done)

```bash
tail -20 /tmp/${COLLECTION}_index.log
```

Confirm the summary line `Done: N files indexed (X chunks), Y skipped, Z adopted` — N+Y+Z must equal the total number of `.md` files found. Cross-check with `rag-cli progress` — every document should show `done == total` (call only after lock is free). NULL-embedding skips are logged at WARNING level in `src/rag/logs/indexer.log` (search for `NULL embedding skipped`); investigate via the indexer log before treating the collection as complete if any are present.

#### Verify

```bash
cd ~/Documents/ai/Meta/ClaudeCode/MCP/RAG && \
./venv/bin/python workflow.py search \
    --query "<topic from collection content>" \
    --top-k 3
```

Top result should be a chunk from the just-indexed collection.

---

### Completion Report

Output back to Opus when done:

```
CLEANUP-AND-INDEX REPORT
=========================
Mode:             [web-md | pdf]
Collection:       <COLLECTION>
Input:            <INPUT path> (N items)
Phase 0:          [crawl: M ok, K failed | convert: M ok, K failed]
Cleanup shapes:   [shape: file_count, ...]  (web-md only)
Cleanup issues:   [issue: count, ...]       (pdf only)
Char reduction:   X% total                  (web-md)
Word stability:   ±Y%                       (pdf)
Indexed:          N chunks across M documents
Verification:     query "<q>" → top result snippet (~50 chars)
Status:           [Success | Issues — describe]
```

End with this report. STOP. No commit needed (output is data files, not code).

---

### Anti-Patterns (both modes)

- One mega-script with N regex patterns instead of per-shape/per-issue small scripts
- Treating `strip%` (web-md) or `% removed` (pdf) as a quality metric — bytes-out vs bytes-in says nothing about indexability
- Hardcoded absolute paths in cleanup scripts
- Infinite loops — every `while` MUST increment in all paths
- Skipping the backup step (pdf mode) — restore is impossible without it
- Skipping spot-check after cleanup — strip% can lie, eyeballing 2-3 files catches over-strip
