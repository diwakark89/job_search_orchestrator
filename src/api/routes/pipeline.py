from __future__ import annotations

import logging
import re
import threading
import uuid

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


def _run_submitted_jobs_enrichment(ids: list[str], submit_request_id: str) -> None:
    logger.info(
        "pipeline submit background started submit_request_id=%s ids_count=%s",
        submit_request_id,
        len(ids),
    )
    logger.debug(
        "pipeline submit background ids submit_request_id=%s ids=%s",
        submit_request_id,
        ids,
    )
    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        logger.debug("pipeline submit background repo_init submit_request_id=%s", submit_request_id)
        copilot_client = CopilotClient(config=load_copilot_config())
        logger.debug("pipeline submit background copilot_init submit_request_id=%s", submit_request_id)
        logger.info(
            "pipeline submit background calling enrich_jobs_by_ids submit_request_id=%s ids_count=%s set_job_status_enriched=True target_job_status=SAVED",
            submit_request_id,
            len(ids),
        )
        summary = enrich_jobs_by_ids(
            repo=repo,
            copilot_client=copilot_client,
            ids=ids,
            set_job_status_enriched=True,
            target_job_status="SAVED",
            submit_request_id=submit_request_id,
        )
        logger.info(
            "pipeline submit background completed submit_request_id=%s ids_count=%s enriched=%s skipped=%s failed=%s errors=%s",
            submit_request_id,
            len(ids),
            summary.enriched.count,
            summary.skipped.count,
            summary.failed.count,
            len(summary.errors),
        )
        logger.debug(
            "pipeline submit background enriched_ids submit_request_id=%s ids=%s",
            submit_request_id,
            summary.enriched.ids,
        )
        for job_id in summary.enriched.ids:
            logger.info(
                "pipeline submit background saved_job submit_request_id=%s id=%s",
                submit_request_id,
                job_id,
            )
        if summary.failed.ids:
            logger.debug(
                "pipeline submit background failed_ids submit_request_id=%s ids=%s",
                submit_request_id,
                summary.failed.ids,
            )
    except Exception:  # noqa: BLE001
        logger.exception(
            "pipeline submit background enrichment failed submit_request_id=%s ids=%s",
            submit_request_id,
            ids,
        )


@router.post("/run", response_model=PipelineResultResponse)
def pipeline_run(payload: PipelineRunRequest) -> PipelineResultResponse:
    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        copilot_client = CopilotClient(config=load_copilot_config())
        result = run_pipeline(
            repo=repo,
            copilot_client=copilot_client,
            rows=payload.jobs,
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
    submit_request_id = str(uuid.uuid4())
    logger.info(
        "POST /pipeline/submit received submit_request_id=%s submitted_row_count=%s",
        submit_request_id,
        len(payload.jobs),
    )
    logger.debug(
        "POST /pipeline/submit job_urls submit_request_id=%s urls=%s",
        submit_request_id,
        [row.get("job_url") for row in payload.jobs if isinstance(row, dict)],
    )

    try:
        repo = SupabaseRepository(client=PostgrestClient(config=load_config()))
        result = submit_jobs_for_enrichment(repo=repo, rows=payload.jobs)
    except ValueError as exc:
        logger.warning(
            "POST /pipeline/submit validation_error submit_request_id=%s detail=%s",
            submit_request_id,
            str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error(
            "POST /pipeline/submit runtime_error submit_request_id=%s detail=%s",
            submit_request_id,
            str(exc),
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    logger.info(
        "POST /pipeline/submit service_result submit_request_id=%s accepted=%s rejected=%s jobs_final_rows=%s shared_links_rows=%s",
        submit_request_id,
        len(result.accepted_ids),
        len(result.rejected_row_indexes),
        result.jobs_final_row_count,
        result.shared_links_row_count,
    )
    logger.debug(
        "POST /pipeline/submit accepted_ids submit_request_id=%s ids=%s",
        submit_request_id,
        result.accepted_ids,
    )

    enrichment_thread = threading.Thread(
        target=_run_submitted_jobs_enrichment,
        args=(list(result.accepted_ids), submit_request_id),
        name="pipeline-submit-enrichment",
        daemon=True,
    )
    enrichment_thread.start()

    logger.info(
        "POST /pipeline/submit queued_background submit_request_id=%s queued_ids_count=%s thread=%s",
        submit_request_id,
        len(result.accepted_ids),
        enrichment_thread.name,
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
        result = run_stage_ingest(repo=repo, rows=payload.jobs)
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
