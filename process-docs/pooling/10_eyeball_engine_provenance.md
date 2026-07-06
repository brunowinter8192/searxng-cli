# Pooling Phase 13.5 — Eyeball Test + Engine-Provenance + Pivot to Drill-Down

**Date:** 2026-05-23
**Predecessor:** Phase 13 — 12-method eval, M11 winner Jaccard 0.259
**Result:** Pooling-as-unified-ranking abandoned. Pivot to Engine-Breakdown UI + per-engine drill-down.

---

## Eyeball Test — what Jaccard 0.259 conceals

Phase 13 crowned M11 (C3→LLM-Filter) winner with overall Jaccard 0.259. Eyeball inspection on 4 representative queries (one per mode) shows the number does not reflect user perception.

### M11 Top-10 classification (useful / borderline / SEO)

| Query | Useful | Borderline | SEO/Spam | Note |
|---|---|---|---|---|
| general × transformer attention | 5 | 3 | 2 | hakia + medium-spam, Vaswani/Jalammar/LilLog missing |
| pdf × postgresql indexes | 8 | 1 | 0 | excellent, only 9 of 10 picks (LLM bug) |
| books × asyncio | 8 | 2 | 0 | excellent, publisher-oriented |
| docs × contrastive learning | 9 | 0 | 1 | excellent, but duplicate (LLM bug) |

**Aggregate: 30/39 useful (77%), 3 SEO-Spam, 6 borderline.** But: general-mode has 5/10 useful + 2 SEO, which is both the worst-case class and the most common query form.

### Jaccard is a weak metric

Jaccard measures set overlap, not WHICH oracle URLs overlap. M11 hits the "easy" oracle picks (Wikipedia + MachineLearningMastery + D2L) and misses the "hard" ones (Vaswani paper, Jalammar Illustrated Transformer, Lil Log Attention). Two methods with identical Jaccard can differ dramatically in UX-relevant quality.

---

## Engine-Provenance — where do oracle hits and oracle misses come from

Per URL in the pool we count: which engines surfaced it? Aggregated over all 16 pairs:

| Engine | Hit (M11 ∩ Oracle) | Oracle-missed | M11-only | Pool-only | Pool-Total | Signal% |
|---|---|---|---|---|---|---|
| duckduckgo | 39 | 51 | 23 | 47 | 160 | 24.4% |
| mojeek | 17 | 16 | 35 | 92 | 160 | 10.6% |
| openalex | 10 | 6 | 15 | 115 | 146 | 6.8% |
| crossref | 3 | 11 | 11 | 141 | 166 | 1.8% |
| **lobsters** | **0** | **7** | **0** | 131 | 138 | **0%** |
| stack_exchange | 0 | 0 | 10 | 72 | 82 | 0% |
| open_library | 0 | 0 | 0 | 16 | 16 | 0% |

### Lobsters — structural blind spot of M11

Lobsters surfaced 7 oracle URLs across 16 pairs (Jalammar, Lil Log, DeepRevision, Aman.ai, etc. — the canonical ML blogs). M11 picked **none** of them into its Top-10. Hypothesis: Lobsters snippets are short (often just the domain name), the cross-encoder has too little text substance to recognize authority. The instruction prefix does not help either — it biases semantically toward "official/canonical", but with missing snippet data the encoder is lookup-blind.

### Stack Exchange — niche signal, not oracle-typed

Stack Exchange surfaced 0 oracle hits (the oracle curator does not rate SE as "primary authoritative source"). M11 still picked 10 SE URLs (M11-only). For QA-intent queries ("why is X slower than Y?") SE is exactly right — the oracle's bias against SE is a metric weakness, not an M11 problem.

---

## Drill-Down Hypothesis — first iteration too weak

**User intuition (starting point):** if 4 oracle hits from M11 all come from Lobsters + OpenAlex, that signals "these engines deliver signal, others noise". Per-engine drill-down lets the user decide where to dig deeper.

**First analysis too weak:** we showed that Lobsters delivers oracle picks that M11 misses. But that is not an outward-facing UX signal. "Lobsters has 8 in the pool" sends the searcher no quality information — it just means "the engine responded, here are 8 URLs". The user cannot tell whether the 8 are useful or noise.

A real drill-down signal would need: "M11 picked 2 from Lobsters into the Top-10 and both were useful → drill here". But M11 structurally never has this constellation, because M11 ignores Lobsters.

---

## Pivot — abandon pooling, Engine-Breakdown UI

