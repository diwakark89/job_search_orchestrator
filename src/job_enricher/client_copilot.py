from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

from .config import CopilotConfig
from .constants import (
    BATCH_EXTRACTION_SYSTEM_PROMPT,
    BATCH_EXTRACTION_USER_PROMPT_TEMPLATE,
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_USER_PROMPT_TEMPLATE,
)


@dataclass(frozen=True)
class CopilotBatchExtractionInput:
    row_id: str
    description: str


@dataclass
class CopilotExtractionResult:
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class CopilotBatchExtractionResult:
    row_id: str
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


class CopilotClient:
    def __init__(self, config: CopilotConfig) -> None:
        self.config = config

    @property
    def batch_size(self) -> int:
        return self.config.batch_size

    def _create_client(self):
        try:
            from copilot import CopilotClient as SDKCopilotClient
        except ImportError as exc:
            raise RuntimeError(
                "Missing 'copilot-sdk' dependency. Install with: pip install copilot-sdk"
            ) from exc

        return SDKCopilotClient()

    async def _run_prompt_async(self, prompt: str) -> dict[str, Any]:
        from copilot.session import PermissionHandler

        async with self._create_client() as client:
            async with await client.create_session(
                model=self.config.model,
                on_permission_request=PermissionHandler.approve_all,
            ) as session:
                content_parts: list[str] = []
                done = asyncio.Event()

                def on_event(event):
                    event_type = event.type.value if hasattr(event.type, "value") else str(event.type)
                    if event_type == "assistant.message":
                        content_parts.append(event.data.content or "")
                        done.set()
                    elif event_type == "session.idle":
                        done.set()

                session.on(on_event)
                await session.send(prompt)
                await asyncio.wait_for(done.wait(), timeout=self.config.timeout_seconds)

                content = "".join(content_parts).strip()
                if not content:
                    raise ValueError("Model returned empty response.")

                parsed = json.loads(content)
                if not isinstance(parsed, dict):
                    raise ValueError("Model output was not a JSON object.")
                return parsed

    async def _extract_async(self, description: str) -> dict[str, Any]:
        user_prompt = EXTRACTION_USER_PROMPT_TEMPLATE.format(description=description)
        prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\n{user_prompt}"
        return await self._run_prompt_async(prompt)

    async def _extract_batch_async(self, items: list[CopilotBatchExtractionInput]) -> dict[str, Any]:
        serialized_items = [
            {"id": item.row_id, "description": item.description}
            for item in items
        ]
        user_prompt = BATCH_EXTRACTION_USER_PROMPT_TEMPLATE.format(
            items_json=json.dumps(serialized_items, ensure_ascii=True)
        )
        prompt = f"{BATCH_EXTRACTION_SYSTEM_PROMPT}\n\n{user_prompt}"
        return await self._run_prompt_async(prompt)

    def _extract_batch_once(
        self,
        items: list[CopilotBatchExtractionInput],
    ) -> list[CopilotBatchExtractionResult]:
        if not items:
            return []

        raw_response = asyncio.run(self._extract_batch_async(items))
        raw_results = raw_response.get("results")
        if not isinstance(raw_results, list):
            raise ValueError("Model output missing results array.")

        expected_ids = [item.row_id for item in items]
        results_by_id: dict[str, dict[str, Any]] = {}
        for raw_result in raw_results:
            if not isinstance(raw_result, dict):
                raise ValueError("Each batch result must be a JSON object.")
            row_id = raw_result.get("id")
            if not isinstance(row_id, str) or not row_id.strip():
                raise ValueError("Each batch result must include a non-empty id.")
            normalized_id = row_id.strip()
            if normalized_id not in expected_ids:
                raise ValueError(f"Model returned unexpected id={normalized_id}.")
            if normalized_id in results_by_id:
                raise ValueError(f"Model returned duplicate id={normalized_id}.")

            payload = {key: value for key, value in raw_result.items() if key != "id"}
            results_by_id[normalized_id] = payload

        batch_results: list[CopilotBatchExtractionResult] = []
        for item in items:
            payload = results_by_id.get(item.row_id)
            if payload is None:
                batch_results.append(
                    CopilotBatchExtractionResult(
                        row_id=item.row_id,
                        success=False,
                        error="Model output missing result for id.",
                    )
                )
                continue

            batch_results.append(
                CopilotBatchExtractionResult(
                    row_id=item.row_id,
                    success=True,
                    data=payload,
                )
            )

        return batch_results

    def extract_from_description(self, description: str) -> CopilotExtractionResult:
        if not description.strip():
            return CopilotExtractionResult(success=False, error="Description is empty.")

        last_error: str | None = None
        for attempt in range(self.config.max_retries):
            if attempt > 0:
                time.sleep(self.config.retry_backoff_seconds * (2 ** (attempt - 1)))

            try:
                parsed = asyncio.run(self._extract_async(description))
                return CopilotExtractionResult(success=True, data=parsed)
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)

        return CopilotExtractionResult(success=False, error=last_error or "Unknown extraction failure.")

    def extract_from_descriptions(
        self,
        items: list[CopilotBatchExtractionInput],
    ) -> list[CopilotBatchExtractionResult]:
        if not items:
            return []

        invalid_items = [item.row_id for item in items if not item.description.strip()]
        if invalid_items:
            return [
                CopilotBatchExtractionResult(
                    row_id=item.row_id,
                    success=False,
                    error="Description is empty.",
                )
                for item in items
            ]

        last_error: str | None = None
        for attempt in range(self.config.max_retries):
            if attempt > 0:
                time.sleep(self.config.retry_backoff_seconds * (2 ** (attempt - 1)))

            try:
                return self._extract_batch_once(items)
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)

        return [
            CopilotBatchExtractionResult(
                row_id=item.row_id,
                success=False,
                error=last_error or "Unknown extraction failure.",
            )
            for item in items
        ]
