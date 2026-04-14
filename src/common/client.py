from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import requests
from requests import Response, Session

from .config import SupabaseConfig

_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


@dataclass
class OperationResult:
    success: bool
    status_code: int | None
    table: str
    operation: str
    row_count: int
    data: Any | None = None
    error: str | None = None


class PostgrestClient:
    def __init__(self, config: SupabaseConfig, max_retries: int = 3, retry_backoff_seconds: float = 1.0) -> None:
        self.config = config
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.session: Session = requests.Session()

    def _build_url(self, table: str) -> str:
        return f"{self.config.rest_base_url}/{table}"

    @staticmethod
    def _stringify_filter_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    @staticmethod
    def _row_count(body: Any | None) -> int:
        if isinstance(body, list):
            return len(body)
        if body is None:
            return 0
        return 1

    @staticmethod
    def _parse_response_payload(response: Response) -> Any | None:
        if not response.text:
            return None

        try:
            return response.json()
        except json.JSONDecodeError:
            return response.text

    def _success_result(
        self,
        response: Response,
        table: str,
        operation: str,
        row_count: int,
        payload: Any | None,
    ) -> OperationResult:
        return OperationResult(
            success=True,
            status_code=response.status_code,
            table=table,
            operation=operation,
            row_count=row_count,
            data=payload,
        )

    def _failure_result(
        self,
        response: Response,
        table: str,
        operation: str,
        row_count: int,
        payload: Any | None,
    ) -> OperationResult:
        if response.text:
            try:
                body = json.loads(response.text)
                if isinstance(body, dict):
                    detail = body.get("message") or body.get("error") or body.get("detail") or response.text[:300]
                else:
                    detail = response.text[:300]
            except (json.JSONDecodeError, ValueError):
                detail = response.text[:300]
            error_msg = f"HTTP {response.status_code} on {operation} {table}: {detail}"
        else:
            error_msg = f"HTTP {response.status_code} on {operation} {table}: Unknown API error"

        return OperationResult(
            success=False,
            status_code=response.status_code,
            table=table,
            operation=operation,
            row_count=row_count,
            data=payload,
            error=error_msg,
        )

    def _request(
        self,
        method: str,
        table: str,
        operation: str,
        params: dict[str, Any] | None = None,
        body: Any | None = None,
        extra_headers: dict[str, str] | None = None,
        expected_codes: set[int] | None = None,
    ) -> OperationResult:
        url = self._build_url(table)
        headers = dict(self.config.headers)
        if extra_headers:
            headers.update(extra_headers)

        expected_codes = expected_codes or {200, 201, 204}
        row_count = self._row_count(body)

        last_result: OperationResult | None = None
        for attempt in range(max(1, self.max_retries)):
            if attempt > 0:
                time.sleep(self.retry_backoff_seconds * (2 ** (attempt - 1)))
            try:
                response: Response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=headers,
                    json=body,
                    timeout=self.config.timeout_seconds,
                )
            except requests.RequestException as exc:
                last_result = OperationResult(
                    success=False,
                    status_code=None,
                    table=table,
                    operation=operation,
                    row_count=row_count,
                    error=f"Request failed: {exc}",
                )
                continue

            payload = self._parse_response_payload(response)

            if response.status_code in expected_codes:
                return self._success_result(response, table, operation, row_count, payload)

            last_result = self._failure_result(response, table, operation, row_count, payload)
            if response.status_code not in _RETRYABLE_STATUS_CODES:
                break  # Non-transient error — don't retry.

        assert last_result is not None
        return last_result

    def select(
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
        params: dict[str, Any] = {"select": columns}

        if filters:
            for key, value in filters.items():
                params[key] = f"{operator}.{self._stringify_filter_value(value)}"

        if order_by:
            direction = "asc" if ascending else "desc"
            params["order"] = f"{order_by}.{direction}"

        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)

        headers = {"Prefer": "count=exact"}
        return self._request(
            method="GET",
            table=table,
            operation="select",
            params=params,
            extra_headers=headers,
            expected_codes={200, 206},
        )

    def upsert(self, table: str, rows: list[dict[str, Any]], on_conflict: str) -> OperationResult:
        params = {"on_conflict": on_conflict}
        headers = {"Prefer": "resolution=merge-duplicates"}
        return self._request(
            method="POST",
            table=table,
            operation="upsert",
            params=params,
            body=rows,
            extra_headers=headers,
            expected_codes={200, 201, 204},
        )

    def insert(self, table: str, rows: list[dict[str, Any]]) -> OperationResult:
        headers = {"Prefer": "return=minimal"}
        return self._request(
            method="POST",
            table=table,
            operation="insert",
            body=rows,
            extra_headers=headers,
            expected_codes={200, 201, 204},
        )

    def patch(
        self,
        table: str,
        payload: dict[str, Any],
        filters: dict[str, Any],
        operator: str = "eq",
    ) -> OperationResult:
        params = {
            key: f"{operator}.{self._stringify_filter_value(value)}" for key, value in filters.items()
        }
        return self._request(
            method="PATCH",
            table=table,
            operation="patch",
            params=params,
            body=payload,
            expected_codes={200, 204},
        )

    def delete(
        self,
        table: str,
        filters: dict[str, Any],
        operator: str = "eq",
        treat_404_as_success: bool = False,
    ) -> OperationResult:
        params = {
            key: f"{operator}.{self._stringify_filter_value(value)}" for key, value in filters.items()
        }
        expected = {200, 204}
        if treat_404_as_success:
            expected.add(404)
        return self._request(
            method="DELETE",
            table=table,
            operation="delete",
            params=params,
            expected_codes=expected,
        )
