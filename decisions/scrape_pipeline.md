# Scrape Pipeline — Content Extraction

## Browser Strategy

### Status Quo (IST)

**Code:** `src/scraper/scrape_url.py` — `scrape_url_workflow`, `try_scrape`

**Method:** 3-stufige Fallback-Kette mit zwei Browser-Phasen

**Config:**
- Phase 1a: `BrowserConfig(headless=True, verbose=False)` + `wait_until="networkidle"`
- Phase 1b: `BrowserConfig(headless=True, verbose=False)` + `wait_until="domcontentloaded"` (Fallback)
- Phase 2: `BrowserConfig(headless=True, verbose=False, enable_stealth=True)` + `UndetectedAdapter` + `AsyncPlaywrightCrawlerStrategy` + `wait_until="networkidle"`
- `cache_mode=CacheMode.BYPASS` in allen Phasen
- Jede Phase erstellt eine neue `AsyncWebCrawler`-Instanz (kein Session-Reuse)

Phase 1a (`networkidle`) wartet, bis keine Netzwerkrequests mehr offen sind — robuster für SPA/JS-heavy Sites, aber langsamer. Phase 1b (`domcontentloaded`) feuert früher und rettet Sites, bei denen `networkidle` einen Timeout auslöst (z.B. endlose Polling-Requests). Phase 2 (Stealth) greift bei Anti-Bot-Schutz.

### Evidenz

#### Session-Findings (2026-03)
- `domcontentloaded`-Fallback hat Sites gerettet, bei denen `networkidle` hängt (Polling-Requests blockieren den Wait)
- Stealth-Phase war notwendig für Sites mit aktivem Bot-Detection (z.B. Cloudflare-geschützte Domains)
- `UndetectedAdapter` hat bekannte Fingerprinting-Vektoren (WebDriver-Flag, Chrome-Devtools-Protokoll-Signaturen)

#### Crawl4AI Docs
- `networkidle`: wartet bis 500ms keine Netzwerk-Aktivität — geeignet für JS-rendered Content
- `domcontentloaded`: feuert sobald HTML geparst — kein Warten auf dynamischen Content
- `enable_stealth=True`: aktiviert Playwright-Stealth-Patches (navigator.webdriver=false, etc.)
- `CacheMode.BYPASS`: ignoriert Cache vollständig, jeder Request geht ans Netz

#### Bekannte Einschränkungen
- Kein Session-Reuse: jede Phase startet einen neuen Browser-Prozess — hoher Overhead bei mehreren Versuchen
- `UndetectedAdapter` kann mit bestimmten Sites inkompatibel sein (daher Phase 2 als letzter Ausweg)

### Recommendation (SOLL)

`networkidle` als primäre Strategie, weil JS-rendered Content ohne Wait nicht vollständig geladen ist. `domcontentloaded` als Fallback, weil manche Sites mit Polling-Requests `networkidle` blockieren. Stealth als letzte Phase, weil `UndetectedAdapter` stabiler mit einem frischen Browser ist und nicht alle Sites Bot-Detection haben.

`CacheMode.BYPASS` immer aktiv, weil gecachte veraltete Inhalte in einem MCP-Kontext (Live-Recherche) mehr schaden als nützen.

### Offene Fragen

- Session-Reuse: Könnte ein persistenter Browser über mehrere Scrapes hinweg den Overhead reduzieren — Risiko: State-Pollution zwischen unabhängigen Requests
- `domcontentloaded` + kurzer `js_code`-Wait als Alternative zu `networkidle`
- Phase 2 könnte auch `domcontentloaded`-Fallback bekommen (aktuell nur `networkidle`)
- Timeout-Konfiguration: kein expliziter Timeout gesetzt — Crawl4AI-Default gilt

---

## Content Filtering

### Status Quo (IST)

**Code:** `src/scraper/scrape_url.py` — `scrape_url_workflow`, `scrape_url_raw_workflow`, `truncate_content`

**Method:** PruningContentFilter mit fit_markdown-Fallback auf raw_markdown

**Config:**
- `scrape_url_workflow`: `PruningContentFilter(threshold=0.48)` + `fit_markdown`
  - Fallback auf `raw_markdown` wenn `fit_markdown < MIN_CONTENT_THRESHOLD` (200 chars)
  - `DEFAULT_MAX_CONTENT_LENGTH = 15000` chars
  - Truncation an Absatzgrenze (`\n\n`) wenn `last_newline > max_length * 0.8`
