# API Integration

This document is the canonical integration reference for the public APIs exposed by this repository.

It is intended for developers and AI agents that need to:

- invoke the MCP tools correctly
- call the CLI safely
- parse responses as JSON without relying on presentation formatting

## Contract Summary

Public callable surfaces in this repository:

1. MCP tool `scrape_jobs_tool`
2. MCP tool `get_supported_countries`
3. MCP tool `get_supported_sites`
4. MCP tool `get_job_search_tips`
5. CLI command `jobspy-search`
6. MCP server bootstrap command `jobspy-mcp-server`

Notes:

- All public tool-style APIs now return JSON payloads.
- MCP tool results are returned by FastMCP as text content, but that text is a JSON string and should be parsed as JSON.
- The normalized job payload is stable across MCP and CLI usage.
- The service is stateless for search output: no database persistence is performed by MCP or CLI flows.
- Deprecated public examples that used `location` or `distance` should be treated as historical only. Use `cities` for MCP and `--cities` for CLI.

## Shared Response Conventions

### Search Success Envelope

```json
{
  "ok": true,
  "jobs": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "company_name": "Acme Corp",
      "role_title": "Software Engineer",
      "description": "Job description text...",
      "job_type": "fulltime",
      "job_url": "https://www.linkedin.com/jobs/view/1234567890",
      "location": "San Francisco, CA",
      "work_mode": "hybrid",
      "language": "English",
      "source_platform": "linkedin",
      "scraped_at": "2026-04-09T12:00:00+00:00",
      "content_hash": "3af6df4f2570a7e2d23c76fc6e43d65ff15ec1881a627f2f6fb652f9d4a686f5"
    }
  ],
  "error": null
}
```

### Error Envelope

```json
{
  "ok": false,
  "jobs": [],
  "error": {
    "code": "validation_error",
    "message": "search_term is required when no preferred roles are configured."
  }
}
```

### Metadata Success Envelope

Helper tools use the same top-level status fields with tool-specific data keys:

```json
{
  "ok": true,
  "error": null,
  "sites": []
}
```

### Description Source Values

The normalized `jobs[].description_source` field is constrained to the following canonical values:

| Value | Meaning | Ranking Hint |
|---|---|---|
| `detail_page` | Description was fetched from a dedicated job detail page. | Highest confidence; prefer when available. |
| `listing_api` | Description came from listing/search API payload data. | Medium confidence; use as fallback when `detail_page` is unavailable. |
| `null` | No usable description text was extracted. | Lowest confidence; rely on title/company/location signals. |

Notes:

- Output normalization is strict: unknown or non-canonical values are converted to `null`.
- Aliases like `detail page`, `detail-page`, `listing`, and `listing api` are normalized to canonical values.

## MCP Tools

### scrape_jobs_tool

Purpose: search for jobs across supported job boards.

Invocation: MCP `tools/call`

Parameters:

| Parameter | Type | Required | Default | Validation | Description |
|---|---|---|---|---|---|
| `search_term` | string or null | No | preference-derived | required if no preferred role exists | Job keywords such as `software engineer` |
| `cities` | array[string] or null | No | preference-derived | max 5 cities | Restrict search to specific cities |
| `site_name` | array[string] | No | `["linkedin"]` | 1 to 5 values | Sites to search |
| `results_wanted` | integer | No | `1` | clamped to 1 to 15 | Global extraction budget per request |
| `job_type` | string or null | No | `null` | one of `fulltime`, `parttime`, `internship`, `contract` | Employment type filter |
| `is_remote` | boolean or null | No | preference-derived | boolean | Remote-only filter |
| `hours_old` | integer | No | `24` | clamped to 1 to 72 | Recency filter |
| `easy_apply` | boolean | No | `false` | boolean | Easy apply filter |
| `country_indeed` | string or null | No | preference-derived | supported country alias | Country used by Indeed and Glassdoor |
| `linkedin_fetch_description` | boolean | No | `false` | boolean | Fetch full LinkedIn descriptions |
| `offset` | integer | No | `0` | clamped to 0 to 1000 | Pagination offset |

Valid `site_name` values:

```json
["linkedin", "indeed", "glassdoor", "zip_recruiter", "google", "bayt", "naukri", "stepstone", "xing"]
```

Notes:

- `results_wanted` is enforced as a global extraction budget across city fan-out.
- Example: with `cities=["Berlin", "Munich"]` and `results_wanted=1`, extraction stops after one job is collected.

