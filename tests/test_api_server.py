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
    assert payload["default_conflict_keys"]["jobs_final"] == "id"
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
        data=[{"id": "aaaaaaaa-0000-0000-0000-000000000001"}],
    )
    monkeypatch.setattr(tables_module, "_repo", MagicMock(return_value=repo))

    client = _make_client()
    response = client.get("/db/jobs-final?job_status=Applied&limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["table"] == "jobs_final"
    assert payload["count"] == 1
    assert payload["rows"][0]["id"] == "aaaaaaaa-0000-0000-0000-000000000001"
    repo.select_rows.assert_called_once()


def test_db_list_rows_forwards_filters_and_ordering(monkeypatch) -> None:
    import api.routes.tables as tables_module

    repo = MagicMock()
    repo.select_rows.return_value = OperationResult(True, 200, "jobs_final", "select", 0, data=[])
    monkeypatch.setattr(tables_module, "_repo", MagicMock(return_value=repo))

    client = _make_client()
    response = client.get(
        "/db/jobs-final?job_status=Applied&company_name=Acme&columns=id,company_name&limit=25&offset=5&order_by=created_at&ascending=false"
    )

    assert response.status_code == 200
    repo.select_rows.assert_called_once_with(
        table="jobs_final",
        columns="id,company_name",
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
        json={"rows": [{"id": "aaaaaaaa-0000-0000-0000-000000000001"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["operation"] == "upsert"


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
                {
                    "processed": type("Bucket", (), {"count": 3, "ids": ["id-1", "id-2", "id-3"]})(),
                    "enriched": type("Bucket", (), {"count": 2, "ids": ["id-1", "id-2"]})(),
                    "skipped": type("Bucket", (), {"count": 1, "ids": ["id-3"]})(),
                    "failed": type("Bucket", (), {"count": 0, "ids": []})(),
                    "errors": [],
                },
            )()
        ),
    )

    client = _make_client()
    response = client.post("/enricher/run", json={"limit": 5, "dry_run": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["processed"]["count"] == 3
    assert payload["processed"]["ids"] == ["id-1", "id-2", "id-3"]
    assert payload["enriched"]["count"] == 2
    assert payload["enriched"]["ids"] == ["id-1", "id-2"]
    assert payload["skipped"]["count"] == 1
    assert payload["skipped"]["ids"] == ["id-3"]
    assert payload["failed"]["count"] == 0
    assert payload["failed"]["ids"] == []


def test_enricher_by_ids_success(monkeypatch) -> None:
    import api.routes.enricher as enricher_module

    monkeypatch.setattr(enricher_module, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "CopilotClient", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "load_copilot_config", MagicMock(return_value=object()))
    enrich_jobs_by_ids_mock = MagicMock(
        return_value=type(
            "Summary",
            (),
            {
                "processed": type("Bucket", (), {"count": 3, "ids": ["id-1", "id-2", "id-3"]})(),
                "enriched": type("Bucket", (), {"count": 1, "ids": ["id-1"]})(),
                "skipped": type("Bucket", (), {"count": 1, "ids": ["id-2"]})(),
                "failed": type("Bucket", (), {"count": 1, "ids": ["id-3"]})(),
                "errors": ["id=id-3: jobs_final row not found or soft-deleted"],
            },
        )()
    )
    monkeypatch.setattr(enricher_module, "enrich_jobs_by_ids", enrich_jobs_by_ids_mock)

    client = _make_client()
    response = client.post("/enricher/by-ids", json=[{"id": "id-1"}, {"id": "id-2"}, {"id": "id-3"}])

    assert response.status_code == 200
    payload = response.json()
    assert payload["processed"]["count"] == 3
    assert payload["enriched"]["count"] == 1
    assert payload["skipped"]["count"] == 1
    assert payload["failed"]["count"] == 1
    assert payload["errors"] == ["id=id-3: jobs_final row not found or soft-deleted"]
    assert enrich_jobs_by_ids_mock.call_args.kwargs["ids"] == ["id-1", "id-2", "id-3"]
    assert enrich_jobs_by_ids_mock.call_args.kwargs["dry_run"] is False


def test_enricher_by_ids_supports_dry_run(monkeypatch) -> None:
    import api.routes.enricher as enricher_module

    monkeypatch.setattr(enricher_module, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "CopilotClient", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "load_copilot_config", MagicMock(return_value=object()))
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
            },
        )()
    )
    monkeypatch.setattr(enricher_module, "enrich_jobs_by_ids", enrich_jobs_by_ids_mock)

    client = _make_client()
    response = client.post("/enricher/by-ids?dry_run=true", json=[{"id": "id-1"}])

    assert response.status_code == 200
    assert response.json()["enriched"]["ids"] == ["id-1"]
    assert enrich_jobs_by_ids_mock.call_args.kwargs["dry_run"] is True


def test_enricher_by_ids_validation_error(monkeypatch) -> None:
    import api.routes.enricher as enricher_module

    monkeypatch.setattr(enricher_module, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "CopilotClient", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "load_copilot_config", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "enrich_jobs_by_ids", MagicMock(side_effect=ValueError("bad input")))

    client = _make_client()
    response = client.post("/enricher/by-ids", json=[{"id": "id-1"}])

    assert response.status_code == 400
    assert "bad input" in response.json()["detail"]


def test_enricher_by_ids_runtime_error(monkeypatch) -> None:
    import api.routes.enricher as enricher_module

    monkeypatch.setattr(enricher_module, "PostgrestClient", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "SupabaseRepository", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "CopilotClient", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "load_config", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "load_copilot_config", MagicMock(return_value=object()))
    monkeypatch.setattr(enricher_module, "enrich_jobs_by_ids", MagicMock(side_effect=RuntimeError("DB down")))

    client = _make_client()
    response = client.post("/enricher/by-ids", json=[{"id": "id-1"}])

    assert response.status_code == 502
    assert "DB down" in response.json()["detail"]
