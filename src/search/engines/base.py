# INFRASTRUCTURE
from abc import ABC, abstractmethod

from src.search.result import SearchResult


# Abstract base class for all search engine implementations
class BaseEngine(ABC):
    name: str

    @abstractmethod
    async def search(self, query: str, language: str = "en", max_results: int = 10) -> list[SearchResult]:
        ...

    # Default: delegates to search(); Stage 2 engines override to return sub-status empty_reason
    async def search_with_reason(self, query: str, language: str = "en", max_results: int = 10) -> tuple[list[SearchResult], str | None]:
        results = await self.search(query, language, max_results)
        return results, None
