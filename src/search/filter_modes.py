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

# Default engine set — all 9 active engines. Scholar fully removed (not just dormant) until
# Pooling-Rework assigns it a Google-free pool. See decisions/OldThemes/bee_cdp_starvation/fix_summary.md.
_DEFAULT_ENGINES: frozenset[str] = frozenset({
    "google", "crossref", "duckduckgo", "mojeek", "lobsters",
    "openalex", "stack_exchange", "semantic_scholar", "open_library",
})

# --books mode: engines that receive the '+book' query modifier (web engines only; open_library excluded — already a catalog)
_BOOKS_ENGINES: frozenset[str] = frozenset({"google", "duckduckgo", "mojeek", "open_library"})
_BOOKS_MODIFIER: Callable[[str], str] = lambda q: f"{q} book"

# --pdf mode: engines that receive the '+pdf' query modifier; post-filter via is_pdf_url
# google/ddg/mojeek surface direct .pdf URLs; crossref/openalex return doi.org-only (0 yield post-filter)
_PDF_ENGINES: frozenset[str] = frozenset({"google", "duckduckgo", "mojeek"})
_PDF_MODIFIER: Callable[[str], str] = lambda q: f"{q} pdf"

# --docs mode: engines that receive the '+documentation' query modifier; post-filter via is_docs_url
# Pure blacklist: blocks known noise (forums, blogs, code-hosting, tutorial sites), passes everything else
_DOCS_ENGINES: frozenset[str] = frozenset({"google", "duckduckgo", "mojeek"})
_DOCS_MODIFIER: Callable[[str], str] = lambda q: f"{q} documentation"


# FUNCTIONS

# Resolve 3-way mutex, set per-engine modifier map; return (selected, qmm, mode_id, excluded)
# Bucket-uniformity invariant: selected dict passes through unchanged — all engines fire on every query.
# Modifier applied only to mode-relevant engines; others receive bare query. excluded always {}.
def apply_filter_mode(
    selected: dict,
    books: bool,
    pdf: bool,
    docs: bool,
    query_modifier_map: dict[str, Callable] | None,
) -> tuple[dict, dict[str, Callable] | None, str | None, dict[str, str]]:
    if sum([books, pdf, docs]) > 1:
        if pdf:
            logger.info("Multiple mode flags set — pdf takes precedence; ignoring books/docs")
            books = False
            docs = False
        elif docs:
            logger.info("Multiple mode flags set — docs takes precedence; ignoring books")
            books = False
    if books:
        query_modifier_map = {name: _BOOKS_MODIFIER for name in _BOOKS_ENGINES if name != "open_library"}
        return selected, query_modifier_map, "books", {}
    if pdf:
        query_modifier_map = {name: _PDF_MODIFIER for name in _PDF_ENGINES}
        return selected, query_modifier_map, "pdf", {}
    if docs:
        query_modifier_map = {name: _DOCS_MODIFIER for name in _DOCS_ENGINES}
        return selected, query_modifier_map, "docs", {}
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
