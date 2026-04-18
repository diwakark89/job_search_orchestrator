from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.client import OperationResult
from service.enricher import enrich_jobs, enrich_jobs_by_ids


class _FakeCopilotClient:
    def __init__(self) -> None:
        self.batch_size = 20
        self.batch_calls: list[list[str]] = []

    def extract_from_description(self, description: str):
        if "bad" in description:
            return SimpleNamespace(success=False, data=None, error="bad output")
        return SimpleNamespace(
            success=True,
            data={
                "tech_stack": ["python", "postgres"],
                "experience_level": "Senior",
                "remote_type": "Remote",
            },
            error=None,
        )

    def extract_from_descriptions(self, items):
        self.batch_calls.append([item.row_id for item in items])
        results = []
        for item in items:
            if "bad" in item.description:
                results.append(SimpleNamespace(row_id=item.row_id, success=False, data=None, error="bad output"))
                continue
            results.append(
                SimpleNamespace(
                    row_id=item.row_id,
                    success=True,
                    data={
                        "tech_stack": ["python", "postgres"],
                        "experience_level": "Senior",
                        "remote_type": "Remote",
                    },
                    error=None,
                )
            )
        return results


def _ok(table: str, operation: str, data=None) -> OperationResult:
    return OperationResult(success=True, status_code=200, table=table, operation=operation, row_count=0, data=data)


def _fake_client() -> Any:
    return _FakeCopilotClient()


def test_enrich_jobs_dry_run_counts() -> None:
    repo = MagicMock()
    client = _fake_client()
    repo.select_rows.return_value = _ok(
        "jobs_final",
        "select",
        [
            {"id": "id-1", "description": "good description", "job_status": "SCRAPED", "is_deleted": False},
            {"id": "id-2", "description": "", "job_status": "SCRAPED", "is_deleted": False},
            {"id": "id-3", "description": "bad description", "job_status": "SCRAPED", "is_deleted": False},
        ],
    )

    summary = enrich_jobs(repo=repo, copilot_client=client, limit=10, dry_run=True)
    assert summary.processed.count == 3
    assert summary.enriched.count == 1
    assert summary.enriched.ids == ["id-1"]
    assert summary.skipped.count == 1
    assert summary.skipped.ids == ["id-2"]
    assert summary.failed.count == 1
    assert summary.failed.ids == ["id-3"]
    assert client.batch_calls == [["id-1", "id-3"]]
    assert summary.copilot_batches_sent == 1
    assert summary.database_batches_sent == 0
    assert summary.database_rows_reported == 0


def test_enrich_jobs_write_patches_jobs_final() -> None:
    repo = MagicMock()
    client = _fake_client()
    repo.select_rows.return_value = _ok(
        "jobs_final",
        "select",
        [{"id": "id-1", "description": "good description", "job_status": "SCRAPED", "is_deleted": False}],
    )
    repo.upsert_rows.return_value = OperationResult(True, 204, "jobs_final", "upsert", 1)

    summary = enrich_jobs(repo=repo, copilot_client=client, limit=10, dry_run=False)
    assert summary.enriched.count == 1
    assert summary.enriched.ids == ["id-1"]
    assert summary.failed.count == 0
    assert summary.copilot_batches_sent == 1
    assert summary.database_batches_sent == 1
    assert summary.database_rows_reported == 1
    repo.upsert_rows.assert_called_once()
    call_kwargs = repo.upsert_rows.call_args.kwargs
    assert call_kwargs["table"] == "jobs_final"
    assert call_kwargs["on_conflict"] == "id"
    assert call_kwargs["rows"] == [{
        "id": "id-1",
        "tech_stack": ["Python", "PostgreSQL"],
        "experience_level": "Senior",
        "remote_type": "Remote",
        "job_status": "ENRICHED",
    }]


def test_enrich_jobs_patch_failure_records_error() -> None:
    repo = MagicMock()
    repo.select_rows.return_value = _ok(
        "jobs_final",
        "select",
        [{"id": "id-1", "description": "good description", "job_status": "SCRAPED", "is_deleted": False}],
    )
    repo.upsert_rows.return_value = OperationResult(False, 500, "jobs_final", "upsert", 0, error="DB error")

    summary = enrich_jobs(repo=repo, copilot_client=_fake_client(), limit=10, dry_run=False)
    assert summary.enriched.count == 0
    assert summary.failed.count == 1
    assert "id-1" in summary.failed.ids
    assert any("failed to persist" in e for e in summary.errors)
    assert summary.database_batches_sent == 1
    assert summary.database_rows_reported == 0


