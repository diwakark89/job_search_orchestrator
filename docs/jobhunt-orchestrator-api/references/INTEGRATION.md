# Integration Guide: Automated Job Hunt Orchestrator

This reference is the current integration contract for developers and AI agents using this project.

It explains:

- the supported integration surfaces
- the consolidated `/db/{table}` HTTP API
- supported request and response shapes
- the repository and service Python modules
- the current CLI commands

## Integration Surfaces

This project exposes three supported interfaces:

1. CLI commands via `main.py`
2. Python API via `common`, `repository`, `service`, `job_enricher`, and `pipeline`
3. HTTP API via FastAPI (`server:app`)

## Architecture Layers

- `common`: shared client, config, constants, validators, and db CLI
- `repository`: `SupabaseRepository`, the only database access boundary
- `service`: table helpers plus enricher and pipeline orchestration
- `api`: FastAPI routes built on top of repository and service layers

## Migration Note

Legacy HTTP routes and the old CLI command group are no longer part of the supported contract.

Use these surfaces instead:

- HTTP under `/db/{table}`
- CLI under `python main.py db ...`
- Python imports through `common`, `repository`, and `service`

## Supported Tables

- `jobs_final`
- `shared_links`
- `jobs_raw`
- `jobs_enriched`
- `job_decisions`
- `job_approvals`
- `job_metrics`

## Table Slug Mapping

| URL slug | Database table | Primary key |
| --- | --- | --- |
| `jobs-final` | `jobs_final` | `job_id` |
| `jobs-raw` | `jobs_raw` | `id` |
| `jobs-enriched` | `jobs_enriched` | `job_id` |
| `shared-links` | `shared_links` | `id` |
| `job-decisions` | `job_decisions` | `id` |
| `job-approvals` | `job_approvals` | `decision_id` |
| `job-metrics` | `job_metrics` | `id` |

## Setup

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

Install with the preferred tool:

```bash
uv sync
```

Or:

```bash
pip install -r requirements.txt
```

Start the API server:

```bash
uv run uvicorn server:app --host 0.0.0.0 --port 8000
```

## HTTP API

System endpoints:

- `GET /health`
- `GET /tables`

Table endpoints:

- `GET /db/{table}` list rows with query filters
- `GET /db/{table}/{record_id}` fetch one row by primary key
- `POST /db/{table}` insert or upsert rows depending on table defaults
- `PATCH /db/{table}/{record_id}` patch one row by primary key
- `DELETE /db/{table}/{record_id}` hard delete one row
- `DELETE /db/{table}/{record_id}/soft` soft delete for `jobs-final` and `jobs-raw`

### Supported request and response

`GET /health`

Success response:

```json
{
  "status": "ok",
  "supabase_configured": true,
  "copilot_configured": true
}
```

`GET /tables`

Success response:

```json
{
  "tables": ["jobs_final", "jobs_raw", "shared_links"],
  "default_conflict_keys": {
    "jobs_final": "job_id",
    "jobs_raw": "job_url",
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
  "scraped_count": 10
}
```

Important HTTP constraints:

- `job_metrics` is patch-only
- `POST /db/job-metrics` returns `405`
- soft delete is supported only for `jobs-final` and `jobs-raw`

## Per-table Add and Write Examples

The examples below show the supported write path for every table.

### `jobs-final`

```bash
curl -X POST http://localhost:8000/db/jobs-final -H "Content-Type: application/json" -d '{"rows":[{"job_id":"550e8400-e29b-41d4-a716-446655440000","company_name":"Acme Corp","role_title":"Senior Android Engineer","job_status":"Saved","job_url":"https://example.com/jobs/123"}]}'
```

### `jobs-raw`

```bash
curl -X POST http://localhost:8000/db/jobs-raw -H "Content-Type: application/json" -d '{"rows":[{"company_name":"Acme Corp","role_title":"Backend Engineer","job_url":"https://example.com/jobs/1","description":"Build APIs"}]}'
```

### `jobs-enriched`

```bash
curl -X POST http://localhost:8000/db/jobs-enriched -H "Content-Type: application/json" -d '{"rows":[{"job_id":"550e8400-e29b-41d4-a716-446655440000","experience_level":"Senior","remote_type":"Remote","english_friendly":true,"tech_stack":["Python","FastAPI"]}]}'
```

### `shared-links`

```bash
curl -X POST http://localhost:8000/db/shared-links -H "Content-Type: application/json" -d '{"rows":[{"url":"https://www.linkedin.com/jobs/view/123","source":"android-share-intent","status":"Pending"}]}'
```

### `job-decisions`

```bash
curl -X POST http://localhost:8000/db/job-decisions -H "Content-Type: application/json" -d '{"rows":[{"job_id":"550e8400-e29b-41d4-a716-446655440000","decision":"REVIEW","reason":"Needs human review"}]}'
```

### `job-approvals`

```bash
curl -X POST http://localhost:8000/db/job-approvals -H "Content-Type: application/json" -d '{"rows":[{"job_id":"550e8400-e29b-41d4-a716-446655440000","decision_id":"11111111-1111-1111-1111-111111111111","user_action":"APPROVED"}]}'
```

### `job-metrics`

`job_metrics` is patch-only, so the supported write path is:

```bash
curl -X PATCH http://localhost:8000/db/job-metrics/1 -H "Content-Type: application/json" -d '{"payload":{"total_scraped":1200,"total_enriched":800,"updated_at":"2026-04-11T12:00:00.000Z"}}'
```

Orchestration endpoints:

- `POST /enricher/run`
- `POST /pipeline/run`
- `POST /pipeline/stage/raw`
- `POST /pipeline/stage/enriched`
- `POST /pipeline/stage/metrics`

## CLI

The CLI groups are:

- `python main.py db ...`
- `python main.py enricher ...`
- `python main.py pipeline ...`

Examples:

```bash
uv run python main.py db tables
uv run python main.py db patch-metrics --payload '{"total_scraped":1200}'
uv run python main.py enricher enrich --limit 20 --dry-run
uv run python main.py pipeline run payloads/jobs_raw.json --limit 20
```

## Python API

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

## Behavioral Notes

- Stage 1 validates each `jobs_raw` row independently
- valid Stage 1 rows still write even if some rows are invalid
- the enricher reads `jobs_raw` rows where `job_status = SCRAPED` and `is_deleted = false`
- successful enrichment patches `jobs_raw.job_status` to `ENRICHED`
- dry-run pipeline skips Stage 3 metrics writes
