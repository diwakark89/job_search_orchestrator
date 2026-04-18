from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, RootModel

from common.client import OperationResult


class OperationResultResponse(BaseModel):
    success: bool
    status_code: int | None
    table: str
    operation: str
    row_count: int
    data: Any | None = None
    error: str | None = None


class SelectResponse(BaseModel):
    rows: list[dict[str, Any]]
    count: int | None = None
    table: str


class TableRowsRequest(BaseModel):
    rows: list[dict[str, Any]]


class PatchPayload(BaseModel):
    payload: dict[str, Any]


class SoftDeleteRequest(BaseModel):
    hard_delete: bool = False


class EnricherRunRequest(BaseModel):
    limit: int = Field(default=50, ge=1)
    dry_run: bool = False


class EnricherByIdRequestItem(BaseModel):
    id: str = Field(min_length=1)


class EnricherByIdsRequest(RootModel[list[EnricherByIdRequestItem]]):
    pass


class EnrichmentCountResponse(BaseModel):
    count: int
    ids: list[str]


class EnrichmentSummaryResponse(BaseModel):
    processed: EnrichmentCountResponse
    enriched: EnrichmentCountResponse
    skipped: EnrichmentCountResponse
    failed: EnrichmentCountResponse
    errors: list[str]
    copilot_batches_sent: int = 0
    database_batches_sent: int = 0
    database_rows_reported: int = 0


class HealthResponse(BaseModel):
    status: str
    supabase_configured: bool
    copilot_configured: bool


class TablesResponse(BaseModel):
    tables: list[str]
    default_conflict_keys: dict[str, str]


class StageResultResponse(BaseModel):
    stage: str
    success: bool
    stage_error: str | None = None
    processed: EnrichmentCountResponse
    skipped: EnrichmentCountResponse
    failed: EnrichmentCountResponse
    errors: list[str]


class PipelineResultResponse(BaseModel):
    stages: list[StageResultResponse]
    success: bool
    total_processed: int
    total_enriched: int
    total_failed: int


class PipelineRunRequest(BaseModel):
    jobs: list[dict[str, Any]]
    limit: int = Field(default=50, ge=1)
    dry_run: bool = False


class PipelineSubmitRequest(BaseModel):
    jobs: list[dict[str, Any]]


class PipelineSubmitResponse(BaseModel):
    submitted_row_count: int
    accepted: EnrichmentCountResponse
    queued: EnrichmentCountResponse
    rejected_row_indexes: list[int]
    errors: list[str]
    jobs_final_row_count: int
    shared_links_row_count: int


class PipelineStageIngestRequest(BaseModel):
    jobs: list[dict[str, Any]]


class PipelineStageEnrichRequest(BaseModel):
    limit: int = Field(default=50, ge=1)
    dry_run: bool = False


class MetricsResponse(BaseModel):
    status_counts: dict[str, int]
    total: int


def operation_result_to_response(result: OperationResult) -> OperationResultResponse:
    return OperationResultResponse(
        success=result.success,
        status_code=result.status_code,
        table=result.table,
        operation=result.operation,
        row_count=result.row_count,
        data=result.data,
        error=result.error,
    )
