# crawl4ai Stealth Stack — Befunde für die Scraping-Phase

**Session:** 2026-05-31  
**Versionen:** crawl4ai 0.8.6, playwright-stealth 2.0.2, patchright 1.58.2  
**Quelle:** github_issues Collection (crawl4ai stealth issues), verifiziert via `pip show` + Import-Repro

---

## IST: Zwei Stealth-Mechanismen, einer kaputt

### Mechanismus A: playwright-stealth / `enable_stealth=True` — KAPUTT

`BrowserConfig(enable_stealth=True)` injiziert playwright-stealth-JS. Abhängigkeit:

```python
# src/crawl4ai/async_crawler_strategy.py → browser_adapter.py:161
from playwright_stealth import stealth_async   # ImportError auf 0.8.6
```

`playwright_stealth` exportiert `stealth_async` nicht mehr in 2.0.x — API-Break zwischen
playwright-stealth 1.x → 2.0. Auf crawl4ai 0.8.6 + playwright-stealth 2.0.2 wirft jeder
`enable_stealth=True`-Aufruf **`ImportError`** beim ersten tatsächlichen Stealth-Inject.

**Fix:** crawl4ai PR #1960 (noch nicht released auf 0.8.6). Auf unserer Version ist
`enable_stealth=True` ein **No-Op** (oder crasht, je nach Codepfad).

### Mechanismus B: `UndetectedAdapter` + patchright — FUNKTIONIERT

```python
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
from crawl4ai import UndetectedAdapter

strategy = AsyncPlaywrightCrawlerStrategy(
    browser_config=cfg,
    browser_adapter=UndetectedAdapter(),
)
```

Anderer Mechanismus: patchright 1.58.2 patcht Playwright auf C++-Ebene (V8-Fingerprint-Hiding,
`navigator.webdriver = false`, Canvas/WebGL-Noise). Nicht berührt von PR #1959 (playwright-stealth
Import-Fix). Das ist der **einzige funktionierende Stealth-Pfad** auf 0.8.6.

Aktiv in Produktion: `src/crawler/explore_site.py` `--stealth`-Flag und `src/scraper/scrape_url.py`
Phase-2-Escalation nutzen beide diesen Pfad.

---

## Gotcha: UndetectedAdapter + hohe Concurrency = instabil

**crawl4ai Issue #1500:** `UndetectedAdapter` bei Concurrency > 1 crasht häufig mit:

```
Target page/context/browser has been closed
```

Ursache: patchright-Patching ist nicht thread-/task-safe unter parallelen `arun()`-Aufrufen.
Symptom: nicht-deterministisch (manchmal funktioniert Concurrency=2, manchmal crasht es sofort).

**Konsequenz für Scraping-Phase:**
- Stealth + Concurrency > 1 = instabil / nicht reproduzierbar — **nicht verwenden**
- Stealth-Scraping bleibt sequentiell (Concurrency=1)
- Ohne Stealth: Concurrency bis zu 3 laut `05_playwright_bfs.py` dokumentiert (WAF-Verhalten
  bei hoher Concurrency noch nicht gemessen — treat as experimental)

---

## Entscheidungsmatrix für Scraping-Phase

| Anforderung | Mechanismus | Stabil? |
|------------|------------|---------|
| Stealth, seq. (WAF-geschützte Sites) | `UndetectedAdapter` + patchright, Concurrency=1 | ✅ |
| Stealth, parallel | `UndetectedAdapter` + Concurrency >1 | ❌ (Issue #1500) |
| Kein Stealth, parallel | Standard `BrowserConfig`, Concurrency 2-3 | ✅ experimentell |
| `enable_stealth=True` (any) | playwright-stealth ImportError | ❌ (0.8.6) |

---

## Quellen

- crawl4ai Issue #1500: UndetectedAdapter crash bei hoher Concurrency
- crawl4ai PR #1959: playwright-stealth `stealth_async` Import-Fix (noch nicht in 0.8.6)
- crawl4ai PR #1960: enable_stealth Codepfad-Fix (noch nicht in 0.8.6)
- `pip show crawl4ai playwright-stealth patchright` — Versionsverifikation diese Session
- Import-Repro: `from playwright_stealth import stealth_async` → `ImportError` auf 0.8.6 + playwright-stealth 2.0.2
