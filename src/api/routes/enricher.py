from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.models import EnricherRunRequest, EnrichmentSummaryResponse
from common.client import PostgrestClient
from common.config import load_config
from job_enricher.client_copilot import CopilotClient
from job_enricher.config import load_copilot_config
from repository.supabase import SupabaseRepository
from service.enricher import enrich_jobs

router = APIRouter(prefix="/enricher", tags=["enricher"])


@router.post("/run", response_model=EnrichmentSummaryResponse)
def run_enricher(payload: EnricherRunRequest) -> EnrichmentSummaryResponse:
    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        copilot_client = CopilotClient(config=load_copilot_config())
        summary = enrich_jobs(
            repo=repo,
            copilot_client=copilot_client,
            limit=payload.limit,
            dry_run=payload.dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return EnrichmentSummaryResponse(
        processed=summary.processed,
        enriched=summary.enriched,
        skipped=summary.skipped,
        failed=summary.failed,
        errors=summary.errors,
    )