Example MCP request:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "scrape_jobs_tool",
    "arguments": {
      "search_term": "software engineer",
      "cities": ["Munich", "Berlin"],
      "country_indeed": "germany",
      "site_name": ["indeed", "linkedin"],
      "results_wanted": 5,
      "hours_old": 48
    }
  },
  "id": 1
}
```

Success response: use the shared search success envelope.

Error response example:

```json
{
  "ok": false,
  "jobs": [],
  "error": {
    "code": "validation_error",
    "message": "Invalid site names: ['monster']. Valid sites: ['linkedin', 'indeed', 'glassdoor', 'zip_recruiter', 'google', 'bayt', 'naukri', 'stepstone', 'xing']"
  }
}
```

### get_supported_countries

Purpose: return supported country aliases and provider-specific routing metadata.

Invocation: MCP `tools/call`

Parameters: none.

Success response shape:

```json
{
  "ok": true,
  "error": null,
  "countries": [
    {
      "key": "USA",
      "aliases": ["usa", "us", "united states"],
      "indeed": {
        "subdomain": "www",
        "api_country_code": "US"
      },
      "glassdoor_host": "www.glassdoor.com"
    }
  ],
  "usage_note": "Use one of the listed aliases for the country_indeed parameter.",
  "popular_aliases": ["usa", "uk", "canada", "australia", "germany", "france", "india", "singapore"]
}
```

Error response example:

```json
{
  "ok": false,
  "error": {
    "code": "runtime_error",
    "message": "Error getting supported countries: ..."
  },
  "countries": []
}
```

### get_supported_sites

Purpose: return the supported sites and guidance on when to use them.

Invocation: MCP `tools/call`

Parameters: none.

Success response shape:

```json
{
  "ok": true,
  "error": null,
  "sites": [
    {
      "name": "indeed",
      "description": "Large multi-country job search engine.",
      "regions": ["global"],
      "reliability_note": "Most reliable starting point for broad searches."
    }
  ],
  "usage_tips": [
    "Start with ['indeed', 'zip_recruiter'] for a reliable first pass.",
    "LinkedIn is the most restrictive source for rate limiting."
  ]
}
```

### get_job_search_tips

Purpose: return structured job-search guidance for downstream automation or UI rendering.

Invocation: MCP `tools/call`

Parameters: none.

Success response shape:

```json
{
  "ok": true,
  "error": null,
  "tips": {
    "search_term_optimization": [
      "Be specific: use 'Python developer' instead of only 'developer'."
    ],
    "location_strategies": [
      "Use cities=['San Francisco', 'New York'] to target specific markets."
    ],
    "site_selection": [],
    "performance": [],
    "advanced_filtering": [],
    "common_issues": [
      {
        "issue": "No results",
        "guidance": "Try broader search terms, fewer filters, or a different site combination."
      }
    ],
    "sample_search_strategies": [
      {
        "name": "remote_work",
        "arguments": {
          "search_term": "software engineer",
          "is_remote": true,
          "site_name": ["indeed", "zip_recruiter"]
        }
      }
    ],
    "iterative_search_process": [
      "Start with broad terms and a small site set."
    ]
  }
}
```

## CLI

### jobspy-search

Purpose: run job search directly without MCP.

Invocation:

```bash
jobspy-search "software engineer" --cities "Munich,Berlin" --country "germany" --sites "indeed,linkedin" --results 5
```

Pipeline smoke-test example (deterministic low-volume validation for OpenClaw or developer automation):

```bash
jobspy-search "software engineer" --cities "Berlin" --sites "stepstone,xing" --job-type "contract" --results 1
```

Parameters:

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `<search_term>` | string | No | preference-derived | Search keywords |
| `--cities` | comma-separated string | No | preference-derived | Cities to search |
| `--country` | string | No | preference-derived | Country alias for Indeed and Glassdoor |
| `--sites` | comma-separated string | No | `linkedin` | 1 to 3 sites |
| `--results` | integer | No | `1` | Global extraction budget, clamped to 1 to 15 |
| `--job-type` | string | No | `null` | `fulltime`, `parttime`, `internship`, `contract` |
| `--remote` | flag | No | preference-derived | Remote-only search |
| `--preferences-file` | string | No | auto-discovered | Override resume preferences file |
| `--min-salary-eur` | integer | No | `null` | Reserved preference-style filter |
| `--seniority` | string | No | `null` | `Junior`, `Mid`, `Senior`, `Lead` |
| `--hours-old` | integer | No | `24` | Recency filter |
| `--fetch-descriptions` | flag | No | `false` | Fetch full descriptions from LinkedIn or Naukri |

CLI success output: same JSON search success envelope as `scrape_jobs_tool`.

CLI extraction behavior: `--results` is a global budget across city fan-out.
If multiple default cities are configured and `--results 1` is used
extraction stops after the first collected job.

CLI error output example:

```json
{
  "ok": false,
  "jobs": [],
  "error": {
    "code": "validation_error",
    "message": "Invalid sites: ['monster']. Valid: ['linkedin', 'indeed', 'glassdoor', 'zip_recruiter', 'google', 'bayt', 'naukri', 'stepstone', 'xing']"
  }
}
```

## MCP Server Bootstrap

### jobspy-mcp-server

Purpose: start the MCP server for stdio or HTTP transports.

Invocation:

```bash
jobspy-mcp-server --transport stdio
jobspy-mcp-server --transport sse --host 127.0.0.1 --port 8765
jobspy-mcp-server --transport streamable-http --host 127.0.0.1 --port 8765
```

Flags:

| Flag | Type | Default | Description |
|---|---|---|---|
| `--transport` | string | `stdio` | One of `stdio`, `sse`, `streamable-http` |
| `--host` | string | `127.0.0.1` | Host for HTTP transports |
| `--port` | integer | `8765` | Port for HTTP transports |

Transport behavior:

- `stdio`: MCP over standard input and output for clients like Claude Desktop.
- `sse`: HTTP endpoints at `/sse` and `/messages`.
- `streamable-http`: HTTP endpoint at `/mcp`.

Example initialize request for `streamable-http`:

```json
{
  "jsonrpc": "2.0",
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-03-26",
    "capabilities": {},
    "clientInfo": {
      "name": "example-client",
      "version": "1.0.0"
    }
  },
  "id": 1
}
```

## Migration Note

Before this change, helper MCP tools returned markdown text.
They now return structured JSON envelopes.
If you have an existing client that rendered helper tool output directly,
update it to parse the tool result as JSON and then render the structured fields you need.
