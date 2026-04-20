---
name: job_manager
description: Search, query, update, soft-delete, submit, and enrich jobs in the local Automated Job Hunt Orchestrator (FastAPI + Typer CLI). Use when the user asks to look up tracked jobs, change a job's status (e.g. APPLIED), ingest scraped jobs, trigger enrichment, or read pipeline metrics.
metadata:
  {
    "openclaw":
      { "requires": { "bins": ["curl"] }, "os": ["darwin", "linux", "win32"] },
  }
---

# Job Manager Skill

Manage jobs tracked in the **Automated Job Hunt Orchestrator** running locally on `http://localhost:8000`. The orchestrator is a FastAPI + Typer service backed by Supabase (PostgREST). This skill teaches the agent how to search/query existing jobs, update them, soft-delete them, submit new scraped jobs for async enrichment, run enrichment on demand, and read pipeline metrics.

> Format reference: this skill follows the OpenClaw skill spec at <https://docs.openclaw.ai/tools/creating-skills>.

## When to Use

Use this skill when the user asks to:

- **Search / query** tracked jobs (by company, status, role, etc.)
- **Get** a single job by id
- **Update** a job (e.g. mark `job_status` as `APPLIED`, `INTERVIEWING`, `REJECTED`)
- **Soft-delete** a job (sets `is_deleted=true` instead of removing the row)
- **Submit** new scraped jobs for ingestion + background enrichment
- **Run enrichment** on existing `SCRAPED` rows or on a specific list of ids
- **Read pipeline metrics** (status counts)

If the user wants to **scrape** new jobs from external boards (LinkedIn, Indeed, etc.), that is a separate concern — the Job Search MCP server lives at `src/job_search_mcp_server/`.

## Prerequisites

- Orchestrator FastAPI server running (default `http://localhost:8000`). Start with VS Code task **Start Server (uv)** or:

  ```bash
  uv run uvicorn server:app --host 0.0.0.0 --port 8000
  ```

- Verify with `curl http://localhost:8000/health` — expect `{"status":"ok","supabase_configured":true,"copilot_configured":true}`.
- **Auth**: when the server has the `API_KEY` env var set, every request must include header `X-API-Key: <value>`. If `API_KEY` is unset (typical local dev), auth is disabled.
- **CLI method (Method B)** additionally requires `python` and `uv` on `PATH` and an activated `.venv`.

## Method A: HTTP via curl / web_fetch — Recommended

All endpoints accept and return JSON. Set `Content-Type: application/json` on requests with a body.

### Endpoint Reference

| Operation                   | Method   | Path                       |
| --------------------------- | -------- | -------------------------- |
| Health check                | `GET`    | `/health`                  |
| List tables                 | `GET`    | `/tables`                  |
| Search / list jobs          | `GET`    | `/db/jobs-final`           |
| Get one job by id           | `GET`    | `/db/jobs-final/{id}`      |
| Update a job                | `PATCH`  | `/db/jobs-final/{id}`      |
| Soft-delete a job           | `DELETE` | `/db/jobs-final/{id}/soft` |
| Submit scraped jobs (async) | `POST`   | `/pipeline/submit`         |
| Run enricher (all SCRAPED)  | `POST`   | `/enricher/run`            |
| Enrich specific ids         | `POST`   | `/enricher/by-ids`         |
| Pipeline metrics            | `GET`    | `/pipeline/metrics`        |

### 1. Search / list jobs

`GET /db/jobs-final` — extra query params become equality filters on columns. Reserved params: `columns`, `limit`, `offset`, `order_by`, `ascending`.

**Find applied jobs at Acme, newest first, max 5:**

```bash
curl "http://localhost:8000/db/jobs-final?company_name=Acme%20Corp&job_status=APPLIED&order_by=created_at&ascending=false&limit=5"
```

**Project only a few columns:**

```bash
curl "http://localhost:8000/db/jobs-final?job_status=SAVED&columns=id,company_name,role_title,job_url&limit=10"
```

Success response:

```json
{
  "rows": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "company_name": "Acme Corp",
      "role_title": "Senior Android Engineer",
      "job_status": "APPLIED",
      "job_url": "https://example.com/jobs/123"
    }
  ],
  "count": 1,
  "table": "jobs_final"
}
```

### 2. Get one job by id

```bash
curl "http://localhost:8000/db/jobs-final/550e8400-e29b-41d4-a716-446655440000"
```

Returns the same `{ "rows": [...], "count": 1, "table": "jobs_final" }` shape.

### 3. Update a job (PATCH)

