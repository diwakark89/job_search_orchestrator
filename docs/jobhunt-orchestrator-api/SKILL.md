---
name: jobhunt-orchestrator-api
description: >-
  Integration skill for the Automated Job Hunt Orchestrator. Use when asked to call
  the consolidated FastAPI table API under `/db/{table}`, run the enricher or pipeline
  routes, use the CLI groups under `main.py db`, `main.py enricher`, or
  `main.py pipeline`, or write Python code against the `common`, `repository`, and
  `service` layers. Covers supported table slugs, request and response shapes,
  representative success and error responses, patch-only `job_metrics` behavior,
  service and repository imports, and the current CLI and HTTP contract.
---

# Orchestrator API Skill

This skill teaches you how to interact with the current Automated Job Hunt Orchestrator integration surface.

## When to Use This Skill

- Calling the FastAPI table API under `/db/{table}`
- Running the enricher or pipeline over HTTP
- Running CLI workflows via `main.py`
- Writing Python code against `common`, `repository`, `service`, `job_enricher`, or `pipeline`
- Checking valid table slugs, primary keys, conflict keys, request bodies, or response shapes
- Verifying the current `/db/{table}` and `main.py db ...` contract

## Current Structure

```text
main.py
server.py
src/
  api/
    routes/
      system.py
      tables.py
      enricher.py
      pipeline.py
  common/
    client.py
    config.py
    constants.py
    validators.py
    cli.py
  repository/
    supabase.py
  service/
    tables.py
    enricher.py
    pipeline.py
  job_enricher/
    cli.py
    client_copilot.py
    config.py
    extractors.py
  pipeline/
    cli.py
    models.py
```

## HTTP API

System endpoints:

- `GET /health`
- `GET /tables`

Table endpoints:

- `GET /db/{table}`
- `GET /db/{table}/{record_id}`
- `POST /db/{table}`
- `PATCH /db/{table}/{record_id}`
- `DELETE /db/{table}/{record_id}`
- `DELETE /db/{table}/{record_id}/soft`

Supported table slugs:

| Slug            | Table           | Primary key   |
| --------------- | --------------- | ------------- |
| `jobs-final`    | `jobs_final`    | `job_id`      |
| `jobs-raw`      | `jobs_raw`      | `id`          |
| `jobs-enriched` | `jobs_enriched` | `job_id`      |
| `shared-links`  | `shared_links`  | `id`          |
| `job-decisions` | `job_decisions` | `id`          |
| `job-approvals` | `job_approvals` | `decision_id` |
| `job-metrics`   | `job_metrics`   | `id`          |

Query behavior for `GET /db/{table}`:

- extra query params become equality filters
- `order_by` and `ascending` control ordering
- `limit` and `offset` control pagination
- `columns` controls selected columns

## Supported Request and Response

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

## Add Data to Every Table

`jobs-final`

```bash
curl -X POST http://localhost:8000/db/jobs-final -H "Content-Type: application/json" -d '{"rows":[{"job_id":"550e8400-e29b-41d4-a716-446655440000","company_name":"Acme Corp","role_title":"Senior Android Engineer","job_status":"Saved","job_url":"https://example.com/jobs/123"}]}'
```

`jobs-raw`

```bash
curl -X POST http://localhost:8000/db/jobs-raw -H "Content-Type: application/json" -d '{"rows":[{"company_name":"Acme Corp","role_title":"Backend Engineer","job_url":"https://example.com/jobs/1","description":"Build APIs","pipeline_stage":"SCRAPED"}]}'
```

`jobs-enriched`

```bash
curl -X POST http://localhost:8000/db/jobs-enriched -H "Content-Type: application/json" -d '{"rows":[{"job_id":"550e8400-e29b-41d4-a716-446655440000","experience_level":"Senior","remote_type":"Remote","english_friendly":true,"tech_stack":["Python","FastAPI"]}]}'
```

`shared-links`

```bash
curl -X POST http://localhost:8000/db/shared-links -H "Content-Type: application/json" -d '{"rows":[{"url":"https://www.linkedin.com/jobs/view/123","source":"android-share-intent","status":"Pending"}]}'
```

`job-decisions`

```bash
curl -X POST http://localhost:8000/db/job-decisions -H "Content-Type: application/json" -d '{"rows":[{"job_id":"550e8400-e29b-41d4-a716-446655440000","decision":"REVIEW","reason":"Needs human review"}]}'
```

`job-approvals`

```bash
curl -X POST http://localhost:8000/db/job-approvals -H "Content-Type: application/json" -d '{"rows":[{"job_id":"550e8400-e29b-41d4-a716-446655440000","decision_id":"11111111-1111-1111-1111-111111111111","user_action":"APPROVED"}]}'
```

`job-metrics`

`job_metrics` is patch-only, so the supported write path is:

```bash
curl -X PATCH http://localhost:8000/db/job-metrics/1 -H "Content-Type: application/json" -d '{"payload":{"total_scraped":1200,"total_enriched":800,"updated_at":"2026-04-11T12:00:00.000Z"}}'
```

Constraints:

- `job_metrics` is patch-only over HTTP
- soft delete is supported only for `jobs-final` and `jobs-raw`
- full request and response coverage lives in `docs/INTEGRATION.md`

## CLI

CLI groups remain:

```bash
python main.py db tables
python main.py db upsert --table jobs_final --payload-file payloads/jobs_final_upsert.json
python main.py db patch-metrics --payload '{"total_scraped":1200}'
python main.py enricher enrich --limit 20 --dry-run
python main.py pipeline run payloads/jobs_raw.json --limit 20
```

Extra CLI examples:

```bash
python main.py db patch --table jobs_final --filter-column job_id --filter-value 550e8400-e29b-41d4-a716-446655440000 --payload '{"job_status":"Applied"}'
python main.py db delete --table jobs_raw --filter-column id --filter-value 550e8400-e29b-41d4-a716-446655440000 --treat-404-as-success
python main.py pipeline stage-metrics --scraped 10
```

## Python API

Preferred imports use repository and service layers.

Repository example:

```python
from common.client import PostgrestClient
from common.config import load_config
from repository.supabase import SupabaseRepository

repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
result = repo.select_rows(table="jobs_final", filters={"job_status": "Applied"})
```

Service helper example:

```python
from common.client import PostgrestClient
from common.config import load_config
from repository.supabase import SupabaseRepository
from service.tables import upsert_jobs_final

repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
upsert_jobs_final(repo, [{"job_id": "550e8400-e29b-41d4-a716-446655440000"}])
```
