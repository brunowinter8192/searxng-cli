---
name: searxng-cli-capture-and-index
description: Discover URLs agentically (write /tmp scripts), select which to scrape, scrape raw/maximal, clean (incl. post-scrape noise drop), and index into RAG. Modes: web-md (Discovery→Select→Scrape→Cleanup→Index), pdf (Acquisition→Cleanup→Index).
---

# Capture-and-Index — Skill

---

### Mode 1: Web-MD Capture (discovery → select → scrape → clean → index)

Pipeline: Discovery → URL Selection (pre-scrape) → Scrape (raw) → Cleanup (incl. post-scrape drop) → Index.

**Scraper posture — best-effort, not guaranteed.** `src/crawler/pipe_scraper.py` is a GENERAL scraper; do NOT assume the scrape worked. Coverage verification is a first-class duty: every discovered URL that survives the cull must actually yield real content. On ANY systemic, diagnosable problem — a patterned coverage gap, a repeating block-type, a dominant error class (NOT scattered legit 404s) — STOP, do not push a half-broken capture into indexing, and report the IDENTIFIED problem to Opus: what fails, the evidence, your read of the cause. Iterate from there (different wait strategy, per-URL isolation, stealth, a per-site discover tweak — then re-run). The `>50%` / dozens-of-blocks thresholds below are hard floors, not the bar — a clearly-diagnosed problem warrants a STOP even under them.

#### Phase 0 — Discovery

Deliverable: `/tmp/<domain>_discovered_urls.txt` — one URL per line, maximum coverage of the target domain/section.

Write your discovery scripts to `/tmp` — no pinned reference script. Choose the path below based on structural signals from the seed page. **Any errors during discovery (HTTP failures, 429s, blocked fetches) MUST be recorded for the Completion Report.**

##### Step 0 — Structural Signals (always, ~30s)

Fetch the seed page HTML (plain HTTP, no browser). Check:

- `/sitemap.xml` and `/sitemaps/sitemap-0.xml` — does one exist?
- `<script id="__NEXT_DATA__">` in the raw HTML — signals Next.js SSR (see Path A).

`robots.txt` is NOT consulted.

##### Path A — `__NEXT_DATA__` Extraction (Next.js SSR sites, preferred)

Applicable when: `<script id="__NEXT_DATA__">` found in seed HTML.

No browser needed.

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
5. **Always check the OLDEST version** (same walk: construct its root URL, extract nav, union in).
6. Write the normalized union to `/tmp/<domain>_discovered_urls.txt`.

**Expected outcome:** 100% of pages appearing in ANY version's sidebar, in ~1–5s.

**Sitemap-coverage trap:** if the site also exposes a sitemap, verify it covers the target section (spot-check ≥5 known pages against the sitemap) before trusting it as an alternative.

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

`stop_reason="frontier_exhausted"` means all link-reachable pages were found.

Write discovered URLs to `/tmp/<domain>_discovered_urls.txt`.

#### Phase 1 — URL Selection (pre-scrape)

The cull happens on the URL LIST, before any scraping — not by reading scraped `.md` files. Inspect `/tmp/<domain>_discovered_urls.txt`, decide which URLs are obvious noise (e.g. changelog/archive/legal/asset paths, known-dead sections), and write a `/tmp` script that rewrites the list so only the URLs worth scraping remain.

Record which patterns were dropped and why — this goes into the Completion Report (`URLs dropped (pre-scrape, pattern): K — patterns + why`).

Do NOT read page content here; that is impossible pre-scrape. This step is purely list-level pattern selection.

#### Phase 1b — Opus Cull Review (MANDATORY STOP)

After the pattern-noise cull, the list still contains pages that are valid content but may be **irrelevant to what the user actually needs**. Do NOT edit the list for relevance; present it, and **Opus edits the `/tmp` file directly**.

STOP here. Report to Opus:
- the URL-list path (`/tmp/<domain>_discovered_urls.txt`) and total count
- a **per-section breakdown**: group URLs by their first path segment under the target root, with counts — e.g. `rest/actions: 41 · rest/repos: 28 · rest/enterprise-admin: 35 · …`

