# Supported Job Boards

The orchestrator scraping flow supports these exact job board ids:

- `linkedin`
- `indeed`
- `glassdoor`
- `zip_recruiter`
- `google`
- `bayt`
- `naukri`
- `stepstone`
- `xing`
- `berlin_startup_jobs`
- `welcome_to_the_jungle`
- `eu_startups`
- `join`

## Search Guardrails

These limits come from the orchestrator scraping guardrails:

| Parameter | Min | Max | Default |
| --- | --- | --- | --- |
| `sites` | 1 | 5 | `linkedin` |
| `results` | 1 | 50 | `1` |
| `hours_old` | 1 | 72 | `24` |

## Search Examples

Search through the orchestrator CLI:

```bash
python main.py job-search "software engineer" --sites linkedin,indeed --results 5 --hours-old 24
```

```bash
python main.py job-search "data scientist" --sites glassdoor,google --results 10 --country germany
```

Search through the installed script:

```bash
job-search "backend engineer" --sites linkedin,indeed --results 3 --hours-old 48
```

```bash
job-search "product manager" --sites linkedin --cities Berlin,Munich --country Germany --results 2
```

## Notes

- Use comma-separated values for `--sites`
- `job-search` is the installed script name
- `python main.py job-search ...` uses the orchestrator-owned scraping flow and is the safest documentation target for feature coverage
