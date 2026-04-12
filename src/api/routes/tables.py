from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from api.models import (
    OperationResultResponse,
    PatchPayload,
    SelectResponse,
    SoftDeleteRequest,
    TableRowsRequest,
    operation_result_to_response,
)
from common.client import PostgrestClient
from common.config import load_config
from common.constants import DEFAULT_CONFLICT_KEYS
from repository.supabase import SupabaseRepository
from service.tables import soft_delete_jobs_final, soft_delete_jobs_raw

router = APIRouter(prefix="/db", tags=["tables"])

TABLE_CONFIG: dict[str, tuple[str, str]] = {
    "jobs-final": ("jobs_final", "job_id"),
    "jobs-raw": ("jobs_raw", "id"),
    "jobs-enriched": ("jobs_enriched", "job_id"),
    "shared-links": ("shared_links", "id"),
    "job-decisions": ("job_decisions", "id"),
    "job-approvals": ("job_approvals", "decision_id"),
    "job-metrics": ("job_metrics", "id"),
}

_SOFT_DELETE_TABLES: dict[str, str] = {
    "jobs_final": "job_id",
    "jobs_raw": "id",
}

_RESERVED_PARAMS: set[str] = {"columns", "limit", "offset", "order_by", "ascending"}


def _repo() -> SupabaseRepository:
    try:
        return SupabaseRepository(client=PostgrestClient(config=load_config()))
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _resolve_table(slug: str) -> tuple[str, str]:
    if slug not in TABLE_CONFIG:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown table '{slug}'. Available: {sorted(TABLE_CONFIG)}",
        )
    return TABLE_CONFIG[slug]


def _raise_if_failed(result: OperationResultResponse) -> None:
    if result.success:
        return
    status_code = result.status_code if isinstance(result.status_code, int) else 502
    raise HTTPException(status_code=status_code, detail=result.model_dump())


@router.get("/{table}", response_model=SelectResponse)
def list_rows(
    table: str,
    request: Request,
    columns: str = Query("*", description="Comma-separated column names."),
    limit: int = Query(50, ge=1, le=1000, description="Max rows to return."),
    offset: int = Query(0, ge=0, description="Number of rows to skip."),
    order_by: str | None = Query(None, description="Column to order by."),
    ascending: bool = Query(True, description="Sort ascending if true."),
) -> SelectResponse:
    db_table, _pk = _resolve_table(table)
    repo = _repo()

    filters: dict[str, Any] = {
        k: v for k, v in request.query_params.items() if k not in _RESERVED_PARAMS
    }

    try:
        result = repo.select_rows(
            table=db_table,
            columns=columns,
            filters=filters or None,
            limit=limit,
            offset=offset,
            order_by=order_by,
            ascending=ascending,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not result.success:
        status_code = result.status_code if isinstance(result.status_code, int) else 502
        raise HTTPException(status_code=status_code, detail=result.error or "Select failed")

    rows = result.data if isinstance(result.data, list) else []
    return SelectResponse(rows=rows, count=len(rows), table=db_table)


@router.get("/{table}/{record_id}", response_model=SelectResponse)
def get_record(table: str, record_id: str) -> SelectResponse:
    db_table, pk = _resolve_table(table)
    repo = _repo()

    try:
        result = repo.select_rows(
            table=db_table,
            filters={pk: record_id},
            limit=1,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not result.success:
        status_code = result.status_code if isinstance(result.status_code, int) else 502
        raise HTTPException(status_code=status_code, detail=result.error or "Select failed")

    rows = result.data if isinstance(result.data, list) else []
    if not rows:
        raise HTTPException(status_code=404, detail=f"Record '{record_id}' not found in {db_table}.")

    return SelectResponse(rows=rows, count=len(rows), table=db_table)


@router.post("/{table}", response_model=OperationResultResponse)
def create_rows(table: str, payload: TableRowsRequest) -> OperationResultResponse:
    db_table, _pk = _resolve_table(table)

    if db_table == "job_metrics":
        raise HTTPException(status_code=405, detail="job_metrics is a patch-only table. Use PATCH instead.")

    repo = _repo()

    try:
        if db_table in DEFAULT_CONFLICT_KEYS:
            result = repo.upsert_rows(table=db_table, rows=payload.rows)
        else:
            result = repo.insert_rows(table=db_table, rows=payload.rows)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = operation_result_to_response(result)
    _raise_if_failed(response)
    return response


@router.patch("/{table}/{record_id}", response_model=OperationResultResponse)
def update_record(table: str, record_id: str, payload: PatchPayload) -> OperationResultResponse:
    db_table, pk = _resolve_table(table)
    repo = _repo()

    try:
        result = repo.patch_rows(
            table=db_table,
            payload=payload.payload,
            filters={pk: record_id},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = operation_result_to_response(result)
    _raise_if_failed(response)
    return response


@router.delete("/{table}/{record_id}", response_model=OperationResultResponse)
def delete_record(table: str, record_id: str) -> OperationResultResponse:
    db_table, pk = _resolve_table(table)
    repo = _repo()

    try:
        result = repo.delete_rows(
            table=db_table,
            filters={pk: record_id},
            treat_404_as_success=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = operation_result_to_response(result)
    _raise_if_failed(response)
    return response


@router.delete("/{table}/{record_id}/soft", response_model=OperationResultResponse)
def soft_delete_record(table: str, record_id: str, payload: SoftDeleteRequest | None = None) -> OperationResultResponse:
    db_table, _pk = _resolve_table(table)

    if db_table not in _SOFT_DELETE_TABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Soft-delete is not supported for '{table}'. Only jobs-final and jobs-raw support it.",
        )

    hard_delete = payload.hard_delete if payload else False
    repo = _repo()

    try:
        if db_table == "jobs_final":
            result = soft_delete_jobs_final(repo=repo, job_id=record_id, hard_delete=hard_delete)
        else:
            result = soft_delete_jobs_raw(repo=repo, row_id=record_id, hard_delete=hard_delete)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = operation_result_to_response(result)
    _raise_if_failed(response)
    return response
