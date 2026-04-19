"""Persistence helper for enrichment results.

Isolates the database-side concern (upsert into ``jobs_final`` and the
associated logging/error bookkeeping) from the LLM extraction pipeline so it
can be unit-tested independently.
"""
from __future__ import annotations

import logging
from typing import Any

from repository.supabase import SupabaseRepository


logger = logging.getLogger("uvicorn.error")


def patch_enriched_rows(
    repo: SupabaseRepository,
    enriched_rows: list[dict[str, Any]],
    success_ids: list[str],
    failed_ids: list[str],
    errors: list[str],
    set_job_status_enriched: bool,
    target_job_status: str,
    submit_request_id: str | None = None,
) -> tuple[list[str], int, int]:
    """Upsert enriched rows into ``jobs_final``.

    Mutates ``failed_ids`` and ``errors`` in place when the upsert fails so the
    caller's bookkeeping stays consistent.

    Returns ``(persisted_ids, database_batches_sent, database_rows_reported)``.
    """
    if not enriched_rows:
        return [], 0, 0

    rows_to_upsert: list[dict[str, Any]] = []
    for enriched_row in enriched_rows:
        payload = dict(enriched_row)
        if set_job_status_enriched:
            payload["job_status"] = target_job_status
        rows_to_upsert.append(payload)

    if set_job_status_enriched:
        enriched_ids_for_patch = [str(r.get("id", "")) for r in rows_to_upsert]
        logger.info(
            "enricher setting job_status=%s for %s rows submit_request_id=%s",
            target_job_status,
            len(rows_to_upsert),
            submit_request_id,
        )
        logger.debug(
            "enricher job_status=%s ids submit_request_id=%s ids=%s",
            target_job_status,
            submit_request_id,
            enriched_ids_for_patch,
        )

    logger.info(
        "enricher persisting batch rows=%s set_job_status_enriched=%s submit_request_id=%s",
        len(rows_to_upsert),
        set_job_status_enriched,
        submit_request_id,
    )
    upsert_result = repo.upsert_rows(table="jobs_final", rows=rows_to_upsert, on_conflict="id")
    if upsert_result.success:
        logger.info(
            "enricher persisted batch rows=%s repo_row_count=%s submit_request_id=%s",
            len(rows_to_upsert),
            upsert_result.row_count,
            submit_request_id,
        )
        return list(success_ids), 1, upsert_result.row_count

    logger.error(
        "enricher persist_failed rows=%s repo_row_count=%s submit_request_id=%s",
        len(rows_to_upsert),
        upsert_result.row_count,
        submit_request_id,
    )
    for row in rows_to_upsert:
        row_id = str(row["id"])
        errors.append(f"id={row_id}: failed to persist enrichment data")
        failed_ids.append(row_id)

    return [], 1, upsert_result.row_count


__all__ = ["patch_enriched_rows"]
