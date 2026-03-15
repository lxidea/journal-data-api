"""CrossRef API — primary metadata source."""

from __future__ import annotations

import logging

from journal_api.config import get_settings
from journal_api.http_client import fetch
from journal_api.models import Author, Paper, SearchResult
from journal_api.sources.base import Source

logger = logging.getLogger(__name__)

_BASE = "https://api.crossref.org"


class CrossRefSource(Source):
    name = "crossref"

    async def get_metadata(self, doi: str) -> Paper | None:
        try:
            settings = get_settings()
            params = {}
            headers = {}
            if settings.crossref_email:
                params["mailto"] = settings.crossref_email
                headers["User-Agent"] = (
                    f"journal-data-api/0.1 (mailto:{settings.crossref_email})"
                )

            resp = await fetch(
                f"{_BASE}/works/{doi}",
                source=self.name,
                params=params,
                headers=headers,
            )
            if resp.status_code != 200:
                return None

            data = resp.json()["message"]
            return self._parse(doi, data)
        except Exception:
            logger.exception("CrossRef error for %s", doi)
            return None

    async def search(self, query: str, limit: int = 10) -> SearchResult | None:
        try:
            settings = get_settings()
            params: dict = {"query": query, "rows": limit}
            if settings.crossref_email:
                params["mailto"] = settings.crossref_email

            resp = await fetch(
                f"{_BASE}/works",
                source=self.name,
                params=params,
            )
            if resp.status_code != 200:
                return None

            items = resp.json()["message"]["items"]
            total = resp.json()["message"]["total-results"]
            papers = []
            for item in items:
                doi = item.get("DOI", "")
                if doi:
                    paper = self._parse(doi, item)
                    if paper:
                        papers.append(paper)

            return SearchResult(
                query=query,
                total=total,
                papers=papers,
                source=self.name,
            )
        except Exception:
            logger.exception("CrossRef search error")
            return None

    def _parse(self, doi: str, data: dict) -> Paper | None:
        try:
            title_list = data.get("title", [])
            title = title_list[0] if title_list else None

            authors = []
            for a in data.get("author", []):
                name_parts = []
                if a.get("given"):
                    name_parts.append(a["given"])
                if a.get("family"):
                    name_parts.append(a["family"])
                if name_parts:
                    authors.append(Author(
                        name=" ".join(name_parts),
                        orcid=a.get("ORCID"),
                        affiliation=(
                            a["affiliation"][0].get("name")
                            if a.get("affiliation") else None
                        ),
                    ))

            # Year from published-print or published-online or created
            year = None
            for date_field in ["published-print", "published-online", "created"]:
                date_parts = data.get(date_field, {}).get("date-parts", [[]])
                if date_parts and date_parts[0] and date_parts[0][0]:
                    year = date_parts[0][0]
                    break

            abstract = data.get("abstract", "")
            # CrossRef abstracts often have JATS XML tags
            if abstract:
                import re
                abstract = re.sub(r"<[^>]+>", "", abstract).strip()

            return Paper(
                doi=doi.lower(),
                title=title,
                authors=authors,
                abstract=abstract or None,
                journal=data.get("container-title", [None])[0] if data.get("container-title") else None,
                publisher=data.get("publisher"),
                year=year,
                volume=data.get("volume"),
                issue=data.get("issue"),
                pages=data.get("page"),
                url=data.get("URL"),
                is_open_access=data.get("is-referenced-by-count") is not None,  # placeholder
                citation_count=data.get("is-referenced-by-count"),
                references=[
                    ref["DOI"]
                    for ref in data.get("reference", [])
                    if ref.get("DOI")
                ],
            )
        except Exception:
            logger.exception("CrossRef parse error for %s", doi)
            return None
