from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich import print

from common.client import OperationResult, PostgrestClient
from common.config import load_config
from repository.supabase import SupabaseRepository
from service.automation import (
    AutomationConflictError,
    approve_job_for_apply,
    create_apply_session_for_job,
    reject_job_for_apply,
)

app = typer.Typer(help="Automation session operations for OpenClaw.")

_TABLE = "automation_sessions"


def _repo() -> SupabaseRepository:
    return SupabaseRepository(client=PostgrestClient(config=load_config()))


def _parse_json_payload(payload: str | None, payload_file: Path | None) -> Any:
    if bool(payload) == bool(payload_file):
        raise typer.BadParameter("Provide exactly one of --payload or --payload-file.")

    if payload is not None:
        raw = payload
    else:
        assert payload_file is not None
        raw = payload_file.read_text(encoding="utf-8")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON payload: {exc}") from exc


def _parse_rows_payload(payload: str | None, payload_file: Path | None) -> list[dict[str, Any]]:
    parsed = _parse_json_payload(payload=payload, payload_file=payload_file)
    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list):
        if not all(isinstance(item, dict) for item in parsed):
            raise typer.BadParameter("Array payload must contain JSON objects only.")
        return parsed
    raise typer.BadParameter("Payload must be a JSON object or JSON array of objects.")


def _parse_patch_payload(payload: str | None, payload_file: Path | None) -> dict[str, Any]:
    parsed = _parse_json_payload(payload=payload, payload_file=payload_file)
    if not isinstance(parsed, dict):
        raise typer.BadParameter("Payload must be a JSON object for patch.")
    return parsed


def _parse_filter_options(filters: list[str] | None) -> dict[str, str] | None:
    if not filters:
        return None

    parsed: dict[str, str] = {}
    for item in filters:
        if "=" not in item:
            raise typer.BadParameter(f"Invalid --filter '{item}'. Expected key=value format.")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise typer.BadParameter(f"Invalid --filter '{item}'. Filter key cannot be empty.")
        parsed[key] = value
    return parsed


def _print_result(result: OperationResult) -> None:
    color = "green" if result.success else "red"
    print(
        f"[{color}]operation={result.operation} table={result.table} success={result.success} "
        f"status={result.status_code} rows={result.row_count}[/{color}]"
    )
    if result.error:
        print(f"[red]error:[/red] {result.error}")
    if result.data is not None:
        print(json.dumps(result.data, indent=2, default=str))


def _print_select_result(rows: list[dict[str, Any]]) -> None:
    print(json.dumps({"rows": rows, "count": len(rows), "table": _TABLE}, indent=2, default=str))


def _print_json_payload(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, default=str))


@app.command("create")
def cmd_create(
    payload: str | None = typer.Option(None, "--payload", help="Inline JSON object or JSON array payload."),
    payload_file: Path | None = typer.Option(None, "--payload-file", help="Path to JSON object/array payload."),
    on_conflict: str = typer.Option("id", "--on-conflict", help="Conflict key used for upsert."),
) -> None:
    rows = _parse_rows_payload(payload=payload, payload_file=payload_file)
    result = _repo().upsert_rows(table=_TABLE, rows=rows, on_conflict=on_conflict)
    _print_result(result)


@app.command("list")
def cmd_list(
    columns: str = typer.Option("*", "--columns", help="Comma-separated column names."),
    limit: int = typer.Option(50, "--limit", min=1, help="Maximum rows to return."),
    offset: int = typer.Option(0, "--offset", min=0, help="Rows to skip."),
    order_by: str | None = typer.Option(None, "--order-by", help="Column used for ordering."),
    ascending: bool = typer.Option(True, "--ascending/--descending", help="Sort ascending or descending."),
    filter_items: list[str] | None = typer.Option(None, "--filter", help="Equality filter key=value. Repeatable."),
) -> None:
    filters = _parse_filter_options(filter_items)
    result = _repo().select_rows(
        table=_TABLE,
        columns=columns,
        filters=filters,
        limit=limit,
        offset=offset,
        order_by=order_by,
        ascending=ascending,
    )
    if not result.success:
        _print_result(result)
        raise typer.Exit(code=1)

    rows = result.data if isinstance(result.data, list) else []
    _print_select_result(rows=rows)


@app.command("get")
def cmd_get(
    session_id: str = typer.Option(..., "--id", help="Automation session id."),
    columns: str = typer.Option("*", "--columns", help="Comma-separated column names."),
) -> None:
    result = _repo().select_rows(
        table=_TABLE,
        columns=columns,
        filters={"id": session_id},
        limit=1,
    )
    if not result.success:
        _print_result(result)
        raise typer.Exit(code=1)

    rows = result.data if isinstance(result.data, list) else []
    _print_select_result(rows=rows)


@app.command("patch")
def cmd_patch(
    session_id: str = typer.Option(..., "--id", help="Automation session id."),
    payload: str | None = typer.Option(None, "--payload", help="Inline JSON object payload."),
    payload_file: Path | None = typer.Option(None, "--payload-file", help="Path to JSON object payload."),
    operator: str = typer.Option("eq", "--operator", help="PostgREST operator, default eq."),
) -> None:
    patch_payload = _parse_patch_payload(payload=payload, payload_file=payload_file)
    result = _repo().patch_rows(
        table=_TABLE,
        payload=patch_payload,
        filters={"id": session_id},
        operator=operator,
    )
    _print_result(result)


@app.command("delete")
def cmd_delete(
    session_id: str = typer.Option(..., "--id", help="Automation session id."),
    treat_404_as_success: bool = typer.Option(True, "--treat-404-as-success", help="Idempotent delete behavior."),
) -> None:
    result = _repo().delete_rows(
        table=_TABLE,
        filters={"id": session_id},
        treat_404_as_success=treat_404_as_success,
    )
    _print_result(result)


@app.command("approve-job")
def cmd_approve_job(
    job_id: str = typer.Option(..., "--job-id", help="jobs_final row id to approve for automation."),
) -> None:
    try:
        payload = approve_job_for_apply(repo=_repo(), job_id=job_id)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except RuntimeError as exc:
        print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _print_json_payload(payload)


@app.command("reject-job")
def cmd_reject_job(
    job_id: str = typer.Option(..., "--job-id", help="jobs_final row id to reject for automation."),
) -> None:
    try:
        payload = reject_job_for_apply(repo=_repo(), job_id=job_id)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except RuntimeError as exc:
        print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _print_json_payload(payload)


@app.command("create-apply-session")
def cmd_create_apply_session(
    job_id: str = typer.Option(..., "--job-id", help="jobs_final row id that is READY_TO_APPLY."),
    current_step: str = typer.Option(
        "OPEN_JOB_PAGE",
        "--current-step",
        help="Initial automation step name.",
    ),
) -> None:
    try:
        payload = create_apply_session_for_job(
            repo=_repo(),
            job_id=job_id,
            current_step=current_step,
        )
    except AutomationConflictError as exc:
        print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except RuntimeError as exc:
        print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _print_json_payload(payload)
