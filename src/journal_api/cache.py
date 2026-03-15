"""Disk-based cache for metadata and PDFs using diskcache."""

from __future__ import annotations

import logging
from pathlib import Path

from diskcache import Cache

from journal_api.config import get_settings

logger = logging.getLogger(__name__)

_cache: Cache | None = None

_METADATA_TTL = None  # Set on init
_PDF_TTL = None  # No expiry for PDFs


def _get_cache() -> Cache:
    global _cache, _METADATA_TTL
    if _cache is None:
        settings = get_settings()
        cache_dir = Path(settings.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        _cache = Cache(str(cache_dir), size_limit=2 * 1024**3)  # 2 GB limit
        _METADATA_TTL = settings.metadata_ttl_days * 86400
    return _cache


def get_metadata(doi: str) -> dict | None:
    """Retrieve cached metadata for a DOI."""
    cache = _get_cache()
    key = f"meta:{doi}"
    value = cache.get(key)
    if value is not None:
        logger.debug("Cache hit (metadata): %s", doi)
    return value


def set_metadata(doi: str, data: dict) -> None:
    """Cache metadata for a DOI with TTL."""
    cache = _get_cache()
    cache.set(f"meta:{doi}", data, expire=_METADATA_TTL)


def get_pdf(doi: str) -> bytes | None:
    """Retrieve cached PDF for a DOI."""
    cache = _get_cache()
    key = f"pdf:{doi}"
    value = cache.get(key)
    if value is not None:
        logger.debug("Cache hit (PDF): %s", doi)
    return value


def set_pdf(doi: str, data: bytes) -> None:
    """Cache PDF permanently (no TTL)."""
    cache = _get_cache()
    cache.set(f"pdf:{doi}", data)


def get_search(query: str) -> dict | None:
    """Retrieve cached search results."""
    cache = _get_cache()
    return cache.get(f"search:{query}")


def set_search(query: str, data: dict, ttl: int = 3600) -> None:
    """Cache search results with 1-hour default TTL."""
    cache = _get_cache()
    cache.set(f"search:{query}", data, expire=ttl)
