# Automated Job Hunt Orchestrator

This project exposes four integration surfaces for the Automated Job Hunt data pipeline:

- a FastAPI HTTP API for table CRUD and orchestration
- a Typer CLI for operator workflows
- an MCP server for multi-site job scraping
- a Python library split into `common`, `repository`, `service`, `pipeline`, `job_enricher`, `scraping`, and `mcp_interface` layers

The pipeline manages these Supabase tables:

- `jobs_final`
- `shared_links`

It also includes:

- an enricher that reads `jobs_final` rows where `job_status=SCRAPED` and patches enrichment data plus `job_status=ENRICHED` directly on `jobs_final`
- a submit endpoint that upserts incoming jobs by `job_url`, updates `shared_links`, and queues in-process enrichment for those submitted jobs
- a 2-stage pipeline runner: `ingest → enrich`
- a merged scraping domain and vendored `jobspy_mcp_server` compatibility package for job-board search and MCP tooling

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

If you need the new `jobs_final.job_type` and `jobs_final.work_mode` columns, apply [db/migrations/2026-04-18_add_job_type_work_mode_to_jobs_final.sql](db/migrations/2026-04-18_add_job_type_work_mode_to_jobs_final.sql) manually in Supabase before using the updated pipeline payloads.
That migration backfills `work_mode` from existing legacy values and then removes the old column.

1. Provide environment variables:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=sb_secret_your_generated_key_here
SUPABASE_TIMEOUT_SECONDS=30
COPILOT_MODEL=gpt-5.4-mini
COPILOT_TIMEOUT_SECONDS=45
COPILOT_MAX_RETRIES=3
COPILOT_RETRY_BACKOFF_SECONDS=1.0
COPILOT_BATCH_SIZE=20
```

## Run With uv

CLI examples:

```bash
uv run python main.py db tables
uv run python main.py db upsert --table jobs_final --payload-file payloads/jobs_final_upsert.json
uv run python main.py enricher enrich --limit 20 --dry-run
uv run python main.py pipeline run payloads/jobs_raw.json --limit 20
uv run python main.py scraping search "software engineer" --sites linkedin,indeed --results 5
```

Start the server:

```bash
uv run uvicorn server:app --host 0.0.0.0 --port 8000
```

Start the MCP server:

```bash
uv run python mcp_server.py
```

Installed-script compatibility for the merged MCP package:

```bash
uv run jobspy-mcp-server
uv run jobspy-search "software engineer" --sites linkedin,indeed --results 5
```

## Scraping Compatibility Contract

The merged repository preserves job scraping core functionality without changing external usage patterns:

- CLI access remains available through `jobspy-search`.
- MCP server access remains available through `jobspy-mcp-server` and `python mcp_server.py`.
- Existing users can continue scraping through either interface without changing payload semantics.

Compatibility smoke-check commands:

```bash
uv run jobspy-search --help
uv run jobspy-mcp-server --help
python mcp_server.py --help
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

`POST /enricher/by-ids?dry_run=false`

Request body:

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

Notes:

- re-enriches rows regardless of `job_status`
- excludes soft-deleted rows and reports missing ids in `errors`
- when `dry_run=true`, computes the summary without patching `jobs_final`

Success response:

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

Quick dry-run cURL:

```bash
curl -X POST "http://localhost:8000/enricher/by-ids?dry_run=true" \
  -H "Content-Type: application/json" \
  -d '[{"id":"e27be3e8-f4b2-4dba-a353-0a3c0b7125d4"},{"id":"98fa3757-c584-4849-8e7f-16a3d0881d28"}]'
```

`POST /pipeline/run`

`POST /pipeline/submit`

Accepts `jobs`, upserts valid jobs into `jobs_final` with `job_status=SCRAPED`, upserts `shared_links` by `job_url`, and returns `202` after queueing background enrichment for the accepted ids.

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
    }
  ]
}
```

Success response:

```json
{
  "submitted_row_count": 1,
  "accepted": {
    "count": 1,
    "ids": ["550e8400-e29b-41d4-a716-446655440000"]
  },
  "queued": {
    "count": 1,
    "ids": ["550e8400-e29b-41d4-a716-446655440000"]
  },
  "rejected_row_indexes": [],
  "errors": [],
  "jobs_final_row_count": 1,
  "shared_links_row_count": 1
}
```

Notes:

- background enrichment is in-process and non-durable
- only ids accepted in the same request are queued
- successful background enrichment updates those rows to `job_status=ENRICHED`
- `job_type` stored values are `fulltime`, `parttime`, `internship`, `contract`, `temporary`, or `other`
- `work_mode` stored values are `remote`, `hybrid`, `on-site`, or `other`

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

`POST /pipeline/stage/enriched`

Runs the enrich stage only. Processes SCRAPED jobs and extracts enrichment data from job descriptions.

**Fields updated in `jobs_final`:**

- `job_status` → "ENRICHED"
- `tech_stack` → Normalized list of technologies extracted from job description
- `experience_level` → Normalized experience level (Internship, Entry, Mid, Senior, Lead, or Unknown)
- `work_mode` → Normalized work mode (remote, hybrid, on-site, or other)

```bash
curl -X POST http://localhost:8000/pipeline/stage/enriched \
  -H "Content-Type: application/json" \
  -d '{"limit":20,"dry_run":false}'
