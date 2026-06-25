# Scrape Pipeline — Content Extraction

## Browser Strategy

### Status Quo (IST)

**Code:** `src/scraper/scrape_url.py` — `scrape_url_workflow`, `try_scrape`

**Method:** Einzelner crawl4ai-Browser-Call mit nativer Anti-Bot-Baseline

**Config (`try_scrape`):**
- `BrowserConfig(headless=True, verbose=False, enable_stealth=True)`
- `UndetectedAdapter()` verdrahtet via `AsyncPlaywrightCrawlerStrategy(browser_config=..., browser_adapter=...)`
- `CrawlerRunConfig(magic=True, wait_until="load", page_timeout=60000, max_retries=0, cache_mode=CacheMode.BYPASS, markdown_generator=DefaultMarkdownGenerator(content_filter=PruningContentFilter(threshold=0.48)), excluded_selector=COOKIE_CONSENT_SELECTOR)`

**Parameter-Herleitung:**
- `enable_stealth=True` + `magic=True` — No-Blocking: `enable_stealth` hält WebGL aktiv (kein `--disable-gpu`), `magic` übernimmt automatisches Overlay/Popup-Handling
- `wait_until="load"` — Vollständigkeit: vollständiger Page-Load, weniger hängeanfällig als `networkidle` (kein 500ms-Idle-Wait), früher als `networkidle` auf tracker-heavy Sites
- `page_timeout=60000` — Determinismus: harte Navigationsgrenze, Worst Case ~64s/URL
- `UndetectedAdapter` — Patchright als primäre Anti-Bot-Evasion (ersetzt den schwächeren playwright-stealth-Pfad)
- `max_retries=0` — kein internes Retry (No-Op, entspricht Default), Determinismus
- `cache_mode=CacheMode.BYPASS` — kein Cache, jeder Request geht ans Netz

### Evidenz

