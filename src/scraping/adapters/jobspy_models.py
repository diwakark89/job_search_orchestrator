"""Adapter-local re-exports of vendored jobspy_mcp_server domain types.

Only this module (and other files inside src/scraping/adapters/) is permitted to
import from the vendored jobspy_mcp_server package. The orchestrator-owned
src/scraping/models.py wraps these symbols.
"""
from __future__ import annotations

from jobspy_mcp_server.jobspy_scrapers.model import (
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
