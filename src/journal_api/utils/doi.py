"""DOI parsing and normalization utilities."""

from __future__ import annotations

import re
from urllib.parse import unquote


# Match DOI pattern: 10.XXXX/...
_DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s]+)")


def normalize_doi(raw: str) -> str | None:
    """Extract and normalize a DOI from various input formats.

    Handles:
    - Plain DOI: 10.1038/nature12373
    - URL: https://doi.org/10.1038/nature12373
    - dx.doi.org URLs
    - URL-encoded DOIs
    """
    raw = raw.strip()
    raw = unquote(raw)

    # Strip common URL prefixes
    for prefix in [
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
    ]:
        if raw.lower().startswith(prefix):
            raw = raw[len(prefix):]
            break

    match = _DOI_RE.search(raw)
    if match:
        doi = match.group(1)
        # Remove trailing punctuation that's not part of DOI
        doi = doi.rstrip(".,;:)")
        return doi.lower()
    return None
