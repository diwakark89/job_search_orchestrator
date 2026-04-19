from __future__ import annotations

"""Shared MCP response envelope formatting helpers.

These functions are the single point of truth for the JSON and Markdown
envelope shapes returned by all MCP tools in the orchestrator.  Keeping them
here avoids duplicating envelope logic across multiple tool modules.
"""

from typing import Any

from scraping.output import (
    build_error_envelope,
    build_jobs_success_envelope,
    render_error_markdown,
    render_jobs_markdown,
    serialize_json_payload,
)


def success_json_envelope(
    jobs: list[dict[str, Any]],
    *,
    site_errors: list[dict[str, Any]] | None = None,
) -> str:
    """Serialise a successful job-search result as a JSON envelope string."""
    return serialize_json_payload(build_jobs_success_envelope(jobs, site_errors=site_errors))


def error_json_envelope(code: str, message: str) -> str:
    """Serialise an error as a JSON envelope string."""
    return serialize_json_payload(build_error_envelope(code, message, jobs=[]))


def success_markdown(jobs: list[dict[str, Any]], search_term: str) -> str:
    """Render a successful job-search result as Markdown."""
    return render_jobs_markdown(jobs, search_term)


def error_markdown(code: str, message: str) -> str:
    """Render an error as Markdown."""
    return render_error_markdown(code, message)


def format_search_success(
    jobs: list[dict[str, Any]],
    search_term: str,
    *,
    output_format: str,
    site_errors: list[dict[str, Any]] | None = None,
) -> str:
    """Return success response in the requested output format.

    Args:
        jobs: Normalised job dicts.
        search_term: The original search term (used for Markdown headings).
        output_format: Either ``"json"`` or ``"markdown"``.
        site_errors: Optional per-site error metadata.

    Returns:
        Formatted string response.
    """
    if output_format == "markdown":
        return success_markdown(jobs, search_term)
    return success_json_envelope(jobs, site_errors=site_errors)


def format_search_error(
    code: str,
    message: str,
    *,
    output_format: str,
) -> str:
    """Return an error response in the requested output format.

    Args:
        code: Short error code string (e.g. ``"validation_error"``).
        message: Human-readable error message.
        output_format: Either ``"json"`` or ``"markdown"``.

    Returns:
        Formatted string response.
    """
    if output_format == "markdown":
        return error_markdown(code, message)
    return error_json_envelope(code, message)
