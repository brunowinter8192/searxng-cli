# Agentic Discovery — Pipe-Flow-Entscheidungen & Roadmap

**Session:** 2026-05-31  
**Status:** Entscheidungen aus dieser Session — Skill-Struktur noch offen (nächste Session)

---

## Neuer Pipe-Flow (beschlossen)

### Bisher (Opus-seitig, pre-crawl, pattern-basiert)

```
Opus: explore_site → filter_urls (--exclude-patterns, fnmatch) → crawl_site → index
         ↑ Opus entscheidet pre-crawl welche URLs überhaupt gecrawlt werden
```

Filter-Logik: `filter_urls_workflow` + `match_any()` in `src/crawler/filter_urls.py`.
Patterns werden vor dem Crawl definiert — Opus muss die Noise-Muster kennen, BEVOR der Crawl läuft.

### Neu (Worker-seitig, post-crawl, content-basiert)

```
Worker: Discovery (agentic, __NEXT_DATA__-first) → Crawl → content-basiertes Drop-Assessment → Index
                                                              ↑ Worker entscheidet nach Crawl
```

**Entscheidungslogik:** Der Worker crawlt alle gefundenen URLs, liest den Content, und entscheidet
per-URL ob der Content indexierbar ist. Drop-Kriterien sind content-basiert (leere Seite, redirect-only,
reine nav-page, duplicate content) — nicht pattern-basiert.

**Worker-Endreport-Form:**
```
URLs gefunden:  N
URLs gecrawlt:  M
URLs gedroppt:  K  (mit Begründung pro URL oder per Kategorie)
URLs indexed:   M-K
```

**Warum post-crawl besser:**
- Pattern-Filter vor dem Crawl erfordern Domain-Priorwissen (welche URL-Muster sind Noise?)
- Content-basierter Drop nach dem Crawl ist domain-agnostisch — der Worker sieht den echten Inhalt
- Passt zur generischen Discovery: wer die URLs ohne Priorwissen findet, sollte sie auch ohne Priorwissen filtern

**Konkrete Konsequenz:** `filter_urls` / `--exclude-patterns` bleibt als CLI-Tool für manuelle Nachbearbeitung,
wird aber kein Pflichtschritt mehr im Worker-Flow. Der Worker-Drop-Vorschlag ersetzt den pre-crawl-Filter
als primäre Qualitätsstufe.

---

## Hinweis: Nicht alle gefundenen URLs sind gleich wertvoll

Aus dem `__NEXT_DATA__`-Experiment:
- 299 der 305 goldstandard-URLs kamen aus FPT + GHEC-Sidebars (aktuelle, gepflegte Seiten)
- 6 kamen aus GHES 3.16 (älteste verfügbare Version): `projects-classic/*` + `repos/tags`
  — diese Seiten sind deprecated, in neueren Versionen nicht mehr verlinkt, und technisch
  veraltet (`projects-classic` = GitHub Classic Projects, seit Jahren abgekündigt)

Der Worker-Drop-Vorschlag löst genau das: Post-crawl kann der Worker erkennen, dass
deprecated-content dünn ist, veraltet wirkt, oder auf neuere Alternativen verweist —
und einen Drop empfehlen, ohne dass Opus vorher ein Pattern kannte.

---

## Offene Entscheidung (nächste Session): Skill-/Baukasten-Struktur

Zwei bestehende Pipeline-Skills:
- **web-research** (Opus-seitig): Discovery + evtl. Filterung, gibt gecrawlte URLs weiter
- **cleanup-and-index** (Worker-seitig): Indexierung, Post-processing

Offene Fragen:
1. **Umbenennung `cleanup-and-index`?** — der Name passt nicht mehr wenn der Worker auch Discovery +
   Crawl + Drop-Assessment macht. Kandidaten: `crawl-and-index`, `index-worker`, `doc-pipeline-worker`.
2. **Baukasten vs. monolithischer Skill:** Sollen Discovery, Crawl, Drop-Assessment, Index als
   einzelne wiederverwendbare Bausteine existieren (jeder aufrufbar), oder bleibt ein Worker-Skill
   der die ganze Pipeline macht?
3. **Vorgefertigte Scripts vs. Worker schreibt Scripts selbst:** Der Worker könnte (a) feste
   Scripts aufrufen (`06_nextdata_probe.py`, `crawl_site.py`, ...) oder (b) nach einem generischen
   Workflow selbst situationsabhängige Probe-Scripts schreiben. Option (b) ist flexibler aber
   schwerer zu testen und zu reproduzieren.
4. **`web-research` Scope:** Bleibt Opus für Discovery zuständig, oder übergibt Opus nur den Seed
   und der Worker macht Discovery + Crawl + Index komplett?

---

## Roadmap-Sequenz (beschlossen)

| Schritt | Was | Abhängigkeit |
|---------|-----|-------------|
| 1 | Skill-/Baukasten-Struktur entscheiden | nächste Session, offene Fragen oben |
| 2 | Scraping-Phase: geteilte CLI/Pipeline-Logik + prod-config | nach (1) — Struktur bestimmt wo Config lebt |
| 3 | Die 305 docs.github.com/de/rest URLs indexieren | nach (2) — Scraping muss production-ready sein |
| 4 | Zweite Website als Prüfstand | nach (3) — generische Discovery auf unbekannter Domain testen |

Schritt 4 ist der eigentliche Generalisierbarkeitsbeweis: funktioniert der `__NEXT_DATA__`-Ansatz
auf einer anderen Next.js-Doc-Site, oder braucht es site-spezifische Anpassungen?
