from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from .constants import (
    APPROVAL_VALUES,
    AUTOMATION_SESSION_STATUS_VALUES,
    AUTOMATION_TYPE_VALUES,
    DECISION_VALUES,
    JOB_STATUS_VALUES,
    JOB_TYPE_VALUES,
    WORK_MODE_VALUES,
    normalize_job_status,
    normalize_job_type,
    normalize_work_mode,
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
    match_score: float | int | None = None
    saved_at: str | int | float | datetime | None = None
    job_status: str | None = "SAVED"
    is_deleted: bool = False
    modified_at: str | int | float | datetime | None = None
    language: str | None = "English"
    content_hash: str | None = None
    location: str | None = None
    source_platform: str | None = None
    job_type: str | None = None
    work_mode: str | None = None
    tech_stack: list[str] | None = None
    experience_level: str | None = None
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

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = normalize_job_type(value)
        if normalized not in JOB_TYPE_VALUES:
            raise ValueError(f"Invalid job_type '{value}'.")
        return normalized

    @field_validator("work_mode")
    @classmethod
    def validate_work_mode(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = normalize_work_mode(value)
        if normalized not in WORK_MODE_VALUES:
            raise ValueError(f"Invalid work_mode '{value}'.")
        return normalized

    @field_validator("user_action")
    @classmethod
    def validate_user_action(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in APPROVAL_VALUES:
            raise ValueError(f"Invalid user_action '{value}'.")
        return value


class AutomationSessionsRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    job_id: str
    automation_type: str
    session_status: str = "RUNNING"
    current_step: str | None = None
    browser_state_path: str | None = None
    screenshot_path: str | None = None
    last_error: str | None = None
    retry_count: int = 0
    started_at: str | int | float | datetime | None = None
    updated_at: str | int | float | datetime | None = None

    @field_validator("automation_type")
    @classmethod
    def validate_automation_type(cls, value: str) -> str:
        if value not in AUTOMATION_TYPE_VALUES:
            raise ValueError(f"Invalid automation_type '{value}'.")
        return value

    @field_validator("session_status")
    @classmethod
    def validate_session_status(cls, value: str) -> str:
        if value not in AUTOMATION_SESSION_STATUS_VALUES:
            raise ValueError(f"Invalid session_status '{value}'.")
        return value

    @field_validator("retry_count")
    @classmethod
    def validate_retry_count(cls, value: int) -> int:
        if value < 0:
            raise ValueError("retry_count must be >= 0.")
        return value


def _validate_rows(
    rows: list[dict[str, Any]],
    model: type[BaseModel],
    timestamp_fields: tuple[str, ...],
    preserve_fields: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        validated = model.model_validate(row)
        excluded_fields = {"id"} - set(preserve_fields)
        normalized_row = normalize_timestamp_fields(
            validated.model_dump(exclude_none=True, exclude=excluded_fields),
            timestamp_fields,
        )
        normalized.append(normalized_row)
    return normalized


def validate_jobs_final_rows(
    rows: list[dict[str, Any]],
    preserve_fields: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    return _validate_rows(rows, JobsFinalRow, ("saved_at", "modified_at", "approved_at"), preserve_fields)


def validate_automation_sessions_rows(
    rows: list[dict[str, Any]],
    preserve_fields: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    return _validate_rows(
        rows,
        AutomationSessionsRow,
        ("started_at", "updated_at"),
        preserve_fields,
    )
