from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from automation_sessions.cli import app
from common.client import OperationResult


runner = CliRunner()


def _ok(operation: str, row_count: int = 1, data: object | None = None) -> OperationResult:
    return OperationResult(
        success=True,
        status_code=200,
        table="automation_sessions",
        operation=operation,
        row_count=row_count,
        data=data,
    )


def test_cli_create_upserts_payload() -> None:
    repo = MagicMock()
    repo.upsert_rows.return_value = _ok(operation="upsert")

    with (
        patch("automation_sessions.cli.load_config", MagicMock(return_value=object())),
        patch("automation_sessions.cli.PostgrestClient", MagicMock(return_value=object())),
        patch("automation_sessions.cli.SupabaseRepository", MagicMock(return_value=repo)),
    ):
        payload = json.dumps(
            {
                "job_id": "bbbbbbbb-0000-0000-0000-000000000001",
                "automation_type": "JOB_APPLY",
                "session_status": "RUNNING",
            }
        )
        result = runner.invoke(app, ["create", "--payload", payload])

    assert result.exit_code == 0
    repo.upsert_rows.assert_called_once_with(
        table="automation_sessions",
        rows=[
            {
                "job_id": "bbbbbbbb-0000-0000-0000-000000000001",
                "automation_type": "JOB_APPLY",
                "session_status": "RUNNING",
            }
        ],
        on_conflict="id",
    )


def test_cli_list_forwards_filters_and_sorting() -> None:
    repo = MagicMock()
    repo.select_rows.return_value = _ok(
        operation="select",
        row_count=1,
        data=[{"id": "aaaaaaaa-0000-0000-0000-000000000001", "session_status": "RUNNING"}],
    )

    with (
        patch("automation_sessions.cli.load_config", MagicMock(return_value=object())),
        patch("automation_sessions.cli.PostgrestClient", MagicMock(return_value=object())),
        patch("automation_sessions.cli.SupabaseRepository", MagicMock(return_value=repo)),
    ):
        result = runner.invoke(
            app,
            [
                "list",
                "--filter",
                "session_status=RUNNING",
                "--limit",
                "10",
                "--order-by",
                "updated_at",
                "--descending",
            ],
        )

    assert result.exit_code == 0
    repo.select_rows.assert_called_once_with(
        table="automation_sessions",
        columns="*",
        filters={"session_status": "RUNNING"},
        limit=10,
        offset=0,
        order_by="updated_at",
        ascending=False,
    )


def test_cli_patch_updates_by_id() -> None:
    repo = MagicMock()
    repo.patch_rows.return_value = _ok(operation="patch")

    with (
        patch("automation_sessions.cli.load_config", MagicMock(return_value=object())),
        patch("automation_sessions.cli.PostgrestClient", MagicMock(return_value=object())),
        patch("automation_sessions.cli.SupabaseRepository", MagicMock(return_value=repo)),
    ):
        result = runner.invoke(
            app,
            [
                "patch",
                "--id",
                "aaaaaaaa-0000-0000-0000-000000000001",
                "--payload",
                '{"session_status":"WAITING_USER","current_step":"FINAL_REVIEW"}',
            ],
        )

    assert result.exit_code == 0
    repo.patch_rows.assert_called_once_with(
        table="automation_sessions",
        payload={"session_status": "WAITING_USER", "current_step": "FINAL_REVIEW"},
        filters={"id": "aaaaaaaa-0000-0000-0000-000000000001"},
        operator="eq",
    )


def test_cli_delete_uses_idempotent_default() -> None:
    repo = MagicMock()
    repo.delete_rows.return_value = _ok(operation="delete")

    with (
        patch("automation_sessions.cli.load_config", MagicMock(return_value=object())),
        patch("automation_sessions.cli.PostgrestClient", MagicMock(return_value=object())),
        patch("automation_sessions.cli.SupabaseRepository", MagicMock(return_value=repo)),
    ):
        result = runner.invoke(app, ["delete", "--id", "aaaaaaaa-0000-0000-0000-000000000001"])

    assert result.exit_code == 0
    repo.delete_rows.assert_called_once_with(
        table="automation_sessions",
        filters={"id": "aaaaaaaa-0000-0000-0000-000000000001"},
        treat_404_as_success=True,
    )
