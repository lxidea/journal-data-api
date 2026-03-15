"""FastMCP tool definitions."""

from __future__ import annotations

from fastmcp import FastMCP

from journal_api import resolver
from journal_api.models import PaperResult, SearchResult

mcp = FastMCP(
    "journal-data-api",
    instructions="Academic article access API with multi-source fallback. "
    "Provides metadata, full text, and PDF for academic papers by DOI, "
    "and search by title/author/keywords.",
)


@mcp.tool()
async def search_papers(query: str, limit: int = 10) -> dict:
    """Search academic papers by title, author, or keywords.

    Args:
        query: Search query string (title, author name, or keywords)
        limit: Maximum number of results to return (default 10, max 50)

    Returns:
        Search results with paper metadata including DOIs for further lookup.
    """
    limit = min(max(1, limit), 50)
    result = await resolver.search_papers(query, limit=limit)
    return result.model_dump()


@mcp.tool()
async def get_paper_metadata(doi: str) -> dict:
    """Get metadata for an academic paper by DOI.

    Retrieves title, authors, abstract, journal, year, citation count, etc.
    Uses multi-source fallback: CrossRef → OpenAlex → Semantic Scholar.

    Args:
        doi: Digital Object Identifier (e.g., "10.1038/nature12373")

    Returns:
        Paper metadata and list of sources used.
    """
    result = await resolver.get_metadata(doi)
    if not result:
        return {"error": f"Paper not found for DOI: {doi}"}
    return result.model_dump(exclude={"fulltext", "pdf_base64"})


@mcp.tool()
async def get_paper_fulltext(doi: str) -> dict:
    """Get the full text of an academic paper by DOI.

    Downloads the PDF and extracts text content. Uses multi-source fallback
    for PDF acquisition: Unpaywall (OA) → Campus proxy → Sci-Hub.

    Args:
        doi: Digital Object Identifier (e.g., "10.1038/nature12373")

    Returns:
        Paper metadata, extracted full text, and sources used.
        The pdf_base64 field is excluded to keep response size manageable.
    """
    result = await resolver.get_fulltext(doi)
    if not result:
        return {"error": f"Paper not found for DOI: {doi}"}
    return result.model_dump(exclude={"pdf_base64"})


@mcp.tool()
async def get_paper_pdf(doi: str) -> dict:
    """Download the PDF of an academic paper by DOI.

    Returns the PDF as a base64-encoded string. Uses multi-source fallback
    for PDF acquisition: Unpaywall (OA) → Campus proxy → Sci-Hub.

    Args:
        doi: Digital Object Identifier (e.g., "10.1038/nature12373")

    Returns:
        Paper metadata, base64-encoded PDF, and sources used.
    """
    result = await resolver.get_pdf_result(doi)
    if not result:
        return {"error": f"Paper not found for DOI: {doi}"}
    if not result.pdf_base64:
        return {
            "error": f"PDF not available for DOI: {doi}",
            "paper": result.paper.model_dump(),
            "sources_used": result.sources_used,
        }
    return result.model_dump(exclude={"fulltext"})
