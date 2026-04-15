from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from repository.supabase import SupabaseRepository

from job_enricher.client_copilot import CopilotClient
from job_enricher.extractors import enrich_job_row


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


def enrich_jobs(
    repo: SupabaseRepository,
    copilot_client: CopilotClient,
    limit: int,
    dry_run: bool = False,
) -> EnrichmentSummary:
    scraped_rows = _fetch_scraped_jobs(repo=repo, limit=limit)
    logger.info("enricher fetched %s SCRAPED rows", len(scraped_rows))

    pending_ids = [str(row.get("id")) for row in scraped_rows if row.get("id")]

    enriched_rows: list[dict[str, Any]] = []
    success_ids: list[str] = []
    skipped_ids: list[str] = []
    failed_ids: list[str] = []
    errors: list[str] = []

    for row in scraped_rows:
        enriched_row, error = enrich_job_row(copilot_client=copilot_client, job_row=row)
        if error:
            if "missing description" in error:
                skipped_ids.append(str(row.get("id")))
            else:
                errors.append(f"id={row.get('id')}: {error}")
                failed_ids.append(str(row.get("id")))
            continue
        assert enriched_row is not None
        enriched_rows.append(enriched_row)
        success_ids.append(str(row["id"]))

    logger.info(
        "enricher extraction summary pending=%s extracted=%s skipped=%s failed=%s",
        len(scraped_rows),
        len(enriched_rows),
        len(skipped_ids),
        len(failed_ids),
    )

    if dry_run:
        return EnrichmentSummary(
            processed=EnrichmentBucket(count=len(scraped_rows), ids=pending_ids),
            enriched=EnrichmentBucket(count=len(enriched_rows), ids=success_ids),
            skipped=EnrichmentBucket(count=len(skipped_ids), ids=skipped_ids),
            failed=EnrichmentBucket(count=len(failed_ids), ids=failed_ids),
            errors=errors,
        )

    for enriched_row in enriched_rows:
        row_id = enriched_row.pop("id")
        enriched_row["job_status"] = "ENRICHED"
        patch_result = repo.patch_rows(
            table="jobs_final",
            payload=enriched_row,
            filters={"id": row_id},
        )
        if not patch_result.success:
            errors.append(f"id={row_id}: failed to patch enrichment data")
            failed_ids.append(row_id)
            if row_id in success_ids:
                success_ids.remove(row_id)

    logger.info("enricher patched %s jobs_final rows", len(success_ids))

    return EnrichmentSummary(
        processed=EnrichmentBucket(count=len(scraped_rows), ids=pending_ids),
        enriched=EnrichmentBucket(count=len(success_ids), ids=success_ids),
        skipped=EnrichmentBucket(count=len(skipped_ids), ids=skipped_ids),
        failed=EnrichmentBucket(count=len(failed_ids), ids=failed_ids),
        errors=errors,
    )
