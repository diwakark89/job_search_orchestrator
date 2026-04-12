from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.models import HealthResponse, SelectResponse, TablesResponse
from common.client import PostgrestClient
from common.config import load_config
from common.constants import DEFAULT_CONFLICT_KEYS, VALID_TABLES
from job_enricher.config import load_copilot_config
from repository.supabase import SupabaseRepository
from service.queries import select_approvals_for_job, select_decisions_for_job
from typing import Any

router = APIRouter(tags=["system"])


def _is_supabase_ready() -> bool:
    try:
        load_config()
        return True
    except ValueError:
        return False


def _is_copilot_ready() -> bool:
    try:
        load_copilot_config()
        return True
    except ValueError:
        return False


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    supabase_ready = _is_supabase_ready()
    copilot_ready = _is_copilot_ready()
    status = "ok" if supabase_ready and copilot_ready else "degraded"

    return HealthResponse(
        status=status,
        supabase_configured=supabase_ready,
        copilot_configured=copilot_ready,
    )


@router.get("/tables", response_model=TablesResponse)
def list_tables() -> TablesResponse:
    return TablesResponse(
        tables=sorted(VALID_TABLES),
        default_conflict_keys=DEFAULT_CONFLICT_KEYS,
    )


@router.get("/diagnostics/jobs/{job_id}/decisions", response_model=SelectResponse)
def get_job_decisions(job_id: str) -> SelectResponse:
    """Fetch all decisions for a specific job (audit trail)."""
    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        result = select_decisions_for_job(repo=repo, job_id=job_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not result.success:
        status_code = result.status_code if isinstance(result.status_code, int) else 502
        raise HTTPException(status_code=status_code, detail=result.error or "Query failed")

    rows = result.data if isinstance(result.data, list) else []
    return SelectResponse(rows=rows, count=len(rows), table="job_decisions")


@router.get("/diagnostics/jobs/{job_id}/approvals", response_model=SelectResponse)
def get_job_approvals(job_id: str) -> SelectResponse:
    """Fetch all approvals for a specific job (approval history)."""
    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        result = select_approvals_for_job(repo=repo, job_id=job_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not result.success:
        status_code = result.status_code if isinstance(result.status_code, int) else 502
        raise HTTPException(status_code=status_code, detail=result.error or "Query failed")

    rows = result.data if isinstance(result.data, list) else []
    return SelectResponse(rows=rows, count=len(rows), table="job_approvals")
