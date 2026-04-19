"""Ingest stage: validate raw rows (with scrape-origin mapping) and upsert
into ``jobs_final`` with status ``SCRAPED``.
"""
from __future__ import annotations

from typing import Any

from common.validators import JobsFinalRow, normalize_timestamp_fields
from pipeline.models import StageResult
from repository.supabase import SupabaseRepository

from ..mappers.scrape_to_jobs_final import map_scraped_job_to_jobs_final

_INGEST_TIMESTAMP_FIELDS = ("created_at", "modified_at")


def _validate_and_map_ingest_row(
    row: dict[str, Any],
    idx: int,
) -> tuple[dict[str, Any] | None, str | None]:
    """Apply scrape→jobs_final mapping (if needed), validate, normalise.

    Returns ``(normalised_row, None)`` on success or ``(None, error_message)``
    on validation failure. Pure function — no I/O, easy to unit-test.
    """
    try:
        candidate = dict(row)

        # Apply scrape-to-persistence mapper when row originates from a scrape
        # payload (signalled by 'scraped_at' or 'description_source').
        if "scraped_at" in candidate or "description_source" in candidate:
            candidate = map_scraped_job_to_jobs_final(candidate)

        if "job_status" not in candidate:
            candidate["job_status"] = "SCRAPED"

        # Strict schema gate: reject rows missing job_url before upsert.
        job_url = str(candidate.get("job_url") or "").strip()
        if not job_url:
            raise ValueError("job_url is required and must not be empty.")
        candidate["job_url"] = job_url

        validated = JobsFinalRow.model_validate(candidate)
        normalised = normalize_timestamp_fields(
            validated.model_dump(exclude_none=True),
            _INGEST_TIMESTAMP_FIELDS,
        )
        return normalised, None
    except Exception as exc:  # noqa: BLE001
        return None, f"row[{idx}]: {exc}"


def run_stage_ingest(repo: SupabaseRepository, rows: list[dict[str, Any]]) -> StageResult:
    valid_rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for idx, row in enumerate(rows):
        normalised, error = _validate_and_map_ingest_row(row, idx)
        if error is not None:
            errors.append(error)
        elif normalised is not None:
            valid_rows.append(normalised)

    if not valid_rows:
        return StageResult(stage="ingest", success=False, processed=0, errors=errors)

    result = repo.upsert_rows(table="jobs_final", rows=valid_rows, on_conflict="job_url")
    if not result.success:
        errors.append(result.error or "upsert jobs_final (ingest) failed")
        return StageResult(stage="ingest", success=False, processed=0, errors=errors)

    return StageResult(stage="ingest", success=True, processed=len(valid_rows), errors=errors)


__all__ = ["_validate_and_map_ingest_row", "run_stage_ingest"]
