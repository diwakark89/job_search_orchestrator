from __future__ import annotations

import json
from pathlib import Path

import typer
from rich import print

from common.client import PostgrestClient
from common.config import load_config
from repository.supabase import SupabaseRepository
from service.enricher import EnrichmentSummary, enrich_jobs, enrich_jobs_by_ids

from .client_copilot import CopilotClient
from .config import load_copilot_config

app = typer.Typer(help="Job enrichment pipeline powered by Copilot SDK.")


def _print_summary(summary: EnrichmentSummary, dry_run: bool) -> None:
    mode = "DRY-RUN" if dry_run else "WRITE"
    print(
        f"[cyan]mode={mode} processed={summary.processed.count} enriched={summary.enriched.count} "
        f"skipped={summary.skipped.count} failed={summary.failed.count} "
        f"copilot_batches_sent={summary.copilot_batches_sent} "
        f"database_batches_sent={summary.database_batches_sent} "
        f"database_rows_reported={summary.database_rows_reported}[/cyan]"
    )
    for error in summary.errors[:20]:
        print(f"[red]{error}[/red]")


def _parse_ids(ids: str | None, ids_file: Path | None) -> list[str]:
    if bool(ids) == bool(ids_file):
        raise typer.BadParameter("Provide exactly one of --ids or --ids-file.")

    if ids:
        raw_ids = [item.strip() for item in ids.split(",")]
    else:
        assert ids_file is not None
        data = json.loads(ids_file.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise typer.BadParameter("--ids-file must contain a JSON array of id strings.")
        raw_ids = [str(item).strip() for item in data]

    parsed = [item for item in raw_ids if item]
    if not parsed:
        raise typer.BadParameter("At least one id is required.")
    return parsed


@app.command("enrich")
def cmd_enrich(
    limit: int = typer.Option(50, "--limit", min=1, help="Maximum number of SCRAPED jobs_raw rows to inspect."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run extraction without database writes."),
) -> None:
    repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
    copilot_client = CopilotClient(config=load_copilot_config())
    summary = enrich_jobs(
        repo=repo,
        copilot_client=copilot_client,
        limit=limit,
        dry_run=dry_run,
    )
    _print_summary(summary=summary, dry_run=dry_run)


@app.command("by-ids")
def cmd_enrich_by_ids(
    ids: str | None = typer.Option(None, "--ids", help="Comma-separated list of jobs_final ids."),
    ids_file: Path | None = typer.Option(None, "--ids-file", help="Path to JSON array of jobs_final ids."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run extraction without database writes."),
) -> None:
    repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
    copilot_client = CopilotClient(config=load_copilot_config())
    parsed_ids = _parse_ids(ids=ids, ids_file=ids_file)
    summary = enrich_jobs_by_ids(
        repo=repo,
        copilot_client=copilot_client,
        ids=parsed_ids,
        dry_run=dry_run,
    )
    _print_summary(summary=summary, dry_run=dry_run)
