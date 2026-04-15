from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from api.models import (
    EnricherByIdsRequest,
    EnricherRunRequest,
    EnrichmentCountResponse,
    EnrichmentSummaryResponse,
)
from common.client import PostgrestClient
from common.config import load_config
from job_enricher.client_copilot import CopilotClient
from job_enricher.config import load_copilot_config
from repository.supabase import SupabaseRepository
from service.enricher import enrich_jobs, enrich_jobs_by_ids

router = APIRouter(prefix="/enricher", tags=["enricher"])
logger = logging.getLogger("uvicorn.error")


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
        processed=EnrichmentCountResponse(count=summary.processed.count, ids=summary.processed.ids),
        enriched=EnrichmentCountResponse(count=summary.enriched.count, ids=summary.enriched.ids),
        skipped=EnrichmentCountResponse(count=summary.skipped.count, ids=summary.skipped.ids),
        failed=EnrichmentCountResponse(count=summary.failed.count, ids=summary.failed.ids),
        errors=summary.errors,
    )


@router.post("/by-ids", response_model=EnrichmentSummaryResponse)
def run_enricher_by_ids(
    payload: EnricherByIdsRequest,
    dry_run: bool = Query(default=False),
) -> EnrichmentSummaryResponse:
    requested_ids = [item.id for item in payload.root]
    logger.info(
        "POST /enricher/by-ids received ids_count=%s dry_run=%s",
        len(requested_ids),
        dry_run,
    )

    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        copilot_client = CopilotClient(config=load_copilot_config())
        summary = enrich_jobs_by_ids(
            repo=repo,
            copilot_client=copilot_client,
            ids=requested_ids,
            dry_run=dry_run,
        )
    except ValueError as exc:
        logger.warning("POST /enricher/by-ids validation_error=%s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("POST /enricher/by-ids runtime_error=%s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    logger.info(
        "POST /enricher/by-ids completed processed=%s enriched=%s skipped=%s failed=%s errors=%s",
        summary.processed.count,
        summary.enriched.count,
        summary.skipped.count,
        summary.failed.count,
        len(summary.errors),
    )

    return EnrichmentSummaryResponse(
        processed=EnrichmentCountResponse(count=summary.processed.count, ids=summary.processed.ids),
        enriched=EnrichmentCountResponse(count=summary.enriched.count, ids=summary.enriched.ids),
        skipped=EnrichmentCountResponse(count=summary.skipped.count, ids=summary.skipped.ids),
        failed=EnrichmentCountResponse(count=summary.failed.count, ids=summary.failed.ids),
        errors=summary.errors,
    )
