# Pooling Phase 13.5 — Eyeball Test + Engine-Provenance + Pivot to Drill-Down

**Date:** 2026-05-23
**Predecessor:** `09_12_method_eval.md` (Phase 13 — 12-method eval, M11 winner Jaccard 0.259)
**Result:** Pooling-as-unified-ranking abgehakt. Pivot zu Engine-Breakdown UI + Drill-Down per Engine.

---

## Eyeball Test — was Jaccard 0.259 verschweigt

Phase 13 hat M11 (C3→LLM-Filter) als Winner gekürt mit overall Jaccard 0.259. Eyeball-Inspektion an 4 repräsentativen Queries (eine pro Modus) zeigt aber dass die Zahl die User-Perception nicht widerspiegelt.

### M11 Top-10 Klassifikation (useful / borderline / SEO)

| Query | Useful | Borderline | SEO/Spam | Bemerkung |
|---|---|---|---|---|
| general × transformer attention | 5 | 3 | 2 | hakia + medium-spam, Vaswani/Jalammar/LilLog fehlen |
| pdf × postgresql indexes | 8 | 1 | 0 | excellent, nur 9 statt 10 picks (LLM-Bug) |
| books × asyncio | 8 | 2 | 0 | excellent, Publisher-orientiert |
| docs × contrastive learning | 9 | 0 | 1 | excellent, aber Duplikat (LLM-Bug) |

**Aggregat: 30/39 useful (77%), 3 SEO-Spam, 6 borderline.** Aber: general-mode hat 5/10 useful + 2 SEO, das ist die Worst-Case-Klasse und gleichzeitig die häufigste Query-Form.

### Jaccard ist eine schwache Metrik

Jaccard misst Set-Overlap, nicht WELCHE Oracle-URLs überlappen. M11 trifft die "leichten" Oracle-Picks (Wikipedia + MachineLearningMastery + D2L) und verfehlt die "harten" (Vaswani Paper, Jalammar Illustrated Transformer, Lil Log Attention). Zwei Methoden mit identischem Jaccard können UX-relevant dramatisch unterschiedlich sein.

---

## Engine-Provenance — wo kommen Oracle-Hits und Oracle-Misses her

Pro URL im Pool zählen wir: in welchen Engines surfacte sie? Aggregiert über alle 16 Pairs:

| Engine | Hit (M11 ∩ Oracle) | Oracle-verpasst | M11-only | Pool-only | Pool-Total | Signal% |
|---|---|---|---|---|---|---|
| duckduckgo | 39 | 51 | 23 | 47 | 160 | 24.4% |
| mojeek | 17 | 16 | 35 | 92 | 160 | 10.6% |
| openalex | 10 | 6 | 15 | 115 | 146 | 6.8% |
| crossref | 3 | 11 | 11 | 141 | 166 | 1.8% |
| **lobsters** | **0** | **7** | **0** | 131 | 138 | **0%** |
| stack_exchange | 0 | 0 | 10 | 72 | 82 | 0% |
| open_library | 0 | 0 | 0 | 16 | 16 | 0% |

### Lobsters — strukturelle Blindheit von M11

Lobsters surfacte 7 Oracle-URLs über 16 Pairs (Jalammar, Lil Log, DeepRevision, Aman.ai etc. — die kanonischen ML-Blogs). M11 hat **kein einziges davon** in seine Top-10 gewählt. Hypothese: Lobsters-Snippets sind kurz (oft nur Domain-Name), der Cross-Encoder hat zu wenig Text-Substance um Authority zu erkennen. Auch der Instruction-Prefix hilft nicht — er biased semantisch in Richtung "official/canonical", aber bei fehlenden Snippet-Daten ist der Encoder lookup-blind.

### Stack Exchange — niche-signal, nicht oracle-typed

Stack Exchange surfacte 0 Oracle-Hits (Oracle-Curator stuft SE nicht als "primary authoritative source" ein). M11 picked aber 10 SE-URLs (m11-only). Für QA-Intent-Queries ("warum X langsamer als Y?") ist SE genau das richtige — Oracle-Bias gegen SE ist eine Metric-Schwäche, nicht ein M11-Problem.

---

## Drill-Down These — erste Iteration zu schwach

**User-Intuition (Ausgangspunkt):** wenn 4 Oracle-Treffer von M11 alle aus Lobsters + OpenAlex kommen, signalisiert das "diese Engines liefern Signal, andere Rauschen". Drill-Down per Engine lässt User entscheiden wo er tiefer suchen will.

**Erste Analyse zu schwach:** wir haben gezeigt dass Lobsters Oracle-Picks liefert die M11 verfehlt. Das ist aber kein UX-Signal nach außen. "Lobsters hat 8 im Pool" sendet dem Sucher keine Qualitäts-Information — es heißt nur "die Engine hat geantwortet, hier 8 URLs". Der User kann nicht unterscheiden ob die 8 useful sind oder Noise.

Ein echtes Drill-Down-Signal bräuchte: "M11 hat 2 von Lobsters in den Top-10 gepickt und beide waren useful → drill hier". Aber genau diese Konstellation hat M11 strukturell nicht, weil M11 Lobsters ignoriert.

---

## Pivot — Pooling abhaken, Engine-Breakdown UI