Then WAIT. Opus strips the unwanted URLs from `/tmp/<domain>_discovered_urls.txt` itself. When Opus says go, re-read the now-shorter file and proceed to Phase 2 — do NOT modify the list yourself.

Do NOT scrape before Opus says go.

#### Phase 2 — Scrape

Scrape every URL in the filtered list **raw and maximal** — no content filter, no truncation.

```bash
mkdir -p $OUTPUT_DIR
```

Launch the pipe-scraper as a **background Bash call** (`run_in_background=true`), then go idle. Invoke via the absolute source path:

```bash
SEARXNG=/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/searxng-cli
cd "$SEARXNG" && ./venv/bin/python -m src.crawler.pipe_scraper \
    --url-file /tmp/<domain>_discovered_urls.txt \
    --output-dir $OUTPUT_DIR > /tmp/<domain>_scrape.log 2>&1
```

> You own Scrape → Cleanup → Index end-to-end — never hand back to Opus mid-pipeline. After launch, go idle; do NOT `pgrep`/name-poll/`wait`-loop. When the run completes, read `/tmp/<domain>_scrape.log` ONCE for the `Scraped N/N ok` summary, then continue on your own to Cleanup → Index → final report.

The scraper's own output is short: a console line with **success count, error count, and total duration**, plus a full per-URL report written to `/tmp/<domain>_scrape_report.md` (per-URL status + outcome). It does NOT dump a per-URL list to the console — failures live in the report md.

Take from that console line for the Completion Report: scraped N, errors K, **duration T**. The error breakdown (429 / timeout / http_error) is already itemized in the scrape report md.

**Coverage gate — verify, don't assume.** Compare the scrape outcome against the cull-survived URL list — every URL should have yielded a usable body. `>50%` failed → STOP, report to Opus, do not proceed. STOP below that threshold too when the shortfall is SYSTEMIC and diagnosable: one block-type or error class hitting a coherent slice of URLs (e.g. all article pages regwalled while index pages pass). Report the identified problem to Opus — what failed, the evidence (block text / coverage delta / error breakdown), the suspected cause — and iterate; do NOT carry a patterned gap into Cleanup/Index. Scattered legit 404s / thin pages are NOT a stop — those flow to the post-scrape drop.

#### Phase 3 — Cleanup

Diagnose first. Don't write cleanup regex before classifying shape.

##### Diagnose Pass

Build a small script that scans ALL `.md` files in OUTPUT_DIR, extracts per-file fingerprints (h1 count, h2 count, prose density, table presence, source domain from `<!-- source: URL -->` comment, total LOC). Cluster by fingerprint similarity to identify 4-5 shape groups. ~50 LOC, ~5s runtime.

**Fold in — Block Detection (cookie / paywall / JS-wall / captcha).** In the same diagnose pass, ALSO match each file against a BROAD, high-recall block-signature list (case-insensitive substring set, extend freely):

```
cookie/consent : "accept cookies", "we use cookies", "cookie policy", "consent", "gdpr", "manage preferences"
paywall/sub    : "subscribe to", "sign in to continue", "members only", "create a free account", "register to read"
js/bot wall    : "enable javascript", "javascript is required", "verify you are human", "captcha", "checking your browser", "access denied"
```

A file is a CANDIDATE when it matches a signature AND is small (byte-size in the thin-page range). For every candidate, the diagnose script PRINTS its `<!-- source -->` URL + first ~15 lines into its own output — confirm real-block vs false-positive from that output. If the candidate set is large (dozens+) → STOP and report to Opus.

A confirmed block page is garbage → **DELETE it** (same as a thin page) — no content-stripping. REPORT the confirmed-block count + example URLs in the Completion Report.

##### Post-Scrape Drop — thin successful pages (part of the diagnose pass)

Scrape gaps (429 / timeout / http_error) are already reported by the scraper. The only thing to analyse here are the **successful but very small** `.md` files (HTTP 200, tiny byte size): pages that scraped fine but carry little or no real content (stub, redirect landing, pure nav).

Delete those. Record the count for the Completion Report. Re-read only the small successful files, not every page.

