---
name: capture-and-index
description: Worker-side skill — discover URLs agentic (worker writes /tmp scripts), select which to scrape, scrape raw/maximal, clean (incl. post-scrape noise drop), and index into RAG. Modes: web-md (Discovery→Select→Scrape→Cleanup→Index), pdf (Acquisition→Cleanup→Index).
---

# Capture-and-Index — Skill

---

### Mode 1: Web-MD Capture (discovery → select → scrape → clean → index)

Pipeline: Discovery → URL Selection (pre-scrape) → Scrape (raw) → Cleanup (incl. post-scrape drop) → Index.

#### Phase 0 — Discovery

Deliverable: `/tmp/<domain>_discovered_urls.txt` — one URL per line, maximum coverage of the target domain/section.

Write your discovery scripts to `/tmp` — no pinned reference script. Choose the path below based on structural signals from the seed page. **Any errors during discovery (HTTP failures, 429s, blocked fetches) MUST be recorded for the Completion Report** — they distinguish complete coverage from coverage the site blocked.

##### Step 0 — Structural Signals (always, ~30s)

Fetch the seed page HTML (plain HTTP, no browser). Check:

- `/sitemap.xml` and `/sitemaps/sitemap-0.xml` — does one exist?
- `<script id="__NEXT_DATA__">` in the raw HTML — signals Next.js SSR (see Path A).

`robots.txt` is NOT consulted — we capture every URL that matters to us regardless of disallow rules.

##### Path A — `__NEXT_DATA__` Extraction (Next.js SSR sites, preferred)

Applicable when: `<script id="__NEXT_DATA__">` found in seed HTML.

No browser needed — the full nav tree is in the initial SSR HTML.

**Procedure:**

1. Parse the `__NEXT_DATA__` JSON blob from the seed page.
2. Walk any field containing `childPages`, `items`, or `navigation` keys paired with `href` or `url` strings — that is the nav tree. Key path is site-specific — discover by inspection (grep the blob for fields containing `childPages`/`href` pairs; do NOT assume `props.pageProps.mainContext.sidebarTree`).
3. Collect all URL strings matching the target section/domain from the primary nav (latest / free-pro-team / main version).
4. Check for an `allVersions`, `versions`, or equivalent version-list field in the blob. For EACH version:
   - Construct the version-scoped root URL.
   - Fetch it via plain HTTP.
   - Extract its nav tree (same walk logic).
   - Normalize version-prefixed URLs to canonical form (strip the version segment: `/de/enterprise-cloud@latest/rest/X` → `/de/rest/X`).
   - Union into the main set.
5. **Always check the OLDEST version.** Deprecated pages are removed from newer versions' sidebars but persist in the oldest, and their pages still return HTTP 200. Missing the oldest version means missing deprecated content — this pattern recurs on any versioned doc site.
6. Write the normalized union to `/tmp/<domain>_discovered_urls.txt`.

**Expected outcome:** 100% of pages appearing in ANY version's sidebar, in ~1–5s (O(versions) HTTP fetches, no browser).

**Sitemap-coverage trap:** if the site also exposes a sitemap, verify it covers the target section (spot-check ≥5 known pages against the sitemap) before trusting it as an alternative. Sitemaps are often root-only or homepage-only even on sites where `__NEXT_DATA__` yields full coverage.

##### Path B — Sitemap (non-Next.js, sitemap exists and is verified)

Applicable when: sitemap found AND spot-check confirms it covers the target section adequately.

Fetch and parse the sitemap; filter to target section URLs; write to `/tmp/<domain>_discovered_urls.txt`.

##### Path C — Playwright BFS (fallback — no `__NEXT_DATA__`, no usable sitemap)

Applicable when: neither Path A nor Path B applies.

Write a /tmp BFS script using `crawler.arun()` per frontier URL; extract `result.links.internal` from the fully rendered DOM. Config:

```python
wait_until = "domcontentloaded"
delay_before_return_html = 3.0   # the one genuine time↔completeness dial
page_timeout = 15000             # load ceiling; does NOT add to delay
concurrency = 1                  # WAF-safe default
```

429 policy: back off 5s once; stop if second consecutive batch also 429 — report `stop_reason="429_persistent"`. No retry loops.

