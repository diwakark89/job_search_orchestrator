"""Pure validation and clamping helpers for scraping search parameters.

Each function takes a value and the relevant guardrail constants, returning a
sanitised value or raising ``ValueError`` with a human-readable message. None
of these functions perform I/O, which keeps them trivially unit-testable.
"""
from __future__ import annotations

from .guardrails import (
    CITIES_MAX,
    HOURS_OLD_MAX,
    HOURS_OLD_MIN,
    OFFSET_MAX,
    OFFSET_MIN,
    RESULTS_WANTED_MAX,
    RESULTS_WANTED_MIN,
    SITES_MAX,
    SITES_MIN,
    VALID_SITES,
    WORK_MODES,
)


def resolve_sites(site_name: list[str] | None, *, defaults: list[str]) -> list[str]:
    """Resolve and validate the requested site list.

    ``None`` means "use defaults"; an explicit empty list is a validation error
    so callers cannot accidentally bypass the SITES_MIN guarantee.
    """
    selected_sites = list(site_name) if site_name is not None else list(defaults)
    invalid_sites = [site for site in selected_sites if site not in VALID_SITES]
    if invalid_sites:
        raise ValueError(f"Invalid site names: {invalid_sites}. Valid sites: {VALID_SITES}")
    if len(selected_sites) < SITES_MIN:
        raise ValueError(f"At least {SITES_MIN} site must be specified.")
    if len(selected_sites) > SITES_MAX:
        raise ValueError(
            f"Maximum {SITES_MAX} sites per request, got {len(selected_sites)}. "
            f"Choose up to {SITES_MAX} from: {VALID_SITES}"
        )
    return selected_sites


def validate_work_mode(work_mode: str | None) -> None:
    if work_mode is not None and work_mode not in WORK_MODES:
        raise ValueError(f"Invalid work_mode '{work_mode}'. Valid values: {WORK_MODES}")


def validate_cities_count(cities: list[str] | None) -> None:
    if cities and len(cities) > CITIES_MAX:
        raise ValueError(f"Maximum {CITIES_MAX} cities per request, got {len(cities)}.")


def clamp_results_wanted(value: int) -> int:
    return min(max(value, RESULTS_WANTED_MIN), RESULTS_WANTED_MAX)


def clamp_hours_old(value: int) -> int:
    return min(max(value, HOURS_OLD_MIN), HOURS_OLD_MAX)


def clamp_offset(value: int) -> int:
    return min(max(value, OFFSET_MIN), OFFSET_MAX)


__all__ = [
    "clamp_hours_old",
    "clamp_offset",
    "clamp_results_wanted",
    "resolve_sites",
    "validate_cities_count",
    "validate_work_mode",
]
