# AGENTS.md

## Project Overview

Automated Job Hunt Orchestrator is a Python 3.11+ codebase that manages job ingestion, enrichment, and scraping integrations.

It exposes four integration surfaces:

- FastAPI HTTP API at `server.py` and `src/api/`
- Typer CLI at `main.py` and `src/*/cli.py`
- MCP server entrypoint at `mcp_server.py` and `src/mcp_server/`
- Python library modules under `src/`

Primary external dependencies:

- Supabase (PostgREST over HTTP) for persistence
- GitHub Copilot SDK for LLM enrichment
- FastAPI, Typer, Pydantic v2, Requests, Uvicorn

## Architecture Overview

Layering rule (do not violate):

```
API routes -> service -> repository -> PostgrestClient (requests)
```

Major packages:

- `src/api/`: FastAPI app, route handlers, response models
- `src/common/`: shared config, constants, validators, Supabase HTTP client, CLI group
- `src/repository/`: table-aware CRUD adapter (`SupabaseRepository`)
- `src/service/`: orchestration logic (tables, enricher, pipeline, submit)
- `src/job_enricher/`: Copilot client, extraction logic, enricher CLI
- `src/pipeline/`: pipeline models and CLI wrapper
- `src/scraping/`: orchestrator-facing scraping domain
- `src/mcp_server/`: orchestrator MCP wrappers
- `src/jobspy_mcp_server/`: vendored compatibility package for jobspy MCP and CLI

Entrypoints `server.py` and `main.py` prepend `src/` to `sys.path`, so imports are package-short (for example, `from api.app import app`).

## Setup Commands

Install dependencies (preferred):

```bash
uv sync
```

Install development tools (pytest, ruff, pyright, etc.):

```bash
uv sync --extra dev
```

Fallback install path:

```bash
pip install -r requirements.txt
```

Required environment variables (via `.env` or shell):

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

Optional schema migration called out in README:

- Apply `db/migrations/2026-04-18_add_job_type_work_mode_to_jobs_final.sql` before using payloads that depend on `jobs_final.job_type` and `jobs_final.work_mode`.

## Development Workflow

Start API server:

```bash
uv run uvicorn server:app --host 0.0.0.0 --port 8000
```

Start API server with verbose logs:

```bash
uv run uvicorn server:app --host 0.0.0.0 --port 8000 --log-level debug
```

Start MCP server:

```bash
uv run python mcp_server.py
```

Alternative compatibility entrypoints:

```bash
uv run jobspy-mcp-server
uv run jobspy-search "software engineer" --sites linkedin,indeed --results 5
```

CLI examples:

```bash
uv run python main.py job-manage table tables
uv run python main.py job-manage table upsert --table jobs_final --payload-file payloads/jobs_final_upsert.json
uv run python main.py job-manage enricher enrich --limit 20 --dry-run
uv run python main.py job-manage pipeline run payloads/jobs_raw.json --limit 20
```

