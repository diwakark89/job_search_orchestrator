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
uv run python main.py pipeline stage-ingest payloads/jobs_raw.json
uv run python main.py pipeline stage-enriched --limit 20 --dry-run
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

- Stage order is `ingest → enrich`
- The ingest stage validates each row independently
- Invalid rows are reported; valid rows continue
- Pipeline stops only when all ingest rows fail

## 3. Supported Tables

- `jobs_final`
- `shared_links`

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
| Upsert rows | `db upsert` | `repo.upsert_rows`, `upsert_jobs_final` | tables with conflict keys | `POST /db/{table}` | Defaults from `DEFAULT_CONFLICT_KEYS` |
| Insert rows | `db insert` | `repo.insert_rows`, `insert_shared_links` | insert-only flows | `POST /db/{table}` | Used when no default upsert key exists |
| Patch rows | `db patch` | `repo.patch_rows` | all tables | `PATCH /db/{table}/{record_id}` | |
| Hard delete | `db delete`, `db delete-jobs-final` | `repo.delete_rows`, `delete_jobs_final_by_id` | all tables | `DELETE /db/{table}/{record_id}` | 404 may be treated as success |
| Soft delete helper | `db soft-delete` | `soft_delete_jobs_final` | `jobs_final` | `DELETE /db/{table}/{record_id}/soft` | Soft delete only on `jobs_final` |
| Get metrics | n/a | `get_metrics` | `jobs_final` | `GET /pipeline/metrics` | Dynamic `COUNT(*) GROUP BY job_status` |
| Enricher | `enricher enrich` | `service.enricher.enrich_jobs` | `jobs_final` | `POST /enricher/run` | Reads SCRAPED rows, patches ENRICHED |
| Enricher by ids | n/a | `service.enricher.enrich_jobs_by_ids` | `jobs_final` | `POST /enricher/by-ids?dry_run=true\|false` | Re-enriches requested ids without changing job_status |
| Submit jobs async | n/a | `service.pipeline.submit_jobs_for_enrichment`, `service.enricher.enrich_jobs_by_ids` | `jobs_final`, `shared_links` | `POST /pipeline/submit` | Upserts jobs by `job_url`, upserts `shared_links`, queues in-process enrichment for submitted ids |
| Pipeline runner | `pipeline run`, `pipeline stage-*` | `service.pipeline.run_pipeline`, `run_stage_ingest`, `run_stage_enriched` | `jobs_final` | `POST /pipeline/*` | 2-stage orchestration |

Important constraints:

- `shared_links` uses URL-based upsert (`on_conflict=url`) for deduplication.
- `POST /pipeline/submit` starts an in-process daemon thread. If the API process restarts, queued enrichment work is lost.

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
    "jobs_final",
    "shared_links"
  ],
  "default_conflict_keys": {
    "jobs_final": "id",
    "shared_links": "url"
  }
}
```

### 6.2 Table endpoints

All table endpoints use these slug-to-table mappings:

| URL slug | Database table | Primary key |
| --- | --- | --- |
| `jobs-final` | `jobs_final` | `id` |
| `shared-links` | `shared_links` | `id` |

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
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "company_name": "Acme Corp",
      "job_status": "APPLIED"
    }
  ],
  "count": 1,
  "table": "jobs_final"
}
```

- Common error (`404`) for an unknown table slug:

```json
{
  "detail": "Unknown table 'not-a-table'. Available: ['jobs-final', 'shared-links']"
}
```

Example:

```bash
curl "http://localhost:8000/db/jobs-final?job_status=APPLIED&company_name=Acme&order_by=created_at&ascending=false&limit=25&offset=0"
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
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "company_name": "Acme Corp",
      "job_status": "SAVED"
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
      "id": "550e8400-e29b-41d4-a716-446655440000"
    }
  ]
}
```

Behavior:

- tables with default conflict keys use upsert
- tables without default conflict keys use insert

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

Example insert for `shared-links`:

```bash
curl -X POST http://localhost:8000/db/shared-links \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"url":"https://www.linkedin.com/jobs/view/123","source":"android-share-intent"}]}'
```

#### PATCH /db/{table}/{record_id}

Patch one record by primary key.

Request body:

```json
{
  "payload": {
    "job_status": "APPLIED"
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
curl -X PATCH http://localhost:8000/db/jobs-final/550e8400-e29b-41d4-a716-446655440000 \
  -H "Content-Type: application/json" \
  -d '{"payload":{"job_status":"APPLIED"}}'
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
  "table": "jobs_final",
  "operation": "delete",
  "row_count": 1,
  "data": null,
  "error": null
}
```

- Common error (`404`) for an unknown table slug:

```json
{
  "detail": "Unknown table 'not-a-table'. Available: ['jobs-final', 'shared-links']"
}
```

