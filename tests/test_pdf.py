"""Tests for PDF utilities."""

from journal_api.utils.pdf import is_valid_pdf


def test_invalid_pdf_empty():
    assert not is_valid_pdf(b"")


def test_invalid_pdf_wrong_magic():
    assert not is_valid_pdf(b"<html>not a pdf</html>")


def test_invalid_pdf_truncated():
    assert not is_valid_pdf(b"%PDF-1.4 truncated")
