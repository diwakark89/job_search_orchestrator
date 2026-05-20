---
name: job-manager
description: Search supported job boards, submit scraped jobs for async persistence and enrichment, run the full automated scrape-enrich-approve-apply-confirm pipeline, and perform jobs-final and automation-sessions CRUD operations in the Automated Job Hunt Orchestrator. Use when the user asks to find jobs, run the automated pipeline, save scraped jobs to the database, update job status, approve or reject jobs for apply automation, create automation sessions, soft-delete records, enrich by ids, or read pipeline metrics.
---

# Job Manager Skill

Manage jobs in the **Automated Job Hunt Orchestrator** through CLI commands only. This skill covers four main workflows:

- search jobs across supported external job boards
- save scraped jobs through the pipeline submit flow
- perform CRUD-style operations against `jobs_final`
- run approval and automation-session lifecycle for auto-apply

> Format reference: this skill follows the OpenClaw skill spec at <https://docs.openclaw.ai/tools/creating-skills>.

## When to Use

Use this skill when the user asks to:

- **Search / scrape** jobs from supported boards such as LinkedIn, Indeed, and Glassdoor
- **Submit** scraped jobs for ingestion and background enrichment
- **List / query** tracked jobs by company, status, role, or other fields
- **Get** a single job by id
- **Update** a job (e.g. mark `job_status` as `APPLIED`, `INTERVIEWING`, `REJECTED`)
- **Soft-delete** a job (sets `is_deleted=true` instead of removing the row)
- **Hard-delete** a job when permanent removal is required
- **Run enrichment** on `SCRAPED` rows or a specific list of ids
- **Read pipeline metrics** to see counts by `job_status`
- **Run the full automated pipeline** — scrape → enrich → score-gate → approve/reject → create apply session → apply via Playwright → pause for Telegram confirmation → submit

## Prerequisites

- Work from repository root.
- Python environment must be available.
- Use one launcher:
  - `python main.py ...`
  - `.\\.venv\\Scripts\\python.exe main.py ...` (Windows fallback when interpreter resolution fails)
- CLI examples assume you are in the repository root with the project environment available.

## OpenClaw Runtime Policy: CLI-Only Mandatory

OpenClaw must use a **strict CLI-only execution model** for this skill.

Execution policy:

1. **Always execute the CLI command directly** for the requested operation.
2. **Do not use HTTP routes** in this skill.
3. **Do not require starting the API server** for normal operations.
4. If a CLI command fails, report the exact blocker and provide the exact fix command.

### CLI Execution Runbook (Detailed)

Use this sequence before any job-manager action:

1. Map the user request to the CLI command in the map below.
2. Run from repository root with one of the launchers in **Prerequisites**.
3. For submit operations, ensure the input file is either:
   - a top-level array of job objects, or
   - an object with a `jobs` array.
4. Validate submit output keys:
   - `submitted_row_count`
   - `accepted` with `count` and `ids`
   - `queued` with `count` and `ids`
   - `rejected_row_indexes`
   - `errors`
   - `jobs_final_row_count`
5. Submit output does **not** include `shared_links_row_count`.
6. If CLI fails due environment/configuration, report the blocker and the exact fix command.

### CLI Command Map (Use First)

