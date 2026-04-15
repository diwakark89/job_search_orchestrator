from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from .constants import (
    APPROVAL_VALUES,
    DECISION_VALUES,
    JOB_STATUS_VALUES,
    SHARED_LINK_SOURCES,
    normalize_job_status,
)


def _to_iso8601_utc(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return value


def normalize_timestamp_fields(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    output = dict(row)
    for field in fields:
        if field in output and output[field] is not None:
            output[field] = _to_iso8601_utc(output[field])
    return output


class JobsFinalRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    company_name: str | None = None
    role_title: str | None = None
    job_url: str | None = None
    description: str | None = None
    match_score: float | int | None = 90
    tags: list[str] | None = None
    saved_at: str | int | float | datetime | None = None
    job_status: str | None = "SAVED"
    is_deleted: bool = False
    modified_at: str | int | float | datetime | None = None
    language: str | None = "English"
    content_hash: str | None = None
    external_id: str | None = None
    location: str | None = None
    source_platform: str | None = None
    tech_stack: list[str] | None = None
    experience_level: str | None = None
    remote_type: str | None = None
    decision: str | None = None
    reason: str | None = None
    confidence: float | int | None = None
    user_action: str | None = None
    approved_at: str | int | float | datetime | None = None

    @field_validator("job_status")
    @classmethod
    def validate_job_status(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = normalize_job_status(value)
        if normalized not in JOB_STATUS_VALUES:
            raise ValueError(f"Invalid job_status '{value}'.")
        return normalized

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in DECISION_VALUES:
            raise ValueError(f"Invalid decision '{value}'.")
        return value

    @field_validator("user_action")
    @classmethod
    def validate_user_action(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in APPROVAL_VALUES:
            raise ValueError(f"Invalid user_action '{value}'.")
        return value


class SharedLinkRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    source: str = "android-share-intent"

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        if value not in SHARED_LINK_SOURCES:
            raise ValueError(f"Invalid source '{value}'.")
        return value


def _validate_rows(rows: list[dict[str, Any]], model: type[BaseModel], timestamp_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        validated = model.model_validate(row)
        normalized_row = normalize_timestamp_fields(validated.model_dump(exclude_none=True, exclude={"id"}), timestamp_fields)
        normalized.append(normalized_row)
    return normalized


def validate_jobs_final_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _validate_rows(rows, JobsFinalRow, ("saved_at", "modified_at", "approved_at"))


def validate_shared_links_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _validate_rows(rows, SharedLinkRow, ())
