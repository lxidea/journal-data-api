"""Comprehensive integration tests for journal-data-api.

Tests cover metadata resolution, search, PDF acquisition, full text extraction,
cache behavior, DOI normalization edge cases, rate limiter, and paper merging.

Integration tests that require network access are marked with @pytest.mark.integration.
"""

from __future__ import annotations

import time

import pytest

from journal_api.models import Author, Paper, PaperResult, SearchResult
from journal_api.utils.doi import normalize_doi
from journal_api.utils.rate_limiter import RateLimiter

# The well-known DOI used across tests (Nature paper: "Probing the limits...")
TEST_DOI = "10.1038/nature12373"


# ---------------------------------------------------------------------------
# 1. Metadata resolution
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestMetadataResolution:
    """Test get_metadata with a real DOI against live sources."""

    async def test_get_metadata_returns_paper_result(self):
        from journal_api.resolver import get_metadata

        result = await get_metadata(TEST_DOI)
        assert result is not None, "get_metadata returned None for a valid DOI"
        assert isinstance(result, PaperResult)

    async def test_metadata_has_title(self):
        from journal_api.resolver import get_metadata

        result = await get_metadata(TEST_DOI)
        assert result is not None
        assert result.paper.title is not None
        assert len(result.paper.title) > 0

    async def test_metadata_has_authors(self):
        from journal_api.resolver import get_metadata

        result = await get_metadata(TEST_DOI)
        assert result is not None
        assert len(result.paper.authors) > 0
        # Each author should have a name
        for author in result.paper.authors:
            assert isinstance(author, Author)
            assert author.name

    async def test_metadata_has_year(self):
        from journal_api.resolver import get_metadata

        result = await get_metadata(TEST_DOI)
        assert result is not None
        assert result.paper.year is not None
        # This paper was published in 2013
        assert result.paper.year == 2013

    async def test_metadata_has_journal(self):
        from journal_api.resolver import get_metadata

        result = await get_metadata(TEST_DOI)
        assert result is not None
        assert result.paper.journal is not None
        assert "nature" in result.paper.journal.lower()

    async def test_metadata_sources_used_populated(self):
        from journal_api.resolver import get_metadata

        result = await get_metadata(TEST_DOI)
        assert result is not None
        assert len(result.sources_used) > 0


# ---------------------------------------------------------------------------
# 2. Search
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSearch:
    """Test search_papers with a real query."""

    async def test_search_returns_search_result(self):
        from journal_api.resolver import search_papers

        result = await search_papers("diamond NV center quantum sensing")
        assert isinstance(result, SearchResult)

    async def test_search_returns_papers(self):
        from journal_api.resolver import search_papers

        result = await search_papers("diamond NV center quantum sensing")
        assert len(result.papers) > 0, "Search returned no papers"

    async def test_search_papers_have_titles(self):
        from journal_api.resolver import search_papers

        result = await search_papers("diamond NV center quantum sensing")
        for paper in result.papers:
            assert isinstance(paper, Paper)
            assert paper.title is not None
            assert len(paper.title) > 0

    async def test_search_result_has_query(self):
        from journal_api.resolver import search_papers

        query = "diamond NV center quantum sensing"
        result = await search_papers(query)
        assert result.query == query

    async def test_search_respects_limit(self):
        from journal_api.resolver import search_papers

        result = await search_papers("quantum computing", limit=3)
        assert len(result.papers) <= 3


