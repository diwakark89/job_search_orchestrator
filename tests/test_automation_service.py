from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.client import OperationResult
from service.automation import (
    AutomationConflictError,
    approve_job_for_apply,
    create_apply_session_for_job,
    reject_job_for_apply,
)


def _ok(
    *,
    table: str,
    operation: str,
    data: object | None = None,
    row_count: int = 1,
) -> OperationResult:
    return OperationResult(
        success=True,
        status_code=200,
        table=table,
        operation=operation,
        row_count=row_count,
        data=data,
    )


def test_approve_job_for_apply_success() -> None:
    repo = MagicMock()
    repo.select_rows.side_effect = [
        _ok(
            table="jobs_final",
            operation="select",
            data=[{"id": "job-1", "job_status": "ENRICHED", "user_action": "PENDING", "approved_at": None}],
        ),
        _ok(
            table="jobs_final",
            operation="select",
            data=[
                {
                    "id": "job-1",
                    "job_status": "READY_TO_APPLY",
                    "user_action": "APPROVED",
                    "approved_at": "2026-05-19T10:00:00.000Z",
                }
            ],
        ),
    ]
    repo.patch_rows.return_value = _ok(table="jobs_final", operation="patch")

    result = approve_job_for_apply(repo=repo, job_id="job-1")

    assert result["job_id"] == "job-1"
    assert result["action"] == "APPROVE"
    assert result["job_status"] == "READY_TO_APPLY"
    assert result["user_action"] == "APPROVED"
    assert result["approved_at"] == "2026-05-19T10:00:00.000Z"

    repo.patch_rows.assert_called_once()
    patch_payload = repo.patch_rows.call_args.kwargs["payload"]
    assert patch_payload["job_status"] == "READY_TO_APPLY"
    assert patch_payload["user_action"] == "APPROVED"
    assert patch_payload["approved_at"].endswith("Z")


def test_approve_job_for_apply_rejects_invalid_status() -> None:
    repo = MagicMock()
    repo.select_rows.return_value = _ok(
        table="jobs_final",
        operation="select",
        data=[{"id": "job-1", "job_status": "APPLIED", "user_action": "PENDING", "approved_at": None}],
    )

    with pytest.raises(ValueError, match="cannot be approved"):
        approve_job_for_apply(repo=repo, job_id="job-1")

    repo.patch_rows.assert_not_called()


def test_reject_job_for_apply_success() -> None:
    repo = MagicMock()
    repo.select_rows.side_effect = [
        _ok(
            table="jobs_final",
            operation="select",
            data=[{"id": "job-1", "job_status": "READY_TO_APPLY", "user_action": "APPROVED", "approved_at": "x"}],
        ),
        _ok(
            table="jobs_final",
            operation="select",
            data=[{"id": "job-1", "job_status": "SAVED", "user_action": "REJECTED", "approved_at": None}],
        ),
    ]
    repo.patch_rows.return_value = _ok(table="jobs_final", operation="patch")

    result = reject_job_for_apply(repo=repo, job_id="job-1")

    assert result["action"] == "REJECT"
    assert result["job_status"] == "SAVED"
    assert result["user_action"] == "REJECTED"

    patch_payload = repo.patch_rows.call_args.kwargs["payload"]
    assert patch_payload == {
        "job_status": "SAVED",
        "user_action": "REJECTED",
        "approved_at": None,
    }


def test_create_apply_session_for_job_success() -> None:
    repo = MagicMock()
    repo.select_rows.side_effect = [
        _ok(
            table="jobs_final",
            operation="select",
            data=[{"id": "job-1", "job_status": "READY_TO_APPLY", "user_action": "APPROVED", "approved_at": "z"}],
        ),
        _ok(table="automation_sessions", operation="select", data=[]),
        _ok(
            table="automation_sessions",
            operation="select",
            data=[
                {
                    "id": "session-1",
                    "job_id": "job-1",
                    "session_status": "RUNNING",
                    "current_step": "OPEN_JOB_PAGE",
                    "updated_at": "2026-05-19T10:00:00.000Z",
                }
            ],
        ),
    ]
    repo.upsert_rows.return_value = _ok(table="automation_sessions", operation="upsert")

    result = create_apply_session_for_job(repo=repo, job_id="job-1")

    assert result == {
        "session_id": "session-1",
        "job_id": "job-1",
        "session_status": "RUNNING",
        "current_step": "OPEN_JOB_PAGE",
    }
    repo.upsert_rows.assert_called_once_with(
        table="automation_sessions",
        rows=[
            {
                "job_id": "job-1",
                "automation_type": "JOB_APPLY",
                "session_status": "RUNNING",
                "current_step": "OPEN_JOB_PAGE",
            }
        ],
        on_conflict="id",
    )


def test_create_apply_session_for_job_rejects_active_session_conflict() -> None:
    repo = MagicMock()
    repo.select_rows.side_effect = [
        _ok(
            table="jobs_final",
            operation="select",
            data=[{"id": "job-1", "job_status": "READY_TO_APPLY", "user_action": "APPROVED", "approved_at": "z"}],
        ),
        _ok(
            table="automation_sessions",
            operation="select",
            data=[
                {
                    "id": "session-existing",
                    "job_id": "job-1",
                    "session_status": "WAITING_USER",
                    "current_step": "FINAL_REVIEW",
                    "updated_at": "2026-05-19T10:00:00.000Z",
                }
            ],
        ),
    ]

    with pytest.raises(AutomationConflictError, match="already has an active automation session"):
        create_apply_session_for_job(repo=repo, job_id="job-1")

    repo.upsert_rows.assert_not_called()
