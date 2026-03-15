"""Sci-Hub — PDF acquisition via mirror rotation and HTML parsing."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from journal_api.config import get_settings
from journal_api.http_client import fetch, get_client
from journal_api.models import Paper
from journal_api.sources.base import Source
from journal_api.utils.pdf import is_valid_pdf
from journal_api.utils.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


class SciHubSource(Source):
    name = "scihub"

    async def get_metadata(self, doi: str) -> Paper | None:
        # Sci-Hub doesn't provide metadata
        return None

    async def get_pdf(self, doi: str) -> bytes | None:
        """Try each Sci-Hub mirror until we get a valid PDF."""
        settings = get_settings()
        mirrors = settings.scihub_mirrors

        for mirror in mirrors:
            try:
                pdf = await self._try_mirror(mirror, doi)
                if pdf and is_valid_pdf(pdf):
                    logger.info("Got PDF from Sci-Hub mirror %s for %s", mirror, doi)
                    return pdf
            except Exception:
                logger.warning("Sci-Hub mirror %s failed for %s", mirror, doi)
                continue

        return None

    async def _try_mirror(self, mirror: str, doi: str) -> bytes | None:
        """Attempt to get PDF from a specific mirror."""
        await rate_limiter.acquire(self.name)

        url = f"{mirror}/{doi}"
        resp = await fetch(
            url,
            source="",  # already rate-limited above
            accept="text/html",
        )
        if resp.status_code != 200:
            return None

        content_type = resp.headers.get("content-type", "")

        # Sometimes Sci-Hub returns PDF directly
        if "application/pdf" in content_type or resp.content[:5] == b"%PDF-":
            return resp.content

        # Otherwise parse HTML to find the PDF embed/iframe
        html = resp.text
        pdf_url = self._extract_pdf_url(html, mirror)
        if not pdf_url:
            return None

        # Download the actual PDF
        client = get_client()
        pdf_resp = await client.get(
            pdf_url,
            headers={"User-Agent": resp.request.headers.get("User-Agent", "")},
            follow_redirects=True,
        )
        if pdf_resp.status_code == 200:
            return pdf_resp.content

        return None

    @staticmethod
    def _extract_pdf_url(html: str, mirror: str) -> str | None:
        """Extract PDF URL from Sci-Hub HTML page."""
        soup = BeautifulSoup(html, "html.parser")

        # Try iframe/embed with PDF src
        for tag in soup.find_all(["iframe", "embed"]):
            src = tag.get("src", "")
            if src and (".pdf" in src or "/pdf/" in src):
                if src.startswith("//"):
                    return "https:" + src
                if src.startswith("/"):
                    return mirror + src
                return src

        # Try direct link pattern
        match = re.search(r'(https?://[^\s"\']+\.pdf)', html)
        if match:
            return match.group(1)

        # Try onclick with location.href
        match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+\.pdf[^'\"]*)['\"]", html)
        if match:
            url = match.group(1)
            if url.startswith("//"):
                return "https:" + url
            if url.startswith("/"):
                return mirror + url
            return url

        return None
