---
name: jobspy_search
description: Search for jobs across 9 job boards (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google, Bayt, Naukri, Stepstone, Xing). Use when the user asks about job listings, career opportunities, open positions, or hiring.
metadata:
  {
    "openclaw":
      {
        "requires": { "bins": ["jobspy-search"] },
        "os": ["darwin", "linux", "win32"],
      },
  }
---

# JobSpy Job Search Skill

Search for jobs across **9 job boards** using the locally installed JobSpy MCP Server.

## When to Use

Use this skill when the user asks to:

- Search or find job listings / open positions
- Look for jobs on specific job boards
- Find remote jobs, jobs in a specific city, or jobs matching certain criteria
- Get information about supported job boards or countries

## Method A: CLI (exec tool) — Recommended

Run the `jobspy-search` CLI via the `exec` tool. This is the simplest approach and requires no background server.

### Basic Syntax

```bash
jobspy-search "<search_term>" [options]
```

### Parameters

| Flag                   | Type   | Default      | Description                                                                                                                                    |
| ---------------------- | ------ | ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `<search_term>`        | string | **required** | Job search keywords (e.g. `"software engineer"`)                                                                                               |
| `--cities`             | string | none         | Comma-separated city filters (e.g. `"San Francisco,New York"`)                                                                                 |
| `--sites`              | string | `linkedin`   | Comma-separated job boards (max 3). Valid: `linkedin`, `indeed`, `glassdoor`, `zip_recruiter`, `google`, `bayt`, `naukri`, `stepstone`, `xing` |
| `--results`            | int    | `10`         | Number of results (1–15)                                                                                                                       |
| `--job-type`           | string | none         | `fulltime`, `parttime`, `internship`, or `contract`                                                                                            |
| `--remote`             | flag   | false        | Filter for remote jobs only                                                                                                                    |
| `--hours-old`          | int    | `24`         | Only jobs posted within last N hours (1–72)                                                                                                    |
| `--country`            | string | `usa`        | Country for Indeed/Glassdoor searches                                                                                                          |
| `--fetch-descriptions` | flag   | false        | Fetch full descriptions from LinkedIn/Naukri (slower)                                                                                          |
| `--preferences-file`   | string | auto         | Optional path to a resume preferences YAML file                                                                                                |

### Examples

**Search for Python developer jobs in NYC:**

```bash
jobspy-search "python developer" --cities "New York" --sites "linkedin,indeed" --results 5
```

**Find remote data science roles posted in last 48 hours:**

```bash
jobspy-search "data scientist" --remote --hours-old 48 --sites "indeed,glassdoor"
```

**Search for jobs in India on Naukri:**

```bash
jobspy-search "machine learning engineer" --cities "Bangalore" --sites "naukri,linkedin" --country "india"
```

**Find contract jobs in Germany:**

```bash
jobspy-search "software engineer" --cities "Berlin" --sites "stepstone,xing" --job-type "contract"
```

**Pipeline smoke test (OpenClaw/developer integration):**

```bash
jobspy-search "software engineer" --cities "Berlin" --sites "stepstone,xing" --job-type "contract" --results 1
```

**Quick broad search across multiple boards:**

```bash
jobspy-search "product manager" --sites "indeed,linkedin,glassdoor" --results 10
```

## Method B: HTTP Server (web_fetch tool) — Advanced

If the MCP server is running as an HTTP service, use `web_fetch` to interact with it.

### Start the Server (run once in background)

```bash
jobspy-mcp-server --transport sse --host 127.0.0.1 --port 8765
```

### Call via curl/web_fetch

The server exposes a standard MCP SSE endpoint at `http://127.0.0.1:8765/sse`.

MCP tool calls are sent as JSON-RPC messages. Example using curl:

```bash
curl -X POST http://127.0.0.1:8765/messages \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"scrape_jobs_tool","arguments":{"search_term":"software engineer","cities":["New York"],"site_name":["linkedin"],"results_wanted":5}},"id":1}'
```

## Available MCP Tools (HTTP mode)

When running as an HTTP server, these MCP tools are available:

1. **`scrape_jobs_tool`** — Main job search tool (parameters same as CLI flags above)
2. **`get_supported_countries`** — Returns a JSON envelope with supported country identifiers
3. **`get_supported_sites`** — Returns a JSON envelope with all 9 job boards and usage guidance
4. **`get_job_search_tips`** — Returns a JSON envelope with search optimization guidance

## API Reference

All MCP tools and the CLI return structured JSON envelopes. Below is a summary of the response contract. For the full canonical specification, see [`references/API_Integration.md`](./references/API_Integration.md).

### Response Format

A successful search returns:

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
      "source_platform": "linkedin",
      "scraped_at": "2026-04-09T12:00:00+00:00",
      "content_hash": "3af6df4f..."
    }
  ],
  "error": null
}
```

Helper tools (`get_supported_countries`, `get_supported_sites`, `get_job_search_tips`) use the same `ok` / `error` fields with tool-specific data keys (e.g. `sites`, `countries`, `tips`).

### Error Handling

When a request fails, the envelope signals the error clearly:

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

Always check `ok` before consuming `jobs`. The `error.code` field indicates the error category (`validation_error`, `runtime_error`, etc.) and `error.message` provides a human-readable explanation.

### Description Source Values

The `jobs[].description_source` field tells you how the description was obtained:

| Value         | Meaning                                    | Confidence |
| ------------- | ------------------------------------------ | ---------- |
| `detail_page` | Fetched from the dedicated job detail page | Highest    |
| `listing_api` | Came from the listing/search API payload   | Medium     |
| `null`        | No usable description text was extracted   | Lowest     |

Prefer `detail_page` descriptions when available. Unknown or non-canonical values are normalized to `null`.

> **Full API contract:** [`docs/API_Integration.md`](../../docs/API_Integration.md) — includes all MCP tool parameters, CLI flags, server bootstrap options, and migration notes.

## Tips

- **Start with 1–2 sites** to keep searches fast; expand if needed.
- **Indeed** is the most reliable and least rate-limited.
- **LinkedIn** has the best data quality but stricter rate limits.
- Use `--fetch-descriptions` only when you need full job descriptions (it's slower).
- For Middle East jobs use `bayt`; for India use `naukri`; for Germany/DACH use `stepstone` or `xing`.
- If no results are found, try broader search terms or different sites.

## Troubleshooting

- **"command not found: jobspy-search"** — The package is not installed. Run: `pip install -e /path/to/jobs-search-mcp-server`
- **No results** — Try broader keywords, different sites, or increase `--hours-old`.
- **Rate limiting / blocks** — Reduce `--results`, try `indeed` instead of `linkedin`.
- **HTTP server not responding** — Ensure the server is running: `jobspy-mcp-server --transport sse --port 8765`
