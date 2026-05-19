from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import typer
from rich import print

from common.client import PostgrestClient
from common.config import load_config
from job_enricher.client_copilot import CopilotClient
from job_enricher.config import load_copilot_config
from repository.supabase import SupabaseRepository
from scraping.service import JobSearchRequest, search_jobs
from service.pipeline import run_pipeline, run_stage_enriched, run_stage_ingest, submit_jobs_for_enrichment
from service.tables import get_metrics

from .models import PipelineResult, StageResult

app = typer.Typer(help="Pipeline runner: ingest → enrich (all in jobs_final).")


def _new_run_id() -> str:
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"daily-{timestamp}-{uuid4().hex[:8]}"


def _print_stage(result: StageResult) -> None:
    colour = "green" if result.success else "red"
    print(f"[{colour}]stage={result.stage} success={result.success} processed={result.processed}[/{colour}]")
    for error in result.errors[:20]:
        print(f"  [red]{error}[/red]")


def _print_pipeline(result: PipelineResult) -> None:
    for stage in result.stages:
        _print_stage(stage)
    colour = "green" if result.success else "red"
    print(
        f"[{colour}]pipeline success={result.success} "
        f"processed={result.total_processed} enriched={result.total_enriched} "
        f"failed={result.total_failed}[/{colour}]"
    )


def _load_rows(file: Path) -> list[dict]:
    data = json.loads(file.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise typer.BadParameter(f"Expected JSON array or object, got {type(data).__name__}")
    return data


def _load_submit_rows(file: Path) -> list[dict[str, Any]]:
    data = json.loads(file.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        jobs = data.get("jobs")
        if isinstance(jobs, list):
            return jobs
        return [data]
    if isinstance(data, list):
        return data
    raise typer.BadParameter(f"Expected JSON array or object, got {type(data).__name__}")


@app.command("run")
def cmd_run(
    file: Path = typer.Argument(..., help="JSON file containing raw job rows (array or single object)."),
    limit: int = typer.Option(50, "--limit", min=1, help="Max SCRAPED rows to enrich."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run without database writes for enrichment."),
) -> None:
    """Run the full pipeline: ingest → enrich (all in jobs_final)."""
    rows = _load_rows(file)
    repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
    copilot_client = CopilotClient(config=load_copilot_config())
    result = run_pipeline(
        repo=repo,
        copilot_client=copilot_client,
        rows=rows,
        limit=limit,
        dry_run=dry_run,
    )
    _print_pipeline(result)


@app.command("stage-ingest")
def cmd_stage_ingest(
    file: Path = typer.Argument(..., help="JSON file containing raw job rows."),
) -> None:
    """Run Stage 1 only: ingest rows into jobs_final with status SCRAPED."""
    rows = _load_rows(file)
    repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
    result = run_stage_ingest(repo=repo, rows=rows)
    _print_stage(result)


@app.command("stage-enriched")
def cmd_stage_enriched(
    limit: int = typer.Option(50, "--limit", min=1, help="Max SCRAPED rows to enrich."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run extraction without database writes."),
) -> None:
    """Run Stage 2 only: enrich SCRAPED rows in jobs_final."""
    repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
    copilot_client = CopilotClient(config=load_copilot_config())
    result = run_stage_enriched(
        repo=repo,
        copilot_client=copilot_client,
        limit=limit,
        dry_run=dry_run,
    )
    _print_stage(result)


@app.command("submit")
def cmd_submit(
    file: Path = typer.Argument(..., help="JSON file with job rows (array or {\"jobs\": [...] })."),
) -> None:
    """Submit jobs for ingest and queue metadata for follow-up enrichment workflows."""
    rows = _load_submit_rows(file)
    repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
    result = submit_jobs_for_enrichment(repo=repo, rows=rows)
    payload = {
        "submitted_row_count": result.submitted_row_count,
        "accepted": {"count": len(result.accepted_ids), "ids": result.accepted_ids},
        "queued": {"count": len(result.accepted_ids), "ids": result.accepted_ids},
        "rejected_row_indexes": result.rejected_row_indexes,
        "errors": result.errors,
        "jobs_final_row_count": result.jobs_final_row_count,
    }
    print(json.dumps(payload, indent=2, default=str))


@app.command("metrics")
def cmd_metrics() -> None:
    """Show current pipeline status counts from jobs_final."""
    repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
    metrics = get_metrics(repo=repo)
    print(json.dumps(metrics, indent=2, default=str))


@app.command("daily-submit")
def cmd_daily_submit(
    search_term: str = typer.Option(..., "--search-term", help="Job search keywords."),
    cities: str | None = typer.Option(None, "--cities", help="Comma-separated city list."),
    country: str | None = typer.Option(None, "--country", help="Country override for search sources."),
    sites: str = typer.Option("linkedin", "--sites", help="Comma-separated site list."),
    requested_results: int = typer.Option(
        20,
        "--requested-results",
        min=1,
        help="Requested scrape size before daily cap is applied.",
    ),
    daily_cap: int = typer.Option(
        10,
        "--daily-cap",
        min=1,
        max=50,
        help="Maximum jobs submitted in one daily run.",
    ),
    hours_old: int = typer.Option(24, "--hours-old", help="Only return jobs posted within the last N hours."),
    easy_apply: bool = typer.Option(False, "--easy-apply", help="Filter for easy-apply jobs."),
) -> None:
    """Run daily scrape and submit accepted rows for enrichment with a hard cap."""

    site_values = [item.strip() for item in sites.split(",") if item.strip()]
    city_values = [item.strip() for item in cities.split(",") if item.strip()] if cities else None
    run_id = _new_run_id()

    scrape_result = search_jobs(
        JobSearchRequest(
            search_term=search_term,
            cities=city_values,
            site_name=site_values,
            results_wanted=requested_results,
            hours_old=hours_old,
            easy_apply=easy_apply,
            country_indeed=country,
        )
    )

    scraped_jobs = scrape_result.jobs
    capped_jobs = scraped_jobs[:daily_cap]

    repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
    submit_result = submit_jobs_for_enrichment(repo=repo, rows=capped_jobs)

    payload = {
        "run_id": run_id,
        "search_term": scrape_result.search_term,
        "scraped_count": len(scraped_jobs),
        "submitted_count": len(capped_jobs),
        "daily_cap": daily_cap,
        "accepted": {"count": len(submit_result.accepted_ids), "ids": submit_result.accepted_ids},
        "queued": {"count": len(submit_result.accepted_ids), "ids": submit_result.accepted_ids},
        "rejected_row_indexes": submit_result.rejected_row_indexes,
        "errors": submit_result.errors,
        "jobs_final_row_count": submit_result.jobs_final_row_count,
        "site_errors": scrape_result.site_errors or [],
    }
    print(json.dumps(payload, indent=2, default=str))
