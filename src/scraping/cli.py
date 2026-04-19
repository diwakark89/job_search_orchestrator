from __future__ import annotations

import typer

from .guardrails import (
    FETCH_DESCRIPTIONS_DEFAULT,
    HOURS_OLD_DEFAULT,
    RESULTS_WANTED_DEFAULT,
    SITES_DEFAULT,
)
from .service import JobSearchRequest, render_search_error, render_search_result, search_jobs

app = typer.Typer(help="Multi-site job scraping workflows and MCP-compatible search output.")


def _parse_csv_values(raw_value: str | None) -> list[str] | None:
    if raw_value is None:
        return None
    values = [item.strip() for item in raw_value.split(",") if item.strip()]
    return values or None


@app.command("search")
def cmd_search(
    search_term: str | None = typer.Argument(None, help="Job search keywords."),
    cities: str | None = typer.Option(None, "--cities", help="Comma-separated list of cities to search."),
    country: str | None = typer.Option(None, "--country", help="Country for Indeed and Glassdoor searches."),
    sites: str = typer.Option(
        ",".join(SITES_DEFAULT),
        "--sites",
        help="Comma-separated list of job boards to search.",
    ),
    results: int = typer.Option(
        RESULTS_WANTED_DEFAULT,
        "--results",
        min=1,
        help="Maximum jobs wanted per request before guardrail clamping.",
    ),
    job_type: str | None = typer.Option(None, "--job-type", help="Employment type filter."),
    work_mode: str | None = typer.Option(None, "--work-mode", help="Work mode filter."),
    remote_filter: str = typer.Option(
        "auto",
        "--remote-filter",
        help="Remote filter strategy: auto, remote, or all.",
    ),
    hours_old: int = typer.Option(
        HOURS_OLD_DEFAULT,
        "--hours-old",
        help="Only return jobs posted within the last N hours.",
    ),
    easy_apply: bool = typer.Option(False, "--easy-apply", help="Filter for easy-apply jobs."),
    fetch_descriptions: bool = typer.Option(
        FETCH_DESCRIPTIONS_DEFAULT,
        "--fetch-descriptions/--no-fetch-descriptions",
        help="Fetch full job descriptions when supported by the source.",
    ),
    output_format: str = typer.Option(
        "json",
        "--output-format",
        help="Response format: json or markdown.",
    ),
) -> None:
    resolved_remote: bool | None
    normalized_remote_filter = remote_filter.strip().lower()
    if normalized_remote_filter == "auto":
        resolved_remote = None
    elif normalized_remote_filter == "remote":
        resolved_remote = True
    elif normalized_remote_filter == "all":
        resolved_remote = False
    else:
        typer.echo(
            render_search_error(
                "validation_error",
                "Invalid --remote-filter value. Use one of: auto, remote, all.",
                output_format=output_format,
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    try:
        result = search_jobs(JobSearchRequest(
            search_term=search_term,
            cities=_parse_csv_values(cities),
            site_name=_parse_csv_values(sites),
            results_wanted=results,
            job_type=job_type,
            work_mode=work_mode,
            is_remote=resolved_remote,
            hours_old=hours_old,
            easy_apply=easy_apply,
            country_indeed=country,
            linkedin_fetch_description=fetch_descriptions,
        ))
        typer.echo(render_search_result(result, output_format=output_format, indent=2))
    except ValueError as exc:
        typer.echo(
            render_search_error(
                "validation_error",
                str(exc),
                output_format=output_format,
                indent=2,
            )
        )
        raise typer.Exit(code=1) from exc
    except RuntimeError as exc:
        typer.echo(
            render_search_error(
                "runtime_error",
                str(exc),
                output_format=output_format,
                indent=2,
            )
        )
        raise typer.Exit(code=1) from exc