**Entscheidung 2026-05-23:** Pooling-Methoden-Tuning ist hopeless case. Tradeoffs zwischen den 12 Methoden sind klein (Jaccard 0.122–0.259) und der Winner M11 produziert Eyeball-mediocre Output im wichtigsten Mode (general). Weiteres Tuning bringt Marginal-Gains aber löst nicht den strukturellen Verzicht von Cross-Encoder auf Short-Snippets.

**Pivot zu zwei-Call UI-Architektur:**

```
CALL 1 — search_web returns:
  - Optional: Top-N (z.B. M9 oder M7 oder ungeranked Random-Sample) als orientation
  - Engine breakdown table:
      duckduckgo: N hits found
      mojeek:     N hits found  
      lobsters:   N hits found  ← user weiß: Lobsters liefert Programmer/Researcher Blogs
      openalex:   N hits found  ← user weiß: academic source
      crossref:   N hits found  ← user weiß: academic source
      stack_exchange: N hits found  ← user weiß: QA-Intent
      open_library:   N hits found  ← user weiß: books
      
CALL 2 — search_engine_drilldown <query> --engine <name>:
  - Returns ALL URLs from that engine for that query (cached pool)
```

User bekommt Transparenz statt Algorithmen-Magic. Die Engine-Reputation ersetzt die in-pool Authority-Heuristik. User weiß was Lobsters / SE / OpenAlex liefern — basiert auf Engine-Charakter, nicht auf per-Query Snippet-Ranking.

---

## Future Actions

### Sofort
- Bead `searxng-g82` (pooling-rework) deferred indefinitely — pooling-as-unified-ranking aus. Aktueller Production-Code (Hard-Slot 12+6+2) bleibt erstmal als CALL-1-orientation, ist algorithmisch egal.
- Bead `searxng-y6e` aktiviert als primärer Pfad: implement zwei-Call-Architektur.

### Architektur-Skizze für y6e
1. `search_web_workflow` Output erweitern um Engine-Breakdown-Block. Caching der per-engine Pool-Listen via cache.py (schon vorhanden, nur Schema-Add für per-engine separation).
2. Neuer CLI-Befehl: `searxng-cli search_engine_drilldown <query> --engine <name>` → liest gecachten Pool, gibt URL-Liste für die Engine zurück. Optional `--top-n` für Truncation.
3. cache.py Schema: pro Pair speichern wir bereits `engines: [name]` und `snippets: {engine: text}` (Phase 12 Update). Für y6e brauchen wir per-Engine Position (`positions: {engine: rank}`) — das hat unser stage1 v3 schon angereichert.
4. CALL-1 Top-N orientation: einfache Methode (C1 Overlap oder M7 Cross-Encoder mit Instruction-Prefix), aber bewusst NICHT als "Production-Antwort" framing. Es ist orientation, nicht canonical.

### Was NICHT mehr passiert
- Keine weitere Methoden-Iteration (kein α/β-Tuning für Hybrid, kein 8B-Reranker-Test, kein Full-Content-Rerank). Marginal-Gains sind nicht den Engineering-Aufwand wert.
- Keine Migration in `src/search/merge.py`. Bestehender Hard-Slot Code bleibt.
- Keine Production-Verkündigung "M11 ist der Winner". Phase 13 wird festgehalten als Evidenz für die Hopeless-Case-Diagnose, nicht als Production-Antwort.

### Was vom Phase-13-Eval überlebt
- v3 pool schema mit per-engine positions — wird in y6e gebraucht für drill-down sorting
- clean_pool.py filter helper — könnte für engine-class-based filtering in y6e wiederverwendet werden
- oracle_v3clean.json — bleibt als methodologisches Referenzset falls wir später wieder ranking evaluieren wollen
- Findings über Engine-Charakter (Lobsters = programmer-blogs, SE = QA, openalex/crossref = academic, OL = books, mojeek+ddg = web-workhorse) — fließen in y6e-UX-Texte und CLI-Doku ein

---

## Open Question (User noch am Nachdenken)

Wie genau die Engine-Breakdown UI dem User Vertrauen vermittelt. Pool-Existenz ("Lobsters hat 8 URLs gefunden") ist nicht stark genug als Signal. Mögliche Alternativen:

1. **Engine-Reputation pro Mode statisch**: hardcoded oder dokumentiert was jede Engine "macht" (Lobsters → programmer blogs, SE → QA, etc.). User kennt Engine-Charakteristika und entscheidet danach.
2. **Engine-Reputation pro Query dynamisch**: schwer messbar ohne Eval-Loop für jede Query — was wir gerade als hopeless eingestuft haben.
3. **Result count + Engine-Tag als simple UX**: ohne Quality-Claim, nur "diese Engine hat N URLs". Vertrauen kommt aus der User-Kenntnis der Engine, nicht aus unserer Bewertung.

User-Tendency 2026-05-23: (3) — "sucher entscheidet was er drillt", wir machen kein Quality-Tweaking, nur Transparenz.

---

## Quellen

Daten-Basis dieser Analyse:
- `dev/search_pipeline/01_reports/value_eval_v3_20260523_021216/*_methods_v3.json` (16 Pairs, M11 picks)
- `dev/search_pipeline/01_reports/value_eval_v3_20260523_021216/*_pool.json` (16 Pairs mit per-engine positions)
- `dev/search_pipeline/01_reports/value_eval_v2_20260523_000156/*_oracle_v3clean.json` (16 Pairs, 10 picks each)
- Eyeball-Klassifikation: subjektiv pro URL, Kriterien: useful (canonical/primary/official/expert), borderline (decent secondary), SEO/spam (listicle/content-farm/low-effort)
