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
    delete_jobs_final_by_job_id,
    delete_jobs_raw_by_id,
    insert_job_decisions,
    insert_shared_links,
    patch_job_metrics,
    soft_delete_jobs_final,
    soft_delete_jobs_raw,
    upsert_job_approvals,
    upsert_jobs_enriched,
    upsert_jobs_final,
    upsert_jobs_raw,
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
    VALID_JF_ROW = {"job_id": "aaaaaaaa-0000-0000-0000-000000000001"}

    def test_calls_upsert_with_correct_conflict_key(self):
        client = _mock_client(_ok())
        repo = SupabaseRepository(client)
        result = repo.upsert_rows("jobs_final", [self.VALID_JF_ROW])
        client.upsert.assert_called_once()
        _, kwargs = client.upsert.call_args
        assert kwargs["on_conflict"] == "job_id"
        assert result.success is True

    def test_jobs_raw_defaults_conflict_to_job_url(self):
        client = _mock_client(_ok(table="jobs_raw"))
        repo = SupabaseRepository(client)
        rows = [{"company_name": "Acme", "role_title": "Dev", "job_url": "https://example.com/1"}]
        repo.upsert_rows("jobs_raw", rows)
        client.upsert.assert_called_once()

    def test_unsupported_table_raises(self):
        repo = SupabaseRepository(_mock_client(_ok()))
        with pytest.raises(ValueError, match="Unsupported table"):
            repo.upsert_rows("nonexistent_table", [{"job_id": "x"}])

    def test_shared_links_defaults_conflict_to_url(self):
        client = _mock_client(_ok())
        repo = SupabaseRepository(client)
        repo.upsert_rows("shared_links", [{"url": "https://example.com"}])
        _, kwargs = client.upsert.call_args
        assert kwargs["on_conflict"] == "url"

    def test_invalid_payload_raises_before_network_call(self):
        client = _mock_client(_ok())
        repo = SupabaseRepository(client)
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000002", "job_status": "GARBAGE"}]
        with pytest.raises(Exception):
            repo.upsert_rows("jobs_final", rows)
        client.upsert.assert_not_called()

    def test_job_metrics_raises(self):
        client = _mock_client(_ok())
        repo = SupabaseRepository(client)
        with pytest.raises(ValueError, match="job_metrics"):
            repo.upsert_rows("job_metrics", [{"total_scraped": 5}])


class TestRepositoryInsertRows:
    def test_shared_links_insert_called(self):
        client = _mock_client(_ok(table="shared_links", operation="insert"))
        repo = SupabaseRepository(client)
        rows = [{"url": "https://linkedin.com/jobs/view/999"}]
        result = repo.insert_rows("shared_links", rows)
        client.insert.assert_called_once()
        assert result.success is True

    def test_invalid_shared_link_raises_before_call(self):
        client = _mock_client(_ok())
        repo = SupabaseRepository(client)
        rows = [{"url": "https://example.com", "source": "bad-source"}]
        with pytest.raises(Exception):
            repo.insert_rows("shared_links", rows)
        client.insert.assert_not_called()


class TestRepositoryPatchRows:
    def test_patch_called_with_filters(self):
        client = _mock_client(_ok(operation="patch"))
        repo = SupabaseRepository(client)
        result = repo.patch_rows("jobs_final", {"job_status": "Applied"}, {"job_id": "abc"})
        client.patch.assert_called_once()
        assert result.success is True

    def test_job_metrics_payload_validated(self):
        client = _mock_client(_ok(table="job_metrics", operation="patch"))
        repo = SupabaseRepository(client)
        repo.patch_rows("job_metrics", {"total_scraped": 100}, {"id": 1})
        client.patch.assert_called_once()

    def test_job_metrics_negative_counter_raises(self):
        client = _mock_client(_ok())
        repo = SupabaseRepository(client)
        with pytest.raises(Exception):
            repo.patch_rows("job_metrics", {"total_scraped": -5}, {"id": 1})
        client.patch.assert_not_called()


class TestRepositoryDeleteRows:
    def test_delete_called_with_filters(self):
        client = _mock_client(_ok(operation="delete"))
        repo = SupabaseRepository(client)
        result = repo.delete_rows("jobs_final", {"job_id": "abc"})
        client.delete.assert_called_once()
        assert result.success is True

    def test_treat_404_as_success_forwarded(self):
        client = _mock_client(_ok(operation="delete"))
        repo = SupabaseRepository(client)
        repo.delete_rows("jobs_final", {"job_id": "abc"}, treat_404_as_success=True)
        _, kwargs = client.delete.call_args
        assert kwargs["treat_404_as_success"] is True


