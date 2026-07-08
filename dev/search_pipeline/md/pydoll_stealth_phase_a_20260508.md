# Phase A: pydoll Stealth Investigation — 2026-05-08

Probe: `dev/search_pipeline/pydoll_fingerprint_probe.py`
Branch: `pydoll-stealth-probe`

---

## 1. pydoll Stealth Inventory

### pydoll v2.22.0 native stealth — what's there

| Component | File | What it does |
|---|---|---|
| UA override via CDP | `browser/chromium/base.py:769-790` | When `--user-agent=` arg set: calls `Emulation.setUserAgentOverride` (HTTP headers + Client Hints) + `Page.addScriptToEvaluateOnNewDocument` to patch `navigator.vendor` + `navigator.appVersion` |
| WebRTC flag | `browser/options.py` | `--force-webrtc-ip-handling-policy=disable_non_proxied_udp` via `webrtc_leak_protection` property |
| Default args | `browser/managers/browser_options_manager.py:52` | Only `--no-first-run`, `--no-default-browser-check` |

**pydoll has NO native stealth mode.** There is no `--disable-blink-features=AutomationControlled`, no `navigator.webdriver` patch, no fingerprint injection. All stealth work is manual add-on.

### What our `src/search/browser.py` adds on top

| Patch | Implementation | Effect |
|---|---|---|
| `--disable-blink-features=AutomationControlled` | `browser.py:76` | Sets `navigator.webdriver = false` (undefined in modern Chrome) |
| Real User-Agent | `browser.py:17-21, 80` | Removes `HeadlessChrome` signal from UA string |
| CDP `Emulation.setUserAgentOverride` | Triggered by `--user-agent=` arg; pydoll handles internally | Syncs HTTP headers + Client Hints |
| Screen/window JS patches | `browser.py:24-57` | Patches `screen.width/height`, `devicePixelRatio`, `outerWidth/Height`, CSS ActiveText color |
| Session persistence | `browser.py:71` | `--user-data-dir=~/.searxng-mcp/browser-session` — real persistent profile |
| `apply_fingerprint_patches()` | `browser.py:101-107` | `Page.addScriptToEvaluateOnNewDocument` with JS above, applied to every new tab |
| WebRTC protection | `browser.py:77` | Via pydoll `webrtc_leak_protection` setter |

### What is NOT patched (gaps)

| Gap | Risk | Notes |
|---|---|---|
| `Runtime.enable` CDP leak | **HIGH** for enterprise bot detection | pydoll uses `Runtime.enable` CDP domain for all JS execution. Pages can detect CDP is active via timing attacks on isolated contexts. Patchright patches this. |
| TLS/JA3 fingerprint | LOW | pydoll uses Chrome's native TLS stack (via subprocess), not a custom implementation. JA3 should be Chrome-normal. |
| Canvas noise injection | LOW | Not patched, but our real GPU (Apple M4 Pro ANGLE Metal) produces a natural-looking canvas hash (-1941328102), not SwiftShader. |
| Audio context fingerprint | LOW | Not patched. Low-priority target for most bot detection. |
| `navigator.plugins` names | NEGLIGIBLE | Count is 5 (real), but plugin names serialize as empty objects in JSON. Not a common detection point. |
| Concurrent tab count | **HIGH** (behavioral) | 9 tabs opened simultaneously via `asyncio.gather` is a strong behavioral bot signal regardless of fingerprint quality. NOT a fingerprint issue — see section 4. |

---

## 2. Probe Results — bot.sannysoft.com

Script: `dev/search_pipeline/pydoll_fingerprint_probe.py`
Run: `./venv/bin/python dev/search_pipeline/pydoll_fingerprint_probe.py`
Screenshot: `/tmp/pydoll_probe_sannysoft.png`

### Summary

bot.sannysoft.com runs 57 detection checks. CSS class-based pass/fail detection (`row.classList.contains('passed')`) returned UNKNOWN for all rows (page uses inline styles, not classes). However, the **value** of each check is the authoritative signal.

**All 57 checks show passing values.**

### Key check values

