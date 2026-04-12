from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient

from api.app import app
from pipeline.models import PipelineResult, StageResult

_VALID_ROW = {
    "company_name": "Acme Corp",
    "role_title": "Backend Engineer",
    "job_url": "https://example.com/jobs/1",
    "description": "Build APIs.",
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
            StageResult(stage="jobs_raw", success=True, processed=1, errors=[]),
            StageResult(stage="jobs_enriched", success=True, processed=1, errors=[]),
            StageResult(stage="job_metrics", success=True, processed=1, errors=[]),
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
    response = client.post("/pipeline/run", json={"rows": [_VALID_ROW]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["stages"]) == 3
    assert payload["total_processed"] == 1
    assert payload["total_enriched"] == 1


def test_pipeline_run_validation_error(monkeypatch) -> None:
    import api.routes.pipeline as pipeline_route

    monkeypatch.setattr(pipeline_route, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "CopilotClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_copilot_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "run_pipeline", MagicMock(side_effect=ValueError("bad input")))

    client = _make_client()
    response = client.post("/pipeline/run", json={"rows": [_VALID_ROW]})

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
    response = client.post("/pipeline/run", json={"rows": [_VALID_ROW]})

    assert response.status_code == 502
    assert "DB down" in response.json()["detail"]


# ---------------------------------------------------------------------------
# POST /pipeline/stage/raw
# ---------------------------------------------------------------------------


def test_stage_raw_endpoint_success(monkeypatch) -> None:
    import api.routes.pipeline as pipeline_route

    fake_result = StageResult(stage="jobs_raw", success=True, processed=2, errors=[])
    monkeypatch.setattr(pipeline_route, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "run_stage_raw", MagicMock(return_value=fake_result))

    client = _make_client()
    response = client.post("/pipeline/stage/raw", json={"rows": [_VALID_ROW, _VALID_ROW]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["stage"] == "jobs_raw"
    assert payload["success"] is True
    assert payload["processed"] == 2


# ---------------------------------------------------------------------------
# POST /pipeline/stage/enriched
# ---------------------------------------------------------------------------


def test_stage_enriched_endpoint_success(monkeypatch) -> None:
    import api.routes.pipeline as pipeline_route

    fake_result = StageResult(stage="jobs_enriched", success=True, processed=3, errors=[])
    monkeypatch.setattr(pipeline_route, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "CopilotClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_copilot_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "run_stage_enriched", MagicMock(return_value=fake_result))

    client = _make_client()
    response = client.post("/pipeline/stage/enriched", json={"limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["stage"] == "jobs_enriched"
    assert payload["processed"] == 3


# ---------------------------------------------------------------------------
# POST /pipeline/stage/metrics
# ---------------------------------------------------------------------------


def test_stage_metrics_endpoint_success(monkeypatch) -> None:
    import api.routes.pipeline as pipeline_route

    fake_result = StageResult(stage="job_metrics", success=True, processed=1, errors=[])
    monkeypatch.setattr(pipeline_route, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(pipeline_route, "run_stage_metrics", MagicMock(return_value=fake_result))

    client = _make_client()
    response = client.post("/pipeline/stage/metrics", json={"scraped_count": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["stage"] == "job_metrics"
    assert payload["success"] is True
