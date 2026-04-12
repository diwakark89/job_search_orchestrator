# Automated Job Hunt Orchestrator

This project exposes three integration surfaces for the Automated Job Hunt data pipeline:

- a FastAPI HTTP API for table CRUD and orchestration
- a Typer CLI for operator workflows
- a Python library split into `common`, `repository`, and `service` layers

The pipeline manages these Supabase tables:

- `jobs_final`
- `shared_links`
- `jobs_raw`
- `jobs_enriched`
- `job_decisions`
- `job_approvals`
- `job_metrics`

It also includes:

- an enricher that reads `jobs_raw.description` and writes structured metadata to `jobs_enriched`
- a 3-stage pipeline runner: `jobs_raw -> jobs_enriched -> job_metrics`

## Integration Guide

The full contract lives in [docs/INTEGRATION.md](docs/INTEGRATION.md).

Use that guide for:

- supported request bodies
- representative success and error responses
- per-table write examples for every supported table
- pipeline and enricher request and response shapes

## Setup

1. Create and activate a virtual environment.
2. Install dependencies with the preferred tool:

```bash
uv sync
```

Or with pip:

```bash
pip install -r requirements.txt
```

1. Provide environment variables:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=sb_secret_your_generated_key_here
SUPABASE_TIMEOUT_SECONDS=30
COPILOT_MODEL=gpt-5.4-mini
COPILOT_TIMEOUT_SECONDS=45
COPILOT_MAX_RETRIES=3
COPILOT_RETRY_BACKOFF_SECONDS=1.0
```

## Run With uv

CLI examples:

```bash
uv run python main.py db tables
uv run python main.py db upsert --table jobs_final --payload-file payloads/jobs_final_upsert.json
uv run python main.py enricher enrich --limit 20 --dry-run
uv run python main.py pipeline run payloads/jobs_raw.json --limit 20
```

Start the server:

```bash
uv run uvicorn server:app --host 0.0.0.0 --port 8000
```

Or run with Python directly:

```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

Or use the VS Code task:

```text
Task: Start Server (uv)
```

Open API docs:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

