# Garbage Detection Fix Prototypes

## Fix 1: status_code based 404 detection

| URL | status_code | Would trigger http_error? | Correct? |
|-----|-------------|---------------------------|----------|
| medium.com/nonexistent-article-xyz-12345 | 404 | YES | YES ✅ |
| dev.to/nonexistent-user-xyz/nonexistent-post-12345 | 404 | YES | YES ✅ |
| en.wikipedia.org/wiki/Python_(programming_language) | 200 | NO | YES ✅ |
| www.azubiyo.de/bewerbung/layout/ | 200 | NO | YES ✅ |

## Fix 2: consent prefix stripping

### azubiyo.de/bewerbung/layout/

- Original first 200 chars: `Willkommen bei Azubiyo.de Auf Azubiyo.de und anderen Webseiten der FUNKE Works GmbH verwenden wir Cookies und vergleichbare Technologien („Tracking-Technologien”), um die Nutzung unserer Website zu an`
- Stripped first 200 chars: `#  Layout der Bewerbung  ![Mann mit Katze gestaltet sein Layout der Bewerbung am Laptop](https://www.azubiyo.de/bilder/umb/bi/lcigefz90upg2ejqfgwh2k56ft0y/layout-bewerbung.jpg?m=0&si=1&fd=1&fto=0.2&w=`
- Chars removed: 8437
- Content starts at heading: `#  Layout der Bewerbung `
- Assessment: effective — removed 8437 chars ✅

### stepstone.de/magazin/bewerbung/

- Original first 200 chars: `[](https://www.stepstone.de/de) Suche [Login](https://www.stepstone.de/de-DE/candidate/register?login_source=Other_top-register&intcid=Button_Other-navigation_register) Menu * * * Genug gesucht? Lass `
- Stripped first 200 chars: `[](https://www.stepstone.de/de) Suche [Login](https://www.stepstone.de/de-DE/candidate/register?login_source=Other_top-register&intcid=Button_Other-navigation_register) Menu * * * Genug gesucht? Lass `
- Chars removed: 0
- Content starts at heading: `(no heading found at start)`
- Assessment: not effective — nothing removed ❌

### en.wikipedia.org/wiki/Python_(programming_language

- Original first 200 chars: `[Jump to content](https://en.wikipedia.org/wiki/Python_\(programming_language\)#bodyContent) Main menu Main menu move to sidebar hide Navigation    * [Main page](https://en.wikipedia.org/wiki/Main_Pag`
- Stripped first 200 chars: `[Jump to content](https://en.wikipedia.org/wiki/Python_\(programming_language\)#bodyContent) Main menu Main menu move to sidebar hide Navigation    * [Main page](https://en.wikipedia.org/wiki/Main_Pag`
- Chars removed: 0
- Content starts at heading: `(no heading found at start)`
- Assessment: nothing removed ✅

### docs.python.org/3/tutorial/

- Original first 200 chars: `[ ![Python logo](https://docs.python.org/3/_static/py.svg) ](https://www.python.org/) dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6 Greek | Ελληνικά English Spa`
- Stripped first 200 chars: `[ ![Python logo](https://docs.python.org/3/_static/py.svg) ](https://www.python.org/) dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6 Greek | Ελληνικά English Spa`
- Chars removed: 0
- Content starts at heading: `(no heading found at start)`
- Assessment: nothing removed ✅


## Recommendation

**Fix 1 (status_code >= 400): Production-ready.** Check `result.status_code` before content analysis in `try_scrape()`. If >= 400, return `("" , "http_error")` immediately — eliminates content-length dependency and catches padded error pages regardless of body size.

**Fix 2 (consent prefix strip): Prototype shows promise for azubiyo-style sites.** Requires integration into `try_scrape()` as a post-processing step before `is_garbage_content()`. Stepstone is a nav-dump, not a consent-prefix — different problem. Not yet production-ready: threshold and heading-search need broader site testing.