from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from common.validators import JobsRawRow, normalize_timestamp_fields
from job_enricher.client_copilot import CopilotClient
from repository.supabase import SupabaseRepository

from pipeline.models import PipelineResult, StageResult

from .enricher import enrich_jobs
from .tables import patch_job_metrics, upsert_jobs_raw

_RAW_TIMESTAMP_FIELDS = ("created_at", "modified_at")


def run_stage_raw(repo: SupabaseRepository, rows: list[dict[str, Any]]) -> StageResult:
    valid_rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for idx, row in enumerate(rows):
        try:
            validated = JobsRawRow.model_validate(row)
            normalised = normalize_timestamp_fields(
                validated.model_dump(exclude_none=True), _RAW_TIMESTAMP_FIELDS
            )
            valid_rows.append(normalised)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"row[{idx}]: {exc}")

    if not valid_rows:
        return StageResult(stage="jobs_raw", success=False, processed=0, errors=errors)

    result = upsert_jobs_raw(repo=repo, rows=valid_rows)
    if not result.success:
        errors.append(result.error or "upsert_jobs_raw failed")
        return StageResult(stage="jobs_raw", success=False, processed=0, errors=errors)

    return StageResult(stage="jobs_raw", success=True, processed=len(valid_rows), errors=errors)


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
        return StageResult(stage="jobs_enriched", success=False, processed=0, errors=[str(exc)])

    return StageResult(
        stage="jobs_enriched",
        success=True,
        processed=summary.enriched,
        errors=summary.errors,
    )


def run_stage_metrics(
    repo: SupabaseRepository,
    scraped_count: int = 0,
) -> StageResult:
    now_iso = datetime.now(tz=UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    payload: dict[str, Any] = {"updated_at": now_iso}
    if scraped_count > 0:
        payload["total_scraped"] = scraped_count

    result = patch_job_metrics(repo=repo, payload=payload)
    if not result.success:
        return StageResult(
            stage="job_metrics",
            success=False,
            processed=0,
            errors=[result.error or "patch_job_metrics failed"],
        )

    return StageResult(stage="job_metrics", success=True, processed=1, errors=[])


def run_pipeline(
    repo: SupabaseRepository,
    copilot_client: CopilotClient,
    rows: list[dict[str, Any]],
    limit: int = 50,
    dry_run: bool = False,
) -> PipelineResult:
    stages: list[StageResult] = []

    # Stage 1: jobs_raw
    raw_result = run_stage_raw(repo=repo, rows=rows)
    stages.append(raw_result)

    if not raw_result.success:
        return PipelineResult(
            stages=stages,
            success=False,
            total_processed=raw_result.processed,
            total_enriched=0,
            total_failed=len(rows) - raw_result.processed,
        )

    # Stage 2: jobs_enriched
    enriched_result = run_stage_enriched(
        repo=repo,
        copilot_client=copilot_client,
        limit=limit,
        dry_run=dry_run,
    )
    stages.append(enriched_result)

    # Stage 3: job_metrics
    if not dry_run:
        metrics_result = run_stage_metrics(
            repo=repo,
            scraped_count=raw_result.processed,
        )
        stages.append(metrics_result)

    all_errors = sum(len(s.errors) for s in stages)
    overall_success = all(s.success for s in stages)

    return PipelineResult(
        stages=stages,
        success=overall_success,
        total_processed=raw_result.processed,
        total_enriched=enriched_result.processed,
        total_failed=all_errors,
    )
