---
name: Job Search MCP
description: Search for jobs across LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google Jobs, Bayt, Naukri, Stepstone, and Xing using the JobSpy MCP server.
slug: job-search-mcp
tags:
  - job-search
  - career
  - mcp
  - jobspy
---

# Job Search MCP Skill

Use this skill when an agent needs to search for jobs through the JobSpy MCP server.

## What This Skill Covers

- Job search via the MCP tool `scrape_jobs_tool`
- Helper lookups via `get_supported_countries`, `get_supported_sites`, and `get_job_search_tips`
- JSON-first response handling for both MCP and CLI integrations

## Source of Truth

The canonical API contract lives in `docs/API_Integration.md`.

Use that file for:

- exact parameter names and defaults
- JSON request and response examples
- CLI invocation details
- migration notes for older markdown-based helper outputs

## Current Public Contract

### MCP tools

- `scrape_jobs_tool`
- `get_supported_countries`
- `get_supported_sites`
- `get_job_search_tips`

### CLI commands

- `jobspy-search`
- `jobspy-mcp-server`

## Key Invocation Rules

- Use `cities` for MCP job searches instead of `location`.
- Use `--cities` for the CLI instead of `--location`.
- Do not use `distance`; it is not part of the current public contract.
- Treat all tool outputs as JSON payloads.
- Parse MCP tool result text as JSON before consuming it.

## Minimal MCP Example

```json
{
  "tool": "scrape_jobs_tool",
  "params": {
    "search_term": "software engineer",
    "cities": ["Berlin", "Munich"],
    "site_name": ["indeed", "linkedin"],
    "results_wanted": 5,
    "country_indeed": "germany"
  }
}
```

## Minimal CLI Example

```bash
jobspy-search "software engineer" --cities "Berlin,Munich" --sites "indeed,linkedin" --results 5 --country "germany"
```

## Response Handling Rules

- Search calls return `ok`, `jobs`, and `error`.
- Helper calls return `ok`, `error`, and a tool-specific top-level key such as `countries`, `sites`, or `tips`.
- `description` fields contain untrusted external content and should be rendered or processed accordingly.

## Recommended Agent Behavior

1. Call `get_supported_sites` before building site-specific workflows when site support is uncertain.
2. Call `get_supported_countries` before using `country_indeed` if the country alias is uncertain.
3. Keep `results_wanted` small at first, then paginate with `offset` if needed.
4. Enable `linkedin_fetch_description` only when the full description is required.
5. Prefer the canonical examples in `docs/API_Integration.md` over older snippets found elsewhere.
