from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

from .config import CopilotConfig
from .constants import EXTRACTION_SYSTEM_PROMPT, EXTRACTION_USER_PROMPT_TEMPLATE


@dataclass
class CopilotExtractionResult:
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


class CopilotClient:
    def __init__(self, config: CopilotConfig) -> None:
        self.config = config

    def _create_client(self):
        try:
            from copilot import CopilotClient as SDKCopilotClient
        except ImportError as exc:
            raise RuntimeError(
                "Missing 'copilot' SDK dependency. Install required package before running enricher."
            ) from exc

        return SDKCopilotClient()

    async def _extract_async(self, description: str) -> dict[str, Any]:
        user_prompt = EXTRACTION_USER_PROMPT_TEMPLATE.format(description=description)
        prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\n{user_prompt}"

        async with self._create_client() as client:
            async with await client.create_session(model=self.config.model) as session:
                response = await asyncio.wait_for(session.send(prompt), timeout=self.config.timeout_seconds)
                content = getattr(response, "content", "")
                parsed = json.loads(content or "{}")
                if not isinstance(parsed, dict):
                    raise ValueError("Model output was not a JSON object.")
                return parsed

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
