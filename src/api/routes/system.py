from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.models import HealthResponse, TablesResponse
from common.client import PostgrestClient
from common.config import load_config
from common.constants import DEFAULT_CONFLICT_KEYS, VALID_TABLES
from job_enricher.config import load_copilot_config

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


def _supabase_reachable() -> bool:
    """Attempt a lightweight live probe against the Supabase REST endpoint.

    Returns ``True`` only when the REST endpoint responds successfully.
    On any error (network, auth, timeout) returns ``False`` so the health
    endpoint degrades gracefully rather than raising.
    """
    try:
        config = load_config()
        client = PostgrestClient(config=config)
        result = client.select("jobs_final", columns="id", limit=1, filters={})
        return result.success
    except Exception:  # noqa: BLE001
        return False


@router.get("/health", response_model=HealthResponse)
def health(deep: bool = False) -> HealthResponse:
    """Shallow health probe (default) or deep connectivity probe.

    Args:
        deep: When ``True``, performs a live round-trip to Supabase.
              Use with care — this adds network latency and costs one REST call.
    """
    supabase_ready = _is_supabase_ready()
    copilot_ready = _is_copilot_ready()

    if deep and supabase_ready:
        supabase_ready = _supabase_reachable()

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