**Known ceiling:** sites with section-scoped navigation (sidebar shows only the current section's nav, not a global tree) produce a structural recall ceiling regardless of rendering quality. `stop_reason="frontier_exhausted"` means all link-reachable pages found; orphan pages (never linked from anywhere) are an inherent BFS blind spot.

Write discovered URLs to `/tmp/<domain>_discovered_urls.txt`.

#### Phase 1 — URL Selection (pre-scrape)

The cull happens on the URL LIST, before any scraping — not by reading scraped `.md` files. Inspect `/tmp/<domain>_discovered_urls.txt`, decide which URLs are obvious noise (e.g. changelog/archive/legal/asset paths, known-dead sections), and write a `/tmp` script that rewrites the list so only the URLs worth scraping remain.

Record which patterns were dropped and why — this goes into the Completion Report (`URLs dropped (pre-scrape, pattern): K — patterns + why`).

Do NOT read page content here; that is impossible pre-scrape. This step is purely list-level pattern selection.

#### Phase 1b — Opus Cull Review (MANDATORY STOP)

After the pattern-noise cull, the list still contains pages that are valid content but may be **irrelevant to what the user actually needs**. You (worker) cannot judge user-relevance — you lack the session context, and the cull is domain-specific. So you do NOT edit the list for relevance; you present, **Opus edits the `/tmp` file directly** (it is shared between sessions).

STOP here. Report to Opus:
- the URL-list path (`/tmp/<domain>_discovered_urls.txt`) and total count
- a **per-section breakdown**: group URLs by their first path segment under the target root, with counts — e.g. `rest/actions: 41 · rest/repos: 28 · rest/enterprise-admin: 35 · …`

Then WAIT. Opus strips the unwanted URLs from `/tmp/<domain>_discovered_urls.txt` itself (its own bash — the cull patterns are domain-specific). When Opus says go, re-read the now-shorter file and proceed to Phase 2 — do NOT modify the list yourself.

Do NOT scrape before Opus says go. Scraping the full list wastes scrape + index time, blocks RAG globally during indexing, and dilutes retrieval with irrelevant pages. This STOP is the single highest-leverage step for retrieval quality.

#### Phase 2 — Scrape

Scrape every URL in the filtered list **raw and maximal** — no content filter, no truncation. Cleanup strips chrome after the fact, but content not captured here is gone for good.

```bash
mkdir -p $OUTPUT_DIR
```

Run the pipe-scraper on the filtered list. It lives in the searxng SOURCE — the plugin **cache has NO venv**, so a plugin-relative `./venv/bin/python` resolves into the worktree and fails. Invoke via the absolute source path (so both the venv and the `src.crawler` module resolve) as a background-wait (scrapes of N>50 URLs exceed CC's auto-background threshold):

```bash
SEARXNG=/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/searxng
cd "$SEARXNG" && ./venv/bin/python -m src.crawler.pipe_scraper \
    --url-file /tmp/<domain>_discovered_urls.txt \
    --output-dir $OUTPUT_DIR > /tmp/<domain>_scrape.log 2>&1 &
( while pgrep -f 'pipe_scraper' > /dev/null 2>&1; do sleep 15; done; echo SCRAPE_DONE ) &
wait
```

> `src/crawler/pipe_scraper.py` is the validated production scraper (crawl4ai browser, raw markdown, Scrapy-style per-domain pacing — see `decisions/pipe_scraper.md`). When `wait` returns the scrape is DONE — read `/tmp/<domain>_scrape.log` ONCE for the summary line. Do NOT add manual `sleep`/`tail`/`ps`/poll calls between launch and the `wait` return — the environment's polling-loop hook blocks them and wastes turns.

The scraper's own output is short: a console line with **success count, error count, and total duration**, plus a full per-URL report written to `/tmp/<domain>_scrape_report.md` (per-URL status + outcome). It does NOT dump a per-URL list to the console — failures live in the report md and can be inspected there if needed.

Take from that console line for the Completion Report: scraped N, errors K, **duration T**. The error breakdown (429 / timeout / http_error) is already itemized in the scrape report md.

If `>50%` failed → STOP, report to Opus, do not proceed.

#### Phase 3 — Cleanup

Diagnose first. Don't write cleanup regex before classifying shape.

##### Diagnose Pass

Build a small script that scans ALL `.md` files in OUTPUT_DIR, extracts per-file fingerprints (h1 count, h2 count, prose density, table presence, source domain from `<!-- source: URL -->` comment, total LOC). Cluster by fingerprint similarity to identify 4-5 shape groups. ~50 LOC, ~5s runtime.

**Fold in — Block Detection (cookie / paywall / JS-wall / captcha).** The diagnose script already holds every file's content in memory — so ALSO match each file against a BROAD, high-recall block-signature list (it deliberately over-catches; block text is too fuzzy across domains for a precise list to generalize — over-catch + verify is the model). Case-insensitive substring set, extend freely:

```
cookie/consent : "accept cookies", "we use cookies", "cookie policy", "consent", "gdpr", "manage preferences"
paywall/sub    : "subscribe to", "sign in to continue", "members only", "create a free account", "register to read"
js/bot wall    : "enable javascript", "javascript is required", "verify you are human", "captcha", "checking your browser", "access denied"
```

A file is a CANDIDATE when it matches a signature AND is small (byte-size in the thin-page range — large matches are legit content merely mentioning the term). For every candidate, the diagnose script PRINTS its `<!-- source -->` URL + first ~15 lines into its own output — so you confirm real-block vs false-positive from the already-returned output, no extra call. If the candidate set is large (dozens+), that signals a systemic crawl block → STOP and report to Opus.

A confirmed block page is garbage → **DELETE it** (same as a thin page) — no content-stripping. REPORT the confirmed-block count + example URLs in the Completion Report.

##### Post-Scrape Drop — thin successful pages (part of the diagnose pass)

Scrape gaps (429 / timeout / http_error) are already reported by the scraper — they never produced a usable `.md`. The only thing to analyse here are the **successful but very small** `.md` files (HTTP 200, tiny byte size): pages that scraped fine but genuinely carry little or no real content (stub, redirect landing, pure nav).

Delete those — they are thin/noise. Record the count for the Completion Report. There is no per-file content re-read of every page; only the small successful ones get this look.

The two numbers stay separate in the report: scrape errors come from the scraper, thin/noise comes from this check. Together they tell us whether a dropped URL was a scraper problem or just an empty page.

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
- After cleaning, spot-check 2-3 files — strip% can lie; eyeballing catches over-strip

##### Edge Cases

- Files with no `# ` heading (auto-generated redirect pages) → keep content between source comment and logo line
- Files nearly empty after cleanup (<5 lines) → still output, don't delete
- `user_None.md` / `user_{}.md` files = crawled error pages, minimal content expected

---

### Mode 2: PDF Capture (download → convert → clean → index)

Input: absolute path to a single PDF file OR a directory of `*.pdf` files.

Pipeline: Acquisition → Cleanup → Index.

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

The `sleep 15` *inside* the loop is normal blocking sleep — it does NOT trigger CC tool-completion events. CC sees ONE backgrounded call, ONE completion when MinerU is truly gone. Zero cascade.

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

### Index — Final Phase (both modes)

One script call. `index-dir` is incremental (hash-based skip) — re-running only embeds new/changed files; existing chunks are never touched or re-embedded.

```bash
cd ~/Documents/ai/Meta/ClaudeCode/MCP/RAG && \
PYTHONUNBUFFERED=1 ./venv/bin/python workflow.py index-dir \
    --input "$OUTPUT_DIR" --collection "$COLLECTION" \
    > /tmp/${COLLECTION}_index.log 2>&1 &
( while pgrep -f 'workflow.py index-dir' > /dev/null 2>&1; do sleep 30; done; echo INDEXING_DONE ) &
wait
```

The script prints per file `Indexed <doc> -> N chunks` and a final summary line:

```
Done: N files indexed (X chunks), Y skipped, Z adopted
```

Report `N` (files indexed) and `X` (chunks) from that line — `N` is the **final md** count for the Completion Report.

When `wait` returns, indexing is DONE — read `/tmp/${COLLECTION}_index.log` ONCE for the summary line. Do NOT manually poll the log or process between launch and the `wait` return (no `sleep`/`tail`/`ps`/`until pgrep` loops) — the environment's polling-loop hook blocks them and wastes turns. Indexing blocks RAG globally for ALL projects while it runs — one more reason not to busy-wait around it.

No separate verify step inside the pipe: the real verification is the research done on the indexed data back in the main session, not a query here.

---

### Completion Report

Output back to Opus when done.

**web-md — the funnel:**

```
URLs discovered:                    N
URLs dropped (pre-scrape, pattern): K    — which patterns + why
URLs scraped:                       N − K
Scrape:                             M ok, E errors   ·   duration: T   (errors itemized in /tmp scrape report md)
md dropped (post-scrape, thin):     D
blocks detected (cookie/paywall):   B    — confirmed real-block MDs + example URLs (NOT auto-stripped)
Final md indexed:                   M − D
Collection:                         <COLLECTION>
```

Keep the two drop reasons separate: scrape errors **E** come from the scraper (a scraper/WAF gap), thin/noise **D** comes from the cleanup check (pages that scraped fine but carry no content). Together they tell us whether the scraper has gaps or the URLs were just empty.

**pdf:** `convert: M ok, K failed` · `cleanup issues: [...]` · `indexed: N chunks across M documents`.

End with this report. STOP. No commit needed (output is data files, not code).