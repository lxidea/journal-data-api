"""Tests for data models."""

from journal_api.models import Author, Paper


def test_paper_metadata_complete():
    paper = Paper(
        doi="10.1038/nature12373",
        title="Test Paper",
        authors=[Author(name="Test Author")],
        year=2023,
    )
    assert paper.is_metadata_complete()


def test_paper_metadata_incomplete():
    paper = Paper(doi="10.1038/nature12373")
    assert not paper.is_metadata_complete()


def test_paper_merge():
    p1 = Paper(doi="10.1038/nature12373", title="Test Paper")
    p2 = Paper(
        doi="10.1038/nature12373",
        authors=[Author(name="Author A")],
        year=2023,
        abstract="An abstract.",
    )
    merged = p1.merge(p2)
    assert merged.title == "Test Paper"
    assert merged.year == 2023
    assert merged.abstract == "An abstract."
    assert len(merged.authors) == 1


def test_paper_merge_no_overwrite():
    p1 = Paper(doi="10.1038/nature12373", title="Original Title", year=2020)
    p2 = Paper(doi="10.1038/nature12373", title="Other Title", year=2023)
    merged = p1.merge(p2)
    assert merged.title == "Original Title"
    assert merged.year == 2020
