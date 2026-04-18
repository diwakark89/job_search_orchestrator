from __future__ import annotations

import logging
import re
import threading

from fastapi import APIRouter, HTTPException

from api.models import (
    EnrichmentCountResponse,
    EnrichmentSummaryResponse,
    MetricsResponse,
    PipelineResultResponse,
    PipelineRunRequest,
    PipelineSubmitRequest,
    PipelineSubmitResponse,
    PipelineStageEnrichRequest,
    PipelineStageIngestRequest,
    StageResultResponse,
)
from common.client import PostgrestClient
from common.config import load_config
from job_enricher.client_copilot import CopilotClient
from job_enricher.config import load_copilot_config
from repository.supabase import SupabaseRepository
from service.enricher import enrich_jobs_by_ids
from service.pipeline import (
    run_pipeline,
    run_stage_enriched_detailed,
    run_stage_ingest,
    submit_jobs_for_enrichment,
)
from service.tables import get_metrics

router = APIRouter(prefix="/pipeline", tags=["pipeline"])
logger = logging.getLogger("uvicorn.error")


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
        enriched=EnrichmentCountResponse(count=0, ids=[]),
        skipped=EnrichmentCountResponse(count=0, ids=[]),
        failed=EnrichmentCountResponse(count=len(stage.errors), ids=[]),
        errors=stage.errors,
        copilot_batches_sent=0,
        database_batches_sent=0,
        database_rows_reported=0,
    )


def _run_submitted_jobs_enrichment(ids: list[str]) -> None:
    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        copilot_client = CopilotClient(config=load_copilot_config())
        summary = enrich_jobs_by_ids(
            repo=repo,
            copilot_client=copilot_client,
            ids=ids,
            set_job_status_enriched=True,
        )
        logger.info(
            "pipeline submit background enrichment completed ids_count=%s enriched=%s skipped=%s failed=%s errors=%s",
            len(ids),
            summary.enriched.count,
            summary.skipped.count,
            summary.failed.count,
            len(summary.errors),
        )
    except Exception:  # noqa: BLE001
        logger.exception("pipeline submit background enrichment failed ids=%s", ids)


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


@router.post("/submit", response_model=PipelineSubmitResponse, status_code=202)
def pipeline_submit(payload: PipelineSubmitRequest) -> PipelineSubmitResponse:
    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        result = submit_jobs_for_enrichment(repo=repo, rows=payload.rows)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    enrichment_thread = threading.Thread(
        target=_run_submitted_jobs_enrichment,
        args=(list(result.accepted_ids),),
        name="pipeline-submit-enrichment",
        daemon=True,
    )
    enrichment_thread.start()

    logger.info(
        "POST /pipeline/submit queued ids_count=%s rejected=%s shared_links=%s",
        len(result.accepted_ids),
        len(result.rejected_row_indexes),
        result.shared_links_row_count,
    )

    return PipelineSubmitResponse(
        submitted_row_count=result.submitted_row_count,
        accepted=EnrichmentCountResponse(count=len(result.accepted_ids), ids=result.accepted_ids),
        queued=EnrichmentCountResponse(count=len(result.accepted_ids), ids=result.accepted_ids),
        rejected_row_indexes=result.rejected_row_indexes,
        errors=result.errors,
        jobs_final_row_count=result.jobs_final_row_count,
        shared_links_row_count=result.shared_links_row_count,
    )


@router.post("/stage/ingest", response_model=EnrichmentSummaryResponse)
def pipeline_stage_ingest(payload: PipelineStageIngestRequest) -> EnrichmentSummaryResponse:
    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        result = run_stage_ingest(repo=repo, rows=payload.rows)
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

    copilot_batches_sent = getattr(result, "copilot_batches_sent", 0)
    database_batches_sent = getattr(result, "database_batches_sent", 0)
    database_rows_reported = getattr(result, "database_rows_reported", 0)

    return EnrichmentSummaryResponse(
        processed=EnrichmentCountResponse(count=result.processed.count, ids=result.processed.ids),
        enriched=EnrichmentCountResponse(count=result.enriched.count, ids=result.enriched.ids),
        skipped=EnrichmentCountResponse(count=result.skipped.count, ids=result.skipped.ids),
        failed=EnrichmentCountResponse(count=result.failed.count, ids=result.failed.ids),
        errors=result.errors,
        copilot_batches_sent=copilot_batches_sent,
        database_batches_sent=database_batches_sent,
        database_rows_reported=database_rows_reported,
    )


@router.get("/metrics", response_model=MetricsResponse)
def pipeline_metrics() -> MetricsResponse:
    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        metrics = get_metrics(repo=repo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return MetricsResponse(
        status_counts=metrics["status_counts"],
        total=metrics["total"],
    )
