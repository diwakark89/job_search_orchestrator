#!/usr/bin/env python3
"""
JobSpy MCP Server - 2025 Latest Implementation

An MCP server that provides job scraping capabilities using the JobSpy library.
Built with FastMCP for modern MCP protocol compliance.
"""

import argparse
import logging
from typing import Any

# Modern MCP imports (2025)
from mcp.server.fastmcp import FastMCP, Context

# JobSpy imports
from jobspy_mcp_server.json_output import (
    build_data_success_envelope,
    build_error_envelope,
    build_jobs_json_payload,
    build_jobs_success_envelope,
    serialize_json_payload,
)
from jobspy_mcp_server.jobspy_scrapers import scrape_jobs
from jobspy_mcp_server.jobspy_scrapers.model import Country
from jobspy_mcp_server.preferences import derive_runtime_defaults, load_search_preferences
from jobspy_mcp_server.markdown_output import (
    validate_output_format,
    render_jobs_markdown,
    render_error_markdown,
    render_countries_markdown,
    render_sites_markdown,
    render_tips_markdown,
)
from jobspy_mcp_server.guardrails import (
    CITIES_DEFAULT,
    CITIES_MAX,
    CITIES_MIN,
    FETCH_DESCRIPTIONS_DEFAULT,
    HOURS_OLD_DEFAULT,
    HOURS_OLD_MAX,
    HOURS_OLD_MIN,
    OFFSET_DEFAULT,
    OFFSET_MAX,
    OFFSET_MIN,
    RESULTS_WANTED_DEFAULT,
    RESULTS_WANTED_MAX,
    RESULTS_WANTED_MIN,
    SITES_DEFAULT,
    SITES_MAX,
    SITES_MIN,
    VALID_SITES,
    WORK_MODES,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jobspy-mcp")

# Create FastMCP server instance
mcp = FastMCP("JobSpy Job Search Server")


def _success_envelope(
    jobs: list[dict[str, Any]],
    *,
    site_errors: list[dict[str, Any]] | None = None,
) -> str:
    return serialize_json_payload(build_jobs_success_envelope(jobs, site_errors=site_errors))


def _error_envelope(code: str, message: str) -> str:
    return serialize_json_payload(build_error_envelope(code, message, jobs=[]))


def _serialize_success_payload(**data: object) -> str:
    return serialize_json_payload(build_data_success_envelope(**data))


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
    """
    Search for jobs across multiple job boards including LinkedIn, Indeed, Glassdoor,
    ZipRecruiter, Google Jobs, Bayt, Naukri, Stepstone, Xing, Berlin Startup Jobs,
    Welcome to the Jungle, EU-Startups, and join.com.

    Args:
        search_term: Job search keywords (e.g., 'software engineer', 'data scientist')
        ctx: MCP context for progress reporting
        cities: List of cities to search (e.g., ['Munich', 'Berlin', 'Darmstadt']).
                If provided, search is limited to these cities only.
        site_name: Job boards to search (1-3 sites, default: linkedin)
        results_wanted: Number of job results to retrieve (1-15, default 10)
        job_type: Type of employment ('fulltime', 'parttime', 'internship', 'contract')
        work_mode: Work mode filter ('remote', 'hybrid', 'on-site')
        is_remote: Filter for remote jobs only (None applies preference defaults)
        hours_old: Only return jobs posted within the last N hours (1-72, default 24)
        easy_apply: Filter for jobs with easy apply options
        country_indeed: Country for Indeed/Glassdoor searches (None applies preference defaults)
        linkedin_fetch_description: Fetch full job descriptions from LinkedIn (slower)
        offset: Number of results to skip for pagination (0-1000)
        output_format: Response format — 'json' (default) or 'markdown'

    Returns:
        JSON envelope with `ok`, `jobs`, and `error` keys, or Markdown when output_format='markdown'
    """
    try:
        format_error = validate_output_format(output_format)
        if format_error:
            return _error_envelope("validation_error", format_error)

        preferences = load_search_preferences()
        runtime_defaults = derive_runtime_defaults(preferences)

        effective_search_term = search_term or runtime_defaults.default_search_term
        if not effective_search_term:
            return _error_envelope(
                "validation_error",
                "search_term is required when no preferred roles are configured.",
            )

        # Resolve cities from argument or preferences
        effective_cities = cities if cities is not None else runtime_defaults.default_cities
        effective_country = country_indeed or runtime_defaults.default_country_indeed
        effective_is_remote = is_remote if is_remote is not None else runtime_defaults.prefer_remote

        logger.info(f"Starting job search for: {effective_search_term}")
        
        # Send progress update
        await ctx.info(f"Searching for '{effective_search_term}' jobs...")
        
        # Validate site names
        invalid_sites = [site for site in site_name if site not in VALID_SITES]
        if invalid_sites:
            return _error_envelope(
                "validation_error",
                f"Invalid site names: {invalid_sites}. Valid sites: {VALID_SITES}",
            )

        # Validate site count
        if len(site_name) < SITES_MIN:
            return _error_envelope(
                "validation_error",
                f"At least {SITES_MIN} site must be specified.",
            )
        if len(site_name) > SITES_MAX:
            return _error_envelope(
                "validation_error",
                f"Maximum {SITES_MAX} sites per request, got {len(site_name)}. Choose up to {SITES_MAX} from: {VALID_SITES}"
            )

        if work_mode is not None and work_mode not in WORK_MODES:
            return _error_envelope(
                "validation_error",
                f"Invalid work_mode '{work_mode}'. Valid values: {WORK_MODES}",
            )

        # Validate cities if provided
        if effective_cities and len(effective_cities) > CITIES_MAX:
            return _error_envelope(
                "validation_error",
                f"Maximum {CITIES_MAX} cities per request, got {len(effective_cities)}."
            )

        # Clamp numeric parameters to safe ranges (ADR-001)
        original = {"results_wanted": results_wanted, "hours_old": hours_old, "offset": offset}
        results_wanted = min(max(results_wanted, RESULTS_WANTED_MIN), RESULTS_WANTED_MAX)
        hours_old = min(max(hours_old, HOURS_OLD_MIN), HOURS_OLD_MAX)
        offset = min(max(offset, OFFSET_MIN), OFFSET_MAX)
        clamped = {
            k: v for k, v in {
                "results_wanted": results_wanted, "hours_old": hours_old,
                "offset": offset,
            }.items() if v != original[k]
        }
        if clamped:
            logger.warning("Clamped parameters to safe ranges: %s (original: %s)", clamped, {k: original[k] for k in clamped})

        # Report progress
        await ctx.report_progress(
            progress=0.1,
            total=1.0,
            message="Initializing job search..."
        )
        
        # Call JobSpy scrape_jobs function
        jobs_df = scrape_jobs(
            site_name=site_name,
            search_term=effective_search_term,
            cities=effective_cities,
            results_wanted=results_wanted,
            job_type=job_type,
            work_mode=work_mode,
            is_remote=effective_is_remote,
            hours_old=hours_old,
            easy_apply=easy_apply,
            country_indeed=effective_country,
            linkedin_fetch_description=linkedin_fetch_description,
            offset=offset,
            verbose=1,
            description_format="markdown"
        )
        
        await ctx.report_progress(
            progress=0.8,
            total=1.0,
            message="Processing job results..."
        )

        site_errors = jobs_df.attrs.get("site_errors") if hasattr(jobs_df, "attrs") else None
        if site_errors:
            await ctx.warning(f"Some sites failed during scraping: {site_errors}")
        
        if jobs_df.empty:
            await ctx.warning("No jobs found matching the search criteria")
            if output_format == "markdown":
                return render_jobs_markdown([], effective_search_term)
            return _success_envelope([], site_errors=site_errors)

        jobs_list = build_jobs_json_payload(jobs_df)
        jobs_payload: list[dict[str, Any]] = [dict(job) for job in jobs_list]
        await ctx.report_progress(progress=1.0, total=1.0, message="Job search completed!")
        await ctx.info(f"Successfully found {len(jobs_df)} jobs")
        if output_format == "markdown":
            return render_jobs_markdown(jobs_payload, effective_search_term)
        return _success_envelope(jobs_payload, site_errors=site_errors)

    except Exception as e:
        logger.error(f"Error scraping jobs: {e}")
        await ctx.error(f"Job search failed: {str(e)}")
        if output_format == "markdown":
            return render_error_markdown("runtime_error", f"Job search failed: {str(e)}")
        return _error_envelope("runtime_error", f"Job search failed: {str(e)}")


@mcp.tool()
def get_supported_countries(output_format: str = "json") -> str:
    """
    Get list of supported countries for job searches.

    Args:
        output_format: Response format — 'json' (default) or 'markdown'

    Returns:
        JSON envelope containing supported countries and aliases, or Markdown
    """
    format_error = validate_output_format(output_format)
    if format_error:
        return serialize_json_payload(build_error_envelope("validation_error", format_error, countries=[]))
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
                    "indeed": {
                        "subdomain": indeed_subdomain,
                        "api_country_code": indeed_code,
                    },
                    "glassdoor_host": glassdoor_host,
                }
            )

        countries.sort(key=lambda item: item["key"])
        popular_aliases = [
            "usa", "uk", "canada", "australia",
            "germany", "france", "india", "singapore",
        ]
        usage_note = "Use one of the listed aliases for the country_indeed parameter."
        if output_format == "markdown":
            return render_countries_markdown(countries, usage_note, popular_aliases)
        return _serialize_success_payload(
            countries=countries,
            usage_note=usage_note,
            popular_aliases=popular_aliases,
        )
    except Exception as e:
        logger.error(f"Error getting supported countries: {e}")
        if output_format == "markdown":
            return render_error_markdown("runtime_error", f"Error getting supported countries: {str(e)}")
        return serialize_json_payload(
            build_error_envelope(
                "runtime_error",
                f"Error getting supported countries: {str(e)}",
                countries=[],
            )
        )


