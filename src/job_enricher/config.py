from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class CopilotConfig:
    model: str
    timeout_seconds: int = 45
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0


def load_copilot_config() -> CopilotConfig:
    load_dotenv()

    model = os.getenv("COPILOT_MODEL", "gpt-5.4-mini").strip()
    timeout_value = os.getenv("COPILOT_TIMEOUT_SECONDS", "45").strip()
    max_retries_value = os.getenv("COPILOT_MAX_RETRIES", "3").strip()
    backoff_value = os.getenv("COPILOT_RETRY_BACKOFF_SECONDS", "1.0").strip()

    if not model:
        raise ValueError("Missing COPILOT_MODEL in environment.")

    try:
        timeout_seconds = int(timeout_value)
    except ValueError as exc:
        raise ValueError("COPILOT_TIMEOUT_SECONDS must be an integer.") from exc

    if timeout_seconds <= 0:
        raise ValueError("COPILOT_TIMEOUT_SECONDS must be > 0.")

    try:
        max_retries = int(max_retries_value)
    except ValueError as exc:
        raise ValueError("COPILOT_MAX_RETRIES must be an integer.") from exc

    if max_retries <= 0:
        raise ValueError("COPILOT_MAX_RETRIES must be > 0.")

    try:
        retry_backoff_seconds = float(backoff_value)
    except ValueError as exc:
        raise ValueError("COPILOT_RETRY_BACKOFF_SECONDS must be a number.") from exc

    if retry_backoff_seconds <= 0:
        raise ValueError("COPILOT_RETRY_BACKOFF_SECONDS must be > 0.")

    return CopilotConfig(
        model=model,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
    )
