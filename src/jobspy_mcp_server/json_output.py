from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, TypedDict

import pandas as pd

from jobspy_mcp_server.jobspy_scrapers.model import normalize_description_source
from jobspy_mcp_server.jobspy_scrapers.util import (
    extract_job_type,
    normalize_job_type_value,
    normalize_work_mode,
)


class NormalizedJob(TypedDict):
    id: str
    company_name: str | None
    role_title: str | None
    description: str | None
    description_source: str | None
    job_type: str | None
    job_url: str | None
    location: str | None
    work_mode: str | None
    language: str
    source_platform: str | None
    scraped_at: str
    content_hash: str


class ErrorDetail(TypedDict):
    code: str
    message: str


def build_jobs_success_envelope(
    jobs: list[dict[str, Any]],
    *,
    site_errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "jobs": jobs, "error": None}
    if site_errors:
        payload["site_errors"] = site_errors
        payload["site_error_summary"] = _build_site_error_summary(site_errors)
    return payload


def _build_site_error_summary(site_errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in site_errors:
        site = str(item.get("site") or "unknown")
        message = str(item.get("message") or "unknown error")
        city = item.get("city")
        key = (site, message)
        if key not in grouped:
            grouped[key] = {
                "site": site,
                "message": message,
                "count": 0,
                "cities": [],
            }
        grouped[key]["count"] += 1
        if city and city not in grouped[key]["cities"]:
            grouped[key]["cities"].append(city)

    summary = list(grouped.values())
    summary.sort(key=lambda entry: (entry["site"], -entry["count"]))
    return summary


def build_data_success_envelope(**data: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "error": None}
    payload.update(data)
    return payload


def build_error_envelope(code: str, message: str, **data: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": {"code": code, "message": message},
    }
    payload.update(data)
    return payload


def serialize_json_payload(payload: Any, *, indent: int | None = None) -> str:
    return json.dumps(payload, indent=indent, default=str)


def build_jobs_json_payload(jobs_df: pd.DataFrame, scraped_at: datetime | None = None) -> list[NormalizedJob]:
    """Convert a JobSpy DataFrame into the strict normalized JSON schema."""
    timestamp = (scraped_at or datetime.now(timezone.utc)).isoformat()
    normalized_jobs: list[NormalizedJob] = []

    for _, job in jobs_df.iterrows():
        source_platform = _optional_text(job.get("site"))
        job_url = _optional_text(job.get("job_url"))
        company_name = _optional_text(job.get("company"))
        role_title = _optional_text(job.get("title"))
        location = _optional_text(job.get("location"))
        description = _optional_text(job.get("description"))
        description_source = normalize_description_source(job.get("description_source"))
        job_type = _normalize_job_type_output(job.get("job_type"), description)
        work_mode = _normalize_work_mode_output(
            explicit_work_mode=job.get("work_mode"),
            description=description,
            role_title=role_title,
            location=location,
        )

        normalized_jobs.append(
            {
                "id": str(uuid.uuid4()),
                "company_name": company_name,
                "role_title": role_title,
                "description": description,
                "description_source": description_source,
                "job_type": job_type,
                "job_url": job_url,
                "location": location,
                "work_mode": work_mode,
                "language": "English",
                "source_platform": source_platform,
                "scraped_at": timestamp,
                "content_hash": _build_content_hash(role_title, company_name, location),
            }
        )

    return normalized_jobs


def _build_content_hash(role_title: str | None, company_name: str | None, location: str | None) -> str:
    fingerprint = "|".join(
        _hash_text(value) for value in (role_title, company_name, location)
    )
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


def _optional_text(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _hash_text(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value).strip().lower()


def _normalize_job_type_output(job_type: object, description: str | None) -> str | None:
    normalized = normalize_job_type_value(_optional_text(job_type))
    if normalized is not None:
        return normalized

    inferred_types = extract_job_type(description or "")
    if not inferred_types:
        return None
    for inferred_type in inferred_types:
        mapped = normalize_job_type_value(inferred_type.value[0])
        if mapped is not None:
            return mapped
    return None


def _normalize_work_mode_output(
    *,
    explicit_work_mode: object,
    description: str | None,
    role_title: str | None,
    location: str | None,
) -> str | None:
    for candidate in (
        _optional_text(explicit_work_mode),
        description,
        role_title,
        location,
    ):
        normalized = normalize_work_mode(candidate)
        if normalized is not None:
            return normalized
    return None