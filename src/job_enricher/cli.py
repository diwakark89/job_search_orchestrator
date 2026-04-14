from __future__ import annotations

import typer
from rich import print

from common.client import PostgrestClient
from common.config import load_config
from repository.supabase import SupabaseRepository
from service.enricher import EnrichmentSummary, enrich_jobs

from .client_copilot import CopilotClient
from .config import load_copilot_config

app = typer.Typer(help="Job enrichment pipeline powered by Copilot SDK.")


def _print_summary(summary: EnrichmentSummary, dry_run: bool) -> None:
    mode = "DRY-RUN" if dry_run else "WRITE"
    print(
        f"[cyan]mode={mode} processed={summary.processed.count} enriched={summary.enriched.count} "
        f"skipped={summary.skipped.count} failed={summary.failed.count}[/cyan]"
    )
    for error in summary.errors[:20]:
        print(f"[red]{error}[/red]")


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
