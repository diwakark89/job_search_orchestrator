from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from common.validators import JobsRawRow, normalize_timestamp_fields
from job_enricher.client_copilot import CopilotClient
from repository.supabase import SupabaseRepository

from pipeline.models import PipelineResult, StageResult

from .enricher import EnrichmentSummary, enrich_jobs
from .tables import patch_job_metrics, upsert_jobs_final, upsert_jobs_raw

_RAW_TIMESTAMP_FIELDS = ("created_at", "modified_at")


@dataclass
class BucketCount:
    count: int
    ids: list[str]


@dataclass
class FinalizeSummary:
    processed: BucketCount
    enriched: BucketCount
    skipped: BucketCount
    failed: BucketCount
    errors: list[str]


def _fetch_persisted_final_ids(repo: SupabaseRepository, job_ids: list[str]) -> set[str]:
    if not job_ids:
        return set()

    in_filter = "(" + ",".join(job_ids) + ")"
    result = repo.client.select(
        table="jobs_final",
        columns="job_id",
        filters={"job_id": in_filter},
        operator="in",
    )
    if not result.success or not isinstance(result.data, list):
        raise RuntimeError(result.error or "Failed to verify persisted jobs_final rows.")

    return {str(row.get("job_id")) for row in result.data if row.get("job_id")}


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


def run_stage_finalize_detailed(
    repo: SupabaseRepository,
    limit: int = 50,
    dry_run: bool = False,
) -> FinalizeSummary:
    selection = repo.select_rows(
        table="jobs_raw",
        columns="id,company_name,role_title,job_url,description,language,job_status,is_deleted",
        filters={"job_status": "ENRICHED", "is_deleted": False},
        limit=limit,
        order_by="created_at",
        ascending=True,
    )
    if not selection.success or not isinstance(selection.data, list):
        return FinalizeSummary(
            processed=BucketCount(count=0, ids=[]),
            enriched=BucketCount(count=0, ids=[]),
            skipped=BucketCount(count=0, ids=[]),
            failed=BucketCount(count=0, ids=[]),
            errors=[selection.error or "Failed to fetch ENRICHED rows from jobs_raw"],
        )

    final_rows: list[dict[str, Any]] = []
    processed_ids: list[str] = []
    skipped_ids: list[str] = []
    failed_ids: list[str] = []
    enriched_ids: list[str] = []
    errors: list[str] = []

    for row in selection.data:
        row_id = row.get("id")
        if not row_id:
            errors.append("jobs_raw row missing id; cannot map to jobs_final.job_id")
            skipped_ids.append("missing-id")
            continue

        row_id_text = str(row_id)
        processed_ids.append(row_id_text)

        final_rows.append(
            {
                "job_id": row_id_text,
                "company_name": row.get("company_name"),
                "role_title": row.get("role_title"),
                "job_url": row.get("job_url"),
                "description": row.get("description"),
                "language": row.get("language") or "English",
                # jobs_final only supports display/legacy status values such as Saved/Applied.
                "job_status": "Saved",
            }
        )

    if not final_rows:
        return FinalizeSummary(
            processed=BucketCount(count=len(processed_ids), ids=processed_ids),
            enriched=BucketCount(count=0, ids=[]),
            skipped=BucketCount(count=len(skipped_ids), ids=skipped_ids),
            failed=BucketCount(count=0, ids=[]),
            errors=errors or ["No ENRICHED rows found"],
        )

    if dry_run:
        return FinalizeSummary(
            processed=BucketCount(count=len(processed_ids), ids=processed_ids),
            enriched=BucketCount(count=len(processed_ids), ids=processed_ids),
            skipped=BucketCount(count=len(skipped_ids), ids=skipped_ids),
            failed=BucketCount(count=0, ids=[]),
            errors=errors,
        )

    upsert_result = upsert_jobs_final(repo=repo, rows=final_rows)
    if not upsert_result.success:
        failed_ids = list(processed_ids)
        return FinalizeSummary(
            processed=BucketCount(count=len(processed_ids), ids=processed_ids),
            enriched=BucketCount(count=0, ids=[]),
            skipped=BucketCount(count=len(skipped_ids), ids=skipped_ids),
            failed=BucketCount(count=len(failed_ids), ids=failed_ids),
            errors=errors + [upsert_result.error or "upsert_jobs_final failed"],
        )

    try:
        persisted_ids = _fetch_persisted_final_ids(repo=repo, job_ids=processed_ids)
    except RuntimeError as exc:
        failed_ids = list(processed_ids)
        return FinalizeSummary(
            processed=BucketCount(count=len(processed_ids), ids=processed_ids),
            enriched=BucketCount(count=0, ids=[]),
            skipped=BucketCount(count=len(skipped_ids), ids=skipped_ids),
            failed=BucketCount(count=len(failed_ids), ids=failed_ids),
            errors=errors + [str(exc)],
        )

    missing_ids = [row_id for row_id in processed_ids if row_id not in persisted_ids]
    if missing_ids:
        return FinalizeSummary(
            processed=BucketCount(count=len(processed_ids), ids=processed_ids),
            enriched=BucketCount(count=len(processed_ids) - len(missing_ids), ids=[rid for rid in processed_ids if rid in persisted_ids]),
            skipped=BucketCount(count=len(skipped_ids), ids=skipped_ids),
            failed=BucketCount(count=len(missing_ids), ids=missing_ids),
            errors=errors
            + [
                "Upsert returned success, but rows were not found in jobs_final for ids: "
                + ", ".join(missing_ids)
            ],
        )

    # Mark successfully finalized rows in jobs_raw so they are not re-processed as ENRICHED.
    status_update_failures: list[str] = []
    for row_id in processed_ids:
        patch_result = repo.patch_rows(
            table="jobs_raw",
            payload={"job_status": "Saved"},
            filters={"id": row_id},
        )
        if not patch_result.success:
            status_update_failures.append(row_id)

    if status_update_failures:
        return FinalizeSummary(
            processed=BucketCount(count=len(processed_ids), ids=processed_ids),
            enriched=BucketCount(
                count=len(processed_ids) - len(status_update_failures),
                ids=[rid for rid in processed_ids if rid not in status_update_failures],
            ),
            skipped=BucketCount(count=len(skipped_ids), ids=skipped_ids),
            failed=BucketCount(count=len(status_update_failures), ids=status_update_failures),
            errors=errors
            + [
                "Moved to jobs_final but failed to set jobs_raw.job_status=Saved for ids: "
                + ", ".join(status_update_failures)
            ],
        )

    enriched_ids = list(processed_ids)
    return FinalizeSummary(
        processed=BucketCount(count=len(processed_ids), ids=processed_ids),
        enriched=BucketCount(count=len(enriched_ids), ids=enriched_ids),
        skipped=BucketCount(count=len(skipped_ids), ids=skipped_ids),
        failed=BucketCount(count=0, ids=[]),
        errors=errors,
    )


def run_stage_finalize(
    repo: SupabaseRepository,
    limit: int = 50,
    dry_run: bool = False,
) -> StageResult:
    summary = run_stage_finalize_detailed(repo=repo, limit=limit, dry_run=dry_run)
    return StageResult(
        stage="jobs_final",
        success=summary.failed.count == 0 and len(summary.errors) == 0,
        processed=summary.enriched.count,
        errors=summary.errors,
    )


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
