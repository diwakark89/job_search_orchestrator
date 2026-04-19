from __future__ import annotations

"""Pure mapping functions from scrape output to JobsFinalRow-compatible dicts.

These functions are intentionally free of side effects: no I/O, no imports of
repository or service modules.  Tests can exercise them in isolation.

Mapping contract
----------------
Source schema  (NormalizedJob-compatible dict from scraping.output):
    id              – scrape-generated UUID (dropped; DB assigns its own PK)
    company_name    – str | None
    role_title      – str | None
    description     – str | None
    description_source – str | None  (not persisted; metadata only)
    job_type        – str | None
    job_url         – str | None  (REQUIRED for upsert conflict resolution)
    location        – str | None
    work_mode       – str | None
    language        – str
    source_platform – str | None
    scraped_at      – ISO-8601 UTC string  → saved_at in JobsFinalRow
    content_hash    – str | None

Target schema (JobsFinalRow-compatible dict):
    company_name    – passed through
    role_title      – passed through
    description     – passed through
    job_type        – passed through
    job_url         – passed through
    location        – passed through
    work_mode       – passed through
    language        – passed through
    source_platform – passed through
    content_hash    – passed through
    saved_at        – mapped from scraped_at
    job_status      – hardcoded "SCRAPED"
    is_deleted      – hardcoded False

Fields absent in the scrape payload (match_score, tech_stack, experience_level,
decision, reason, confidence, modified_at, approved_at) are left out; the
validator layer fills them in with None / defaults.
"""

from typing import Any


def map_scraped_job_to_jobs_final(scraped_job: dict[str, Any]) -> dict[str, Any]:
    """Map a single normalised scrape-output dict to a ``JobsFinalRow``-compatible dict.

    The caller is responsible for validating the result with ``JobsFinalRow.model_validate``
    before passing it to the repository.

    Args:
        scraped_job: A dict produced by ``scraping.output.build_jobs_json_payload``
                     or the ``JobspyAdapter.search`` return value.

    Returns:
        A dict suitable for ``JobsFinalRow.model_validate``.

    Raises:
        ValueError: If ``job_url`` is missing or empty (required for upsert key).
    """
    job_url = str(scraped_job.get("job_url") or "").strip()
    if not job_url:
        raise ValueError("scraped job is missing required field 'job_url'.")

    return {
        # Identity / display
        "company_name": scraped_job.get("company_name"),
        "role_title": scraped_job.get("role_title"),
        "job_url": job_url,
        "description": scraped_job.get("description"),
        # Classification
        "job_type": scraped_job.get("job_type"),
        "work_mode": scraped_job.get("work_mode"),
        # Location & platform
        "location": scraped_job.get("location"),
        "source_platform": scraped_job.get("source_platform"),
        "language": scraped_job.get("language", "English"),
        # Integrity
        "content_hash": scraped_job.get("content_hash"),
        # Timestamps: scraped_at becomes saved_at for the persistence layer
        "saved_at": scraped_job.get("scraped_at"),
        # Pipeline status
        "job_status": "SCRAPED",
        "is_deleted": False,
    }


def map_scraped_jobs_to_jobs_final(
    scraped_jobs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[tuple[int, str]]]:
    """Map a list of scraped jobs, collecting per-row errors without aborting.

    Args:
        scraped_jobs: List of normalised scrape-output dicts.

    Returns:
        A 2-tuple of:
        - ``mapped``: successfully mapped rows as JobsFinalRow-compatible dicts.
        - ``errors``: list of ``(original_index, error_message)`` for rows that failed.
    """
    mapped: list[dict[str, Any]] = []
    errors: list[tuple[int, str]] = []

    for idx, job in enumerate(scraped_jobs):
        try:
            mapped.append(map_scraped_job_to_jobs_final(job))
        except ValueError as exc:
            errors.append((idx, str(exc)))

    return mapped, errors
