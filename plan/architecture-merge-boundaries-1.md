---
goal: Post-Merge Architecture Refactor Plan for Unified Orchestrator
version: 1.0
date_created: 2026-04-19
last_updated: 2026-04-19
owner: Platform Engineering
status: Completed
tags: [architecture, refactor, migration, integration, mcp, scraping]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan defines a deterministic, phase-based architecture refactor after merging the sister MCP scraping project into Orchestrator. The goal is to remove compatibility-layer coupling, establish explicit domain boundaries, unify testing and CI, and preserve all existing integration surfaces (FastAPI, Typer CLI, MCP server, and Python library).

## 1. Requirements & Constraints

- **REQ-001**: Preserve all four integration surfaces without breaking current commands in main.py and mcp_server.py.
- **REQ-002**: Keep runtime behavior compatible for jobspy-search and jobspy-mcp-server script entrypoints defined in pyproject.toml.
- **REQ-003**: Preserve job scraping core functionality exactly: any user must be able to execute job scraping through CLI and MCP server after refactors.
- **REQ-004**: Replace direct service-layer imports of vendored scraper internals with a single orchestrator-owned scraping interface.
- **REQ-005**: Provide deterministic mapping from scrape output payload to JobsFinalRow persistence payload.
- **SEC-001**: Introduce explicit API authentication dependency wiring for pipeline and enricher routes before internet exposure.
- **SEC-002**: Keep secret access environment-variable based only; no hardcoded credentials in code or plan tasks.
- **ARC-001**: Maintain layered architecture direction: routes -> service -> repository -> client.
- **CON-001**: Do not remove vendored package in first refactor pass; migrate by adapter pattern first.
- **CON-002**: Avoid changes to user-owned in-flight work unless required by this plan.
- **GUD-001**: Use deterministic task outputs with explicit file paths and function symbols.
- **PAT-001**: Use ports-and-adapters pattern for scraper and MCP integration boundaries.
- **OPS-001**: Add CI workflows in Orchestrator before decommissioning split repo validation.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Create explicit scraping domain boundary and remove direct service dependency on vendored internals.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create src/scraping/ports.py with ScraperPort protocol and deterministic search contract objects (request/result dataclasses or pydantic models). | ✅ | 2026-04-19 |
| TASK-002 | Create src/scraping/adapters/jobspy_adapter.py implementing ScraperPort and wrapping jobspy_mcp_server.jobspy_scrapers.scrape_jobs. | ✅ | 2026-04-19 |
| TASK-003 | Refactor src/scraping/service.py to depend on ScraperPort and adapter injection instead of direct scrape_jobs import. | ✅ | 2026-04-19 |
| TASK-004 | Refactor src/scraping/models.py to orchestrator-native models only (remove re-export strategy). | ✅ | 2026-04-19 |
| TASK-005 | Refactor src/scraping/guardrails.py to keep only orchestrator-owned constants or adapter-local compatibility mapping. | ✅ | 2026-04-19 |

### Implementation Phase 2

- **GOAL-002**: Isolate persistence mapping and make scrape-to-database flow deterministic.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | Create src/service/mappers/scrape_to_jobs_final.py with pure mapping function(s) from scrape normalized job payload to JobsFinalRow-compatible dict. | ✅ | 2026-04-19 |
| TASK-007 | Refactor src/service/pipeline.py ingest path to call mapper module for all scrape-originated rows prior to JobsFinalRow validation. | ✅ | 2026-04-19 |
| TASK-008 | Add strict schema validation gate in src/service/pipeline.py for required fields after mapping and before repository upsert. | ✅ | 2026-04-19 |
| TASK-009 | Update docs/SUPABASE_SCHEMA.md to include scrape-origin field mapping table and status transition rules. | ✅ | 2026-04-19 |

### Implementation Phase 3

- **GOAL-003**: Convert MCP wrapper into orchestrator integration module with explicit boundary to scraping service.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Create src/mcp_interface/server.py and move MCP tool wiring from src/mcp_server/server.py re-export style to explicit service invocation style. | ✅ | 2026-04-19 |
| TASK-011 | Create src/mcp_interface/serialization.py for shared MCP response envelope formatting and output-format handling. | ✅ | 2026-04-19 |
| TASK-012 | Keep src/mcp_server/server.py as compatibility shim that imports from src/mcp_interface/server.py only. | ✅ | 2026-04-19 |
| TASK-013 | Reduce parameter and cognitive complexity in MCP tool entrypoint by splitting validation, execution, and formatting helpers. | ✅ | 2026-04-19 |

### Implementation Phase 4

