"""Output formatters for ``JobSearchResult`` / search errors.

These are pure functions over orchestrator-owned types and the output helpers
exposed by ``scraping.output``. No I/O, no scraping calls — easy to unit-test.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .output import (
    build_error_envelope,
    build_jobs_success_envelope,
    render_error_markdown,
    render_jobs_markdown,
    serialize_json_payload,
    validate_output_format,
)

if TYPE_CHECKING:
    from .service import JobSearchResult


def render_search_result(
    result: "JobSearchResult",
    *,
    output_format: str = "json",
    indent: int | None = None,
) -> str:
    format_error = validate_output_format(output_format)
    if format_error:
        raise ValueError(format_error)

    if output_format == "markdown":
        return render_jobs_markdown(result.jobs, result.search_term)

    payload = build_jobs_success_envelope(result.jobs, site_errors=result.site_errors)
    return serialize_json_payload(payload, indent=indent)


def render_search_error(
    code: str,
    message: str,
    *,
    output_format: str = "json",
    indent: int | None = None,
) -> str:
    format_error = validate_output_format(output_format)
    if format_error:
        output_format = "json"

    if output_format == "markdown":
        return render_error_markdown(code, message)

    return serialize_json_payload(
        build_error_envelope(code, message, jobs=[]),
        indent=indent,
    )


__all__ = ["render_search_error", "render_search_result"]