The two numbers stay separate in the report: scrape errors come from the scraper, thin/noise comes from this check.

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
   - Keep story title row + comment threads. Markdown-table syntax stays.

4. **Repo-Heavy-Chrome-Shape** — very long pre-content chrome (>100 lines), many h1 chrome lines (search box, feedback, sponsor, repo headers), real title appears late.
   - GitHub issue/PR: extract `#<N>` from URL, find `^# .+ #<N>` line, strip everything before.
   - GitHub repo home: anchor on README's first h1 or file-tree end-marker.

5. **Index-Aggregator-Shape** — page is mostly link list, no real prose. Wikipedia category pages, blog index pages, doc TOC pages.
   - Flag as low-content. Optionally exclude from indexing (skip the file).

##### Web-Specific: Sphinx Documentation

Sphinx-generated docs (SearXNG, ReadTheDocs, many Python project docs) have a distinctive pattern.

Header (top of file, before first `# ` heading):
- `### Navigation` block with index/modules/next/previous links
- Breadcrumb trail with `»` separators
- Strip: everything between `<!-- source:` line and first `# ` heading

Footer (after last content line):
- Logo image line: `[ ![Logo of ...](...) ](...)` — content-end marker
- `### [Table of Contents]`, `### Project Links`, second `### Navigation`, `### Quick search`, `### This Page`, `© Copyright`
- Strip: everything from `^\[ !\[Logo of ` to EOF

Inline noise (`_modules_*` files only): `[docs][](URL)` markers before class/function defs. Regex: `\[docs\]\[]\(https://[^)]*\)`.

##### Per-Shape Cleaner Pattern

For each detected shape, write ONE small script in `/tmp/clean_<shape>_<COLLECTION_lower>.py` (~20-30 LOC each). NOT one big function with N patterns.

##### Script Safety Rules (CRITICAL)

- Every `while` loop MUST increment in ALL code paths (skip/continue/break/normal — all)
- Test on 1 file FIRST, then run on all
- ALWAYS `python3` (not `python`)
- Use `Path(__file__).parent` — NEVER hardcode absolute paths like `/Users/...`
- Preserve `<!-- source: URL -->` comments in every file
- Overwrite originals in-place
- After cleaning, spot-check 2-3 files

##### Edge Cases

- Files with no `# ` heading (auto-generated redirect pages) → keep content between source comment and logo line
- Files nearly empty after cleanup (<5 lines) → still output, don't delete
- `user_None.md` / `user_{}.md` files = crawled error pages, minimal content expected

---

### Mode 2: PDF Capture (download → convert → clean → index)

Input: absolute path to a single PDF file OR a directory of `*.pdf` files.

Pipeline: Acquisition → Cleanup → Index.

#### Phase 0 — Acquisition

