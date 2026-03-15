"""Pydantic models for papers, authors, and results."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Author(BaseModel):
    name: str
    orcid: str | None = None
    affiliation: str | None = None


class Paper(BaseModel):
    doi: str
    title: str | None = None
    authors: list[Author] = Field(default_factory=list)
    abstract: str | None = None
    journal: str | None = None
    publisher: str | None = None
    year: int | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    is_open_access: bool | None = None
    citation_count: int | None = None
    references: list[str] = Field(default_factory=list)  # DOIs

    def is_metadata_complete(self) -> bool:
        """Check if we have the essential metadata fields."""
        return all([self.title, self.authors, self.year])

    def merge(self, other: Paper) -> Paper:
        """Merge another Paper into this one, filling missing fields."""
        data = self.model_dump()
        other_data = other.model_dump()
        for key, value in other_data.items():
            current = data.get(key)
            if key == "authors":
                if not current and value:
                    data[key] = value
            elif key == "references":
                if not current and value:
                    data[key] = value
            elif current is None and value is not None:
                data[key] = value
        return Paper(**data)


class PaperResult(BaseModel):
    """Result wrapper with source attribution."""
    paper: Paper
    sources_used: list[str] = Field(default_factory=list)
    fulltext: str | None = None
    pdf_base64: str | None = None


class SearchResult(BaseModel):
    """Search results."""
    query: str
    total: int = 0
    papers: list[Paper] = Field(default_factory=list)
    source: str = ""
