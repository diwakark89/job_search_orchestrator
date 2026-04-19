from __future__ import annotations

"""Orchestrator MCP interface module.

This module wires MCP tools against the orchestrator's service layer instead of
calling the vendored jobspy internals directly.  The ``scrape_jobs_tool`` is the
primary integration point: it delegates entirely to ``scraping.service.search_jobs``
and ``mcp_interface.serialization`` for formatting, keeping this file thin.

The three informational tools (countries, sites, tips) proxy to the vendored
output helpers since those do not touch scraping core.

Backward compatibility is preserved:
  - All tool names, parameter names, and default values are identical to the
    vendored ``jobspy_mcp_server.server``.
  - The ``main()`` entry point accepts the same ``--transport``, ``--host``,
    and ``--port`` arguments.
"""

import argparse
import logging
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from scraping.guardrails import (
    FETCH_DESCRIPTIONS_DEFAULT,
    HOURS_OLD_DEFAULT,
    OFFSET_DEFAULT,
    RESULTS_WANTED_DEFAULT,
    SITES_DEFAULT,
)
from scraping.models import Country
from scraping.output import (
    build_data_success_envelope,
    build_error_envelope,
    render_countries_markdown,
    render_sites_markdown,
    render_tips_markdown,
    serialize_json_payload,
    validate_output_format,
)
from scraping.service import JobSearchRequest, search_jobs

from .serialization import format_search_error, format_search_success

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jobspy-mcp")

mcp = FastMCP("JobSpy Job Search Server")

# ── helper ──────────────────────────────────────────────────────────────────

def _data_envelope(**data: Any) -> str:
    return serialize_json_payload(build_data_success_envelope(**data))


def _error_envelope(code: str, message: str, **extra: Any) -> str:
    return serialize_json_payload(build_error_envelope(code, message, **extra))


# ── scrape tool ─────────────────────────────────────────────────────────────

@mcp.tool()
async def scrape_jobs_tool(
    ctx: Context,
    search_term: str | None = None,
    cities: list[str] | None = None,
    site_name: list[str] = SITES_DEFAULT,
    results_wanted: int = RESULTS_WANTED_DEFAULT,
    job_type: str | None = None,
    work_mode: str | None = None,
    is_remote: bool | None = None,
    hours_old: int = HOURS_OLD_DEFAULT,
    easy_apply: bool = False,
    country_indeed: str | None = None,
    linkedin_fetch_description: bool = FETCH_DESCRIPTIONS_DEFAULT,
    offset: int = OFFSET_DEFAULT,
    output_format: str = "json",
) -> str:
    """Search for jobs across multiple job boards including LinkedIn, Indeed, Glassdoor,
    ZipRecruiter, Google Jobs, Bayt, Naukri, Stepstone, Xing, Berlin Startup Jobs,
    Welcome to the Jungle, EU-Startups, and join.com.

    Args:
        search_term: Job search keywords (e.g., 'software engineer', 'data scientist')
        ctx: MCP context for progress reporting
        cities: List of cities to search (e.g., ['Munich', 'Berlin', 'Darmstadt']).
        site_name: Job boards to search (1-5 sites, default: linkedin)
        results_wanted: Number of job results to retrieve (1-50, default 1)
        job_type: Type of employment ('fulltime', 'parttime', 'internship', 'contract')
        work_mode: Work mode filter ('remote', 'hybrid', 'on-site')
        is_remote: Filter for remote jobs only (None applies preference defaults)
        hours_old: Only return jobs posted within the last N hours (1-72, default 24)
        easy_apply: Filter for jobs with easy apply options
        country_indeed: Country for Indeed/Glassdoor searches
        linkedin_fetch_description: Fetch full job descriptions from LinkedIn (slower)
        offset: Number of results to skip for pagination (0-1000)
        output_format: Response format — 'json' (default) or 'markdown'

    Returns:
        JSON envelope with 'ok', 'jobs', and 'error' keys, or Markdown when output_format='markdown'
    """
    format_error = validate_output_format(output_format)
    if format_error:
        return format_search_error("validation_error", format_error, output_format=output_format)

    await ctx.info(f"Searching for '{search_term or '(from preferences)'}' jobs…")
    await ctx.report_progress(progress=0.1, total=1.0, message="Initialising job search…")

    try:
        request = JobSearchRequest(
            search_term=search_term,
            cities=cities,
            site_name=site_name,
            results_wanted=results_wanted,
            job_type=job_type,
            work_mode=work_mode,
            is_remote=is_remote,
            hours_old=hours_old,
            easy_apply=easy_apply,
            country_indeed=country_indeed,
            linkedin_fetch_description=linkedin_fetch_description,
            offset=offset,
            verbose=1,
        )
        result = search_jobs(request)
    except ValueError as exc:
        return format_search_error("validation_error", str(exc), output_format=output_format)
    except RuntimeError as exc:
        logger.error("scrape_jobs_tool runtime error: %s", exc)
        await ctx.error(str(exc))
        return format_search_error("runtime_error", str(exc), output_format=output_format)

    await ctx.report_progress(progress=0.9, total=1.0, message="Formatting results…")

    if result.site_errors:
        await ctx.warning(f"Some sites failed during scraping: {result.site_errors}")

    if not result.jobs:
        await ctx.warning("No jobs found matching the search criteria.")

    await ctx.report_progress(progress=1.0, total=1.0, message="Done.")
    await ctx.info(f"Found {len(result.jobs)} job(s).")

    return format_search_success(
        result.jobs,
        result.search_term,
        output_format=output_format,
        site_errors=result.site_errors,
    )


