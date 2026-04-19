# Example MCP Calls for Job Search

This file contains example MCP tool calls and their expected JSON outputs.

## Basic Search with Cities

### Request
```json
{
  "tool": "scrape_jobs_tool",
  "params": {
    "search_term": "software engineer",
    "cities": ["Munich", "Berlin", "Frankfurt"],
    "country_indeed": "germany",
    "results_wanted": 10,
    "site_name": ["indeed", "linkedin"]
  }
}
```

### Response
```json
{
  "ok": true,
  "jobs": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "company_name": "TechCorp Inc.",
      "role_title": "Software Engineer",
      "description": "We are looking for a talented Software Engineer to join our team...",
      "description_source": "listing_api",
      "job_type": "fulltime",
      "job_url": "https://indeed.com/viewjob?jk=abc123",
      "location": "Munich, Germany",
      "work_mode": "on-site",
      "language": "English",
      "source_platform": "indeed",
      "scraped_at": "2026-04-05T12:00:00+00:00",
      "content_hash": "0cb62f2d07c0ecb8c80b25949b73e5a7bde9f43af8c9459ff18ea48b868cd1f0"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "company_name": "StartupXYZ",
      "role_title": "Senior Software Engineer",
      "description": "Join our growing team as a Senior Software Engineer...",
      "description_source": "detail_page",
      "job_type": "fulltime",
      "job_url": "https://linkedin.com/jobs/view/123456789",
      "location": "Berlin, Germany",
      "work_mode": "hybrid",
      "language": "English",
      "source_platform": "linkedin",
      "scraped_at": "2026-04-05T12:00:00+00:00",
      "content_hash": "06eebea261d4e78be0db4eb32973fd11be8b1632634e7bbf1ad1a6ef6cc8396b"
    }
  ],
  "error": null
}
```

---

## Remote Jobs Search (No City Filter)

### Request
```json
{
  "tool": "scrape_jobs_tool",
  "params": {
    "search_term": "Python developer",
    "is_remote": true,
    "site_name": ["indeed", "zip_recruiter"],
    "results_wanted": 20
  }
}
```

---

## Recent Data Science Jobs in Multiple US Cities

### Request
```json
{
  "tool": "scrape_jobs_tool",
  "params": {
    "search_term": "data scientist",
    "cities": ["Boston", "New York", "San Francisco"],
    "country_indeed": "usa",
    "hours_old": 48,
    "site_name": ["linkedin", "glassdoor", "indeed"],
    "linkedin_fetch_description": true
  }
}
```

---

## International Search (Germany)

### Request
```json
{
  "tool": "scrape_jobs_tool",
  "params": {
    "search_term": "software developer",
    "cities": ["Berlin"],
    "country_indeed": "germany",
    "site_name": ["indeed"],
    "results_wanted": 15
  }
}
```

---

## Work Mode Filter and Per-Site Cap

### Request
```json
{
  "tool": "scrape_jobs_tool",
  "params": {
    "search_term": "software engineer",
    "cities": ["Berlin"],
    "site_name": ["stepstone", "xing"],
    "job_type": "contract",
    "work_mode": "on-site",
    "results_wanted": 1
  }
}
```

Notes:
- `results_wanted` is applied per selected site.
- If a selected site returns zero jobs, that site appears in `site_errors`.

---

## Helper Tools

### Get Supported Sites
```json
{
  "tool": "get_supported_sites",
  "params": {}
}
```

### Response
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

### Get Supported Countries
```json
{
  "tool": "get_supported_countries",
  "params": {}
}
```

### Response
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
  "popular_aliases": ["usa", "uk", "canada"]
}
```

### Get Job Search Tips
```json
{
  "tool": "get_job_search_tips",
  "params": {}
}
```

### Response
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
    "common_issues": [],
    "sample_search_strategies": [],
    "iterative_search_process": []
  }
}
```
