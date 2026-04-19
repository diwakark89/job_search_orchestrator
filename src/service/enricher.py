from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from repository.supabase import SupabaseRepository

from job_enricher.client_copilot import CopilotBatchExtractionInput, CopilotBatchExtractionResult
from job_enricher.extractors import enrich_job_rows

from .enricher_persistence import patch_enriched_rows as _patch_enriched_rows_impl


logger = logging.getLogger("uvicorn.error")


class SupportsJobExtraction(Protocol):
    @property
    def batch_size(self) -> int: ...

    def extract_from_description(self, description: str) -> Any: ...

    def extract_from_descriptions(
        self,
        items: list[CopilotBatchExtractionInput],
    ) -> list[CopilotBatchExtractionResult]: ...


@dataclass
class EnrichmentBucket:
    count: int
    ids: list[str]


@dataclass
class EnrichmentSummary:
    processed: EnrichmentBucket
    enriched: EnrichmentBucket
    skipped: EnrichmentBucket
    failed: EnrichmentBucket
    errors: list[str]
    copilot_batches_sent: int = 0
    database_batches_sent: int = 0
    database_rows_reported: int = 0


def _fetch_scraped_jobs(repo: SupabaseRepository, limit: int) -> list[dict[str, Any]]:
    result = repo.select_rows(
        table="jobs_final",
        columns="id,description,job_status,is_deleted",
        filters={"job_status": "SCRAPED", "is_deleted": False},
        limit=limit,
        order_by="created_at",
        ascending=True,
    )
    if not result.success or not isinstance(result.data, list):
        raise RuntimeError(result.error or "Failed to fetch SCRAPED jobs_final rows.")
    return result.data


