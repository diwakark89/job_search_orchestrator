# Submit And CRUD Recipes

Copy-ready CLI examples for saving scraped jobs, managing `jobs_final`, and running enrichment.

This reference is **CLI-only**. OpenClaw should execute these commands directly for this workflow.

## Submit Jobs

Primary persistence flow:

```bash
python main.py job-manage pipeline submit payloads/jobs_raw.json
```

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

## List Jobs

```bash
python main.py job-manage table list --table jobs_final --filter job_status=APPLIED --limit 10
```

## Get One Job

```bash
python main.py job-manage table get --table jobs_final --id 550e8400-e29b-41d4-a716-446655440000
```

## Patch One Job

```bash
python main.py job-manage table patch --table jobs_final --filter-column id --filter-value 550e8400-e29b-41d4-a716-446655440000 --payload '{"job_status":"APPLIED"}'
```

## Soft-Delete One Job

```bash
python main.py job-manage table soft-delete --table jobs_final --record-id 550e8400-e29b-41d4-a716-446655440000
```

## Hard Delete One Job

```bash
python main.py job-manage table delete --table jobs_final --filter-column id --filter-value 550e8400-e29b-41d4-a716-446655440000 --treat-404-as-success
```

## Upsert Jobs

```bash
python main.py job-manage table upsert --table jobs_final --payload-file payloads/jobs_final_upsert.json
```

## Create Automation Session

```bash
python main.py job-manage automation-session create --payload '{"job_id":"550e8400-e29b-41d4-a716-446655440000","automation_type":"JOB_APPLY","session_status":"RUNNING","current_step":"OPEN_JOB_PAGE"}'
```

## List Automation Sessions

```bash
python main.py job-manage automation-session list --filter session_status=RUNNING --limit 10
```

## Patch Automation Session

```bash
python main.py job-manage automation-session patch --id 550e8400-e29b-41d4-a716-446655440000 --payload '{"session_status":"WAITING_USER","current_step":"FINAL_REVIEW"}'
```

## Delete Automation Session

```bash
python main.py job-manage automation-session delete --id 550e8400-e29b-41d4-a716-446655440000
```

## Approve Or Reject For Apply

```bash
python main.py job-manage automation-session approve-job --job-id 550e8400-e29b-41d4-a716-446655440000
python main.py job-manage automation-session reject-job --job-id 550e8400-e29b-41d4-a716-446655440000
```

## Create Apply Session

```bash
python main.py job-manage automation-session create-apply-session --job-id 550e8400-e29b-41d4-a716-446655440000
```

## Enrich By Ids

```bash
python main.py job-manage enricher by-ids --ids 550e8400-e29b-41d4-a716-446655440000,550e8400-e29b-41d4-a716-446655440001 --dry-run
```

```bash
python main.py job-manage enricher by-ids --ids-file payloads/job_ids.json --dry-run
```

## Pipeline Metrics

```bash
python main.py job-manage pipeline metrics
```

Metrics response shape:

```json
{
  "status_counts": {
    "SCRAPED": 5,
    "ENRICHED": 3,
    "SAVED": 10,
    "APPLIED": 2
  },
  "total": 20
}
```
