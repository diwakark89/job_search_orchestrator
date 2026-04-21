# Submit And CRUD Recipes

Copy-ready examples for saving scraped jobs, managing `jobs_final`, and running enrichment.

## Submit Jobs

Primary persistence flow:

```bash
curl -X POST "http://localhost:8000/pipeline/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "jobs": [
      {
        "company_name": "Acme Corp",
        "role_title": "Senior Engineer",
        "job_url": "https://example.com/jobs/1",
        "description": "Build APIs",
        "job_type": "fulltime",
        "work_mode": "remote"
      }
    ]
  }'
```

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
curl "http://localhost:8000/db/jobs-final?job_status=APPLIED&limit=10"
```

```bash
python main.py job-manage table list --table jobs_final --filter job_status=APPLIED --limit 10
```

## Get One Job

```bash
curl "http://localhost:8000/db/jobs-final/550e8400-e29b-41d4-a716-446655440000"
```

```bash
python main.py job-manage table get --table jobs_final --id 550e8400-e29b-41d4-a716-446655440000
```

## Patch One Job

HTTP patch payloads must wrap fields inside `payload`.

```bash
curl -X PATCH "http://localhost:8000/db/jobs-final/550e8400-e29b-41d4-a716-446655440000" \
  -H "Content-Type: application/json" \
  -d '{"payload": {"job_status": "APPLIED"}}'
```

```bash
python main.py job-manage table patch --table jobs_final --filter-column id --filter-value 550e8400-e29b-41d4-a716-446655440000 --payload '{"job_status":"APPLIED"}'
```

## Soft-Delete One Job

```bash
curl -X DELETE "http://localhost:8000/db/jobs-final/550e8400-e29b-41d4-a716-446655440000/soft"
```

```bash
curl -X DELETE "http://localhost:8000/db/jobs-final/550e8400-e29b-41d4-a716-446655440000/soft" \
  -H "Content-Type: application/json" \
  -d '{"hard_delete": true}'
```

```bash
python main.py job-manage table soft-delete --table jobs_final --record-id 550e8400-e29b-41d4-a716-446655440000
```

## Hard Delete One Job

```bash
curl -X DELETE "http://localhost:8000/db/jobs-final/550e8400-e29b-41d4-a716-446655440000"
```

```bash
python main.py job-manage table delete --table jobs_final --filter-column id --filter-value 550e8400-e29b-41d4-a716-446655440000 --treat-404-as-success
```

## Upsert Jobs

```bash
curl -X POST "http://localhost:8000/db/jobs-final" \
  -H "Content-Type: application/json" \
  -d '{
    "rows": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "company_name": "Acme Corp",
        "role_title": "Senior Engineer",
        "job_url": "https://example.com/jobs/1",
        "job_status": "SAVED"
      }
    ]
  }'
```

```bash
python main.py job-manage table upsert --table jobs_final --payload-file payloads/jobs_final_upsert.json
```

## Enrich By Ids

`/enricher/by-ids` expects a JSON array of `{ "id": "..." }` objects and supports `dry_run` as a query parameter.

```bash
curl -X POST "http://localhost:8000/enricher/by-ids?dry_run=true" \
  -H "Content-Type: application/json" \
  -d '[
    {"id": "550e8400-e29b-41d4-a716-446655440000"},
    {"id": "550e8400-e29b-41d4-a716-446655440001"}
  ]'
```

```bash
python main.py job-manage enricher by-ids --ids 550e8400-e29b-41d4-a716-446655440000,550e8400-e29b-41d4-a716-446655440001 --dry-run
```

```bash
python main.py job-manage enricher by-ids --ids-file payloads/job_ids.json --dry-run
```

## Pipeline Metrics

```bash
curl "http://localhost:8000/pipeline/metrics"
```

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
