from __future__ import annotations

from datetime import date, datetime

from jobspy_mcp_server.jobspy_scrapers.model import Country, Location


def parse_location(location_text: str | None) -> Location | None:
    """Parse a Berlin Startup Jobs location string into a Location object.

    The board is Berlin-focused, so when no text is given we still default to Berlin/Germany.
    """
    if not location_text:
        return Location(country=Country.GERMANY, city="Berlin")
    parts = [p.strip() for p in location_text.split(",") if p.strip()]
    city = parts[0] if parts else "Berlin"
    return Location(city=city, country=Country.GERMANY)


def parse_post_date(value: str | None) -> date | None:
    """Parse an ISO-style or human-readable date string into a date object."""
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%B %d, %Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None