class TestTableWrappers:
    def test_upsert_jobs_final(self):
        repo = _mock_repo(_ok())
        result = upsert_jobs_final(repo, [{"job_id": "aaaaaaaa-0000-0000-0000-000000000001"}])
        repo.upsert_rows.assert_called_once_with(
            table="jobs_final",
            rows=[{"job_id": "aaaaaaaa-0000-0000-0000-000000000001"}],
            on_conflict="job_id",
        )
        assert result.success is True

    def test_insert_shared_links(self):
        repo = _mock_repo(_ok(table="shared_links", operation="upsert"))
        result = insert_shared_links(repo, [{"url": "https://example.com/job/1"}])
        repo.upsert_rows.assert_called_once_with(
            table="shared_links",
            rows=[{"url": "https://example.com/job/1"}],
            on_conflict="url",
        )
        assert result.success is True

    def test_upsert_jobs_raw(self):
        repo = _mock_repo(_ok(table="jobs_raw"))
        upsert_jobs_raw(repo, [{"company_name": "X", "role_title": "Y", "job_url": "https://x.com/1"}])
        repo.upsert_rows.assert_called_once_with(
            table="jobs_raw",
            rows=[{"company_name": "X", "role_title": "Y", "job_url": "https://x.com/1"}],
            on_conflict="job_url",
        )

    def test_upsert_jobs_enriched(self):
        repo = _mock_repo(_ok(table="jobs_enriched"))
        upsert_jobs_enriched(repo, [{"job_id": "aaaaaaaa-0000-0000-0000-000000000001"}])
        repo.upsert_rows.assert_called_once_with(
            table="jobs_enriched",
            rows=[{"job_id": "aaaaaaaa-0000-0000-0000-000000000001"}],
            on_conflict="job_id",
        )

    def test_insert_job_decisions_valid(self):
        repo = _mock_repo(_ok(table="job_decisions", operation="insert"))
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000001", "decision": "AUTO_APPROVE"}]
        insert_job_decisions(repo, rows)
        repo.insert_rows.assert_called_once_with(table="job_decisions", rows=rows)

    def test_upsert_job_approvals_valid(self):
        repo = _mock_repo(_ok(table="job_approvals"))
        rows = [{"job_id": "a", "decision_id": "b", "user_action": "APPROVED"}]
        upsert_job_approvals(repo, rows)
        repo.upsert_rows.assert_called_once_with(table="job_approvals", rows=rows, on_conflict="decision_id")

    def test_patch_job_metrics(self):
        repo = _mock_repo(_ok(table="job_metrics", operation="patch"))
        result = patch_job_metrics(repo, {"total_scraped": 200})
        repo.patch_rows.assert_called_once_with(table="job_metrics", payload={"total_scraped": 200}, filters={"id": 1})
        assert result.success is True

    def test_delete_jobs_final_by_job_id(self):
        repo = _mock_repo(_ok(operation="delete"))
        delete_jobs_final_by_job_id(repo, "aaaaaaaa-0000-0000-0000-000000000001")
        repo.delete_rows.assert_called_once_with(
            table="jobs_final",
            filters={"job_id": "aaaaaaaa-0000-0000-0000-000000000001"},
            treat_404_as_success=True,
        )

    def test_delete_jobs_raw_by_id(self):
        repo = _mock_repo(_ok(table="jobs_raw", operation="delete"))
        delete_jobs_raw_by_id(repo, "aaaaaaaa-0000-0000-0000-000000000001")
        repo.delete_rows.assert_called_once_with(
            table="jobs_raw",
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

    def test_soft_delete_raw_sets_is_deleted(self):
        repo = _mock_repo(_ok(table="jobs_raw", operation="patch"))
        soft_delete_jobs_raw(repo, "aaaaaaaa-0000-0000-0000-000000000001", hard_delete=False)
        repo.patch_rows.assert_called_once()
        repo.delete_rows.assert_not_called()

    def test_soft_delete_raw_with_hard_delete(self):
        repo = _mock_repo(_ok(table="jobs_raw", operation="patch"))
        repo.delete_rows = MagicMock(return_value=_ok(table="jobs_raw", operation="delete"))
        soft_delete_jobs_raw(repo, "aaaaaaaa-0000-0000-0000-000000000001", hard_delete=True)
        repo.patch_rows.assert_called_once()
        repo.delete_rows.assert_called_once()
