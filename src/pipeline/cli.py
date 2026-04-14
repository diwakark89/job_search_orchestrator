from __future__ import annotations

import json
from pathlib import Path

import typer
from rich import print

from common.client import PostgrestClient
from common.config import load_config
from job_enricher.client_copilot import CopilotClient
from job_enricher.config import load_copilot_config
from repository.supabase import SupabaseRepository
from service.pipeline import run_pipeline, run_stage_enriched, run_stage_ingest

from .models import PipelineResult, StageResult

app = typer.Typer(help="Pipeline runner: ingest → enrich (all in jobs_final).")


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
