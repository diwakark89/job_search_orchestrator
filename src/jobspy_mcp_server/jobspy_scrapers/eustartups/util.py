from __future__ import annotations

from datetime import date, datetime

from jobspy_mcp_server.jobspy_scrapers.model import Location


def parse_location(location_text: str | None) -> Location | None:
    if not location_text:
        return None
    text = location_text.strip()
    if not text:
        return None
    parts = [p.strip() for p in text.split(",") if p.strip()]
    city = parts[0] if parts else None
    country = parts[-1] if len(parts) > 1 else None
    state = parts[1] if len(parts) > 2 else None
    return Location(city=city, state=state, country=country)


def parse_post_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%B %d, %Y", "%d %B %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None
