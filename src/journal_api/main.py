"""Entry point: mcp | serve | get <doi>"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

from journal_api.config import get_settings
from journal_api.utils.rate_limiter import rate_limiter


def _setup_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _setup_rate_limits() -> None:
    settings = get_settings()
    rate_limiter.configure("crossref", settings.rate_crossref)
    rate_limiter.configure("openalex", settings.rate_openalex)
    rate_limiter.configure("semantic_scholar", settings.rate_semantic_scholar)
    rate_limiter.configure("unpaywall", settings.rate_unpaywall)
    rate_limiter.configure("scihub", settings.rate_scihub)
    rate_limiter.configure("google_scholar", settings.rate_google_scholar)
    rate_limiter.configure("publisher_proxy", settings.rate_publisher_proxy)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m journal_api <command> [args]")
        print("Commands:")
        print("  mcp              Start MCP server (stdio)")
        print("  serve            Start FastAPI REST server")
        print("  get <doi>        Lookup a paper by DOI (CLI)")
        print("  search <query>   Search for papers (CLI)")
        sys.exit(1)

    command = sys.argv[1]

    _setup_logging()
    _setup_rate_limits()

    if command == "mcp":
        from journal_api.mcp_server import mcp
        mcp.run()

    elif command == "serve":
        import uvicorn
        from journal_api.api_server import app

        settings = get_settings()
        uvicorn.run(app, host=settings.api_host, port=settings.api_port)

    elif command == "get":
        if len(sys.argv) < 3:
            print("Usage: python -m journal_api get <doi>")
            sys.exit(1)
        doi = sys.argv[2]
        asyncio.run(_cli_get(doi))

    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: python -m journal_api search <query>")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        asyncio.run(_cli_search(query))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


async def _cli_get(doi: str) -> None:
    from journal_api import resolver
    from journal_api.http_client import close_clients

    try:
        print(f"Looking up DOI: {doi}")
        result = await resolver.get_metadata(doi)
        if result:
            data = result.model_dump(exclude={"fulltext", "pdf_base64"})
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"Paper not found: {doi}")

        # Try PDF
        pdf_data, pdf_sources = await resolver.get_pdf(doi)
        if pdf_data:
            print(f"\nPDF acquired ({len(pdf_data)} bytes) from: {pdf_sources}")
        else:
            print("\nPDF not available")
    finally:
        await close_clients()


async def _cli_search(query: str) -> None:
    from journal_api import resolver
    from journal_api.http_client import close_clients

    try:
        print(f"Searching: {query}")
        result = await resolver.search_papers(query)
        data = result.model_dump()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    finally:
        await close_clients()


if __name__ == "__main__":
    main()
