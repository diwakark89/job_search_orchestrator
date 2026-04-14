# Automated Job Hunt Orchestrator

This project exposes three integration surfaces for the Automated Job Hunt data pipeline:

- a FastAPI HTTP API for table CRUD and orchestration
- a Typer CLI for operator workflows
- a Python library split into `common`, `repository`, and `service` layers

The pipeline manages these Supabase tables:

- `jobs_final`
- `shared_links`

It also includes:

- an enricher that reads `jobs_final` rows where `job_status=SCRAPED` and patches enrichment data plus `job_status=ENRICHED` directly on `jobs_final`
- a 2-stage pipeline runner: `ingest → enrich`

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
- `shared-links`

Available table operations:

- `GET /db/{table}` list rows with optional filters from query parameters
- `GET /db/{table}/{record_id}` fetch one record by primary key
- `POST /db/{table}` create rows using insert or upsert depending on table defaults
- `PATCH /db/{table}/{record_id}` update one record by primary key
- `DELETE /db/{table}/{record_id}` hard delete one record
- `DELETE /db/{table}/{record_id}/soft` soft delete for `jobs-final`

Important HTTP constraints:

- legacy HTTP routes are not supported
- list filtering uses plain query parameters, for example `?job_status=APPLIED&company_name=Acme`
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
  "tables": ["jobs_final", "shared_links"],
  "default_conflict_keys": {
    "jobs_final": "job_id",
    "shared_links": "url"
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
      "job_status": "APPLIED"
    }
  ],
  "count": 1,
  "table": "jobs_final"
}
```

Common error:

```json
{
  "detail": "Unknown table 'not-a-table'. Available: ['jobs-final', 'shared-links']"
}
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

`POST /pipeline/stage/ingest`

### Add data to every table

`jobs-final`

```bash
curl -X POST http://localhost:8000/db/jobs-final \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"job_id":"550e8400-e29b-41d4-a716-446655440000","company_name":"Acme Corp","role_title":"Senior Android Engineer","job_status":"SAVED","job_url":"https://example.com/jobs/123"}]}'
```

`shared-links`

```bash
curl -X POST http://localhost:8000/db/shared-links \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"url":"https://www.linkedin.com/jobs/view/123","source":"android-share-intent","status":"Pending"}]}'
```

## CLI

The CLI uses the `db`, `enricher`, and `pipeline` groups.

Examples:

```bash
uv run python main.py db soft-delete --table jobs_final --record-id 550e8400-e29b-41d4-a716-446655440000
uv run python main.py db patch --table jobs_final --filter-column job_id --filter-value 550e8400-e29b-41d4-a716-446655440000 --payload '{"job_status":"APPLIED"}'
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