Send only the fields you want to change. Common use case: move a job through the funnel by patching `job_status`.

**Mark a job as APPLIED:**

```bash
curl -X PATCH "http://localhost:8000/db/jobs-final/550e8400-e29b-41d4-a716-446655440000" \
  -H "Content-Type: application/json" \
  -d '{"job_status":"APPLIED"}'
```

Success response:

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

### 4. Soft-delete a job

Soft delete sets `is_deleted=true`. The row stays in the table but is excluded from enricher pickup. Supported only for `jobs-final`.

```bash
curl -X DELETE "http://localhost:8000/db/jobs-final/550e8400-e29b-41d4-a716-446655440000/soft"
```

### 5. Submit scraped jobs (async ingest + enrich)

`POST /pipeline/submit` validates each row, upserts valid ones into `jobs_final` with `job_status=SCRAPED` (deduped by `job_url`), upserts matching `shared_links`, and queues background enrichment. Returns **HTTP 202** immediately.

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

Success response (`202`):

```json
{
  "submitted_row_count": 1,
  "accepted": { "count": 1, "ids": ["550e8400-e29b-41d4-a716-446655440000"] },
  "queued": { "count": 1, "ids": ["550e8400-e29b-41d4-a716-446655440000"] },
  "rejected_row_indexes": [],
  "errors": [],
  "jobs_final_row_count": 1,
  "shared_links_row_count": 1
}
```

### 6. Run enricher

**All `SCRAPED` rows (limit 50, dry run preview):**

```bash
curl -X POST "http://localhost:8000/enricher/run" \
  -H "Content-Type: application/json" \
  -d '{"limit": 50, "dry_run": true}'
```

**Specific ids:**

```bash
curl -X POST "http://localhost:8000/enricher/by-ids" \
  -H "Content-Type: application/json" \
  -d '[{"id":"550e8400-e29b-41d4-a716-446655440000"}]'
```

Success response (both):

```json
{
  "processed": { "count": 1, "ids": ["550e8400-e29b-41d4-a716-446655440000"] },
  "enriched": { "count": 1, "ids": ["550e8400-e29b-41d4-a716-446655440000"] },
  "skipped": { "count": 0, "ids": [] },
  "failed": { "count": 0, "ids": [] },
  "errors": []
}
```

### 7. Pipeline metrics

```bash
curl "http://localhost:8000/pipeline/metrics"
```

```json
{
  "status_counts": { "SAVED": 10, "SCRAPED": 5, "ENRICHED": 3 },
  "total": 18
}
```

## Method B: CLI via `exec` tool

Run from the orchestrator project root with the `.venv` activated.

| Operation             | Command                                                                                                                                  |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| List supported tables | `python main.py job-manage table tables`                                                                                                 |
| List rows             | `python main.py job-manage table list --table jobs_final --filter job_status=APPLIED --limit 10`                                         |
| Get one row           | `python main.py job-manage table get --table jobs_final --id <UUID>`                                                                     |
| Upsert rows           | `python main.py job-manage table upsert --table jobs_final --payload-file payloads/jobs_final_upsert.json`                               |
| Patch a row           | `python main.py job-manage table patch --table jobs_final --filter-column id --filter-value <UUID> --payload '{"job_status":"APPLIED"}'` |
| Run enricher          | `python main.py job-manage enricher enrich --limit 20 --dry-run`                                                                         |
| Enrich by ids         | `python main.py job-manage enricher by-ids --ids <UUID1>,<UUID2> --dry-run`                                                              |
| Run full pipeline     | `python main.py job-manage pipeline run payloads/jobs_raw.json --limit 20`                                                               |
| Pipeline submit       | `python main.py job-manage pipeline submit payloads/jobs_raw.json`                                                                       |
| Pipeline metrics      | `python main.py job-manage pipeline metrics`                                                                                             |
| Stage: enrich SCRAPED | `python main.py job-manage pipeline stage-enriched --limit 20 --dry-run`                                                                 |

## Which Endpoint to Use

