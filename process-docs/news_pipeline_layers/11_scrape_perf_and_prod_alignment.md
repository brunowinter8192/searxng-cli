# Iter 11 — Scrape Performance & Prod Alignment

**Date:** 2026-06-07
**State:** Problem analysiert, Directive klar. Umbau von 02b steht als nächster Schritt aus.

---

## Scrape-Performance-Problem (Lauf 2026-06-07)

**Symptom:** Stage 02b lief in den Orchestrator-Timeout (600s, ERROR im Log). Ergebnis: 0 ok / 0 failed → cleanup + publish übersprungen → Lauf 1 hat **nichts** indexiert.

**Gemessene Rate:** 19 MDs produziert in 600s = ~31s/URL.

**Ursache (Code-belegt, Rate-gestützt):**

`02b` nutzt `fetch_with_fallback` — networkidle zuerst, domcontentloaded als Fallback:

```python
async def fetch_with_fallback(crawler, url, run_config, run_config_fallback):
    result = await crawler.arun(url=url, config=run_config)   # wait_until="networkidle"
    content = result.markdown.raw_markdown if result.markdown else ""
    if content:
        return content, "networkidle"
    # Empty or timeout: retry with domcontentloaded
    result = await crawler.arun(url=url, config=run_config_fallback)
    ...
```

Auf werbe- und tracker-lastigen News-Seiten wie CoinDesk settled networkidle nie vollständig → läuft pro URL in den ~30s Page-Timeout → erst dann greift der schnelle domcontentloaded-Fallback. Dazu kommt: frischer `AsyncWebCrawler` (= neuer Playwright-Browser-Prozess) pro URL, ~2–5s Startup, plus voll sequenzielles Abarbeiten. Summe: ~31s/URL ist erklärbar und erwartbar.

---

## Prod-Vergleich (src/crawler/pipe_scraper.py)

Prod-Scraper macht dieselbe Aufgabe ~30× schneller:

| Dimension | 02b (dev) | Prod (pipe_scraper.py) |
|---|---|---|
| Browser-Session | Frische `AsyncWebCrawler`-Instanz pro URL | Eine geteilte Session |
| Concurrency | Voll sequenziell | `asyncio.gather` + `Semaphore(8)` per-domain |
| Page-wait | networkidle (primär) + domcontentloaded-Fallback | `delay_before_return_html` (fixes Delay, kein networkidle) |
| Rate-Limit | `asyncio.sleep(1.0)` fix | Scrapy `DOWNLOAD_DELAY=1.0` + Jitter |
| Messung | ~31s/URL (19 URLs in 600s) | ~1s/URL (316 URLs in 319s) |

Der geteilte Session-Ansatz war in iter 1 (`02_coindesk_scrape.py`) der Regwall-Auslöser (21/25 regwall'd). Der Wechsel auf frisch-pro-URL in iter 2 (`02b`) hat das gelöst — aber auf Kosten des Startups pro URL. Prod löst das anders: geteilte Browser-Instanz + frischer **Context** pro Request (innerhalb derselben Instanz), was sowohl Speed als auch Cookie-Isolation geben kann.

---

## Sitemap-vs-Discover-Vergleich (verifiziert 2026-06-07)

Stichprobe: 32 Discover-URLs vs. CoinDesk-Sitemap (`news-sitemap-index` + `articles-1.xml` / `articles-2.xml`), Fenster 2026-06-04 … 2026-06-07.

**A\B = 0: Alle 32 Discover-URLs sind in der Sitemap** (Sitemap ist Obermenge).

Per Datum:

| Datum | Discover | Sitemap | Nur-Sitemap |
|---|---|---|---|
| 2026-06-07 | 4 | 4 | 0 |
| 2026-06-06 | 13 | 13 | 0 |
| 2026-06-05 | 14 | 20 | 6 |
| 2026-06-04 | 1 | 25 | 24 |

**Fazit:** Für das Ziel-Fenster heute + gestern sind Discover und Sitemap **identisch** — der Browser-Discover ist vollständig für die Pipeline-relevante Zone. Die 30 Extras liegen ausschließlich in der Overshoot-Zone (06-04 / 06-05), die der Discover wegen Früh-Abbruch (PRE_48H_THRESHOLD) nur teilweise paginiert.

Praktische Implikation: Die Sitemap wäre gleichwertig, einfacher und vollständiger für tiefere Fenster, falls je ein breiteres Backfill-Fenster gebraucht wird. Für den täglichen 48h-Lauf ist der Browser-Discover validiert.

---

## Minor: Live-Blog-Filter zu eng

Der aktuelle Filter in `filter_live_blogs()` fängt nur `/live-markets-` im URL:

```python
kept = [e for e in entries if "/live-markets-" not in e["url"]]
```

Ein `/live-updates-`-Artikel ist beim 2026-06-07-Lauf durchgerutscht. Bei Ein-Tages-Fenstern ist das meist kein Problem; bei größeren Fenstern (mehr Paginierung) häufen sich solche URLs. Der Filter sollte auf ein breiteres Muster erweitert werden (z.B. `/live-`).

---

## Directive — Nächster Schritt: 02b auf Prod-Ansatz umstellen

**Eine Option, keine Auswahl:** 02b auf den Prod-Ansatz umstellen — geteilte Session + `asyncio.gather` + `Semaphore` + fixes Delay statt networkidle. Ziel: ~30× Speed-Up, damit 32 URLs in <60s durchlaufen statt in >600s.

**Bekanntes Risiko (empirisch zu prüfen, kein Block):** Geteilte Session kann die CoinDesk-Regwall wieder triggern (iter-1-Problem). Das ist ein Test, keine Option — wenn Regwall zurückkommt, beim Umbau lösen, z.B.:
- Frischer Playwright-Browser-Context pro URL innerhalb der geteilten Browser-Instanz (Cookie-Isolation ohne Browser-Prozess-Startup).
- Prod tut das bereits für andere Sites — prüfen ob pipe_scraper.py das als Muster liefert.

**Orchestrator-Timeout mitfixen:** Der fixe 600s-Timeout per Stage (`run_pipeline.py:_run()`) ist zu starr für den Scrape. Skalieren mit URL-Anzahl (z.B. `60 + n_urls * 30`) oder auf einen großzügigeren Fixwert (z.B. 1800s) setzen. Beim 02b-Umbau erledigen.

**Live-Blog-Filter erweitern:** `/live-` statt `/live-markets-` beim Umbau ergänzen (Minor, kein eigener Task).
