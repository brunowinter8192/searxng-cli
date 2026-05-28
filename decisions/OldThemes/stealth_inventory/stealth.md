# Stealth

> **Demoted to OldThemes 2026-05-28 (research-inventory artifact).** The only concrete production-stealth code path in the current codebase is the Phase-2 fallback (BrowserConfig(enable_stealth=True) + UndetectedAdapter in src/scraper/scrape_url.py — see decisions/scrape_pipeline.md → Browser Strategy). The remainder of this file is cross-layer detection-knowledge inventory and historical engine-status snapshots (pre-engine-cut 2026-04 SearXNG stack, Brave drop-decision). Kept as research reference.

Applies to: `src/search/` (pydoll-based custom engine) + `dev/search_pipeline/` (test suite)

## Detection Layers — Overview

| # | Ebene | Was geprüft wird | Unsere Stellschrauben | Status |
|---|-------|-------------------|----------------------|--------|
| 1 | **Browser-Fingerprint** | webdriver-Flag, WebGL vendor/renderer, Canvas Hash, navigator.plugins, chrome.runtime, Screen-Dimensionen, Permissions API, CSS media queries | screen/DPR/outer/css JS-Patches, `disable_blink_features=AutomationControlled` | 4/4 aktive Patches ON. WebGL, Canvas, chrome.runtime, navigator.plugins nicht implementiert |
| 2 | **Behavioral** | Request-Timing, fehlende Mausbewegung/Scrolling, Klick-Muster | `humanize_click`, `humanize_type`, `humanize_scroll` | Alle OFF |
| 3 | **Session-Tracking** | Cookie-Tracking über Queries, Cookie-Walls | SOCS consent cookie via CDP per Tab, `use_context` | SOCS ON, use_context OFF |
| 4 | **IP-Reputation** | Datacenter-IPs, VPN/Tor Exit-Nodes, Proxy-Listen | `proxy` per Engine | Direct only. Kein Proxy. |
| 5 | **Rate-Limiting** | X Requests/Zeitfenster pro IP | `delay_between_queries` | 0 — kein Delay (bewusst) |
| 6 | **TLS/HTTP-Fingerprint** | JA3 Hash, HTTP/2 Frame-Order, Header-Order | Nicht steuerbar — Chrome ist Chrome | OK (Chrome TLS ist real) |
| 7 | **CAPTCHA** | PoW (Brave), reCAPTCHA, hCaptcha | `captcha_path` URL-Erkennung | Detect-only, kein Solving |

## Stellschrauben-Inventar

### Global (config.yml + 01_google_smoke.py)

