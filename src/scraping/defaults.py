"""Preference fallback resolver.

Combines a ``JobSearchRequest`` with the ``RuntimePreferenceDefaults`` derived
from the user's preferences file into a frozen ``EffectiveSearchParams`` dataclass
holding exactly the values the scraper adapter will be invoked with. This is the
single seam between "what the caller asked for" and "what the adapter receives".
"""
from __future__ import annotations

from dataclasses import dataclass

from .guardrails import SITES_DEFAULT
from .preferences import RuntimePreferenceDefaults
from .requests import JobSearchRequest
from .validators import (
    clamp_hours_old,
    clamp_offset,
    clamp_results_wanted,
    resolve_sites,
    validate_cities_count,
    validate_work_mode,
)


@dataclass(frozen=True)
class EffectiveSearchParams:
    search_term: str
    cities: list[str] | None
    sites: list[str]
    results_wanted: int
    job_type: str | None
    work_mode: str | None
    is_remote: bool | None
    hours_old: int
    easy_apply: bool
    country_indeed: str | None
    linkedin_fetch_description: bool
    offset: int
    verbose: int


def resolve_effective_request(
    request: JobSearchRequest,
    defaults: RuntimePreferenceDefaults,
) -> EffectiveSearchParams:
    """Apply preference fallbacks and validation/clamping to produce adapter inputs.

    Raises ``ValueError`` for any invalid input (no search term, too many cities,
    invalid sites, invalid work mode, etc.).
    """
    effective_search_term = request.search_term or defaults.default_search_term
    if not effective_search_term:
        raise ValueError("search_term is required when no preferred roles are configured.")

    effective_cities = request.cities if request.cities is not None else defaults.default_cities
    validate_cities_count(effective_cities)

    selected_sites = resolve_sites(request.site_name, defaults=list(SITES_DEFAULT))
    validate_work_mode(request.work_mode)

    effective_country = request.country_indeed or defaults.default_country_indeed
    effective_is_remote = request.is_remote if request.is_remote is not None else defaults.prefer_remote

    return EffectiveSearchParams(
        search_term=effective_search_term,
        cities=effective_cities,
        sites=selected_sites,
        results_wanted=clamp_results_wanted(request.results_wanted),
        job_type=request.job_type,
        work_mode=request.work_mode,
        is_remote=effective_is_remote,
        hours_old=clamp_hours_old(request.hours_old),
        easy_apply=request.easy_apply,
        country_indeed=effective_country,
        linkedin_fetch_description=request.linkedin_fetch_description,
        offset=clamp_offset(request.offset),
        verbose=request.verbose,
    )


__all__ = ["EffectiveSearchParams", "resolve_effective_request"]
