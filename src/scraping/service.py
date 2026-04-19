"""Scraping service orchestrator (slim)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .adapters.jobspy_adapter import JobspyAdapter
from .defaults import resolve_effective_request
from .ports import ScraperPort
from .preferences import derive_runtime_defaults, load_search_preferences
from .renderers import render_search_error, render_search_result
from .requests import JobSearchRequest

_DEFAULT_ADAPTER: ScraperPort = JobspyAdapter()


@dataclass(frozen=True)
class JobSearchResult:
    search_term: str
    jobs: list[dict[str, Any]]
    site_errors: list[dict[str, Any]] | None = None


def search_jobs(
    request: JobSearchRequest,
    *,
    adapter: ScraperPort = _DEFAULT_ADAPTER,
) -> JobSearchResult:
    preferences = load_search_preferences(request.preferences_file)
    runtime_defaults = derive_runtime_defaults(preferences)
    effective = resolve_effective_request(request, runtime_defaults)

    jobs_payload, site_errors = adapter.search(
        site_name=effective.sites,
        search_term=effective.search_term,
        cities=effective.cities,
        results_wanted=effective.results_wanted,
        job_type=effective.job_type,
        work_mode=effective.work_mode,
        is_remote=effective.is_remote,
        hours_old=effective.hours_old,
        easy_apply=effective.easy_apply,
        country_indeed=effective.country_indeed,
        linkedin_fetch_description=effective.linkedin_fetch_description,
        offset=effective.offset,
        verbose=effective.verbose,
    )

    return JobSearchResult(
        search_term=effective.search_term,
        jobs=jobs_payload,
        site_errors=site_errors,
    )


__all__ = [
    "JobSearchRequest",
    "JobSearchResult",
    "render_search_error",
    "render_search_result",
    "search_jobs",
]