**Naming — PDFs carry speaking names, the md inherits them.** A source PDF must have a speaking
PascalCase name BEFORE conversion (e.g. `NadeauBengio2003InferenceGeneralizationError.pdf`). If a PDF
has a cryptic name (`6280358.pdf`, `2104.03667v1.pdf`, a libgen / Anna's-Archive string), RENAME it in
place first — derive the name from the first page / title metadata, sanitize per the char rules below.
The markdown then simply inherits the PDF's basename: `STEM = basename(PDF without .pdf)`, output =
`$OUTPUT_DIR/$STEM.md`. PDF name and md name stay identical.

##### Scan Check — BEFORE converting (cheap, do it first)

SCAN if EITHER condition is true (OR-logic; pdffonts is primary):

```bash
pdffonts "$PDF" | grep -iq "OCR" && echo SCAN   # OCR-layer font (e.g. HiddenHorzOCR) = scanned
pdftotext -f 5 -l 8 "$PDF" - | wc -w            # near-0 words = scanned
```

A high `pdftotext` word count does NOT rule out a scan — pdffonts is the decisive check.

If SCAN:

```bash
cd /Users/brunowinter2000/Documents/ai/Mineru
./venv/bin/python workflow.py convert --pdf "$PDF" --backend hybrid-engine --chunk-pages 100
```

Work dir: `Mineru/output/<stem>/`. Check all parts present via `Mineru/output/<stem>/parts.json`
(any `"md": null` = gap). Then:

```bash
# all parts present
./venv/bin/python workflow.py merge --stem "$STEM" --out-dir "$OUTPUT_DIR" --clean

# gap — re-run convert (fills only missing parts), then merge
./venv/bin/python workflow.py convert --pdf "$PDF" --backend hybrid-engine --chunk-pages 100
./venv/bin/python workflow.py merge --stem "$STEM" --out-dir "$OUTPUT_DIR" --clean
```

Then proceed to Job-Log Check and Phase 1.

##### Convert — one PDF per call

**Convert ONE PDF per `workflow.py convert` call, in a loop — NOT all PDFs in a single call.**
Output per PDF: `$OUTPUT_DIR/<stem>.md` (`stem = basename(PDF without .pdf)`).

`MINERU_PDF_RENDER_THREADS=1` is hard-wired in `workflow.py` — nothing to export.

A directory of PDFs (rename any cryptic ones first — see below) — loop, ONE call per PDF,
continue-on-failure (no `set -e`):

```bash
mkdir -p "$OUTPUT_DIR"
cd /Users/brunowinter2000/Documents/ai/Mineru
for pdf in "$PDF_DIR"/*.pdf; do
    echo "=== $(basename "$pdf") ($(date +%H:%M:%S)) ==="
    ./venv/bin/python workflow.py convert --pdf "$pdf" --out-dir "$OUTPUT_DIR"
done
```

A single PDF — pass just that one path:

```bash
./venv/bin/python workflow.py convert --pdf "$INPUT" --out-dir "$OUTPUT_DIR"
```

The lock allows at most one job at a time; a second concurrent call fails immediately with
exit 1. workflow prints only `job done` on success — per-PDF detail (output md, page/word counts)
goes to the job log, read in the Job-Log Check below, not to the console.

Note on naming a cryptic PDF: when a PDF's filename is not already speaking, derive a descriptive PascalCase name from the first page header / title metadata, condensed to ~30 chars (e.g. `AslamMontague2001MetasearchModels`, `ManningRaghavanSchutze2008IRTextbook`), and RENAME the PDF to it. Once the PDF carries a speaking name, `STEM = basename(PDF)` is correct and the md inherits it. Avoid filename collisions inside one batch — append year or first-author-initial when needed.

**STEM character constraints (hard rules):** alphanumeric + underscore ONLY. NEVER include brackets `[ ]`, parentheses `( )`, dots `.` (other than the trailing `.md` extension), commas, spaces, or any glob metachar. Sanitize the stem at derivation time.

`STEM = basename(PDF)` — no `pdf → stem` mapping table. Rename cryptic PDFs once, BEFORE the job runs.

A PDF that fails to convert surfaces in the job log with `md: null` (no output produced) → report
it to the user (PDF name). Do NOT auto-retry; the user decides whether to re-run.

##### Background Convert — launch + go idle

Launch the entire `for`-loop as a single background Bash call (`run_in_background=true`) and go
idle. Do NOT `pgrep`/name-poll/`wait`-loop. When the loop has attempted every PDF, run the
Job-Log Check.

##### Job-Log Check — read after the loop

Each normal `workflow.py convert` call appends 2 lines to
`/Users/brunowinter2000/Documents/ai/Mineru/logs/jobs.jsonl` (one per-PDF line + one `job_summary`).
The two-phase scan path writes to the log in two steps: `convert` appends `N_parts` `type:"part"`
lines (one per 100-page chunk); `merge` appends 1 per-pdf line. No `job_summary` in the chunked path.

For a loop over N normal PDFs — read **2N** tail lines:

```bash
tail -n $((2*N)) /Users/brunowinter2000/Documents/ai/Mineru/logs/jobs.jsonl
```

For a single chunked convert — N_parts = ceil(total_pages / 100): after `convert`, tail `N_parts`
lines; after `merge`, tail 1 line.

Any per-PDF line with `md: null` → no output produced → report it to the user (PDF name). That is
the only check here. Fidelity of the produced md is judged in Phase 1.

#### Phase 1 — Cleanup

PDFs come from MinerU as Markdown. Phase 1 opens with a per-md fidelity check that both catches bad
converts AND detects the cleanable artifacts. Cleanup itself focuses on inline OCR artifacts, not
block chrome. Skip any md with `md: null` (failed convert, already reported).

##### Fidelity Check — per md, BEFORE cleaning

Run on EVERY produced md — every file, not a sample of files. NEVER full-read an md (a book md is
thousands of lines). Two cheap steps:

1. **grep noise-signature patterns** → counts + line numbers only:
   - spaced single-char runs: `([A-Za-z] ){3,}[A-Za-z]`
   - spaced contents inside a LaTeX command: `\\[a-z]+ *\{[^}]*([a-z] ){2,}`
   - spaced command names: `\\ [a-z]( [a-z])+`
2. **Read with offset** on the grep hit lines, plus fixed PROSE windows (~30–40 lines each) after the
   front-matter, at ~25/50/75%, and the tail. Read prose, not only formulas.

Classify each md:
- **clean** — no/trivial hits, prose coherent → index as-is, no cleanup.
- **cleanable** — hits collapse into REAL words/formulas (`\mathrm { t h e }` → "the"), prose
  coherent → fix below, then index.
- **bad convert** — hits collapse into nonsense / wrong characters (`\ n u m b 9 e r`), OR sampled
  PROSE is garbled (scan OCR) → EXCLUDE: no cleanup, no index. Report to the USER: PDF name +
  example line(s); it is a scan that slipped past the Scan Check — re-run via the two-phase
  Scan path above (convert → check parts.json → merge). NOT the same as `md: null`.

Discriminator: does collapsing a spaced run yield a real word? Yes → cleanable. No → bad convert.

##### Pre-cleanup: Backup + Word Count Baseline

```bash
cp "$OUTPUT_DIR/$STEM.md" "/tmp/backup_$STEM.md"
wc -w "$OUTPUT_DIR/$STEM.md"
```

##### Artifacts to Detect and Fix

- **LaTeX spaced command name** — `\ f r a c`, `\ s u m`, `\ m a t h r m` → `\frac`, `\sum`, `\mathrm`
- **LaTeX spaced command contents** — `\mathrm { t h e \ d e s i g n }` → `\mathrm{the design}`; `\operatorname* { m i n }` → `\operatorname*{min}`
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

Don't over-engineer. Stop when:
- All known issue categories have 0 remaining matches in the file
- Word count is stable
- Spot-check 10-15 lines from the middle reads as natural text

---

### Index — Final Phase (both modes)

One script call. `rag-cli index` is incremental (hash-based skip) — re-running only embeds new/changed files.

**Important — OUTPUT_DIR must be the collection dir.** Set `OUTPUT_DIR` to the rag-cli collection directory:

```bash
RAG_ROOT=~/Documents/ai/Meta/ClaudeCode/cli/rag-cli
OUTPUT_DIR="$RAG_ROOT/data/documents/$COLLECTION"
mkdir -p "$OUTPUT_DIR"
```

Set this BEFORE the Scrape phase (Phase 2).

Then launch index as a background Bash call:

```bash
PYTHONUNBUFFERED=1 rag-cli index --collection "$COLLECTION" \
    > /tmp/${COLLECTION}_index.log 2>&1
```

The script prints per file `Indexed <doc> -> N chunks` and a final summary line:

```
Done: N files indexed (X chunks), Y skipped, Z adopted
```

Report `N` (files indexed) and `X` (chunks) from that line — `N` is the **final md** count for the Completion Report.

Launch index as a background Bash call (`run_in_background=true`) and go idle; do NOT `pgrep`/name-poll/`wait`-loop. When it completes, read `/tmp/${COLLECTION}_index.log` ONCE for the summary line, then output the Completion Report.

No separate verify step inside the pipe.

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

Keep the two drop reasons separate: scrape errors **E** come from the scraper, thin/noise **D** comes from the cleanup check.

**pdf:** `convert: M ok, K md:null (reported to user)` · `bad converts excluded (reported to user, need better source/reconvert): B` · `cleaned: C files` · `indexed: N chunks across M documents`.

End with this report. STOP. No commit needed (output is data files, not code).