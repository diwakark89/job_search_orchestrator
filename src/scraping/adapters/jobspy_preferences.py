"""Adapter-local re-exports of vendored jobspy_mcp_server preference helpers.

Only this module (and other files inside src/scraping/adapters/) is permitted to
import from the vendored jobspy_mcp_server package. The orchestrator-owned
src/scraping/preferences.py wraps these symbols.
"""
from __future__ import annotations

from jobspy_mcp_server.preferences import (
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
