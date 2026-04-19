"""Orchestrator-owned scraping preferences surface.

Delegates to an adapter-local shim so the vendored jobspy_mcp_server package
stays isolated behind src/scraping/adapters/.
"""
from __future__ import annotations

from .adapters.jobspy_preferences import (
    RuntimePreferenceDefaults,
    SearchPreferences,
    derive_runtime_defaults,
    load_search_preferences,
    resolve_preferences_file,
)

__all__ = [
    "RuntimePreferenceDefaults",
    "SearchPreferences",
    "derive_runtime_defaults",
    "load_search_preferences",
    "resolve_preferences_file",
]
