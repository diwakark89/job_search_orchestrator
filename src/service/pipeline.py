from __future__ import annotations

import logging
from typing import Any

from common.validators import JobsFinalRow, normalize_timestamp_fields
from job_enricher.client_copilot import CopilotClient
from repository.supabase import SupabaseRepository

from pipeline.models import PipelineResult, StageResult, SubmitJobsResult

from .enricher import EnrichmentSummary, enrich_jobs
from .tables import insert_shared_links

_INGEST_TIMESTAMP_FIELDS = ("created_at", "modified_at")
_SUBMIT_TIMESTAMP_FIELDS = ("saved_at", "modified_at", "approved_at")

logger = logging.getLogger("uvicorn.error")


def _validate_submit_rows(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[int], list[str]]:
    validated_by_url: dict[str, dict[str, Any]] = {}
    accepted_urls: list[str] = []
    rejected_row_indexes: list[int] = []
    errors: list[str] = []

    logger.debug("submit _validate_submit_rows input_row_count=%s", len(rows))
    for idx, row in enumerate(rows):
        try:
            candidate = dict(row)
            candidate["job_status"] = "SCRAPED"
            validated = JobsFinalRow.model_validate(candidate)
            normalized = normalize_timestamp_fields(
                validated.model_dump(exclude_none=True, exclude={"id"}),
                _SUBMIT_TIMESTAMP_FIELDS,
            )
            job_url = str(normalized.get("job_url") or "").strip()
            if not job_url:
                raise ValueError("job_url is required.")

            normalized["job_url"] = job_url
            if job_url not in validated_by_url:
                accepted_urls.append(job_url)
            validated_by_url[job_url] = normalized
        except Exception as exc:  # noqa: BLE001
            logger.debug("submit validation_rejected row_idx=%s reason=%s", idx, exc)
            rejected_row_indexes.append(idx)
            errors.append(f"row[{idx}]: {exc}")

    validated_rows = [validated_by_url[job_url] for job_url in accepted_urls]
    logger.info(
        "submit validation_summary input=%s accepted=%s rejected=%s",
        len(rows),
        len(accepted_urls),
        len(rejected_row_indexes),
    )
    if rejected_row_indexes:
        logger.debug("submit rejected_row_indexes=%s", rejected_row_indexes)
    return validated_rows, accepted_urls, rejected_row_indexes, errors


def _select_submitted_jobs(repo: SupabaseRepository, job_urls: list[str]) -> tuple[list[str], list[str]]:
    logger.info("submit select_submitted_jobs url_count=%s", len(job_urls))
    select_result = repo.select_rows(
        table="jobs_final",
        columns="id,job_url",
        filters={"job_url": ("in", job_urls), "is_deleted": False},
    )
    if not select_result.success or not isinstance(select_result.data, list):
        raise RuntimeError(select_result.error or "Failed to fetch submitted jobs_final rows.")

    rows_by_url = {
        str(row.get("job_url")): row
        for row in select_result.data
        if row.get("job_url") and row.get("id")
    }

    accepted_ids: list[str] = []
    missing_urls: list[str] = []
    for job_url in job_urls:
        row = rows_by_url.get(job_url)
        if row is None:
            missing_urls.append(job_url)
            continue
        accepted_ids.append(str(row["id"]))

    if missing_urls:
        raise RuntimeError(
            "Upsert returned success, but rows were not found in jobs_final for urls: "
            + ", ".join(missing_urls)
        )

    logger.info(
        "submit select_submitted_jobs found=%s ids=%s",
        len(accepted_ids),
        accepted_ids,
    )
    return accepted_ids, job_urls


def submit_jobs_for_enrichment(
    repo: SupabaseRepository,
    rows: list[dict[str, Any]],
) -> SubmitJobsResult:
    logger.info("submit_jobs_for_enrichment started submitted_row_count=%s", len(rows))
    validated_rows, accepted_urls, rejected_row_indexes, errors = _validate_submit_rows(rows)

    if not accepted_urls:
        detail = "; ".join(errors) if errors else "No valid jobs submitted."
        raise ValueError(f"No valid jobs submitted. {detail}".strip())

    logger.info(
        "submit jobs_final upsert starting accepted_url_count=%s on_conflict=job_url",
        len(accepted_urls),
    )
    jobs_final_result = repo.upsert_rows(
        table="jobs_final",
        rows=validated_rows,
        on_conflict="job_url",
    )
    if not jobs_final_result.success:
        raise RuntimeError(jobs_final_result.error or "Failed to upsert jobs_final rows.")
    logger.info(
        "submit jobs_final upsert completed row_count=%s",
        jobs_final_result.row_count,
    )

    accepted_ids, persisted_urls = _select_submitted_jobs(repo=repo, job_urls=accepted_urls)

    logger.info(
        "submit shared_links upsert starting url_count=%s",
        len(persisted_urls),
    )
    shared_links_result = insert_shared_links(
        repo=repo,
        rows=[{"url": job_url} for job_url in persisted_urls],
    )
    if not shared_links_result.success:
        raise RuntimeError(shared_links_result.error or "Failed to upsert shared_links rows.")
    logger.info(
        "submit shared_links upsert completed row_count=%s",
        shared_links_result.row_count,
    )

    logger.info(
        "submit_jobs_for_enrichment completed accepted_ids=%s rejected=%s jobs_final_rows=%s shared_links_rows=%s",
        len(accepted_ids),
        len(rejected_row_indexes),
        jobs_final_result.row_count,
        shared_links_result.row_count,
    )
    logger.debug("submit accepted_ids=%s", accepted_ids)

    return SubmitJobsResult(
        submitted_row_count=len(rows),
        accepted_ids=accepted_ids,
        accepted_urls=persisted_urls,
        rejected_row_indexes=rejected_row_indexes,
        errors=errors,
        jobs_final_row_count=jobs_final_result.row_count,
        shared_links_row_count=shared_links_result.row_count,
    )


def run_stage_ingest(repo: SupabaseRepository, rows: list[dict[str, Any]]) -> StageResult:
    valid_rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for idx, row in enumerate(rows):
        try:
            candidate = dict(row)
            if "job_status" not in candidate:
                candidate["job_status"] = "SCRAPED"
            validated = JobsFinalRow.model_validate(candidate)
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
