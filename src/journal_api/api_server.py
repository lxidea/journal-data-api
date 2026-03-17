"""FastAPI REST endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from journal_api import resolver
from journal_api.http_client import close_clients


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_clients()


app = FastAPI(
    title="Journal Data API",
    description="Academic article access API with multi-source fallback",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/api/search")
async def search(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
):
    """Search for academic papers."""
    result = await resolver.search_papers(q, limit=limit)
    return result.model_dump()


@app.get("/api/metadata")
async def get_paper(doi: str = Query(..., description="DOI, e.g. 10.1038/nature12373")):
    """Get paper metadata by DOI."""
    result = await resolver.get_metadata(doi)
    if not result:
        raise HTTPException(status_code=404, detail=f"Paper not found: {doi}")
    return result.model_dump(exclude={"fulltext", "pdf_base64"})


@app.get("/api/fulltext")
async def get_fulltext(doi: str = Query(..., description="DOI")):
    """Get paper full text (extracted from PDF)."""
    result = await resolver.get_fulltext(doi)
    if not result:
        raise HTTPException(status_code=404, detail=f"Paper not found: {doi}")
    return result.model_dump(exclude={"pdf_base64"})


@app.get("/api/pdf")
async def get_pdf(doi: str = Query(..., description="DOI")):
    """Get paper PDF as base64."""
    result = await resolver.get_pdf_result(doi)
    if not result or not result.pdf_base64:
        raise HTTPException(status_code=404, detail=f"PDF not available: {doi}")
    return result.model_dump(exclude={"fulltext"})


@app.get("/health")
async def health():
    return {"status": "ok"}
