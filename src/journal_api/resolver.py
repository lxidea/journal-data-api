"""Multi-source fallback orchestrator."""

from __future__ import annotations

import base64
import logging

from journal_api import cache
from journal_api.config import get_settings
from journal_api.http_client import fetch, get_client
from journal_api.models import Paper, PaperResult, SearchResult
from journal_api.sources.base import Source
from journal_api.sources.crossref import CrossRefSource
from journal_api.sources.google_scholar import GoogleScholarSource
from journal_api.sources.openalex import OpenAlexSource
from journal_api.sources.publisher_proxy import PublisherProxySource
from journal_api.sources.scihub import SciHubSource
from journal_api.sources.semantic_scholar import SemanticScholarSource
from journal_api.sources.unpaywall import UnpaywallSource
from journal_api.utils.doi import normalize_doi
from journal_api.utils.pdf import extract_text, is_valid_pdf

logger = logging.getLogger(__name__)

# Source instances (singletons)
_metadata_sources: list[Source] = [
    CrossRefSource(),
    OpenAlexSource(),
    SemanticScholarSource(),
    GoogleScholarSource(),
]

_pdf_sources_oa: list[Source] = [
    UnpaywallSource(),
]

_search_sources: list[Source] = [
    SemanticScholarSource(),
    CrossRefSource(),
    GoogleScholarSource(),
]


async def get_metadata(doi: str) -> PaperResult | None:
    """Resolve metadata for a DOI using multi-source fallback.

    Order: Cache → CrossRef → OpenAlex → Semantic Scholar → Google Scholar
    """
    doi = normalize_doi(doi) or doi.lower()
    sources_used: list[str] = []

    # 1. Cache
    cached = cache.get_metadata(doi)
    if cached:
        paper = Paper(**cached)
        if paper.is_metadata_complete():
            return PaperResult(paper=paper, sources_used=["cache"])

    # 2. Try each source, merge results
    paper = Paper(doi=doi) if not cached else Paper(**cached)

    for source in _metadata_sources:
        if paper.is_metadata_complete():
            break
        try:
            result = await source.get_metadata(doi)
            if result:
                paper = paper.merge(result)
                sources_used.append(source.name)
        except Exception:
            logger.warning("Source %s failed for %s", source.name, doi)
            continue

    if not paper.title:
        return None

    # Cache the result
    cache.set_metadata(doi, paper.model_dump())

    return PaperResult(paper=paper, sources_used=sources_used)


async def get_pdf(doi: str) -> tuple[bytes | None, list[str]]:
    """Get PDF for a DOI using multi-source fallback.

    Order: Cache → Unpaywall (OA) → Publisher via proxy → Sci-Hub
    Returns (pdf_bytes, sources_used).
    """
    doi = normalize_doi(doi) or doi.lower()
    sources_used: list[str] = []

    # 1. Cache
    cached_pdf = cache.get_pdf(doi)
    if cached_pdf:
        return cached_pdf, ["cache"]

    # 2. Try OA sources for PDF URL
    for source in _pdf_sources_oa:
        try:
            pdf_url = await source.get_pdf_url(doi)
            if pdf_url:
                pdf_data = await _download_pdf(pdf_url)
                if pdf_data:
                    cache.set_pdf(doi, pdf_data)
                    sources_used.append(source.name)
                    return pdf_data, sources_used
        except Exception:
            logger.warning("OA source %s failed for %s", source.name, doi)

    # Also check Semantic Scholar for OA PDF
    try:
        ss = SemanticScholarSource()
        pdf_url = await ss.get_pdf_url(doi)
        if pdf_url:
            pdf_data = await _download_pdf(pdf_url)
            if pdf_data:
                cache.set_pdf(doi, pdf_data)
                return pdf_data, ["semantic_scholar"]
    except Exception:
        pass

    # 3. Publisher via campus proxy
    proxy_source = PublisherProxySource()
    try:
        pdf_data = await proxy_source.get_pdf(doi)
        if pdf_data:
            cache.set_pdf(doi, pdf_data)
            return pdf_data, ["publisher_proxy"]
    except Exception:
        logger.warning("Publisher proxy failed for %s", doi)

    # 4. Sci-Hub
    scihub = SciHubSource()
    try:
        pdf_data = await scihub.get_pdf(doi)
        if pdf_data:
            cache.set_pdf(doi, pdf_data)
            return pdf_data, ["scihub"]
    except Exception:
        logger.warning("Sci-Hub failed for %s", doi)

    return None, sources_used


async def get_fulltext(doi: str) -> PaperResult | None:
    """Get paper metadata + full text extracted from PDF."""
    meta_result = await get_metadata(doi)
    if not meta_result:
        meta_result = PaperResult(paper=Paper(doi=doi), sources_used=[])

    pdf_data, pdf_sources = await get_pdf(doi)
    sources = list(set(meta_result.sources_used + pdf_sources))

    fulltext = None
    pdf_b64 = None
    if pdf_data:
        fulltext = extract_text(pdf_data)
        pdf_b64 = base64.b64encode(pdf_data).decode()

    return PaperResult(
        paper=meta_result.paper,
        sources_used=sources,
        fulltext=fulltext,
        pdf_base64=pdf_b64,
    )


async def get_pdf_result(doi: str) -> PaperResult | None:
    """Get paper PDF as base64."""
    meta_result = await get_metadata(doi)
    if not meta_result:
        meta_result = PaperResult(paper=Paper(doi=doi), sources_used=[])

    pdf_data, pdf_sources = await get_pdf(doi)
    sources = list(set(meta_result.sources_used + pdf_sources))

    pdf_b64 = None
    if pdf_data:
        pdf_b64 = base64.b64encode(pdf_data).decode()

    return PaperResult(
        paper=meta_result.paper,
        sources_used=sources,
        pdf_base64=pdf_b64,
    )


async def search_papers(query: str, limit: int = 10) -> SearchResult:
    """Search for papers using multi-source fallback.

    Order: Semantic Scholar → CrossRef → Google Scholar
    """
    # Check cache
    cached = cache.get_search(query)
    if cached:
        return SearchResult(**cached)

    for source in _search_sources:
        try:
            result = await source.search(query, limit=limit)
            if result and result.papers:
                cache.set_search(query, result.model_dump())
                return result
        except Exception:
            logger.warning("Search source %s failed", source.name)
            continue

    return SearchResult(query=query)


async def _download_pdf(url: str) -> bytes | None:
    """Download and validate a PDF from a URL."""
    try:
        client = get_client()
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code == 200 and is_valid_pdf(resp.content):
            return resp.content
    except Exception:
        logger.debug("PDF download failed from %s", url)
    return None