def test_enrich_jobs_by_ids_success_ignores_status_and_keeps_job_status() -> None:
    repo = MagicMock()
    client = _fake_client()
    repo.select_rows.return_value = _ok(
        "jobs_final",
        "select",
        [
            {"id": "id-1", "description": "good description", "job_status": "APPLIED", "is_deleted": False},
            {"id": "id-2", "description": "good description", "job_status": "SCRAPED", "is_deleted": False},
        ],
    )
    repo.upsert_rows.return_value = OperationResult(True, 204, "jobs_final", "upsert", 2)

    summary = enrich_jobs_by_ids(repo=repo, copilot_client=client, ids=["id-1", "id-2"])

    assert summary.processed.count == 2
    assert summary.processed.ids == ["id-1", "id-2"]
    assert summary.enriched.count == 2
    assert summary.enriched.ids == ["id-1", "id-2"]
    assert summary.failed.count == 0
    assert summary.copilot_batches_sent == 1
    assert summary.database_batches_sent == 1
    assert summary.database_rows_reported == 2
    repo.upsert_rows.assert_called_once()
    assert client.batch_calls == [["id-1", "id-2"]]

    rows = repo.upsert_rows.call_args.kwargs["rows"]
    assert all("job_status" not in row for row in rows)


def test_enrich_jobs_by_ids_missing_description_and_missing_id() -> None:
    repo = MagicMock()
    repo.select_rows.return_value = _ok(
        "jobs_final",
        "select",
        [{"id": "id-1", "description": "", "job_status": "APPLIED", "is_deleted": False}],
    )

    summary = enrich_jobs_by_ids(repo=repo, copilot_client=_fake_client(), ids=["id-1", "id-2"])

    assert summary.processed.count == 2
    assert summary.skipped.count == 1
    assert summary.skipped.ids == ["id-1"]
    assert summary.failed.count == 1
    assert summary.failed.ids == ["id-2"]
    assert summary.errors == ["id=id-2: jobs_final row not found or soft-deleted"]
    repo.upsert_rows.assert_not_called()


def test_enrich_jobs_by_ids_patch_failure_records_error() -> None:
    repo = MagicMock()
    repo.select_rows.return_value = _ok(
        "jobs_final",
        "select",
        [{"id": "id-1", "description": "good description", "job_status": "APPLIED", "is_deleted": False}],
    )
    repo.upsert_rows.return_value = OperationResult(False, 500, "jobs_final", "upsert", 0, error="DB error")

    summary = enrich_jobs_by_ids(repo=repo, copilot_client=_fake_client(), ids=["id-1"])

    assert summary.enriched.count == 0
    assert summary.failed.count == 1
    assert summary.failed.ids == ["id-1"]
    assert summary.errors == ["id=id-1: failed to persist enrichment data"]
    assert summary.database_batches_sent == 1
    assert summary.database_rows_reported == 0


def test_enrich_jobs_by_ids_requires_at_least_one_id() -> None:
    repo = MagicMock()

    with pytest.raises(ValueError, match="At least one id is required"):
        enrich_jobs_by_ids(repo=repo, copilot_client=_fake_client(), ids=[])


def test_enrich_jobs_by_ids_dry_run_skips_patch() -> None:
    repo = MagicMock()
    repo.select_rows.return_value = _ok(
        "jobs_final",
        "select",
        [{"id": "id-1", "description": "good description", "job_status": "APPLIED", "is_deleted": False}],
    )

    summary = enrich_jobs_by_ids(repo=repo, copilot_client=_fake_client(), ids=["id-1"], dry_run=True)

    assert summary.processed.count == 1
    assert summary.enriched.count == 1
    assert summary.enriched.ids == ["id-1"]
    assert summary.copilot_batches_sent == 1
    assert summary.database_batches_sent == 0
    assert summary.database_rows_reported == 0
    repo.upsert_rows.assert_not_called()


def test_enrich_jobs_by_ids_can_set_job_status_enriched() -> None:
    repo = MagicMock()
    client = _fake_client()
    repo.select_rows.return_value = _ok(
        "jobs_final",
        "select",
        [{"id": "id-1", "description": "good description", "job_status": "SCRAPED", "is_deleted": False}],
    )
    repo.upsert_rows.return_value = OperationResult(True, 204, "jobs_final", "upsert", 1)

    summary = enrich_jobs_by_ids(
        repo=repo,
        copilot_client=client,
        ids=["id-1"],
        set_job_status_enriched=True,
    )

    assert summary.enriched.count == 1
    assert summary.enriched.ids == ["id-1"]
    repo.upsert_rows.assert_called_once()
    assert repo.upsert_rows.call_args.kwargs["rows"] == [{
        "id": "id-1",
        "tech_stack": ["Python", "PostgreSQL"],
        "experience_level": "Senior",
        "remote_type": "Remote",
        "job_status": "ENRICHED",
    }]
