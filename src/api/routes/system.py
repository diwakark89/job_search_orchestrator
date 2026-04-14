from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.models import HealthResponse, TablesResponse
from common.constants import DEFAULT_CONFLICT_KEYS, VALID_TABLES
from job_enricher.config import load_copilot_config
from common.config import load_config

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
