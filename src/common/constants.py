from __future__ import annotations

DEFAULT_CONFLICT_KEYS: dict[str, str] = {
    "jobs_final": "job_id",
    "jobs_raw": "job_url",
    "jobs_enriched": "job_id",
    "job_approvals": "decision_id",
    "shared_links": "url",
}

VALID_TABLES: set[str] = {
    "jobs_final",
    "shared_links",
    "jobs_raw",
    "jobs_enriched",
    "job_decisions",
    "job_approvals",
    "job_metrics",
}

JOB_STATUS_VALUES: set[str] = {
    "SCRAPED",
    "ENRICHED",
    "Saved",
    "Applied",
    "Interview",
    "Interviewing",
    "Offer",
    "Resume-Rejected",
    "Interview-Rejected",
    "SAVED",
    "APPLIED",
    "INTERVIEW",
    "INTERVIEWING",
    "OFFER",
    "RESUME_REJECTED",
    "INTERVIEW_REJECTED",
}

SHARED_LINK_SOURCES: set[str] = {
    "android-share-intent",
    "web-extension",
    "manual",
}

DECISION_VALUES: set[str] = {
    "AUTO_APPROVE",
    "REVIEW",
    "REJECT",
}

APPROVAL_VALUES: set[str] = {
    "APPROVED",
    "REJECTED",
    "PENDING",
}
