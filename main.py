from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "src"))

import typer

from job_enricher.cli import app as enricher_app
from pipeline.cli import app as pipeline_app
from common.cli import app as db_app
from scraping.cli import cmd_search
from scraping.guardrails import FETCH_DESCRIPTIONS_DEFAULT

app = typer.Typer(help="Automated Job Hunt orchestration CLI.")
job_manage_app = typer.Typer(help="Unified job management CLI for table, pipeline, and enricher operations.")
job_manage_app.add_typer(db_app, name="table")
job_manage_app.add_typer(pipeline_app, name="pipeline")
job_manage_app.add_typer(enricher_app, name="enricher")
app.add_typer(job_manage_app, name="job-manage")


@app.command("job-search")
def job_search(
    search_term: str | None = typer.Argument(None, help="Job search keywords."),
    cities: str | None = typer.Option(None, "--cities", help="Comma-separated list of cities to search."),
    country: str | None = typer.Option(None, "--country", help="Country for Indeed and Glassdoor searches."),
    sites: str = typer.Option("linkedin", "--sites", help="Comma-separated list of job boards to search."),
    results: int = typer.Option(1, "--results", min=1, help="Maximum jobs wanted per request before guardrail clamping."),
    job_type: str | None = typer.Option(None, "--job-type", help="Employment type filter."),
    work_mode: str | None = typer.Option(None, "--work-mode", help="Work mode filter."),
    remote_filter: str = typer.Option("auto", "--remote-filter", help="Remote filter strategy: auto, remote, or all."),
    hours_old: int = typer.Option(24, "--hours-old", help="Only return jobs posted within the last N hours."),
    easy_apply: bool = typer.Option(False, "--easy-apply", help="Filter for easy-apply jobs."),
    fetch_descriptions: bool = typer.Option(
        FETCH_DESCRIPTIONS_DEFAULT,
        "--fetch-descriptions/--no-fetch-descriptions",
        help="Fetch full job descriptions when supported by the source.",
    ),
    output_format: str = typer.Option("json", "--output-format", help="Response format: json or markdown."),
) -> None:
    """Search jobs across supported sites."""
    cmd_search(
        search_term=search_term,
        cities=cities,
        country=country,
        sites=sites,
        results=results,
        job_type=job_type,
        work_mode=work_mode,
        remote_filter=remote_filter,
        hours_old=hours_old,
        easy_apply=easy_apply,
        fetch_descriptions=fetch_descriptions,
        output_format=output_format,
    )

if __name__ == "__main__":
    app()
