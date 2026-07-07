# Garbage Detection Edge Cases


## Category: consent_prefix

### URL: https://www.azubiyo.de/bewerbung/layout/

- Raw content: 33776 chars
- First 300 chars: `Willkommen bei Azubiyo.de Auf Azubiyo.de und anderen Webseiten der FUNKE Works GmbH verwenden wir Cookies und vergleichbare Technologien („Tracking-Technologien”), um die Nutzung unserer Website zu analysieren, deine User-Experience zu verbessern, auf deine Interessen zugeschnittene Inhalte und Werb`
- Filtered content: 23962 chars
- First 300 chars: `Willkommen bei Azubiyo.de Auf Azubiyo.de und anderen Webseiten der FUNKE Works GmbH verwenden wir Cookies und vergleichbare Technologien („Tracking-Technologien”), um die Nutzung unserer Website zu analysieren, deine User-Experience zu verbessern, auf deine Interessen zugeschnittene Inhalte und Werb`
- is_garbage(raw): None
- is_garbage(filtered): None
- Assessment: garbage missed — consent prefix not detected

## Category: consent_prefix

### URL: https://www.stepstone.de/magazin/bewerbung/

- Raw content: 12267 chars
- First 300 chars: `[](https://www.stepstone.de/de) Suche [Login](https://www.stepstone.de/de-DE/candidate/register?login_source=Other_top-register&intcid=Button_Other-navigation_register) Menu * * * Genug gesucht? Lass uns schneller passende Jobs für dich findenJetzt starten * * * Jobs finden [ ](https://www.stepstone`
- Filtered content: 8252 chars
- First 300 chars: `Suche Genug gesucht? Lass uns schneller passende Jobs für dich findenJetzt starten Jobs finden [ Alle Artikel ](https://www.stepstone.de/magazin/) [ Ausbildung ](https://www.stepstone.de/magazin/kategorien/ausbildung) [ Arbeitsrecht ](https://www.stepstone.de/magazin/kategorien/arbeitsrecht) [ Arbei`
- is_garbage(raw): None
- is_garbage(filtered): None
- Assessment: garbage missed — consent prefix not detected

## Category: padded_404

### URL: https://medium.com/nonexistent-article-xyz-12345

- Raw content: 7189 chars
- First 300 chars: `[Sitemap](https://medium.com/sitemap/sitemap.xml) [Open in app](https://play.google.com/store/apps/details?id=com.medium.reader&referrer=utm_source%3DmobileNavBar&source=---not_found_layout_nav-----------------------------------------) Sign up [Sign in](https://medium.com/m/signin?operation=login&re`
- Filtered content: 3209 chars
- First 300 chars: `[Sitemap](https://medium.com/sitemap/sitemap.xml) [Open in app](https://play.google.com/store/apps/details?id=com.medium.reader&referrer=utm_source%3DmobileNavBar&source=---not_found_layout_nav-----------------------------------------) Sign up Get app Sign up PAGE NOT FOUND ## 404 ## Out of nothing,`
- is_garbage(raw): None
- is_garbage(filtered): None
- is_garbage(first_500_chars): http_error  ← header-zone test
- Assessment: garbage missed — padded 404 not detected

## Category: padded_404

### URL: https://dev.to/nonexistent-user-xyz/nonexistent-post-12345

- Raw content: 555 chars
- First 300 chars: `404 / page not found # Looks like this page doesn't exist or may not be published. We searched the feed, checked the tags, even refreshed the cache. This page is still missing. If you were aiming for some sweet community content, you might be one URL away.  **$** find /pages/your-requested-page   **`
- Filtered content: 551 chars
- First 300 chars: `404 / page not found # Looks like this page doesn't exist or may not be published. We searched the feed, checked the tags, even refreshed the cache. This page is still missing. If you were aiming for some sweet community content, you might be one URL away.  **$** find /pages/your-requested-page **→*`
- is_garbage(raw): http_error
- is_garbage(filtered): http_error
- is_garbage(first_500_chars): http_error  ← header-zone test
- Assessment: correctly detected — http_error

## Category: baseline_good

### URL: https://en.wikipedia.org/wiki/Python_(programming_language)

- Raw content: 282359 chars
- First 300 chars: `[Jump to content](https://en.wikipedia.org/wiki/Python_\(programming_language\)#bodyContent) Main menu Main menu move to sidebar hide Navigation    * [Main page](https://en.wikipedia.org/wiki/Main_Page "Visit the main page \[ctrl-option-z\]")   * [Contents](https://en.wikipedia.org/wiki/Wikipedia:Co`
- Filtered content: 180191 chars
- First 300 chars: `[Jump to content](https://en.wikipedia.org/wiki/Python_\(programming_language\)#bodyContent) From Wikipedia, the free encyclopedia General-purpose programming language This article **may contain[unverified](https://en.wikipedia.org/wiki/Wikipedia:Verifiability "Wikipedia:Verifiability") or [indiscri`
- is_garbage(raw): None
- is_garbage(filtered): None
- Assessment: correctly detected (no garbage)

## Category: baseline_good

### URL: https://docs.python.org/3/tutorial/

- Raw content: 21548 chars
- First 300 chars: `[ ![Python logo](https://docs.python.org/3/_static/py.svg) ](https://www.python.org/) dev (3.15) 3.14.3 3.13 3.12 3.11 3.10 3.9 3.8 3.7 3.6 3.5 3.4 3.3 3.2 3.1 3.0 2.7 2.6 Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Braz`
- Filtered content: 18810 chars
- First 300 chars: `### Navigation   * Greek | Ελληνικά English Spanish | español French | français Italian | italiano Japanese | 日本語 Korean | 한국어 Polish | polski Brazilian Portuguese | Português brasileiro Romanian | Românește Turkish | Türkçe Simplified Chinese | 简体中文 Traditional Chinese | 繁體中文 dev (3.15) 3.14.3 3.13`
- is_garbage(raw): None
- is_garbage(filtered): None
- Assessment: correctly detected (no garbage)