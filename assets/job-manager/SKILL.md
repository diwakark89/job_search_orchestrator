---
name: job_manager
description: Search supported job boards, submit scraped jobs for async persistence and enrichment, and perform jobs-final CRUD operations in the Automated Job Hunt Orchestrator. Use when the user asks to find jobs, save scraped jobs to the database, update job status, soft-delete records, enrich by ids, or read pipeline metrics.
metadata:
  {
    "openclaw":
      { "requires": { "bins": ["curl"] }, "os": ["darwin", "linux", "win32"] },
  }
---

# Job Manager Skill

Manage jobs in the **Automated Job Hunt Orchestrator** running locally on `http://localhost:8000`. This skill covers three main workflows:

- search jobs across supported external job boards
- save scraped jobs through the pipeline submit flow
- perform CRUD-style operations against `jobs_final`

> Format reference: this skill follows the OpenClaw skill spec at <https://docs.openclaw.ai/tools/creating-skills>.

## When to Use

Use this skill when the user asks to:

- **Search / scrape** jobs from supported boards such as LinkedIn, Indeed, and Glassdoor
- **Submit** scraped jobs for ingestion and background enrichment
- **List / query** tracked jobs by company, status, role, or other fields
- **Get** a single job by id
- **Update** a job (e.g. mark `job_status` as `APPLIED`, `INTERVIEWING`, `REJECTED`)
- **Soft-delete** a job (sets `is_deleted=true` instead of removing the row)
- **Hard-delete** a job when permanent removal is required
- **Run enrichment** on `SCRAPED` rows or a specific list of ids
- **Read pipeline metrics** to see counts by `job_status`

## Prerequisites

- Orchestrator FastAPI server running on `http://localhost:8000`:

  ```bash
  uv run uvicorn server:app --host 0.0.0.0 --port 8000
  ```

- Verify health:

  ```bash
  curl http://localhost:8000/health
  ```

- If the server has `API_KEY` configured, include `X-API-Key: <value>` on every HTTP request.
- CLI examples assume you are in the repository root with the project environment available.

## Supported Job Boards

Use `python main.py job-search ...` to scrape jobs from boards supported by the orchestrator. The exact board ids and search guardrails are documented in [supported-job-boards.md](./references/supported-job-boards.md).

Common examples:

```bash
python main.py job-search "software engineer" --sites linkedin,indeed --results 5 --hours-old 24
```

```bash
job-search "data scientist" --sites linkedin,glassdoor --results 3 --country germany
```

## Save Flow: Use Pipeline Submit

When the user wants to **save scraped jobs to the database**, the primary flow is:

- HTTP: `POST /pipeline/submit`
- CLI: `python main.py job-manage pipeline submit <file.json>`

This route validates input rows, writes accepted jobs into `jobs_final` with initial `job_status=SCRAPED`, and queues asynchronous enrichment. It returns **HTTP 202** immediately.

### HTTP Submit Example

```bash
curl -X POST "http://localhost:8000/pipeline/submit" \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

Expected response shape:

```json
{
  "submitted_row_count": 1,
  "accepted": { "count": 1, "ids": ["550e8400-e29b-41d4-a716-446655440000"] },
  "queued": { "count": 1, "ids": ["550e8400-e29b-41d4-a716-446655440000"] },
  "rejected_row_indexes": [],
  "errors": [],
  "jobs_final_row_count": 1
}
```

### CLI Submit Example

```bash
python main.py job-manage pipeline submit payloads/jobs_raw.json
```

The JSON file may contain either a top-level array of job objects or an object with a `jobs` array.

## Method A: HTTP CRUD And Operations

All supported HTTP routes in this skill operate on the `jobs-final` slug, which maps to the `jobs_final` table.

### Endpoint Reference

| Operation           | Method   | Path                              |
| ------------------- | -------- | --------------------------------- |
| List rows           | `GET`    | `/db/jobs-final`                  |
| Get one row         | `GET`    | `/db/jobs-final/{id}`             |
| Upsert rows         | `POST`   | `/db/jobs-final`                  |
| Patch one row       | `PATCH`  | `/db/jobs-final/{id}`             |
| Hard delete one row | `DELETE` | `/db/jobs-final/{id}`             |
| Soft-delete one row | `DELETE` | `/db/jobs-final/{id}/soft`        |
| Submit jobs         | `POST`   | `/pipeline/submit`                |
| Run enricher        | `POST`   | `/enricher/run`                   |
| Enrich by ids       | `POST`   | `/enricher/by-ids?dry_run=<bool>` |
| Pipeline metrics    | `GET`    | `/pipeline/metrics`               |

### 1. List / Search Jobs

`GET /db/jobs-final` supports equality filters through query parameters. Reserved parameters are `columns`, `limit`, `offset`, `order_by`, and `ascending`.

```bash
curl "http://localhost:8000/db/jobs-final?job_status=APPLIED&company_name=Acme%20Corp&limit=5"
```

```bash
curl "http://localhost:8000/db/jobs-final?job_status=SAVED&columns=id,company_name,role_title,job_url&order_by=created_at&ascending=false&limit=10"
```

Response shape:

```json
{
  "rows": [],
  "count": 0,
  "table": "jobs_final"
}
```

### 2. Get One Job By Id

```bash
curl "http://localhost:8000/db/jobs-final/550e8400-e29b-41d4-a716-446655440000"
```

### 3. Upsert Jobs

`POST /db/jobs-final` expects a `rows` array.

```bash
curl -X POST "http://localhost:8000/db/jobs-final" \
  -H "Content-Type: application/json" \
  -d '{
    "rows": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "company_name": "Acme Corp",
        "role_title": "Senior Engineer",
        "job_url": "https://example.com/jobs/1",
        "job_status": "SAVED"
      }
    ]
  }'