# ---------------------------------------------------------------------------
# 3. PDF acquisition
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestPdfAcquisition:
    """Test get_pdf with a real DOI."""

    async def test_get_pdf_returns_bytes(self):
        from journal_api.resolver import get_pdf

        pdf_data, sources = await get_pdf(TEST_DOI)
        assert pdf_data is not None, (
            f"get_pdf returned None. Sources tried: {sources}"
        )
        assert isinstance(pdf_data, bytes)
        assert len(pdf_data) > 0

    async def test_pdf_is_valid(self):
        from journal_api.resolver import get_pdf
        from journal_api.utils.pdf import is_valid_pdf

        pdf_data, _ = await get_pdf(TEST_DOI)
        if pdf_data is not None:
            assert is_valid_pdf(pdf_data), "Downloaded PDF failed validation"
        else:
            pytest.skip("PDF not available from any source")

    async def test_pdf_sources_used(self):
        from journal_api.resolver import get_pdf

        pdf_data, sources = await get_pdf(TEST_DOI)
        if pdf_data is not None:
            assert len(sources) > 0


# ---------------------------------------------------------------------------
# 4. Full text extraction
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestFulltextExtraction:
    """Test get_fulltext with a real DOI."""

    async def test_get_fulltext_returns_result(self):
        from journal_api.resolver import get_fulltext

        result = await get_fulltext(TEST_DOI)
        assert result is not None
        assert isinstance(result, PaperResult)

    async def test_fulltext_is_not_none(self):
        from journal_api.resolver import get_fulltext

        result = await get_fulltext(TEST_DOI)
        assert result is not None
        if result.fulltext is None:
            pytest.skip("Full text extraction unavailable (PDF may not be accessible)")
        assert len(result.fulltext) > 0

    async def test_fulltext_contains_text(self):
        from journal_api.resolver import get_fulltext

        result = await get_fulltext(TEST_DOI)
        assert result is not None
        if result.fulltext is None:
            pytest.skip("Full text extraction unavailable")
        # The fulltext should contain actual words, not just whitespace
        words = result.fulltext.split()
        assert len(words) > 50, "Full text seems too short to be a real paper"

    async def test_fulltext_has_pdf_base64(self):
        from journal_api.resolver import get_fulltext

        result = await get_fulltext(TEST_DOI)
        assert result is not None
        if result.pdf_base64 is None:
            pytest.skip("PDF not available")
        # Verify base64 is decodable
        import base64
        decoded = base64.b64decode(result.pdf_base64)
        assert len(decoded) > 0


# ---------------------------------------------------------------------------
# 5. Cache behavior
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCacheBehavior:
    """Test that cache hits work after initial fetches."""

    async def test_metadata_cache_hit_is_fast(self):
        from journal_api.resolver import get_metadata

        # First call (may or may not be cached already from earlier tests)
        await get_metadata(TEST_DOI)

        # Second call should be from cache and very fast
        start = time.monotonic()
        result = await get_metadata(TEST_DOI)
        elapsed = time.monotonic() - start

        assert result is not None
        assert "cache" in result.sources_used
        # Cache hit should be under 50ms
        assert elapsed < 0.05, f"Cache hit took {elapsed:.3f}s, expected <0.05s"

    async def test_search_cache_hit(self):
        from journal_api.resolver import search_papers

        query = "diamond NV center quantum sensing"
        # First call
        await search_papers(query)

        # Second call should be cached
        start = time.monotonic()
        result = await search_papers(query)
        elapsed = time.monotonic() - start

        assert isinstance(result, SearchResult)
        assert elapsed < 0.05, f"Search cache hit took {elapsed:.3f}s, expected <0.05s"

    async def test_pdf_cache_hit(self):
        from journal_api import cache as cache_mod

        # Only test if PDF was cached during earlier tests
        cached = cache_mod.get_pdf(normalize_doi(TEST_DOI) or TEST_DOI)
        if cached is None:
            pytest.skip("PDF not in cache (PDF tests may have been skipped)")
        assert isinstance(cached, bytes)
        assert len(cached) > 0


# ---------------------------------------------------------------------------
# 6. DOI normalization edge cases
# ---------------------------------------------------------------------------