| Requested operation                   | CLI command                                                                                                                              |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Search jobs                           | `python main.py job-search "software engineer" --sites linkedin,indeed --results 5`                                                      |
| Submit scraped jobs                   | `python main.py job-manage pipeline submit payloads/jobs_raw.json`                                                                       |
| List jobs                             | `python main.py job-manage table list --table jobs_final --filter job_status=APPLIED --limit 10`                                         |
| Get one job                           | `python main.py job-manage table get --table jobs_final --id <UUID>`                                                                     |
| Upsert jobs                           | `python main.py job-manage table upsert --table jobs_final --payload-file payloads/jobs_final_upsert.json`                               |
| Patch one job                         | `python main.py job-manage table patch --table jobs_final --filter-column id --filter-value <UUID> --payload '{"job_status":"APPLIED"}'` |
| Soft-delete one job                   | `python main.py job-manage table soft-delete --table jobs_final --record-id <UUID>`                                                      |
| Hard delete one job                   | `python main.py job-manage table delete --table jobs_final --filter-column id --filter-value <UUID> --treat-404-as-success`              |
| List automation sessions              | `python main.py job-manage automation-session list --filter session_status=RUNNING --limit 10`                                           |
| Get one automation session            | `python main.py job-manage automation-session get --id <UUID>`                                                                           |
| Create automation session             | `python main.py job-manage automation-session create --payload '{"job_id":"<JOB_UUID>","automation_type":"JOB_APPLY"}'`                  |
| Patch automation session              | `python main.py job-manage automation-session patch --id <UUID> --payload '{"session_status":"WAITING_USER"}'`                           |
| Delete automation session             | `python main.py job-manage automation-session delete --id <UUID>`                                                                        |
| Approve job for apply                 | `python main.py job-manage automation-session approve-job --job-id <UUID>`                                                               |
| Reject job for apply                  | `python main.py job-manage automation-session reject-job --job-id <UUID>`                                                                |
| Create apply session for approved job | `python main.py job-manage automation-session create-apply-session --job-id <UUID>`                                                      |
| Run enricher                          | `python main.py job-manage enricher enrich --limit 20 --dry-run`                                                                         |
| Enrich by ids                         | `python main.py job-manage enricher by-ids --ids <UUID1>,<UUID2> --dry-run`                                                              |
| Pipeline metrics                      | `python main.py job-manage pipeline metrics`                                                                                             |

## Supported Job Boards

Use `python main.py job-search ...` to scrape jobs from boards supported by the orchestrator. The exact board ids and search guardrails are documented in [supported-job-boards.md](./references/supported-job-boards.md).

Common examples:

```bash
python main.py job-search "software engineer" --sites linkedin,indeed --results 5 --hours-old 24
```

```bash
job-search "data scientist" --sites linkedin,glassdoor --results 3 --country germany
```

## Save Flow: Use Pipeline Submit

When the user wants to **save scraped jobs to the database**, the primary flow is:

- CLI only: `python main.py job-manage pipeline submit <file.json>`

The CLI command validates input rows, writes accepted jobs into `jobs_final` with initial `job_status=SCRAPED`, and starts in-process background enrichment for accepted ids.

Expected response shape:

```json
{
  "submitted_row_count": 1,
  "accepted": { "count": 1, "ids": ["550e8400-e29b-41d4-a716-446655440000"] },
  "queued": { "count": 1, "ids": ["550e8400-e29b-41d4-a716-446655440000"] },
  "rejected_row_indexes": [],
  "errors": [],
  "jobs_final_row_count": 1
}
```

### CLI Submit Example

```bash
python main.py job-manage pipeline submit payloads/jobs_raw.json
```

The JSON file may contain either a top-level array of job objects or an object with a `jobs` array.

## Core CLI Operations

Use the unified CLI for local operations.