def _fetch_jobs_by_ids(repo: SupabaseRepository, ids: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []

    result = repo.select_rows(
        table="jobs_final",
        columns="id,description,job_status,is_deleted",
        filters={"id": ("in", ids), "is_deleted": False},
    )
    if not result.success or not isinstance(result.data, list):
        raise RuntimeError(result.error or "Failed to fetch requested jobs_final rows.")
    return result.data


def _build_summary(
    processed_ids: list[str],
    enriched_ids: list[str],
    skipped_ids: list[str],
    failed_ids: list[str],
    errors: list[str],
    copilot_batches_sent: int,
    database_batches_sent: int,
    database_rows_reported: int,
) -> EnrichmentSummary:
    return EnrichmentSummary(
        processed=EnrichmentBucket(count=len(processed_ids), ids=processed_ids),
        enriched=EnrichmentBucket(count=len(enriched_ids), ids=enriched_ids),
        skipped=EnrichmentBucket(count=len(skipped_ids), ids=skipped_ids),
        failed=EnrichmentBucket(count=len(failed_ids), ids=failed_ids),
        errors=errors,
        copilot_batches_sent=copilot_batches_sent,
        database_batches_sent=database_batches_sent,
        database_rows_reported=database_rows_reported,
    )


def _extract_rows(
    rows: list[dict[str, Any]],
    copilot_client: SupportsJobExtraction,
) -> tuple[list[dict[str, Any]], list[str], list[str], list[str], list[str], int]:
    enriched_rows: list[dict[str, Any]] = []
    success_ids: list[str] = []
    skipped_ids: list[str] = []
    failed_ids: list[str] = []
    errors: list[str] = []
    copilot_batches_sent = 0

    batch_size = max(getattr(copilot_client, "batch_size", 1), 1)
    for start in range(0, len(rows), batch_size):
        batch_rows = rows[start : start + batch_size]
        batch_ids = [str(row.get("id")) for row in batch_rows]
        logger.info("enricher processing batch size=%s ids=%s", len(batch_rows), batch_ids)
        copilot_candidates = [row for row in batch_rows if str(row.get("id", "")).strip() and str(row.get("description", "")).strip()]
        if copilot_candidates:
            copilot_batches_sent += 1

        batch_results = enrich_job_rows(copilot_client=copilot_client, job_rows=batch_rows)
        for batch_result in batch_results:
            row_id = batch_result.row_id
            if batch_result.error:
                if batch_result.skipped:
                    logger.warning("enricher skipped id=%s reason=%s", row_id, batch_result.error)
                    skipped_ids.append(row_id)
                else:
                    logger.error("enricher failed id=%s reason=%s", row_id, batch_result.error)
                    errors.append(f"id={row_id}: {batch_result.error}")
                    failed_ids.append(row_id)
                continue

            assert batch_result.enriched_row is not None
            logger.info("enricher extracted id=%s", row_id)
            enriched_rows.append(batch_result.enriched_row)
            success_ids.append(str(batch_result.enriched_row["id"]))

    return enriched_rows, success_ids, skipped_ids, failed_ids, errors, copilot_batches_sent


def _patch_enriched_rows(
    repo: SupabaseRepository,
    enriched_rows: list[dict[str, Any]],
    success_ids: list[str],
    failed_ids: list[str],
    errors: list[str],
    set_job_status_enriched: bool,
    target_job_status: str,
    submit_request_id: str | None = None,
) -> tuple[list[str], int, int]:
    return _patch_enriched_rows_impl(
        repo=repo,
        enriched_rows=enriched_rows,
        success_ids=success_ids,
        failed_ids=failed_ids,
        errors=errors,
        set_job_status_enriched=set_job_status_enriched,
        target_job_status=target_job_status,
        submit_request_id=submit_request_id,
    )


def _enrich_rows(
    repo: SupabaseRepository,
    copilot_client: SupportsJobExtraction,
    rows: list[dict[str, Any]],
    processed_ids: list[str],
    dry_run: bool,
    set_job_status_enriched: bool,
    target_job_status: str,
    initial_failed_ids: list[str] | None = None,
    initial_errors: list[str] | None = None,
    submit_request_id: str | None = None,
) -> EnrichmentSummary:
    enriched_rows, success_ids, skipped_ids, failed_ids, errors, copilot_batches_sent = _extract_rows(
        rows=rows,
        copilot_client=copilot_client,
    )
    database_batches_sent = 0
    database_rows_reported = 0

    if initial_failed_ids:
        failed_ids = [*initial_failed_ids, *failed_ids]
    if initial_errors:
        errors = [*initial_errors, *errors]

    logger.info(
        "enricher extraction summary pending=%s extracted=%s skipped=%s failed=%s",
        len(rows),
        len(enriched_rows),
        len(skipped_ids),
        len(failed_ids),
    )

    if dry_run:
        return _build_summary(
            processed_ids=processed_ids,
            enriched_ids=success_ids,
            skipped_ids=skipped_ids,
            failed_ids=failed_ids,
            errors=errors,
            copilot_batches_sent=copilot_batches_sent,
            database_batches_sent=database_batches_sent,
            database_rows_reported=database_rows_reported,
        )

    persisted_ids, database_batches_sent, database_rows_reported = _patch_enriched_rows(
        repo=repo,
        enriched_rows=enriched_rows,
        success_ids=success_ids,
        failed_ids=failed_ids,
        errors=errors,
        set_job_status_enriched=set_job_status_enriched,
        target_job_status=target_job_status,
        submit_request_id=submit_request_id,
    )

    logger.info("enricher patched %s jobs_final rows", len(persisted_ids))

    return _build_summary(
        processed_ids=processed_ids,
        enriched_ids=persisted_ids,
        skipped_ids=skipped_ids,
        failed_ids=failed_ids,
        errors=errors,
        copilot_batches_sent=copilot_batches_sent,
        database_batches_sent=database_batches_sent,
        database_rows_reported=database_rows_reported,
    )


def enrich_jobs(
    repo: SupabaseRepository,
    copilot_client: SupportsJobExtraction,
    limit: int,
    dry_run: bool = False,
) -> EnrichmentSummary:
    scraped_rows = _fetch_scraped_jobs(repo=repo, limit=limit)
    logger.info("enricher fetched %s SCRAPED rows", len(scraped_rows))

    pending_ids = [str(row.get("id")) for row in scraped_rows if row.get("id")]
    return _enrich_rows(
        repo=repo,
        copilot_client=copilot_client,
        rows=scraped_rows,
        processed_ids=pending_ids,
        dry_run=dry_run,
        set_job_status_enriched=True,
        target_job_status="ENRICHED",
    )


def enrich_jobs_by_ids(
    repo: SupabaseRepository,
    copilot_client: SupportsJobExtraction,
    ids: list[str],
    dry_run: bool = False,
    set_job_status_enriched: bool = False,
    target_job_status: str = "ENRICHED",
    submit_request_id: str | None = None,
) -> EnrichmentSummary:
    logger.info(
        "enricher by_ids requested_ids=%s dry_run=%s submit_request_id=%s",
        len(ids),
        dry_run,
        submit_request_id,
    )

    requested_ids = [row_id.strip() for row_id in ids if row_id and row_id.strip()]
    if not requested_ids:
        raise ValueError("At least one id is required.")

    unique_ids: list[str] = []
    seen_ids: set[str] = set()
    for row_id in requested_ids:
        if row_id in seen_ids:
            continue
        seen_ids.add(row_id)
        unique_ids.append(row_id)

    requested_rows = _fetch_jobs_by_ids(repo=repo, ids=unique_ids)
    row_by_id = {str(row.get("id")): row for row in requested_rows if row.get("id")}

    found_rows: list[dict[str, Any]] = []
    missing_ids: list[str] = []
    missing_errors: list[str] = []
    for row_id in unique_ids:
        row = row_by_id.get(row_id)
        if row is None:
            logger.warning("enricher by_ids missing id=%s", row_id)
            missing_ids.append(row_id)
            missing_errors.append(f"id={row_id}: jobs_final row not found or soft-deleted")
            continue
        found_rows.append(row)

    logger.info(
        "enricher by_ids fetched=%s missing=%s unique_ids=%s",
        len(found_rows),
        len(missing_ids),
        len(unique_ids),
    )

    return _enrich_rows(
        repo=repo,
        copilot_client=copilot_client,
        rows=found_rows,
        processed_ids=unique_ids,
        dry_run=dry_run,
        set_job_status_enriched=set_job_status_enriched,
        target_job_status=target_job_status,
        initial_failed_ids=missing_ids,
        initial_errors=missing_errors,
        submit_request_id=submit_request_id,
    )
