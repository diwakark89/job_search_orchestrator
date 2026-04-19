"""Adapter-local re-exports of vendored jobspy_mcp_server output helpers.

Only this module (and other files inside src/scraping/adapters/) is permitted to
import from the vendored jobspy_mcp_server package. The orchestrator-owned
src/scraping/output.py wraps these symbols so the rest of the codebase depends
on the orchestrator surface, not the vendored one.
"""
from __future__ import annotations

from jobspy_mcp_server.json_output import (
    NormalizedJob,
    build_data_success_envelope,
    build_error_envelope,
    build_jobs_json_payload,
    build_jobs_success_envelope,
    serialize_json_payload,
)
from jobspy_mcp_server.markdown_output import (
    render_countries_markdown,
    render_error_markdown,
    render_jobs_markdown,
    render_sites_markdown,
    render_tips_markdown,
    validate_output_format,
)

__all__ = [
    "NormalizedJob",
    "build_data_success_envelope",
    "build_error_envelope",
    "build_jobs_json_payload",
    "build_jobs_success_envelope",
    "render_countries_markdown",
    "render_error_markdown",
    "render_jobs_markdown",
    "render_sites_markdown",
    "render_tips_markdown",
    "serialize_json_payload",
    "validate_output_format",
]
