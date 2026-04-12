from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

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
                    "visa_sponsorship": False,
                    "english_friendly": True,
                },
                "error": None,
            },
        )()


def _ok(table: str, operation: str, data=None) -> OperationResult:
    return OperationResult(success=True, status_code=200, table=table, operation=operation, row_count=0, data=data)


def test_enrich_jobs_dry_run_filters_existing_and_counts() -> None:
    repo = MagicMock()
    repo.select_rows.return_value = _ok(
        "jobs_raw",
        "select",
        [
            {"id": "id-1", "description": "good description", "job_status": "SCRAPED", "is_deleted": False},
            {"id": "id-2", "description": "", "job_status": "SCRAPED", "is_deleted": False},
            {"id": "id-3", "description": "bad description", "job_status": "SCRAPED", "is_deleted": False},
        ],
    )
    repo.client.select.return_value = _ok("jobs_enriched", "select", [{"job_id": "id-3"}])

    summary = enrich_jobs(repo=repo, copilot_client=_FakeCopilotClient(), limit=10, dry_run=True)
    assert summary.processed == 2
    assert summary.enriched == 1
    assert summary.skipped == 1
    assert summary.failed == 0


def test_enrich_jobs_write_upserts_and_marks_stage() -> None:
    repo = MagicMock()
    repo.select_rows.return_value = _ok(
        "jobs_raw",
        "select",
        [{"id": "id-1", "description": "good description", "job_status": "SCRAPED", "is_deleted": False}],
    )
    repo.client.select.return_value = _ok("jobs_enriched", "select", [])
    repo.upsert_rows.return_value = OperationResult(True, 204, "jobs_enriched", "upsert", 1)
    repo.patch_rows.return_value = OperationResult(True, 204, "jobs_raw", "patch", 1)

    summary = enrich_jobs(repo=repo, copilot_client=_FakeCopilotClient(), limit=10, dry_run=False)
    assert summary.enriched == 1
    repo.upsert_rows.assert_called_once()
    repo.patch_rows.assert_called_once()
