from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from common.client import OperationResult
from repository.supabase import SupabaseRepository

from job_enricher.client_copilot import CopilotClient
from job_enricher.extractors import enrich_job_row

from .tables import upsert_jobs_enriched


logger = logging.getLogger(__name__)


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


def _fetch_jobs_raw_scraped(repo: SupabaseRepository, limit: int) -> list[dict[str, Any]]:
    result = repo.select_rows(
        table="jobs_raw",
        columns="id,description,job_status,is_deleted",
        filters={"job_status": "SCRAPED", "is_deleted": False},
        limit=limit,
        order_by="created_at",
        ascending=True,
    )
    if not result.success or not isinstance(result.data, list):
        raise RuntimeError(result.error or "Failed to fetch jobs_raw rows.")
    return result.data


def _fetch_existing_enriched_ids(repo: SupabaseRepository, job_ids: list[str]) -> set[str]:
    if not job_ids:
        return set()

    in_filter = "(" + ",".join(job_ids) + ")"
    result = repo.client.select(
        table="jobs_enriched",
        columns="job_id",
        filters={"job_id": in_filter},
        operator="in",
    )
    if not result.success or not isinstance(result.data, list):
        raise RuntimeError(result.error or "Failed to fetch jobs_enriched rows.")

    return {str(row.get("job_id")) for row in result.data if row.get("job_id")}


def _mark_enriched_stage(repo: SupabaseRepository, row_id: str) -> OperationResult:
    return repo.patch_rows(
        table="jobs_raw",
        payload={"job_status": "ENRICHED"},
        filters={"id": row_id},
    )


def _fetch_persisted_enriched_ids(repo: SupabaseRepository, job_ids: list[str]) -> set[str]:
    if not job_ids:
        return set()

    in_filter = "(" + ",".join(job_ids) + ")"
    result = repo.client.select(
        table="jobs_enriched",
        columns="job_id",
        filters={"job_id": in_filter},
        operator="in",
    )
    if not result.success or not isinstance(result.data, list):
        raise RuntimeError(result.error or "Failed to verify persisted jobs_enriched rows.")

    return {str(row.get("job_id")) for row in result.data if row.get("job_id")}


def enrich_jobs(
    repo: SupabaseRepository,
    copilot_client: CopilotClient,
    limit: int,
    dry_run: bool = False,
) -> EnrichmentSummary:
    scraped_rows = _fetch_jobs_raw_scraped(repo=repo, limit=limit)
    logger.info("enricher fetched %s SCRAPED rows", len(scraped_rows))
    scraped_ids = [str(row.get("id")) for row in scraped_rows if row.get("id")]
    existing_ids = _fetch_existing_enriched_ids(repo=repo, job_ids=scraped_ids)
    if existing_ids:
        logger.info("enricher found %s already-enriched rows", len(existing_ids))

    pending_rows = [row for row in scraped_rows if str(row.get("id")) not in existing_ids]
    pending_ids = [str(row.get("id")) for row in pending_rows if row.get("id")]

    enriched_rows: list[dict[str, Any]] = []
    success_ids: list[str] = []
    skipped_ids: list[str] = []
    failed_ids: list[str] = []
    errors: list[str] = []

    for row in pending_rows:
        enriched_row, error = enrich_job_row(copilot_client=copilot_client, job_row=row)
        if error:
            if "missing description" in error:
                skipped_ids.append(str(row.get("id")))
            else:
                errors.append(f"job_id={row.get('id')}: {error}")
                failed_ids.append(str(row.get("id")))
            continue
        assert enriched_row is not None
        enriched_rows.append(enriched_row)
        success_ids.append(str(row["id"]))

    logger.info(
        "enricher extraction summary pending=%s extracted=%s skipped=%s failed=%s",
        len(pending_rows),
        len(enriched_rows),
        len(skipped_ids),
        len(failed_ids),
    )

    if dry_run:
        return EnrichmentSummary(
            processed=EnrichmentBucket(count=len(pending_rows), ids=pending_ids),
            enriched=EnrichmentBucket(count=len(enriched_rows), ids=success_ids),
            skipped=EnrichmentBucket(count=len(skipped_ids), ids=skipped_ids),
            failed=EnrichmentBucket(count=len(failed_ids), ids=failed_ids),
            errors=errors,
        )

    if enriched_rows:
        result = upsert_jobs_enriched(repo=repo, rows=enriched_rows)
        if not result.success:
            raise RuntimeError(result.error or "Failed to upsert jobs_enriched rows.")
        logger.info("enricher upsert accepted rows=%s", len(enriched_rows))

        persisted_ids = _fetch_persisted_enriched_ids(repo=repo, job_ids=success_ids)
        missing_ids = [row_id for row_id in success_ids if row_id not in persisted_ids]
        if missing_ids:
            logger.error("enricher upsert verification failed missing_ids=%s", missing_ids)
            raise RuntimeError(
                "Upsert returned success, but rows were not found in jobs_enriched for ids: "
                + ", ".join(missing_ids)
            )

        for row_id in success_ids:
            patch_result = _mark_enriched_stage(repo=repo, row_id=row_id)
            if not patch_result.success:
                errors.append(f"job_id={row_id}: failed to set job_status=ENRICHED")
                failed_ids.append(row_id)

        logger.info("enricher patched jobs_raw status for %s rows", len(success_ids))

    return EnrichmentSummary(
        processed=EnrichmentBucket(count=len(pending_rows), ids=pending_ids),
        enriched=EnrichmentBucket(count=len(enriched_rows), ids=success_ids),
        skipped=EnrichmentBucket(count=len(skipped_ids), ids=skipped_ids),
        failed=EnrichmentBucket(count=len(failed_ids), ids=failed_ids),
        errors=errors,
    )
