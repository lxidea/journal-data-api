"""OpenAlex API — metadata fallback source."""

from __future__ import annotations

import logging

from journal_api.config import get_settings
from journal_api.http_client import fetch
from journal_api.models import Author, Paper, SearchResult
from journal_api.sources.base import Source

logger = logging.getLogger(__name__)

_BASE = "https://api.openalex.org"


class OpenAlexSource(Source):
    name = "openalex"

    async def get_metadata(self, doi: str) -> Paper | None:
        try:
            settings = get_settings()
            params: dict = {}
            if settings.openalex_api_key:
                params["api_key"] = settings.openalex_api_key

            resp = await fetch(
                f"{_BASE}/works/https://doi.org/{doi}",
                source=self.name,
                params=params,
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            return self._parse(doi, data)
        except Exception:
            logger.exception("OpenAlex error for %s", doi)
            return None

    async def search(self, query: str, limit: int = 10) -> SearchResult | None:
        try:
            settings = get_settings()
            params: dict = {
                "search": query,
                "per_page": limit,
            }
            if settings.openalex_api_key:
                params["api_key"] = settings.openalex_api_key

            resp = await fetch(
                f"{_BASE}/works",
                source=self.name,
                params=params,
            )
            if resp.status_code != 200:
                return None

            results = resp.json().get("results", [])
            total = resp.json().get("meta", {}).get("count", 0)
            papers = []
            for item in results:
                doi = item.get("doi", "")
                if doi:
                    # OpenAlex returns full URL as DOI
                    doi = doi.replace("https://doi.org/", "")
                    paper = self._parse(doi, item)
                    if paper:
                        papers.append(paper)

            return SearchResult(query=query, total=total, papers=papers, source=self.name)
        except Exception:
            logger.exception("OpenAlex search error")
            return None

    def _parse(self, doi: str, data: dict) -> Paper | None:
        try:
            authors = []
            for authorship in data.get("authorships", []):
                author_data = authorship.get("author", {})
                name = author_data.get("display_name")
                if name:
                    institutions = authorship.get("institutions", [])
                    affiliation = (
                        institutions[0].get("display_name")
                        if institutions else None
                    )
                    authors.append(Author(
                        name=name,
                        orcid=author_data.get("orcid"),
                        affiliation=affiliation,
                    ))

            # Open access info
            oa = data.get("open_access", {})
            pdf_url = oa.get("oa_url")

            source_info = data.get("primary_location", {}).get("source") or {}

            return Paper(
                doi=doi.lower(),
                title=data.get("title"),
                authors=authors,
                abstract=self._reconstruct_abstract(data.get("abstract_inverted_index")),
                journal=source_info.get("display_name"),
                publisher=data.get("primary_location", {}).get("source", {}).get("host_organization_name"),
                year=data.get("publication_year"),
                url=data.get("doi"),
                pdf_url=pdf_url,
                is_open_access=oa.get("is_oa"),
                citation_count=data.get("cited_by_count"),
            )
        except Exception:
            logger.exception("OpenAlex parse error for %s", doi)
            return None

    @staticmethod
    def _reconstruct_abstract(inverted_index: dict | None) -> str | None:
        """Reconstruct abstract from OpenAlex inverted index format."""
        if not inverted_index:
            return None
        word_positions: list[tuple[int, str]] = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort()
        return " ".join(w for _, w in word_positions) if word_positions else None
