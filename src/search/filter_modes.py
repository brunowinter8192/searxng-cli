# INFRASTRUCTURE
import logging
from collections.abc import Callable

# From book_whitelist.py: domain + path inclusion check for --books mode
from src.search.book_whitelist import is_book_url
# From pdf_filter.py: host + path inclusion check for --pdf mode
from src.search.pdf_filter import is_pdf_url
# From docs_filter.py: noise blacklist check for --docs mode
from src.search.docs_filter import is_docs_url

logger = logging.getLogger(__name__)

# Default engine set — all engines except google_scholar; Scholar excluded because Google co-fire
# (scholar.google.com + google.com from same IP → EMPTY_BLOCK even with HTTP Scholar).
# Scholar dormant until Pooling-Rework (bead searxng-g82) assigns it a Google-free pool.
# See decisions/OldThemes/scholar_decoupling/20260509.md for rationale.
_DEFAULT_ENGINES: frozenset[str] = frozenset({
    "google", "crossref", "duckduckgo", "mojeek", "lobsters",
    "openalex", "stack_exchange", "semantic_scholar", "open_library",
})

# --books mode: restrict to general-web engines + Open Library catalog, append '+book' modifier to web engines
_BOOKS_ENGINES: frozenset[str] = frozenset({"google", "duckduckgo", "mojeek", "open_library"})
_BOOKS_MODIFIER: Callable[[str], str] = lambda q: f"{q} book"

# --pdf mode: restrict to PDF-rich engines and append ' pdf' modifier; post-filter via is_pdf_url
# Engine selection rationale (free_word_injection_probe_20260507_033631.md):
#   google/ddg/mojeek → surface direct .pdf file URLs
#   Scholar dropped 2026-05-09 (Google co-fire constraint — see scholar_decoupling/20260509.md)
#   crossref/openalex dropped: return doi.org-only results, 0 yield after is_pdf_url filter
_PDF_ENGINES: frozenset[str] = frozenset({"google", "duckduckgo", "mojeek"})
_PDF_MODIFIER: Callable[[str], str] = lambda q: f"{q} pdf"

# --docs mode: restrict to general-web engines, append 'documentation' modifier, post-filter via is_docs_url
# Pure blacklist: blocks known noise (forums, blogs, code-hosting, tutorial sites), passes everything else
_DOCS_ENGINES: frozenset[str] = frozenset({"google", "duckduckgo", "mojeek"})
_DOCS_MODIFIER: Callable[[str], str] = lambda q: f"{q} documentation"


# FUNCTIONS

# Resolve 3-way mutex, restrict engine dict, set effective modifier map; return (selected, qmm, mode_id, excluded)
# excluded: engine.name → reason string for engines dropped by the active filter mode
def apply_filter_mode(
    selected: dict,
    books: bool,
    pdf: bool,
    docs: bool,
    query_modifier_map: dict[str, Callable] | None,
) -> tuple[dict, dict[str, Callable] | None, str | None, dict[str, str]]:
    if sum([books, pdf, docs]) > 1:
        if pdf:
            logger.warning("Multiple mode flags set — pdf takes precedence; ignoring books/docs")
            books = False
            docs = False
        elif docs:
            logger.warning("Multiple mode flags set — docs takes precedence; ignoring books")
            books = False
    if books:
        excluded = {v.name: "not_in_books_engine_set" for k, v in selected.items() if k not in _BOOKS_ENGINES}
        selected = {k: v for k, v in selected.items() if k in _BOOKS_ENGINES}
        query_modifier_map = {name: _BOOKS_MODIFIER for name in _BOOKS_ENGINES if name != "open_library"}
        return selected, query_modifier_map, "books", excluded
    if pdf:
        excluded = {v.name: "not_in_pdf_engine_set" for k, v in selected.items() if k not in _PDF_ENGINES}
        selected = {k: v for k, v in selected.items() if k in _PDF_ENGINES}
        query_modifier_map = {name: _PDF_MODIFIER for name in _PDF_ENGINES}
        return selected, query_modifier_map, "pdf", excluded
    if docs:
        excluded = {v.name: "not_in_docs_engine_set" for k, v in selected.items() if k not in _DOCS_ENGINES}
        selected = {k: v for k, v in selected.items() if k in _DOCS_ENGINES}
        query_modifier_map = {name: _DOCS_MODIFIER for name in _DOCS_ENGINES}
        return selected, query_modifier_map, "docs", excluded
    return selected, query_modifier_map, None, {}


# Apply mode-specific URL filter to ranked results post-merge; returns list unchanged when mode is None
def filter_urls_by_mode(ranked: list, mode: str | None) -> list:
    if mode == "books":
        return [r for r in ranked if is_book_url(r.url)]
    if mode == "pdf":
        return [r for r in ranked if is_pdf_url(r.url)]
    if mode == "docs":
        return [r for r in ranked if is_docs_url(r.url)]
    return ranked