```

### Add data to every table

`jobs-final`

```bash
curl -X POST http://localhost:8000/db/jobs-final \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"id":"550e8400-e29b-41d4-a716-446655440000","company_name":"Acme Corp","role_title":"Senior Android Engineer","job_status":"SAVED","job_url":"https://example.com/jobs/123"}]}'
```

`shared-links`

```bash
curl -X POST http://localhost:8000/db/shared-links \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"url":"https://www.linkedin.com/jobs/view/123","source":"android-share-intent"}]}'
```

## CLI

The CLI uses the `db`, `enricher`, `pipeline`, and `scraping` groups.

Examples:

```bash
uv run python main.py db soft-delete --table jobs_final --record-id 550e8400-e29b-41d4-a716-446655440000
uv run python main.py db patch --table jobs_final --filter-column id --filter-value 550e8400-e29b-41d4-a716-446655440000 --payload '{"job_status":"APPLIED"}'
uv run python main.py enricher enrich --limit 50
uv run python main.py pipeline stage-enriched --limit 20 --dry-run
uv run python main.py scraping search "android engineer" --cities Berlin,Munich --sites linkedin,stepstone
```

Run API tests only:

```bash
uv run python -m pytest tests/test_api_server.py -v
```

## Project Structure

The `src/` tree is organized into focused, single-responsibility packages. Each large workflow is split into sibling modules so concerns can be tested in isolation.

```text
src/
  api/                       FastAPI app + route handlers (routes/ grouped by domain)
  common/                    PostgrestClient, SupabaseConfig, Pydantic row validators
  repository/                SupabaseRepository (table-aware CRUD with validation dispatch)
  service/
    tables.py                Per-table service helpers
    submit.py                /pipeline/submit row validation + selection
    queries.py               Reusable query helpers
    enricher.py              enrich_jobs() + enrich_jobs_by_ids() orchestration
    enricher_persistence.py  patch_enriched_rows() batched DB writes
    pipeline.py              run_pipeline() slim orchestrator (ingest → enrich)
    stages/
      ingest.py              run_stage_ingest() — validates and upserts SCRAPED rows
      enrich.py              run_stage_enriched() / run_stage_enriched_detailed()
    mappers/                 Scrape → jobs_final field mappers
  pipeline/                  Pipeline-specific Pydantic/dataclass models + Typer CLI
  job_enricher/              CopilotClient wrapper, prompts, extractors, Typer CLI
  scraping/
    requests.py              JobSearchRequest (Pydantic v2)
    validators.py            Pure request-shape validators (sites, work mode, clamps)
    defaults.py              EffectiveSearchParams + resolve_effective_request()
    renderers.py             Markdown rendering for search results / errors
    service.py               search_jobs() slim orchestrator
    ports.py                 ScraperPort Protocol (adapter contract)
    output.py / models.py /  Public re-export shims that delegate to adapters/
      preferences.py
    adapters/                Only place allowed to import jobspy_mcp_server.*
      jobspy_adapter.py      JobspyAdapter (concrete ScraperPort impl)
      jobspy_models.py       Vendored model re-exports
      jobspy_output.py       Vendored output formatter re-exports
      jobspy_preferences.py  Vendored preferences re-exports
    cli.py                   Typer CLI (scraping search ...)
  mcp_interface/             FastMCP server entry + serialization helpers
  mcp_server/                MCP server entry-point glue
  jobspy_mcp_server/         Vendored upstream package — DO NOT modify
```

### Adapter boundary (CON-001)

The vendored `src/jobspy_mcp_server/` package must not be touched and must only be imported from `src/scraping/adapters/`. This is enforced by `tests/test_adapter_boundary.py`, which scans every `src/**/*.py` outside the allowed prefixes for `from jobspy_mcp_server` / `import jobspy_mcp_server`.

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
    rows=[{"id": "550e8400-e29b-41d4-a716-446655440000"}],
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
result = upsert_jobs_final(repo, [{"id": "550e8400-e29b-41d4-a716-446655440000"}])
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
