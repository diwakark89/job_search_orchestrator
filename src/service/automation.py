from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from repository.supabase import SupabaseRepository

_ACTIVE_SESSION_STATUSES: tuple[str, ...] = ("RUNNING", "WAITING_USER", "RESUMING")
_APPROVE_ALLOWED_JOB_STATUSES: set[str] = {"ENRICHED", "SAVED", "READY_TO_APPLY"}
_REJECT_ALLOWED_JOB_STATUSES: set[str] = {
    "ENRICHED",
    "SAVED",
    "READY_TO_APPLY",
    "WAITING_CONFIRMATION",
}


class AutomationConflictError(ValueError):
    """Raised when the requested lifecycle action conflicts with active state."""


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _select_rows_or_raise(
    repo: SupabaseRepository,
    table: str,
    columns: str,
    filters: dict[str, Any],
    *,
    limit: int = 1,
    order_by: str | None = None,
    ascending: bool = True,
) -> list[dict[str, Any]]:
    result = repo.select_rows(
        table=table,
        columns=columns,
        filters=filters,
        limit=limit,
        order_by=order_by,
        ascending=ascending,
    )
    if not result.success or not isinstance(result.data, list):
        raise RuntimeError(result.error or f"Failed to query {table}.")
    return result.data


def _get_job_row(repo: SupabaseRepository, job_id: str) -> dict[str, Any]:
    rows = _select_rows_or_raise(
        repo=repo,
        table="jobs_final",
        columns="id,job_status,user_action,approved_at,is_deleted",
        filters={"id": job_id, "is_deleted": False},
        limit=1,
    )
    if not rows:
        raise ValueError(f"jobs_final row '{job_id}' not found or soft-deleted.")
    return rows[0]


def _build_job_decision_response(job_row: dict[str, Any], action: str) -> dict[str, Any]:
    return {
        "job_id": str(job_row.get("id") or ""),
        "action": action,
        "job_status": str(job_row.get("job_status") or ""),
        "user_action": str(job_row.get("user_action") or ""),
        "approved_at": job_row.get("approved_at"),
    }


def approve_job_for_apply(repo: SupabaseRepository, job_id: str) -> dict[str, Any]:
    job_row = _get_job_row(repo=repo, job_id=job_id)
    current_status = str(job_row.get("job_status") or "")
    if current_status not in _APPROVE_ALLOWED_JOB_STATUSES:
        raise ValueError(
            f"Job '{job_id}' with status '{current_status or 'Unknown'}' cannot be approved. "
            f"Allowed: {sorted(_APPROVE_ALLOWED_JOB_STATUSES)}"
        )

    patch_result = repo.patch_rows(
        table="jobs_final",
        payload={
            "job_status": "READY_TO_APPLY",
            "user_action": "APPROVED",
            "approved_at": _utc_now_iso(),
        },
        filters={"id": job_id},
    )
    if not patch_result.success:
        raise RuntimeError(patch_result.error or f"Failed to approve job '{job_id}'.")

    updated = _get_job_row(repo=repo, job_id=job_id)
    return _build_job_decision_response(updated, action="APPROVE")


def reject_job_for_apply(repo: SupabaseRepository, job_id: str) -> dict[str, Any]:
    job_row = _get_job_row(repo=repo, job_id=job_id)
    current_status = str(job_row.get("job_status") or "")
    if current_status not in _REJECT_ALLOWED_JOB_STATUSES:
        raise ValueError(
            f"Job '{job_id}' with status '{current_status or 'Unknown'}' cannot be rejected. "
            f"Allowed: {sorted(_REJECT_ALLOWED_JOB_STATUSES)}"
        )

    patch_result = repo.patch_rows(
        table="jobs_final",
        payload={
            "job_status": "SAVED",
            "user_action": "REJECTED",
            "approved_at": None,
        },
        filters={"id": job_id},
    )
    if not patch_result.success:
        raise RuntimeError(patch_result.error or f"Failed to reject job '{job_id}'.")

    updated = _get_job_row(repo=repo, job_id=job_id)
    return _build_job_decision_response(updated, action="REJECT")


def _get_active_session_for_job(repo: SupabaseRepository, job_id: str) -> dict[str, Any] | None:
    rows = _select_rows_or_raise(
        repo=repo,
        table="automation_sessions",
        columns="id,job_id,session_status,current_step,updated_at",
        filters={"job_id": job_id, "session_status": ("in", list(_ACTIVE_SESSION_STATUSES))},
        limit=1,
        order_by="updated_at",
        ascending=False,
    )
    if not rows:
        return None
    return rows[0]


def create_apply_session_for_job(
    repo: SupabaseRepository,
    job_id: str,
    current_step: str = "OPEN_JOB_PAGE",
) -> dict[str, Any]:
    if not current_step.strip():
        raise ValueError("current_step must not be empty.")

    job_row = _get_job_row(repo=repo, job_id=job_id)
    if str(job_row.get("job_status") or "") != "READY_TO_APPLY":
        raise ValueError(
            f"Job '{job_id}' must be in READY_TO_APPLY before creating an automation session."
        )
    if str(job_row.get("user_action") or "") != "APPROVED":
        raise ValueError(
            f"Job '{job_id}' must have user_action=APPROVED before creating an automation session."
        )

    active_session = _get_active_session_for_job(repo=repo, job_id=job_id)
    if active_session is not None:
        raise AutomationConflictError(
            f"Job '{job_id}' already has an active automation session "
            f"'{active_session.get('id')}' in status '{active_session.get('session_status')}'."
        )

    upsert_result = repo.upsert_rows(
        table="automation_sessions",
        rows=[
            {
                "job_id": job_id,
                "automation_type": "JOB_APPLY",
                "session_status": "RUNNING",
                "current_step": current_step.strip(),
            }
        ],
        on_conflict="id",
    )
    if not upsert_result.success:
        raise RuntimeError(upsert_result.error or f"Failed to create automation session for '{job_id}'.")

    created_session = _get_active_session_for_job(repo=repo, job_id=job_id)
    if created_session is None:
        raise RuntimeError(
            f"Automation session creation for '{job_id}' succeeded but no active session was found."
        )

    return {
        "session_id": str(created_session.get("id") or ""),
        "job_id": str(created_session.get("job_id") or job_id),
        "session_status": str(created_session.get("session_status") or ""),
        "current_step": created_session.get("current_step"),
    }
