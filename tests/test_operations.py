"""Unit tests for repository and service table operations."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.client import OperationResult, PostgrestClient
from common.config import SupabaseConfig
from repository.supabase import SupabaseRepository
from service.tables import (
    delete_jobs_final_by_id,
    soft_delete_jobs_final,
    upsert_jobs_final,
)


def _ok(table: str = "jobs_final", operation: str = "upsert", rows: int = 1) -> OperationResult:
    return OperationResult(success=True, status_code=204, table=table, operation=operation, row_count=rows)


def _err(table: str = "jobs_final", operation: str = "upsert") -> OperationResult:
    return OperationResult(
        success=False,
        status_code=422,
        table=table,
        operation=operation,
        row_count=0,
        error="Unprocessable Entity",
    )


def _mock_client(return_value: OperationResult) -> PostgrestClient:
    cfg = SupabaseConfig(url="https://test.supabase.co", api_key="test-key")
    client = PostgrestClient(config=cfg)
    for method_name in ("upsert", "insert", "patch", "delete", "select"):
        setattr(client, method_name, MagicMock(return_value=return_value))
    return client


def _mock_repo(result: OperationResult | None = None) -> SupabaseRepository:
    repo = SupabaseRepository(client=_mock_client(result or _ok()))
    repo.upsert_rows = MagicMock(return_value=result or _ok())
    repo.insert_rows = MagicMock(return_value=result or _ok(operation="insert"))
    repo.patch_rows = MagicMock(return_value=result or _ok(operation="patch"))
    repo.delete_rows = MagicMock(return_value=result or _ok(operation="delete"))
    repo.select_rows = MagicMock(return_value=result or _ok(operation="select"))
    return repo


class TestRepositoryUpsertRows:
    VALID_JF_ROW = {"id": "aaaaaaaa-0000-0000-0000-000000000001"}
    VALID_AUTOMATION_ROW = {
        "id": "aaaaaaaa-0000-0000-0000-000000000001",
        "job_id": "bbbbbbbb-0000-0000-0000-000000000001",
        "automation_type": "JOB_APPLY",
        "session_status": "RUNNING",
    }

    def test_calls_upsert_with_correct_conflict_key(self):
        client = _mock_client(_ok())
        repo = SupabaseRepository(client)
        result = repo.upsert_rows("jobs_final", [self.VALID_JF_ROW])
        client.upsert.assert_called_once()
        _, kwargs = client.upsert.call_args
        assert kwargs["on_conflict"] == "id"
        assert kwargs["rows"][0]["id"] == self.VALID_JF_ROW["id"]
        assert result.success is True

    def test_unsupported_table_raises(self):
        repo = SupabaseRepository(_mock_client(_ok()))
        with pytest.raises(ValueError, match="Unsupported table"):
            repo.upsert_rows("nonexistent_table", [{"id": "x"}])

    def test_invalid_payload_raises_before_network_call(self):
        client = _mock_client(_ok())
        repo = SupabaseRepository(client)
        rows = [{"id": "aaaaaaaa-0000-0000-0000-000000000002", "job_status": "GARBAGE"}]
        with pytest.raises(Exception):
            repo.upsert_rows("jobs_final", rows)
        client.upsert.assert_not_called()

    def test_automation_sessions_upsert_uses_id_conflict_key(self):
        client = _mock_client(_ok(table="automation_sessions"))
        repo = SupabaseRepository(client)
        result = repo.upsert_rows("automation_sessions", [self.VALID_AUTOMATION_ROW])
        client.upsert.assert_called_once()
        _, kwargs = client.upsert.call_args
        assert kwargs["on_conflict"] == "id"
        assert kwargs["rows"][0]["id"] == self.VALID_AUTOMATION_ROW["id"]
        assert kwargs["rows"][0]["automation_type"] == "JOB_APPLY"
        assert result.success is True

    def test_automation_sessions_invalid_status_raises_before_network_call(self):
        client = _mock_client(_ok(table="automation_sessions"))
        repo = SupabaseRepository(client)
        rows = [{"job_id": "bbbbbbbb-0000-0000-0000-000000000001", "automation_type": "JOB_APPLY", "session_status": "PAUSED"}]
        with pytest.raises(Exception):
            repo.upsert_rows("automation_sessions", rows)
        client.upsert.assert_not_called()



class TestRepositoryPatchRows:
    def test_patch_called_with_filters(self):
        client = _mock_client(_ok(operation="patch"))
        repo = SupabaseRepository(client)
        result = repo.patch_rows("jobs_final", {"job_status": "Applied"}, {"id": "abc"})
        client.patch.assert_called_once()
        assert result.success is True


class TestRepositoryDeleteRows:
    def test_delete_called_with_filters(self):
        client = _mock_client(_ok(operation="delete"))
        repo = SupabaseRepository(client)
        result = repo.delete_rows("jobs_final", {"id": "abc"})
        client.delete.assert_called_once()
        assert result.success is True

    def test_treat_404_as_success_forwarded(self):
        client = _mock_client(_ok(operation="delete"))
        repo = SupabaseRepository(client)
        repo.delete_rows("jobs_final", {"id": "abc"}, treat_404_as_success=True)
        _, kwargs = client.delete.call_args
        assert kwargs["treat_404_as_success"] is True


class TestTableWrappers:
    def test_upsert_jobs_final(self):
        repo = _mock_repo(_ok())
        result = upsert_jobs_final(repo, [{"id": "aaaaaaaa-0000-0000-0000-000000000001"}])
        repo.upsert_rows.assert_called_once_with(
            table="jobs_final",
            rows=[{"id": "aaaaaaaa-0000-0000-0000-000000000001"}],
            on_conflict="id",
        )
        assert result.success is True

    def test_delete_jobs_final_by_id(self):
        repo = _mock_repo(_ok(operation="delete"))
        delete_jobs_final_by_id(repo, "aaaaaaaa-0000-0000-0000-000000000001")
        repo.delete_rows.assert_called_once_with(
            table="jobs_final",
            filters={"id": "aaaaaaaa-0000-0000-0000-000000000001"},
            treat_404_as_success=True,
        )


class TestSoftDelete:
    def test_soft_delete_final_sets_is_deleted(self):
        repo = _mock_repo(_ok(operation="patch"))
        soft_delete_jobs_final(repo, "aaaaaaaa-0000-0000-0000-000000000001", hard_delete=False)
        repo.patch_rows.assert_called_once()
        repo.delete_rows.assert_not_called()

    def test_soft_delete_final_with_hard_delete_calls_both(self):
        repo = _mock_repo(_ok(operation="patch"))
        repo.delete_rows = MagicMock(return_value=_ok(operation="delete"))
        soft_delete_jobs_final(repo, "aaaaaaaa-0000-0000-0000-000000000001", hard_delete=True)
        repo.patch_rows.assert_called_once()
        repo.delete_rows.assert_called_once()

    def test_soft_delete_final_hard_delete_skipped_on_patch_failure(self):
        repo = _mock_repo(_ok(operation="patch"))
        repo.patch_rows = MagicMock(return_value=_err(operation="patch"))
        repo.delete_rows = MagicMock()
        soft_delete_jobs_final(repo, "abc", hard_delete=True)
        repo.delete_rows.assert_not_called()
