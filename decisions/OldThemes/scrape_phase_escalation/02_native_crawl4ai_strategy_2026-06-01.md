# Scrape Phase-Escalation: Native Crawl4AI Strategy

**Date:** 2026-06-01
**Topic:** Ablösung der hand-gebauten 4-Phasen-Kette durch einen einzigen crawl4ai-Browser-Call mit dokumentierter Anti-Bot-Baseline.

## Sources

- `decisions/scrape_pipeline.md` — IST before/after this migration
- `decisions/OldThemes/scrape_phase_escalation/01_networkidle_timeout_cost_2026-05-24.md` — Vorgänger-Analyse: networkidle-Timeout-Kosten + Hamster-Wheel-Risiko
- `src/scraper/scrape_url.py` — Code vor und nach der Migration
- `venv/lib/python3.14/site-packages/crawl4ai/async_configs.py:1399–1519` — CrawlerRunConfig 0.8.6 Konstruktor
- `venv/lib/python3.14/site-packages/crawl4ai/async_crawler_strategy.py:76,117,762–763` — UndetectedAdapter-Wiring, page_timeout
- `venv/lib/python3.14/site-packages/crawl4ai/browser_manager.py:95,763` — enable_stealth GPU-Flags + StealthAdapter-Bedingung

## Ausgangslage

Die alte Kette (`fastpath → browser_1a/networkidle → browser_1b/domcontentloaded → browser_2_stealth`) hatte drei strukturelle Schwächen:

1. **Nicht-deterministisch in der Laufzeit.** networkidle-Timeout von 60s war der Worst Case auf tracker-heavy Sites (BfN.de: 90s total wall, `01_networkidle_timeout_cost_2026-05-24.md`). Keine harte Navigationsgrenze — nur ein implizierter Crawl4AI-Default.
2. **Kaskadierender Overhead.** Jede Phase startet eine neue `AsyncWebCrawler`-Instanz. Bei fastpath-Miss + networkidle-Timeout + domcontentloaded-Fallback wurden drei Browser-Prozesse gestartet, bevor überhaupt die Stealth-Phase erreicht wurde.
3. **Komplexität ohne strategischen Gewinn.** Per-Phase-Tuning (welche Wait-Strategie für welchen Site-Typ?) ist der Hamster-Wheel-Anteil: fine-tune für Site A, Site B regrediert. Die Erkenntnis aus 01 war, dass nur domain-agnostische Optimierungen strukturell sinnvoll sind.

## Ziel-Config und Herleitung

**Einzelner Call, vier Parameter-Entscheidungen:**

### `wait_until="load"` statt networkidle/domcontentloaded-Kaskade

`networkidle` wartet auf 500ms Zero-Netzwerk-Aktivität — auf tracker-heavy Sites (Analytics, Social Pixels) nie erreicht → 60s Timeout unausweichlich. `domcontentloaded` feuert zu früh, verpasst JS-injected Content bei echten SPAs. `load` ist der Mittelweg: fired when the page and all subresources (images, scripts) have loaded — vollständig genug für die meisten Sites, aber ohne den Idle-Wait von networkidle. Weniger hängeanfällig bei Polling-Heavy-Sites.

### `page_timeout=60000` (explizit)

Harte Navigationsgrenze. Bestätigt als Navigations-Timeout in `async_crawler_strategy.py:762–763`:
```python
response = await page.goto(url, wait_until=config.wait_until, timeout=config.page_timeout)
```
Worst Case: 60s Navigation + kurze Crawl4AI-Overhead = ~64s/URL. Determinismus: der Call scheitert sauber mit einem bekannten Timeout statt unendlich zu hängen.

### `magic=True`

crawl4ai-Dokumentation: "attempts automatic handling of overlays/popups". Ergänzt `excluded_selector=COOKIE_CONSENT_SELECTOR` auf JS-Ebene: der Selector entfernt DOM-Nodes vor dem Crawl, `magic` dismissed dynamisch erzeugte Overlays, die kein statisches DOM-Markup haben. Zusammen: No-Blocking-Baseline ohne per-Site-JS-Code.

