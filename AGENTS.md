# AGENTS.md

## Project Overview

Python orchestrator for an automated job-hunt data pipeline. Exposes three integration surfaces:

- **FastAPI HTTP API** — table CRUD and orchestration at `server.py` → `src/api/`
- **Typer CLI** — operator workflows at `main.py` → `src/common/cli.py`, `src/job_enricher/cli.py`, `src/pipeline/cli.py`
- **Python library** — layered into `common`, `repository`, `service`, `job_enricher`, and `pipeline` packages under `src/`

All source code lives under `src/`. The `server.py` and `main.py` entry points add `src/` to `sys.path` so modules are imported without a top-level package prefix (e.g., `from api.app import app`).

### Architecture Layers

```
API routes  →  service layer  →  repository  →  PostgrestClient (HTTP to Supabase)
  (FastAPI)     (dataclass       (SupabaseRepository)   (requests)
                 results)
```

### Key Technologies

- Python 3.11+, FastAPI, Uvicorn, Pydantic v2, Typer, Rich, Requests
- Supabase (PostgREST) as the data store
- GitHub Copilot SDK for LLM-powered job enrichment

## Setup Commands

```bash
# Install dependencies (preferred)
uv sync

# Or with pip
pip install -r requirements.txt

# Install dev dependencies
uv sync --extra dev
```

### Required Environment Variables

Create a `.env` file or export these variables:

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

## Development Workflow

### Start the API Server

```bash
uv run uvicorn server:app --host 0.0.0.0 --port 8000
```

Or use the VS Code task `Start Server (uv)` which runs on folder open.

### Verify the Server

```bash
curl http://localhost:8000/health
```

Expected response: `{"status": "ok", "supabase_configured": true, "copilot_configured": true}`

### API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### CLI Usage

```bash
uv run python main.py db tables
uv run python main.py db upsert --table jobs_final --payload-file payloads/jobs_final_upsert.json
uv run python main.py enricher enrich --limit 20 --dry-run
uv run python main.py pipeline run payloads/jobs_raw.json --limit 20
```

## Testing Instructions

- Run all tests: `uv run python -m pytest -v`
- Run API tests only: `uv run python -m pytest tests/test_api_server.py -v`
- Run a single test: `uv run python -m pytest tests/test_validators.py::TestJobsFinalValidator::test_minimal_valid_row -v`

VS Code tasks `Run Tests (uv)` and `Run API Tests Only (uv)` are also available.

### Test Conventions

- Tests live in `tests/` and use `pytest` with `monkeypatch` for mocking (no `unittest.mock.patch` decorators).
- Use `MagicMock` for repository and client dependencies; assert on method calls.
- Test names follow `test_<feature>_<scenario>` (e.g., `test_db_list_rows_success`).
- FastAPI endpoints are tested via `fastapi.testclient.TestClient`.
- Validator tests use `pytest.raises(Exception)` for invalid inputs.
- `pythonpath = ["src"]` is configured in `pyproject.toml` so tests import from `src/` directly.
- Dev dependencies (`pytest`, `httpx`) are declared in `[project.optional-dependencies] dev`.

## Code Style

### General Conventions

- `from __future__ import annotations` at the top of every module.
- Modern union syntax: `str | None` (PEP 604), not `Optional[str]`.
- Type hints on all function signatures and return types.
- No explicit linter or formatter is configured; follow existing style.

### Configuration

- Frozen dataclasses (`@dataclass(frozen=True)`) for config objects.
- Lazy `load_config()` / `load_copilot_config()` factory functions that read from environment variables.
- Validation happens inside the factory; raise `ValueError` for missing or invalid config.

### Pydantic Models

- `ConfigDict(extra="forbid")` on all row models — unknown fields are rejected.
- `@field_validator` decorators for enum-style fields.
- `model_dump(exclude_none=True)` when serializing for the database.
- Timestamps are normalized to ISO 8601 UTC via `normalize_timestamp_fields()`.

### Error Handling

- `ValueError` → HTTP 400 (bad input from the caller).
- `RuntimeError` → HTTP 502 (upstream Supabase or Copilot failure).
- All API routes wrap service calls in `try/except` and convert to `HTTPException`.

### Result Types

- Repository and client operations return `OperationResult` (success, status_code, table, operation, row_count, data, error).
- Service functions return typed dataclasses (`EnrichmentSummary`, `StageResult`, `PipelineResult`).
- API responses use explicit Pydantic models from `src/api/models.py`.

### Package & Import Conventions

- Minimal `__init__.py` files — prefer direct imports from submodules.
- No circular imports; layers import downward only (routes → service → repository → client).

## Project Structure

