"""Abstract base class for paper sources."""

from __future__ import annotations

from abc import ABC, abstractmethod

from journal_api.models import Paper, SearchResult


class Source(ABC):
    """Base class for all paper data sources."""

    name: str = "base"

    @abstractmethod
    async def get_metadata(self, doi: str) -> Paper | None:
        """Fetch metadata for a DOI. Returns None on failure."""
        ...

    async def get_pdf_url(self, doi: str) -> str | None:
        """Return a direct PDF download URL, or None."""
        return None

    async def get_pdf(self, doi: str) -> bytes | None:
        """Download PDF bytes, or None."""
        return None

    async def search(self, query: str, limit: int = 10) -> SearchResult | None:
        """Search for papers. Not all sources support this."""
        return None