```

### 4. Patch One Job

For the HTTP API, patch payloads must be wrapped in a `payload` object.

```bash
curl -X PATCH "http://localhost:8000/db/jobs-final/550e8400-e29b-41d4-a716-446655440000" \
  -H "Content-Type: application/json" \
  -d '{"payload": {"job_status": "APPLIED"}}'
```

### 5. Soft-Delete One Job

Soft delete sets `is_deleted=true`. The request body is optional. If provided, it supports `hard_delete`.

```bash
curl -X DELETE "http://localhost:8000/db/jobs-final/550e8400-e29b-41d4-a716-446655440000/soft"
```

```bash
curl -X DELETE "http://localhost:8000/db/jobs-final/550e8400-e29b-41d4-a716-446655440000/soft" \
  -H "Content-Type: application/json" \
  -d '{"hard_delete": true}'
```

### 6. Hard Delete One Job

```bash
curl -X DELETE "http://localhost:8000/db/jobs-final/550e8400-e29b-41d4-a716-446655440000"
```

### 7. Run Enricher

```bash
curl -X POST "http://localhost:8000/enricher/run" \
  -H "Content-Type: application/json" \
  -d '{"limit": 50, "dry_run": true}'
```

### 8. Enrich By Ids

`POST /enricher/by-ids` expects a JSON array of objects, not a wrapped payload.

```bash
curl -X POST "http://localhost:8000/enricher/by-ids?dry_run=true" \
  -H "Content-Type: application/json" \
  -d '[
    {"id": "550e8400-e29b-41d4-a716-446655440000"},
    {"id": "550e8400-e29b-41d4-a716-446655440001"}
  ]'