**Decision 2026-05-23:** Pooling-method tuning is a hopeless case. Tradeoffs between the 12 methods are small (Jaccard 0.122–0.259) and the winner M11 produces eyeball-mediocre output in the most important mode (general). Further tuning brings marginal gains but does not solve the structural weakness of cross-encoder-on-short-snippets.

**Pivot to two-call UI architecture:**

```
CALL 1 — search_web returns:
  - Optional: Top-N (e.g. M9 or M7 or unranked random sample) as orientation
  - Engine breakdown table:
      duckduckgo: N hits found
      mojeek:     N hits found
      lobsters:   N hits found  ← user knows: Lobsters delivers programmer/researcher blogs
      openalex:   N hits found  ← user knows: academic source
      crossref:   N hits found  ← user knows: academic source
      stack_exchange: N hits found  ← user knows: QA intent
      open_library:   N hits found  ← user knows: books

CALL 2 — search_engine_drilldown <query> --engine <name>:
  - Returns ALL URLs from that engine for that query (cached pool)
```

The user gets transparency instead of algorithmic magic. Engine reputation replaces the in-pool authority heuristic. The user knows what Lobsters / SE / OpenAlex deliver — based on engine character, not per-query snippet ranking.

---

## Future Actions

### Immediate (as of 2026-05-23)
- Pooling-rework work item deferred indefinitely — pooling-as-unified-ranking dropped. As-of-2026-05 production code (Hard-Slot 12+6+2) stays for now as CALL-1 orientation; algorithmically it does not matter which.
- Two-call-architecture implementation activated as the primary path.

### Architecture sketch for the drill-down work
1. Extend `search_web_workflow` output with an engine-breakdown block. Caching of per-engine pool lists via cache.py (already present, only schema-add for per-engine separation).
2. New CLI command: `searxng-cli search_engine_drilldown <query> --engine <name>` → reads cached pool, returns URL list for that engine. Optional `--top-n` for truncation.
3. cache.py schema already stores `engines: [name]` and `snippets: {engine: text}` per pair (Phase 12 update). The drill-down work needs per-engine position (`positions: {engine: rank}`) — already enriched by stage1 v3.
4. CALL-1 Top-N orientation: simple method (C1 Overlap or M7 Cross-Encoder with instruction prefix), but deliberately NOT framed as "production answer". It is orientation, not canonical.

### What no longer happens
- No further method iteration (no α/β tuning for hybrid, no 8B-reranker test, no full-content rerank). Marginal gains are not worth the engineering effort.
- No migration into `src/search/merge.py`. Existing Hard-Slot code stays.
- No production announcement of "M11 is the winner". Phase 13 is recorded as evidence for the hopeless-case diagnosis, not as a production answer.

### What survives the Phase-13 eval
- v3 pool schema with per-engine positions — needed for drill-down sorting
- clean_pool.py filter helper — could be reused for engine-class-based filtering
- oracle_v3clean.json — stays as a methodological reference set should ranking evaluation resume later
- Findings on engine character (Lobsters = programmer blogs, SE = QA, openalex/crossref = academic, OL = books, mojeek+ddg = web workhorse) — feed into UX text and CLI docs for the drill-down work

---

## Open Question (user still deliberating, as of 2026-05-23)

How exactly the engine-breakdown UI conveys trust to the user. Pool existence ("Lobsters found 8 URLs") is not strong enough as a signal. Possible alternatives:

1. **Static per-mode engine reputation**: hardcoded or documented what each engine "does" (Lobsters → programmer blogs, SE → QA, etc.). User knows engine characteristics and decides accordingly.
2. **Dynamic per-query engine reputation**: hard to measure without an eval loop per query — which is what was just classified as hopeless.
3. **Result count + engine tag as simple UX**: no quality claim, just "this engine has N URLs". Trust comes from the user's knowledge of the engine, not from our assessment.

User tendency as of 2026-05-23: (3) — "the searcher decides what to drill into", no quality-tweaking on our side, only transparency.

---

## Sources

Data basis for this analysis:
- `dev/search_pipeline/01_reports/value_eval_v3_20260523_021216/*_methods_v3.json` (16 pairs, M11 picks)
- `dev/search_pipeline/01_reports/value_eval_v3_20260523_021216/*_pool.json` (16 pairs with per-engine positions)
- `dev/search_pipeline/01_reports/value_eval_v2_20260523_000156/*_oracle_v3clean.json` (16 pairs, 10 picks each)
- Eyeball classification: subjective per URL, criteria: useful (canonical/primary/official/expert), borderline (decent secondary), SEO/spam (listicle/content-farm/low-effort)
