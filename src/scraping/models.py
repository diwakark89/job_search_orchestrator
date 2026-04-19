from __future__ import annotations

"""Orchestrator-native type aliases for commonly used scraper domain types.

These re-exports are an explicit orchestrator choice — the names below are the
types the orchestrator service layer recognises.  If the underlying vendored
package is replaced, only the adapter shim needs to change.
"""

from .adapters.jobspy_models import (
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

