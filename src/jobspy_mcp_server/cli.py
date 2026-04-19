#!/usr/bin/env python3
"""
Standalone CLI for JobSpy job search.

Provides a direct command-line interface for searching jobs without MCP protocol
overhead. Designed to be called by OpenClaw's exec tool or any shell.

Usage:
    jobspy-search "software engineer" --cities Munich,Berlin --country Germany --sites linkedin,indeed
    jobspy-search "data scientist" --remote --results 5 --hours-old 48
"""

import argparse
import sys

from jobspy_mcp_server.json_output import (
    build_error_envelope,
    build_jobs_json_payload,
    build_jobs_success_envelope,
    serialize_json_payload,
)
from jobspy_mcp_server.jobspy_scrapers import scrape_jobs
from jobspy_mcp_server.preferences import derive_runtime_defaults, load_search_preferences
from jobspy_mcp_server.guardrails import (
    FETCH_DESCRIPTIONS_DEFAULT,
    RESULTS_WANTED_DEFAULT,
    RESULTS_WANTED_MAX,
    RESULTS_WANTED_MIN,
    WORK_MODES,
)

VALID_SITES = [
    "linkedin", "indeed", "glassdoor", "zip_recruiter",
    "google", "bayt", "naukri", "stepstone", "xing",
    "berlin_startup_jobs", "welcome_to_the_jungle", "eu_startups", "join",
]


def _print_json(payload: object, exit_code: int) -> None:
    print(serialize_json_payload(payload, indent=2))
    sys.exit(exit_code)


def _print_success_envelope(
    jobs: list[dict],
    exit_code: int = 0,
    site_errors: list[dict] | None = None,
) -> None:
    _print_json(build_jobs_success_envelope(jobs, site_errors=site_errors), exit_code)


def _print_error_envelope(code: str, message: str, exit_code: int = 1) -> None:
    _print_json(build_error_envelope(code, message, jobs=[]), exit_code)


def main() -> None:
    """Entry point for the jobspy-search CLI."""
    parser = argparse.ArgumentParser(
        prog="jobspy-search",
        description="Search for jobs across multiple job boards",
    )
    parser.add_argument(
        "search_term",
        nargs="?",
        default=None,
        help="Job search keywords (e.g. 'software engineer', 'data scientist')",
    )
    parser.add_argument(
        "--cities",
        default=None,
        help="Comma-separated list of cities to search (e.g. 'Munich,Berlin,Darmstadt'). "
             "If specified, search is limited to these cities only.",
    )
    parser.add_argument(
        "--country",
        default=None,
        help="Country for job search (default from preferences; fallback: usa). "
             "Examples: Germany, USA, UK, Canada, India",
    )
    parser.add_argument(
        "--sites",
        default="linkedin",
        help="Comma-separated list of job boards (default: linkedin). "
        f"Valid: {', '.join(VALID_SITES)}",
    )
    parser.add_argument(
        "--results",
        type=int,
        default=RESULTS_WANTED_DEFAULT,
        help=(
            "Number of results "
            f"({RESULTS_WANTED_MIN}-{RESULTS_WANTED_MAX}, default: {RESULTS_WANTED_DEFAULT})"
        ),
    )
    parser.add_argument(
        "--job-type",
        default=None,
        choices=["fulltime", "parttime", "internship", "contract"],
        help="Type of employment",
    )
    parser.add_argument(
        "--work-mode",
        default=None,
        choices=WORK_MODES,
        help="Work mode filter: remote, hybrid, or on-site",
    )
    remote_group = parser.add_mutually_exclusive_group()
    remote_group.add_argument(
        "--remote",
        dest="remote",
        action="store_true",
        default=None,
        help="Filter for remote jobs only",
    )
    remote_group.add_argument(
        "--no-remote",
        dest="remote",
        action="store_false",
        help="Disable remote-only filtering even if preferences default to remote",
    )
    parser.add_argument(
        "--preferences-file",
        default=None,
        help="Path to resume preferences YAML (default: resume.yaml or assets/resume.yaml)",
    )
    parser.add_argument(
        "--min-salary-eur",
        type=int,
        default=None,
        help="Optional minimum salary filter in EUR (0 disables, default from preferences)",
    )
    parser.add_argument(
        "--seniority",
        default=None,
        choices=["Junior", "Mid", "Senior", "Lead"],
        help="Optional seniority keyword filter",
    )
    parser.add_argument(
        "--hours-old",
        type=int,
        default=24,
        help="Only jobs posted within last N hours (1-72, default: 24)",
    )
    parser.add_argument(
        "--no-fetch-descriptions",
        dest="fetch_descriptions",
        action="store_false",
        default=FETCH_DESCRIPTIONS_DEFAULT,
        help="Disable fetching full job descriptions when supported by the site",
    )
    args = parser.parse_args()

    preferences = load_search_preferences(args.preferences_file)
    runtime_defaults = derive_runtime_defaults(preferences)

    effective_search_term = args.search_term or runtime_defaults.default_search_term
    if not effective_search_term:
        _print_error_envelope(
            "validation_error",
            "search_term is required when no preferred roles are configured.",
        )

    # Parse cities from comma-separated list
    effective_cities: list[str] = []
    if args.cities:
        effective_cities = [city.strip() for city in args.cities.split(",") if city.strip()]
    elif runtime_defaults.default_cities:
        effective_cities = runtime_defaults.default_cities
    
    effective_country = args.country or runtime_defaults.default_country_indeed
    effective_remote = args.remote if args.remote is not None else runtime_defaults.prefer_remote

    # Parse and validate sites
    site_list = [s.strip() for s in args.sites.split(",") if s.strip()]
    invalid = [s for s in site_list if s not in VALID_SITES]
    if invalid:
        _print_error_envelope("validation_error", f"Invalid sites: {invalid}. Valid: {VALID_SITES}")
    if not site_list:
        _print_error_envelope("validation_error", "At least 1 site must be specified.")
    if len(site_list) > 3:
        _print_error_envelope("validation_error", f"Maximum 3 sites per request, got {len(site_list)}.")

    # Clamp numeric parameters to safe ranges
    results_wanted = min(max(args.results, RESULTS_WANTED_MIN), RESULTS_WANTED_MAX)
    hours_old = min(max(args.hours_old, 1), 72)

    try:
        jobs_df = scrape_jobs(
            site_name=site_list,
            search_term=effective_search_term,
            cities=effective_cities,
            results_wanted=results_wanted,
            job_type=args.job_type,
            work_mode=args.work_mode,
            is_remote=effective_remote,
            hours_old=hours_old,
            country_indeed=effective_country,
            linkedin_fetch_description=args.fetch_descriptions,
            verbose=0,
            description_format="markdown",
        )
    except Exception as e:
        _print_error_envelope("runtime_error", f"Job search failed: {e}")

    site_errors = jobs_df.attrs.get("site_errors") if hasattr(jobs_df, "attrs") else None

    if jobs_df.empty:
        _print_success_envelope([], 0, site_errors=site_errors)

    jobs_list = build_jobs_json_payload(jobs_df)
    _print_success_envelope(jobs_list, 0, site_errors=site_errors)


if __name__ == "__main__":
    main()