- **GOAL-004**: Establish unified security and CI quality gates in Orchestrator.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-014 | Add API auth dependency module in src/api/security.py and apply dependency checks in src/api/app.py router registration or route-level dependencies. | ✅ | 2026-04-19 |
| TASK-015 | Add deep health probe route in src/api/routes/system.py validating Supabase and Copilot connectivity status. | ✅ | 2026-04-19 |
| TASK-016 | Create .github/workflows/ci.yml in Orchestrator to run formatting, type checks, and pytest suite. | ✅ | 2026-04-19 |
| TASK-017 | Migrate MCP tests into Orchestrator tests/ from sister repo test/ and normalize import paths for pythonpath=src. | ✅ | 2026-04-19 |
| TASK-018 | Add pytest markers and selective integration profile in pyproject.toml and document execution matrix in README.md. | ✅ | 2026-04-19 |

## 3. Alternatives

- **ALT-001**: Keep current wrapper-and-reexport structure indefinitely. Rejected because it preserves high coupling to vendored internals and duplicates evolution paths.
- **ALT-002**: Remove vendored package immediately and rewrite all scrapers in orchestrator namespace. Rejected because migration risk is high and may break existing CLI/MCP compatibility.
- **ALT-003**: Maintain two separate repositories with periodic copy sync. Rejected because it creates drift, duplicate CI, and higher operational overhead.

## 4. Dependencies

- **DEP-001**: Existing Orchestrator runtime dependencies in pyproject.toml must continue to satisfy scraping and MCP requirements.
- **DEP-002**: jobs-search-mcp-server test fixtures and MCP tests are required inputs for migration of test coverage.
- **DEP-003**: Supabase availability and existing table schemas documented in docs/SUPABASE_SCHEMA.md.
- **DEP-004**: Copilot SDK credentials and runtime configuration used by job enricher service.

## 5. Files

- **FILE-001**: src/scraping/service.py
- **FILE-002**: src/scraping/models.py
- **FILE-003**: src/scraping/guardrails.py
- **FILE-004**: src/scraping/ports.py
- **FILE-005**: src/scraping/adapters/jobspy_adapter.py
- **FILE-006**: src/service/pipeline.py
- **FILE-007**: src/service/mappers/scrape_to_jobs_final.py
- **FILE-008**: src/mcp_server/server.py
- **FILE-009**: src/mcp_interface/server.py
- **FILE-010**: src/mcp_interface/serialization.py
- **FILE-011**: src/api/app.py
- **FILE-012**: src/api/routes/system.py
- **FILE-013**: src/api/security.py
- **FILE-014**: pyproject.toml
- **FILE-015**: README.md
- **FILE-016**: docs/SUPABASE_SCHEMA.md
- **FILE-017**: .github/workflows/ci.yml
- **FILE-018**: tests/test_scraping_service.py
- **FILE-019**: tests/test_scraping_cli.py
- **FILE-020**: tests/test_scraping_mcp_interface.py
- **FILE-021**: tests/test_scrape_to_jobs_final_mapper.py

## 6. Testing

- **TEST-001**: Add unit tests for ScraperPort adapter behavior with monkeypatched scrape_jobs return values.
- **TEST-002**: Add unit tests for scrape_to_jobs_final mapper with valid, missing, and malformed payload scenarios.
- **TEST-003**: Add regression tests for existing scraping CLI behavior in tests/test_scraping_cli.py.
- **TEST-004**: Add MCP tool contract tests in tests/test_scraping_mcp_interface.py for success/error envelopes and guardrail clamping.
- **TEST-005**: Add compatibility smoke tests that assert both commands continue to work: `uv run jobspy-search --help` and `uv run jobspy-mcp-server --help`.
- **TEST-006**: Add integration test for pipeline ingest path using mapped scrape payload and repository mocks.
- **TEST-007**: Add auth dependency tests ensuring protected endpoints reject unauthorized requests.
- **TEST-008**: Execute uv run python -m pytest -v and store pass/fail summary in CI output.

## 7. Risks & Assumptions

- **RISK-001**: Compatibility shims may drift if adapter and vendored API are changed independently.
- **RISK-002**: Mapper assumptions about optional scrape fields may fail for edge-case sites with sparse payloads.
- **RISK-003**: CI migration may initially fail due to fixture path and import differences between sister repos.
- **RISK-004**: Introducing auth checks may break existing internal automation clients if rollout is not coordinated.
- **ASSUMPTION-001**: Existing database schemas for jobs_final and shared_links remain stable during Phase 1-2.
- **ASSUMPTION-002**: Existing CLI and MCP command names must remain stable for backward compatibility.
- **ASSUMPTION-003**: The merged repository remains the single source of truth after this plan starts execution.

## 8. Related Specifications / Further Reading

- docs/ARCHITECTURE.md
- docs/INTEGRATION.md
- docs/SUPABASE_SCHEMA.md
- AGENTS.md
- ../jobs-search-mcp-server/docs/API_Integration.md
