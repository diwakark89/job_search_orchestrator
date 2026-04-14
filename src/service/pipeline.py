from __future__ import annotations

from typing import Any

from common.validators import JobsFinalRow, normalize_timestamp_fields
from job_enricher.client_copilot import CopilotClient
from repository.supabase import SupabaseRepository

from pipeline.models import PipelineResult, StageResult

from .enricher import EnrichmentSummary, enrich_jobs
from .tables import upsert_jobs_final

_INGEST_TIMESTAMP_FIELDS = ("created_at", "modified_at")


def run_stage_ingest(repo: SupabaseRepository, rows: list[dict[str, Any]]) -> StageResult:
    valid_rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for idx, row in enumerate(rows):
        try:
            if "job_status" not in row:
                row["job_status"] = "SCRAPED"
            validated = JobsFinalRow.model_validate(row)
            normalised = normalize_timestamp_fields(
                validated.model_dump(exclude_none=True), _INGEST_TIMESTAMP_FIELDS
            )
            valid_rows.append(normalised)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"row[{idx}]: {exc}")

    if not valid_rows:
        return StageResult(stage="ingest", success=False, processed=0, errors=errors)

    result = repo.upsert_rows(table="jobs_final", rows=valid_rows, on_conflict="job_url")
    if not result.success:
        errors.append(result.error or "upsert jobs_final (ingest) failed")
        return StageResult(stage="ingest", success=False, processed=0, errors=errors)

    return StageResult(stage="ingest", success=True, processed=len(valid_rows), errors=errors)


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
