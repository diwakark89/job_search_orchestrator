"""
Centralized search-constraint constants (ADR-001).

Adjust any value here to tighten or relax limits across the entire
MCP tool surface.  Every guardrail used in ``server.py`` and validated
in the test suite is sourced from this single file.
"""

# ── results_wanted ──────────────────────────────────────────────
RESULTS_WANTED_MIN = 1
RESULTS_WANTED_MAX = 50
RESULTS_WANTED_DEFAULT = 1

# ── hours_old (job recency window) ──────────────────────────────
HOURS_OLD_MIN = 1
HOURS_OLD_MAX = 72
HOURS_OLD_DEFAULT = 24

# ── cities (job location search) ─────────────────────────────────
CITIES_MIN = 1
CITIES_MAX = 5  # Maximum number of cities per search
CITIES_DEFAULT: list[str] = []  # Empty list means no city filtering

# ── remote preference fallback ───────────────────────────────────
# Used when no work-mode preference is configured.
IS_REMOTE_DEFAULT = True

# ── work mode ─────────────────────────────────────────────────────
WORK_MODES: list[str] = ["remote", "hybrid", "on-site"]

# ── description fetching ─────────────────────────────────────────
FETCH_DESCRIPTIONS_DEFAULT = True

# ── offset (pagination) ────────────────────────────────────────
OFFSET_MIN = 0
OFFSET_MAX = 1000
OFFSET_DEFAULT = 0

# ── site_name ───────────────────────────────────────────────────
SITES_MIN = 1
SITES_MAX = 5
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

# Kept for backward compatibility with older tests and integrations.
VALID_OUTPUT_FORMATS: list[str] = ["markdown", "json"]
OUTPUT_FORMAT_DEFAULT: str = "markdown"

