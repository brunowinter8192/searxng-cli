---
name: searxng-cli-pdf
description: Convert PDF(s) to Markdown (whole-document, MinerU mlx / vlm-auto-engine) and index into a RAG collection. No worker, fully interactive — the USER runs ONE convert command that processes all PDFs sequentially; Claude does naming, cleanup, index.
---

# PDF → MD → Index — Skill

No worker. Interactive. The USER runs the convert command; Claude does ONLY: naming, cleanup, index.
ONE command converts ALL PDFs in the batch sequentially — each as a whole document (no chunking),
MinerU `vlm-auto-engine` (mlx) — the only engine.

## Paths
- MINERU = `~/Documents/ai/Mineru/venv/bin/python ~/Documents/ai/Mineru/workflow.py`
- COLLECTION = `trading-reference` (default; confirm only if user names another)
- OUTPUT_DIR = `~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents/<COLLECTION>/`
- COMMAND FILE = `~/Downloads/<batch>_pdf_commands.md`

## Rule
The CONVERT command → USER runs it. Claude never runs a convert. Claude runs: naming, cleanup
scripts, `rag-cli index`.

## Phase 0 — Naming + skip-check (CLAUDE)
1. Per PDF: assign a PascalCase STEM, alphanumeric + underscore ONLY — no brackets, parentheses,
   dots, commas, spaces. Rename the source PDF in place → `<STEM>.pdf`.
2. Skip-check: drop any PDF that already has `<OUTPUT_DIR>/<STEM>.md` — only un-converted PDFs go
   into the command.
3. Backend is always `vlm-auto-engine` (mlx) — the only engine. No backend choice; workflow.py takes
   no `-b`/`-l`/`--effort` flags.

## Phase 1 — MinerU convert (USER runs, ONE command for the whole batch)
Write the COMMAND FILE: ONE block listing ALL non-skipped PDFs (whole document, no chunks):
```
mkdir -p <OUTPUT_DIR>
PYTHONUNBUFFERED=1 ~/Documents/ai/Mineru/venv/bin/python ~/Documents/ai/Mineru/workflow.py convert \
  --pdf "<PDF1>" "<PDF2>" "<PDF3>" ... \
  --out-dir <OUTPUT_DIR> 2>&1 | tee /tmp/<batch>_mineru.log
```
- ONE invocation processes all PDFs sequentially — each as a single whole-document mineru process.
- The mem_watchdog wraps each process and aborts a runaway before it takes the Mac down. A PDF that
  aborts is logged as failed (`md:null`) and the batch CONTINUES with the next PDF.
- Output: flat `<OUTPUT_DIR>/<STEM>.md` per PDF.
- Re-run is safe: Phase 0 skip-check drops PDFs already converted, so a re-run only fills the gaps
  (including any PDF that aborted on the previous pass).
- USER runs the block, reports done.

## Phase 2 — Clean (CLAUDE)
Run on each `<OUTPUT_DIR>/<STEM>.md`. Audit FIRST (counts are signals — sample the hits), then strip.

Per-class detection + action:
- **A — lost formula (UNRECOVERABLE → do NOT clean):** `??`, `` (U+FFFD), empty/`?`-containing
  `<sub>`/`<sup>` (`<su[bp]>[[:space:]]*</su[bp]>|<su[bp]>[^<]*\?[^<]*</su[bp]>`), whitespace-only
  `$$…$$` blocks (split on `$$`, test odd segments). Any A hit → the output for that doc is
  gone; cleaning cannot recover it. **Report the symbol/page to the user** — no backend fallback,
  `vlm-auto-engine` is the only engine.
- **B — spaced math (RECOVERABLE → de-space):** `_ {`, `^ {`, `\ [a-z]( [a-z])+`, spaced single-char
  runs `([A-Za-z] ){3,}[A-Za-z]`. Collapse runs to real tokens (`\mathrm { a r g m i n }` →
  `\mathrm{argmin}`). Invariant: alphanumeric-char count EXACTLY stable; word count drops.
- **C — encoding (RECOVERABLE → unescape):** HTML entities
  `&(amp|lt|gt|quot|apos|nbsp|#\d+|#x[0-9a-fA-F]+);`, mojibake `Ã.`/`â€`. Entity count → 0.
- **D — prose char-typos:** ignore (negligible). Pervasive prose garble = treat as A → report (unrecoverable).
- **E — backmatter (MANDATORY STRIP):** from the first
  References/Bibliography/Index/Symbols/Abbreviations/Nomenclature heading in the last ~40% (or
  headingless reference run: most non-blank lines match `\(\d{4}[a-z]?\)`/`^Surname, Init.`; index run:
  `,\s*\d+([–-]\d+)?`) through EOF. Confirm 3 lines above the cut are real content. Do NOT cut numbered
  content subsections (heading text starts with a digit) or per-chapter "Bibliographic Notes".
- **F — table markup (RECOVERABLE → pipe-text):** MinerU `<table>` HTML, markup ratio > 50%. Strip
  tags, one row per `</tr>`, cells `|`-separated, content unchanged, no truncation. Validate cell-text
  token set unchanged.

Prose window (every md): pull 1–2 body lines (len > 70, starts alpha, > 10 spaces, alpha-ratio > 0.78)
from the middle third and READ. Coherent → pass; garbled → A → report (unrecoverable).

Per-issue scripts: one `/tmp/fix_<issue>_<STEM>.py` each, test on the file, re-scan that class to 0,
spot-check 10–15 middle lines. Preserve source content; overwrite in place; back up to
`/tmp/backup_<STEM>.md` first.

## Phase 3 — Index (CLAUDE)
```
rag-cli index --collection <COLLECTION>
```
Incremental (hash-skip). Report files indexed + chunks. Confirm docs in the collection.
