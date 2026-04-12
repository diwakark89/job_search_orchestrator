from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .constants import (
    APPROVAL_VALUES,
    DECISION_VALUES,
    JOB_STATUS_VALUES,
    SHARED_LINK_SOURCES,
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

    job_id: str
    company_name: str | None = None
    role_title: str | None = None
    job_url: str | None = None
    description: str | None = None
    match_score: float | int | None = 90
    tags: list[str] | None = None
    saved_at: str | int | float | datetime | None = None
    job_status: str | None = "Saved"
    is_deleted: bool = False
    modified_at: str | int | float | datetime | None = None
    language: str | None = "English"

    @field_validator("job_status")
    @classmethod
    def validate_job_status(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in JOB_STATUS_VALUES:
            raise ValueError(f"Invalid job_status '{value}'.")
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


class JobsRawRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    company_name: str
    role_title: str
    description: str | None = None
    job_url: str
    job_status: str | None = "SCRAPED"
    language: str | None = "English"
    content_hash: str | None = None
    external_id: str | None = None
    source_platform: str | None = None
    location: str | None = None
    created_at: str | int | float | datetime | None = None
    modified_at: str | int | float | datetime | None = None
    is_deleted: bool = False

    @field_validator("job_status")
    @classmethod
    def validate_job_status(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in JOB_STATUS_VALUES:
            raise ValueError(f"Invalid job_status '{value}'.")
        return value


class JobsEnrichedRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    tech_stack: list[str] | None = None
    experience_level: str | None = None
    remote_type: str | None = None
    visa_sponsorship: bool | None = None
    english_friendly: bool | None = None
    created_at: str | int | float | datetime | None = None


class JobDecisionRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    match_score: float | int | None = None
    decision: str
    reason: str | None = None
    confidence: float | int | None = None
    created_at: str | int | float | datetime | None = None

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, value: str) -> str:
        if value not in DECISION_VALUES:
            raise ValueError(f"Invalid decision '{value}'.")
        return value


class JobApprovalRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    decision_id: str
    user_action: str
    approved_at: str | int | float | datetime | None = None
    created_at: str | int | float | datetime | None = None

    @field_validator("user_action")
    @classmethod
    def validate_user_action(cls, value: str) -> str:
        if value not in APPROVAL_VALUES:
            raise ValueError(f"Invalid user_action '{value}'.")
        return value


class JobMetricsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_scraped: int | None = Field(default=None, ge=0)
    total_approved: int | None = Field(default=None, ge=0)
    total_rejected: int | None = Field(default=None, ge=0)
    updated_at: str | int | float | datetime | None = None


def _validate_rows(rows: list[dict[str, Any]], model: type[BaseModel], timestamp_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        validated = model.model_validate(row)
        normalized_row = normalize_timestamp_fields(validated.model_dump(exclude_none=True), timestamp_fields)
        normalized.append(normalized_row)
    return normalized


def validate_jobs_final_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _validate_rows(rows, JobsFinalRow, ("saved_at", "modified_at"))


def validate_shared_links_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _validate_rows(rows, SharedLinkRow, ())


def validate_jobs_raw_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _validate_rows(rows, JobsRawRow, ("created_at", "modified_at"))


def validate_jobs_enriched_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _validate_rows(rows, JobsEnrichedRow, ("created_at",))


def validate_job_decisions_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _validate_rows(rows, JobDecisionRow, ("created_at",))


def validate_job_approvals_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _validate_rows(rows, JobApprovalRow, ("approved_at", "created_at"))


def validate_job_metrics_patch(payload: dict[str, Any]) -> dict[str, Any]:
    validated = JobMetricsPatch.model_validate(payload)
    return normalize_timestamp_fields(validated.model_dump(exclude_none=True), ("updated_at",))
