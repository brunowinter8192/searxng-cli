# GENERAL-Engine-Redundanz + Skill-Fallback-Guidance

**Datum:** 2026-06-09
**Typ:** Enhancement (Engine-Pool + Skill-Doku) — Feld-Beobachtung, noch nicht umgesetzt.
**Quelle:** reale Recherche-Session (DE-Hochschul-Studiengang-Findung: „welche FH bietet WiInfo-Master in Stadt X")
**Betroffen:** `src/search/engines/`, `src/search/filter_modes.py`, `skills/*/SKILL.md`, `decisions/search_pipeline.md`

## Kurzfassung

In einer längeren Recherche-Session fiel **Google bei 5 von 8 `search_web`-Queries auf 0** (CAPTCHA/EMPTY_BLOCK — deckt sich mit dem dokumentierten 73 %-OK / 23 %-CAPTCHA-IST). Der Fallback auf die übrigen GENERAL-Engines trug die Session über Wasser, **aber knapp**: es gibt nur **2 weitere GENERAL-Engines** (duckduckgo, mojeek), und **mojeek lieferte durchweg Müll** (SEO-Aggregatoren, tote Verzeichnisseiten, Foren). Faktisch hing die Redundanz an **DuckDuckGo allein**.

Größter Hebel laut User-Einschätzung: **nicht an Google schrauben** (bekannt, Backoff bewusst entfernt — `decisions/rate_limiting.md`), sondern **(a) mehr GENERAL-Engines** in den Pool und **(b) die Skill-Doku explizit machen, dass die übrigen GENERAL-Engines Google ersetzen, wenn es 0 liefert.**

## Feld-Evidenz (Session 2026-06-09)

GENERAL-Engine-Ausbeute pro `search_web` (nur google/ddg/mojeek; Akademik-Engines weggelassen):

| Query | google | ddg | mojeek | brauchbar? |
|---|---:|---:|---:|---|
| „…Hochschule angewandte Wissenschaften" | 0 | 0 | 0 | ❌ nur Akademik-Rauschen |
| „…Hochschule München" (Variante 1) | 0 | 0 | 0 | ❌ nur Akademik-Rauschen |
| „…FH Dortmund Münster Hannover" | 10 | 9 | 10 | ✅ |
| „…Hochschule München Nürnberg Ohm" | 9 | 9 | 9 | ✅ |
| „…HAW Hamburg Bremen" | **0** | 9 | 10 | ⚠️ ohne Google, ddg/mojeek trugen |
| „FH Münster…Zulassungsvoraussetzungen" | **0** | **0** | 10 (Müll) | ❌ nur Mojeek-Müll |
| „Hochschule München Wirtschaftsinformatik Master" | 8 | 8 | 8 | ✅ |
| „…Hannover Bremen Bielefeld" | **0** | 10 | 10 | ✅ ddg/mojeek trugen |

- **Google: 0 bei 5/8 (62,5 %)** — im erwarteten Bereich des dokumentierten 23 %-CAPTCHA + Query-Varianz, aber in dieser Session gehäuft.
- **DuckDuckGo war der eigentliche Träger** des Fallbacks. Fiel ddg *gleichzeitig* aus (2 Queries), blieb nur Mojeek — und damit Müll oder nichts.
- **Mojeek-Qualität:** Drilldowns lieferten konsistent `studienwahl-deutschland.de` („nicht mehr verfügbar"), `stuvia`, `fernstudium-direkt`, `wiwi-treff`-Foren statt der echten `.de`-Studiengangsseiten. Effektiver Mehrwert ≈ 0 für „offizielle Programmseite finden".
- **Akademik-Engines (crossref/openalex/semantic_scholar)** lieferten bei *jeder* Query 8–10 Treffer, aber für „welche Hochschule bietet Studiengang X" reines Rauschen (Forschungspaper). Bei den zwei Totalausfällen bestand die Breakdown faktisch nur aus diesem Rauschen → optisch „Treffer", real unbrauchbar.

### Scrape-Seite (zur Vollständigkeit)
- **1 harter Error:** `scrape_url` auf die FH-Münster-WiInfo-Seite → `Page returned only whitespace or near-empty content` (JS-gerendert / Cookie-Wall). Sonst 6/7 Scrapes sauber.
- **DAAD-Detailseiten + offizielle `.de`-Hochschulseiten scrapen exzellent** (strukturierte Zulassungsbedingungen + Fristen). Verlässliche Quelle, wenn die Suche eine Programmseite findet.

## Root Cause (deckt sich mit IST)

1. **Nur 3 GENERAL-Engines** im Pool (`google`, `duckduckgo`, `mojeek` — `decisions/search_pipeline.md`). Bei Google-CAPTCHA bleibt eine **2-Engine-Redundanz**, von der eine (mojeek) qualitativ schwach ist → effektiv **Single-Point-of-Failure DuckDuckGo**.
2. **Google ist zusätzlich der K-Anker** des Pool-Caps (`K = google_count`, Fallback 10). Sein Ausfall degradiert auch die Cap-Logik auf den 10er-Default.
3. **Akademik-Engines verwässern die Breakdown** bei nicht-akademischen Queries — täuschen eine „erfolgreiche" Breakdown vor, obwohl 0 brauchbare GENERAL-Treffer da sind.

## Skill-Wording-Präzisierung (Nebenbefund, kleinere Prio)

Die SKILL.md-Formulierung „Mode flags `--books`/`--pdf`/`--docs` **restrict to google/duckduckgo/mojeek**, append the modifier, post-filter the URLs" ist **inhaltlich korrekt** (google/ddg/mojeek sind die Engines, an deren Query der Modifier gehängt + post-gefiltert wird — `_BOOKS_/_PDF_/_DOCS_ENGINES` in `filter_modes.py`). „restrict" = **Modifier + URL-Postfilter**, nicht Engine-Satz.

**Nur missverständlich:** „restrict to" liest sich als „nur diese 3 Engines feuern". Tatsächlich gilt die Bucket-Uniformity-Invariante — **alle 9 Engines feuern weiter** (`apply_filter_mode()` → `excluded={}`); die Flag beeinflusst nur Query von 3 Engines + URL-Postfilter. → Ein Satz Klarstellung genügt, kein Verhaltensfehler.

Operativ relevant: **`--docs` ist NICHT das Mittel gegen Akademik-Rauschen** — entfernt crossref/openalex nicht, hängt „documentation" an die Query (für Programm-Findung kontraproduktiv), blacklistet nur Foren/Blogs/Tutorials. Akademik-Rauschen ist ein **separater** Punkt (über Skill-Guidance „Akademik ≠ Allgemeinsuche").

## Vorgeschlagene Richtung

### A) Engine-Pool — mehr GENERAL-Redundanz
- **Marginalia** (`search.marginalia.nu`) — steht bereits als „Pending — Marginalia probe: try-or-drop … when there is a concrete use-case gap" in `decisions/search_pipeline.md`. **Diese Session IST der Use-Case-Gap** → Probe priorisieren.
- Weitere GENERAL-Kandidaten evaluieren (Brave Search API / Startpage / ggf. Scholar im Google-freien Pool, blockiert auf g82 Pooling-Rework).
- Ziel: bei Google=0 mindestens **2 qualitativ brauchbare** GENERAL-Engines übrig (nicht nur ddg + Mojeek-Müll).

### B) Skill-Guidance — Fallback explizit machen
- SKILL.md klarstellen: **GENERAL-Engines sind gegenseitig substituierbar; Google-0 ist Normalfall (CAPTCHA), kein Fehler — dann drilldown auf die übrigen GENERAL-Engines.**
- **Akademik-Engines explizit als nicht-allgemeine Quelle markieren** — bei „Entity/Programm/Produkt finden"-Queries ignorieren, nicht als „Treffer" fehldeuten.
- `--docs`-Wortlaut korrigieren + klarstellen was die Mode-Flags real tun.

### C) Optional (Scrape-Robustheit, niedrige Prio)
- Fallback bei `whitespace/near-empty`-Scrape (FH-Münster-Fall): automatisch auf **DAAD-Spiegelseite / Hochschulkompass** ausweichen.

## Akzeptanzkriterien
- ≥1 zusätzliche GENERAL-Engine im aktiven Pool (Marginalia-Probe zuerst) **oder** dokumentierte try-or-drop-Entscheidung mit Begründung.
- SKILL.md: Mode-Flag-Wortlaut präzisiert (alle Engines feuern; „restrict" = Modifier/URL-Postfilter auf 3 Engines).
- SKILL.md: expliziter Abschnitt „Google=0 ist Normalfall → GENERAL-Fallback; Akademik-Engines ≠ Allgemeinsuche".
- (optional) Scrape-Fallback DAAD/Hochschulkompass bei empty-content.

## Non-Goals
- **Kein Google-Backoff/Retry** — bewusst entfernt, `decisions/rate_limiting.md` (466 s Backoff-Waste für 0 Nutzen; Bot-Detection decayt nicht in Sekunden).
- Kein globales Cross-Engine-Ranking (Pooling-Rework abgebrochen, `decisions/OldThemes/pooling/10_*`).

## Quellen
- `decisions/search_pipeline.md` — 9-Engine-IST, „Pending — Marginalia probe", g82 Pooling-Rework, K=google_count-Cap.
- `decisions/rate_limiting.md` — Google 73 % OK / 23 % CAPTCHA, Fail-Fast, No-Backoff-Begründung.
- `src/search/filter_modes.py` — Bucket-Uniformity-Invariante (`excluded={}`), Mode-Modifier-Sätze.
