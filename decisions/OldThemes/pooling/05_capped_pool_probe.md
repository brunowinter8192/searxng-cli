# Capped-Pool Probe — Phase 9 Resolution (Pooling Strategy Comparison)

**Date:** 2026-05-21  
**Bead:** searxng-g82 (open)  
**Verdict:** C2 BM25 / C3 Cross-Encoder / C4 Embedding-Cosine all equivalent on obvious-Müll-criterion (0 / 20 queries each). C1 Overlap-Count produces 12 obvious-Müll across 20 queries (rate 5.9%), concentrated in one product query.  
**Report:** `dev/search_pipeline/01_reports/pooling_probe_20260521_215844.md`  
**Prior probes:** `02_rerank_findings.md` (4-query Cross-Encoder verdict), `03_rerank_validation_20queries.md` (bee-corrupted predecessor)

---

## Hypothesis

Architecture change: per-engine top-K cap at K=`google_count`, output Top-`google_count` URLs, Hard-Slot 12/6/2 dropped. Compare 4 ranking strategies on the same capped pool, identify the strategy with the lowest "obvious-Müll" rate.

## Methodology

**Pool composition:** per-engine top-K cap with K = google's result count for that query. Hard-stop on google_count=0 (= empty result, no fallback). Bucket-uniformity-fixed codebase (commit `af77cc5`) so all 9 engines fire uniformly on every query.

**Müll-Eyeball, conservative:** binary off-topic classification per URL. "Obvious, unambiguous off-topic" = wrong topic semantically, spam/SEO listicle, broken/empty. When in doubt → NOT Müll. False-positives stay in the "good" zone, never in the Müll zone.

**Calibration examples** (validated post-hoc via spot-check on Q6 + Q16):
- Müll: "Microsoft PL-500 Exam Dumps" matched against "best espresso machine under 500" — surface match on "500", topic completely different
- Müll: "KGEARSRG: Kernel Graph Embedding on SIFT image regions" for "knowledge graph embedding relational learning" — KGE acronym matches but stands for KERNEL (image classification), not KNOWLEDGE graph
- Müll: openlibrary "Understanding events" (Zacks 2007 psychology book) for "transformer attention mechanism" — psychology of event perception, no ML connection
- NOT Müll: aman.ai LLM-primer with empty snippet for "bert fine-tuning" — BERT is an LLM, primer plausibly topical, no contradicting evidence
- NOT Müll: BioBERT for "bert fine-tuning natural language processing" — paper IS literally about BERT fine-tuning in biomedical domain, on-topic with domain shift

**Sample:** 20 queries — academic (5), product (5), technical (5), mixed_pathology (5). Same 20-query sample as Phase 9 `rerank_probe_20260520_204414.md` for direct comparison.

**Pool sizes after cap:** 45-84 URLs per query (median ~62). 5-7× shrink versus uncapped pool (Phase 7 saw 400-450 uncapped).

## Key Numbers

**Bucket-uniformity verification:** RATE_SKIP = 0 across all 9 engines × 20 queries = 180 engine-call instances. Bee-fix held.

**Aggregate Müll per config** (over 20 queries × Top-`google_count` URLs ≈ ~210 URL slots per config):

| Config | muell_abs_total | muell_rate_mean | rank latency |
|---|---:|---:|---:|
| C1 Overlap-Count | 12 | 0.059 | 0ms |
| C2 BM25 | 0 | 0.000 | ~1ms |
| C3 Cross-Encoder (Qwen3-0.6B) | 0 | 0.000 | ~2400ms |
| C4 Embedding-Cosine (Qwen3-0.6B) | 0 | 0.000 | ~1700ms |

**Discriminating queries (max−min > 2 across configs):** 1 of 20.

| Query | C1 | C2 | C3 | C4 |
|---|---:|---:|---:|---:|
| best espresso machine under 500 2026 | 3 | 0 | 0 | 0 |

