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
   - Keep story title row + comment threads. Markdown-table syntax stays (embedding handles it).

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
- Logo image line: `[ ![Logo of ...](...) ](...)` — RELIABLE content-end marker
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

If INPUT is a single PDF file:

```bash
mkdir -p $OUTPUT_DIR
# Ensure $INPUT already carries a speaking name (rename first if cryptic), then:
STEM="$(basename "$INPUT" .pdf)"
cd /Users/brunowinter2000/Documents/ai/Mineru && \
./venv/bin/python workflow.py convert \
    --input "$INPUT" \
    --output "$OUTPUT_DIR/$STEM.md"
```

If INPUT is a directory: first ensure EVERY `*.pdf` carries a speaking name (rename the cryptic ones — read first page / title), then loop, taking `STEM` from the PDF basename. Report progress: `[N/M] <STEM>: phase 0 done`.

**Concrete loop template — use exactly this shape, including both guards:**

```bash
for PDF in "$PDF_DIR"/*.pdf; do
    STEM="$(basename "$PDF" .pdf)"   # PDF already carries its speaking name
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

Note on naming a cryptic PDF: when a PDF's filename is not already speaking, derive a descriptive PascalCase name from the first page header / title metadata, condensed to ~30 chars (e.g. `AslamMontague2001MetasearchModels`, `ManningRaghavanSchutze2008IRTextbook`), and RENAME the PDF to it. Once the PDF carries a speaking name, `STEM = basename(PDF)` is correct and the md inherits it. Avoid filename collisions inside one batch — append year or first-author-initial when needed.

**STEM character constraints (hard rules):** alphanumeric + underscore ONLY. NEVER include brackets `[ ]`, parentheses `( )`, dots `.` (other than the trailing `.md` extension), commas, spaces, or any glob metachar. Sanitize the stem at derivation time.

`STEM = basename(PDF)` in the loop above — no `pdf → stem` mapping table. Rename cryptic PDFs once, BEFORE the batch runs.

If MinerU fails for any PDF: log + skip + continue. Report failed PDFs at end.

##### Background Convert — launch + go idle

For any non-trivial convert (PDF >50 MB, a batch over a directory, or a single PDF expected to exceed ~60 s — any academic paper >10 MB, any book PDF): launch `workflow.py convert` as a background Bash call (`run_in_background=true`) and go idle; then run the post-convert verify and continue. Do NOT `pgrep`/name-poll/`wait`-loop.

##### Post-Convert Verify

After every convert (single file or end of batch loop), verify the output is non-empty and substantial:

```bash
[ -s "$OUTPUT_DIR/$STEM.md" ] && wc -w "$OUTPUT_DIR/$STEM.md"
```

Threshold: **≥ 100 words** = meaningful conversion. Below threshold:
- Log `WARNING: $STEM.md has <N> words — expected ≥100`
- Retry: add `--timeout 300` (or higher) to the `workflow.py convert` call
- If retry also fails: skip file, add to failed list, continue batch

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

**pdf:** `convert: M ok, K failed` · `cleanup issues: [...]` · `indexed: N chunks across M documents`.

End with this report. STOP. No commit needed (output is data files, not code).