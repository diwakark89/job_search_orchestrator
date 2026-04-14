from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from job_enricher.extractors import build_enriched_row, enrich_job_row


class _FakeCopilotClient:
    def __init__(self, payload: dict, success: bool = True, error: str | None = None) -> None:
        self.payload = payload
        self.success = success
        self.error = error

    def extract_from_description(self, description: str):
        return type(
            "Result",
            (),
            {"success": self.success, "data": self.payload if self.success else None, "error": self.error},
        )()


def test_build_enriched_row_normalizes_fields() -> None:
    row = build_enriched_row(
        job_id="aaaaaaaa-0000-0000-0000-000000000001",
        payload={
            "tech_stack": ["js", "ReactJS", "node", "react"],
            "experience_level": "senior",
            "remote_type": "hybrid",
            "visa_sponsorship": "yes",
            "english_friendly": "no",
        },
    )

    assert row["tech_stack"] == ["JavaScript", "React", "Node.js"]
    assert row["experience_level"] == "Senior"
    assert row["remote_type"] == "Hybrid"
    assert row["visa_sponsorship"] is True
    assert row["english_friendly"] is False


def test_enrich_job_row_success() -> None:
    client = _FakeCopilotClient(
        payload={
            "tech_stack": ["python", "postgres"],
            "experience_level": "Lead",
            "remote_type": "Remote",
            "visa_sponsorship": False,
            "english_friendly": True,
        }
    )
    row, error = enrich_job_row(
        copilot_client=client,
        job_row={"job_id": "aaaaaaaa-0000-0000-0000-000000000002", "description": "some jd"},
    )
    assert error is None
    assert row is not None
    assert row["job_id"] == "aaaaaaaa-0000-0000-0000-000000000002"


def test_enrich_job_row_missing_description() -> None:
    client = _FakeCopilotClient(payload={})
    row, error = enrich_job_row(
        copilot_client=client,
        job_row={"job_id": "aaaaaaaa-0000-0000-0000-000000000003", "description": ""},
    )
    assert row is None
    assert error == "jobs_final row missing description"


def test_enrich_job_row_model_failure() -> None:
    client = _FakeCopilotClient(payload={}, success=False, error="rate limit")
    row, error = enrich_job_row(
        copilot_client=client,
        job_row={"job_id": "aaaaaaaa-0000-0000-0000-000000000004", "description": "jd"},
    )
    assert row is None
    assert error == "rate limit"
