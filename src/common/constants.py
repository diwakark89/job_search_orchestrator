from __future__ import annotations

DEFAULT_CONFLICT_KEYS: dict[str, str] = {
    "jobs_final": "job_id",
    "shared_links": "url",
}

VALID_TABLES: set[str] = {
    "jobs_final",
    "shared_links",
}

JOB_STATUS_VALUES: set[str] = {
    "SCRAPED",
    "ENRICHED",
    "SAVED",
    "APPLIED",
    "INTERVIEW",
    "INTERVIEWING",
    "OFFER",
    "RESUME_REJECTED",
    "INTERVIEW_REJECTED",
}

# Maps common display-form aliases → canonical uppercase value.
# Used by the validator to accept case-insensitive input.
_JOB_STATUS_ALIASES: dict[str, str] = {
    "saved": "SAVED",
    "applied": "APPLIED",
    "interview": "INTERVIEW",
    "interviewing": "INTERVIEWING",
    "offer": "OFFER",
    "resume-rejected": "RESUME_REJECTED",
    "interview-rejected": "INTERVIEW_REJECTED",
}


def normalize_job_status(value: str) -> str:
    """Return the canonical uppercase job_status, or *value* unchanged if unknown."""
    upper = value.upper().replace("-", "_")
    if upper in JOB_STATUS_VALUES:
        return upper
    alias = _JOB_STATUS_ALIASES.get(value.lower())
    if alias is not None:
        return alias
    return value

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
