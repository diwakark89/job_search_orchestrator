---
goal: Harden job-search-mcp-server for low-volume personal daily scraping with Supabase-backed dedup
version: 1.0
date_created: 2026-04-19
last_updated: 2026-04-19
owner: diwakark89
status: 'Planned'
tags: [feature, hardening, anti-detection, dedup, personal-use]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan adapts the MCP server for a single-user, once-per-day cron-style execution profile (Germany / Senior Software Engineer / Remote, last 24h). It minimizes ban risk through low-cost behavioral changes and integrates the existing external Supabase store (`public.jobs_raw`) for cross-run deduplication via `external_id` and `job_url`. Storage of new jobs is out of scope (already handled by the separate project) — this plan only **reads** known IDs to filter out already-seen postings before returning results.

## 1. Requirements & Constraints

- **REQ-001**: Single daily run per portal; total surface area <50 HTTP requests per run
- **REQ-002**: Filter results to last 24h, location Germany, remote, role "Senior Software Engineer"
- **REQ-003**: Return only jobs not already present in Supabase `public.jobs_raw`
- **REQ-004**: Zero new paid services (no proxies, no captcha solvers)
- **REQ-005**: Default site list reduced to those that yield signal for German remote SWE roles
- **SEC-001**: Supabase credentials loaded only from environment variables; never committed
- **SEC-002**: Use Supabase `anon` or `service_role` key via `SUPABASE_URL` + `SUPABASE_KEY` env vars; never log keys
- **CON-001**: No async refactor; keep existing `ThreadPoolExecutor` orchestration but cap concurrency
- **CON-002**: No new heavy dependencies; allow only `supabase-py` (already likely present from sister project) or fall back to `httpx` REST calls
- **CON-003**: All anti-detection changes must be opt-in via existing `guardrails.py` constants
- **GUD-001**: Preserve backward compatibility of the `scrape_jobs_tool` MCP signature
- **GUD-002**: All new behavior toggleable through env vars or guardrail constants
- **PAT-001**: Follow ADR-001 (centralize knobs in [`guardrails.py`](job_search_mcp_server/guardrails.py))
- **PAT-002**: Follow existing env-var pattern from [`preferences.py`](job_search_mcp_server/preferences.py#L101)

## 2. Implementation Steps

### Implementation Phase 1: Defaults & Guardrails Tuning

- GOAL-001: Reduce request volume and tighten defaults to a personal-use profile.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In [`guardrails.py`](job_search_mcp_server/guardrails.py): set `RESULTS_WANTED_DEFAULT = 25`, add `INTER_SITE_DELAY_SECONDS_DEFAULT = 60`, add `SEQUENTIAL_SITES_DEFAULT = True`, add `DEDUP_ENABLED_DEFAULT = True` | | |
| TASK-002 | In [`guardrails.py`](job_search_mcp_server/guardrails.py): change `SITES_DEFAULT` from `["linkedin"]` to `["linkedin", "stepstone", "xing", "google"]` | | |
| TASK-003 | In [`guardrails.py`](job_search_mcp_server/guardrails.py): keep `HOURS_OLD_DEFAULT = 24` (already correct); add `COUNTRY_INDEED_DEFAULT = "germany"` | | |
| TASK-004 | Add module docstring note in [`guardrails.py`](job_search_mcp_server/guardrails.py) explaining personal-use profile | | |

### Implementation Phase 2: Sequential Site Execution with Inter-Site Delay

- GOAL-002: Replace parallel fan-out across sites with sequential execution to avoid burst patterns from a single residential IP.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | In [`job_search_scrapers/__init__.py`](job_search_mcp_server/job_search_scrapers/__init__.py) `scrape_jobs()`: detect `SEQUENTIAL_SITES_DEFAULT` flag; when true, iterate sites in a loop instead of submitting all to `ThreadPoolExecutor` simultaneously | | |
| TASK-006 | Between sites, `time.sleep(random.uniform(INTER_SITE_DELAY_SECONDS_DEFAULT, INTER_SITE_DELAY_SECONDS_DEFAULT * 1.5))` | | |
| TASK-007 | Allow per-city parallelism within a single site to remain (since cities are different search params), but cap `ThreadPoolExecutor` `max_workers=2` per site | | |
| TASK-008 | Log start/end timestamp per site at INFO so cron runs are auditable | | |

### Implementation Phase 3: User-Agent Refresh & Cookie Persistence

- GOAL-003: Modernize browser fingerprints across all scrapers and stop wiping LinkedIn cookies on every request.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Update hardcoded `user-agent` in [`linkedin/constant.py`](job_search_mcp_server/job_search_scrapers/linkedin/constant.py) to current Chrome stable (138+) on Windows | | |
| TASK-010 | Audit `constant.py` for `indeed`, `glassdoor`, `google`, `stepstone`, `xing`, `naukri`, `bayt`, `ziprecruiter` and refresh any UAs older than Chrome 130 | | |
| TASK-011 | In LinkedIn scraper init in [`linkedin/__init__.py`](job_search_mcp_server/job_search_scrapers/linkedin/__init__.py): change `clear_cookies=True` → `clear_cookies=False` | | |
| TASK-012 | Add `COOKIE_JAR_DIR` env var (default `~/.job-search_cookies/`); persist `session.cookies` to `<site>.json` after scrape and reload on next run via `requests.cookies.RequestsCookieJar` | | |
| TASK-013 | Add `sec-fetch-dest`, `sec-fetch-mode`, `sec-fetch-site`, `sec-ch-ua`, `sec-ch-ua-mobile`, `sec-ch-ua-platform` to [`linkedin/constant.py`](job_search_mcp_server/job_search_scrapers/linkedin/constant.py) headers dict | | |

### Implementation Phase 4: Supabase-Based Dedup Filter

- GOAL-004: Before returning results from `scrape_jobs_tool`, query Supabase for already-stored job IDs and filter the response.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-014 | Create new module `job_search_mcp_server/dedup.py` with class `SupabaseDedupClient` | | |
| TASK-015 | `SupabaseDedupClient.__init__()` reads `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_JOBS_TABLE` (default `jobs_raw`) from env; raise `RuntimeError` if missing AND dedup enabled | | |
| TASK-016 | Implement `fetch_known_keys(window_days: int = 30) -> set[str]` returning union of `external_id` and `job_url` values where `created_at >= now() - window_days` and `is_deleted = false`. Use Supabase REST `GET /rest/v1/jobs_raw?select=external_id,job_url&created_at=gte.<iso>&is_deleted=eq.false&limit=10000` via `httpx` (no extra dep beyond what's installed) | | |
| TASK-017 | Implement `is_duplicate(job: dict, known: set[str]) -> bool` checking both `job["job_url"]` and `job["external_id"]` (or scraper-specific id field) against `known` | | |
| TASK-018 | In [`server.py`](job_search_mcp_server/server.py) `scrape_jobs_tool()`: after `build_jobs_json_payload()`, if `DEDUP_ENABLED_DEFAULT`, instantiate `SupabaseDedupClient`, call `fetch_known_keys()` once per tool invocation, filter `jobs` list, and add `dedup_summary` to the success envelope (`total_scraped`, `duplicates_removed`, `new_returned`) | | |
| TASK-019 | Add graceful degradation: if Supabase fetch fails, log WARNING and return all jobs (do not block the run) | | |
| TASK-020 | Cache `known_keys` in-process for the lifetime of one tool call; do not refetch per site | | |

### Implementation Phase 5: Daily Scheduling

- GOAL-005: Provide a runnable entry point and Windows Task Scheduler XML so the user can trigger the daily run.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-021 | Add `job_search_mcp_server/daily_run.py` script: loads preferences, calls `scrape_jobs()` directly (bypassing MCP transport), pipes results to stdout JSON for the sister storage project to ingest | | |
| TASK-022 | Add `pyproject.toml` console script entry: `job-search-daily = "job_search_mcp_server.daily_run:main"` | | |
| TASK-023 | Document Windows Task Scheduler setup in repo README (cron equivalent for non-Windows) — daily at 04:00 local | | |

## 3. Alternatives

- **ALT-001**: Local SQLite dedup cache instead of Supabase query → rejected; user already has Supabase as source of truth, two stores risk drift.
- **ALT-002**: Pre-fetch full job table into memory at startup → rejected; tool runs once/day, single fetch per invocation is fine and avoids stale cache.
- **ALT-003**: Push dedup filter into each scraper's `_process_job` to skip fetching descriptions for known jobs → deferred; small optimization, adds coupling. Revisit if API request budget becomes tight.
- **ALT-004**: Use `curl_cffi` to impersonate Chrome JA3 → deferred; not needed at 1 req/day volume per site.
- **ALT-005**: Switch to Adzuna / JSearch / TheirStack official APIs → out of scope (user wants free, current scrapers work).

## 4. Dependencies

- **DEP-001**: `httpx` (likely already transitively present; if not, add to `pyproject.toml`) for Supabase REST calls — avoids pulling full `supabase-py` stack
- **DEP-002**: Existing `requests`, `tls_client`, `bs4` — no version changes
- **DEP-003**: Supabase project must expose `public.jobs_raw` with columns `external_id`, `job_url`, `created_at`, `is_deleted` (already present per repo memory)
- **DEP-004**: Env vars at runtime: `SUPABASE_URL`, `SUPABASE_KEY` (anon or service_role), optional `SUPABASE_JOBS_TABLE`

## 5. Files

- **FILE-001**: [`job_search_mcp_server/guardrails.py`](job_search_mcp_server/guardrails.py) — new constants for personal-use profile
- **FILE-002**: [`job_search_mcp_server/job_search_scrapers/__init__.py`](job_search_mcp_server/job_search_scrapers/__init__.py) — sequential site loop + inter-site delay
- **FILE-003**: [`job_search_mcp_server/job_search_scrapers/linkedin/__init__.py`](job_search_mcp_server/job_search_scrapers/linkedin/__init__.py) — cookie persistence flag
- **FILE-004**: [`job_search_mcp_server/job_search_scrapers/linkedin/constant.py`](job_search_mcp_server/job_search_scrapers/linkedin/constant.py) — refreshed UA + sec-* headers
- **FILE-005**: Other `*/constant.py` UA refreshes as identified in TASK-010
- **FILE-006**: `job_search_mcp_server/dedup.py` — **NEW** Supabase dedup client
- **FILE-007**: [`job_search_mcp_server/server.py`](job_search_mcp_server/server.py) — wire dedup filter into `scrape_jobs_tool`
- **FILE-008**: `job_search_mcp_server/daily_run.py` — **NEW** standalone daily entry point
- **FILE-009**: [`pyproject.toml`](pyproject.toml) — register `job-search-daily` console script
- **FILE-010**: [`README.md`](README.md) — daily scheduling instructions

## 6. Testing

- **TEST-001**: Unit test `test/test_dedup.py::test_fetch_known_keys_returns_union_of_external_id_and_job_url` — mock `httpx.get`, assert returned set
- **TEST-002**: Unit test `test/test_dedup.py::test_is_duplicate_matches_either_key`
- **TEST-003**: Unit test `test/test_dedup.py::test_graceful_degradation_on_supabase_failure` — mock `httpx.HTTPError`, assert empty set returned and warning logged
- **TEST-004**: Update existing `test/test_job_search_mcp.py` guardrail tests to assert new defaults (`RESULTS_WANTED_DEFAULT == 25`, `SITES_DEFAULT == [...]`)
- **TEST-005**: Integration test `test/test_server.py::test_dedup_filters_known_jobs` — mock scraper to return 3 jobs, mock Supabase to return 1 known `job_url`, assert envelope contains 2 jobs and `dedup_summary.duplicates_removed == 1`
- **TEST-006**: Smoke test in `test/local_run.py` — exercise `daily_run.main()` with mocked scrapers + mocked Supabase

## 7. Risks & Assumptions

- **RISK-001**: LinkedIn may still block on first request from a new residential IP regardless of behavior (low prob at this volume).
- **RISK-002**: Supabase free-tier rate limits could throttle the dedup `select` if the table grows beyond 10k rows — mitigated by `window_days=30` filter.
- **RISK-003**: Stepstone/Xing scrapers in this repo may need their own header refreshes that fall outside Phase 3 audit scope.
- **RISK-004**: `external_id` may be `NULL` for legacy rows; `job_url` is the more reliable dedup key.
- **ASSUMPTION-001**: Supabase table `public.jobs_raw` is reachable from the user's home network with the configured `SUPABASE_KEY`.
- **ASSUMPTION-002**: Sister storage project will continue to insert scraped jobs into Supabase after each daily run; this plan does not write.
- **ASSUMPTION-003**: The user's home IP is residential (not flagged as datacenter/VPN). If on VPN, ban risk increases regardless of behavioral hardening.
- **ASSUMPTION-004**: Job URLs from scrapers are normalized (no tracking query params) — confirm in [`json_output.py`](job_search_mcp_server/json_output.py) `build_jobs_json_payload`.

## 8. Related Specifications / Further Reading

- [ADR-001 — Centralized guardrails](job_search_mcp_server/guardrails.py)
- [Supabase REST API filters](https://supabase.com/docs/guides/api/rest/generating-types)
- [/memories/repo/supabase-integration-findings.md](/memories/repo/supabase-integration-findings.md) — schema and integration points already discovered
- [LinkedIn guest API rate limit notes](https://www.linkedin.com/legal/professional-community-policies)