| Goal                                               | Endpoint                                           | Notes                                                      |
| -------------------------------------------------- | -------------------------------------------------- | ---------------------------------------------------------- |
| Ingest new raw jobs and enrich automatically       | `POST /pipeline/submit`                            | Returns 202; background enrichment; `shared_links` created |
| Ingest + enrich synchronously in one blocking call | `POST /pipeline/run`                               | See canonical doc; not covered in detail here              |
| Ingest jobs only (no enrichment)                   | `POST /pipeline/stage/ingest`                      | Writes rows as `SCRAPED`; no enrichment triggered          |
| Enrich existing `SCRAPED` rows                     | `POST /pipeline/stage/enriched` or `/enricher/run` | Same effect; pick by limit                                 |
| Enrich a specific set of ids                       | `POST /enricher/by-ids`                            | Targeted enrichment                                        |
| Read, update, or soft-delete a single record       | `GET/PATCH/DELETE /db/jobs-final[/{id}]`           | Direct table CRUD; no enrichment logic                     |
| `shared_links` CRUD                                | `GET/POST/PATCH/DELETE /db/shared-links`           | Out of scope here; see canonical doc                       |

## Field & Enum Reference

`jobs_final` row fields used in examples:

| Field          | Type   | Notes                                                                          |
| -------------- | ------ | ------------------------------------------------------------------------------ |
| `id`           | UUID   | Primary key **and** conflict key for upserts. Do **not** use `job_id`.         |
| `company_name` | string | —                                                                              |
| `role_title`   | string | —                                                                              |
| `job_url`      | string | Used for `shared_links` dedupe via `on_conflict=url`.                          |
| `description`  | string | Free text from scrape; enriched downstream.                                    |
| `job_type`     | enum   | One of `fulltime`, `parttime`, `internship`, `contract`, `temporary`, `other`. |
| `work_mode`    | enum   | One of `remote`, `hybrid`, `on-site`, `other`. **Do not send `remote_type`.**  |
| `job_status`   | enum   | Pipeline lifecycle: `SCRAPED` → `ENRICHED` → `SAVED` → `APPLIED` → ...         |
| `is_deleted`   | bool   | Set by soft-delete; excluded from enricher pickup.                             |

Constraints (verified):

- Unmatched `job_type` / `work_mode` values normalize to `other`.
- `tags` is **not** an accepted field on `jobs_final`; rows containing it are rejected.
- `shared_links` payloads must **not** include a `status` field.

## Error Responses

| HTTP | Cause                                | Example body                                                                     |
| ---- | ------------------------------------ | -------------------------------------------------------------------------------- |
| 400  | Bad request body / unknown column    | `{ "detail": "No valid jobs submitted. row[0]: job_url is required." }`          |
| 401  | Missing/wrong `X-API-Key` (when set) | `{ "detail": "Invalid API key" }`                                                |
| 404  | Unknown table slug                   | `{ "detail": "Unknown table 'foo'. Available: ['jobs-final', 'shared-links']" }` |
| 502  | Upstream Supabase or Copilot failure | `{ "success": false, "status_code": 502, "error": "..." }`                       |

Always check HTTP status before parsing the body. For `/db/...` write operations, additionally check the `success` field in the response envelope.

## Tips

- For **search**, prefer narrow filters + `limit` to keep responses small.
- For **status updates**, PATCH only the changed field; do not echo back the full row.
- For **bulk ingestion**, prefer `POST /pipeline/submit` over manual upsert + enrich — it handles validation, dedupe, and background enrichment in one call.
- Use `dry_run: true` on `/enricher/run` to preview without writing.
- The enricher only picks up `jobs_final` rows where `job_status=SCRAPED` **and** `is_deleted=false`.

## Troubleshooting

- **Connection refused on `:8000`** — server is not running. Start it with the **Start Server (uv)** task or `uv run uvicorn server:app --host 0.0.0.0 --port 8000`.
- **`401 Invalid API key`** — server has `API_KEY` set; include `-H "X-API-Key: <value>"`.
- **`404 Unknown table 'xxx'`** — slug must be hyphenated (`jobs-final`, `shared-links`), not the underlying table name.
- **`400 Extra inputs are not permitted`** — payload includes a field rejected by the validator (e.g. `tags`, `remote_type`, `job_id`). Remove it.
- **`502` from `/enricher/*`** — Copilot/Supabase upstream failure. Check server logs and the `COPILOT_*` env vars.
- **Background enrichment from `/pipeline/submit` is in-process** — if the API restarts, queued work is lost. Re-run `/enricher/run` to retry.

## References

- [`../../docs/INTEGRATION.md`](../../docs/INTEGRATION.md) — canonical integration contract for HTTP endpoints, `job-manage` CLI, and `job-search` script usage.
- [`../../docs/SUPABASE_SCHEMA.md`](../../docs/SUPABASE_SCHEMA.md) — database schema for `jobs_final` and `shared_links`.
- <https://docs.openclaw.ai/tools/creating-skills> — OpenClaw skill format spec used by this file.