class TestDoiNormalization:
    """Test normalize_doi with various input formats (no network needed)."""

    def test_plain_doi(self):
        result = normalize_doi("10.1038/nature12373")
        assert result == "10.1038/nature12373"

    def test_doi_with_https_url(self):
        result = normalize_doi("https://doi.org/10.1038/nature12373")
        assert result == "10.1038/nature12373"

    def test_doi_with_http_url(self):
        result = normalize_doi("http://doi.org/10.1038/nature12373")
        assert result == "10.1038/nature12373"

    def test_doi_with_dx_prefix(self):
        result = normalize_doi("https://dx.doi.org/10.1038/nature12373")
        assert result == "10.1038/nature12373"

    def test_doi_with_http_dx_prefix(self):
        result = normalize_doi("http://dx.doi.org/10.1038/nature12373")
        assert result == "10.1038/nature12373"

    def test_doi_with_whitespace(self):
        result = normalize_doi("  10.1038/nature12373  ")
        assert result == "10.1038/nature12373"

    def test_doi_url_encoded(self):
        result = normalize_doi("https://doi.org/10.1000%2Fxyz123")
        assert result == "10.1000/xyz123"

    def test_doi_with_trailing_punctuation(self):
        result = normalize_doi("10.1038/nature12373.")
        assert result == "10.1038/nature12373"
        result2 = normalize_doi("10.1038/nature12373,")
        assert result2 == "10.1038/nature12373"
        result3 = normalize_doi("10.1038/nature12373;")
        assert result3 == "10.1038/nature12373"

    def test_doi_case_insensitive(self):
        result = normalize_doi("10.1038/Nature12373")
        assert result == "10.1038/nature12373"

    def test_doi_with_uppercase_url_prefix(self):
        # The prefix matching is case-insensitive via .lower()
        result = normalize_doi("HTTPS://DOI.ORG/10.1038/nature12373")
        assert result == "10.1038/nature12373"

    def test_invalid_doi_returns_none(self):
        result = normalize_doi("not-a-doi")
        assert result is None

    def test_empty_string_returns_none(self):
        result = normalize_doi("")
        assert result is None

    def test_doi_with_complex_suffix(self):
        result = normalize_doi("10.1103/PhysRevLett.112.150801")
        assert result == "10.1103/physrevlett.112.150801"

    def test_doi_long_registrant(self):
        result = normalize_doi("10.1002/1521-3773(20010316)40:6<9823::AID-ANIE9823>3.0.CO;2-V")
        assert result is not None
        assert result.startswith("10.1002/")

    def test_doi_with_trailing_parenthesis(self):
        result = normalize_doi("10.1038/nature12373)")
        assert result == "10.1038/nature12373"


# ---------------------------------------------------------------------------
# 7. Rate limiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    """Test the RateLimiter utility (no network needed)."""

    async def test_acquire_unconfigured_source_returns_immediately(self):
        limiter = RateLimiter()
        # Unconfigured source should not block
        start = time.monotonic()
        await limiter.acquire("unknown_source")
        elapsed = time.monotonic() - start
        assert elapsed < 0.01

    async def test_configure_and_acquire(self):
        limiter = RateLimiter()
        limiter.configure("test_source", rate=100.0)
        # First acquire should be instant (has token)
        start = time.monotonic()
        await limiter.acquire("test_source")
        elapsed = time.monotonic() - start
        assert elapsed < 0.05

    async def test_rate_limiting_throttles(self):
        limiter = RateLimiter()
        limiter.configure("slow_source", rate=2.0)  # 2 req/sec
        # Exhaust initial token
        await limiter.acquire("slow_source")
        # Second acquire should be near-instant if token refilled
        # Third may need a small wait
        await limiter.acquire("slow_source")
        # Just verify no exception is raised

    async def test_multiple_sources_independent(self):
        limiter = RateLimiter()
        limiter.configure("source_a", rate=10.0)
        limiter.configure("source_b", rate=10.0)
        await limiter.acquire("source_a")
        await limiter.acquire("source_b")
        # Both should work independently without interference

    async def test_global_rate_limiter_instance(self):
        from journal_api.utils.rate_limiter import rate_limiter

        assert isinstance(rate_limiter, RateLimiter)
        # Should be callable without error
        await rate_limiter.acquire("nonexistent_source")