Quick server checks:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/tables
```

Expected health response shape:

```json
{
  "status": "ok",
  "supabase_configured": true,
  "copilot_configured": true
}
```

## HTTP API

System endpoints:

- `GET /health`
- `GET /tables`

Table endpoints use the consolidated `/db/{table}` contract. Supported table slugs are:

- `jobs-final`
- `jobs-raw`
- `jobs-enriched`
- `shared-links`
- `job-decisions`
- `job-approvals`
- `job-metrics`

Available table operations:

- `GET /db/{table}` list rows with optional filters from query parameters
- `GET /db/{table}/{record_id}` fetch one record by primary key
- `POST /db/{table}` create rows using insert or upsert depending on table defaults
- `PATCH /db/{table}/{record_id}` update one record by primary key
- `DELETE /db/{table}/{record_id}` hard delete one record
- `DELETE /db/{table}/{record_id}/soft` soft delete for `jobs-final` and `jobs-raw`

Important HTTP constraints:

- legacy HTTP routes are not supported
- `job-metrics` is patch-only over HTTP; `POST /db/job-metrics` returns `405`
- list filtering uses plain query parameters, for example `?job_status=Applied&company_name=Acme`
- list ordering uses `order_by` and `ascending`

### Supported request and response

`GET /health`

Request body: none

Success response:

```json
{
  "status": "ok",
  "supabase_configured": true,
  "copilot_configured": true
}
```

`GET /tables`

Request body: none

Success response:

```json
{
  "tables": ["jobs_final", "jobs_raw", "shared_links"],
  "default_conflict_keys": {
    "jobs_final": "job_id",
    "jobs_raw": "id"
  }
}
```

`GET /db/{table}` and `GET /db/{table}/{record_id}`

Success response:

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

Common error:

```json
{
  "detail": "Unknown table 'not-a-table'. Available: ['job-approvals', 'job-decisions', 'job-metrics', 'jobs-enriched', 'jobs-final', 'jobs-raw', 'shared-links']"
}
```

`POST /db/{table}`, `PATCH /db/{table}/{record_id}`, `DELETE /db/{table}/{record_id}`, and `DELETE /db/{table}/{record_id}/soft`

Success response:

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

Common error for unsupported create on `job-metrics`:

```json
{
  "detail": "job_metrics is a patch-only table. Use PATCH instead."
}
```

`POST /enricher/run`

Request body:

```json
{
  "limit": 50,
  "dry_run": false
}
```

Success response:

```json
{
  "processed": 10,
  "enriched": 8,
  "skipped": 1,
  "failed": 1,
  "errors": []
}
```

`POST /pipeline/run`

Request body:

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

Success response:

```json
{
  "stages": [
    {
      "stage": "raw",
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

`POST /pipeline/stage/metrics`

Request body:

```json
{
  "scraped_count": 10,
  "enriched_count": 8
}
```

Common error:

```json
{
  "detail": "scraped_count must be greater than or equal to 0"
}
```

### Add data to every table

`jobs-final`

```bash
curl -X POST http://localhost:8000/db/jobs-final \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"job_id":"550e8400-e29b-41d4-a716-446655440000","company_name":"Acme Corp","role_title":"Senior Android Engineer","job_status":"Saved","job_url":"https://example.com/jobs/123"}]}'
```

`jobs-raw`

```bash
curl -X POST http://localhost:8000/db/jobs-raw \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"company_name":"Acme Corp","role_title":"Backend Engineer","job_url":"https://example.com/jobs/1","description":"Build APIs"}]}'
```

`jobs-enriched`

```bash
curl -X POST http://localhost:8000/db/jobs-enriched \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"job_id":"550e8400-e29b-41d4-a716-446655440000","experience_level":"Senior","remote_type":"Remote","english_friendly":true,"tech_stack":["Python","FastAPI"]}]}'
```

`shared-links`

```bash
curl -X POST http://localhost:8000/db/shared-links \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"url":"https://www.linkedin.com/jobs/view/123","source":"android-share-intent","status":"Pending"}]}'
```

`job-decisions`

```bash
curl -X POST http://localhost:8000/db/job-decisions \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"job_id":"550e8400-e29b-41d4-a716-446655440000","decision":"REVIEW","reason":"Needs human review"}]}'
```

`job-approvals`

```bash
curl -X POST http://localhost:8000/db/job-approvals \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"job_id":"550e8400-e29b-41d4-a716-446655440000","decision_id":"11111111-1111-1111-1111-111111111111","user_action":"APPROVED"}]}'
```

`job-metrics`

`job_metrics` is patch-only, so the supported write path is to update the singleton row:

```bash
curl -X PATCH http://localhost:8000/db/job-metrics/1 \
  -H "Content-Type: application/json" \
  -d '{"payload":{"total_scraped":1200,"total_enriched":800,"updated_at":"2026-04-11T12:00:00.000Z"}}'
```

## CLI

The CLI uses the `db`, `enricher`, and `pipeline` groups.

Examples:

```bash
uv run python main.py db patch-metrics --payload '{"total_scraped":1200}'
uv run python main.py db soft-delete --table jobs_final --record-id 550e8400-e29b-41d4-a716-446655440000
uv run python main.py db patch --table jobs_final --filter-column job_id --filter-value 550e8400-e29b-41d4-a716-446655440000 --payload '{"job_status":"Applied"}'
uv run python main.py db delete --table jobs_raw --filter-column id --filter-value 550e8400-e29b-41d4-a716-446655440000 --treat-404-as-success
uv run python main.py enricher enrich --limit 50
uv run python main.py pipeline stage-enriched --limit 20 --dry-run
```

Run API tests only:

```bash
uv run python -m pytest tests/test_api_server.py -v
```

## Python Library

Use the shared client and config from `common`, the database boundary in `repository`, and business workflows in `service`.

Generic repository usage:

```python
from common.client import PostgrestClient
from common.config import load_config
from repository.supabase import SupabaseRepository

repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
result = repo.upsert_rows(
    table="jobs_final",
    rows=[{"job_id": "550e8400-e29b-41d4-a716-446655440000"}],
)
print(result)
```

Table service usage:

```python
from common.client import PostgrestClient
from common.config import load_config
from repository.supabase import SupabaseRepository
from service.tables import upsert_jobs_final

repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
result = upsert_jobs_final(repo, [{"job_id": "550e8400-e29b-41d4-a716-446655440000"}])
print(result)
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

result = run_pipeline(
    repo=repo,
    copilot_client=copilot,
    rows=[
        {
            "company_name": "Acme Corp",
            "role_title": "Senior Android Engineer",
            "job_url": "https://www.linkedin.com/jobs/view/1234567890",
            "description": "Build and maintain Android platform features."
        }
    ],
    limit=50,
    dry_run=False,
)
print(result)
  ```
