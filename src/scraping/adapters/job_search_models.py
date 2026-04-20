"""Adapter-local re-exports of vendored job_search_mcp_server domain types.

Only this module (and other files inside src/scraping/adapters/) is permitted to
import from the vendored job_search_mcp_server package. The orchestrator-owned
src/scraping/models.py wraps these symbols.
"""
from __future__ import annotations

from job_search_mcp_server.job_search_scrapers.model import (
    Country,
    JobPost,
    JobResponse,
    JobType,
    Location,
    Site,
)

__all__ = [
    "Country",
    "JobPost",
    "JobResponse",
    "JobType",
    "Location",
    "Site",
]
