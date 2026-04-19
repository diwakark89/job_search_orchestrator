"""Orchestrator-owned scraping output surface.

This module is the only public entry point for scraping output helpers used by
the service, MCP, and CLI layers. It delegates to an adapter-local shim so the
vendored jobspy_mcp_server package stays isolated behind src/scraping/adapters/.
"""
from __future__ import annotations

from .adapters.jobspy_output import (
    NormalizedJob,
    build_data_success_envelope,
    build_error_envelope,
    build_jobs_json_payload,
    build_jobs_success_envelope,
    render_countries_markdown,
    render_error_markdown,
    render_jobs_markdown,
    render_sites_markdown,
    render_tips_markdown,
    serialize_json_payload,
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
