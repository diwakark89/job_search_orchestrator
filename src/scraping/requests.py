"""Pydantic request model for the scraping service.

Re-exported from ``scraping.service`` for backward compatibility — existing
callers may continue to ``from scraping.service import JobSearchRequest``.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .guardrails import (
    FETCH_DESCRIPTIONS_DEFAULT,
    HOURS_OLD_DEFAULT,
    OFFSET_DEFAULT,
    RESULTS_WANTED_DEFAULT,
)


class JobSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search_term: str | None = None
    cities: list[str] | None = None
    site_name: list[str] | None = None
    results_wanted: int = RESULTS_WANTED_DEFAULT
    job_type: str | None = None
    work_mode: str | None = None
    is_remote: bool | None = None
    hours_old: int = HOURS_OLD_DEFAULT
    easy_apply: bool = False
    country_indeed: str | None = None
    linkedin_fetch_description: bool = FETCH_DESCRIPTIONS_DEFAULT
    offset: int = OFFSET_DEFAULT
    preferences_file: str | None = None
    verbose: int = 0


__all__ = ["JobSearchRequest"]