@mcp.tool()
def get_supported_sites(output_format: str = "json") -> str:
    """
    Get list of supported job board sites with descriptions.

    Args:
        output_format: Response format — 'json' (default) or 'markdown'

    Returns:
        JSON envelope containing supported sites and usage guidance, or Markdown
    """
    format_error = validate_output_format(output_format)
    if format_error:
        return serialize_json_payload(build_error_envelope("validation_error", format_error, sites=[]))
    try:
        sites_info = [
            {
                "name": "linkedin",
                "description": "Professional networking platform with job listings.",
                "regions": ["global"],
                "reliability_note": "Requires the most careful rate limiting.",
            },
            {
                "name": "indeed",
                "description": "Large multi-country job search engine.",
                "regions": ["global"],
                "reliability_note": "Most reliable starting point for broad searches.",
            },
            {
                "name": "glassdoor",
                "description": "Job listings with company reviews and salary context.",
                "regions": ["multi-country"],
                "reliability_note": "Useful when company context matters.",
            },
            {
                "name": "zip_recruiter",
                "description": "Job matching platform for US and Canada.",
                "regions": ["usa", "canada"],
                "reliability_note": "Good supplemental source for North America.",
            },
            {
                "name": "google",
                "description": "Aggregated job listings surfaced through Google Jobs.",
                "regions": ["global"],
                "reliability_note": "Works best with specific search terms.",
            },
            {
                "name": "bayt",
                "description": "Job portal focused on Middle East markets.",
                "regions": ["middle-east"],
                "reliability_note": "Use for regional coverage not available on larger sites.",
            },
            {
                "name": "naukri",
                "description": "India-focused job portal with strong local coverage.",
                "regions": ["india"],
                "reliability_note": "Best for India-focused searches.",
            },
            {
                "name": "stepstone",
                "description": "European job board with strong Germany and DACH coverage.",
                "regions": ["germany", "dach", "europe"],
                "reliability_note": "Strong regional source for German-speaking markets.",
            },
            {
                "name": "xing",
                "description": "German professional network with job listings.",
                "regions": ["germany", "dach"],
                "reliability_note": "Useful when targeting German-speaking markets.",
            },
            {
                "name": "berlin_startup_jobs",
                "description": "Curated startup roles based in Berlin (berlinstartupjobs.com).",
                "regions": ["berlin", "germany"],
                "reliability_note": "Best for Berlin startup ecosystem; defaults all listings to Berlin/Germany.",
            },
            {
                "name": "welcome_to_the_jungle",
                "description": "Welcome to the Jungle (welcometothejungle.com) European tech and startup jobs.",
                "regions": ["france", "europe", "global"],
                "reliability_note": "Backed by a public Algolia search API; disabled when JOBSPY_RESPECT_ROBOTS is set.",
            },
            {
                "name": "eu_startups",
                "description": "EU-Startups jobs board (jobs.eu-startups.com) with pan-European startup roles.",
                "regions": ["europe"],
                "reliability_note": "Strong for EU startup roles; standard WP Job Manager markup.",
            },
            {
                "name": "join",
                "description": "join.com aggregator of European SMB and startup roles.",
                "regions": ["germany", "dach", "europe"],
                "reliability_note": "Disabled when JOBSPY_RESPECT_ROBOTS is set (ToS-restricted).",
            },
        ]

        usage_tips = [
            "Start with ['indeed', 'zip_recruiter'] for a reliable first pass.",
            "Use ['indeed', 'linkedin', 'glassdoor'] when you need broader coverage.",
            "Include regional sites like bayt, naukri, stepstone, xing, berlin_startup_jobs, welcome_to_the_jungle, eu_startups, or join for location-specific searches.",
            "LinkedIn is the most restrictive source for rate limiting.",
        ]
        if output_format == "markdown":
            return render_sites_markdown(sites_info, usage_tips)
        return _serialize_success_payload(
            sites=sites_info,
            usage_tips=usage_tips,
        )
    except Exception as e:
        logger.error(f"Error getting supported sites: {e}")
        if output_format == "markdown":
            return render_error_markdown("runtime_error", f"Error getting supported sites: {str(e)}")
        return serialize_json_payload(
            build_error_envelope(
                "runtime_error",
                f"Error getting supported sites: {str(e)}",
                sites=[],
            )
        )


