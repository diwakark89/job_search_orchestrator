"""Unit tests for the ingest stage validators and orchestrator."""
from __future__ import annotations

from unittest.mock import MagicMock

from common.client import OperationResult
from service.stages.ingest import _validate_and_map_ingest_row, run_stage_ingest


def _scrape_row(**overrides):
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "job_url": "https://example.com/jobs/1",
        "site": "linkedin",
        "title": "Senior Engineer",
        "company": "Acme",
        "scraped_at": "2026-01-01T00:00:00Z",
        "description": "We are hiring.",
    }
    base.update(overrides)
    return base


def _persisted_row(**overrides):
    base = {
        "id": "22222222-2222-2222-2222-222222222222",
        "job_url": "https://example.com/jobs/2",
        "company_name": "Acme",
        "role_title": "SWE",
    }
    base.update(overrides)
    return base


class TestValidateAndMapIngestRow:
    def test_scrape_row_gets_mapped(self) -> None:
        normalised, error = _validate_and_map_ingest_row(_scrape_row(), 0)
        assert error is None
        assert normalised is not None
        assert normalised["job_status"] == "SCRAPED"
        assert normalised["job_url"] == "https://example.com/jobs/1"

    def test_persisted_row_passes_through(self) -> None:
        normalised, error = _validate_and_map_ingest_row(_persisted_row(), 0)
        assert error is None
        assert normalised is not None
        assert normalised["job_status"] == "SCRAPED"

    def test_existing_job_status_preserved(self) -> None:
        row = _persisted_row(job_status="ENRICHED")
        normalised, error = _validate_and_map_ingest_row(row, 0)
        assert error is None
        assert normalised is not None
        assert normalised["job_status"] == "ENRICHED"

    def test_missing_job_url_rejected(self) -> None:
        row = _persisted_row()
        del row["job_url"]
        normalised, error = _validate_and_map_ingest_row(row, 7)
        assert normalised is None
        assert error is not None
        assert error.startswith("row[7]:")
        assert "job_url" in error

    def test_blank_job_url_rejected(self) -> None:
        normalised, error = _validate_and_map_ingest_row(_persisted_row(job_url="   "), 0)
        assert normalised is None
        assert error is not None and "job_url" in error


class TestRunStageIngest:
    def test_no_valid_rows_short_circuits(self) -> None:
        repo = MagicMock()
        bad = _persisted_row()
        del bad["job_url"]
        result = run_stage_ingest(repo=repo, rows=[bad])
        assert result.success is False
        assert result.processed == 0
        assert len(result.errors) == 1
        repo.upsert_rows.assert_not_called()

    def test_upserts_valid_rows(self) -> None:
        repo = MagicMock()
        repo.upsert_rows.return_value = OperationResult(True, 201, "jobs_final", "upsert", 2)
        result = run_stage_ingest(repo=repo, rows=[_persisted_row(), _scrape_row()])
        assert result.success is True
        assert result.processed == 2
        repo.upsert_rows.assert_called_once()
        kwargs = repo.upsert_rows.call_args.kwargs
        assert kwargs["table"] == "jobs_final"
        assert kwargs["on_conflict"] == "job_url"

    def test_upsert_failure_returns_error(self) -> None:
        repo = MagicMock()
        repo.upsert_rows.return_value = OperationResult(False, 500, "jobs_final", "upsert", 0, error="db down")
        result = run_stage_ingest(repo=repo, rows=[_persisted_row()])
        assert result.success is False
        assert result.processed == 0
        assert any("db down" in e for e in result.errors)

    def test_partial_validation_errors_collected(self) -> None:
        repo = MagicMock()
        repo.upsert_rows.return_value = OperationResult(True, 201, "jobs_final", "upsert", 1)
        bad = _persisted_row()
        del bad["job_url"]
        result = run_stage_ingest(repo=repo, rows=[_persisted_row(), bad])
        assert result.success is True
        assert result.processed == 1
        assert len(result.errors) == 1
