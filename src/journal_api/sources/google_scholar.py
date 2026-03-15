"""Google Scholar — search discovery (lowest priority, highest ban risk)."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from journal_api.http_client import fetch
from journal_api.models import Author, Paper, SearchResult
from journal_api.sources.base import Source

logger = logging.getLogger(__name__)

_BASE = "https://scholar.google.com"


class GoogleScholarSource(Source):
    name = "google_scholar"

    async def get_metadata(self, doi: str) -> Paper | None:
        """Search Google Scholar by DOI — very rate-limited."""
        result = await self.search(doi, limit=1)
        if result and result.papers:
            return result.papers[0]
        return None

    async def search(self, query: str, limit: int = 10) -> SearchResult | None:
        try:
            resp = await fetch(
                f"{_BASE}/scholar",
                source=self.name,
                params={"q": query, "num": min(limit, 20), "hl": "en"},
                accept="text/html",
            )
            if resp.status_code != 200:
                logger.warning("Google Scholar returned %d", resp.status_code)
                return None

            if "unusual traffic" in resp.text.lower():
                logger.warning("Google Scholar CAPTCHA detected")
                return None

            papers = self._parse_results(resp.text)
            return SearchResult(
                query=query,
                total=len(papers),
                papers=papers[:limit],
                source=self.name,
            )
        except Exception:
            logger.exception("Google Scholar search error")
            return None

    def _parse_results(self, html: str) -> list[Paper]:
        """Parse Google Scholar search results HTML."""
        soup = BeautifulSoup(html, "html.parser")
        papers = []

        for result in soup.select(".gs_ri"):
            try:
                # Title
                title_tag = result.select_one(".gs_rt")
                title = title_tag.get_text(strip=True) if title_tag else None

                # Remove [PDF] [HTML] etc prefixes
                if title:
                    title = re.sub(r"^\[.+?\]\s*", "", title)

                # Authors / year / journal line
                info_tag = result.select_one(".gs_a")
                info_text = info_tag.get_text(strip=True) if info_tag else ""

                authors = []
                year = None
                journal = None
                if info_text:
                    parts = info_text.split(" - ")
                    if len(parts) >= 1:
                        author_names = parts[0].split(",")
                        authors = [Author(name=n.strip()) for n in author_names if n.strip() and n.strip() != "…"]
                    if len(parts) >= 2:
                        year_match = re.search(r"(\d{4})", parts[1])
                        if year_match:
                            year = int(year_match.group(1))
                        journal = re.sub(r"\d{4}", "", parts[1]).strip(" ,- ")

                # Abstract snippet
                abstract_tag = result.select_one(".gs_rs")
                abstract = abstract_tag.get_text(strip=True) if abstract_tag else None

                # Try to find DOI in links
                doi = None
                for link in result.select("a"):
                    href = link.get("href", "")
                    doi_match = re.search(r"(10\.\d{4,9}/[^\s&]+)", href)
                    if doi_match:
                        doi = doi_match.group(1).lower()
                        break

                if title:
                    papers.append(Paper(
                        doi=doi or "",
                        title=title,
                        authors=authors,
                        abstract=abstract,
                        journal=journal if journal else None,
                        year=year,
                    ))
            except Exception:
                continue

        return papers