Prozess-Narrative, Iteration-History und Alternativ-Bewertung (networkidle-Timeout-Kosten, Hamster-Wheel-Risiko, enable_stealth/#1959-Analyse): `decisions/OldThemes/scrape_phase_escalation/`

Crawl4AI 0.8.6 API-Verifikation:
- Alle `CrawlerRunConfig`-Parameter (`magic`, `wait_until`, `page_timeout`, `max_retries`) in `async_configs.py:1399–1519` vorhanden
- `page_timeout` als Navigations-Timeout bestätigt: `async_crawler_strategy.py:762–763` — `page.goto(url, wait_until=config.wait_until, timeout=config.page_timeout)`
- `UndetectedAdapter` + `AsyncPlaywrightCrawlerStrategy(browser_adapter=...)` API: `async_crawler_strategy.py:76`

### Recommendation (SOLL)

Keep — architecture is the IST.

### Offene Fragen

- Session-Reuse: Könnte ein persistenter Browser über mehrere Scrapes hinweg den Overhead reduzieren — Risiko: State-Pollution zwischen unabhängigen Requests
- `wait_until="load"` vs. kurzer `js_code`-Wait für Sites, die Content nach `load` nachladen (echte JS-SPAs)

---

## Content Filtering

### Status Quo (IST)

**Code:** `src/scraper/scrape_url.py` — `scrape_url_workflow`, `truncate_content`

**Method:** PruningContentFilter mit fit_markdown-Fallback auf raw_markdown

**Config:**
- `scrape_url_workflow`: `PruningContentFilter(threshold=0.48)` + `fit_markdown`
  - Fallback auf `raw_markdown` wenn `fit_markdown < MIN_CONTENT_THRESHOLD` (200 chars)
  - `DEFAULT_MAX_CONTENT_LENGTH = 15000` chars (fixed, no CLI param)
  - Truncation an Absatzgrenze (`\n\n`) wenn `last_newline > max_length * 0.8`
- `COOKIE_CONSENT_SELECTOR`: CSS-Selektor-Liste für DOM-Elemente vor dem Crawl entfernen
  - CookieYes: `cky-consent`, `cky-banner`, `cky-modal`
  - OneTrust: `onetrust-*`
  - Cookiebot: `CookiebotDialog`, `CookiebotWidget`
  - Generisch: `cc-banner`, `cc-window`, `gdpr`, `cookie-banner/consent/notice/law`

`PruningContentFilter` entfernt Blöcke mit niedrigem Informationsgehalt (Navigation, Footer, Werbung) anhand eines Scoring-Algorithmus. `fit_markdown` ist das gefilterte Ergebnis, `raw_markdown` der ungefilterte HTML-zu-Markdown-Output.

### Evidenz

#### Session-Findings (2026-03)
- `cky-modal` fehlte initial in `COOKIE_CONSENT_SELECTOR` — führte zu ~12K chars CookieYes-Consent-Wall als Content
- TDS (Towards Data Science) Cookie-Wall wurde durch den Selector nicht vollständig eliminiert — `is_garbage_content()` hat als zweite Verteidigungslinie gegriffen
- `fit_markdown`-Fallback auf `raw_markdown` rettet Short-Pages (z.B. simple API-Docs, One-Pager)

#### Crawl4AI Docs
- `PruningContentFilter(threshold=0.48)`: Blöcke unterhalb des Scores werden entfernt. Höherer Threshold = aggressivere Filterung
- Bekannte Limitation: PruningFilter kann Code-Blöcke zerstören, wenn sie als "low-density" eingestuft werden (wenig natürliche Sprache)
- `DefaultMarkdownGenerator()` ohne Filter: vollständiger HTML→Markdown, kein Scoring — für Dev-Suites sinnvoller als für Live-Recherche
- `content_source`-Option in `CrawlerRunConfig`: alternative Quelle (z.B. `fit_html`, `cleaned_html`) statt Markdown-Pipeline

#### Truncation-Logik
- 15000 chars entspricht ~3750 Wörtern — ausreichend für die meisten Artikel, vermeidet Context-Window-Overflow
- Absatzgrenze-Truncation (`\n\n` wenn > 80% der Grenze) verhindert mid-sentence cuts

#### Empirical Sweep (2026-05)

`dev/scrape_pipeline/04_overview_sweep/` — 36 configs × 20 URLs (Q24 search-result set across 5 page shapes: Blog / Paper-Landing / Forum-Thread / Repo-Heavy-Chrome / Index-Aggregator). Diff against clean-raw baseline (raw scrape + dev-only cleanup script).

Asymmetric preference frame: chrome retention is much worse than content loss. Quality > quantity. Filter must strip noise even at cost of some content detail, as long as title + general message preserved.

Per-config median F1 across 17 analyzed URLs (PDF stubs + scrape-failures excluded):

| Filter / source | F1 | Note |
|---|---|---|
| `none + cleaned_html` | 0.98 | quasi identical to clean-raw, no size reduction |
| `prune_030 + cleaned_html` | 0.89 | lenient, residual chrome (Skip-link visible on some sites) |
| **`prune_048 + cleaned_html`** (current prod) | **0.75** | **empirically optimal for asymmetric preference** |
| `prune_060 + cleaned_html` | 0.60 | aggressive, drops title text on short-title pages (e.g. webscraping.fyi shows `# ` empty header) |
| `prune_075 + cleaned_html` | 0.47 | title text gone, only body prose remains |
| `bm25 + *` | 0.05 | unusable for general overview — query-snippet extractor only |
| `* + fit_html` | 0.44 (constant) | anomaly: `fit_html` source is always-pre-filtered regardless of additional filter, not a useful tuning knob |

Per-shape break: `none + cleaned_html` wins on Blog/Forum/Index, `prune_030+` wins on Paper-Landing + Repo-Heavy-Chrome. Single-config trade-off: prune_048 most consistent across shapes for the noise-removal preference.

Cookies vs cookies+sphinx selectors: no measurable difference on this URL set (≤ 0.01 F1 delta).

**Closes 3 of 5 open questions:**
- threshold validation: prune_048 confirmed empirically optimal (asymmetric metric: precision over recall)
- content_source="fit_html": NOT useful (always-pre-filtered anomaly)
- 0.48 vs alternatives: 0.30 retains chrome, 0.60+ damages titles → 0.48 is sweetspot

### Recommendation (SOLL)

`PruningContentFilter(threshold=0.48)` als Standard: reduziert Boilerplate erheblich und hält Context klein. Threshold 0.48 ist empirisch — niedrig genug, um echten Content zu behalten, hoch genug, um Navigation/Footer zu entfernen.

`raw_markdown`-Fallback bei < 200 chars: sichert Short-Pages, wo der Filter zu aggressiv filtert.

`COOKIE_CONSENT_SELECTOR` als DOM-Intervention vor dem Crawl: entfernt Cookie-Walls auf DOM-Ebene, bevor Crawl4AI den Content verarbeitet — zuverlässiger als Post-Processing.

Raw markdown for pipe-scraping (offline doc indexing): handled by `crawl_site_workflow` in `src/crawler/crawl_site.py` — uses `DefaultMarkdownGenerator()` without filter, saves to files. Not exposed as a CLI command.

### Offene Fragen

- ~~Threshold 0.48 nicht durch systematische Tests belegt~~ → DONE 2026-05: Sweep bestätigt empirisch optimal für asymmetrische Noise-Removal-Präferenz
- ~~`content_source="fit_html"` als Alternative~~ → RULED OUT 2026-05: always-pre-filtered Anomalie, nicht als tuning-knob nutzbar
- Code-Seiten (GitHub, Docs): PruningFilter destruktiv für Code-Blöcke — raw mode (DefaultMarkdownGenerator via crawl_site) als Indexing-Pfad; für ad-hoc CLI-Scraping gibt es kein raw-mode equivalent (scrape_url_raw entfernt)
- Cookie-Consent via `excluded_selector` entfernt den DOM-Node, aber manchmal bleibt ein Overlay-Backdrop — JS-basierte Dismissal wäre robuster
- `MIN_CONTENT_THRESHOLD` (200 chars) ggf. zu niedrig — 200 chars kann auch ein valider Error-Text sein
- **15K cap removal pending (2026-05-06 user direction)** — `DEFAULT_MAX_CONTENT_LENGTH = 15000` strippt 95% von long-form articles (seirdy.one 226K → 14K), verzerrt empirische Vergleiche. Removal via Prod-Migration-Bead nach pfk (Paper Mode) sequenziert.
- **Per-shape filter dispatch?** — Sweep zeigte: Blog/Forum/Index profitieren von less filtering (none/prune_030), Paper-Landing/Repo profitieren von prune_048+. Single-config = Trade-off. Per-shape dispatch wäre konsistenter, würde aber eigene Shape-Detection-Logik vor dem Filter brauchen (Komplexität vs Crawl4AI's eingebauter Filter alone)

---

## Garbage Detection

### Status Quo (IST)

**Code:** `src/scraper/scrape_url.py` — `is_garbage_content`, `_GARBAGE_MESSAGES`, `get_plugin_hint`

**Method:** Rule-based Garbage-Detektion in 6 typisierten Kategorien + differenzierte Fehlermeldungen + Logging

**Return type:** `is_garbage_content()` returns `str | None` (None = not garbage, str = garbage type identifier)

**Config:**
- `crawl4ai_error` — Crawl4AI-Fehlermeldungen als Content:
  - Trigger: `"crawl4ai error:"`, `"document is empty"`, `"page is not fully supported"`
  - Bedingung: Pattern in `content.lower()`
- `http_error` — HTTP-Fehlerseiten (zwei Checks):
  - **Primary (status_code):** `result.status_code >= 400` in `try_scrape()` — direkt nach `crawler.arun()`, VOR Content-Analyse. Fängt gepolsterte 404-Seiten unabhängig von Content-Länge.
  - **Secondary (content heuristic):** `len(content) < 1000` UND eines von `"not_found"`, `"404"`, `"403"`, `"forbidden"`, `"access denied"`, `"page not found"` — Fallback wenn status_code nicht verfügbar
- `nav_dump` — Navigation-Dumps:
  - Trigger: `len(lines) >= 20` UND `link_lines / len(lines) > 0.6`
  - Bedingung: Mehr als 60% der Zeilen sind reine Markdown-Links
- `cookie_wall` — Cookie-Consent-Walls:
  - Trigger: `count("cookie") + count("consent") + count("duration") > 15` in ersten 5000 chars
  - UND `"consent preferences"` oder `"cookieyes"` oder `"cookie preferences"` im Sample
- `login_wall` — Login/Paywall-Seiten:
  - Trigger: `len(content) < 2000` UND eines von `"sign in"`, `"log in"`, `"login"`, `"subscribe to continue"`, `"create account"`, `"create an account"`, `"premium content"`, `"paywall"`, `"members only"`, `"subscriber only"`
- `cloudflare` — Cloudflare-Protection:
  - Trigger: `len(content) < 500` UND `"checking your browser"` oder `"enable javascript and cookies"`
  - ODER: `"just a moment"` UND `"cloudflare"` (ohne Längenlimit)

**Error Messages:** `_GARBAGE_MESSAGES` dict maps jede Kategorie auf eine menschenlesbare Fehlermeldung. `scrape_url_workflow()` gibt differenzierte Meldung auf Basis des `garbage_type` aus `try_scrape` meta zurück.

**Role:** `is_garbage_content()` dient ausschließlich der Klassifikation für Logging (`garbage_type` im JSONL-Record) und Fehlermeldung an den Caller. Bei erkanntem Garbage ohne Recovery (cookie_wall-Stripping fehlgeschlagen oder anderer Typ) scheitert der Scrape und wird als `garbage_type` geloggt. Kein Retry über weitere Phasen — ein einziger Call.

**Logging:** `logger.warning("Garbage detected [%s]: %s", garbage_type, url)` bei jeder Garbage-Erkennung in `try_scrape()`.

**PDF-URLs:** `scrape_url` returns `"PDF must be downloaded by the user: <url>"` when the URL path ends in `.pdf`. The user downloads PDFs themselves — no scrape attempt is made.

**`PLUGIN_HINTS`:** generischer Hint via `get_plugin_hint()` (Stub — gibt immer `""` zurück), wird an Fehlermeldung angehängt wenn Scrape scheitert.

**Consent-Prefix Stripping (added 2026-04):** `strip_consent_prefix()` in `src/scraper/scrape_url.py` — recovery for `cookie_wall` pages. When `is_garbage_content()` returns `cookie_wall`, `try_scrape()` attempts to strip the leading consent block and recover actual page content instead of immediately discarding. Only triggers on `cookie_wall`; all other garbage types still discarded immediately.

Algorithm:
1. Count CONSENT_WORDS (`cookie`, `consent`, `einwilligung`, `tracking`, `akzeptieren`, `datenschutz`, `zweck`) in first 3000 chars
2. If density ≤ 5 (CONSENT_DENSITY_THRESHOLD): return original unchanged (baseline pages safe)
3. Search for first `#` or `##` heading after offset 300 (CONSENT_SKIP_OFFSET)
4. If heading found: return content from that heading onward
5. If no heading: return original unchanged

Recovery condition: stripped content must (a) differ from original and (b) pass `is_garbage_content()` returning None; otherwise falls through to normal garbage discard. Prototype source: `dev/scrape_pipeline/garbage_eval/09_garbage_fix_prototype.py`. `cookie_wall` threshold calibration (>15 cookie-signals) remains open — see Offene Fragen.

### Evidenz

#### Session-Findings (2026-03)
- CookieYes-Wall (cky-modal fehlte in Selector): `is_garbage_content()` hat als zweite Verteidigungslinie korrekt als Garbage erkannt und `""` zurückgegeben — Fallback auf Phase 2 (Stealth) hat geholfen
- TDS (Towards Data Science): Cookie-Consent-Density-Check hat ausgelöst
- LanceDB 404-Seite: Kategorie 2 (kurz + "404" im Text) hat korrekt gefeuert
- `"duration"` als Cookie-Signal: CookieYes-Walls enthalten typischerweise Cookie-Laufzeiten ("Duration: 1 year") — erhöht den Signal-Score

#### Schwäche des aktuellen Ansatzes
- `http_error`: 1000-char-Limit ist willkürlich — eine kurze, valide One-Pager-Seite könnte fälschlicherweise als Garbage eingestuft werden, wenn sie zufällig "403" im Text hat (z.B. ein Artikel über HTTP-Statuscodes)
- `cookie_wall`: Threshold 15 wurde nicht systematisch kalibriert — ein legitimer Cookie-Policy-Artikel könnte fälschlicherweise getriggert werden
- `login_wall`: 2000-char-Limit + generische Patterns ("log in", "sign in") könnten auf kurzen Login-Tutorial-Seiten false-positive triggern

#### PLUGIN_HINTS Logik
- Hints werden nur ausgespielt, wenn ALLE Phasen Garbage/leer zurückgeben
- Zwei fixe Domain-Mappings — nicht konfigurierbar ohne Code-Änderung

### Recommendation (SOLL)

6-Kategorien-Ansatz mit typisierten Returns für die häufigsten Failure-Cases:
1. `crawl4ai_error`: direkte String-Matches zuverlässig, da Crawl4AI feste Error-Templates hat
2. `http_error`: Kombination aus Länge und Keyword ist robuster als nur Keyword — kurze Error-Pages haben charakteristisches Profil
3. `nav_dump`: Link-Density-Check fängt Seiten die nur Navigation ohne Content liefern
4. `cookie_wall`: Density-Check statt DOM-Matching (DOM ist schon durch `excluded_selector` behandelt) — fängt Walls, die der Selector verpasst
5. `login_wall`: Kurzer Content + Login-Pattern-Matching für Paywalls und Login-geschützte Seiten
6. `cloudflare`: Bot-Protection-Detection (Cloudflare "Just a moment" und Browser-Check-Seiten)

Typisierte Returns ermöglichen differenzierte Fehlermeldungen für den Caller und Logging für Debugging.

`PLUGIN_HINTS` als letzter Ausweg: liefert dem Nutzer einen konkreten Handlungshinweis statt blankem Fehler.

PDF-URLs: `scrape_url` returns an error for `.pdf`-suffix URLs — the user downloads them.

### Offene Fragen

- ~~Login/Paywall-Erkennung fehlt komplett~~ → DONE: `login_wall` Kategorie implementiert
- ~~Garbage-Typ als Return-Value~~ → DONE: `str | None` Return-Type mit 6 Kategorien
- ~~Kein Logging wenn Garbage erkannt~~ → DONE: `logger.warning()` in `try_scrape()`
- `http_error`: False-Positive-Risiko bei kurzen legitimen Pages mit Zahlen wie "403" im Fließtext
- `cookie_wall`: Threshold-Kalibrierung (15 cookie-signals) nicht durch Testdaten validiert
- `login_wall`: False-Positive-Risiko bei kurzen Login-Tutorial-Seiten — 2000-char-Limit + generische Patterns
- `PLUGIN_HINTS` ist hardcoded — eine konfigurierbare Map in `config.py` wäre flexibler

---

## Quellen

**Code:**
- `src/scraper/scrape_url.py` (Code-Inspektion — Browser Strategy, Content Filtering, Garbage Detection)
- `venv/lib/python3.14/site-packages/crawl4ai/async_configs.py:1399–1519` (CrawlerRunConfig 0.8.6 Konstruktor-Signatur)
- `venv/lib/python3.14/site-packages/crawl4ai/async_crawler_strategy.py:76,117,762–763` (UndetectedAdapter-Wiring, page_timeout-Wirkung)
- `venv/lib/python3.14/site-packages/crawl4ai/browser_manager.py:95,763` (enable_stealth GPU-Flags + StealthAdapter-Bedingung)

**Session-Findings:**
- CookieYes cky-modal Fix, TDS Cookie-Wall, LanceDB 404, Truncation-Logik (2026-03)
- Phasen-Eskalations-Analyse, networkidle-Timeout-Kosten, Ship-and-Observe-Entscheidung (2026-05/06): `decisions/OldThemes/scrape_phase_escalation/`

**Zum Indexieren (für systematische Verbesserung):**
- Crawl4AI GitHub Issues "stealth" — UndetectedAdapter Bugs, Browser-Detection: https://github.com/unclecode/crawl4ai/issues?q=stealth+undetected
- Crawl4AI Page Interaction Docs — js_code, wait_for, session_id: https://docs.crawl4ai.com/core/page-interaction
- Crawl4AI GitHub Issues "PruningContentFilter" — Threshold-Tuning, Code-Block-Destruction: https://github.com/unclecode/crawl4ai/issues?q=pruning+filter
- CookieYes Developer Docs — DOM-Struktur, Klassen-Konventionen: https://www.cookieyes.com/documentation/
- OneTrust Developer Docs — Cookie-Banner DOM-Struktur: https://developer.onetrust.com/
- Cookiebot Developer Docs — Dialog-Klassen: https://www.cookiebot.com/en/developer/