| Check | Value | Verdict |
|---|---|---|
| WebDriver (New) | missing (passed) | ✅ |
| WebDriver Advanced | passed | ✅ |
| Chrome (New) | present (passed) | ✅ |
| Permissions (New) | prompt | ✅ |
| Plugins Length (Old) | 5 | ✅ |
| Plugins is PluginArray | passed | ✅ |
| Languages (Old) | de-DE,de,en-US,en | ✅ |
| WebGL Vendor | Google Inc. (Apple) | ✅ |
| WebGL Renderer | ANGLE (Apple, ANGLE Metal Renderer: Apple M4 Pro, Unspecified Version) | ✅ real GPU |
| Broken Image Dimensions | 16x16 | ✅ |
| HEADCHR_UA | ok | ✅ |
| HEADCHR_CHROME_OBJ | ok | ✅ |
| HEADCHR_PERMISSIONS | ok | ✅ |
| HEADCHR_PLUGINS | ok | ✅ |
| HEADCHR_IFRAME | ok | ✅ |
| CHR_DEBUG_TOOLS | ok | ✅ |
| SELENIUM_DRIVER | ok | ✅ |
| CHR_BATTERY | ok | ✅ (Charging: false, Level: 0.74) |
| CHR_MEMORY | ok | ✅ |
| PHANTOM_* (8 checks) | ok | ✅ |
| Canvas1-5 | Hash: -1941328102 (consistent, real GPU) | ✅ |

### Direct navigator reads (from probe JS)

```
navigator.webdriver       = false          ✅ NOT true
navigator.plugins_length  = 5              ✅ NOT 0
navigator.languages       = ["de-DE","de","en-US","en"]  ✅ multiple
navigator.hardwareConcurrency = 14         ✅ real CPU count (M4 Pro)
navigator.deviceMemory    = 32             ✅ real RAM
navigator.vendor          = "Google Inc."  ✅
navigator.platform        = "MacIntel"     ✅
webgl_vendor              = "Google Inc. (Apple)"
webgl_renderer            = "ANGLE (Apple, ANGLE Metal Renderer: Apple M4 Pro, Unspecified Version)"  ✅ NOT SwiftShader
permissions.notifications = "prompt"       ✅ NOT "denied"
```

### Interpretation

Our fingerprint is **clean for all JS-visible detection checks.** The fingerprint is NOT what's causing Scholar concurrent blocks. Evidence:
1. All sannysoft checks pass
2. Both isolated-mode and concurrent-mode use the same pydoll fingerprint — the fingerprint can't explain the concurrent-vs-isolated difference
3. The probe ran on the same Chrome session + options that production uses

The unpatched `Runtime.enable` CDP leak is invisible to JS-based tests (it operates at CDP protocol level). It would affect both isolated and concurrent modes equally.

---

## 3. Alternatives Ranking

### Library comparison table

| Library | License | Installed | Version | API model | Runtime.enable patch | `navigator.webdriver` patch | Concurrent tab support | Migration cost |
|---|---|---|---|---|---|---|---|---|
| **pydoll** (current) | MIT | ✅ | 2.22.0 | CDP direct | ❌ leaks | ✅ (via our `--disable-blink-features`) | ✅ (asyncio tab pool) | — |
| **patchright** | Apache-2.0 | ✅ | 1.58.2 | Playwright | ✅ patched | ✅ | ✅ | MEDIUM |
| **nodriver** | **AGPL-3.0** | ❌ | 0.48.1 | CDP direct | ❌ leaks | ✅ (no Selenium → no `--enable-automation`) | ✅ | MEDIUM |
| botasaurus | Apache-2.0 | ❌ | — | Framework | ❌ (varies) | ✅ | ✅ (but heavier) | HIGH |
| playwright-stealth | MIT | ❌ | — | JS injection | ❌ | ✅ (JS injection only) | ✅ | MEDIUM |

### Per-library notes

**nodriver 0.48.1 (AGPL-3.0) — RULED OUT**
License is AGPL-3.0. Any project using nodriver must be open-sourced under AGPL. This is a hard blocker unless the repo is published under AGPL terms. Stealth is also minimal: nodriver only removes "Headless" from UA and uses Chrome directly (no `--enable-automation`), but doesn't patch Runtime.enable and doesn't fix `--disable-blink-features`. Its "undetected" claim comes from not using ChromeDriver, which we already avoid with pydoll.

