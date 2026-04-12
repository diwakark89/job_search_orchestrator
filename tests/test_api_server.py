from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.app import app
from common.client import OperationResult


def _make_client() -> TestClient:
    return TestClient(app)


def test_health_endpoint_reports_status() -> None:
    client = _make_client()
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert isinstance(payload["supabase_configured"], bool)
    assert isinstance(payload["copilot_configured"], bool)


def test_tables_endpoint_lists_supported_tables() -> None:
    client = _make_client()
    response = client.get("/tables")

    assert response.status_code == 200
    payload = response.json()
    assert "jobs_final" in payload["tables"]
    assert payload["default_conflict_keys"]["jobs_final"] == "job_id"
    assert payload["default_conflict_keys"]["jobs_raw"] == "job_url"
    assert payload["default_conflict_keys"]["shared_links"] == "url"


def test_db_list_rows_success(monkeypatch) -> None:
    import api.routes.tables as tables_module

    repo = MagicMock()
    repo.select_rows.return_value = OperationResult(
        True,
        200,
        "jobs_final",
        "select",
        1,
        data=[{"job_id": "aaaaaaaa-0000-0000-0000-000000000001"}],
    )
    monkeypatch.setattr(tables_module, "_repo", MagicMock(return_value=repo))

    client = _make_client()
    response = client.get("/db/jobs-final?job_status=Applied&limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["table"] == "jobs_final"
    assert payload["count"] == 1
    assert payload["rows"][0]["job_id"] == "aaaaaaaa-0000-0000-0000-000000000001"
    repo.select_rows.assert_called_once()


def test_db_list_rows_forwards_filters_and_ordering(monkeypatch) -> None:
    import api.routes.tables as tables_module

    repo = MagicMock()
    repo.select_rows.return_value = OperationResult(True, 200, "jobs_final", "select", 0, data=[])
    monkeypatch.setattr(tables_module, "_repo", MagicMock(return_value=repo))

    client = _make_client()
    response = client.get(
        "/db/jobs-final?job_status=Applied&company_name=Acme&columns=job_id,company_name&limit=25&offset=5&order_by=created_at&ascending=false"
    )

    assert response.status_code == 200
    repo.select_rows.assert_called_once_with(
        table="jobs_final",
        columns="job_id,company_name",
        filters={"job_status": "Applied", "company_name": "Acme"},
        limit=25,
        offset=5,
        order_by="created_at",
        ascending=False,
    )


def test_db_get_record_not_found(monkeypatch) -> None:
    import api.routes.tables as tables_module

    repo = MagicMock()
    repo.select_rows.return_value = OperationResult(True, 200, "jobs_final", "select", 0, data=[])
    monkeypatch.setattr(tables_module, "_repo", MagicMock(return_value=repo))

    client = _make_client()
    response = client.get("/db/jobs-final/missing-id")

    assert response.status_code == 404
    assert "missing-id" in response.json()["detail"]


def test_db_create_rows_success(monkeypatch) -> None:
    import api.routes.tables as tables_module

    repo = MagicMock()
    repo.upsert_rows.return_value = OperationResult(True, 201, "jobs_final", "upsert", 1)
    monkeypatch.setattr(tables_module, "_repo", MagicMock(return_value=repo))

    client = _make_client()
    response = client.post(
        "/db/jobs-final",
        json={"rows": [{"job_id": "aaaaaaaa-0000-0000-0000-000000000001"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["operation"] == "upsert"


def test_job_metrics_create_is_rejected_as_patch_only() -> None:
    client = _make_client()
    response = client.post("/db/job-metrics", json={"rows": [{"id": 1, "total_scraped": 1}]})

    assert response.status_code == 405
    assert "patch-only" in response.json()["detail"]


def test_job_metrics_patch_uses_record_id_filter(monkeypatch) -> None:
    import api.routes.tables as tables_module

    repo = MagicMock()
    repo.patch_rows.return_value = OperationResult(True, 200, "job_metrics", "patch", 1)
    monkeypatch.setattr(tables_module, "_repo", MagicMock(return_value=repo))

    client = _make_client()
    response = client.patch("/db/job-metrics/1", json={"payload": {"total_scraped": 42}})

    assert response.status_code == 200
    repo.patch_rows.assert_called_once_with(
        table="job_metrics",
        payload={"total_scraped": 42},
        filters={"id": "1"},
    )


def test_db_patch_failure_maps_http_error(monkeypatch) -> None:
    import api.routes.tables as tables_module

    repo = MagicMock()
    repo.patch_rows.return_value = OperationResult(False, 404, "jobs_final", "patch", 0, error="Not found")
    monkeypatch.setattr(tables_module, "_repo", MagicMock(return_value=repo))

    client = _make_client()
    response = client.patch(
        "/db/jobs-final/aaaaaaaa-0000-0000-0000-000000000001",
        json={"payload": {"job_status": "Applied"}},
    )

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["success"] is False
    assert detail["operation"] == "patch"


def test_db_soft_delete_success(monkeypatch) -> None:
    import api.routes.tables as tables_module

    repo = MagicMock()
    monkeypatch.setattr(tables_module, "_repo", MagicMock(return_value=repo))
    monkeypatch.setattr(
        tables_module,
        "soft_delete_jobs_final",
        MagicMock(return_value=OperationResult(True, 200, "jobs_final", "patch", 1)),
    )

    client = _make_client()
    response = client.request(
        "DELETE",
        "/db/jobs-final/aaaaaaaa-0000-0000-0000-000000000001/soft",
        json={"hard_delete": False},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_db_unknown_table_returns_404() -> None:
    client = _make_client()
    response = client.get("/db/not-a-table")

    assert response.status_code == 404
    assert "Unknown table" in response.json()["detail"]


def test_enricher_run_success(monkeypatch) -> None:
    import api.routes.enricher as enricher_module

    monkeypatch.setattr(enricher_module, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "CopilotClient", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "load_copilot_config", MagicMock(return_value=object()))
    monkeypatch.setattr(
        enricher_module,
        "enrich_jobs",
        MagicMock(
            return_value=type(
                "Summary",
                (),
                {"processed": 3, "enriched": 2, "skipped": 1, "failed": 0, "errors": []},
            )()
        ),
    )

    client = _make_client()
    response = client.post("/enricher/run", json={"limit": 5, "dry_run": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["processed"] == 3
    assert payload["enriched"] == 2
    assert payload["failed"] == 0
