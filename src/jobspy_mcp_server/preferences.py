from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from jobspy_mcp_server.guardrails import IS_REMOTE_DEFAULT


KNOWN_SENIORITY = {"junior", "mid", "senior", "lead"}
KNOWN_WORK_MODES = {"remote", "hybrid", "on-site", "onsite", "on site"}


@dataclass(frozen=True)
class SearchPreferences:
    roles: list[str]
    job_types: list[str]
    locations: list[str]
    min_salary_eur: int
    seniority: str | None


@dataclass(frozen=True)
class RuntimePreferenceDefaults:
    default_search_term: str | None
    default_cities: list[str]
    default_country_indeed: str
    prefer_remote: bool
    prefer_hybrid: bool
    min_salary_eur: int
    seniority: str | None


def _normalize_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        candidate = item.strip()
        if candidate:
            normalized.append(candidate)
    return normalized


def _parse_min_salary(raw_value: Any) -> int:
    if isinstance(raw_value, bool):
        return 0
    if isinstance(raw_value, (int, float)):
        return max(0, int(raw_value))
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if not stripped:
            return 0
        try:
            return max(0, int(float(stripped)))
        except ValueError:
            return 0
    return 0


def _normalize_seniority(raw_value: Any) -> str | None:
    if not isinstance(raw_value, str):
        return None
    candidate = raw_value.strip().lower()
    if candidate not in KNOWN_SENIORITY:
        return None
    return candidate.capitalize()


def _normalize_job_types(raw_job_types: list[str]) -> list[str]:
    normalized: list[str] = []
    for raw in raw_job_types:
        key = raw.strip().lower()
        if key not in KNOWN_WORK_MODES:
            continue
        if key in {"onsite", "on site"}:
            key = "on-site"
        if key not in normalized:
            normalized.append(key)
    return normalized


def _default_preferences() -> SearchPreferences:
    return SearchPreferences(
        roles=[],
        job_types=[],
        locations=[],
        min_salary_eur=0,
        seniority=None,
    )


def resolve_preferences_file(preferences_file: str | None = None) -> Path | None:
    if preferences_file:
        candidate = Path(preferences_file).expanduser()
        return candidate if candidate.exists() else None

    env_file = os.getenv("JOBSPY_PREFERENCES_FILE", "").strip()
    if env_file:
        candidate = Path(env_file).expanduser()
        if candidate.exists():
            return candidate

    for candidate in [Path("resume.yaml"), Path("assets/resume.yaml")]:
        if candidate.exists():
            return candidate
    return None


def load_search_preferences(preferences_file: str | None = None) -> SearchPreferences:
    file_path = resolve_preferences_file(preferences_file)
    if not file_path:
        return _default_preferences()

    try:
        with file_path.open("r", encoding="utf-8") as file_handle:
            data = yaml.safe_load(file_handle) or {}
    except (OSError, yaml.YAMLError):
        return _default_preferences()

    if not isinstance(data, dict):
        return _default_preferences()

    preferences_obj = data.get("preferences", {})
    if not isinstance(preferences_obj, dict):
        return _default_preferences()

    roles = _normalize_list(preferences_obj.get("roles"))
    job_types = _normalize_job_types(_normalize_list(preferences_obj.get("job_types")))
    locations = _normalize_list(preferences_obj.get("locations"))
    min_salary_eur = _parse_min_salary(preferences_obj.get("min_salary_eur"))
    seniority = _normalize_seniority(preferences_obj.get("seniority"))

    return SearchPreferences(
        roles=roles,
        job_types=job_types,
        locations=locations,
        min_salary_eur=min_salary_eur,
        seniority=seniority,
    )


def derive_runtime_defaults(preferences: SearchPreferences) -> RuntimePreferenceDefaults:
    # Extract cities from locations, excluding "remote" and "hybrid" keywords
    default_cities: list[str] = []
    for location in preferences.locations:
        location_key = location.lower()
        if "remote" in location_key or "hybrid" in location_key:
            continue
        if location not in default_cities:  # Avoid duplicates
            default_cities.append(location)

    default_search_term = preferences.roles[0] if preferences.roles else None

    # Auto-detect country from cities if possible (e.g., detect "Germany" from city names)
    prefers_germany = any("germany" in location.lower() for location in preferences.locations)
    default_country_indeed = "germany" if prefers_germany else "usa"

    return RuntimePreferenceDefaults(
        default_search_term=default_search_term,
        default_cities=default_cities,
        default_country_indeed=default_country_indeed,
        prefer_remote=("remote" in preferences.job_types) or (
            not preferences.job_types and IS_REMOTE_DEFAULT
        ),
        prefer_hybrid="hybrid" in preferences.job_types,
        min_salary_eur=preferences.min_salary_eur,
        seniority=preferences.seniority,
    )