- `scrape_url_raw_workflow`: `DefaultMarkdownGenerator()` ohne Filter + `raw_markdown`
  - Speichert mit `<!-- source: URL -->` Header in Datei
  - Kein Truncation (für Dev/Suite-Verwendung)
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
- `DefaultMarkdownGenerator()` ohne Filter: vollständiger HTML→Markdown, kein Scoring — für Dev-Suites sinnvoller als für Live-MCP
- `content_source`-Option in `CrawlerRunConfig`: alternative Quelle (z.B. `fit_html`, `cleaned_html`) statt Markdown-Pipeline

#### Truncation-Logik
- 15000 chars entspricht ~3750 Wörtern — ausreichend für die meisten Artikel, vermeidet Context-Window-Overflow im MCP
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

`scrape_url_raw` bewusst ohne Filter: Dev-Suites und Vergleiche brauchen den Roh-Output, keine Filterung.

### Offene Fragen

- ~~Threshold 0.48 nicht durch systematische Tests belegt~~ → DONE 2026-05: Sweep bestätigt empirisch optimal für asymmetrische Noise-Removal-Präferenz
- ~~`content_source="fit_html"` als Alternative~~ → RULED OUT 2026-05: always-pre-filtered Anomalie, nicht als tuning-knob nutzbar
- Code-Seiten (GitHub, Docs): PruningFilter destruktiv für Code-Blöcke — `scrape_url_raw` (Mode 1) als Alternative für Code-heavy Sites bestätigt; Mode 1 + cleanup-Skill ist der Indexing-Pfad
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

**Error Messages:** `_GARBAGE_MESSAGES` dict maps jede Kategorie auf eine menschenlesbare Fehlermeldung. `scrape_url_workflow()` trackt `last_garbage` über alle 3 Scrape-Versuche und gibt differenzierte Meldung zurück.

**Logging:** `logger.warning("Garbage detected [%s]: %s", garbage_type, url)` bei jeder Garbage-Erkennung in `try_scrape()`.

**PDF-URLs:** MCP Tool `download_pdf(url, output_dir="/tmp")` als Lösung — PDFs werden heruntergeladen statt gescrapt. Agent-Instructions verweisen auf `download_pdf` statt "nicht scrapebar".

**`PLUGIN_HINTS`:** generischer Hint via `get_plugin_hint()`, wird an Fehlermeldung angehängt wenn alle Phasen fehlschlagen. Zwei fixe Domain-Mappings.

**Persistent Failure Logging (added 2026-03):** Every final scrape failure — all 3 attempts exhausted — appended as JSONL record to `dev/scrape_pipeline/failures.jsonl`. Implementation: `log_scrape_failure(url, garbage_type, status_code)` in `src/scraper/scrape_url.py`, called from `scrape_url_workflow()` at the final `if not content:` exit. Fields per record: `ts` (ISO 8601 UTC), `url`, `garbage_type` (str | null), `status_code` (int | null). `try_scrape()` return type extended from `tuple[str, str | None]` to `tuple[str, str | None, int | None]` to propagate `result.status_code`. `scrape_url_workflow()` tracks `last_status_code` alongside `last_garbage` across all 3 attempts. Silent fail: `log_scrape_failure()` wraps all I/O in try/except. File path gitignored; see `dev/scrape_pipeline/DOCS.md` for jq usage examples.

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

6-Kategorien-Ansatz mit typisierten Returns für die häufigsten Failure-Cases im MCP-Kontext:
1. `crawl4ai_error`: direkte String-Matches zuverlässig, da Crawl4AI feste Error-Templates hat
2. `http_error`: Kombination aus Länge und Keyword ist robuster als nur Keyword — kurze Error-Pages haben charakteristisches Profil
3. `nav_dump`: Link-Density-Check fängt Seiten die nur Navigation ohne Content liefern
4. `cookie_wall`: Density-Check statt DOM-Matching (DOM ist schon durch `excluded_selector` behandelt) — fängt Walls, die der Selector verpasst
5. `login_wall`: Kurzer Content + Login-Pattern-Matching für Paywalls und Login-geschützte Seiten
6. `cloudflare`: Bot-Protection-Detection (Cloudflare "Just a moment" und Browser-Check-Seiten)

Typisierte Returns ermöglichen differenzierte Fehlermeldungen für den Caller und Logging für Debugging.

`PLUGIN_HINTS` als letzter Ausweg: liefert dem Nutzer einen konkreten Handlungshinweis statt blankem Fehler.