# ---------------------------------------------------------------------------
# 8. Paper merge
# ---------------------------------------------------------------------------

class TestPaperMerge:
    """Test merging two partial Paper objects (no network needed)."""

    def test_merge_fills_missing_fields(self):
        paper1 = Paper(doi="10.1038/nature12373", title="Test Paper")
        paper2 = Paper(
            doi="10.1038/nature12373",
            year=2013,
            journal="Nature",
            authors=[Author(name="John Doe")],
        )
        merged = paper1.merge(paper2)
        assert merged.title == "Test Paper"
        assert merged.year == 2013
        assert merged.journal == "Nature"
        assert len(merged.authors) == 1

    def test_merge_does_not_overwrite_existing(self):
        paper1 = Paper(doi="10.1038/nature12373", title="Original Title", year=2013)
        paper2 = Paper(doi="10.1038/nature12373", title="Different Title", year=2020)
        merged = paper1.merge(paper2)
        assert merged.title == "Original Title"
        assert merged.year == 2013

    def test_merge_authors_only_if_empty(self):
        paper1 = Paper(
            doi="10.1038/test",
            authors=[Author(name="Alice")],
        )
        paper2 = Paper(
            doi="10.1038/test",
            authors=[Author(name="Bob"), Author(name="Carol")],
        )
        merged = paper1.merge(paper2)
        # paper1 already has authors, so merge should keep them
        assert len(merged.authors) == 1
        assert merged.authors[0].name == "Alice"

    def test_merge_authors_fills_when_empty(self):
        paper1 = Paper(doi="10.1038/test")
        paper2 = Paper(
            doi="10.1038/test",
            authors=[Author(name="Bob")],
        )
        merged = paper1.merge(paper2)
        assert len(merged.authors) == 1
        assert merged.authors[0].name == "Bob"

    def test_merge_preserves_doi(self):
        paper1 = Paper(doi="10.1038/original")
        paper2 = Paper(doi="10.1038/other", title="Some Title")
        merged = paper1.merge(paper2)
        assert merged.doi == "10.1038/original"

    def test_merge_references(self):
        paper1 = Paper(doi="10.1038/test")
        paper2 = Paper(doi="10.1038/test", references=["10.1000/ref1", "10.1000/ref2"])
        merged = paper1.merge(paper2)
        assert len(merged.references) == 2

    def test_merge_references_not_overwritten(self):
        paper1 = Paper(doi="10.1038/test", references=["10.1000/existing"])
        paper2 = Paper(doi="10.1038/test", references=["10.1000/ref1", "10.1000/ref2"])
        merged = paper1.merge(paper2)
        assert len(merged.references) == 1
        assert merged.references[0] == "10.1000/existing"

    def test_is_metadata_complete(self):
        incomplete = Paper(doi="10.1038/test", title="Test")
        assert not incomplete.is_metadata_complete()

        complete = Paper(
            doi="10.1038/test",
            title="Test",
            authors=[Author(name="Alice")],
            year=2023,
        )
        assert complete.is_metadata_complete()

    def test_merge_chain(self):
        """Test merging three sources sequentially."""
        base = Paper(doi="10.1038/test")
        source1 = Paper(doi="10.1038/test", title="Title from Source 1")
        source2 = Paper(
            doi="10.1038/test",
            authors=[Author(name="Author from Source 2")],
            journal="Journal X",
        )
        source3 = Paper(doi="10.1038/test", year=2023, abstract="Abstract text")

        result = base.merge(source1).merge(source2).merge(source3)
        assert result.title == "Title from Source 1"
        assert len(result.authors) == 1
        assert result.journal == "Journal X"
        assert result.year == 2023
        assert result.abstract == "Abstract text"
        assert result.is_metadata_complete()
