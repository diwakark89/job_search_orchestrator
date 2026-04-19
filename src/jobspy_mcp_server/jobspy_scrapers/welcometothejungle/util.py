from __future__ import annotations

from datetime import date, datetime

from jobspy_mcp_server.jobspy_scrapers.model import Country


def truthy_env(value: str | None) -> bool:
    """Return True if the env-var value indicates an enabled flag."""
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def map_country_to_code(country: Country | None) -> str | None:
    """Map a Country enum to a two-letter ISO code suitable for WTTJ filters."""
    if country is None or not isinstance(country, Country):
        return None
    code = country.value[1].split(":")[0].upper()
    if not code or len(code) > 3:
        return None
    return code


def parse_iso_date(value: str | int | None) -> date | None:
    """Parse Algolia date strings (ISO 8601 or epoch) into a date."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.utcfromtimestamp(int(value)).date()
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None
