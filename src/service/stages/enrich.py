"""Enrich stage: delegate to ``service.enricher.enrich_jobs`` and wrap the
result as a ``StageResult``. ``run_stage_enriched_detailed`` returns the full
``EnrichmentSummary`` for callers (API routes) that need richer output.
"""
from __future__ import annotations

from job_enricher.client_copilot import CopilotClient
from pipeline.models import StageResult
from repository.supabase import SupabaseRepository

from ..enricher import EnrichmentSummary, enrich_jobs


def run_stage_enriched(
    repo: SupabaseRepository,
    copilot_client: CopilotClient,
    limit: int,
    dry_run: bool = False,
) -> StageResult:
    try:
        summary = enrich_jobs(
            repo=repo,
            copilot_client=copilot_client,
            limit=limit,
            dry_run=dry_run,
        )
    except RuntimeError as exc:
        return StageResult(stage="enrich", success=False, processed=0, errors=[str(exc)])

    return StageResult(
        stage="enrich",
        success=True,
        processed=summary.enriched.count,
        errors=summary.errors,
    )


def run_stage_enriched_detailed(
    repo: SupabaseRepository,
    copilot_client: CopilotClient,
    limit: int,
    dry_run: bool = False,
) -> EnrichmentSummary:
    return enrich_jobs(
        repo=repo,
        copilot_client=copilot_client,
        limit=limit,
        dry_run=dry_run,
    )


__all__ = ["run_stage_enriched", "run_stage_enriched_detailed"]