| Operation             | Command                                                                                                                                  |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| List supported tables | `python main.py job-manage table tables`                                                                                                 |
| Create session        | `python main.py job-manage automation-session create --payload '{"job_id":"<JOB_UUID>","automation_type":"JOB_APPLY"}'`                  |
| List sessions         | `python main.py job-manage automation-session list --filter session_status=RUNNING --limit 10`                                           |
| Get one session       | `python main.py job-manage automation-session get --id <UUID>`                                                                           |
| Patch one session     | `python main.py job-manage automation-session patch --id <UUID> --payload '{"session_status":"WAITING_USER"}'`                           |
| Hard delete session   | `python main.py job-manage automation-session delete --id <UUID>`                                                                        |
| List rows             | `python main.py job-manage table list --table jobs_final --filter job_status=APPLIED --limit 10`                                         |
| Get one row           | `python main.py job-manage table get --table jobs_final --id <UUID>`                                                                     |
| Upsert rows           | `python main.py job-manage table upsert --table jobs_final --payload-file payloads/jobs_final_upsert.json`                               |
| Patch a row           | `python main.py job-manage table patch --table jobs_final --filter-column id --filter-value <UUID> --payload '{"job_status":"APPLIED"}'` |
| Soft-delete a row     | `python main.py job-manage table soft-delete --table jobs_final --record-id <UUID>`                                                      |
| Hard delete a row     | `python main.py job-manage table delete --table jobs_final --filter-column id --filter-value <UUID> --treat-404-as-success`              |
| Submit jobs           | `python main.py job-manage pipeline submit payloads/jobs_raw.json`                                                                       |
| Run enricher          | `python main.py job-manage enricher enrich --limit 20 --dry-run`                                                                         |
| Enrich by ids         | `python main.py job-manage enricher by-ids --ids <UUID1>,<UUID2> --dry-run`                                                              |
| Enrich by ids file    | `python main.py job-manage enricher by-ids --ids-file payloads/job_ids.json --dry-run`                                                   |
| Pipeline metrics      | `python main.py job-manage pipeline metrics`                                                                                             |
| Search job boards     | `python main.py job-search "software engineer" --sites linkedin,indeed --results 5`                                                      |

## Which CLI Command To Use

| Goal                           | CLI command or command group                                            | Notes                                                            |
| ------------------------------ | ----------------------------------------------------------------------- | ---------------------------------------------------------------- | ----------- | ----------- | -------------------------------- |
| Track browser automation state | `job-manage automation-session ...`                                     | Create/update/list automation session state per job              |
| Search external job boards     | `python main.py job-search ...`                                         | Search/scrape is provided through the CLI surface                |
| Save scraped jobs to DB        | `python main.py job-manage pipeline submit <file.json>`                 | Primary persistence flow; writes `SCRAPED` and queues enrichment |
| Ingest jobs only               | `python main.py job-manage pipeline stage-ingest <file.json>`           | Writes rows as `SCRAPED` without running enrichment              |
| Enrich existing `SCRAPED` rows | `python main.py job-manage enricher enrich --limit <N> [--dry-run]`     | Processes scraped jobs with enrichment                           |
| Enrich specific records        | `python main.py job-manage enricher by-ids --ids <id1,id2> [--dry-run]` | Targeted enrichment by explicit ids                              |
| Read/update/delete one job     | `job-manage table get                                                   | patch                                                            | soft-delete | delete ...` | Direct `jobs_final` CRUD via CLI |

## Automated End-to-End Pipeline Workflow

This section is the authoritative runbook for OpenClaw running the full automated apply pipeline. OpenClaw is the browser automation worker; `job_manager` is the orchestration brain; all state is persisted in Supabase via the CLI commands below.

Full flow: **Scrape → Submit → Enrich → Score Gate → Approve/Reject → Create Session → Apply → Pause → Telegram Confirm → Submit → Done**

### Phase 1: Scrape and Submit

Search for jobs on configured boards and immediately submit them for ingestion:

```bash
# Search and write results to a file
python main.py job-search "software engineer" --sites linkedin,indeed --results 10 --hours-old 24 > payloads/jobs_raw.json

# Submit to pipeline (validates, deduplicates, writes SCRAPED rows)
python main.py job-manage pipeline submit payloads/jobs_raw.json
```

Expected submit output keys: `submitted_row_count`, `accepted`, `queued`, `rejected_row_indexes`, `errors`, `jobs_final_row_count`.

### Phase 2: Enrich

Enrichment fires automatically in the background after `pipeline submit`. If enrichment must be re-run manually:

```bash
python main.py job-manage enricher enrich --limit 50
```

Enrichment sets `job_status=ENRICHED` and writes `match_score`, `decision`, and tech stack fields.

### Phase 3: Score Decision Gate

Query all newly `ENRICHED` rows and evaluate each `match_score`:

```bash
python main.py job-manage table list --table jobs_final --filter job_status=ENRICHED --limit 50
```

For each row apply the following thresholds:

| `match_score` range | Action                                         | CLI command                                                                |
| ------------------- | ---------------------------------------------- | -------------------------------------------------------------------------- |
| **≥ 85**            | Silent auto-approve (no Telegram)              | `python main.py job-manage automation-session approve-job --job-id <UUID>` |
| **65 – 84**         | Send Telegram approval request; wait for reply | See Telegram approval flow below                                           |
| **< 65**            | Silent auto-reject (no Telegram)               | `python main.py job-manage automation-session reject-job --job-id <UUID>`  |

`approve-job` transitions `job_status → READY_TO_APPLY` and sets `user_action=APPROVED`.
`reject-job` transitions `job_status → SAVED` and sets `user_action=REJECTED`.

#### Telegram Approval Flow (65 – 84 band)

1. Send a Telegram message with the job summary (company, role, `job_url`, `match_score`) and ask the user to reply **APPROVE** or **REJECT**.
2. Wait for the reply.
3. On **APPROVE**:
   ```bash
   python main.py job-manage automation-session approve-job --job-id <UUID>
   ```
4. On **REJECT**:
   ```bash
   python main.py job-manage automation-session reject-job --job-id <UUID>
   ```

### Phase 4: Create Apply Session

For every job that is now `READY_TO_APPLY` (approved in Phase 3), create an automation session:

```bash
python main.py job-manage automation-session create-apply-session --job-id <UUID>
```

Preconditions enforced by the service:

- `job_status` must be `READY_TO_APPLY`
- `user_action` must be `APPROVED`
- No other active session (`RUNNING` or `RESUMING`) may already exist for this `job_id`

On success the session is created with `session_status=RUNNING` and `current_step=OPEN_JOB_PAGE`.

Output keys: `session_id`, `job_id`, `session_status`, `current_step`.

### Phase 5: OpenClaw Applies (Playwright)

Fetch sessions ready for work:

```bash
python main.py job-manage automation-session list --filter session_status=RUNNING --limit 10
```

For each `RUNNING` session, execute the Playwright apply workflow. As each browser step completes, patch `current_step` to reflect progress:

```bash
# Example step progression patches
python main.py job-manage automation-session patch --id <SESSION_UUID> --payload '{"current_step":"FILL_FORM"}'
python main.py job-manage automation-session patch --id <SESSION_UUID> --payload '{"current_step":"UPLOAD_RESUME"}'
python main.py job-manage automation-session patch --id <SESSION_UUID> --payload '{"current_step":"REVIEW_ANSWERS"}'
```

On a recoverable step failure, increment retry count and persist the error:

```bash
python main.py job-manage automation-session patch --id <SESSION_UUID> --payload '{"last_error":"<message>","retry_count":1}'
```

On a terminal failure, mark the session failed:

```bash
python main.py job-manage automation-session patch --id <SESSION_UUID> --payload '{"session_status":"FAILED","last_error":"<reason>"}'
```

### Phase 6: Pause for Final Confirmation

Before clicking the final submit button, save the browser state and a screenshot, then transition both records to their waiting states:

```bash
# 1. Patch session to WAITING_USER and record artifact paths
python main.py job-manage automation-session patch --id <SESSION_UUID> \
  --payload '{"session_status":"WAITING_USER","current_step":"FINAL_REVIEW","screenshot_path":"<absolute_path_to_screenshot>","browser_state_path":"<absolute_path_to_browser_state>"}'

# 2. Patch job to WAITING_CONFIRMATION
python main.py job-manage table patch --table jobs_final \
  --filter-column id --filter-value <JOB_UUID> \
  --payload '{"job_status":"WAITING_CONFIRMATION"}'
```

Then send a Telegram message using the built-in Telegram tool:

