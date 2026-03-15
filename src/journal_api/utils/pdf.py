"""PDF validation and text extraction using PyMuPDF."""

from __future__ import annotations

import logging

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def is_valid_pdf(data: bytes) -> bool:
    """Check if data is a valid PDF by magic bytes and parseability."""
    if not data or not data[:5].startswith(b"%PDF-"):
        return False
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        valid = doc.page_count > 0
        doc.close()
        return valid
    except Exception:
        return False


def extract_text(data: bytes) -> str | None:
    """Extract text from PDF bytes."""
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        pages = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages.append(text)
        doc.close()
        return "\n\n".join(pages) if pages else None
    except Exception:
        logger.exception("PDF text extraction failed")
        return None
