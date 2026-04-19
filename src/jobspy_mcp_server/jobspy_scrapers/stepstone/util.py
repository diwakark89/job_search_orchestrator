from __future__ import annotations

from jobspy_mcp_server.jobspy_scrapers.model import Location


def parse_location(location_text: str | None) -> Location | None:
    """Parse a Stepstone location string into a Location object."""
    if not location_text:
        return None
    parts = [p.strip() for p in location_text.split(",")]
    city = parts[0] if parts else None
    state = parts[1] if len(parts) > 1 else None
    return Location(city=city, state=state)
