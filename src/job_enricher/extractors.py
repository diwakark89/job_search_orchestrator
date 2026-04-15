from __future__ import annotations

from typing import Any

from .client_copilot import CopilotClient, CopilotExtractionResult
from .constants import ALLOWED_EXPERIENCE_LEVELS, ALLOWED_REMOTE_TYPES, CANONICAL_TECH_STACK


def _normalize_tech(name: str) -> str:
    key = name.strip().lower()
    if key in CANONICAL_TECH_STACK:
        return CANONICAL_TECH_STACK[key]
    return name.strip()


def _normalize_tech_stack(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        tech = _normalize_tech(item)
        if not tech:
            continue
        marker = tech.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        normalized.append(tech)
    return normalized or None


def _normalize_enum(value: Any, allowed: set[str]) -> str:
    if not isinstance(value, str):
        return "Unknown"
    cleaned = value.strip().title()
    return cleaned if cleaned in allowed else "Unknown"


def build_enriched_row(row_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row_id,
        "tech_stack": _normalize_tech_stack(payload.get("tech_stack")),
        "experience_level": _normalize_enum(payload.get("experience_level"), ALLOWED_EXPERIENCE_LEVELS),
        "remote_type": _normalize_enum(payload.get("remote_type"), ALLOWED_REMOTE_TYPES),
    }


def enrich_job_row(copilot_client: CopilotClient, job_row: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    row_id = str(job_row.get("id", "")).strip()
    description = str(job_row.get("description", "")).strip()

    if not row_id:
        return None, "jobs_final row missing id"
    if not description:
        return None, "jobs_final row missing description"

    result: CopilotExtractionResult = copilot_client.extract_from_description(description)
    if not result.success or result.data is None:
        return None, result.error or "Unknown extraction error"

    try:
        return build_enriched_row(row_id=row_id, payload=result.data), None
    except Exception as exc:  # noqa: BLE001
        return None, f"Validation failed: {exc}"
