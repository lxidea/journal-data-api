"""Tests for DOI parsing/normalization."""

from journal_api.utils.doi import normalize_doi


def test_plain_doi():
    assert normalize_doi("10.1038/nature12373") == "10.1038/nature12373"


def test_doi_url():
    assert normalize_doi("https://doi.org/10.1038/nature12373") == "10.1038/nature12373"


def test_dx_doi_url():
    assert normalize_doi("http://dx.doi.org/10.1038/nature12373") == "10.1038/nature12373"


def test_doi_with_trailing_punctuation():
    assert normalize_doi("10.1038/nature12373.") == "10.1038/nature12373"


def test_doi_uppercase():
    assert normalize_doi("10.1038/Nature12373") == "10.1038/nature12373"


def test_doi_with_spaces():
    assert normalize_doi("  10.1038/nature12373  ") == "10.1038/nature12373"


def test_invalid_doi():
    assert normalize_doi("not a doi") is None


def test_url_encoded_doi():
    assert normalize_doi("https://doi.org/10.1000%2Fxyz123") == "10.1000/xyz123"