Example:

```bash
curl -X DELETE "http://localhost:8000/db/jobs-final/550e8400-e29b-41d4-a716-446655440000"
```

#### DELETE /db/{table}/{record_id}/soft

Soft delete one record.

Supported only for:

- `jobs-final`

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
  "detail": "Soft-delete is not supported for 'shared-links'. Only jobs-final supports it."
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
  -d '{"rows":[{"id":"550e8400-e29b-41d4-a716-446655440000","company_name":"Acme Corp","role_title":"Senior Android Engineer","job_status":"SAVED","job_url":"https://example.com/jobs/123"}]}'
```

#### `shared-links`

Add one shared link row:

```bash
curl -X POST http://localhost:8000/db/shared-links \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"url":"https://www.linkedin.com/jobs/view/123","source":"android-share-intent"}]}'
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
  "processed": {
    "count": 10,
    "ids": ["id-1", "id-2"]
  },
  "enriched": {
    "count": 8,
    "ids": ["id-1"]
  },
  "skipped": {
    "count": 1,
    "ids": ["id-9"]
  },
  "failed": {
    "count": 1,
    "ids": ["id-10"]
  },
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

#### POST /enricher/by-ids

Run enrichment for the requested `jobs_final` ids regardless of `job_status`.

Supported request and response:

- Query parameter: `dry_run=true|false` (defaults to `false`)
- Request body:

```json
[
  {
    "id": "e27be3e8-f4b2-4dba-a353-0a3c0b7125d4"
  },
  {
    "id": "98fa3757-c584-4849-8e7f-16a3d0881d28"
  }
]
```

- Success response (`200`):

```json
{
  "processed": {
    "count": 2,
    "ids": [
      "e27be3e8-f4b2-4dba-a353-0a3c0b7125d4",
      "98fa3757-c584-4849-8e7f-16a3d0881d28"
    ]
  },
  "enriched": {
    "count": 1,
    "ids": [
      "e27be3e8-f4b2-4dba-a353-0a3c0b7125d4"
    ]
  },
  "skipped": {
    "count": 0,
    "ids": []
  },
  "failed": {
    "count": 1,
    "ids": [
      "98fa3757-c584-4849-8e7f-16a3d0881d28"
    ]
  },
  "errors": [
    "id=98fa3757-c584-4849-8e7f-16a3d0881d28: jobs_final row not found or soft-deleted"
  ]
}
```

- Common error (`502`) when the service layer raises a runtime failure:

```json
{
  "detail": "Failed to fetch requested jobs_final rows."
}
```

cURL:

```bash
curl -X POST "http://localhost:8000/enricher/by-ids?dry_run=true" \
  -H "Content-Type: application/json" \
  -d '[{"id":"e27be3e8-f4b2-4dba-a353-0a3c0b7125d4"},{"id":"98fa3757-c584-4849-8e7f-16a3d0881d28"}]'
```

PowerShell live verification using existing rows:

```powershell
$rowsResp = Invoke-RestMethod -Method Get -Uri "http://localhost:8000/db/jobs-final"
$ids = @($rowsResp.rows | Where-Object { $_.id } | Select-Object -First 2 -ExpandProperty id)
if ($ids.Count -eq 0) { throw "No jobs_final ids found from /db/jobs-final" }

$payload = @(
  @{ id = "$($ids[0])" },
  @{ id = "$($ids[1])" }
) | ConvertTo-Json -Depth 4

Invoke-RestMethod -Method Post -Uri "http://localhost:8000/enricher/by-ids?dry_run=true" `
  -ContentType "application/json" `
  -Body $payload | ConvertTo-Json -Depth 8
```

### 6.4 Pipeline endpoints

#### POST /pipeline/submit

Accepts a list of jobs, validates each row independently, upserts valid rows into `jobs_final` with `job_status=SCRAPED`, upserts matching `shared_links` rows by `job_url`, and returns immediately after queueing background enrichment for the submitted ids.

Supported request and response:

- Request body:

```json
{
  "jobs": [
    {
      "company_name": "Acme Corp",
      "role_title": "Senior Engineer",
      "job_url": "https://example.com/jobs/1",
      "description": "Build APIs",
      "job_type": "fulltime",
      "work_mode": "hybrid"
    },
    {
      "bad_field": "x"
    }
  ]
}
```

- Success response (`202`):

```json
{
  "submitted_row_count": 2,
  "accepted": {
    "count": 1,
    "ids": ["550e8400-e29b-41d4-a716-446655440000"]
  },
  "queued": {
    "count": 1,
    "ids": ["550e8400-e29b-41d4-a716-446655440000"]
  },
  "rejected_row_indexes": [1],
  "errors": [
    "row[1]: Extra inputs are not permitted"
  ],
  "jobs_final_row_count": 1,
  "shared_links_row_count": 1
}
```

