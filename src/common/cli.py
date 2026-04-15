from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich import print

from .client import OperationResult, PostgrestClient
from .config import load_config
from .constants import DEFAULT_CONFLICT_KEYS, VALID_TABLES

from repository.supabase import SupabaseRepository
from service.tables import (
    delete_jobs_final_by_id,
    soft_delete_jobs_final,
)

app = typer.Typer(help="Supabase table operations for Automated Job Hunt.")
TABLE_OPTION_HELP = "Target table name."


def _parse_json_payload(payload: str | None, payload_file: Path | None, expect_list: bool) -> Any:
    if bool(payload) == bool(payload_file):
        raise typer.BadParameter("Provide exactly one of --payload or --payload-file.")

    if payload is not None:
        raw = payload
    else:
        assert payload_file is not None
        raw = payload_file.read_text(encoding="utf-8")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON payload: {exc}") from exc

    if expect_list and not isinstance(parsed, list):
        raise typer.BadParameter("Payload must be a JSON array for insert/upsert.")
    if not expect_list and not isinstance(parsed, dict):
        raise typer.BadParameter("Payload must be a JSON object for patch.")

    return parsed


def _repo() -> SupabaseRepository:
    return SupabaseRepository(client=PostgrestClient(config=load_config()))


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


def _ensure_table(table: str) -> None:
    if table not in VALID_TABLES:
        raise typer.BadParameter(f"Invalid table '{table}'. Supported: {sorted(VALID_TABLES)}")


@app.command("upsert")
def cmd_upsert(
    table: str = typer.Option(..., "--table", help=TABLE_OPTION_HELP),
    payload: str | None = typer.Option(None, "--payload", help="Inline JSON array payload."),
    payload_file: Path | None = typer.Option(None, "--payload-file", help="Path to JSON array payload."),
    on_conflict: str | None = typer.Option(None, "--on-conflict", help="Conflict key (optional)."),
) -> None:
    _ensure_table(table)
    rows = _parse_json_payload(payload, payload_file, expect_list=True)

    repo = _repo()
    result = repo.upsert_rows(table=table, rows=rows, on_conflict=on_conflict)
    _print_result(result)


@app.command("insert")
def cmd_insert(
    table: str = typer.Option(..., "--table", help=TABLE_OPTION_HELP),
    payload: str | None = typer.Option(None, "--payload", help="Inline JSON array payload."),
    payload_file: Path | None = typer.Option(None, "--payload-file", help="Path to JSON array payload."),
) -> None:
    _ensure_table(table)
    rows = _parse_json_payload(payload, payload_file, expect_list=True)

    repo = _repo()
    result = repo.insert_rows(table=table, rows=rows)
    _print_result(result)


@app.command("patch")
def cmd_patch(
    table: str = typer.Option(..., "--table", help=TABLE_OPTION_HELP),
    filter_column: str = typer.Option(..., "--filter-column", help="Column for filter."),
    filter_value: str = typer.Option(..., "--filter-value", help="Value for filter."),
    payload: str | None = typer.Option(None, "--payload", help="Inline JSON object payload."),
    payload_file: Path | None = typer.Option(None, "--payload-file", help="Path to JSON object payload."),
    operator: str = typer.Option("eq", "--operator", help="PostgREST operator, default eq."),
) -> None:
    _ensure_table(table)
    patch_payload = _parse_json_payload(payload, payload_file, expect_list=False)

    repo = _repo()
    result = repo.patch_rows(
        table=table,
        payload=patch_payload,
        filters={filter_column: filter_value},
        operator=operator,
    )
    _print_result(result)


@app.command("delete")
def cmd_delete(
    table: str = typer.Option(..., "--table", help=TABLE_OPTION_HELP),
    filter_column: str = typer.Option(..., "--filter-column", help="Column for filter."),
    filter_value: str = typer.Option(..., "--filter-value", help="Value for filter."),
    operator: str = typer.Option("eq", "--operator", help="PostgREST operator, default eq."),
    treat_404_as_success: bool = typer.Option(False, "--treat-404-as-success", help="Idempotent delete behavior."),
) -> None:
    _ensure_table(table)
    repo = _repo()
    result = repo.delete_rows(
        table=table,
        filters={filter_column: filter_value},
        operator=operator,
        treat_404_as_success=treat_404_as_success,
    )
    _print_result(result)


@app.command("soft-delete")
def cmd_soft_delete(
    table: str = typer.Option(..., "--table", help="Only jobs_final."),
    record_id: str = typer.Option(..., "--record-id", help="id for jobs_final."),
    hard_delete: bool = typer.Option(False, "--hard-delete", help="Perform hard delete after soft delete."),
) -> None:
    repo = _repo()

    if table == "jobs_final":
        result = soft_delete_jobs_final(repo=repo, job_id=record_id, hard_delete=hard_delete)
    else:
        raise typer.BadParameter("soft-delete only supports jobs_final.")

    _print_result(result)


@app.command("delete-jobs-final")
def cmd_delete_jobs_final(job_id: str = typer.Option(..., "--id")) -> None:
    result = delete_jobs_final_by_id(repo=_repo(), job_id=job_id)
    _print_result(result)


@app.command("tables")
def cmd_tables() -> None:
    print("Supported tables:")
    for table in sorted(VALID_TABLES):
        conflict = DEFAULT_CONFLICT_KEYS.get(table, "n/a")
        print(f"- {table} (default on_conflict: {conflict})")
