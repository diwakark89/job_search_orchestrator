from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.models import (
    PipelineResultResponse,
    PipelineRunRequest,
    PipelineStageEnrichRequest,
    PipelineStageMetricsRequest,
    PipelineStageRawRequest,
    StageResultResponse,
)
from common.client import PostgrestClient
from common.config import load_config
from job_enricher.client_copilot import CopilotClient
from job_enricher.config import load_copilot_config
from repository.supabase import SupabaseRepository
from service.pipeline import run_pipeline, run_stage_enriched, run_stage_metrics, run_stage_raw

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


def _stage_to_response(stage) -> StageResultResponse:
    return StageResultResponse(
        stage=stage.stage,
        success=stage.success,
        processed=stage.processed,
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


@router.post("/stage/raw", response_model=StageResultResponse)
def pipeline_stage_raw(payload: PipelineStageRawRequest) -> StageResultResponse:
    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        result = run_stage_raw(repo=repo, rows=payload.rows)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return _stage_to_response(result)


@router.post("/stage/enriched", response_model=StageResultResponse)
def pipeline_stage_enriched(payload: PipelineStageEnrichRequest) -> StageResultResponse:
    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        copilot_client = CopilotClient(config=load_copilot_config())
        result = run_stage_enriched(
            repo=repo,
            copilot_client=copilot_client,
            limit=payload.limit,
            dry_run=payload.dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return _stage_to_response(result)


@router.post("/stage/metrics", response_model=StageResultResponse)
def pipeline_stage_metrics(payload: PipelineStageMetricsRequest) -> StageResultResponse:
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

    return _stage_to_response(result)
