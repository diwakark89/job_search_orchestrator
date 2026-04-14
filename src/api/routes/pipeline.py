from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException

from api.models import (
    EnrichmentCountResponse,
    EnrichmentSummaryResponse,
    PipelineResultResponse,
    PipelineRunRequest,
    PipelineStageEnrichRequest,
    PipelineStageFinalizeRequest,
    PipelineStageMetricsRequest,
    PipelineStageRawRequest,
    StageResultResponse,
)
from common.client import PostgrestClient
from common.config import load_config
from job_enricher.client_copilot import CopilotClient
from job_enricher.config import load_copilot_config
from repository.supabase import SupabaseRepository
from service.pipeline import (
    run_pipeline,
    run_stage_enriched_detailed,
    run_stage_finalize_detailed,
    run_stage_metrics,
    run_stage_raw,
)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


def _extract_failed_ids(errors: list[str]) -> list[str]:
    failed_ids: list[str] = []

    def _add_id(identifier: str) -> None:
        if identifier and identifier not in failed_ids:
            failed_ids.append(identifier)

    for message in errors:
        # Stage raw validation shape: row[0]: ...
        for match in re.findall(r"row\[(\d+)\]", message):
            _add_id(f"row[{match}]")

        # Enricher/finalize per-row errors: job_id=<uuid>: ... or id=<uuid>: ...
        for match in re.findall(r"\bjob_id=([^:\s,]+)", message):
            _add_id(match)
        for match in re.findall(r"\bid=([^:\s,]+)", message):
            _add_id(match)

        # Batch verification errors: ... ids: id-1, id-2
        list_match = re.search(r"ids:\s*([^\n]+)", message)
        if list_match:
            for item in list_match.group(1).split(","):
                _add_id(item.strip())

    return failed_ids


def _stage_to_response(stage) -> StageResultResponse:
    failed_ids = _extract_failed_ids(stage.errors)
    stage_error = stage.errors[0] if stage.errors else None
    return StageResultResponse(
        stage=stage.stage,
        success=stage.success,
        stage_error=stage_error,
        processed=EnrichmentCountResponse(count=stage.processed, ids=[]),
        skipped=EnrichmentCountResponse(count=0, ids=[]),
        failed=EnrichmentCountResponse(count=len(stage.errors), ids=failed_ids),
        errors=stage.errors,
    )


def _stage_to_bucket_response(stage) -> EnrichmentSummaryResponse:
    return EnrichmentSummaryResponse(
        processed=EnrichmentCountResponse(count=stage.processed, ids=[]),
        skipped=EnrichmentCountResponse(count=0, ids=[]),
        failed=EnrichmentCountResponse(count=len(stage.errors), ids=[]),
        errors=stage.errors,
    )


@router.post("/run", response_model=PipelineResultResponse)
def pipeline_run(payload: PipelineRunRequest) -> PipelineResultResponse:
    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        copilot_client = CopilotClient(config=load_copilot_config())
        result = run_pipeline(
            repo=repo,
            copilot_client=copilot_client,
            rows=payload.rows,
            limit=payload.limit,
            dry_run=payload.dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return PipelineResultResponse(
        stages=[_stage_to_response(s) for s in result.stages],
        success=result.success,
        total_processed=result.total_processed,
        total_enriched=result.total_enriched,
        total_failed=result.total_failed,
    )


@router.post("/stage/raw", response_model=EnrichmentSummaryResponse)
def pipeline_stage_raw(payload: PipelineStageRawRequest) -> EnrichmentSummaryResponse:
    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        result = run_stage_raw(repo=repo, rows=payload.rows)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return _stage_to_bucket_response(result)


@router.post("/stage/enriched", response_model=EnrichmentSummaryResponse)
def pipeline_stage_enriched(payload: PipelineStageEnrichRequest) -> EnrichmentSummaryResponse:
    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        copilot_client = CopilotClient(config=load_copilot_config())
        result = run_stage_enriched_detailed(
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
        processed=EnrichmentCountResponse(count=result.processed.count, ids=result.processed.ids),
        skipped=EnrichmentCountResponse(count=result.skipped.count, ids=result.skipped.ids),
        failed=EnrichmentCountResponse(count=result.failed.count, ids=result.failed.ids),
        errors=result.errors,
    )


@router.post("/stage/metrics", response_model=EnrichmentSummaryResponse)
def pipeline_stage_metrics(payload: PipelineStageMetricsRequest) -> EnrichmentSummaryResponse:
    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        result = run_stage_metrics(
            repo=repo,
            scraped_count=payload.scraped_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return _stage_to_bucket_response(result)


@router.post("/stage/finalize", response_model=EnrichmentSummaryResponse)
def pipeline_stage_finalize(payload: PipelineStageFinalizeRequest) -> EnrichmentSummaryResponse:
    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        result = run_stage_finalize_detailed(
            repo=repo,
            limit=payload.limit,
            dry_run=payload.dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return EnrichmentSummaryResponse(
        processed=EnrichmentCountResponse(count=result.processed.count, ids=result.processed.ids),
        skipped=EnrichmentCountResponse(count=result.skipped.count, ids=result.skipped.ids),
        failed=EnrichmentCountResponse(count=result.failed.count, ids=result.failed.ids),
        errors=result.errors,
    )