**patchright 1.58.2 (Apache-2.0) — LEADING CANDIDATE**
Already installed as a transitive dependency of Crawl4AI. No new dependency. Key advantages over pydoll:
- Patches `Runtime.enable` leak (isolated ExecutionContexts for all JS evaluation)
- Removes `--enable-automation` flag
- Adds `--disable-blink-features=AutomationControlled`
- Removes several Playwright default args that are bot signals
- Passes: Cloudflare, Datadome, Kasada, Akamai, Fingerprint.com, CreepJS, Sannysoft, Incolumitas, BrowserScan, Pixelscan (per readme, verified against published test results)
- Persistent context API: `playwright.chromium.launch_persistent_context(user_data_dir, channel="chrome")` — uses system Chrome binary (same as we do now)
- Drop-in replacement for Playwright — same API surface as base playwright

Caveat: patchright uses its own patched Chromium driver OR can use system Chrome via `channel="chrome"`. Using system Chrome (`channel="chrome"`) avoids downloading additional binaries and gives us the real Chrome fingerprint (matching actual installed version).

**botasaurus — not recommended**
Heavy framework with many abstractions. Not a drop-in replacement. Would require significant rewrites across pipeline. Overkill for our case.

**playwright-stealth — not recommended**
JS-injection only approach. Does NOT patch Runtime.enable. Strictly dominated by patchright for our use case.

### Verdict

Leading candidate: **patchright** (already installed, Apache-2.0, patches Runtime.enable)
Backup: none needed — nodriver is AGPL-blocked, others are strictly worse

---

## 4. Migration Sizing

### Files that import pydoll directly

```
src/search/browser.py:8     from pydoll.browser import Chrome
src/search/browser.py:9     from pydoll.browser.options import ChromiumOptions
src/search/browser.py:10    from pydoll.commands import PageCommands
src/search/engines/google.py:7   from pydoll.commands.network_commands import NetworkCommands
src/search/engines/google.py:8   from pydoll.protocol.network.types import CookieSameSite
src/search/search_web.py:10      import pydoll.exceptions as _pydoll_exc
```

### Migration scope and effort

