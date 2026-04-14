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
}


def _make_valid_rows(n: int = 1) -> list[dict]:
    return [
        {**_VALID_ROW, "job_url": f"https://example.com/jobs/{i}"}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Stage 1: jobs_raw
# ---------------------------------------------------------------------------


def test_stage_raw_success(monkeypatch) -> None:
    import service.pipeline as ops_module

    fake_result = OperationResult(True, 201, "jobs_raw", "upsert", 2)
    monkeypatch.setattr(ops_module, "upsert_jobs_raw", MagicMock(return_value=fake_result))

    from service.pipeline import run_stage_raw

    result = run_stage_raw(repo=MagicMock(), rows=_make_valid_rows(2))

    assert result.success is True
    assert result.processed == 2
    assert result.errors == []


def test_stage_raw_partial_validation_continues(monkeypatch) -> None:
    import service.pipeline as ops_module

    fake_result = OperationResult(True, 201, "jobs_raw", "upsert", 1)
    monkeypatch.setattr(ops_module, "upsert_jobs_raw", MagicMock(return_value=fake_result))

    from service.pipeline import run_stage_raw

    rows = [
        _VALID_ROW,
        {"bad_field": "x"},  # invalid row
    ]
    result = run_stage_raw(repo=MagicMock(), rows=rows)

    assert result.success is True
    assert result.processed == 1
    assert len(result.errors) == 1
    assert "row[1]" in result.errors[0]


def test_stage_raw_all_invalid_fails() -> None:
    from service.pipeline import run_stage_raw

    rows = [{"bad_field": "x"}, {"another_bad": 1}]
    result = run_stage_raw(repo=MagicMock(), rows=rows)

    assert result.success is False
    assert result.processed == 0
    assert len(result.errors) == 2


def test_stage_raw_upsert_failure(monkeypatch) -> None:
    import service.pipeline as ops_module

    fake_result = OperationResult(False, 500, "jobs_raw", "upsert", 0, error="Server error")
    monkeypatch.setattr(ops_module, "upsert_jobs_raw", MagicMock(return_value=fake_result))

    from service.pipeline import run_stage_raw

    result = run_stage_raw(repo=MagicMock(), rows=_make_valid_rows(1))

    assert result.success is False
    assert "Server error" in result.errors[-1]


# ---------------------------------------------------------------------------
# Stage 2: jobs_enriched
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
# Stage 3: job_metrics
# ---------------------------------------------------------------------------


def test_stage_metrics_success(monkeypatch) -> None:
    import service.pipeline as ops_module

    fake_result = OperationResult(True, 200, "job_metrics", "patch", 1)
    monkeypatch.setattr(ops_module, "patch_job_metrics", MagicMock(return_value=fake_result))

    from service.pipeline import run_stage_metrics

    result = run_stage_metrics(repo=MagicMock(), scraped_count=5)

    assert result.success is True
    assert result.processed == 1


def test_stage_metrics_failure(monkeypatch) -> None:
    import service.pipeline as ops_module

    fake_result = OperationResult(False, 500, "job_metrics", "patch", 0, error="DB error")
    monkeypatch.setattr(ops_module, "patch_job_metrics", MagicMock(return_value=fake_result))

    from service.pipeline import run_stage_metrics

    result = run_stage_metrics(repo=MagicMock(), scraped_count=1)

    assert result.success is False
    assert "DB error" in result.errors[0]


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def test_pipeline_full_success(monkeypatch) -> None:
    import service.pipeline as ops_module

    monkeypatch.setattr(
        ops_module,
        "upsert_jobs_raw",
        MagicMock(return_value=OperationResult(True, 201, "jobs_raw", "upsert", 2)),
    )
    fake_summary = MagicMock(enriched=MagicMock(count=2, ids=["id-1", "id-2"]), errors=[])
    monkeypatch.setattr(ops_module, "enrich_jobs", MagicMock(return_value=fake_summary))
    monkeypatch.setattr(
        ops_module,
        "patch_job_metrics",
        MagicMock(return_value=OperationResult(True, 200, "job_metrics", "patch", 1)),
    )

    from service.pipeline import run_pipeline

    result = run_pipeline(
        repo=MagicMock(),
        copilot_client=MagicMock(),
        rows=_make_valid_rows(2),
    )

    assert result.success is True
    assert len(result.stages) == 3
    assert result.total_processed == 2
    assert result.total_enriched == 2


def test_pipeline_short_circuits_on_raw_failure(monkeypatch) -> None:
    import service.pipeline as ops_module

    monkeypatch.setattr(
        ops_module,
        "upsert_jobs_raw",
        MagicMock(return_value=OperationResult(False, 500, "jobs_raw", "upsert", 0, error="fail")),
    )

    from service.pipeline import run_pipeline

    result = run_pipeline(
        repo=MagicMock(),
        copilot_client=MagicMock(),
        rows=_make_valid_rows(1),
    )

    assert result.success is False
    assert len(result.stages) == 1
    assert result.stages[0].stage == "jobs_raw"


def test_pipeline_skips_metrics_on_dry_run(monkeypatch) -> None:
    import service.pipeline as ops_module

    monkeypatch.setattr(
        ops_module,
        "upsert_jobs_raw",
        MagicMock(return_value=OperationResult(True, 201, "jobs_raw", "upsert", 1)),
    )
    fake_summary = MagicMock(enriched=MagicMock(count=1, ids=["id-1"]), errors=[])
    monkeypatch.setattr(ops_module, "enrich_jobs", MagicMock(return_value=fake_summary))

    from service.pipeline import run_pipeline

    result = run_pipeline(
        repo=MagicMock(),
        copilot_client=MagicMock(),
        rows=_make_valid_rows(1),
        dry_run=True,
    )

    assert result.success is True
    assert len(result.stages) == 2  # no metrics stage
    stage_names = [s.stage for s in result.stages]
    assert "job_metrics" not in stage_names


# ---------------------------------------------------------------------------
# Stage: jobs_final finalize
# ---------------------------------------------------------------------------


def test_stage_finalize_success(monkeypatch) -> None:
    import service.pipeline as ops_module

    repo = MagicMock()
    repo.select_rows.return_value = OperationResult(
        True,
        200,
        "jobs_raw",
        "select",
        2,
        data=[
            {
                "id": "id-1",
                "company_name": "Acme Corp",
                "role_title": "Backend Engineer",
                "job_url": "https://example.com/jobs/1",
                "description": "Build APIs.",
                "language": "English",
                "job_status": "ENRICHED",
                "is_deleted": False,
            },
            {
                "id": "id-2",
                "company_name": "Beta Corp",
                "role_title": "Platform Engineer",
                "job_url": "https://example.com/jobs/2",
                "description": "Ship platform.",
                "language": "English",
                "job_status": "ENRICHED",
                "is_deleted": False,
            },
        ],
    )
    monkeypatch.setattr(
        ops_module,
        "upsert_jobs_final",
        MagicMock(return_value=OperationResult(True, 201, "jobs_final", "upsert", 2)),
    )
    repo.client.select.return_value = OperationResult(
        True,
        200,
        "jobs_final",
        "select",
        2,
        data=[{"job_id": "id-1"}, {"job_id": "id-2"}],
    )
    repo.patch_rows.return_value = OperationResult(True, 204, "jobs_raw", "patch", 1)

    from service.pipeline import run_stage_finalize_detailed

    result = run_stage_finalize_detailed(repo=repo, limit=10, dry_run=False)

    assert result.processed.count == 2
    assert result.processed.ids == ["id-1", "id-2"]
    assert result.enriched.count == 2
    assert result.enriched.ids == ["id-1", "id-2"]

    call_kwargs = ops_module.upsert_jobs_final.call_args.kwargs
    assert call_kwargs["rows"][0]["job_status"] == "Saved"
    assert call_kwargs["rows"][1]["job_status"] == "Saved"
    assert repo.patch_rows.call_count == 2


def test_stage_finalize_upsert_failure(monkeypatch) -> None:
    import service.pipeline as ops_module

    repo = MagicMock()
    repo.select_rows.return_value = OperationResult(
        True,
        200,
        "jobs_raw",
        "select",
        1,
        data=[
            {
                "id": "id-1",
                "company_name": "Acme Corp",
                "role_title": "Backend Engineer",
                "job_url": "https://example.com/jobs/1",
                "description": "Build APIs.",
                "language": "English",
                "job_status": "ENRICHED",
                "is_deleted": False,
            }
        ],
    )
    monkeypatch.setattr(
        ops_module,
        "upsert_jobs_final",
        MagicMock(return_value=OperationResult(False, 500, "jobs_final", "upsert", 0, error="DB error")),
    )

    from service.pipeline import run_stage_finalize_detailed

    result = run_stage_finalize_detailed(repo=repo, limit=10, dry_run=False)

    assert result.enriched.count == 0
    assert result.failed.count == 1
    assert result.failed.ids == ["id-1"]
    assert "DB error" in result.errors[-1]


def test_stage_finalize_verify_missing_rows_after_upsert(monkeypatch) -> None:
    import service.pipeline as ops_module

    repo = MagicMock()
    repo.select_rows.return_value = OperationResult(
        True,
        200,
        "jobs_raw",
        "select",
        1,
        data=[
            {
                "id": "id-1",
                "company_name": "Acme Corp",
                "role_title": "Backend Engineer",
                "job_url": "https://example.com/jobs/1",
                "description": "Build APIs.",
                "language": "English",
                "job_status": "ENRICHED",
                "is_deleted": False,
            }
        ],
    )
    monkeypatch.setattr(
        ops_module,
        "upsert_jobs_final",
        MagicMock(return_value=OperationResult(True, 201, "jobs_final", "upsert", 1)),
    )
    repo.client.select.return_value = OperationResult(
        True,
        200,
        "jobs_final",
        "select",
        0,
        data=[],
    )

    from service.pipeline import run_stage_finalize_detailed

    result = run_stage_finalize_detailed(repo=repo, limit=10, dry_run=False)

    assert result.processed.count == 1
    assert result.enriched.count == 0
    assert result.failed.count == 1
    assert result.failed.ids == ["id-1"]
    assert "rows were not found in jobs_final" in result.errors[-1]


def test_stage_finalize_fails_when_raw_status_patch_fails(monkeypatch) -> None:
    import service.pipeline as ops_module

    repo = MagicMock()
    repo.select_rows.return_value = OperationResult(
        True,
        200,
        "jobs_raw",
        "select",
        1,
        data=[
            {
                "id": "id-1",
                "company_name": "Acme Corp",
                "role_title": "Backend Engineer",
                "job_url": "https://example.com/jobs/1",
                "description": "Build APIs.",
                "language": "English",
                "job_status": "ENRICHED",
                "is_deleted": False,
            }
        ],
    )
    monkeypatch.setattr(
        ops_module,
        "upsert_jobs_final",
        MagicMock(return_value=OperationResult(True, 201, "jobs_final", "upsert", 1)),
    )
    repo.client.select.return_value = OperationResult(
        True,
        200,
        "jobs_final",
        "select",
        1,
        data=[{"job_id": "id-1"}],
    )
    repo.patch_rows.return_value = OperationResult(False, 500, "jobs_raw", "patch", 0, error="Patch failed")

    from service.pipeline import run_stage_finalize_detailed

    result = run_stage_finalize_detailed(repo=repo, limit=10, dry_run=False)

    assert result.processed.count == 1
    assert result.enriched.count == 0
    assert result.failed.count == 1
    assert result.failed.ids == ["id-1"]
    assert "failed to set jobs_raw.job_status=Saved" in result.errors[-1]