The C1 Müll at Q6 stems from keyword-match on the numeric token "500": a Microsoft PL-500 certification exam dump, a SciPy Python-in-Science 2020 conference proceedings, and a Li-ion solid-state-conductor materials-screening paper all matched the "500" token via either crossref/openalex API surface-matching or via the "500" appearing in DOI digits. Overlap-Count's structural signal cannot filter these out — they ARE in the pool and have valid engine origins; the only signal that distinguishes them from real espresso reviews is term-relevance, which BM25/Cross-Encoder/Embedding all encode.

**Per-category Müll distribution (C1 only — the others are 0 across all categories):**

| Category | C1 Müll total | Notes |
|---|---:|---|
| academic | 6 | Mostly openlibrary book false-positives + academic-paper-by-DOI false-positives (e.g. Q16 "Understanding events" psychology book) |
| product | 3 | All 3 from Q6 espresso (the discriminating query) |
| technical | 2 | Two academic-paper-DOI false-positives in technical queries |
| mixed_pathology | 1 | Q16 openlibrary book false-positive |

Academic-query category has the most C1-only Müll because crossref/openalex/openlibrary contribute heavily and their results pass overlap-count via "single-engine = position-1" tiebreaker, but the engines themselves return surface-keyword matches that any text-scoring strategy (C2/C3/C4) demotes.

## Verdict

**C2 BM25, C3 Cross-Encoder, C4 Embedding-Cosine are equivalent at the obvious-Müll level.** All three produce 0 unambiguously off-topic URLs across 20 queries × ~10-12 results = ~210 URL slots per config. The methodology cannot discriminate between them on this criterion.

**C1 Overlap-Count alone is insufficient.** 5.9% obvious-Müll rate, with the failure mode being surface keyword matches that overlap-count cannot suppress (only text-relevance scoring catches them).

**Practical implication for src/ migration:** BM25 is the cheapest winning strategy — ~1ms rank latency, no GPU dependency, no API calls. Cross-Encoder and Embedding match BM25's obvious-Müll quality but add ~2-4s of latency and require running GPU services. For the same observable quality, BM25 is the operational simplification.

If the project decides finer-grained quality matters (e.g. ordering relevant URLs better at the top vs ordering them more arbitrarily), Cross-Encoder may still win on a finer-grained relevance gradient that this methodology does not measure. The capped-pool architecture is small enough that Cross-Encoder runs efficiently — the GPU cost is ~2-4s per query, not prohibitive.

## Methodology Limit

The obvious-Müll methodology is **not discriminating** when applied to a sufficiently good pool. C2/C3/C4 all hit 0 — the ceiling. To differentiate them, a finer methodology would be needed:
- Pairwise comparison (user picks "X better than Y" on side-by-side top-N)
- Relevance gradient (0-3 scale instead of binary)
- nDCG-style position-weighted scoring (a relevant result at rank-1 worth more than at rank-10)

For the current decision (BM25 vs Cross-Encoder vs Embedding), all three are equally clean. Choice can rest on operational concerns (latency, complexity, GPU dependency) rather than quality.

## Recommendation

**Migrate `src/search/merge.py:_merge_and_rank` to per-engine top-K cap pool + BM25 ranking + Top-`google_count` output.** Drop the 12/6/2 Hard-Slot allocation, the GENERAL/ACADEMIC/QA frozensets, and the per-class sort heuristics.

Cross-Encoder remains in scope as a future enhancement if a finer-grained-quality probe shows ordering benefits. For first migration: simplest config that beats baseline.

## Quellen

- Production-architecture decisions (capped pool + Hard-Slot drop): `decisions/bee_fix.md`, `decisions/search07_ranking_format.md`
- Phase 7 BM25 evaluation: `01_bm25_evaluation_findings.md` (BM25 alone ties Hard-Slot 34/40 on uncapped pool)
- Phase 8 Cross-Encoder verdict: `02_rerank_findings.md` (CE 35/40 with BM25 retrieve prefilter on uncapped pool — beats Hard-Slot)
- Phase 9 bee-corrupted attempt: `03_rerank_validation_20queries.md`
- Bee resolution: `04_zero_query_diagnosis.md` + `decisions/OldThemes/bee_cdp_starvation/04_resolution.md`
