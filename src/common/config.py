from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from dotenv import load_dotenv


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    api_key: str
    timeout_seconds: int = 30

    @property
    def rest_base_url(self) -> str:
        return self.url.rstrip("/") + "/rest/v1"

    @property
    def headers(self) -> dict[str, str]:
        return {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }


def _is_valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def load_config() -> SupabaseConfig:
    load_dotenv()

    url = os.getenv("SUPABASE_URL", "").strip()
    api_key = os.getenv("SUPABASE_KEY", "").strip()
    timeout_value = os.getenv("SUPABASE_TIMEOUT_SECONDS", "30").strip()

    if not url:
        raise ValueError("Missing SUPABASE_URL in environment.")
    if not _is_valid_http_url(url):
        raise ValueError("SUPABASE_URL must be a valid http(s) URL.")
    if not api_key:
        raise ValueError("Missing SUPABASE_KEY in environment.")

    try:
        timeout_seconds = int(timeout_value)
    except ValueError as exc:
        raise ValueError("SUPABASE_TIMEOUT_SECONDS must be an integer.") from exc

    if timeout_seconds <= 0:
        raise ValueError("SUPABASE_TIMEOUT_SECONDS must be > 0.")

    return SupabaseConfig(url=url, api_key=api_key, timeout_seconds=timeout_seconds)