```

### 9. Pipeline Metrics

```bash
curl "http://localhost:8000/pipeline/metrics"
```

Response shape:

```json
{
  "status_counts": { "SAVED": 10, "SCRAPED": 5, "ENRICHED": 3 },
  "total": 18
}
```

## Method B: CLI Operations

Use the unified CLI for local operations.

| Operation             | Command                                                                                                                                  |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| List supported tables | `python main.py job-manage table tables`                                                                                                 |
| List rows             | `python main.py job-manage table list --table jobs_final --filter job_status=APPLIED --limit 10`                                         |
| Get one row           | `python main.py job-manage table get --table jobs_final --id <UUID>`                                                                     |
| Upsert rows           | `python main.py job-manage table upsert --table jobs_final --payload-file payloads/jobs_final_upsert.json`                               |
| Patch a row           | `python main.py job-manage table patch --table jobs_final --filter-column id --filter-value <UUID> --payload '{"job_status":"APPLIED"}'` |
| Soft-delete a row     | `python main.py job-manage table soft-delete --table jobs_final --record-id <UUID>`                                                      |
| Hard delete a row     | `python main.py job-manage table delete --table jobs_final --filter-column id --filter-value <UUID> --treat-404-as-success`              |
| Submit jobs           | `python main.py job-manage pipeline submit payloads/jobs_raw.json`                                                                       |
| Run enricher          | `python main.py job-manage enricher enrich --limit 20 --dry-run`                                                                         |
| Enrich by ids         | `python main.py job-manage enricher by-ids --ids <UUID1>,<UUID2> --dry-run`                                                              |
| Enrich by ids file    | `python main.py job-manage enricher by-ids --ids-file payloads/job_ids.json --dry-run`                                                   |
| Pipeline metrics      | `python main.py job-manage pipeline metrics`                                                                                             |
| Search job boards     | `python main.py job-search "software engineer" --sites linkedin,indeed --results 5`                                                      |

## Which Endpoint To Use

| Goal                           | Endpoint                                                | Notes                                                         |
| ------------------------------ | ------------------------------------------------------- | ------------------------------------------------------------- |
| Search external job boards     | `python main.py job-search ...`                         | Search/scrape is provided through the CLI surface             |
| Save scraped jobs to DB        | `POST /pipeline/submit`                                 | Primary persistence flow; returns `202` and queues enrichment |
| Ingest + enrich synchronously  | `POST /pipeline/run`                                    | Supported by the API, but submit is the preferred save flow   |
| Ingest jobs only               | `POST /pipeline/stage/ingest`                           | Writes rows as `SCRAPED`                                      |
| Enrich existing `SCRAPED` rows | `POST /enricher/run` or `POST /pipeline/stage/enriched` | Use `dry_run` to preview                                      |
| Enrich specific records        | `POST /enricher/by-ids`                                 | Send a JSON array of `{ "id": "..." }` items                  |
| Read/update/delete one job     | `/db/jobs-final/{id}`                                   | Direct `jobs_final` CRUD                                      |

## Field And Enum Reference

`jobs_final` fields commonly used in these workflows:

| Field          | Type   | Notes                                                                                                                    |
| -------------- | ------ | ------------------------------------------------------------------------------------------------------------------------ |
| `id`           | UUID   | Primary key and upsert conflict key                                                                                      |
| `company_name` | string | Company name                                                                                                             |
| `role_title`   | string | Job title                                                                                                                |
| `job_url`      | string | Unique URL used for dedupe during submit                                                                                 |
| `description`  | string | Raw or enriched description                                                                                              |
| `job_type`     | enum   | `fulltime`, `parttime`, `internship`, `contract`, `temporary`, `other`                                                   |
| `work_mode`    | enum   | `remote`, `hybrid`, `on-site`, `other`                                                                                   |
| `job_status`   | enum   | `SCRAPED`, `ENRICHED`, `SAVED`, `APPLIED`, `INTERVIEW`, `INTERVIEWING`, `OFFER`, `RESUME_REJECTED`, `INTERVIEW_REJECTED` |
| `is_deleted`   | bool   | Excluded from enricher pickup when true                                                                                  |

Important constraints:

- Unknown `job_type` and `work_mode` values normalize to `other`
- Do not send `job_id`; use `id`
- Do not send `remote_type`; use `work_mode`
- Rows containing unsupported fields such as `tags` may be rejected

## Error Responses

| HTTP | Cause                                    | Example body                                                                        |
| ---- | ---------------------------------------- | ----------------------------------------------------------------------------------- |
| 400  | Invalid request body or validation error | `{ "detail": "No valid jobs submitted. row[0]: job_url is required." }`             |
| 401  | Missing or wrong `X-API-Key`             | `{ "detail": "Invalid API key" }`                                                   |
| 404  | Unknown table slug                       | `{ "detail": "Unknown table 'foo'. Available: ['jobs-final']" }`                    |
| 502  | Upstream Supabase or Copilot failure     | `{ "detail": "..." }` or `{ "success": false, "status_code": 502, "error": "..." }` |

Always check HTTP status before trusting the response body.

## Tips

- Prefer `POST /pipeline/submit` instead of manual upsert + enrich for scraped jobs
- For status updates, patch only the fields that changed
- Use `dry_run: true` for enrich flows when you want a non-writing preview
- The enricher only picks up rows where `job_status=SCRAPED` and `is_deleted=false`

## Troubleshooting

- **Connection refused on `:8000`**: start the API server first
- **`401 Invalid API key`**: add the `X-API-Key` header when auth is enabled
- **`404 Unknown table`**: use the hyphenated slug `jobs-final`, not `jobs_final`
- **`400 Extra inputs are not permitted`**: remove unsupported fields such as `tags`, `remote_type`, or `job_id`
- **`502` from `/enricher/*`**: check server logs and upstream Copilot/Supabase configuration
- **Background enrichment from `/pipeline/submit` is in-process**: if the API restarts, rerun enrichment manually

## References

- [supported-job-boards.md](./references/supported-job-boards.md) — exact supported board ids and search guardrails
- [submit-and-crud-recipes.md](./references/submit-and-crud-recipes.md) — copy-ready submit, CRUD, enrich, and metrics recipes
- [`../../docs/INTEGRATION.md`](../../docs/INTEGRATION.md) — canonical integration contract
- [`../../docs/SUPABASE_SCHEMA.md`](../../docs/SUPABASE_SCHEMA.md) — current database schema notes
- <https://docs.openclaw.ai/tools/creating-skills> — OpenClaw skill format reference
