"""Publisher direct access via campus HTTP proxy."""

from __future__ import annotations

import logging

from journal_api.config import get_settings
from journal_api.http_client import fetch
from journal_api.models import Paper
from journal_api.sources.base import Source
from journal_api.utils.pdf import is_valid_pdf

logger = logging.getLogger(__name__)

# Publisher PDF URL patterns
_PUBLISHER_PDF_PATTERNS: dict[str, str] = {
    "wiley": "https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}",
    "springer": "https://link.springer.com/content/pdf/{doi}.pdf",
    "nature": "https://www.nature.com/articles/{suffix}.pdf",
    "elsevier": "https://www.sciencedirect.com/science/article/pii/{pii}/pdfft",
    "aip": "https://pubs.aip.org/aip/jcp/article-pdf/doi/{doi}",
    "acs": "https://pubs.acs.org/doi/pdf/{doi}",
    "ieee": "https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?arnumber={arnumber}",
}


class PublisherProxySource(Source):
    name = "publisher_proxy"

    async def get_metadata(self, doi: str) -> Paper | None:
        return None

    async def get_pdf(self, doi: str) -> bytes | None:
        """Try to download PDF directly from publisher via campus proxy."""
        settings = get_settings()
        if not settings.campus_proxy_url:
            return None

        # Try generic DOI redirect to PDF
        urls_to_try = [
            f"https://doi.org/{doi}",
        ]

        # Add publisher-specific patterns based on DOI prefix
        doi_lower = doi.lower()
        if "10.1002" in doi_lower or "10.1111" in doi_lower:
            urls_to_try.insert(0, _PUBLISHER_PDF_PATTERNS["wiley"].format(doi=doi))
        elif "10.1007" in doi_lower or "10.1038" in doi_lower:
            suffix = doi.split("/")[-1]
            urls_to_try.insert(0, _PUBLISHER_PDF_PATTERNS["springer"].format(doi=doi))
            urls_to_try.insert(0, _PUBLISHER_PDF_PATTERNS["nature"].format(suffix=suffix))
        elif "10.1021" in doi_lower:
            urls_to_try.insert(0, _PUBLISHER_PDF_PATTERNS["acs"].format(doi=doi))
        elif "10.1063" in doi_lower:
            urls_to_try.insert(0, _PUBLISHER_PDF_PATTERNS["aip"].format(doi=doi))

        for url in urls_to_try:
            try:
                resp = await fetch(
                    url,
                    source=self.name,
                    use_proxy=True,
                    accept="application/pdf",
                )
                if resp.status_code == 200 and is_valid_pdf(resp.content):
                    logger.info("Got PDF via campus proxy from %s", url)
                    return resp.content
            except Exception:
                logger.debug("Publisher proxy failed for %s", url)
                continue

        return None
