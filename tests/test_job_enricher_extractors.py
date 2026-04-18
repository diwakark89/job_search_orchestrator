from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from job_enricher.client_copilot import CopilotBatchExtractionInput
from job_enricher.extractors import build_enriched_row, enrich_job_row, enrich_job_rows


class _FakeCopilotClient:
    def __init__(self, payload: dict, success: bool = True, error: str | None = None) -> None:
        self.payload = payload
        self.success = success
        self.error = error
        self.batch_size = 20
        self.batch_calls: list[list[str]] = []

    def extract_from_description(self, description: str):
        return SimpleNamespace(
            success=self.success,
            data=self.payload if self.success else None,
            error=self.error,
        )

    def extract_from_descriptions(self, items: list[CopilotBatchExtractionInput]):
        self.batch_calls.append([item.row_id for item in items])
        return [
            SimpleNamespace(
                row_id=item.row_id,
                success=self.success,
                data=self.payload if self.success else None,
                error=self.error,
            )
            for item in items
        ]


def test_build_enriched_row_normalizes_fields() -> None:
    row = build_enriched_row(
        row_id="aaaaaaaa-0000-0000-0000-000000000001",
        payload={
            "tech_stack": ["js", "ReactJS", "node", "react"],
            "experience_level": "senior",
            "work_mode": "hybrid",
        },
    )

    assert row["tech_stack"] == ["JavaScript", "React", "Node.js"]
    assert row["experience_level"] == "Senior"
    assert row["work_mode"] == "hybrid"


def test_enrich_job_row_success() -> None:
    client = _FakeCopilotClient(
        payload={
            "tech_stack": ["python", "postgres"],
            "experience_level": "Lead",
            "work_mode": "remote",
        }
    )
    row, error = enrich_job_row(
        copilot_client=client,
        job_row={"id": "aaaaaaaa-0000-0000-0000-000000000002", "description": "some jd"},
    )
    assert error is None
    assert row is not None
    assert row["id"] == "aaaaaaaa-0000-0000-0000-000000000002"


def test_enrich_job_row_missing_description() -> None:
    client = _FakeCopilotClient(payload={})
    row, error = enrich_job_row(
        copilot_client=client,
        job_row={"id": "aaaaaaaa-0000-0000-0000-000000000003", "description": ""},
    )
    assert row is None
    assert error == "jobs_final row missing description"


def test_enrich_job_row_model_failure() -> None:
    client = _FakeCopilotClient(payload={}, success=False, error="rate limit")
    row, error = enrich_job_row(
        copilot_client=client,
        job_row={"id": "aaaaaaaa-0000-0000-0000-000000000004", "description": "jd"},
    )
    assert row is None
    assert error == "rate limit"


def test_enrich_job_rows_batches_and_skips_missing_description() -> None:
    client = _FakeCopilotClient(
        payload={
            "tech_stack": ["python", "postgres"],
            "experience_level": "Senior",
            "work_mode": "remote",
        }
    )

    results = enrich_job_rows(
        copilot_client=client,
        job_rows=[
            {"id": "aaaaaaaa-0000-0000-0000-000000000005", "description": "some jd"},
            {"id": "aaaaaaaa-0000-0000-0000-000000000006", "description": ""},
            {"id": "aaaaaaaa-0000-0000-0000-000000000007", "description": "another jd"},
        ],
    )

    assert client.batch_calls == [[
        "aaaaaaaa-0000-0000-0000-000000000005",
        "aaaaaaaa-0000-0000-0000-000000000007",
    ]]
    assert len(results) == 3
    assert sum(1 for result in results if result.enriched_row is not None) == 2
    skipped = [result for result in results if result.skipped]
    assert len(skipped) == 1
    assert skipped[0].row_id == "aaaaaaaa-0000-0000-0000-000000000006"
    assert skipped[0].error == "jobs_final row missing description"