# ── informational tools ─────────────────────────────────────────────────────

@mcp.tool()
def get_supported_countries(output_format: str = "json") -> str:
    """Get list of supported countries for job searches.

    Args:
        output_format: Response format — 'json' (default) or 'markdown'

    Returns:
        JSON envelope containing supported countries and aliases, or Markdown
    """
    format_error = validate_output_format(output_format)
    if format_error:
        return _error_envelope("validation_error", format_error, countries=[])

    try:
        countries = []
        for country in Country:
            aliases = [alias.strip() for alias in country.value[0].split(",") if alias.strip()]
            try:
                indeed_subdomain, indeed_code = country.indeed_domain_value
            except (IndexError, ValueError):
                indeed_subdomain, indeed_code = None, None
            try:
                glassdoor_host = country.glassdoor_domain_value
            except ValueError:
                glassdoor_host = None

            countries.append(
                {
                    "key": country.name,
                    "aliases": aliases,
                    "indeed": {"subdomain": indeed_subdomain, "api_country_code": indeed_code},
                    "glassdoor_host": glassdoor_host,
                }
            )

        countries.sort(key=lambda item: item["key"])
        popular_aliases = ["usa", "uk", "canada", "australia", "germany", "france", "india", "singapore"]
        usage_note = "Use one of the listed aliases for the country_indeed parameter."
        if output_format == "markdown":
            return render_countries_markdown(countries, usage_note, popular_aliases)
        return _data_envelope(countries=countries, usage_note=usage_note, popular_aliases=popular_aliases)
    except Exception as exc:  # noqa: BLE001
        logger.error("get_supported_countries error: %s", exc)
        return _error_envelope("runtime_error", str(exc), countries=[])


@mcp.tool()
def get_supported_sites(output_format: str = "json") -> str:
    """Get list of supported job board sites with descriptions.

    Args:
        output_format: Response format — 'json' (default) or 'markdown'

    Returns:
        JSON envelope containing supported sites and usage guidance, or Markdown
    """
    format_error = validate_output_format(output_format)
    if format_error:
        return _error_envelope("validation_error", format_error, sites=[])

    sites_info = [
        {"name": "linkedin", "description": "Professional networking platform with job listings.", "regions": ["global"], "reliability_note": "Requires careful rate limiting."},
        {"name": "indeed", "description": "Large multi-country job search engine.", "regions": ["global"], "reliability_note": "Most reliable starting point for broad searches."},
        {"name": "glassdoor", "description": "Job listings with company reviews and salary context.", "regions": ["multi-country"], "reliability_note": "Useful when company context matters."},
        {"name": "zip_recruiter", "description": "Job matching platform for US and Canada.", "regions": ["usa", "canada"], "reliability_note": "Good supplemental source for North America."},
        {"name": "google", "description": "Aggregated job listings surfaced through Google Jobs.", "regions": ["global"], "reliability_note": "Works best with specific search terms."},
        {"name": "bayt", "description": "Job portal focused on Middle East markets.", "regions": ["middle-east"], "reliability_note": "Use for regional coverage not available on larger sites."},
        {"name": "naukri", "description": "India-focused job portal with strong local coverage.", "regions": ["india"], "reliability_note": "Best for India-focused searches."},
        {"name": "stepstone", "description": "European job board with strong Germany and DACH coverage.", "regions": ["germany", "dach", "europe"], "reliability_note": "Strong regional source for German-speaking markets."},
        {"name": "xing", "description": "German professional network with job listings.", "regions": ["germany", "dach"], "reliability_note": "Useful when targeting German-speaking markets."},
        {"name": "berlin_startup_jobs", "description": "Curated startup roles based in Berlin.", "regions": ["berlin", "germany"], "reliability_note": "Best for Berlin startup ecosystem."},
        {"name": "welcome_to_the_jungle", "description": "European tech and startup jobs.", "regions": ["france", "europe", "global"], "reliability_note": "Backed by a public Algolia search API."},
        {"name": "eu_startups", "description": "EU-Startups jobs board with pan-European startup roles.", "regions": ["europe"], "reliability_note": "Strong for EU startup roles."},
        {"name": "join", "description": "join.com aggregator of European SMB and startup roles.", "regions": ["germany", "dach", "europe"], "reliability_note": "Disabled when JOBSPY_RESPECT_ROBOTS is set."},
    ]
    usage_tips = [
        "Start with ['indeed', 'zip_recruiter'] for a reliable first pass.",
        "Use ['indeed', 'linkedin', 'glassdoor'] for broader coverage.",
        "Include regional sites for location-specific searches.",
        "LinkedIn is the most restrictive source for rate limiting.",
    ]
    if output_format == "markdown":
        return render_sites_markdown(sites_info, usage_tips)
    return _data_envelope(sites=sites_info, usage_tips=usage_tips)


