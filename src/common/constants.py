from __future__ import annotations

DEFAULT_CONFLICT_KEYS: dict[str, str] = {
    "jobs_final": "id",
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

JOB_TYPE_VALUES: set[str] = {
    "fulltime",
    "parttime",
    "internship",
    "contract",
    "temporary",
    "other",
}

_JOB_TYPE_ALIASES: dict[str, str] = {
    "full-time": "fulltime",
    "full time": "fulltime",
    "part-time": "parttime",
    "part time": "parttime",
    "intern": "internship",
}


def normalize_job_type(value: str) -> str:
    normalized = value.strip().lower()
    compact = " ".join(normalized.split())
    if compact in JOB_TYPE_VALUES:
        return compact
    return _JOB_TYPE_ALIASES.get(compact, "other")


WORK_MODE_VALUES: set[str] = {
    "remote",
    "hybrid",
    "on-site",
    "other",
}

_WORK_MODE_ALIASES: dict[str, str] = {
    "onsite": "on-site",
    "on site": "on-site",
}


def normalize_work_mode(value: str) -> str:
    normalized = value.strip().lower()
    compact = " ".join(normalized.split())
    if compact in WORK_MODE_VALUES:
        return compact
    return _WORK_MODE_ALIASES.get(compact, "other")

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