### `enable_stealth=True` + `UndetectedAdapter` — Kohärenz und #1959

Die ursprüngliche Frage war: ist `enable_stealth=True` in 0.8.6 ein No-Op, wenn `UndetectedAdapter` bereits verwendet wird?

**Code-Analyse 0.8.6:**

`browser_manager.py:763`:
```python
if self.config.enable_stealth and not self.use_undetected:
    from .browser_adapter import StealthAdapter
    self._stealth_adapter = StealthAdapter()
```

`async_crawler_strategy.py:117`:
```python
use_undetected=isinstance(self.adapter, UndetectedAdapter)
```

Wenn `UndetectedAdapter` verdrahtet ist, ist `use_undetected=True` → die Bedingung in `browser_manager.py:763` ist `True and not True = False` → `StealthAdapter` (playwright-stealth) wird NICHT geladen. Das ist kein Bug — es ist beabsichtigt: `UndetectedAdapter` (Patchright) ist der stärkere Mechanismus, playwright-stealth wäre redundant.

**`enable_stealth=True` trägt trotzdem bei** via `browser_manager.py:95`:
```python
if not config.enable_stealth:
    flags.extend([
        "--disable-gpu",
        "--disable-gpu-compositing",
        "--disable-software-rasterizer",
    ])
```
Mit `enable_stealth=True` werden diese Flags weggelassen → WebGL bleibt aktiv → Anti-Bot-Sensoren, die GPU-Abwesenheit als Headless-Signal verwenden, finden kein Signal. Komplementär zu Patchright, nicht redundant.

**Verhältnis zu GitHub Issue #1959:** #1959 betrifft den Fall, dass `enable_stealth` in bestimmten 0.8.x-Versionen ein vollständiger No-Op war (playwright-stealth wurde nicht korrekt geladen). Auf 0.8.6 trifft uns das NICHT: der playwright-stealth-Pfad über `StealthAdapter` wird bewusst übersprungen (weil `use_undetected=True`), aber der WebGL-GPU-Flags-Effekt von `enable_stealth` ist aktiv. Der UndetectedAdapter liefert die primäre Evasion via Patchright; `enable_stealth=True` ist ein kohärenter Zusatz, keine leere Annotation.

## Fastpath-Wegfall

Der httpx-Fastpath (`fetch_markdown_fastpath`) wurde entfernt. Begründung des Users: der Adoption-Probe (Mai 2026) hat gezeigt, dass die Adoption gering ist (~0% bei Nicht-Cloudflare-CF-Kunden). Use-Case des Scrapers ist ad-hoc Agent-Recherche mit 2-3 URLs — Zeit ist NICHT das Kriterium. Der zusätzliche `httpx`-Import und die HTTP-Round-Trip-Komplexität stehen in keinem Verhältnis zum selten greifenden Nutzen. Ship-and-Observe als Verifikationsmethode: Scraping-Qualität wird über `scrape_log.jsonl` (Outcome-Feld, garbage_type) im Alltag beobachtet, kein formales Pre-Merge-Eval.

## Log-Schema-Entschlackung

Parallel zur Code-Vereinfachung: Phasen-Felder aus dem JSONL-Record entfernt (`phases_attempted`, `fastpath_hit`, `fastpath_miss_reason`, `timings_ms.*` Phasen-Keys, `phase_used`). `phase_used` vollständig gestrichen — vollständig aus `outcome` ableitbar (`outcome="ok"` ↔ Erfolg). Cleaneres Schema ohne Redundanz. `timings_ms` enthält nur noch `total_wall`.

## Verifikationsstrategie

Ship-and-Observe. Kein formales Eval vor dem Merge — der User hat explizit entschieden, dass 1:1 in Prod übernommen wird. Beobachtung über:
- `src/logs/scrape_log.jsonl`: `outcome`-Feld (garbage_type, empty vs ok Rate)
- Anekdotische Qualitäts-Checks im Alltag (Agent-Recherche, 2-3 URLs pro Session)
- Kein Rollback-Plan documented — bei systematischen Regressions: neues OldThemes-Phase.
