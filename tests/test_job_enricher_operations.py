from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.client import OperationResult
from service.enricher import enrich_jobs


class _FakeCopilotClient:
    def extract_from_description(self, description: str):
        if "bad" in description:
            return type("Result", (), {"success": False, "data": None, "error": "bad output"})()
        return type(
            "Result",
            (),
            {
                "success": True,
                "data": {
                    "tech_stack": ["python", "postgres"],
                    "experience_level": "Senior",
                    "remote_type": "Remote",
                },
                "error": None,
            },
        )()


def _ok(table: str, operation: str, data=None) -> OperationResult:
    return OperationResult(success=True, status_code=200, table=table, operation=operation, row_count=0, data=data)


def test_enrich_jobs_dry_run_counts() -> None:
    repo = MagicMock()
    repo.select_rows.return_value = _ok(
        "jobs_final",
        "select",
        [
            {"id": "id-1", "description": "good description", "job_status": "SCRAPED", "is_deleted": False},
            {"id": "id-2", "description": "", "job_status": "SCRAPED", "is_deleted": False},
            {"id": "id-3", "description": "bad description", "job_status": "SCRAPED", "is_deleted": False},
        ],
    )

    summary = enrich_jobs(repo=repo, copilot_client=_FakeCopilotClient(), limit=10, dry_run=True)
    assert summary.processed.count == 3
    assert summary.enriched.count == 1
    assert summary.enriched.ids == ["id-1"]
    assert summary.skipped.count == 1
    assert summary.skipped.ids == ["id-2"]
    assert summary.failed.count == 1
    assert summary.failed.ids == ["id-3"]


def test_enrich_jobs_write_patches_jobs_final() -> None:
    repo = MagicMock()
    repo.select_rows.return_value = _ok(
        "jobs_final",
        "select",
        [{"id": "id-1", "description": "good description", "job_status": "SCRAPED", "is_deleted": False}],
    )
    repo.patch_rows.return_value = OperationResult(True, 204, "jobs_final", "patch", 1)

    summary = enrich_jobs(repo=repo, copilot_client=_FakeCopilotClient(), limit=10, dry_run=False)
    assert summary.enriched.count == 1
    assert summary.enriched.ids == ["id-1"]
    assert summary.failed.count == 0
    repo.patch_rows.assert_called_once()
    call_kwargs = repo.patch_rows.call_args.kwargs
    assert call_kwargs["table"] == "jobs_final"
    assert call_kwargs["payload"]["job_status"] == "ENRICHED"
    assert call_kwargs["filters"] == {"id": "id-1"}


def test_enrich_jobs_patch_failure_records_error() -> None:
    repo = MagicMock()
    repo.select_rows.return_value = _ok(
        "jobs_final",
        "select",
        [{"id": "id-1", "description": "good description", "job_status": "SCRAPED", "is_deleted": False}],
    )
    repo.patch_rows.return_value = OperationResult(False, 500, "jobs_final", "patch", 0, error="DB error")

    summary = enrich_jobs(repo=repo, copilot_client=_FakeCopilotClient(), limit=10, dry_run=False)
    assert summary.enriched.count == 0
    assert summary.failed.count == 1
    assert "id-1" in summary.failed.ids
    assert any("failed to patch" in e for e in summary.errors)
