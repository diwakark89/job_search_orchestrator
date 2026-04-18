---
name: jobhunt-orchestrator-api
description: >-
  Integration skill for the Automated Job Hunt Orchestrator. Use when asked to call
  the consolidated FastAPI table API under `/db/{table}`, run the enricher or pipeline
  routes, use the CLI groups under `main.py db`, `main.py enricher`, or
  `main.py pipeline`, or write Python code against the `common`, `repository`, and
  `service` layers. Covers supported table slugs, request and response shapes,
  representative success and error responses,
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

| Slug           | Table          | Primary key |
| -------------- | -------------- | ----------- |
| `jobs-final`   | `jobs_final`   | `id`        |
| `shared-links` | `shared_links` | `id`        |

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
  "tables": ["jobs_final", "shared_links"],
  "default_conflict_keys": {
    "jobs_final": "id",
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
      "id": "550e8400-e29b-41d4-a716-446655440000",
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

`GET /pipeline/metrics`

Success response:

```json
{
  "status_counts": {
    "SAVED": 10,
    "SCRAPED": 5,
    "ENRICHED": 3
  },
  "total": 18
}
```

## Add Data to Every Table

`jobs-final`

```bash
curl -X POST http://localhost:8000/db/jobs-final -H "Content-Type: application/json" -d '{"rows":[{"id":"550e8400-e29b-41d4-a716-446655440000","company_name":"Acme Corp","role_title":"Senior Android Engineer","job_status":"SAVED","job_url":"https://example.com/jobs/123"}]}'
```

`shared-links`

```bash
curl -X POST http://localhost:8000/db/shared-links -H "Content-Type: application/json" -d '{"rows":[{"url":"https://www.linkedin.com/jobs/view/123","source":"android-share-intent"}]}'
```

Constraints:

- soft delete is supported only for `jobs-final`
- full request and response coverage lives in `docs/INTEGRATION.md`

## POST /pipeline/submit — Async Submit Flow

Use `/pipeline/submit` when you have raw job listings to ingest **and** want background enrichment to run automatically without waiting. The endpoint returns `202` immediately after queueing.

**When to use it:**

- Ingesting new scraped jobs from a mobile share or automation and enriching them in the background
- You want a fire-and-forget pattern: submit jobs, get ids back, let enrichment happen asynchronously
- You want `shared_links` rows created automatically alongside job records

**What it does:**

1. Validates each row independently; invalid rows are rejected per-row
2. Upserts valid rows into `jobs_final` with `job_status=SCRAPED`, deduplicated by `job_url`
3. Upserts matching `shared_links` rows
4. Queues background enrichment **only** for accepted ids
5. Background worker sets `job_status=SAVED` on success

Request body:

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

Success response (`202`):

```json
{
  "submitted_row_count": 2,
  "accepted": { "count": 1, "ids": ["550e8400-e29b-41d4-a716-446655440000"] },
  "queued": { "count": 1, "ids": ["550e8400-e29b-41d4-a716-446655440000"] },
  "rejected_row_indexes": [1],
  "errors": ["row[1]: Extra inputs are not permitted"],
  "jobs_final_row_count": 1,
  "shared_links_row_count": 1
}
```

Common error (`400`) when every row is invalid:

```json
{ "detail": "No valid jobs submitted. row[0]: job_url is required." }
```

Notes:

- `job_type` canonical values: `fulltime`, `parttime`, `internship`, `contract`, `temporary`, `other`. Unmatched input → `other`.
- `work_mode` canonical values: `remote`, `hybrid`, `on-site`, `other`. Unmatched input → `other`.
- Background enrichment is in-process and non-durable. If the API restarts, queued work is lost.
- Logs include a per-request `submit_request_id` UUID that correlates route → background worker → enricher entries.

## Which Endpoint to Use

| Goal                                               | Use endpoint                           | Notes                                                        |
| -------------------------------------------------- | -------------------------------------- | ------------------------------------------------------------ |
| Ingest new raw jobs and enrich automatically       | `POST /pipeline/submit`                | Returns 202; background enrichment; `shared_links` created   |
| Ingest + enrich synchronously in one blocking call | `POST /pipeline/run`                   | Waits for full pipeline; returns combined stage results      |
| Ingest jobs only (no enrichment)                   | `POST /pipeline/stage/ingest`          | Writes rows as `SCRAPED`; no enrichment triggered            |
| Enrich `SCRAPED` rows already in the DB            | `POST /pipeline/stage/enriched`        | Picks up existing `SCRAPED` rows; enriches by limit          |
| Trigger enrichment for all `SCRAPED` rows          | `POST /enricher/run`                   | Same as stage/enriched but via enricher surface              |
| Enrich a specific set of ids on demand             | `POST /enricher/by-ids`                | Targeted enrichment; set `set_job_status_enriched` as needed |
| Read, update, or delete individual records         | `GET/POST/PATCH/DELETE /db/jobs-final` | Direct table CRUD; no enrichment logic                       |

## CLI

CLI groups remain:

```bash
python main.py db tables
python main.py db upsert --table jobs_final --payload-file payloads/jobs_final_upsert.json
python main.py enricher enrich --limit 20 --dry-run
python main.py pipeline run payloads/jobs_raw.json --limit 20
```

Extra CLI examples:

```bash
python main.py db patch --table jobs_final --filter-column id --filter-value 550e8400-e29b-41d4-a716-446655440000 --payload '{"job_status":"APPLIED"}'
python main.py pipeline stage-enriched --limit 20 --dry-run
```

## Python API

Preferred imports use repository and service layers.

Repository example:

```python
from common.client import PostgrestClient
from common.config import load_config
from repository.supabase import SupabaseRepository

repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
result = repo.select_rows(table="jobs_final", filters={"job_status": "APPLIED"})
```

Service helper example:

```python
from common.client import PostgrestClient
from common.config import load_config
from repository.supabase import SupabaseRepository
from service.tables import upsert_jobs_final

repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
upsert_jobs_final(repo, [{"id": "550e8400-e29b-41d4-a716-446655440000"}])
```
