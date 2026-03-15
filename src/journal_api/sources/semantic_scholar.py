"""Semantic Scholar API — metadata + citations + search."""

from __future__ import annotations

import logging

from journal_api.config import get_settings
from journal_api.http_client import fetch
from journal_api.models import Author, Paper, SearchResult
from journal_api.sources.base import Source

logger = logging.getLogger(__name__)

_BASE = "https://api.semanticscholar.org/graph/v1"
_FIELDS = "title,authors,abstract,year,venue,publicationVenue,externalIds,citationCount,referenceCount,openAccessPdf,references.externalIds"


class SemanticScholarSource(Source):
    name = "semantic_scholar"

    def _headers(self) -> dict:
        settings = get_settings()
        h = {}
        if settings.semantic_scholar_api_key:
            h["x-api-key"] = settings.semantic_scholar_api_key
        return h

    async def get_metadata(self, doi: str) -> Paper | None:
        try:
            resp = await fetch(
                f"{_BASE}/paper/DOI:{doi}",
                source=self.name,
                headers=self._headers(),
                params={"fields": _FIELDS},
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            return self._parse(doi, data)
        except Exception:
            logger.exception("Semantic Scholar error for %s", doi)
            return None

    async def search(self, query: str, limit: int = 10) -> SearchResult | None:
        try:
            resp = await fetch(
                f"{_BASE}/paper/search",
                source=self.name,
                headers=self._headers(),
                params={
                    "query": query,
                    "limit": limit,
                    "fields": "title,authors,year,externalIds,citationCount,openAccessPdf",
                },
            )
            if resp.status_code != 200:
                return None

            result = resp.json()
            total = result.get("total", 0)
            papers = []
            for item in result.get("data", []):
                ext = item.get("externalIds", {})
                doi = ext.get("DOI", "")
                if doi:
                    paper = self._parse(doi, item)
                    if paper:
                        papers.append(paper)

            return SearchResult(query=query, total=total, papers=papers, source=self.name)
        except Exception:
            logger.exception("Semantic Scholar search error")
            return None

    async def get_pdf_url(self, doi: str) -> str | None:
        paper = await self.get_metadata(doi)
        if paper and paper.pdf_url:
            return paper.pdf_url
        return None

    def _parse(self, doi: str, data: dict) -> Paper | None:
        try:
            authors = []
            for a in data.get("authors", []):
                name = a.get("name")
                if name:
                    authors.append(Author(name=name))

            oa_pdf = data.get("openAccessPdf", {})
            pdf_url = oa_pdf.get("url") if oa_pdf else None

            references = []
            for ref in data.get("references", []):
                ext = ref.get("externalIds") or {}
                ref_doi = ext.get("DOI")
                if ref_doi:
                    references.append(ref_doi)

            venue = data.get("venue") or ""
            pub_venue = data.get("publicationVenue") or {}

            return Paper(
                doi=doi.lower(),
                title=data.get("title"),
                authors=authors,
                abstract=data.get("abstract"),
                journal=pub_venue.get("name") or venue or None,
                year=data.get("year"),
                pdf_url=pdf_url,
                citation_count=data.get("citationCount"),
                references=references,
            )
        except Exception:
            logger.exception("Semantic Scholar parse error for %s", doi)
            return None
