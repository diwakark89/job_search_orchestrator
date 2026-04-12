from __future__ import annotations

from datetime import UTC, datetime

from common.client import OperationResult
from repository.supabase import SupabaseRepository


def upsert_jobs_final(repo: SupabaseRepository, rows: list[dict]) -> OperationResult:
    return repo.upsert_rows(table="jobs_final", rows=rows, on_conflict="job_id")


def insert_shared_links(repo: SupabaseRepository, rows: list[dict]) -> OperationResult:
    return repo.upsert_rows(table="shared_links", rows=rows, on_conflict="url")


def upsert_jobs_raw(repo: SupabaseRepository, rows: list[dict]) -> OperationResult:
    return repo.upsert_rows(table="jobs_raw", rows=rows, on_conflict="job_url")


def upsert_jobs_enriched(repo: SupabaseRepository, rows: list[dict]) -> OperationResult:
    return repo.upsert_rows(table="jobs_enriched", rows=rows, on_conflict="job_id")


def insert_job_decisions(repo: SupabaseRepository, rows: list[dict]) -> OperationResult:
    return repo.insert_rows(table="job_decisions", rows=rows)


def upsert_job_approvals(repo: SupabaseRepository, rows: list[dict]) -> OperationResult:
    return repo.upsert_rows(table="job_approvals", rows=rows, on_conflict="decision_id")


def patch_job_metrics(repo: SupabaseRepository, payload: dict) -> OperationResult:
    return repo.patch_rows(table="job_metrics", payload=payload, filters={"id": 1})


def delete_jobs_final_by_job_id(repo: SupabaseRepository, job_id: str) -> OperationResult:
    return repo.delete_rows(
        table="jobs_final",
        filters={"job_id": job_id},
        treat_404_as_success=True,
    )


def delete_jobs_raw_by_id(repo: SupabaseRepository, row_id: str) -> OperationResult:
    return repo.delete_rows(
        table="jobs_raw",
        filters={"id": row_id},
        treat_404_as_success=True,
    )


def soft_delete_jobs_final(repo: SupabaseRepository, job_id: str, hard_delete: bool = False) -> OperationResult:
    now_iso = datetime.now(tz=UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    patch_result = repo.patch_rows(
        table="jobs_final",
        payload={"is_deleted": True, "modified_at": now_iso},
        filters={"job_id": job_id},
    )

    if not patch_result.success or not hard_delete:
        return patch_result

    return delete_jobs_final_by_job_id(repo, job_id)


def soft_delete_jobs_raw(repo: SupabaseRepository, row_id: str, hard_delete: bool = False) -> OperationResult:
    now_iso = datetime.now(tz=UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    patch_result = repo.patch_rows(
        table="jobs_raw",
        payload={"is_deleted": True, "modified_at": now_iso},
        filters={"id": row_id},
    )

    if not patch_result.success or not hard_delete:
        return patch_result

    return delete_jobs_raw_by_id(repo, row_id)
