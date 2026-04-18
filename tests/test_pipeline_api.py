from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient

from api.app import app
from pipeline.models import PipelineResult, StageResult, SubmitJobsResult

_VALID_ROW = {
    "company_name": "Acme Corp",
    "role_title": "Backend Engineer",
    "job_url": "https://example.com/jobs/1",
    "description": "Build APIs.",
    "job_type": "fulltime",
    "work_mode": "hybrid",
}


def _make_client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /pipeline/run
# ---------------------------------------------------------------------------


def test_pipeline_run_success(monkeypatch) -> None:
    import api.routes.pipeline as pipeline_route

    fake_result = PipelineResult(
        stages=[
            StageResult(stage="ingest", success=True, processed=1, errors=[]),
            StageResult(stage="enrich", success=True, processed=1, errors=[]),
        ],
        success=True,
        total_processed=1,
        total_enriched=1,
        total_failed=0,
    )
    monkeypatch.setattr(pipeline_route, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "CopilotClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_copilot_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "run_pipeline", MagicMock(return_value=fake_result))

    client = _make_client()
    response = client.post("/pipeline/run", json={"jobs": [_VALID_ROW]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["stages"]) == 2
    assert payload["stages"][0]["processed"]["count"] == 1
    assert payload["stages"][0]["stage_error"] is None
    assert payload["stages"][0]["skipped"]["count"] == 0
    assert payload["stages"][0]["failed"]["count"] == 0
    assert payload["total_processed"] == 1
    assert payload["total_enriched"] == 1


def test_pipeline_submit_success_queues_only_submitted_ids(monkeypatch) -> None:
    import api.routes.pipeline as pipeline_route

    fake_thread = MagicMock()
    thread_factory = MagicMock(return_value=fake_thread)
    fake_result = SubmitJobsResult(
        submitted_row_count=2,
        accepted_ids=["id-1", "id-2"],
        accepted_urls=["https://example.com/jobs/1", "https://example.com/jobs/2"],
        rejected_row_indexes=[2],
        errors=["row[2]: job_url is required."],
        jobs_final_row_count=2,
        shared_links_row_count=2,
    )
    monkeypatch.setattr(pipeline_route, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "submit_jobs_for_enrichment", MagicMock(return_value=fake_result))
    monkeypatch.setattr(pipeline_route.threading, "Thread", thread_factory)

    client = _make_client()
    response = client.post("/pipeline/submit", json={"jobs": [_VALID_ROW, _VALID_ROW, {"job_url": "   "}]})

    assert response.status_code == 202
    payload = response.json()
    assert payload["submitted_row_count"] == 2
    assert payload["accepted"]["count"] == 2
    assert payload["accepted"]["ids"] == ["id-1", "id-2"]
    assert payload["queued"]["count"] == 2
    assert payload["queued"]["ids"] == ["id-1", "id-2"]
    assert payload["rejected_row_indexes"] == [2]
    assert payload["errors"] == ["row[2]: job_url is required."]
    assert payload["jobs_final_row_count"] == 2
    assert payload["shared_links_row_count"] == 2
    call_kwargs = thread_factory.call_args
    assert call_kwargs.kwargs["target"] == pipeline_route._run_submitted_jobs_enrichment
    assert call_kwargs.kwargs["args"][0] == ["id-1", "id-2"]
    assert isinstance(call_kwargs.kwargs["args"][1], str)  # submit_request_id UUID
    assert call_kwargs.kwargs["name"] == "pipeline-submit-enrichment"
    assert call_kwargs.kwargs["daemon"] is True
    fake_thread.start.assert_called_once()


def test_pipeline_submit_validation_error(monkeypatch) -> None:
    import api.routes.pipeline as pipeline_route

    monkeypatch.setattr(pipeline_route, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(
        pipeline_route,
        "submit_jobs_for_enrichment",
        MagicMock(side_effect=ValueError("No valid jobs submitted. row[0]: job_url is required.")),
    )

    client = _make_client()
    response = client.post("/pipeline/submit", json={"jobs": [{"job_url": "   "}]})

    assert response.status_code == 400
    assert "No valid jobs submitted" in response.json()["detail"]


def test_pipeline_submit_runtime_error(monkeypatch) -> None:
    import api.routes.pipeline as pipeline_route

    monkeypatch.setattr(pipeline_route, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(
        pipeline_route,
        "submit_jobs_for_enrichment",
        MagicMock(side_effect=RuntimeError("shared links down")),
    )

    client = _make_client()
    response = client.post("/pipeline/submit", json={"jobs": [_VALID_ROW]})

    assert response.status_code == 502
    assert "shared links down" in response.json()["detail"]


def test_pipeline_submit_background_enrichment_sets_saved_status(monkeypatch) -> None:
    import api.routes.pipeline as pipeline_route

    monkeypatch.setattr(pipeline_route, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "CopilotClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_copilot_config", MagicMock(return_value=object()))
    enrich_jobs_by_ids_mock = MagicMock(
        return_value=type(
            "Summary",
            (),
            {
                "processed": type("Bucket", (), {"count": 1, "ids": ["id-1"]})(),
                "enriched": type("Bucket", (), {"count": 1, "ids": ["id-1"]})(),
                "skipped": type("Bucket", (), {"count": 0, "ids": []})(),
                "failed": type("Bucket", (), {"count": 0, "ids": []})(),
                "errors": [],
                "copilot_batches_sent": 1,
                "database_batches_sent": 1,
                "database_rows_reported": 1,
            },
        )()
    )
    monkeypatch.setattr(pipeline_route, "enrich_jobs_by_ids", enrich_jobs_by_ids_mock)

    pipeline_route._run_submitted_jobs_enrichment(ids=["id-1"], submit_request_id="req-1")

    assert enrich_jobs_by_ids_mock.call_args.kwargs["ids"] == ["id-1"]
    assert enrich_jobs_by_ids_mock.call_args.kwargs["set_job_status_enriched"] is True
    assert enrich_jobs_by_ids_mock.call_args.kwargs["target_job_status"] == "SAVED"
    assert enrich_jobs_by_ids_mock.call_args.kwargs["submit_request_id"] == "req-1"


def test_pipeline_run_stage_failure_includes_failed_row_ids(monkeypatch) -> None:
    import api.routes.pipeline as pipeline_route

    fake_result = PipelineResult(
        stages=[
            StageResult(
                stage="ingest",
                success=False,
                processed=0,
                errors=["row[0]: company_name missing", "row[1]: role_title missing"],
            ),
        ],
        success=False,
        total_processed=0,
        total_enriched=0,
        total_failed=2,
    )
    monkeypatch.setattr(pipeline_route, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "CopilotClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_copilot_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "run_pipeline", MagicMock(return_value=fake_result))

    client = _make_client()
    response = client.post("/pipeline/run", json={"jobs": [_VALID_ROW]})

    assert response.status_code == 200
    payload = response.json()
    stage = payload["stages"][0]
    assert stage["stage_error"] == "row[0]: company_name missing"
    assert stage["failed"]["count"] == 2
    assert stage["failed"]["ids"] == ["row[0]", "row[1]"]


def test_pipeline_run_stage_failure_extracts_job_and_batch_ids(monkeypatch) -> None:
    import api.routes.pipeline as pipeline_route

    fake_result = PipelineResult(
        stages=[
            StageResult(
                stage="enrich",
                success=False,
                processed=0,
                errors=[
                    "job_id=11df3e1c-6f77-4439-aeb2-d86ddec82974: failed to set job_status=ENRICHED",
                    "Upsert returned success, but rows were not found in jobs_final for ids: id-1, id-2",
                ],
            ),
        ],
        success=False,
        total_processed=0,
        total_enriched=0,
        total_failed=2,
    )
    monkeypatch.setattr(pipeline_route, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "CopilotClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_copilot_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "run_pipeline", MagicMock(return_value=fake_result))

    client = _make_client()
    response = client.post("/pipeline/run", json={"jobs": [_VALID_ROW]})

    assert response.status_code == 200
    payload = response.json()
    stage = payload["stages"][0]
    assert stage["failed"]["ids"] == ["11df3e1c-6f77-4439-aeb2-d86ddec82974", "id-1", "id-2"]


def test_pipeline_run_validation_error(monkeypatch) -> None:
    import api.routes.pipeline as pipeline_route

    monkeypatch.setattr(pipeline_route, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "CopilotClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_copilot_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "run_pipeline", MagicMock(side_effect=ValueError("bad input")))

    client = _make_client()
    response = client.post("/pipeline/run", json={"jobs": [_VALID_ROW]})

    assert response.status_code == 400
    assert "bad input" in response.json()["detail"]


def test_pipeline_run_runtime_error(monkeypatch) -> None:
    import api.routes.pipeline as pipeline_route

    monkeypatch.setattr(pipeline_route, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "CopilotClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_copilot_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "run_pipeline", MagicMock(side_effect=RuntimeError("DB down")))

    client = _make_client()
    response = client.post("/pipeline/run", json={"jobs": [_VALID_ROW]})

    assert response.status_code == 502
    assert "DB down" in response.json()["detail"]


# ---------------------------------------------------------------------------
# POST /pipeline/stage/ingest
# ---------------------------------------------------------------------------


def test_stage_ingest_endpoint_success(monkeypatch) -> None:
    import api.routes.pipeline as pipeline_route

    fake_result = StageResult(stage="ingest", success=True, processed=2, errors=[])
    monkeypatch.setattr(pipeline_route, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "run_stage_ingest", MagicMock(return_value=fake_result))

    client = _make_client()
    response = client.post("/pipeline/stage/ingest", json={"jobs": [_VALID_ROW, _VALID_ROW]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["processed"]["count"] == 2
    assert payload["enriched"]["count"] == 0
    assert payload["failed"]["count"] == 0


# ---------------------------------------------------------------------------
# POST /pipeline/stage/enriched
# ---------------------------------------------------------------------------


def test_stage_enriched_endpoint_success(monkeypatch) -> None:
    import api.routes.pipeline as pipeline_route

    fake_result = type(
        "Summary",
        (),
        {
            "processed": type("Bucket", (), {"count": 3, "ids": ["id-1", "id-2", "id-3"]})(),
            "enriched": type("Bucket", (), {"count": 2, "ids": ["id-1", "id-2"]})(),
            "skipped": type("Bucket", (), {"count": 0, "ids": []})(),
            "failed": type("Bucket", (), {"count": 0, "ids": []})(),
            "errors": [],
            "copilot_batches_sent": 2,
            "database_batches_sent": 1,
            "database_rows_reported": 2,
        },
    )()
    monkeypatch.setattr(pipeline_route, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "CopilotClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_copilot_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "run_stage_enriched_detailed", MagicMock(return_value=fake_result))

    client = _make_client()
    response = client.post("/pipeline/stage/enriched", json={"limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["processed"]["count"] == 3
    assert payload["processed"]["ids"] == ["id-1", "id-2", "id-3"]
    assert payload["enriched"]["count"] == 2
    assert payload["enriched"]["ids"] == ["id-1", "id-2"]
    assert payload["failed"]["count"] == 0
    assert payload["copilot_batches_sent"] == 2
    assert payload["database_batches_sent"] == 1
    assert payload["database_rows_reported"] == 2


# ---------------------------------------------------------------------------
# GET /pipeline/metrics
# ---------------------------------------------------------------------------


def test_metrics_endpoint_success(monkeypatch) -> None:
    import api.routes.pipeline as pipeline_route

    monkeypatch.setattr(pipeline_route, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(
        pipeline_route,
        "get_metrics",
        MagicMock(return_value={"status_counts": {"SCRAPED": 5, "ENRICHED": 3}, "total": 8}),
    )

    client = _make_client()
    response = client.get("/pipeline/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status_counts"]["SCRAPED"] == 5
    assert payload["total"] == 8