Quick health checks:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/tables
```

API docs while server is running:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Testing Instructions

Run complete test suite:

```bash
uv run python -m pytest -v
```

Run unit-focused tests (matches CI behavior):

```bash
uv run python -m pytest -v --tb=short -m "not integration"
```

Run API tests only:

```bash
uv run python -m pytest tests/test_api_server.py -v
```

Run one test case:

```bash
uv run python -m pytest tests/test_validators.py::TestJobsFinalValidator::test_minimal_valid_row -v
```

Marker usage:

- `unit`: fast tests
- `integration`: network/live-site tests
- `slow`: long-running tests
- `smoke`: entrypoint checks

Test conventions:

- Place tests under `tests/` with `test_*.py` naming.
- Use `pytest` + `monkeypatch`; avoid decorator-based `unittest.mock.patch` patterns.
- Prefer `MagicMock` for repository/client isolation and assert called behavior.
- Use `fastapi.testclient.TestClient` for route tests.
- Add or update tests for every behavioral change in `service`, `repository`, `job_enricher`, `scraping`, and API route code.

## Code Style Guidelines

Python conventions:

- `from __future__ import annotations` at module top.
- Full type hints on public and internal functions.
- Use PEP 604 unions (`str | None`) instead of `Optional[str]`.
- Keep `__init__.py` files minimal; import concrete symbols from submodules when needed.

Validation and models:

- Use Pydantic v2 with `ConfigDict(extra="forbid")` for payload safety.
- Normalize timestamps with existing helpers (for example `normalize_timestamp_fields`).
- Serialize outbound records with `model_dump(exclude_none=True)` where appropriate.

Error semantics:

- `ValueError` maps to HTTP 400 in routes.
- `RuntimeError` maps to HTTP 502 for upstream/dependency failures.
- API routes should catch and convert service exceptions to `HTTPException` responses.

Architecture constraints:

- Keep dependency flow downward only: routes -> service -> repository -> client.
- Avoid introducing circular imports across `src/` packages.

## Build and Deployment

Packaging/build system:

- Build backend is `hatchling` (`pyproject.toml`).
- Wheel packages are declared under `[tool.hatch.build.targets.wheel]`.

Create distributable artifacts:

```bash
uv build
```

or

```bash
python -m build
```

Deployment/runtime notes:

- This project is typically run as a long-lived API service (`uvicorn`) plus optional MCP server process.
- Production deployment must inject environment variables securely (never from committed files).
- Validate `/health` after deployment and confirm Supabase + Copilot configuration flags are true.

CI pipeline (`.github/workflows/ci.yml`):

- Runs on pushes/PRs to `main`
- Python matrix: 3.11 and 3.12
- Installs via `uv sync --extra dev`
- Advisory checks: `ruff format --check`, `ruff check`, `pyright`
- Required test run: `pytest -m "not integration"`
- Smoke checks: `jobspy-search --help`, `jobspy-mcp-server --help`

## Supported Tables and API Slugs

- `jobs-final` -> `jobs_final` (conflict key: `id`, soft delete supported)

Important API behavior:

- Table routes use `/db/{table}` with hyphenated table slugs.
- Filtering is query-param based (example: `/db/jobs-final?job_status=APPLIED`).
- Enricher default source is `jobs_final` rows with `job_status=SCRAPED` and `is_deleted=false`.
- Pipeline stage order is `ingest -> enrich`.
- `POST /pipeline/submit` upserts jobs by `job_url` and queues in-process enrichment.

## Security Considerations

- Never commit secrets (`SUPABASE_URL`, `SUPABASE_KEY`, Copilot tokens, or `.env` contents).
- Prefer scoped Supabase keys with minimum table permissions required.
- Do not construct raw SQL from user input; use the PostgREST client/repository abstractions.
- Re-validate LLM-enriched output through extractors and Pydantic validators before persistence.
- Preserve `extra="forbid"` on request/row models unless there is a clear schema change.

## Pull Request Guidelines

Title format:

- `[component] Brief imperative description`

Common component tags:

- `api`, `cli`, `common`, `enricher`, `pipeline`, `scraping`, `mcp`, `repository`, `service`, `tests`, `docs`, `deps`

Before opening/merging a PR:

1. Run `uv run python -m pytest -v` (or at minimum CI-equivalent non-integration tests).
2. For enricher/pipeline changes, run a `--dry-run` flow first.
3. Smoke-check service health with `curl http://localhost:8000/health`.
4. Add tests for any new public function or behavior change.
5. Verify layer-discipline imports still follow routes -> service -> repository -> client.

## Troubleshooting

Server startup fails:

- Confirm required env vars are present and valid.
- Missing config values raise `ValueError` during startup.

Frequent 502 responses:

- Check Supabase URL/key reachability and permissions.
- Verify Copilot model value and active SDK authentication.

Import errors in tests:

- Ensure tests are run via `uv run` so project environment and `pythonpath = ["src"]` are applied.

Enricher processes zero rows:

- Verify source records match `job_status=SCRAPED` and `is_deleted=false`.
- Example query:

```bash
curl "http://localhost:8000/db/jobs-final?job_status=SCRAPED"
```

Validation failures (`extra fields not permitted`):

- Check active schema in `src/common/validators.py` and enum/value constants in `src/common/constants.py`.

## Agent Notes

- Prefer `uv` commands for reproducible runs.
- Keep edits minimal and scoped; avoid broad refactors unless requested.
- Update tests together with code changes.
- If adding new integration surfaces or packages, update this file in the same PR.
