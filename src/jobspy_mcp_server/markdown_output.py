"""Markdown rendering helpers for MCP tool responses."""

from __future__ import annotations

from typing import Any

VALID_OUTPUT_FORMATS = {"json", "markdown"}


def validate_output_format(output_format: str) -> str | None:
    """Return an error message if output_format is invalid, else None."""
    if output_format not in VALID_OUTPUT_FORMATS:
        return (
            f"Invalid output_format '{output_format}'. "
            f"Valid values: {sorted(VALID_OUTPUT_FORMATS)}."
        )
    return None


def render_jobs_markdown(jobs: list[dict[str, Any]], search_term: str) -> str:
    """Render a job list as a Markdown document."""
    count = len(jobs)
    lines: list[str] = [
        f"## Job Search Results: \"{search_term}\"",
        "",
        f"**{count} job{'s' if count != 1 else ''} found**",
    ]
    for i, job in enumerate(jobs, 1):
        lines += [
            "",
            "---",
            "",
            f"### {i}. {job.get('role_title') or 'Untitled'}"
            f" — {job.get('company_name') or 'Unknown Company'}",
            "",
            f"| Field | Value |",
            f"| --- | --- |",
            f"| Location | {job.get('location') or '—'} |",
            f"| Platform | {job.get('source_platform') or '—'} |",
            f"| Posted | {job.get('scraped_at') or '—'} |",
            f"| URL | {job.get('job_url') or '—'} |",
        ]
        description = job.get("description")
        if description:
            lines += ["", "**Description:**", "", description]
    if not jobs:
        lines += ["", "_No jobs matched the search criteria._"]
    return "\n".join(lines)


def render_error_markdown(code: str, message: str) -> str:
    """Render an error response as Markdown."""
    return f"## Error\n\n**Code:** `{code}`\n\n**Message:** {message}"


def render_countries_markdown(
    countries: list[dict[str, Any]],
    usage_note: str,
    popular_aliases: list[str],
) -> str:
    """Render supported countries as a Markdown document."""
    lines: list[str] = [
        "## Supported Countries",
        "",
        usage_note,
        "",
        f"**Popular aliases:** {', '.join(f'`{a}`' for a in popular_aliases)}",
        "",
        "| Key | Aliases |",
        "| --- | --- |",
    ]
    for c in countries:
        aliases = ", ".join(f"`{a}`" for a in c.get("aliases", []))
        lines.append(f"| `{c['key']}` | {aliases} |")
    return "\n".join(lines)


def render_sites_markdown(
    sites: list[dict[str, Any]], usage_tips: list[str]
) -> str:
    """Render supported job board sites as a Markdown document."""
    lines: list[str] = [
        "## Supported Job Board Sites",
        "",
        "| Name | Description | Regions | Notes |",
        "| --- | --- | --- | --- |",
    ]
    for s in sites:
        regions = ", ".join(s.get("regions", []))
        lines.append(
            f"| `{s['name']}` | {s['description']} | {regions} | {s.get('reliability_note', '')} |"
        )
    lines += ["", "### Usage Tips", ""]
    for tip in usage_tips:
        lines.append(f"- {tip}")
    return "\n".join(lines)


def render_tips_markdown(tips: dict[str, Any]) -> str:
    """Render job search tips as a Markdown document."""
    lines: list[str] = ["## Job Search Tips", ""]
    section_titles = {
        "search_term_optimization": "Search Term Optimisation",
        "location_strategies": "Location Strategies",
        "site_selection": "Site Selection",
        "performance": "Performance",
        "advanced_filtering": "Advanced Filtering",
        "iterative_search_process": "Iterative Search Process",
    }
    for key, title in section_titles.items():
        items = tips.get(key, [])
        if not items:
            continue
        lines += [f"### {title}", ""]
        for item in items:
            lines.append(f"- {item}")
        lines.append("")
    common_issues = tips.get("common_issues", [])
    if common_issues:
        lines += ["### Common Issues", ""]
        for issue in common_issues:
            lines.append(f"- **{issue['issue']}:** {issue['guidance']}")
        lines.append("")
    sample_strategies = tips.get("sample_search_strategies", [])
    if sample_strategies:
        lines += ["### Sample Search Strategies", ""]
        for strategy in sample_strategies:
            args = strategy.get("arguments", {})
            formatted = ", ".join(f"`{k}={v!r}`" for k, v in args.items())
            lines.append(f"- **{strategy['name']}:** {formatted}")
        lines.append("")
    return "\n".join(lines).rstrip()
