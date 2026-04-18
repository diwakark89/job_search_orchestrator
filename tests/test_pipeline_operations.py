from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pipeline.models import StageResult
from common.client import OperationResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_ROW = {
    "company_name": "Acme Corp",
    "role_title": "Backend Engineer",
    "job_url": "https://example.com/jobs/1",
    "description": "Build APIs.",
    "job_type": "fulltime",
    "work_mode": "hybrid",
}


def _make_valid_rows(n: int = 1) -> list[dict]:
    return [
        {**_VALID_ROW, "job_url": f"https://example.com/jobs/{i}"}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Stage 1: ingest
# ---------------------------------------------------------------------------


def test_stage_ingest_success() -> None:
    repo = MagicMock()
    repo.upsert_rows.return_value = OperationResult(True, 201, "jobs_final", "upsert", 2)

    from service.pipeline import run_stage_ingest

    result = run_stage_ingest(repo=repo, rows=_make_valid_rows(2))

    assert result.success is True
    assert result.processed == 2
    assert result.errors == []


def test_stage_ingest_partial_validation_continues() -> None:
    repo = MagicMock()
    repo.upsert_rows.return_value = OperationResult(True, 201, "jobs_final", "upsert", 1)

    from service.pipeline import run_stage_ingest

    rows = [
        _VALID_ROW,
        {"bad_field": "x"},  # invalid row
    ]
    result = run_stage_ingest(repo=repo, rows=rows)

    assert result.success is True
    assert result.processed == 1
    assert len(result.errors) == 1
    assert "row[1]" in result.errors[0]


def test_stage_ingest_all_invalid_fails() -> None:
    from service.pipeline import run_stage_ingest

    rows = [{"bad_field": "x"}, {"another_bad": 1}]
    result = run_stage_ingest(repo=MagicMock(), rows=rows)

    assert result.success is False
    assert result.processed == 0
    assert len(result.errors) == 2


def test_stage_ingest_upsert_failure() -> None:
    repo = MagicMock()
    repo.upsert_rows.return_value = OperationResult(False, 500, "jobs_final", "upsert", 0, error="Server error")

    from service.pipeline import run_stage_ingest

    result = run_stage_ingest(repo=repo, rows=_make_valid_rows(1))

    assert result.success is False
    assert "Server error" in result.errors[-1]


def test_submit_jobs_for_enrichment_success() -> None:
    repo = MagicMock()
    repo.upsert_rows.side_effect = [
        OperationResult(True, 201, "jobs_final", "upsert", 2),
        OperationResult(True, 201, "shared_links", "upsert", 2),
    ]
    repo.select_rows.return_value = OperationResult(
        True,
        200,
        "jobs_final",
        "select",
        0,
        data=[
            {"id": "id-1", "job_url": "https://example.com/jobs/0"},
            {"id": "id-2", "job_url": "https://example.com/jobs/1"},
        ],
    )

    from service.pipeline import submit_jobs_for_enrichment

    result = submit_jobs_for_enrichment(repo=repo, rows=_make_valid_rows(2))

    assert result.submitted_row_count == 2
    assert result.accepted_ids == ["id-1", "id-2"]
    assert result.accepted_urls == ["https://example.com/jobs/0", "https://example.com/jobs/1"]
    assert result.rejected_row_indexes == []
    assert result.errors == []
    assert result.jobs_final_row_count == 2
    assert result.shared_links_row_count == 2
    assert repo.upsert_rows.call_args_list[0].kwargs == {
        "table": "jobs_final",
        "rows": [
            {
                "company_name": "Acme Corp",
                "role_title": "Backend Engineer",
                "job_url": "https://example.com/jobs/0",
                "description": "Build APIs.",
                "match_score": 90,
                "job_status": "SCRAPED",
                "is_deleted": False,
                "language": "English",
                "job_type": "fulltime",
                "work_mode": "hybrid",
            },
            {
                "company_name": "Acme Corp",
                "role_title": "Backend Engineer",
                "job_url": "https://example.com/jobs/1",
                "description": "Build APIs.",
                "match_score": 90,
                "job_status": "SCRAPED",
                "is_deleted": False,
                "language": "English",
                "job_type": "fulltime",
                "work_mode": "hybrid",
            },
        ],
        "on_conflict": "job_url",
    }
    assert repo.upsert_rows.call_args_list[1].kwargs == {
        "table": "shared_links",
        "rows": [{"url": "https://example.com/jobs/0"}, {"url": "https://example.com/jobs/1"}],
        "on_conflict": "url",
    }


def test_submit_jobs_for_enrichment_partial_validation_continues() -> None:
    repo = MagicMock()
    repo.upsert_rows.side_effect = [
        OperationResult(True, 201, "jobs_final", "upsert", 1),
        OperationResult(True, 201, "shared_links", "upsert", 1),
    ]
    repo.select_rows.return_value = OperationResult(
        True,
        200,
        "jobs_final",
        "select",
        0,
        data=[{"id": "id-1", "job_url": "https://example.com/jobs/1"}],
    )

    from service.pipeline import submit_jobs_for_enrichment

    result = submit_jobs_for_enrichment(repo=repo, rows=[_VALID_ROW, {"bad_field": "x"}])

    assert result.submitted_row_count == 2
    assert result.accepted_ids == ["id-1"]
    assert result.accepted_urls == ["https://example.com/jobs/1"]
    assert result.rejected_row_indexes == [1]
    assert len(result.errors) == 1
    assert "row[1]" in result.errors[0]


def test_submit_jobs_for_enrichment_requires_valid_job() -> None:
    from service.pipeline import submit_jobs_for_enrichment

    with pytest.raises(ValueError, match="No valid jobs submitted"):
        submit_jobs_for_enrichment(repo=MagicMock(), rows=[{"job_url": "   "}, {"bad_field": "x"}])


def test_submit_jobs_for_enrichment_rejects_remote_type_field() -> None:
    from service.pipeline import submit_jobs_for_enrichment

    with pytest.raises(ValueError, match="No valid jobs submitted"):
        submit_jobs_for_enrichment(
            repo=MagicMock(),
            rows=[{
                "company_name": "Acme Corp",
                "role_title": "Backend Engineer",
                "job_url": "https://example.com/jobs/legacy",
                "description": "Build APIs.",
                "remote_type": "Remote",
            }],
        )


def test_submit_jobs_for_enrichment_fails_when_select_misses_url() -> None:
    repo = MagicMock()
    repo.upsert_rows.return_value = OperationResult(True, 201, "jobs_final", "upsert", 1)
    repo.select_rows.return_value = OperationResult(
        True,
        200,
        "jobs_final",
        "select",
        0,
        data=[],
    )

    from service.pipeline import submit_jobs_for_enrichment

    with pytest.raises(RuntimeError, match="rows were not found in jobs_final"):
        submit_jobs_for_enrichment(repo=repo, rows=[_VALID_ROW])


def test_submit_jobs_for_enrichment_fails_when_shared_links_upsert_fails() -> None:
    repo = MagicMock()
    repo.upsert_rows.side_effect = [
        OperationResult(True, 201, "jobs_final", "upsert", 1),
        OperationResult(False, 500, "shared_links", "upsert", 0, error="shared links down"),
    ]
    repo.select_rows.return_value = OperationResult(
        True,
        200,
        "jobs_final",
        "select",
        0,
        data=[{"id": "id-1", "job_url": "https://example.com/jobs/1"}],
    )

    from service.pipeline import submit_jobs_for_enrichment

    with pytest.raises(RuntimeError, match="shared links down"):
        submit_jobs_for_enrichment(repo=repo, rows=[_VALID_ROW])


# ---------------------------------------------------------------------------
# Stage 2: enrich
# ---------------------------------------------------------------------------


def test_stage_enriched_success(monkeypatch) -> None:
    import service.pipeline as ops_module

    fake_summary = MagicMock(enriched=MagicMock(count=3, ids=["id-1", "id-2", "id-3"]), errors=[])
    monkeypatch.setattr(ops_module, "enrich_jobs", MagicMock(return_value=fake_summary))

    from service.pipeline import run_stage_enriched

    result = run_stage_enriched(
        repo=MagicMock(),
        copilot_client=MagicMock(),
        limit=10,
    )

    assert result.success is True
    assert result.processed == 3
    assert result.errors == []


def test_stage_enriched_runtime_error(monkeypatch) -> None:
    import service.pipeline as ops_module

    monkeypatch.setattr(ops_module, "enrich_jobs", MagicMock(side_effect=RuntimeError("Fetch failed")))

    from service.pipeline import run_stage_enriched

    result = run_stage_enriched(
        repo=MagicMock(),
        copilot_client=MagicMock(),
        limit=10,
    )

    assert result.success is False
    assert "Fetch failed" in result.errors[0]


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def test_pipeline_full_success() -> None:
    repo = MagicMock()
    repo.upsert_rows.return_value = OperationResult(True, 201, "jobs_final", "upsert", 2)
    repo.select_rows.return_value = OperationResult(True, 200, "jobs_final", "select", 0, data=[])

    import service.pipeline as ops_module
    from unittest.mock import patch

    fake_summary = MagicMock(enriched=MagicMock(count=2, ids=["id-1", "id-2"]), errors=[])

    with patch.object(ops_module, "enrich_jobs", MagicMock(return_value=fake_summary)):
        from service.pipeline import run_pipeline

        result = run_pipeline(
            repo=repo,
            copilot_client=MagicMock(),
            rows=_make_valid_rows(2),
        )

    assert result.success is True
    assert len(result.stages) == 2
    assert result.total_processed == 2
    assert result.total_enriched == 2


def test_pipeline_short_circuits_on_ingest_failure() -> None:
    repo = MagicMock()
    repo.upsert_rows.return_value = OperationResult(False, 500, "jobs_final", "upsert", 0, error="fail")

    from service.pipeline import run_pipeline

    result = run_pipeline(
        repo=repo,
        copilot_client=MagicMock(),
        rows=_make_valid_rows(1),
    )

    assert result.success is False
    assert len(result.stages) == 1
    assert result.stages[0].stage == "ingest"
