"""Unpaywall API — legal open access PDF links."""

from __future__ import annotations

import logging

from journal_api.config import get_settings
from journal_api.http_client import fetch
from journal_api.models import Author, Paper
from journal_api.sources.base import Source

logger = logging.getLogger(__name__)

_BASE = "https://api.unpaywall.org/v2"


class UnpaywallSource(Source):
    name = "unpaywall"

    async def get_metadata(self, doi: str) -> Paper | None:
        try:
            settings = get_settings()
            email = settings.unpaywall_email or settings.crossref_email
            if not email:
                email = "anonymous@example.com"

            resp = await fetch(
                f"{_BASE}/{doi}",
                source=self.name,
                params={"email": email},
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            return self._parse(doi, data)
        except Exception:
            logger.exception("Unpaywall error for %s", doi)
            return None

    async def get_pdf_url(self, doi: str) -> str | None:
        try:
            settings = get_settings()
            email = settings.unpaywall_email or settings.crossref_email or "anonymous@example.com"

            resp = await fetch(
                f"{_BASE}/{doi}",
                source=self.name,
                params={"email": email},
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            best = data.get("best_oa_location")
            if best:
                return best.get("url_for_pdf") or best.get("url_for_landing_page")
            return None
        except Exception:
            logger.exception("Unpaywall PDF URL error for %s", doi)
            return None

    def _parse(self, doi: str, data: dict) -> Paper | None:
        try:
            authors = []
            for a in data.get("z_authors", []):
                name_parts = []
                if a.get("given"):
                    name_parts.append(a["given"])
                if a.get("family"):
                    name_parts.append(a["family"])
                if name_parts:
                    authors.append(Author(name=" ".join(name_parts)))

            best = data.get("best_oa_location") or {}
            pdf_url = best.get("url_for_pdf") or best.get("url_for_landing_page")

            return Paper(
                doi=doi.lower(),
                title=data.get("title"),
                authors=authors,
                journal=data.get("journal_name"),
                publisher=data.get("publisher"),
                year=data.get("year"),
                url=data.get("doi_url"),
                pdf_url=pdf_url,
                is_open_access=data.get("is_oa"),
            )
        except Exception:
            logger.exception("Unpaywall parse error for %s", doi)
            return None
