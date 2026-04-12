# Integration Guide: Automated Job Hunt Orchestrator

This document is the current integration contract for developers and AI agents using this project.

It explains:

- the supported interfaces
- the consolidated `/db/{table}` HTTP contract
- supported request and response shapes
- the current Python modules to import
- the current CLI commands

## 1. Integration Surface

This project exposes three supported integration interfaces:

1. CLI commands via `main.py`
2. Python API via `common`, `repository`, `service`, `job_enricher`, and `pipeline`
3. HTTP API via FastAPI server (`uvicorn`)

All interfaces operate against Supabase PostgREST using `SUPABASE_URL/rest/v1/{table}`.

## 1.1 Architecture Layers

- `common`: shared client, config, constants, validators, and db CLI
- `repository`: `SupabaseRepository`, the only database access boundary
- `service`: table helpers plus enricher and pipeline orchestration
- `api`: FastAPI routes built on top of the service and repository layers

## 1.2 Current Contract

The supported external surfaces are:

- REST-style HTTP endpoints under `/db/{table}`
- CLI commands under `python main.py db ...`
- Python imports through `common`, `repository`, and `service`

Legacy HTTP routes and the old CLI command group are no longer part of the supported contract.

## 2. Quick Start: Pipeline

1. Start the API server:

```bash
uv run uvicorn server:app --host 0.0.0.0 --port 8000
```

1. Run full pipeline from CLI:

```bash
uv run python main.py pipeline run payloads/jobs_raw.json --limit 50
```

1. Run full pipeline in dry-run mode:

```bash
uv run python main.py pipeline run payloads/jobs_raw.json --limit 20 --dry-run
```

1. Run stages individually:

```bash
uv run python main.py pipeline stage-raw payloads/jobs_raw.json
uv run python main.py pipeline stage-enriched --limit 20 --dry-run
uv run python main.py pipeline stage-metrics --scraped 10
```

1. Run full pipeline over HTTP:

```bash
curl -X POST http://localhost:8000/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{
    "rows": [
      {
        "company_name": "Acme Corp",
        "role_title": "Senior Engineer",
        "job_url": "https://example.com/jobs/1",
        "description": "Build APIs"
      }
    ],
    "limit": 50,
    "dry_run": false
  }'
```

## 2.1 Run Project As Server

Start server with uv:

```bash
uv run uvicorn server:app --host 0.0.0.0 --port 8000
```

Start server with Python directly:

```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

Start server from VS Code task:

```text
Task: Start Server (uv)
```

Verify server health:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/tables
```

Open interactive API docs:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

Execution behavior:

- Stage order is `jobs_raw -> jobs_enriched -> job_metrics`
- Stage 1 validates each row independently
- Invalid rows are reported; valid rows continue
- Pipeline stops only when all Stage 1 rows fail
- In dry-run mode, Stage 3 (`job_metrics`) is skipped

## 3. Supported Tables

- `jobs_final`
- `shared_links`
- `jobs_raw`
- `jobs_enriched`
- `job_decisions`
- `job_approvals`
- `job_metrics`

## 4. Setup

### 4.1 Environment

