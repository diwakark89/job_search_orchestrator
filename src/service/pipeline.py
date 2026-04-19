"""Pipeline orchestrator.

Sequences ingest → enrich and aggregates a ``PipelineResult``. All concrete
stage logic lives in focused sibling modules: ``service.submit``,
``service.stages.ingest``, ``service.stages.enrich``.

Public symbols are re-exported so existing callers (API routes, CLI, tests)
continue to work unchanged.
"""
from __future__ import annotations

from typing import Any

from job_enricher.client_copilot import CopilotClient
from pipeline.models import PipelineResult, StageResult
from repository.supabase import SupabaseRepository

from .stages.enrich import run_stage_enriched, run_stage_enriched_detailed
from .stages.ingest import run_stage_ingest
from .submit import submit_jobs_for_enrichment


def run_pipeline(
    repo: SupabaseRepository,
    copilot_client: CopilotClient,
    rows: list[dict[str, Any]],
    limit: int = 50,
    dry_run: bool = False,
) -> PipelineResult:
    stages: list[StageResult] = []

    # Stage 1: ingest → jobs_final (SCRAPED)
    ingest_result = run_stage_ingest(repo=repo, rows=rows)
    stages.append(ingest_result)

    if not ingest_result.success:
        return PipelineResult(
            stages=stages,
            success=False,
            total_processed=ingest_result.processed,
            total_enriched=0,
            total_failed=len(rows) - ingest_result.processed,
        )

    # Stage 2: enrich SCRAPED → ENRICHED in jobs_final
    enriched_result = run_stage_enriched(
        repo=repo,
        copilot_client=copilot_client,
        limit=limit,
        dry_run=dry_run,
    )
    stages.append(enriched_result)

    all_errors = sum(len(s.errors) for s in stages)
    overall_success = all(s.success for s in stages)

    return PipelineResult(
        stages=stages,
        success=overall_success,
        total_processed=ingest_result.processed,
        total_enriched=enriched_result.processed,
        total_failed=all_errors,
    )


__all__ = [
    "run_pipeline",
    "run_stage_enriched",
    "run_stage_enriched_detailed",
    "run_stage_ingest",
    "submit_jobs_for_enrichment",
]