- Common error (`400`) when every submitted row is invalid:

```json
{
  "detail": "No valid jobs submitted. row[0]: job_url is required."
}
```

Notes:

- Validation is per-row. Invalid rows are reported in `errors`; valid rows still continue.
- Submitted jobs are deduplicated by `job_url` for persistence and queueing.
- `job_type` canonical values are `fulltime`, `parttime`, `internship`, `contract`, `temporary`, and `other`. Unmatched input is stored as `other`.
- `work_mode` canonical values are `remote`, `hybrid`, `on-site`, and `other`. Unmatched input is stored as `other`.
- Background enrichment is scoped only to ids accepted in the same request.
- Successful background enrichment updates those rows to `job_status=ENRICHED`.
- The background worker is in-process and non-durable.

#### POST /pipeline/run

Runs the full pipeline: `ingest → enrich`.

Supported request and response:

- Request body:

```json
{
  "jobs": [
    {
      "company_name": "Acme Corp",
      "role_title": "Senior Engineer",
      "job_url": "https://example.com/jobs/1",
      "description": "Build APIs",
      "job_type": "fulltime",
      "work_mode": "hybrid"
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
      "stage": "ingest",
      "success": true,
      "processed": 1,
      "errors": []
    },
    {
      "stage": "enriched",
      "success": true,
      "processed": 1,
      "errors": []
    }
  ],
  "success": true,
  "total_processed": 2,
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

#### POST /pipeline/stage/ingest

Runs the ingest stage only.

Supported request and response:

- Request body:

```json
{
  "jobs": [
    {
      "company_name": "Acme Corp",
      "role_title": "Senior Engineer",
      "job_url": "https://example.com/jobs/1",
      "description": "Build APIs",
      "job_type": "fulltime",
      "work_mode": "hybrid"
    }
  ]
}
```

- Success response (`200`):

```json
{
  "stage": "ingest",
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

Runs the enrich stage only. Processes `jobs_final` rows with `job_status=SCRAPED` and enriches them with extracted metadata from job descriptions.

**Fields updated on `jobs_final` rows:**

- `job_status` → "ENRICHED"
- `tech_stack` → Normalized array of technology names extracted from job description
- `experience_level` → Normalized experience level from the job description (possible values: "Internship", "Entry", "Mid", "Senior", "Lead", "Unknown")
- `work_mode` → Normalized work mode from the job description (possible values: "remote", "hybrid", "on-site", "other")

Schema note:

- Apply [db/migrations/2026-04-18_add_job_type_work_mode_to_jobs_final.sql](db/migrations/2026-04-18_add_job_type_work_mode_to_jobs_final.sql) manually in Supabase SQL Editor or your deployment workflow before sending `job_type` and `work_mode` to pipeline endpoints.
- The migration backfills `work_mode` from existing legacy values when needed and then drops the old column.

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

cURL example:

```bash
curl -X POST http://localhost:8000/pipeline/stage/enriched \
  -H "Content-Type: application/json" \
  -d '{"limit":20,"dry_run":false}'
```

#### GET /pipeline/metrics

Returns dynamic job status counts.

Supported request and response:

- Request body: none
- Success response (`200`):

```json
{
  "status_counts": {
    "SAVED": 10,
    "SCRAPED": 5,
    "ENRICHED": 3,
    "APPLIED": 2
  },
  "total": 20
}
```

## 7. CLI Examples

```bash
uv run python main.py db tables
uv run python main.py db upsert --table jobs_final --payload-file payloads/jobs_final_upsert.json
uv run python main.py db patch --table jobs_final --filter-column id --filter-value 550e8400-e29b-41d4-a716-446655440000 --payload '{"job_status":"APPLIED"}'
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
    filters={"job_status": "APPLIED"},
    order_by="created_at",
    ascending=False,
)
```

Table helper usage:

```python
from common.client import PostgrestClient
from common.config import load_config
from repository.supabase import SupabaseRepository
from service.tables import upsert_jobs_final, get_metrics

repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
upsert_jobs_final(repo, [{"id": "550e8400-e29b-41d4-a716-446655440000"}])
metrics = get_metrics(repo)
print(metrics)  # {"status_counts": {"SAVED": 10, ...}, "total": 10}
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

- The ingest stage validates each row independently
- Valid ingest rows still write even if some rows are invalid
- The enricher reads `jobs_final` rows where `job_status = SCRAPED` and `is_deleted = false`
- Successful enrichment patches `jobs_final.job_status` to `ENRICHED`
- Metrics are computed dynamically via `SELECT job_status, COUNT(*) FROM jobs_final GROUP BY job_status`
