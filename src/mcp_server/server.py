from __future__ import annotations

"""Compatibility shim — re-exports the orchestrator MCP interface.

Consumers that previously imported from ``mcp_server.server`` continue to work
unchanged.  All implementation now lives in ``mcp_interface.server``.
"""

from mcp_interface.server import (
    get_job_search_tips,
    get_supported_countries,
    get_supported_sites,
    main,
    mcp,
    scrape_jobs_tool,
)

__all__ = [
    "get_job_search_tips",
    "get_supported_countries",
    "get_supported_sites",
    "main",
    "mcp",
    "scrape_jobs_tool",
]