Required environment variables:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=sb_secret_your_generated_key_here
SUPABASE_TIMEOUT_SECONDS=30
COPILOT_MODEL=gpt-5.4-mini
COPILOT_TIMEOUT_SECONDS=45
COPILOT_MAX_RETRIES=3
COPILOT_RETRY_BACKOFF_SECONDS=1.0
```

Validation behavior:

- `SUPABASE_URL` must be valid http/https
- `SUPABASE_KEY` must be non-empty
- `SUPABASE_TIMEOUT_SECONDS` must be an integer greater than 0

### 4.2 Install

```bash
uv sync
```

Or with pip:

```bash
pip install -r requirements.txt
```

## 5. Operation Matrix

| Operation | CLI command | Python function(s) | Destination table(s) | HTTP equivalent | Notes |
| --- | --- | --- | --- | --- | --- |
| Select rows | n/a | `repo.select_rows` | all tables | `GET /db/{table}` | Supports query filters, pagination, ordering |
| Get one record | n/a | `repo.select_rows(..., limit=1)` | all tables | `GET /db/{table}/{record_id}` | Uses table primary key |
| Upsert rows | `db upsert` | `repo.upsert_rows`, `upsert_jobs_final`, `upsert_jobs_raw`, `upsert_jobs_enriched`, `upsert_job_approvals` | tables with conflict keys | `POST /db/{table}` | Defaults from `DEFAULT_CONFLICT_KEYS` |
| Insert rows | `db insert` | `repo.insert_rows`, `insert_shared_links`, `insert_job_decisions` | insert-only flows | `POST /db/{table}` | Used when no default upsert key exists |
| Patch rows | `db patch`, `db patch-metrics` | `repo.patch_rows`, `patch_job_metrics` | all tables | `PATCH /db/{table}/{record_id}` | `job_metrics` is patch-only |
| Hard delete | `db delete`, `db delete-jobs-final`, `db delete-jobs-raw` | `repo.delete_rows`, `delete_jobs_final_by_job_id`, `delete_jobs_raw_by_id` | all tables | `DELETE /db/{table}/{record_id}` | 404 may be treated as success |
| Soft delete helper | `db soft-delete` | `soft_delete_jobs_final`, `soft_delete_jobs_raw` | `jobs_final`, `jobs_raw` | `DELETE /db/{table}/{record_id}/soft` | Soft delete only on these two tables |
| Enricher | `enricher enrich` | `service.enricher.enrich_jobs` | `jobs_raw`, `jobs_enriched` | `POST /enricher/run` | Reads SCRAPED jobs and writes enrichment |
| Pipeline runner | `pipeline run`, `pipeline stage-*` | `service.pipeline.run_pipeline`, `run_stage_raw`, `run_stage_enriched`, `run_stage_metrics` | `jobs_raw`, `jobs_enriched`, `job_metrics` | `POST /pipeline/*` | 3-stage orchestration |

Important constraints:

- `job_metrics` does not support insert or upsert rows. Use patch only.
- HTTP `POST /db/job-metrics` returns `405`.
- `shared_links` and `job_decisions` do not have default HTTP upsert conflict keys and therefore follow insert behavior.

## 6. HTTP API Reference

### 6.0 Server startup

Start the HTTP server:

```bash
uv run uvicorn server:app --host 0.0.0.0 --port 8000
```

API documentation:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

### 6.1 System endpoints

#### GET /health

Returns server and dependency readiness status.

Supported request and response:

- Request body: none
- Success response (`200`):

```json
{
  "status": "ok",
  "supabase_configured": true,
  "copilot_configured": true
}
```

When either dependency is not configured, the route still returns `200` and reports `"status": "degraded"`.

#### GET /tables

Returns supported tables and default conflict keys.

Supported request and response:

- Request body: none
- Success response (`200`):

```json
{
  "tables": [
    "job_approvals",
    "job_decisions",
    "job_metrics",
    "jobs_enriched",
    "jobs_final",
    "jobs_raw",
    "shared_links"
  ],
  "default_conflict_keys": {
    "job_approvals": "decision_id",
    "jobs_enriched": "job_id",
    "jobs_final": "job_id",
    "jobs_raw": "job_url",
    "shared_links": "url"
  }
}
```

### 6.2 Table endpoints

All table endpoints use these slug-to-table mappings:

| URL slug | Database table | Primary key |
| --- | --- | --- |
| `jobs-final` | `jobs_final` | `job_id` |
| `jobs-raw` | `jobs_raw` | `id` |
| `jobs-enriched` | `jobs_enriched` | `job_id` |
| `shared-links` | `shared_links` | `id` |
| `job-decisions` | `job_decisions` | `id` |
| `job-approvals` | `job_approvals` | `decision_id` |
| `job-metrics` | `job_metrics` | `id` |

Shared write response shape:

```json
{
  "success": true,
  "status_code": 201,
  "table": "jobs_final",
  "operation": "upsert",
  "row_count": 1,
  "data": null,
  "error": null
}
```

#### GET /db/{table}

List rows from a table.

Supported query parameters:

- `columns`, default `*`
- `limit`, default `50`, max `1000`
- `offset`, default `0`
- `order_by`
- `ascending`, default `true`
- any additional query parameter is forwarded as an equality filter

Supported request and response:

- Request body: none
- Success response (`200`):

```json
{
  "rows": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "company_name": "Acme Corp",
      "job_status": "Applied"
    }
  ],
  "count": 1,
  "table": "jobs_final"
}
```

- Common error (`404`) for an unknown table slug:

```json
{
  "detail": "Unknown table 'not-a-table'. Available: ['job-approvals', 'job-decisions', 'job-metrics', 'jobs-enriched', 'jobs-final', 'jobs-raw', 'shared-links']"
}
```

Example:

```bash
curl "http://localhost:8000/db/jobs-final?job_status=Applied&company_name=Acme&order_by=created_at&ascending=false&limit=25&offset=0"
```

#### GET /db/{table}/{record_id}

Fetch one record by primary key.

Supported request and response:

- Request body: none
- Success response (`200`):

```json
{
  "rows": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "company_name": "Acme Corp",
      "job_status": "Saved"
    }
  ],
  "count": 1,
  "table": "jobs_final"
}
```

- Common error (`404`) when the record does not exist:

```json
{
  "detail": "Record 'missing-id' not found in jobs_final."
}
```

Example:

```bash
curl "http://localhost:8000/db/jobs-final/550e8400-e29b-41d4-a716-446655440000"
```

#### POST /db/{table}

Create rows for a table.

Request body:

```json
{
  "rows": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  ]
}
```

Behavior:

- tables with default conflict keys use upsert
- tables without default conflict keys use insert
- `job_metrics` is rejected with `405`

Supported request and response:

- Success response (`200`) with per-operation status in the body:

```json
{
  "success": true,
  "status_code": 201,
  "table": "jobs_final",
  "operation": "upsert",
  "row_count": 1,
  "data": null,
  "error": null
}
```

- Common error (`405`) for `job_metrics`:

```json
{
  "detail": "job_metrics is a patch-only table. Use PATCH instead."
}
```

Example insert for `shared-links`:

```bash
curl -X POST http://localhost:8000/db/shared-links \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"url":"https://www.linkedin.com/jobs/view/123","source":"android-share-intent","status":"Pending"}]}'
```

#### PATCH /db/{table}/{record_id}

Patch one record by primary key.

Request body:

```json
{
  "payload": {
    "job_status": "Applied"
  }
}
```

Supported request and response:

- Success response (`200`):

```json
{
  "success": true,
  "status_code": 200,
  "table": "jobs_final",
  "operation": "patch",
  "row_count": 1,
  "data": null,
  "error": null
}
```

- Common error (`404`) when the service reports a missing record:

```json
{
  "detail": {
    "success": false,
    "status_code": 404,
    "table": "jobs_final",
    "operation": "patch",
    "row_count": 0,
    "data": null,
    "error": "Not found"
  }
}
```

Example metrics patch:

```bash
curl -X PATCH http://localhost:8000/db/job-metrics/1 \
  -H "Content-Type: application/json" \
  -d '{"payload":{"total_scraped":1200}}'
```

#### DELETE /db/{table}/{record_id}

Hard delete one record by primary key.

Supported request and response:

- Request body: none
- Success response (`200`):

```json
{
  "success": true,
  "status_code": 200,
  "table": "jobs_raw",
  "operation": "delete",
  "row_count": 1,
  "data": null,
  "error": null
}
```

- Common error (`404`) for an unknown table slug:

```json
{
  "detail": "Unknown table 'not-a-table'. Available: ['job-approvals', 'job-decisions', 'job-metrics', 'jobs-enriched', 'jobs-final', 'jobs-raw', 'shared-links']"
}
```

Example:

```bash
curl -X DELETE "http://localhost:8000/db/jobs-raw/550e8400-e29b-41d4-a716-446655440000"
```

#### DELETE /db/{table}/{record_id}/soft

Soft delete one record.

Supported only for:

- `jobs-final`
- `jobs-raw`

Optional request body:

```json
{
  "hard_delete": false
}
```

Supported request and response:

- Success response (`200`):

```json
{
  "success": true,
  "status_code": 200,
  "table": "jobs_final",
  "operation": "patch",
  "row_count": 1,
  "data": null,
  "error": null
}
```

- Common error (`400`) for unsupported tables:

```json
{
  "detail": "Soft-delete is not supported for 'shared-links'. Only jobs-final and jobs-raw support it."
}
```

Example:

```bash
curl -X DELETE "http://localhost:8000/db/jobs-final/550e8400-e29b-41d4-a716-446655440000/soft" \
  -H "Content-Type: application/json" \
  -d '{"hard_delete":false}'
```

If `hard_delete=true`, the service performs soft delete first and then hard delete only if the patch succeeded.

### 6.2.1 Per-table add and write examples

The examples below show the supported write path for every table. Response bodies follow the generic success and error envelopes documented above.

#### `jobs-final`

Add or update one final job row:

```bash
curl -X POST http://localhost:8000/db/jobs-final \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"job_id":"550e8400-e29b-41d4-a716-446655440000","company_name":"Acme Corp","role_title":"Senior Android Engineer","job_status":"Saved","job_url":"https://example.com/jobs/123"}]}'
```

#### `jobs-raw`

Add one raw scraped row:

```bash
curl -X POST http://localhost:8000/db/jobs-raw \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"company_name":"Acme Corp","role_title":"Backend Engineer","job_url":"https://example.com/jobs/1","description":"Build APIs"}]}'
```

#### `jobs-enriched`

Add one enriched row:

```bash
curl -X POST http://localhost:8000/db/jobs-enriched \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"job_id":"550e8400-e29b-41d4-a716-446655440000","experience_level":"Senior","remote_type":"Remote","english_friendly":true,"tech_stack":["Python","FastAPI"]}]}'
```

#### `shared-links`

Add one shared link row:

```bash
curl -X POST http://localhost:8000/db/shared-links \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"url":"https://www.linkedin.com/jobs/view/123","source":"android-share-intent","status":"Pending"}]}'
```

#### `job-decisions`

Add one decision row:

```bash
curl -X POST http://localhost:8000/db/job-decisions \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"job_id":"550e8400-e29b-41d4-a716-446655440000","decision":"REVIEW","reason":"Needs human review"}]}'
```

#### `job-approvals`

Add or update one approval row:

```bash
curl -X POST http://localhost:8000/db/job-approvals \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"job_id":"550e8400-e29b-41d4-a716-446655440000","decision_id":"11111111-1111-1111-1111-111111111111","user_action":"APPROVED"}]}'
```

#### `job-metrics`

`job_metrics` is patch-only. The supported write path is to patch the singleton row instead of creating a new row:

```bash
curl -X PATCH http://localhost:8000/db/job-metrics/1 \
  -H "Content-Type: application/json" \
  -d '{"payload":{"total_scraped":1200,"total_enriched":800,"updated_at":"2026-04-11T12:00:00.000Z"}}'
```

### 6.3 Enricher endpoints

#### POST /enricher/run

Run the enrichment workflow.

Request:

```json
{
  "limit": 50,
  "dry_run": false
}
```

Supported request and response:

- Success response (`200`):

```json
{
  "processed": 10,
  "enriched": 8,
  "skipped": 1,
  "failed": 1,
  "errors": []
}
```

- Common error (`502`) when the service layer raises a runtime failure:

```json
{
  "detail": "Copilot enrichment failed"
}
```

cURL:

```bash
curl -X POST http://localhost:8000/enricher/run \
  -H "Content-Type: application/json" \
  -d '{"limit":20,"dry_run":true}'
```

### 6.4 Pipeline endpoints

#### POST /pipeline/run

Runs `jobs_raw -> jobs_enriched -> job_metrics`.

Supported request and response:

- Request body:

```json
{
  "rows": [
    {
      "company_name": "Acme Corp",
      "role_title": "Senior Engineer",
      "job_url": "https://example.com/jobs/1",
      "description": "Build APIs"
    }
  ],
  "limit": 50,
  "dry_run": false
}
```

- Success response (`200`):

```json
{
  "stages": [
    {
      "stage": "raw",
      "success": true,
      "processed": 1,
      "errors": []
    },
    {
      "stage": "enriched",
      "success": true,
      "processed": 1,
      "errors": []
    },
    {
      "stage": "metrics",
      "success": true,
      "processed": 1,
      "errors": []
    }
  ],
  "success": true,
  "total_processed": 3,
  "total_enriched": 1,
  "total_failed": 0
}
```

- Common error (`502`) when a pipeline dependency fails:

```json
{
  "detail": "Pipeline execution failed"
}
```

#### POST /pipeline/stage/raw

Runs Stage 1 only.

Supported request and response:

- Request body:

```json
{
  "rows": [
    {
      "company_name": "Acme Corp",
      "role_title": "Senior Engineer",
      "job_url": "https://example.com/jobs/1",
      "description": "Build APIs"
    }
  ]
}
```

- Success response (`200`):

```json
{
  "stage": "raw",
  "success": true,
  "processed": 1,
  "errors": []
}
```

- Common error (`400`) when validation fails before the stage runs:

```json
{
  "detail": "rows must not be empty"
}
```

#### POST /pipeline/stage/enriched

Runs Stage 2 only.

Supported request and response:

- Request body:

```json
{
  "limit": 20,
  "dry_run": true
}
```

- Success response (`200`):

```json
{
  "stage": "enriched",
  "success": true,
  "processed": 8,
  "errors": []
}
```

- Common error (`502`) when enrichment infrastructure fails:

```json
{
  "detail": "Copilot enrichment failed"
}
```

#### POST /pipeline/stage/metrics

Runs Stage 3 only.

Supported request and response:

- Request body:

```json
{
  "scraped_count": 10
}
```

- Success response (`200`):

```json
{
  "stage": "metrics",
  "success": true,
  "processed": 1,
  "errors": []
}
```

- Common error (`400`) when the payload is invalid:

```json
{
  "detail": "scraped_count must be greater than or equal to 0"
}
```

cURL:

```bash
curl -X POST http://localhost:8000/pipeline/stage/metrics \
  -H "Content-Type: application/json" \
  -d '{"scraped_count":10}'
```

## 7. CLI Examples

```bash
uv run python main.py db tables
uv run python main.py db upsert --table jobs_final --payload-file payloads/jobs_final_upsert.json
uv run python main.py db patch --table jobs_final --filter-column job_id --filter-value 550e8400-e29b-41d4-a716-446655440000 --payload '{"job_status":"Applied"}'
uv run python main.py db delete --table jobs_raw --filter-column id --filter-value 550e8400-e29b-41d4-a716-446655440000 --treat-404-as-success
uv run python main.py db patch-metrics --payload '{"total_scraped":1200}'
uv run python main.py enricher enrich --limit 20 --dry-run
uv run python main.py pipeline run payloads/jobs_raw.json --limit 20
```

## 8. Python API

Preferred imports now use repository and service layers.

Repository usage:

```python
from common.client import PostgrestClient
from common.config import load_config
from repository.supabase import SupabaseRepository

repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
result = repo.select_rows(
    table="jobs_final",
    filters={"job_status": "Applied"},
    order_by="created_at",
    ascending=False,
)
```

Table helper usage:

```python
from common.client import PostgrestClient
from common.config import load_config
from repository.supabase import SupabaseRepository
from service.tables import upsert_jobs_final, patch_job_metrics

repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
upsert_jobs_final(repo, [{"job_id": "550e8400-e29b-41d4-a716-446655440000"}])
patch_job_metrics(repo, {"total_scraped": 1200})
```

Enricher usage:

```python
from common.client import PostgrestClient
from common.config import load_config
from job_enricher.client_copilot import CopilotClient
from job_enricher.config import load_copilot_config
from repository.supabase import SupabaseRepository
from service.enricher import enrich_jobs

repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
copilot = CopilotClient(config=load_copilot_config())
summary = enrich_jobs(repo=repo, copilot_client=copilot, limit=50, dry_run=False)
```

Pipeline usage:

```python
from common.client import PostgrestClient
from common.config import load_config
from job_enricher.client_copilot import CopilotClient
from job_enricher.config import load_copilot_config
from repository.supabase import SupabaseRepository
from service.pipeline import run_pipeline

repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
copilot = CopilotClient(config=load_copilot_config())
result = run_pipeline(repo=repo, copilot_client=copilot, rows=[], limit=50, dry_run=False)
```

## 9. Behavioral Notes

- Stage 1 validates each `jobs_raw` row independently
- valid Stage 1 rows still write even if some rows are invalid
- the enricher reads `jobs_raw` rows where `job_status = SCRAPED` and `is_deleted = false`
- successful enrichment patches `jobs_raw.job_status` to `ENRICHED`
- dry-run pipeline skips Stage 3 metrics writes
