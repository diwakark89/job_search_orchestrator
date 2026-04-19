from __future__ import annotations

"""Orchestrator-owned search-constraint constants (ADR-001).

These constants are defined here and owned by the orchestrator.  They are NOT
re-exported from the vendored package so that changes to the vendored package
do not silently alter the orchestrator's guardrails.

Adjust any value here to tighten or relax limits across the entire service
and MCP tool surface.
"""

# ── results_wanted ──────────────────────────────────────────────
RESULTS_WANTED_MIN: int = 1
RESULTS_WANTED_MAX: int = 50
RESULTS_WANTED_DEFAULT: int = 1

# ── hours_old (job recency window) ──────────────────────────────
HOURS_OLD_MIN: int = 1
HOURS_OLD_MAX: int = 72
HOURS_OLD_DEFAULT: int = 24

# ── cities (job location search) ─────────────────────────────────
CITIES_MIN: int = 1
CITIES_MAX: int = 5  # Maximum number of cities per search
CITIES_DEFAULT: list[str] = []  # Empty list means no city filtering

# ── remote preference fallback ───────────────────────────────────
IS_REMOTE_DEFAULT: bool = True

# ── work mode ─────────────────────────────────────────────────────
WORK_MODES: list[str] = ["remote", "hybrid", "on-site"]

# ── description fetching ─────────────────────────────────────────
FETCH_DESCRIPTIONS_DEFAULT: bool = True

# ── offset (pagination) ────────────────────────────────────────
OFFSET_MIN: int = 0
OFFSET_MAX: int = 1000
OFFSET_DEFAULT: int = 0

# ── site_name ───────────────────────────────────────────────────
SITES_MIN: int = 1
SITES_MAX: int = 5
SITES_DEFAULT: list[str] = ["linkedin"]
VALID_SITES: list[str] = [
    "linkedin",
    "indeed",
    "glassdoor",
    "zip_recruiter",
    "google",
    "bayt",
    "naukri",
    "stepstone",
    "xing",
    "berlin_startup_jobs",
    "welcome_to_the_jungle",
    "eu_startups",
    "join",
]

# ── output formats ──────────────────────────────────────────────
VALID_OUTPUT_FORMATS: list[str] = ["markdown", "json"]
OUTPUT_FORMAT_DEFAULT: str = "json"

