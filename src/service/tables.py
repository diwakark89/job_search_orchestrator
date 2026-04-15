from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from common.client import OperationResult
from repository.supabase import SupabaseRepository


def upsert_jobs_final(repo: SupabaseRepository, rows: list[dict]) -> OperationResult:
    return repo.upsert_rows(table="jobs_final", rows=rows, on_conflict="id")


def insert_shared_links(repo: SupabaseRepository, rows: list[dict]) -> OperationResult:
    return repo.upsert_rows(table="shared_links", rows=rows, on_conflict="url")


def delete_jobs_final_by_id(repo: SupabaseRepository, job_id: str) -> OperationResult:
    return repo.delete_rows(
        table="jobs_final",
        filters={"id": job_id},
        treat_404_as_success=True,
    )


def soft_delete_jobs_final(repo: SupabaseRepository, job_id: str, hard_delete: bool = False) -> OperationResult:
    now_iso = datetime.now(tz=UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    patch_result = repo.patch_rows(
        table="jobs_final",
        payload={"is_deleted": True, "modified_at": now_iso},
        filters={"id": job_id},
    )

    if not patch_result.success or not hard_delete:
        return patch_result

    return delete_jobs_final_by_id(repo, job_id)


def get_metrics(repo: SupabaseRepository) -> dict[str, Any]:
    result = repo.select_rows(
        table="jobs_final",
        columns="job_status",
        filters={"is_deleted": False},
    )
    if not result.success or not isinstance(result.data, list):
        raise RuntimeError(result.error or "Failed to fetch jobs_final rows for metrics.")

    status_counts: dict[str, int] = {}
    for row in result.data:
        status = row.get("job_status") or "Unknown"
        status_counts[status] = status_counts.get(status, 0) + 1

    return {"status_counts": status_counts, "total": len(result.data)}
