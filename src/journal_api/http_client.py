"""Shared async HTTP client with UA rotation, proxy support, and retry."""

from __future__ import annotations

import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from journal_api.config import get_settings
from journal_api.utils.rate_limiter import rate_limiter
from journal_api.utils.user_agents import random_user_agent

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None
_proxy_client: httpx.AsyncClient | None = None


def _make_client(proxy: str | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        http2=True,
        timeout=httpx.Timeout(30.0, connect=10.0),
        follow_redirects=True,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        proxy=proxy,
    )


def get_client() -> httpx.AsyncClient:
    """Get the shared async HTTP client (no proxy)."""
    global _client
    if _client is None or _client.is_closed:
        _client = _make_client()
    return _client


def get_proxy_client() -> httpx.AsyncClient | None:
    """Get the campus-proxy HTTP client, or None if not configured."""
    global _proxy_client
    settings = get_settings()
    if not settings.campus_proxy_url:
        return None
    if _proxy_client is None or _proxy_client.is_closed:
        _proxy_client = _make_client(proxy=settings.campus_proxy_url)
    return _proxy_client


async def close_clients() -> None:
    """Close all HTTP clients."""
    global _client, _proxy_client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
    if _proxy_client and not _proxy_client.is_closed:
        await _proxy_client.aclose()
        _proxy_client = None


class RetryableHTTPError(Exception):
    """Wraps HTTP errors that should trigger a retry."""
    def __init__(self, status_code: int, url: str):
        self.status_code = status_code
        self.url = url
        super().__init__(f"HTTP {status_code} from {url}")


@retry(
    retry=retry_if_exception_type((RetryableHTTPError, httpx.ConnectError, httpx.ReadTimeout)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def fetch(
    url: str,
    *,
    source: str = "",
    headers: dict | None = None,
    params: dict | None = None,
    use_proxy: bool = False,
    accept: str = "application/json",
) -> httpx.Response:
    """Fetch a URL with rate limiting, UA rotation, and retry.

    Raises RetryableHTTPError for 429/5xx, httpx errors for others.
    """
    if source:
        await rate_limiter.acquire(source)

    client = (get_proxy_client() if use_proxy else None) or get_client()

    merged_headers = {
        "User-Agent": random_user_agent(),
        "Accept": accept,
    }
    if headers:
        merged_headers.update(headers)

    response = await client.get(url, headers=merged_headers, params=params)

    if response.status_code in (429, 503, 502, 500):
        logger.warning("Retryable HTTP %d from %s", response.status_code, url)
        raise RetryableHTTPError(response.status_code, url)

    return response