- Attach the screenshot file at `screenshot_path`
- Include: company name, role title, `job_url`, `match_score`, and `session_id`
- Ask the user to reply **SUBMIT** or **CANCEL**

### Phase 7: User Responds via Telegram

Wait for the user's reply to the Phase 6 Telegram message.

**On SUBMIT:**

```bash
python main.py job-manage automation-session patch --id <SESSION_UUID> \
  --payload '{"session_status":"RESUMING"}'
```

Proceed to Phase 8.

**On CANCEL:**

```bash
# Mark session failed
python main.py job-manage automation-session patch --id <SESSION_UUID> \
  --payload '{"session_status":"FAILED","last_error":"Cancelled by user"}'

# Reset job to SAVED
python main.py job-manage table patch --table jobs_final \
  --filter-column id --filter-value <JOB_UUID> \
  --payload '{"job_status":"SAVED"}'
```

### Phase 8: Resume and Submit

Fetch sessions ready to resume:

```bash
python main.py job-manage automation-session list --filter session_status=RESUMING --limit 10
```

For each, restore the Playwright browser state from `browser_state_path`, then execute the final submit click.

**On success:**

```bash
# Mark session completed
python main.py job-manage automation-session patch --id <SESSION_UUID> \
  --payload '{"session_status":"COMPLETED","current_step":"SUBMITTED"}'

# Mark job applied
python main.py job-manage table patch --table jobs_final \
  --filter-column id --filter-value <JOB_UUID> \
  --payload '{"job_status":"APPLIED"}'
```

**On failure:**

```bash
python main.py job-manage automation-session patch --id <SESSION_UUID> \
  --payload '{"session_status":"FAILED","last_error":"<reason>"}'
```

### State Machine Reference

`jobs_final` transitions in the automated pipeline:

| From                   | To                     | Triggered by                                   |
| ---------------------- | ---------------------- | ---------------------------------------------- |
| `SCRAPED`              | `ENRICHED`             | Enricher run                                   |
| `ENRICHED`             | `READY_TO_APPLY`       | `approve-job` (score ≥ 85 or Telegram APPROVE) |
| `ENRICHED`             | `SAVED`                | `reject-job` (score < 65 or Telegram REJECT)   |
| `READY_TO_APPLY`       | `WAITING_CONFIRMATION` | Phase 6 pause patch                            |
| `WAITING_CONFIRMATION` | `APPLIED`              | Phase 8 success patch                          |
| `WAITING_CONFIRMATION` | `SAVED`                | Phase 7 CANCEL patch                           |

`automation_sessions` transitions in the automated pipeline:

| From           | To             | Triggered by              |
| -------------- | -------------- | ------------------------- |
| _(new)_        | `RUNNING`      | `create-apply-session`    |
| `RUNNING`      | `WAITING_USER` | Phase 6 pause patch       |
| `RUNNING`      | `FAILED`       | Terminal Playwright error |
| `WAITING_USER` | `RESUMING`     | Phase 7 SUBMIT patch      |
| `WAITING_USER` | `FAILED`       | Phase 7 CANCEL patch      |
| `RESUMING`     | `COMPLETED`    | Phase 8 success patch     |
| `RESUMING`     | `FAILED`       | Phase 8 submit error      |

## Field And Enum Reference

`jobs_final` fields commonly used in these workflows:

| Field          | Type   | Notes                                                                                                                                                              |
| -------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `id`           | UUID   | Primary key and upsert conflict key                                                                                                                                |
| `company_name` | string | Company name                                                                                                                                                       |
| `role_title`   | string | Job title                                                                                                                                                          |
| `job_url`      | string | Unique URL used for dedupe during submit                                                                                                                           |
| `description`  | string | Raw or enriched description                                                                                                                                        |
| `job_type`     | enum   | `fulltime`, `parttime`, `internship`, `contract`, `temporary`, `other`                                                                                             |
| `work_mode`    | enum   | `remote`, `hybrid`, `on-site`, `other`                                                                                                                             |
| `job_status`   | enum   | `SCRAPED`, `ENRICHED`, `SAVED`, `READY_TO_APPLY`, `WAITING_CONFIRMATION`, `APPLIED`, `INTERVIEW`, `INTERVIEWING`, `OFFER`, `RESUME_REJECTED`, `INTERVIEW_REJECTED` |
| `is_deleted`   | bool   | Excluded from enricher pickup when true                                                                                                                            |