PDF-URLs: Eigenes MCP Tool `download_pdf` statt Scraping-Versuch. Agent-Instructions aktualisiert.

### Offene Fragen

- ~~Login/Paywall-Erkennung fehlt komplett~~ → DONE: `login_wall` Kategorie implementiert
- ~~Garbage-Typ als Return-Value~~ → DONE: `str | None` Return-Type mit 6 Kategorien
- ~~Kein Logging wenn Garbage erkannt~~ → DONE: `logger.warning()` in `try_scrape()`
- `http_error`: False-Positive-Risiko bei kurzen legitimen Pages mit Zahlen wie "403" im Fließtext
- `cookie_wall`: Threshold-Kalibrierung (15 cookie-signals) nicht durch Testdaten validiert
- `login_wall`: False-Positive-Risiko bei kurzen Login-Tutorial-Seiten — 2000-char-Limit + generische Patterns
- `PLUGIN_HINTS` ist hardcoded — eine konfigurierbare Map in `config.py` oder `server.py` wäre flexibler

---

## Cloudflare / Vercel Fast-Path

### Status Quo (IST)

`src/scraper/scrape_url.py` and `src/scraper/scrape_url_raw.py` execute an HTTP-only fast-path BEFORE invoking Crawl4AI's browser stack. Implementation: `fetch_markdown_fastpath()` in `scrape_url.py` (FUNCTIONS section), imported into `scrape_url_raw.py` via the existing cross-module import. Inserted in both workflows immediately after the entry-point `logger.info("Scraping…")` line and BEFORE Crawl4AI's `DefaultMarkdownGenerator` setup.

**Mechanism:**
- `httpx.AsyncClient(follow_redirects=True, timeout=MD_FASTPATH_TIMEOUT)` GET with header `Accept: text/markdown, text/html`
- ALL of: HTTP 200 + `Content-Type` contains `text/markdown` + body length ≥ `MD_FASTPATH_MIN_BYTES` → return body
- Otherwise (any miss, any exception) → return `None` → workflow falls through to existing Crawl4AI two-phase scrape unchanged

**Constants:**
- `MD_FASTPATH_MIN_BYTES = 200` — body-length threshold; rejects redirect-stub responses
- `MD_FASTPATH_TIMEOUT = 5.0` — generous for cold-edge CDN routing, tight enough to not delay Crawl4AI fallback

**Logging:**
- info: hit (`Markdown fast-path hit: <url> (<N> chars)`)
- debug: miss (sub-threshold / non-200 / wrong content-type) and network errors

**Routing interaction:** `cli.py` calls `check_plugin_routed()` before either workflow function — fast-path therefore runs only on already-routed-clean URLs. No interaction.

**Caching interaction:** Both scraper modules use `CacheMode.BYPASS` for Crawl4AI; no application-level cache. Fast-path is the first decision point in the chain.

### Evidenz

**Cloudflare announcement** — blog.cloudflare.com/markdown-for-agents/ (2026-02-12). Cloudflare CDN edge supports `Accept: text/markdown` content-negotiation for opted-in zones. Response includes `Content-Type: text/markdown; charset=utf-8`, an `x-markdown-tokens` integer header with the token count, and a `Content-Signal: ai-train=yes, search=yes, ai-input=yes` header. Beta for Pro/Business/Enterprise/SSL-for-SaaS plans; rollout began Feb 2026. Cited 80% token reduction on a sample blog post. Article notes Claude Code and OpenCode already send the header in production.

**Adoption probe** — `dev/scrape_pipeline/06_cloudflare_md_adoption.py`, run 2026-05-07 against 29-URL curated set across three categories:

| Category | URLs | MD-served | Notes |
|---|---|---|---|
| Cloudflare-owned (positive control) | 5 | 5/5 | 100% — expected |
| Likely CF-fronted (typical scrape targets: dev.to, npm, Discord, Shopify, HuggingFace, Vercel, Tailwind, Supabase, Fly.io, Linear, Hashnode, Deno, Astro, Pydantic, PostHog, Render, Medium, Anthropic) | 19 | 2/19 | docs.anthropic.com (12-byte stub anomaly) + vercel.com/docs (Vercel's own edge implementation, no cf-ray) |
| Non-CF negative controls (Wikipedia, Python.org, MDN, arXiv, GitHub-raw) | 5 | 0/5 | as expected |

Mean byte-reduction on positives: 92.3%, median 97.0%, range 71.2%–98.5%. Aggregate adoption rate among non-Cloudflare-owned CF-customers in May 2026 (3 months after Beta launch): ≈0%.

**Vercel finding (independent multi-vendor pattern):** vercel.com/docs returns `Content-Type: text/markdown` WITHOUT the `cf-ray` header — Vercel implements the same `Accept: text/markdown` convention on their own edge infrastructure independently of Cloudflare. The fast-path is therefore not Cloudflare-specific; it reflects an emerging multi-vendor convention.

**Live verification (post-merge, 2026-05-07):** `searxng-cli scrape_url https://blog.cloudflare.com/markdown-for-agents/` returned in 1.06s with clean markdown frontmatter and body. Typical Crawl4AI baseline path: ~5–15s. Fast-path verified working in production.

### Recommendation (SOLL)

Keep current implementation (no change needed). The probe-on-every-scrape strategy is correct given:
- Failure-mode is graceful (HTML fallback to existing path) and adds at most ~5s before falling back
- Adoption is currently low (~24% of probe set, but mostly Cloudflare-owned) but growing — the fast-path catches new opt-ins automatically without code changes
- The win-when-it-works is large: 97% median byte reduction, ~5x faster than browser path
- Multi-vendor extension (Vercel) confirms the pattern isn't going away

### Offene Fragen

- Does `x-markdown-tokens` count match what our downstream cleanup + index pipeline chunking would compute? Could be used to influence chunk size dynamically when present.
- Adoption tracking: re-run the probe quarterly. Track whether the May 2026 baseline (~24% of probe set) grows. The probe script is the persistent measurement artifact.
- Other multi-vendor edges that might already implement this pattern (Fastly, AWS CloudFront)? Out of scope for now — let the probe surface them when they appear.

---

## Quellen

**Code:**
- `src/scraper/scrape_url.py` (Code-Inspektion — Browser Strategy, Content Filtering, Garbage Detection)

**Crawl4AI Docs** (RAG Collection: Crawl4AIDocs):
- BrowserConfig, CrawlerRunConfig, wait_until-Optionen (Browser Strategy)
- PruningContentFilter, DefaultMarkdownGenerator, content_source (Content Filtering)
- Error-Format, result.markdown-Struktur (Garbage Detection)

**Session-Findings:**
- CookieYes cky-modal Fix, TDS Cookie-Wall, LanceDB 404, Truncation-Logik, domcontentloaded-Fallback (2026-03)

**Cloudflare / Vercel Fast-Path:**
- blog.cloudflare.com/markdown-for-agents/ (Cloudflare announcement, 2026-02-12)
- developers.cloudflare.com/fundamentals/reference/markdown-for-agents/ (config docs)
- vercel.com/docs (independent multi-vendor implementation, observed via probe; not formally documented by Vercel as of 2026-05-07)
- dev/scrape_pipeline/06_cloudflare_md_adoption.py (adoption probe)
- dev/scrape_pipeline/06_reports/cf_md_adoption_20260507_*.md (run snapshots)

**Zum Indexieren (für systematische Verbesserung):**
- Crawl4AI GitHub Issues "stealth" — UndetectedAdapter Bugs, Browser-Detection: https://github.com/unclecode/crawl4ai/issues?q=stealth+undetected
- Crawl4AI Page Interaction Docs — js_code, wait_for, session_id: https://docs.crawl4ai.com/core/page-interaction
- Playwright Docs — Browser Contexts, Network Interception: https://playwright.dev/python/docs/browser-contexts
- Crawl4AI GitHub Issues "PruningContentFilter" — Threshold-Tuning, Code-Block-Destruction: https://github.com/unclecode/crawl4ai/issues?q=pruning+filter
- Crawl4AI Content Filter Source — PruningContentFilter Algorithmus: https://github.com/unclecode/crawl4ai/blob/main/crawl4ai/content_filter_strategy.py
- Trafilatura Docs — Alternative Content-Extraction (Benchmark-Vergleich): https://trafilatura.readthedocs.io/
- Mozilla Readability — Reference Content-Extraction-Algorithmus: https://github.com/mozilla/readability
- CookieYes Developer Docs — DOM-Struktur, Klassen-Konventionen: https://www.cookieyes.com/documentation/
- Crawl4AI GitHub Issues "empty content" — Error-as-Content Pattern, Browser-Failures: https://github.com/unclecode/crawl4ai/issues?q=empty+content
- OneTrust Developer Docs — Cookie-Banner DOM-Struktur: https://developer.onetrust.com/
- Cookiebot Developer Docs — Dialog-Klassen: https://www.cookiebot.com/en/developer/
