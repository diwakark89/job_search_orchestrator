from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from common.constants import normalize_work_mode

from .client_copilot import (
    CopilotBatchExtractionInput,
    CopilotBatchExtractionResult,
    CopilotClient,
    CopilotExtractionResult,
)
from .constants import ALLOWED_EXPERIENCE_LEVELS, CANONICAL_TECH_STACK


class SupportsBatchJobExtraction(Protocol):
    def extract_from_description(self, description: str) -> CopilotExtractionResult: ...

    def extract_from_descriptions(
        self,
        items: list[CopilotBatchExtractionInput],
    ) -> list[CopilotBatchExtractionResult]: ...


@dataclass
class JobRowEnrichmentResult:
    row_id: str
    enriched_row: dict[str, Any] | None = None
    error: str | None = None
    skipped: bool = False


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


def _normalize_work_mode_value(value: Any) -> str:
    if not isinstance(value, str):
        return "other"
    return normalize_work_mode(value)


def build_enriched_row(row_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row_id,
        "tech_stack": _normalize_tech_stack(payload.get("tech_stack")),
        "experience_level": _normalize_enum(payload.get("experience_level"), ALLOWED_EXPERIENCE_LEVELS),
        "work_mode": _normalize_work_mode_value(payload.get("work_mode")),
    }


def enrich_job_row(
    copilot_client: SupportsBatchJobExtraction,
    job_row: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
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


def enrich_job_rows(
    copilot_client: SupportsBatchJobExtraction,
    job_rows: list[dict[str, Any]],
) -> list[JobRowEnrichmentResult]:
    results: list[JobRowEnrichmentResult] = []
    batch_inputs: list[CopilotBatchExtractionInput] = []

    for job_row in job_rows:
        row_id = str(job_row.get("id", "")).strip()
        description = str(job_row.get("description", "")).strip()

        if not row_id:
            results.append(JobRowEnrichmentResult(row_id="", error="jobs_final row missing id"))
            continue
        if not description:
            results.append(
                JobRowEnrichmentResult(
                    row_id=row_id,
                    error="jobs_final row missing description",
                    skipped=True,
                )
            )
            continue

        batch_inputs.append(CopilotBatchExtractionInput(row_id=row_id, description=description))

    batch_results = copilot_client.extract_from_descriptions(batch_inputs)
    for batch_result in batch_results:
        if not batch_result.success or batch_result.data is None:
            results.append(
                JobRowEnrichmentResult(
                    row_id=batch_result.row_id,
                    error=batch_result.error or "Unknown extraction error",
                )
            )
            continue

        try:
            enriched_row = build_enriched_row(row_id=batch_result.row_id, payload=batch_result.data)
        except Exception as exc:  # noqa: BLE001
            results.append(
                JobRowEnrichmentResult(
                    row_id=batch_result.row_id,
                    error=f"Validation failed: {exc}",
                )
            )
            continue

        results.append(JobRowEnrichmentResult(row_id=batch_result.row_id, enriched_row=enriched_row))

    return results