`automation_sessions` fields commonly used in these workflows:

| Field                | Type      | Notes                                                                                 |
| -------------------- | --------- | ------------------------------------------------------------------------------------- |
| `id`                 | UUID      | Primary key and upsert conflict key                                                   |
| `job_id`             | UUID      | Foreign key to `jobs_final.id` — required on create                                   |
| `automation_type`    | enum      | `JOB_APPLY`                                                                           |
| `session_status`     | enum      | `RUNNING`, `WAITING_USER`, `RESUMING`, `COMPLETED`, `FAILED`                          |
| `current_step`       | string    | Free-form step label (e.g. `OPEN_JOB_PAGE`, `FILL_FORM`, `FINAL_REVIEW`, `SUBMITTED`) |
| `browser_state_path` | string    | Absolute path to saved Playwright browser state artifact                              |
| `screenshot_path`    | string    | Absolute path to screenshot taken before final submit                                 |
| `last_error`         | string    | Last recoverable or terminal error message                                            |
| `retry_count`        | integer   | Number of step-level retries; default `0`                                             |
| `started_at`         | timestamp | Session creation time (UTC, set automatically)                                        |
| `updated_at`         | timestamp | Last update time (UTC, maintained by DB trigger)                                      |

Important constraints:

- Unknown `job_type` and `work_mode` values normalize to `other`
- Do not send `job_id`; use `id`
- Do not send `remote_type`; use `work_mode`
- Rows containing unsupported fields such as `tags` may be rejected

## CLI Error Patterns

| Pattern                       | Cause                                          | Example output                                                              |
| ----------------------------- | ---------------------------------------------- | --------------------------------------------------------------------------- |
| `Invalid JSON payload`        | Bad JSON passed to `--payload` or payload file | `Invalid JSON payload: Expecting ',' delimiter ...`                         |
| `Invalid --filter`            | Filter not in `key=value` format               | `Invalid --filter 'job_status'. Expected key=value format.`                 |
| `Unsupported table`           | Unknown table name in table commands           | `Unsupported table 'foo'. Supported: ['automation_sessions', 'jobs_final']` |
| `operation=... success=False` | Repository/client operation failed             | `operation=patch table=jobs_final success=False status=502 rows=0`          |

Always check the CLI result line (`success=` and `status=`) before trusting returned payloads.

## Tips

- Prefer `python main.py job-manage pipeline submit ...` instead of manual upsert + enrich for scraped jobs
- For status updates, patch only the fields that changed
- Use `dry_run: true` for enrich flows when you want a non-writing preview
- The enricher only picks up rows where `job_status=SCRAPED` and `is_deleted=false`

## Troubleshooting

- **CLI command not found**: run with the active virtual environment launcher (`python main.py ...` or `.\\.venv\\Scripts\\python.exe main.py ...`)
- **`Unsupported table`**: use underscored table names such as `jobs_final` and `automation_sessions`
- **`400 Extra inputs are not permitted`**: remove unsupported fields such as `tags`, `remote_type`, or `job_id`
- **`success=False` on enrich commands**: verify Copilot/Supabase environment variables and retry with `--dry-run` first
- **Background enrichment from submit is in-process**: if a run is interrupted, rerun enrichment manually

## References

- [supported-job-boards.md](./references/supported-job-boards.md) — exact supported board ids and search guardrails
- [submit-and-crud-recipes.md](./references/submit-and-crud-recipes.md) — copy-ready submit, CRUD, enrich, and metrics recipes
- <https://docs.openclaw.ai/tools/creating-skills> — OpenClaw skill format reference
