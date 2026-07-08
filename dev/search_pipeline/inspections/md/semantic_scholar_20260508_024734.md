# Engine DOM Inspection — semantic_scholar — 20260508_024734

**Query:** `RLHF reinforcement learning human feedback`  **Wait:** 3.0s  **URL:** `https://www.semanticscholar.org/search?q=RLHF+reinforcement+learning+human+feedback`

## H1 — Current Selector Status

| Role | Selector | Count | Status |
|------|----------|-------|--------|
| container | `div.cl-paper-row` | 0 | ❌ BROKEN |
| title | `[data-test-id="title-link"]` | 0 | ❌ BROKEN |
| snippet | `[data-test-id="paper-abstract-toggle"]` | 0 | ❌ BROKEN |
| error | `[data-test-id="error-message-block"]` | 1 | ✅ PRESENT |

## H2 — data-test-id Inventory (semantic keywords filtered)

| data-test-id | Count |
|-------------|-------|
| `footer-feedback-link` | 1 |
| `footer-ai2-link` | 1 |
| `footer-collab-link` | 1 |
| `footer-tos-link` | 1 |
| `footer-privacy-link` | 1 |
| `footer-api-license-link` | 1 |
*Total distinct data-test-id values on page: 10*

## H3 — Repeating Class Clusters (≥4 occurrences, top 20)

| First class | Count |
|-------------|-------|
| `about-us__link-list` | 5 |
| `go2417249464` | 4 |

## H4 — Class-Substring Matches (top 15)

| Keyword:First-class | Count |
|---------------------|-------|
| `item:osano-cm-list__list-item` | 3 |
| `row:flex-row-vcenter` | 3 |
| `row:container` | 2 |
| `row:footer__row` | 2 |
| `row:header-right` | 1 |

## H5 — data-* Attribute Inventory (count ≥ 3)

| Attribute | Count |
|-----------|-------|
| *(none)* | — |

## H6 — HTML Snippet (top H3 cluster element)

```html
<div class="about-us__link-list"><h3>About</h3><a href="/about" class="flex-row about-link" aria-label="About Us">About Us</a><a href="/about/publishers" class="flex-row about-link" aria-label="Publishers">Publishers</a><a href="https://allenai.org/blog" target="_blank" rel="noopener " class="flex-row about-link" aria-label="Blog">Blog<span class="screen-reader-only"> (opens in a new tab)</span></a><a href="https://allenai.org/careers?team=semantic+scholar#current-openings" target="_blank" rel="noopener " class="flex-row about-link" aria-label="Ai2 Careers">Ai2 Careers<span class="screen-reader-only"> (opens in a new tab)</span></a></div>
```

## H7 — External Link Count

External links (excl. `semanticscholar.org`): **10**  
Results rendered: **YES**

---

## Diagnosis

**Status:** BROKEN

Container `div.cl-paper-row` matches 0. Recommended: `div.about-us__link-list` (count=5) — from H3