| File | LOC | Change scope | Notes |
|---|---|---|---|
| `src/search/browser.py` | 146 | Full rewrite | `Chrome()` + options → `async_playwright()` + `launch_persistent_context()`; `apply_fingerprint_patches()` → `add_init_script()`; `new_tab()` → `new_page()` on persistent context |
| `src/search/search_web.py` | 394 | Minor | Exception class rename (`pydoll.exceptions` → patchright exceptions), tab lifecycle (close tab after use — patchright pages don't persist open by default) |
| `src/search/engines/google.py` | 213 | Moderate | `_extract_value(result["result"]["result"]["value"])` disappears — patchright `page.evaluate()` returns value directly; `NetworkCommands.set_cookie()` → `context.add_cookies()`; `tab.go_to()` → `page.goto()`; `tab.execute_script()` → `page.evaluate()` |
| `src/search/engines/scholar.py` | 160 | Moderate | Same as google.py |
| `src/search/engines/duckduckgo.py` | 162 | Moderate | Same pattern |
| `src/search/engines/mojeek.py` | 134 | Moderate | Same pattern |
| `src/search/engines/lobsters.py` | 133 | Moderate | Same pattern |
| `src/search/engines/semantic_scholar.py` | 170 | Moderate | Same pattern |

**Total affected LOC: ~1100** across 8 files.

**API translation summary (pydoll → patchright):**

```
# Browser lifecycle
Chrome(options) + browser.start()
→ async_playwright() as p; p.chromium.launch_persistent_context(user_data_dir, channel="chrome")

# New tab
await browser.new_tab()
→ await context.new_page()   # page auto-closed on context exit

# Navigate
await tab.go_to(url)
→ await page.goto(url)

# Execute JS (with return value)
raw = await tab.execute_script(js)
value = raw["result"]["result"]["value"]
→ value = await page.evaluate(js)   # returns directly

# addScriptToEvaluateOnNewDocument
await tab._execute_command(PageCommands.add_script_to_evaluate_on_new_document(source))
→ await context.add_init_script(script=source)   # applied to ALL new pages in context

# Screenshot
await tab.take_screenshot(path)
→ await page.screenshot(path=path)

# Cookie injection (google.py)
await tab._execute_command(NetworkCommands.set_cookie(...))
→ await context.add_cookies([{"name": ..., "domain": ..., ...}])
```

Net LOC change: slightly negative (the `_extract_value()` helper + nested result dict boilerplate in every engine disappears).

**Migration risk:** LOW-MEDIUM. The API translation is mechanical. The persistent context model in patchright (all pages share one context, one browser instance) maps directly onto our existing shared-Chrome-singleton architecture. The main risk is patchright's patched Chromium driver needing `patchright install chromium` — using `channel="chrome"` avoids this and uses our installed Google Chrome.

Estimated implementation time: **4-6 hours** for a clean migration + smoke test.

---

## 5. Recommendation for Next Session

### Core finding

**The Scholar concurrent CAPTCHA is NOT caused by fingerprint quality.** Our fingerprint is clean (all bot.sannysoft.com checks pass). The concurrent-vs-isolated difference is behavioral: 9 tabs opened simultaneously via `asyncio.gather` creates a burst pattern that reCAPTCHA Enterprise v3 scores as bot behavior. The Runtime.enable CDP leak would affect both modes equally (isolation and concurrent), so it can't explain the difference.

### Two separate problems, two separate fixes

**Problem 1 (CIW bead — immediate priority):** Scholar CAPTCHA in concurrent mode.
**Fix:** Serialize Scholar — remove it from `asyncio.gather`, run it after all other engines with a 1-2s preamble delay. Implementation: ~30 lines in `search_web.py`. Risk: near-zero. This directly mirrors the isolation result (which worked in all tests).

**Problem 2 (medium-term — patchright migration):** Runtime.enable CDP leak exposes us to reCAPTCHA Enterprise v3 and Cloudflare detection on any engine that uses sophisticated bot detection.
**Fix:** Migrate `browser.py` (and engines) to patchright. This also consolidates our CDP library — patchright is already installed, and our scraper stack (Crawl4AI) already uses it. Running pydoll + patchright simultaneously in the same process is wasteful; unifying on patchright is architecturally cleaner.

### Recommendation

1. **Next session immediate:** Implement Scholar serialization (CIW fix). Low risk, directly validated by empirical data.
2. **Follow-up session:** Patchright migration. patchright is the leading candidate — already installed, Apache-2.0, patches Runtime.enable, passes all major enterprise bot detection. Do NOT migrate to nodriver (AGPL-3.0).
3. **If Scholar is still blocked after serialization:** The remaining cause is IP reputation / reCAPTCHA v3 behavioral scoring that we can't solve with fingerprint patches alone. In that case, the choices are: residential proxy (paid), drop Scholar from the active engine set, or accept Scholar as unreliable and handle gracefully.

---

## Completion Checklist

- [x] pydoll stealth inventory: `browser/managers/browser_options_manager.py:52` (default args), `browser/chromium/base.py:769-790` (UA override only with our `--user-agent=` arg), `src/search/browser.py:76` (`--disable-blink-features`), `browser.py:24-57` (screen patches)
- [x] Probe script committed: `dev/search_pipeline/pydoll_fingerprint_probe.py`
- [x] Probe results: all 57 sannysoft checks pass; `navigator.webdriver=false`, 5 plugins, real GPU (ANGLE Metal M4 Pro), permissions=prompt, canvas=-1941328102; screenshot `/tmp/pydoll_probe_sannysoft.png`
- [x] Alternatives table with verdict: patchright (leading, Apache-2.0, already installed); nodriver RULED OUT (AGPL-3.0)
- [x] Migration sizing: 8 files, ~1100 LOC, 4-6h estimate; API translation table above
- [x] Recommendation: (1) Scholar serialization for CIW fix, (2) patchright migration for Runtime.enable patch