@mcp.tool()
def get_job_search_tips(output_format: str = "json") -> str:
    """Get helpful tips and best practices for job searching with JobSpy.

    Args:
        output_format: Response format — 'json' (default) or 'markdown'

    Returns:
        JSON envelope containing search strategies and best practices, or Markdown
    """
    format_error = validate_output_format(output_format)
    if format_error:
        return _error_envelope("validation_error", format_error)

    tips = {
        "search_term_optimization": [
            "Be specific: use 'Python developer' instead of only 'developer'.",
            "Try variations: software engineer, software developer, programmer.",
            "Include technologies such as React, AWS, or Python when relevant.",
            "Add seniority keywords: junior, senior, lead, principal.",
        ],
        "location_strategies": [
            "Set is_remote=true for remote-only jobs.",
            "Use cities=['Munich', 'Berlin'] to target specific markets.",
            "Set country_indeed explicitly for non-US Indeed or Glassdoor searches.",
        ],
        "site_selection": [
            "Start with 1-3 sites to keep requests fast.",
            "Indeed is the most reliable baseline source.",
            "Use regional sources for geography-specific searches.",
        ],
        "performance": [
            "Start with small result counts (5-10), then widen if needed.",
            "Use hours_old to focus on recent postings.",
            "Enable linkedin_fetch_description only when full descriptions are required.",
        ],
        "advanced_filtering": [
            "Supported job_type values: fulltime, parttime, internship, contract.",
            "Set easy_apply=true for quick-apply friendly listings.",
            "Combine cities, country_indeed, and is_remote to narrow broad searches.",
        ],
        "common_issues": [
            {"issue": "No results", "guidance": "Try broader search terms, fewer filters, or a different site."},
            {"issue": "Rate limiting", "guidance": "Reduce results_wanted and use fewer sites."},
            {"issue": "Slow searches", "guidance": "Disable linkedin_fetch_description."},
        ],
    }
    if output_format == "markdown":
        return render_tips_markdown(tips)
    return _data_envelope(tips=tips)


# ── entry point ─────────────────────────────────────────────────────────────

def main() -> None:
    """Run the JobSpy MCP server.

    Supports multiple transports:
      - stdio (default): for MCP clients like Claude Desktop, Cursor
      - sse: Server-Sent Events over HTTP (legacy HTTP transport)
      - streamable-http: modern MCP HTTP transport
    """
    parser = argparse.ArgumentParser(description="JobSpy MCP Server — job scraping as AI-callable tools")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio", help="MCP transport to use (default: stdio)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind when using sse or streamable-http (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind when using sse or streamable-http (default: 8765)")
    args = parser.parse_args()

    logger.info("Starting JobSpy MCP Server…")
    logger.info("Transport: %s", args.transport)
    if args.transport != "stdio":
        logger.info("Listening on http://%s:%d", args.host, args.port)

    try:
        if args.transport == "stdio":
            mcp.run(transport="stdio")
        else:
            mcp.run(transport=args.transport, host=args.host, port=args.port)
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Server error: %s", exc)
