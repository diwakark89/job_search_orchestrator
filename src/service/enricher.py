from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from common.client import OperationResult
from repository.supabase import SupabaseRepository

from job_enricher.client_copilot import CopilotClient
from job_enricher.extractors import enrich_job_row

from .tables import upsert_jobs_enriched


@dataclass
class EnrichmentSummary:
    processed: int
    enriched: int
    skipped: int
    failed: int
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


def enrich_jobs(
    repo: SupabaseRepository,
    copilot_client: CopilotClient,
    limit: int,
    dry_run: bool = False,
) -> EnrichmentSummary:
    scraped_rows = _fetch_jobs_raw_scraped(repo=repo, limit=limit)
    scraped_ids = [str(row.get("id")) for row in scraped_rows if row.get("id")]
    existing_ids = _fetch_existing_enriched_ids(repo=repo, job_ids=scraped_ids)

    pending_rows = [row for row in scraped_rows if str(row.get("id")) not in existing_ids]

    enriched_rows: list[dict[str, Any]] = []
    success_ids: list[str] = []
    errors: list[str] = []
    skipped = 0

    for row in pending_rows:
        enriched_row, error = enrich_job_row(copilot_client=copilot_client, job_row=row)
        if error:
            if "missing description" in error:
                skipped += 1
            else:
                errors.append(f"job_id={row.get('id')}: {error}")
            continue
        assert enriched_row is not None
        enriched_rows.append(enriched_row)
        success_ids.append(str(row["id"]))

    if dry_run:
        return EnrichmentSummary(
            processed=len(pending_rows),
            enriched=len(enriched_rows),
            skipped=skipped,
            failed=len(errors),
            errors=errors,
        )

    if enriched_rows:
        result = upsert_jobs_enriched(repo=repo, rows=enriched_rows)
        if not result.success:
            raise RuntimeError(result.error or "Failed to upsert jobs_enriched rows.")

        for row_id in success_ids:
            patch_result = _mark_enriched_stage(repo=repo, row_id=row_id)
            if not patch_result.success:
                errors.append(f"job_id={row_id}: failed to set job_status=ENRICHED")

    return EnrichmentSummary(
        processed=len(pending_rows),
        enriched=len(enriched_rows),
        skipped=skipped,
        failed=len(errors),
        errors=errors,
    )
