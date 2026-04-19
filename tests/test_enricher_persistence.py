"""Unit tests for service.enricher_persistence.patch_enriched_rows."""
from __future__ import annotations

from unittest.mock import MagicMock

from common.client import OperationResult
from service.enricher_persistence import patch_enriched_rows


def _row(row_id: str = "id-1", **overrides):
    base = {"id": row_id, "company_name": "Acme"}
    base.update(overrides)
    return base


class TestPatchEnrichedRows:
    def test_empty_input_is_noop(self) -> None:
        repo = MagicMock()
        persisted, batches, reported = patch_enriched_rows(
            repo=repo,
            enriched_rows=[],
            success_ids=[],
            failed_ids=[],
            errors=[],
            set_job_status_enriched=True,
            target_job_status="ENRICHED",
        )
        assert persisted == []
        assert batches == 0
        assert reported == 0
        repo.upsert_rows.assert_not_called()

    def test_success_sets_status_when_requested(self) -> None:
        repo = MagicMock()
        repo.upsert_rows.return_value = OperationResult(True, 200, "jobs_final", "upsert", 1)
        persisted, batches, reported = patch_enriched_rows(
            repo=repo,
            enriched_rows=[_row("id-1")],
            success_ids=["id-1"],
            failed_ids=[],
            errors=[],
            set_job_status_enriched=True,
            target_job_status="ENRICHED",
        )
        assert persisted == ["id-1"]
        assert batches == 1
        assert reported == 1
        kwargs = repo.upsert_rows.call_args.kwargs
        assert kwargs["table"] == "jobs_final"
        assert kwargs["on_conflict"] == "id"
        assert kwargs["rows"][0]["job_status"] == "ENRICHED"

    def test_does_not_set_status_when_disabled(self) -> None:
        repo = MagicMock()
        repo.upsert_rows.return_value = OperationResult(True, 200, "jobs_final", "upsert", 1)
        patch_enriched_rows(
            repo=repo,
            enriched_rows=[_row("id-1")],
            success_ids=["id-1"],
            failed_ids=[],
            errors=[],
            set_job_status_enriched=False,
            target_job_status="ENRICHED",
        )
        kwargs = repo.upsert_rows.call_args.kwargs
        assert "job_status" not in kwargs["rows"][0]

    def test_does_not_mutate_input_rows(self) -> None:
        repo = MagicMock()
        repo.upsert_rows.return_value = OperationResult(True, 200, "jobs_final", "upsert", 1)
        original = _row("id-1")
        patch_enriched_rows(
            repo=repo,
            enriched_rows=[original],
            success_ids=["id-1"],
            failed_ids=[],
            errors=[],
            set_job_status_enriched=True,
            target_job_status="ENRICHED",
        )
        assert "job_status" not in original

    def test_failure_mutates_failed_ids_and_errors(self) -> None:
        repo = MagicMock()
        repo.upsert_rows.return_value = OperationResult(
            False, 500, "jobs_final", "upsert", 0, error="db down"
        )
        failed_ids: list[str] = []
        errors: list[str] = []
        persisted, batches, reported = patch_enriched_rows(
            repo=repo,
            enriched_rows=[_row("id-1"), _row("id-2")],
            success_ids=["id-1", "id-2"],
            failed_ids=failed_ids,
            errors=errors,
            set_job_status_enriched=True,
            target_job_status="ENRICHED",
        )
        assert persisted == []
        assert batches == 1
        assert reported == 0
        assert failed_ids == ["id-1", "id-2"]
        assert len(errors) == 2
        assert all("failed to persist" in e for e in errors)
