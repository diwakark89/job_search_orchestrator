from __future__ import annotations

from typing import Any

from common.client import OperationResult, PostgrestClient
from common.constants import DEFAULT_CONFLICT_KEYS, VALID_TABLES
from common.validators import (
    validate_job_approvals_rows,
    validate_job_decisions_rows,
    validate_job_metrics_patch,
    validate_jobs_enriched_rows,
    validate_jobs_final_rows,
    validate_jobs_raw_rows,
    validate_shared_links_rows,
)


class SupabaseRepository:
    def __init__(self, client: PostgrestClient) -> None:
        self.client = client

    @staticmethod
    def _ensure_table_supported(table: str) -> None:
        if table not in VALID_TABLES:
            raise ValueError(f"Unsupported table '{table}'. Supported: {sorted(VALID_TABLES)}")

    @staticmethod
    def _validate_rows_for_table(table: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if table == "jobs_final":
            return validate_jobs_final_rows(rows)
        if table == "shared_links":
            return validate_shared_links_rows(rows)
        if table == "jobs_raw":
            return validate_jobs_raw_rows(rows)
        if table == "jobs_enriched":
            return validate_jobs_enriched_rows(rows)
        if table == "job_decisions":
            return validate_job_decisions_rows(rows)
        if table == "job_approvals":
            return validate_job_approvals_rows(rows)
        if table == "job_metrics":
            raise ValueError("job_metrics does not support insert/upsert rows. Use patch.")
        raise ValueError(f"No validator configured for table '{table}'.")

    def select_rows(
        self,
        table: str,
        columns: str = "*",
        filters: dict[str, Any] | None = None,
        operator: str = "eq",
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | None = None,
        ascending: bool = True,
    ) -> OperationResult:
        self._ensure_table_supported(table)
        return self.client.select(
            table=table,
            columns=columns,
            filters=filters,
            operator=operator,
            limit=limit,
            offset=offset,
            order_by=order_by,
            ascending=ascending,
        )

    def upsert_rows(
        self,
        table: str,
        rows: list[dict[str, Any]],
        on_conflict: str | None = None,
    ) -> OperationResult:
        self._ensure_table_supported(table)
        validated_rows = self._validate_rows_for_table(table, rows)

        conflict_key = on_conflict or DEFAULT_CONFLICT_KEYS.get(table)
        if not conflict_key:
            raise ValueError(f"No default conflict key for table '{table}'. Provide on_conflict.")

        return self.client.upsert(table=table, rows=validated_rows, on_conflict=conflict_key)

    def insert_rows(self, table: str, rows: list[dict[str, Any]]) -> OperationResult:
        self._ensure_table_supported(table)
        validated_rows = self._validate_rows_for_table(table, rows)
        return self.client.insert(table=table, rows=validated_rows)

    def patch_rows(
        self,
        table: str,
        payload: dict[str, Any],
        filters: dict[str, Any],
        operator: str = "eq",
    ) -> OperationResult:
        self._ensure_table_supported(table)

        if table == "job_metrics":
            payload = validate_job_metrics_patch(payload)

        return self.client.patch(table=table, payload=payload, filters=filters, operator=operator)

    def delete_rows(
        self,
        table: str,
        filters: dict[str, Any],
        operator: str = "eq",
        treat_404_as_success: bool = False,
    ) -> OperationResult:
        self._ensure_table_supported(table)
        return self.client.delete(
            table=table,
            filters=filters,
            operator=operator,
            treat_404_as_success=treat_404_as_success,
        )
