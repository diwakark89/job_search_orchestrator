# Merged Architecture

This repository now acts as the single codebase for the Automated Job Hunt system.

## Integration Surfaces

- FastAPI HTTP API via `server.py` and `src/api/`
- Typer operator CLI via `main.py`
- MCP stdio or HTTP server via `mcp_server.py` and `src/mcp_server/`
- Python library modules under `src/`

## Structure

```text
Orchestrator/
├── server.py                    # FastAPI bootstrap
├── main.py                      # Typer CLI bootstrap
├── mcp_server.py                # MCP bootstrap
├── assets/                      # Shared MCP assets and sample preferences
├── src/
│   ├── api/                     # HTTP API layer
│   ├── common/                  # Shared DB config, client, validators
│   ├── repository/              # Supabase repository boundary
│   ├── service/                 # Orchestration and business workflows
│   ├── job_enricher/            # Copilot-powered enrichment
│   ├── pipeline/                # Pipeline CLI models and commands
│   ├── scraping/                # New Orchestrator-facing scraping domain wrappers
│   ├── mcp_server/              # New Orchestrator-facing MCP wrappers
│   └── jobspy_mcp_server/       # Vendored compatibility package from the former sister repo
└── tests/                       # Unified test suite
```

## Merge Strategy

The first implementation step keeps `src/jobspy_mcp_server/` vendored to preserve MCP behavior and standalone CLI compatibility without rewriting all internal imports immediately.

The new `src/scraping/` and `src/mcp_server/` packages are the stable import surface for future Orchestrator-native development.

## Next Refactor Boundary

Future refactors should migrate internals from `src/jobspy_mcp_server/` into `src/scraping/` gradually, then reduce the vendored package to compatibility wrappers only.