| Stellschraube | Ebene | Default (Baseline) | Effekt |
|---------------|-------|--------------------|--------|
| `disable_blink_features: AutomationControlled` | 1 | ON ✅ | Entfernt `navigator.webdriver=true` |
| `js_patches.screen_dimensions` | 1 | ON ✅ | screen.width/height/availWidth/availHeight/colorDepth/pixelDepth Override |
| `js_patches.device_pixel_ratio` | 1 | ON ✅ | window.devicePixelRatio = 2 |
| `js_patches.outer_dimensions` | 1 | ON ✅ | window.outerWidth/outerHeight Override |
| `js_patches.css_active_text` | 1 | ON ✅ | getComputedStyle Proxy — headless CSS-Color-Leak maskiert |
| `webrtc_leak_protection` | 1/4 | ON ✅ | Verhindert IP-Leak via WebRTC |
| WebGL vendor override | 1 | OFF ❌ | WebGL vendor/renderer Override (Apple M1 Pro) |
| Canvas noise | 1 | OFF ❌ | Subtile Canvas-Fingerprint-Randomisierung |
| Permissions override | 1 | OFF ❌ | Permissions.query Override für Notifications |
| chrome.runtime masking | 1 | NICHT IMPLEMENTIERT | chrome.runtime Object Spoofing |
| navigator.plugins spoofing | 1 | NICHT IMPLEMENTIERT | Fake Plugin-Liste für headless |
| `block_popups` | 2 | ON ✅ | Blockiert Pop-ups (kein Behavioral-Signal) |
| `block_notifications` | 2 | ON ✅ | Blockiert Notification-Requests |
| `humanize_click` | 2 | NICHT IMPLEMENTIERT | Menschenähnliche Klick-Muster |
| `humanize_type` | 2 | NICHT IMPLEMENTIERT | Menschenähnliches Tippen |
| `humanize_scroll` | 2 | NICHT IMPLEMENTIERT | Scroll mit Easing/Jitter |
| SOCS consent cookie | 3 | ON ✅ | CDP NetworkCommands.set_cookie pro Tab — bypassed Google Cookie-Wall |
| `use_context` | 3 | OFF ❌ | Frischer Browser-Context pro Query (Cookie-Isolation) |
| `delay_between_queries` | 5 | 0 ❌ | Pause zwischen Queries — 0 = kein Delay (bewusst) — Break bei ~90 queries/10min back-to-back → [Layer 5](#layer-5-rate-limiting) Batch 1 |
| `page_load_timeout` | 5 | 20s | Max Navigation-Wartezeit |

### Per-Engine (in config.yml google-Section)

| Stellschraube | Ebene | Effekt |
|---------------|-------|--------|
| `proxy` | 4 | None (direkt) — kein Proxy konfiguriert |
| `consent_cookie` | 3 | SOCS Cookie + Fallback consent_buttons für Google |
| `wait_for_results` | 2/5 | Max 15 Zyklen × 1s — kein aggressives Polling |
| `consent_settle` | 2 | 2s Settle nach Consent-Handling |

## Engine-Status

### Stresstest 2026-04-07 (Legacy — 9-Engine SearXNG-Stack)

| Engine | Score | Hauptproblem | Erkennungsebene | Routing |
|--------|-------|-------------|-----------------|---------|
| Google | 30/30 ✅ | — | — | direct, consent_cookie |
| Bing | 30/30 ✅ | — | — | direct |
| CrossRef | 30/30 ✅ | — | — | httpx API |
| Mojeek | 15/30 ⚠️ | Block ab Query 16 | Rate-Limiting (IP) | direct |
| DuckDuckGo | 6/30 ⚠️ | Bing-Redirect | Package-Bug (ddgs) | httpx |
| Brave | 1/30 ❌ | PoW CAPTCHA ab Query 2 | Fingerprint + Rate-Limiting | direct (Tor = 0/30) |
| Startpage | 0/30 ❌ | Zero results, kein Error | Unklar | direct |
| Google Scholar | 0/0 ❌ | Engine-Crash | Unklar | direct |
| Semantic Scholar | 3/30 ❌ | 429 Rate-Limit | Rate-Limiting (API) | httpx API |

### Neue Baseline 2026-04-21 (pydoll custom stack, single-engine)

| Engine | Score | Stack | Config |
|--------|-------|-------|--------|
| Google | 30/30 ✅ | headless pydoll Chrome, SOCS cookie, 4 JS-Patches | `dev/search_pipeline/config.yml` + `01_google_smoke.py` |

Dieser Run ist die aktuelle Referenz-Baseline. (Report deleted, see git history at 1ad627f.)

## Dropped Engines — Final Verdict

| Engine | Score | Grund |
|--------|-------|-------|
| Brave | 1–10/30 | PoW CAPTCHA, keine Kombination erreicht 30/30 — siehe Rationale unten |
| Startpage | 0/30 | Zero Results, Root Cause unklar |
| DuckDuckGo | 6/30 | Redirect zu Bing via ddgs-Bug |
| Mojeek | 15/30 | IP-basiertes Rate-Limit (15 req/60s, nicht umgehbar) |
| Semantic Scholar | 3/30 | 429 Rate-Limit (API) |

**Survivor-Set (aktiv in `src/search/`):** ~~Google, Bing, Google Scholar, CrossRef~~ — **historisch, vor Engine-Expansion**.

**Aktueller Stand (2026-05-04):** 8 aktive Engines im 4 req/min uniform Rate-Limit-Pool — Google, DuckDuckGo, Mojeek, Lobsters (Browser via pydoll); Google Scholar (Browser, JS-Fix 2026-05-04); CrossRef, OpenAlex, Stack Exchange (HTTP-API). Bing: src/search/engines/bing.py deleted 2026-05-04 (DOM-drift, no added value over DDG — see `decisions/OldThemes/engine_expansion_2026-05/bing_dropped.md`). HN dropped 2026-05-04 (rate-limit-cascade-hostile — see `decisions/OldThemes/engine_expansion_2026-05/hn_dropped.md`). Vollständige Engine-Expansion-Historie: `decisions/OldThemes/engine_expansion_2026-05/`.

**Update 2026-05-09:** Google Scholar Browser → HTTP migration (bead `searxng-f3i`). Scholar aus `_DEFAULT_ENGINES` ausgeschlossen wegen Google-Co-Fire-Decoupling — dormant in default queries bis Pooling-Rework. Plus Semantic Scholar (browser, added 2026-05-07) und Open Library (HTTP, 2026-05-08). Aktueller Default-Set: 9 Engines (Google, DDG, Mojeek, Lobsters, SemScholar via Browser; CrossRef, OpenAlex, StackExchange, Open Library via HTTP). Siehe `decisions/OldThemes/scholar_decoupling/20260509.md`.

### Brave — Drop-Entscheidung & Rationale

**Entscheidung: Brave wird gedroppt.**

Kern-Grund: Alle CAPTCHA-Lösungen (Warten, Klick-Lösung, API) sind inkompatibel mit der `asyncio.gather` Parallel-Engine-Architektur in `src/search/search_web.py`. Google liefert in ~0.2s. Ein Brave-CAPTCHA erzeugt 10–15s Minimum-Latenz pro Query — macht die gesamte Search-Response unbrauchbar.

Getestet und verworfen:
- Stealth-Patch-Matrix (8 Kombinationen, beste: WebGL +7 → 10/30) — Tabelle in [Layer 1: Browser-Fingerprint](#layer-1-browser-fingerprint)
- Patchright mit Chromium Binary → Slider CAPTCHA statt PoW, 0/30
- Camoufox (Firefox, headless) → 7/30
- PoW Reverse-Engineering (Argon2 + Privacy Pass VOPRF) — lösbar, aber Latenz-Problem bleibt
- Brave Search API (2K/Monat gratis) — kein CAPTCHA, aber Latenz-Architektur-Problem bleibt

### Wie Brave-Arbeit fortgesetzt werden kann

Voraussetzungen für Resume:
1. Architektur-Problem lösen: Brave aus `asyncio.gather` raus (eigener Timeout, Fallback auf restliche 3 Engines)
2. Patchright mit echtem Chrome Binary testen (`patchright install chrome` + `channel="chrome"` + `headless=True`) — wurde nie korrekt getestet
3. Alternativ: Brave Search API evaluieren

## Referenced Files

- `dev/search_pipeline/01_google_smoke.py` — Baseline-Implementation
- `dev/search_pipeline/config.yml` — Baseline-Config
- dev/search_pipeline/01_reports/smoke_20260421_022343.md (deleted, see git 1ad627f) — 30/30 Baseline-Run
- dev/search_pipeline/01_reports/smoke_20260421_182917.md (deleted, see git 1ad627f) — 28/30 Re-verify Run

---

## Layer 1: Browser-Fingerprint

### Status Quo (IST)

#### Baseline Mapping (2026-04-21)

Basis: `dev/search_pipeline/config.yml` + `dev/search_pipeline/01_google_smoke.py`.

**ON:**
- `--disable-blink-features=AutomationControlled` — entfernt `navigator.webdriver=true` Flag
- `screen_dimensions` patch — überschreibt `screen.width/height/availWidth/availHeight/colorDepth/pixelDepth` (1920×1080, colorDepth=30)
- `device_pixel_ratio` patch — setzt `window.devicePixelRatio = 2`
- `outer_dimensions` patch — setzt `window.outerWidth = innerWidth`, `window.outerHeight = innerHeight + 85`
- `css_active_text` patch — `getComputedStyle` Proxy maskiert headless-typischen CSS-Color-Wert (rgb(255,0,0) → rgb(0,102,204))
- User-Agent: Chrome 147 via `--user-agent=` CLI-Argument
- `webrtc_leak_protection: true` (pydoll-Attribut)
- Alle 4 JS-Patches via `PageCommands.add_script_to_evaluate_on_new_document` — injiziert sowohl beim Browserstart (initial tab) als auch per neuem Tab in `run_query()`

**OFF:**
- `patch_webgl` — WebGL vendor/renderer Override nicht konfiguriert
- `patch_canvas_noise` — Canvas-Fingerprint-Randomisierung nicht konfiguriert
- `patch_permissions` — Permissions.query Override nicht konfiguriert

**NICHT IMPLEMENTIERT:**
- chrome.runtime Object Masking (kein `window.chrome.runtime` Spoof)
- navigator.plugins Spoofing (leere Plugin-Liste in headless bleibt sichtbar)
- navigator.userAgentData brands Override (`Chromium` vs `Google Chrome`)

#### Detection Surface

Was Layer 1 prüft:

| Signal | Was erkannt wird | Unser Control |
|--------|-----------------|---------------|
| `navigator.webdriver` | `true` in headless | ✅ AutomationControlled entfernt es |
| Screen-Dimensionen | `screen.width/height = 0` in headless | ✅ Patch auf 1920×1080 |
| devicePixelRatio | 1.0 in headless (statt 2.0 auf Retina) | ✅ Patch auf 2 |
| outerWidth/outerHeight | Fehlt Titlebar-Offset | ✅ Patch +85px outer height |
| CSS active text color | rgb(255,0,0) headless-Artefakt | ✅ Proxy-Patch |
| WebGL vendor/renderer | `Google SwiftShader` = starkes headless-Signal | ❌ kein Patch |
| Canvas Hash | Deterministisch in headless | ❌ kein Rauschen |
| navigator.plugins | Leer in headless | ❌ kein Spoof |
| chrome.runtime | Fehlt in headless | ❌ kein Masking |
| Permissions API | `.query({name:'notifications'})` returns `denied` sofort | ❌ kein Override |
| Error.stack CDP trap | pydoll: `CDP Runtime.enable` detektierbar via Error.stack Getter | ❌ nicht gefixt |
| navigator.userAgentData | `brands: ["Chromium"]` statt `["Google Chrome"]` | ❌ kein Override |

### Evidenz

#### Brave Stealth-Patch-Matrix (2026-04-09)

| Stack / Patch | X/30 | Erste Failure | Delta vs Baseline |
|---------------|------|---------------|-------------------|
| pydoll Baseline (settle=0.0, proxy=None) | 3/30 | Query 3 | — |
| pydoll + patch_webgl=True | 10/30 | Query 11 | +7 |
| pydoll + patch_canvas_noise=True | 6/30 | Query 7 | +3 |
| pydoll + patch_permissions=True | 0/30 | Query 1 | -3 (kontraproduktiv) |
| pydoll + chrome.runtime + navigator.plugins | 0/30 | Query 1 | -3 (kontraproduktiv) |
| pydoll + alle Patches kombiniert | 0/30 | Query 1 | -3 (schlechte Patches dominieren) |
| Patchright (Chromium Binary) | 0/30 | Query 1 | -3 (Slider CAPTCHA statt PoW) |
| Camoufox (Firefox, headless) | 7/30 | Query 8 | +4 |

Erkenntnis: WebGL-Fingerprint ist das stärkste Einzelsignal. Permissions- und plugin-Patches sind bei Brave kontraproduktiv — Brave detektiert JS-Overrides dieser APIs direkt.

#### Brave Detection-Signale (2026-04-09, Reverse-Engineering)

- CDP `Runtime.enable` + `Error.stack` Getter Trap — pydoll betroffen, Patchright fixt es
- `navigator.userAgentData.brands`: `"Chromium"` statt `"Google Chrome"` (Patchright mit Chromium-Binary betroffen)
- `__playwright_evaluation_script__` in `Function.prototype.toString`
- `navigator.webdriver = true`
- WebGL SwiftShader Renderer (starkes Signal — WebGL-Patch bringt +7)
- `navigator.brave.isBrave` fehlt (Soft-Signal)

#### puppeteer-extra-plugin-stealth Vergleich (2026-04-07)

Fehlende Patches vs. puppeteer-extra:
- chrome.runtime Masking — nachträglich implementiert, kontraproduktiv bei Brave (0/30)
- navigator.plugins Spoofing — nachträglich implementiert, kontraproduktiv bei Brave (0/30)

Erkenntnis: Patches die bei Puppeteer Brave schlagen, sind bei pydoll ineffektiv oder schaden — vermutlich weil pydoll zusätzliche CDP-Leak-Signale hat.

### Recommendation (SOLL)

Pending — wird durch Stress-Test-Iterationen bestimmt. Aktuelle Baseline erreicht 30/30 (Google, Run 1, kein Load). SOLL wird nach erstem Break verfeinert.

Kandidaten für nächste Iteration (nach Stress-Break):
- WebGL-Patch (bringt +7 bei Brave — zu testen ob bei Google Effekt neutral oder positiv)
- Canvas-Noise (bringt +3 bei Brave — gleich testen)
- **NICHT** Permissions/plugins/chrome.runtime (kontraproduktiv bei Brave, unklar bei Google)

### Offene Fragen

- Brave: Werden JS-Overrides von Permissions/plugins direkt über CDP detektiert oder über Behavioral-Abweichung?
- Brave: Patchright mit echtem Chrome Binary (nicht Chromium) — wurde nie korrekt getestet (`patchright install chrome` + `channel="chrome"`)
- Google: Verhält sich WebGL-Patch neutral oder positiv bei 30/30-Runs? (Brave-Evidenz zeigt +7, Google könnte anders reagieren)
- navigator.userAgentData Override: Pydoll-Fähigkeit unklar — CDP `Emulation.setUserAgentOverride` mit `userAgentMetadata` wäre der Weg

---

## Layer 2: Behavioral

### Status Quo (IST)

#### Baseline Mapping (2026-04-21)

Basis: `dev/search_pipeline/config.yml` + `dev/search_pipeline/01_google_smoke.py`.

**ON:**
- `block_popups: true` — blockiert Pop-up-Fenster (reduziert unerwartete Interaktionen)
- `block_notifications: true` — blockiert Notification-Permission-Dialoge

**OFF / NICHT IMPLEMENTIERT:**
- Keine Mausbewegungen zwischen Queries
- Keine Scroll-Simulation
- Kein humanisiertes Klick-Muster
- Kein Typing (keine Formularinteraktion — Navigation direkt via URL)
- `delay_between_queries: 0` — kein Delay (Timing-Signal vorhanden, siehe Layer 5)
- `consent_settle: 2.0` — einzige Wartezeit, nur bei Consent-Handling

Der Baseline-Stack navigiert ausschließlich via `tab.go_to(url)` — kein DOM-Interaktion außer beim Consent-Fallback (`btn.click()`). Es gibt keine humanisierten Behavioral-Signale.

#### Detection Surface

Was Layer 2 prüft:

| Signal | Was erkannt wird | Unser Control |
|--------|-----------------|---------------|
| Request-Timing | Zu schnell, zu regelmäßig — bot-typisch | ❌ 0 Delay zwischen Queries |
| Mausbewegung | Fehlt komplett | ❌ nicht implementiert |
| Scroll-Verhalten | Fehlt | ❌ nicht implementiert |
| Klick-Muster | Zu präzise / sofort (kein Human-Jitter) | ❌ bei Consent-Button-Click |
| Tab-Aktivität | Neue Tabs öffnen/schließen ohne Idle | ⚠️ pro Query neuer Tab, sofort navigiert |

### Evidenz

Keine quantitativen Behavioral-Tests durchgeführt. Baseline-30/30 mit komplett OFF bestätigt, dass Google auf Layer 2 bei moderatem Traffic nicht aktiv blockiert.

### Recommendation (SOLL)

Pending — wird durch Stress-Test-Iterationen bestimmt. Erst wenn Stress-Break eintritt und Layer 5 (Rate-Limiting) ausgeschlossen ist, ist Behavioral der nächste Kandidat.

### Offene Fragen

- Google: Beginnt Behavioral-Detection erst bei hohem Traffic (>100 Queries pro Session) oder schon früher?
- Ist der 0-Delay-Effekt Layer 2 (Timing) oder Layer 5 (Rate-Limit) — vermutlich Layer 5 für IP-Blocking, Layer 2 für Session-Score-Erhöhung

---

## Layer 3: Session-Tracking

### Status Quo (IST)

#### Baseline Mapping (2026-04-21)

Basis: `dev/search_pipeline/config.yml` + `dev/search_pipeline/01_google_smoke.py`.

**SOCS Cookie Injection:**
- `config.yml` definiert: `consent_cookie: {name: SOCS, value: "CAISHAgCEhJnd3NfMjAyNjA0MDctMCAgIBgEIAEaBgiA_fC8Bg", domain: ".google.com", path: "/", secure: true}`
- Cookie wird per Tab injiziert via `NetworkCommands.set_cookie` (CDP `Network.setCookie`) mit `same_site=CookieSameSite.LAX`
- Injection erfolgt ZWEIFACH:
  1. Beim Browserstart in `start_browser()` — initial tab bekommt Cookie
  2. Pro Query in `run_query()` via `_inject_consent_cookie(tab, cfg)` — jeder neue Tab bekommt Cookie
- Effekt: Google Cookie-Wall (consent.google.com Redirect + Inline-Consent) wird komplett bypassed

**use_context: OFF:**
- Kein frischer Browser-Context pro Query
- Alle Queries laufen im gleichen Chrome-Profil-Context (`--user-data-dir=~/.searxng-mcp/browser-session-smoke`)
- Cookies akkumulieren über Session — kein Cookie-Isolation zwischen Queries

**Consent-Fallback:**
- `_has_inline_consent()` detektiert Inline-Consent via `'Before you continue'` im Body-Text
- `_handle_consent()` klickt ersten matchenden Button aus `consent_buttons` Fallback-Chain
- Nach Consent: 2s settle + erneute Navigation zur Search-URL

#### Detection Surface

Was Layer 3 prüft:

| Signal | Was erkannt wird | Unser Control |
|--------|-----------------|---------------|
| Cookie-Wall (Redirect) | Redirect zu consent.google.com | ✅ SOCS Cookie bypassed |
| Inline-Consent Banner | `'Before you continue'` auf Search-URL | ✅ Cookie + Fallback-Click |
| Session-Akkumulation | Gleiche Session-Cookies über 30 Queries | ⚠️ kein use_context — Cookies akkumulieren |
| Cookie-Fingerprint | SOCS-Wert ist fix — selber Wert bei jedem Start | ⚠️ unklar ob Google SOCS rotiert |

### Evidenz

- SOCS Cookie Bypass: Stresstest 2026-04-07 + neue Baseline 2026-04-21 — beide 30/30, kein einziger CONSENT-Status
- Brave: kein SOCS-Problem (Brave nutzt kein Google Cookie-System), aber use_context=OFF war aktiv → Session-Tracking beigetragen? Unklar

### Recommendation (SOLL)

Pending — wird durch Stress-Test-Iterationen bestimmt. Aktuelle Baseline zeigt, dass SOCS-Cookie ausreicht für 30/30 ohne Consent-Blockierung.

### Offene Fragen

- Brave: Trackt Brave per IP oder per Session? `use_context=True` würde Session-Tracking brechen, nicht IP-Tracking — relevant wenn Brave wieder aufgenommen wird
- SOCS-Wert: Läuft der Cookie ab? (Format `gws_20260407-0` — datum-basiert?) Muss er periodisch erneuert werden?
- Google Scholar: Braucht eigenen Consent-Cookie (anderer Domain)? (Scholar-Engine in src/ — nicht in smoke-Stack)

---

## Layer 4: IP-Reputation

### Status Quo (IST)

#### Baseline Mapping (2026-04-21)

Basis: `dev/search_pipeline/config.yml` + `dev/search_pipeline/01_google_smoke.py`.

**Direct Connection:**
- Kein Proxy konfiguriert
- Requests laufen über die lokale IP (Mac-Entwickler-IP, Heimnetz oder Büro-Netz)
- `webrtc_leak_protection: true` — verhindert WebRTC-basierte IP-Leaks (lokale IP via STUN)

**Kein Proxy-Support implementiert:**
- `config.yml` hat keinen `proxy`-Key
- Pydoll-Options haben kein `proxy`-Argument in der aktuellen Smoke-Implementation

#### Detection Surface

Was Layer 4 prüft:

| Signal | Was erkannt wird | Unser Control |
|--------|-----------------|---------------|
| Datacenter-IP | ASN-Klassifikation (AWS, GCP, DigitalOcean) | ✅ Heimnetz-IP unkritisch |
| VPN-IP | Bekannte VPN-Provider-ASNs | ⚠️ unklar (je nach Netz) |
| Tor Exit-Node | Öffentliche Tor-Exit-Node-Listen | ❌ Tor gelistet (0/30 Brave mit Tor) |
| Proxy-Listen | Bekannte kommerzielle Proxy-IPs | ❌ kein Proxy |
| IP-Rotation | Keine Rotation zwischen Queries | ❌ gleiche IP für alle 30 Queries |

### Evidenz

#### Tor Exit-Node Blocking (2026-04-07)

- Brave mit Tor-Proxy: 0/30 (alle Tor Exit-Nodes auf Blocklist)
- Brave ohne Proxy (direct): 1/30 — zeigt dass Layer 4 bei Brave aktiver ist als bei Google

#### Google IP-Tolerance

- Google 30/30 mit direkter IP bestätigt (2026-04-07 + 2026-04-21)
- Google scheint bei Heimnetz/Büro-IPs keine IP-Reputation-Probleme zu erzeugen bei dieser Query-Rate

### Recommendation (SOLL)

Pending — aktuell kein Problem für Google. Bei Stress-Tests über mehrere Runs hinweg (IP-Akkumulation) könnte IP-basiertes Blocking einsetzen.

Residential Proxies wären die Ideal-Lösung für IP-Rotation, stehen aber nicht zur Verfügung.

### Offene Fragen

- Residential Proxies: Nicht verfügbar — wäre optimale IP-Rotation (nicht detektierbar als Datacenter/VPN)
- Google: Ab welcher Query-Rate / welchem Zeitfenster beginnt IP-basiertes Blocking? (noch nicht stress-getestet)
- Mehrere Back-to-Back Runs: Akkumulieren sich IP-Signale über Runs, oder resettet Google nach gewissem Idle-Intervall?

---

## Layer 5: Rate-Limiting

### Status Quo (IST)

#### Baseline Mapping (2026-04-21)

Basis: `dev/search_pipeline/config.yml` + `dev/search_pipeline/01_google_smoke.py`.

**`delay_between_queries: 0`** — kein Delay zwischen Queries.

Rationale: 2026-04-07 Baseline lief mit 0 Delay und lieferte 30/30. Ein 10s Delay wurde 2026-04-16 als defensiver Wert eingebaut — ohne Evidenz, dass er nötig war. Im neuen Smoke-Stack wurde auf 0 zurückgesetzt.

**`page_load_timeout: 20`** — maximale Wartezeit pro Navigation.

**`consent_settle: 2.0`** — 2s Settle nur bei Consent-Handling (nicht zwischen normalen Queries).

**`wait_for_results.max_cycles: 15`, `interval_seconds: 1.0`** — bis zu 15 Sekunden Warten auf DOM-Ergebnisse pro Query.

Effektives Timing pro Query: Navigation (~1–2s) + DOM-Wait (0–15s, typisch 1–2s) + Tab-Open/Close (~0.1s). Kein expliziter Delay dazwischen.

Gesamte 30-Query-Run: ~2.5 Minuten (aus Baseline-Report `smoke_20260421_022343.md`).

#### Detection Surface

Was Layer 5 prüft:

| Signal | Was erkannt wird | Unser Control |
|--------|-----------------|---------------|
| X Requests/Zeitfenster (IP) | Rate > Threshold → 429 / Redirect zu /sorry/ | ❌ kein Delay — Rate ist hoch |
| Request-Pattern | Zu regelmäßig (kein Jitter) | ❌ natürliches Jitter durch DOM-Wait variiert |
| Burst-Detection | Viele Requests in kurzer Zeit | ❌ 30 Queries in ~2.5min = ~12 Req/min |

### Evidenz

#### Mojeek Rate-Limit (2026-04-09)

- Exakt 15 Requests pro ~60s Sliding Window
- Ab Request 16: HTTP 403 "automated queries"
- IP-basiert — `use_context` (Browser-Rotation) hilft nicht
- Unabhängig von Sprache der Query

#### Google Rate-Tolerance (2026-04-07 + 2026-04-21)

- 30/30 mit 0 Delay in ~2.5min — kein Rate-Limit
- Google scheint bei 12 Req/min (mit realem DOM-Wait-Jitter) kein Blocking zu aktivieren
- Stress-Test Back-to-Back Batch 1 durchgeführt 2026-04-22 → siehe Subsection unten

#### Google Back-to-Back Stress Batch 1 (2026-04-22)

| Run# | OK | Non-OK | First-Fail-Idx | Nav ms mean/max |
|------|-----|--------|----------------|-----------------|
| 1 | 30/30 | — | — | 520 / 887 |
| 2 | 27/30 | 3× CAPTCHA | Q26 | 422 / 701 |
| 3 | 28/30 | 2× CAPTCHA | Q11 | 345 / 664 |
| 4 | 0/30 | 30× CAPTCHA | Q1 | 537 / 661 |

**Threshold:** Hard IP-Block nach ~90 Queries / ~10 Minuten über 4 konsekutive Runs ohne Cooldown.

**Layer-Attribution: IP-Level (Layer 5), NICHT Fingerprint (Layer 1–3).**

Evidenz für IP-Block (nicht Fingerprint-Detection):
- Run 4 Nav-Mean 537ms (stabil, identisch zu Runs 1–3) — Google serviert /sorry/ sofort, kein Fingerprint-Scan
- DOM-Wait 0ms in Run 4 — keine DOM-Verarbeitung, sofortiger Redirect
- /sorry/ startet ab Q1 in Run 4 — kein Query-spezifischer Trigger, vollständiger IP-Block
- Runs 1–3 zeigen normale Nav-Zeiten (345–520ms mean) — Fingerprint-Patches unangetastet

**Referenz:** dev/search_pipeline/01_reports/stress_20260422_012755.md (deleted, see git 1ad627f)

### Recommendation (SOLL)

**Change:** `delay_between_queries: 0 → uniform(12, 18)` in `dev/search_pipeline/config.yml` und analog `src/search/rate_limiter.py` Token-Bucket auf ~4 Req/min.

Begründung:
- Empirisch (Batch 1, 2026-04-22): 12 Req/min bricht nach ~90 kumulativen Queries. Threshold ist nicht instantan-Rate-basiert sondern kumulativer Score pro IP.
- Community-Baseline: `karust/openserp` config (aktive Commits April 2026) defaultet Google auf `rate_requests: 4, rate_burst: 2` — defensiver Floor weit unter jeder plausiblen Schwelle.
- 12–18s ergibt ~4 Req/min mit natürlichem Jitter. Bei Burst-Toleranz (openserp `rate_burst: 2`) können 2 Queries schnell hintereinander, danach Drosselung.
- Für Agentic-Search-Use-Case (4 Queries pro Engine × N Engines → Dedup) passt das: 4 Queries in ~60s pro Engine statt 30 Queries in 2.5min.

**Stress-Test-Protokoll (bleibt):** Für zukünftige Layer-Experimente — Back-to-Back-Runs ohne Cooldown auf ANDEREM IP-Kontext als Library-NAT. Shared-IP-Scraping verzerrt sowohl die Baseline (andere Nutzer beeinflussen Score) als auch ist ethisch zweifelhaft (andere leiden unter unseren CAPTCHAs).

### Offene Fragen

- Google: Wo ist die tatsächliche Rate-Limit-Schwelle? → answered 2026-04-22: ~90 queries / 10min back-to-back (Batch 1 Break)
- Jitter durch DOM-Wait: Reicht die natürliche Varianz (1–15s pro Query) um Regularity-Detection zu umgehen?

---

## Layer 6: TLS/HTTP-Fingerprint

### Status Quo (IST)

#### Baseline Mapping (2026-04-21)

Basis: `dev/search_pipeline/01_google_smoke.py`.

**Chrome TLS ist real — kein Eingriff nötig oder möglich.**

Der Smoke-Stack verwendet pydoll mit echtem Chrome Binary (`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`). Chrome's TLS-Stack ist der echte Browser-Stack — JA3-Hash, HTTP/2 Frame-Order und Header-Order sind identisch mit einem echten Chrome-User.

Kein httpx in dieser Pipeline — keine Requests via Python-HTTP-Client (die einen anderen TLS-Fingerprint erzeugen würden).

#### Detection Surface

Was Layer 6 prüft:

| Signal | Was erkannt wird | Unser Control |
|--------|-----------------|---------------|
| JA3 Hash | TLS Client-Hello Fingerprint | ✅ Chrome TLS ist real |
| HTTP/2 Frame-Order | SETTINGS Frame, WINDOW_UPDATE Frame Reihenfolge | ✅ Chrome HTTP/2 ist real |
| Header-Order | User-Agent, Accept, Accept-Language Reihenfolge | ✅ Chrome Headers sind real |
| ALPN | `h2` negotiation | ✅ Chrome |
| TLS Version | TLS 1.3 | ✅ Chrome |

### Evidenz

TLS-Fingerprint-Tests wurden in Legacy-Scripts durchgeführt (`20_tls_fingerprint.py`, `21_cipher_shuffle_verify.py`) — diese untersuchten den httpx-Stack (SearXNG-Proxy-Ära), nicht den pydoll-Chrome-Stack. Für den aktuellen Chrome-Stack ist kein Test nötig — Chrome ist nicht fälschbar.

### Recommendation (SOLL)

N/A — keine Handlung erforderlich. Chrome-basierte Stacks sind bei Layer 6 inherent unauffällig. Relevant wird Layer 6 nur wenn httpx-basierte Engines (CrossRef, Bing via API-Fallback) problematisch werden.

### Offene Fragen

- Keine — Layer 6 ist für Chrome-basierte Requests gelöst.

---

## Layer 7: CAPTCHA

### Status Quo (IST)

#### Baseline Mapping (2026-04-21)

Basis: `dev/search_pipeline/config.yml` + `dev/search_pipeline/01_google_smoke.py`.

**Detect-only — kein Solving.**

CAPTCHA-Erkennung erfolgt über URL-Check:
- `config.yml`: `captcha_path: /sorry/` — Google's CAPTCHA-Redirect-Pfad
- In `run_query()`: `if gc["captcha_path"] in current_url: record["status"] = "CAPTCHA"; return record`
- Record bekommt Status `CAPTCHA` und wird nicht weiter verarbeitet

Kein JavaScript-basierter Solver. Kein Klick-Versuch. Kein automatisches Retry.

**Baseline-Ergebnis:** 30/30 Run 2026-04-21 ohne einzigen CAPTCHA-Status. Google scheint CAPTCHA (`/sorry/`) erst bei signifikant höherem Traffic zu aktivieren.

#### Detection Surface

Was Layer 7 ist:

| CAPTCHA-Typ | Engine | Mechanismus | Unser Status |
|-------------|--------|-------------|--------------|
| reCAPTCHA (/sorry/) | Google | Rate-basierter Redirect nach Fingerprint-Verdacht | ✅ Erkannt via URL-Check |
| PoW CAPTCHA (Argon2) | Brave | Proof-of-Work Challenge im Browser | ✅ Erkannt — nicht lösbar |
| Slider CAPTCHA | Brave (Patchright) | Drag-Slider Interaktion | ✅ Erkannt — nicht lösbar |
| hCaptcha | Diverse | Challenge-Response | ❌ Kein Selector konfiguriert |

### Evidenz

#### Brave PoW CAPTCHA (2026-04-07)

- Screenshot: "Confirm you're a human being / I'm not a robot" Dialog mit "Learn more about Proof of Work Captcha"
- Svelte-basierter CAPTCHA — PoW (Proof of Work) Challenge, kein Slider
- Tritt ab Query 2–3 auf (Query 1 liefert Results)
- Mit Tor-Proxy: 0/30 (Tor Exit-Nodes auf Blocklist → sofort CAPTCHA)

#### Brave PoW Technische Analyse (2026-04-09)

- Algorithmus: Argon2 (Memory-Hard Hash) via WASM, berechnet in Web Worker
- Challenge-Parameter: `zero_count=1` (trivial), 21 Tokens, `iterations=2`, `memory_size=512KB`
- Privacy Pass: VOPRF-Protokoll (Blind Tokens) in separatem WASM-Modul
- API-Endpoint: POST `/api/captcha/pow?brave=0` mit solutions + blinded_messages
- Server antwortet mit `signed_tokens` → Cookie → Zugang
- Klick auf "I'm not a robot": Spinner "Letting you in..." erscheint, nach 3s keine Weiterleitung — unklar ob Berechnung zu langsam oder Server rejected wegen Fingerprint

**Zwei CAPTCHA-Tiers:**
- `PoW ("I'm not a robot")` — für Chrome/pydoll
- `Slider ("Drag the slider")` — für Patchright/Chromium

#### captcha_detect_js Bug (Legacy)

Im alten Legacy-Stresstest-Stack war ein `captcha_detect_js` JavaScript konfiguriert mit Selektor `dialog .captcha-card`. Dieser Selektor matchte nicht das tatsächliche Brave CAPTCHA-DOM. Korrekt wäre `[class*="pow-captcha"]` oder Title-Check auf "Captcha". Im neuen Smoke-Stack nicht relevant (kein JS-Selektor für CAPTCHA — nur URL-Check).

### Recommendation (SOLL)

Pending — wird durch Stress-Test-Iterationen bestimmt. Google CAPTCHA tritt erst bei hohem Traffic auf — aktuell kein Problem.

**Brave CAPTCHA Optionen (wenn Brave resume):**
1. Klick + länger warten (10–15s) — unklar ob Argon2-Berechnung abschließt
2. Argon2 PoW programmatisch lösen — technisch möglich, Privacy Pass VOPRF-Teil ist der Blocker
3. Brave Search API (2K Queries/Monat gratis) — kein CAPTCHA, aber Architektur-Problem (siehe [Engine-Status](#engine-status))

### Offene Fragen

- Brave: CAPTCHA-Klick mit 10–15s Wartezeit — reicht die Zeit für PoW-Berechnung + API-Call? Oder rejected Server wegen Fingerprint?
- Brave: Ist das CAPTCHA per Session oder per IP lösbar? (Klick-Lösung persistent für die Session?)
- Google: Ab welchem Traffic-Level schaltet `/sorry/` ein? (Stress-Test-Erkenntnis pending)