```
server.py          → FastAPI entry point (imports src/api/app.py)
main.py            → Typer CLI entry point
src/
  api/
    app.py         → FastAPI app creation and router registration
    models.py      → Pydantic response models for all endpoints
    routes/        → Route handlers grouped by domain
  common/
    cli.py         → Typer subcommand for DB operations
    client.py      → PostgrestClient (HTTP client for Supabase REST)
    config.py      → SupabaseConfig dataclass and load_config()
    constants.py   → Table names, conflict keys, valid enum values
    validators.py  → Pydantic row models and validation functions
  job_enricher/
    cli.py         → Typer subcommand for enrichment
    client_copilot.py → CopilotClient wrapper for LLM calls
    config.py      → CopilotConfig dataclass and load_copilot_config()
    constants.py   → LLM prompts, canonical tech stack, enum sets
    extractors.py  → Field extraction from LLM responses
  pipeline/
    cli.py         → Typer subcommand for pipeline execution
    models.py      → Pipeline-specific data models
  repository/
    supabase.py    → SupabaseRepository (table-aware CRUD with validation dispatch)
  service/
    enricher.py    → enrich_jobs() orchestration logic
    pipeline.py    → run_pipeline() and per-stage functions
    queries.py     → Reusable query helpers
    tables.py      → Table-level service operations
tests/             → pytest test suite
docs/              → Integration guide and API skill reference
```

## Supported Tables

| Slug (HTTP) | Table Name (DB) | Conflict Key | Notes |
|-------------|-----------------|--------------|-------|
| `automation-sessions` | `automation_sessions` | `id` | Tracks OpenClaw automation state per job |
| `jobs-final` | `jobs_final` | `id` | Supports soft delete |
| `shared-links` | `shared_links` | `url` | |

## Security Considerations

- **Never commit secrets**: `SUPABASE_URL` and `SUPABASE_KEY` must be stored in `.env` (git-ignored) or injected via environment — never hardcoded.
- **Key scope**: Use a scoped Supabase service-role key with the minimum permissions required (read + write to `automation_sessions`, `jobs_final`, and `shared_links` only).
- **Input validation**: All inbound data is validated through Pydantic models with `extra="forbid"` before reaching the repository layer.
- **No SQL construction**: The repository layer uses Supabase PostgREST — no raw SQL strings are built from user input, preventing SQL injection.
- **LLM output sanitisation**: Copilot SDK responses are parsed by `extractors.py` and re-validated against Pydantic models before being written to the database.

## Pull Request Guidelines

- **Title format**: `[component] Brief imperative description` — e.g., `[enricher] Add retry backoff for Copilot timeouts`
- **Component tags**: `api`, `cli`, `common`, `enricher`, `pipeline`, `repository`, `service`, `tests`, `docs`, `deps`
- **Required checks before merge**:
  1. `uv run python -m pytest -v` — full test suite must pass
  2. Manual smoke-test: `curl http://localhost:8000/health` against a running server
- **Dry-run first**: For enricher or pipeline changes, verify with `--dry-run` before merging.
- **No new public functions without tests**: Every new service, repository, or extractor function requires a corresponding test in `tests/`.
- **Layer discipline**: PRs must not introduce imports that violate the downward-only dependency rule (routes → service → repository → client).

## Debugging and Troubleshooting

### Server won't start

- Check that all required env vars are set: `SUPABASE_URL`, `SUPABASE_KEY`.
- Missing vars raise `ValueError` at startup — read the traceback carefully; it names the missing variable.

### `502` responses from API

- Indicates a Supabase or Copilot upstream failure. Check `SUPABASE_URL` reachability and `SUPABASE_KEY` validity.
- For enrichment 502s, verify `COPILOT_MODEL` is a valid model name and the Copilot SDK token is active.

### Tests fail with import errors

- Ensure `pythonpath = ["src"]` is present in `pyproject.toml` under `[tool.pytest.ini_options]`.
- Run tests via `uv run python -m pytest` (not `pytest` directly) to pick up the `uv` virtual environment.

### Enricher processes 0 rows

- The enricher only processes rows where `job_status=SCRAPED` and `is_deleted=false`. Verify data state with:
  ```bash
  curl "http://localhost:8000/db/jobs-final?job_status=SCRAPED"
  ```

### Pydantic `extra="forbid"` validation errors

- Unknown fields in a payload are rejected at the validator level. Check `src/common/validators.py` and `src/common/constants.py` for the current allowed field set.

### Logging

- FastAPI/Uvicorn logs to stdout by default. Add `--log-level debug` to the uvicorn command for verbose request logs:
  ```bash
  uv run uvicorn server:app --host 0.0.0.0 --port 8000 --log-level debug
  ```

## Additional Notes

- The HTTP API uses hyphenated slugs (`jobs-final`) while the database uses underscored names (`jobs_final`). Route handlers translate between the two.
- List filtering uses plain query parameters: `GET /db/jobs-final?job_status=APPLIED&company_name=Acme`.
- The enricher reads `jobs_final` rows where `job_status=SCRAPED` and `is_deleted=false`, enriches them, and patches `job_status=ENRICHED` directly on `jobs_final`.
- The full pipeline runs two stages sequentially: `ingest → enrich`.
- Soft delete is supported only for `jobs-final`.
- Metrics are computed dynamically via `SELECT job_status, COUNT(*) FROM jobs_final GROUP BY job_status` — no separate metrics table.
- Service functions accept `dry_run=True` to preview operations without persisting.
- The integration contract is documented in `docs/INTEGRATION.md`.