@mcp.tool()
def get_job_search_tips(output_format: str = "json") -> str:
    """
    Get helpful tips and best practices for job searching with JobSpy.

    Args:
        output_format: Response format — 'json' (default) or 'markdown'

    Returns:
        JSON envelope containing search strategies and best practices, or Markdown
    """
    format_error = validate_output_format(output_format)
    if format_error:
        return serialize_json_payload(build_error_envelope("validation_error", format_error))
    tips = {
            "search_term_optimization": [
                "Be specific: use 'Python developer' instead of only 'developer'.",
                "Use quoted phrases for exact matches such as 'machine learning engineer'.",
                "Try variations like software engineer, software developer, and programmer.",
                "Include technologies such as React, AWS, or Python when relevant.",
                "Add seniority keywords like junior, senior, lead, or principal when needed.",
            ],
            "location_strategies": [
                "Set is_remote=true when you want remote-only jobs.",
                "Use cities=['San Francisco', 'New York'] to target specific markets.",
                "Set country_indeed explicitly for non-US Indeed or Glassdoor searches.",
                "Use multiple cities to compare the same role across locations.",
            ],
            "site_selection": [
                "Start with 1-3 sites to keep requests fast and within guardrails.",
                "Indeed is the most reliable baseline source.",
                "LinkedIn often has strong listings but stricter rate limits.",
                "Use regional sources such as naukri, bayt, stepstone, xing, berlin_startup_jobs, welcome_to_the_jungle, eu_startups, or join when geography matters.",
            ],
            "performance": [
                "Start with small result counts such as 5 or 10, then widen if needed.",
                "Use hours_old to focus on recent postings.",
                "Enable linkedin_fetch_description only when full descriptions are required.",
                "Use offset for pagination when iterating through a result set.",
            ],
            "advanced_filtering": [
                "Supported job_type values are fulltime, parttime, internship, and contract.",
                "Set easy_apply=true when you want quick-apply friendly listings.",
                "Combine cities, country_indeed, and is_remote to narrow broad searches.",
            ],
            "common_issues": [
                {
                    "issue": "No results",
                    "guidance": "Try broader search terms, fewer filters, or a different site combination.",
                },
                {
                    "issue": "Rate limiting",
                    "guidance": "Reduce results_wanted, use fewer sites, and avoid repeated LinkedIn-heavy requests.",
                },
                {
                    "issue": "Slow searches",
                    "guidance": "Disable linkedin_fetch_description unless the description is required.",
                },
            ],
            "sample_search_strategies": [
                {
                    "name": "remote_work",
                    "arguments": {
                        "search_term": "software engineer",
                        "is_remote": True,
                        "site_name": ["indeed", "zip_recruiter"],
                    },
                },
                {
                    "name": "local_markets",
                    "arguments": {
                        "search_term": "marketing manager",
                        "cities": ["Austin"],
                        "site_name": ["indeed", "glassdoor"],
                    },
                },
                {
                    "name": "recent_postings",
                    "arguments": {
                        "search_term": "data scientist",
                        "hours_old": 48,
                        "site_name": ["linkedin", "indeed"],
                        "linkedin_fetch_description": True,
                    },
                },
                {
                    "name": "entry_level",
                    "arguments": {
                        "search_term": "junior developer OR entry level programmer",
                        "job_type": "fulltime",
                        "easy_apply": True,
                    },
                },
            ],
            "iterative_search_process": [
                "Start with broad terms and a small site set.",
                "Review the first result set for title and location patterns.",
                "Refine the search term or cities based on those findings.",
                "Expand to additional sites if coverage is still thin.",
            ],
        }
    if output_format == "markdown":
        return render_tips_markdown(tips)
    return _serialize_success_payload(tips=tips)


# Entry point for running the server
def main():
    """Run the JobSpy MCP server.

    Supports multiple transports:
      - stdio (default): for MCP clients like Claude Desktop, Cursor
      - sse: Server-Sent Events over HTTP (legacy HTTP transport)
      - streamable-http: modern MCP HTTP transport
    """
    parser = argparse.ArgumentParser(
        description="JobSpy MCP Server — job scraping as AI-callable tools"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport to use (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind when using sse or streamable-http (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to bind when using sse or streamable-http (default: 8765)",
    )
    args = parser.parse_args()

    logger.info("Starting JobSpy MCP Server...")
    logger.info("Transport: %s", args.transport)
    if args.transport != "stdio":
        logger.info("Listening on http://%s:%d", args.host, args.port)
    else:
        logger.info("Server is ready and waiting for MCP client connections...")
    logger.info("Use Ctrl+C to stop the server")

    try:
        if args.transport == "stdio":
            mcp.run(transport="stdio")
        else:
            mcp.run(
                transport=args.transport,
                host=args.host,
                port=args.port,
            )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")


if __name__ == "__main__":
    main()
