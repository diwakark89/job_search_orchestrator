"""MCP interface contract tests for the orchestrator mcp_interface.server module.

Migrated and adapted from jobs-search-mcp-server/test/test_jobspy_mcp.py.
Import paths have been normalised to pythonpath=src.
Patch targets updated to match the adapter-based service layer.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

from mcp_interface.server import (
    get_job_search_tips,
    get_supported_countries,
    get_supported_sites,
    mcp,
    scrape_jobs_tool,
)
from jobspy_mcp_server.json_output import build_jobs_json_payload
from scraping.guardrails import (
    CITIES_MAX,
    HOURS_OLD_DEFAULT,
    HOURS_OLD_MAX,
    HOURS_OLD_MIN,
    OFFSET_MAX,
    OFFSET_MIN,
    RESULTS_WANTED_DEFAULT,
    RESULTS_WANTED_MAX,
    RESULTS_WANTED_MIN,
    SITES_MAX,
    VALID_SITES,
    WORK_MODES,
)

# ── helpers ──────────────────────────────────────────────────────────────────

_ADAPTER_PATCH = "scraping.adapters.jobspy_adapter._scrape_jobs"


def _parse_envelope(payload: str) -> dict:
    parsed = json.loads(payload)
    assert set(parsed.keys()) == {"ok", "jobs", "error"}
    return parsed


def _parse_metadata_envelope(payload: str, expected_keys: set[str]) -> dict:
    parsed = json.loads(payload)
    assert parsed["ok"] is True
    assert parsed["error"] is None
    assert set(parsed.keys()) == expected_keys | {"ok", "error"}
    return parsed


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_context() -> Mock:
    ctx = Mock()

    async def async_noop(*args, **kwargs):
        pass

    ctx.info = MagicMock(side_effect=async_noop)
    ctx.warning = MagicMock(side_effect=async_noop)
    ctx.error = MagicMock(side_effect=async_noop)
    ctx.report_progress = MagicMock(side_effect=async_noop)
    return ctx


@pytest.fixture
def sample_jobs_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "title": "Python Developer",
                "company": "Tech Corp",
                "location": "San Francisco, CA",
                "site": "indeed",
                "job_type": "fulltime",
                "date_posted": "2024-01-15",
                "min_amount": 80000,
                "max_amount": 120000,
                "currency": "USD",
                "interval": "yearly",
                "is_remote": False,
                "job_url": "https://indeed.com/job/123",
                "description": "We are looking for a Python developer...",
            },
            {
                "title": "Remote Data Scientist",
                "company": "AI Startup",
                "location": "Remote",
                "site": "linkedin",
                "job_type": "fulltime",
                "date_posted": "2024-01-16",
                "min_amount": None,
                "max_amount": None,
                "currency": None,
                "interval": None,
                "is_remote": True,
                "job_url": "https://linkedin.com/job/456",
                "description": "Join our AI team as a data scientist...",
            },
        ]
    )


# ── MCP envelope tests ────────────────────────────────────────────────────────

class TestMCPEnvelopeBehavior:
    @patch(_ADAPTER_PATCH)
    def test_scrape_jobs_tool_success_returns_envelope(self, mock_scrape_jobs, mock_context, sample_jobs_df):
        mock_scrape_jobs.return_value = sample_jobs_df
        result = asyncio.run(scrape_jobs_tool(search_term="python developer", cities=["San Francisco"], ctx=mock_context))
        payload = _parse_envelope(result)
        assert payload["ok"] is True
        assert payload["error"] is None
        assert len(payload["jobs"]) == 2
        assert payload["jobs"][0]["role_title"] == "Python Developer"
        assert payload["jobs"][0]["company_name"] == "Tech Corp"

    @patch(_ADAPTER_PATCH)
    def test_scrape_jobs_tool_no_results_returns_success_empty_jobs(self, mock_scrape_jobs, mock_context):
        mock_scrape_jobs.return_value = pd.DataFrame()
        result = asyncio.run(scrape_jobs_tool(search_term="nonexistent job", ctx=mock_context))
        payload = _parse_envelope(result)
        assert payload["ok"] is True
        assert payload["jobs"] == []
        assert payload["error"] is None

    @patch(_ADAPTER_PATCH)
    def test_scrape_jobs_tool_returns_site_errors_when_present(self, mock_scrape_jobs, mock_context):
        jobs_df = pd.DataFrame()
        jobs_df.attrs["site_errors"] = [{"site": "linkedin", "city": "Berlin", "message": "blocked"}]
        mock_scrape_jobs.return_value = jobs_df

        result = asyncio.run(scrape_jobs_tool(search_term="python", ctx=mock_context))
        payload = json.loads(result)

        assert payload["ok"] is True
        assert payload["jobs"] == []
        assert payload["error"] is None
        assert payload["site_errors"][0]["site"] == "linkedin"
        assert payload["site_error_summary"][0]["site"] == "linkedin"

    @patch(_ADAPTER_PATCH)
    def test_scrape_jobs_tool_error_returns_runtime_error(self, mock_scrape_jobs, mock_context):
        mock_scrape_jobs.side_effect = Exception("Network error")
        result = asyncio.run(scrape_jobs_tool(search_term="python developer", ctx=mock_context))
        payload = _parse_envelope(result)
        assert payload["ok"] is False
        assert payload["jobs"] == []
        assert payload["error"]["code"] == "runtime_error"
        assert "Network error" in payload["error"]["message"]

    def test_invalid_sites_return_validation_error(self, mock_context):
        result = asyncio.run(
            scrape_jobs_tool(search_term="python developer", site_name=["invalid_site"], ctx=mock_context)
        )
        payload = _parse_envelope(result)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "validation_error"
        assert "Invalid site names" in payload["error"]["message"]

    def test_get_supported_countries(self):
        payload = _parse_metadata_envelope(
            get_supported_countries(),
            {"countries", "usage_note", "popular_aliases"},
        )
        country_keys = {c["key"] for c in payload["countries"]}
        assert "USA" in country_keys
        assert "CANADA" in country_keys
        assert "usa" in payload["popular_aliases"]

    def test_get_supported_sites(self):
        payload = _parse_metadata_envelope(get_supported_sites(), {"sites", "usage_tips"})
        site_names = {s["name"] for s in payload["sites"]}
        assert "linkedin" in site_names
        assert "indeed" in site_names
        assert "stepstone" in site_names

    def test_get_job_search_tips(self):
        payload = _parse_metadata_envelope(get_job_search_tips(), {"tips"})
        assert "search_term_optimization" in payload["tips"]
        assert "performance" in payload["tips"]


def test_server_structure():
    assert mcp is not None
    assert hasattr(mcp, "run")


# ── guardrail tests ─────────────────────────────────────────────────────────

class TestInputGuardrails:
    @patch(_ADAPTER_PATCH)
    def test_results_wanted_clamped_to_min(self, mock_scrape, mock_context):
        mock_scrape.return_value = pd.DataFrame()
        asyncio.run(scrape_jobs_tool(search_term="test", ctx=mock_context, results_wanted=0))
        assert mock_scrape.call_args.kwargs["results_wanted"] == RESULTS_WANTED_MIN

    @patch(_ADAPTER_PATCH)
    def test_results_wanted_clamped_to_max(self, mock_scrape, mock_context):
        mock_scrape.return_value = pd.DataFrame()
        asyncio.run(scrape_jobs_tool(search_term="test", ctx=mock_context, results_wanted=9999))
        assert mock_scrape.call_args.kwargs["results_wanted"] == RESULTS_WANTED_MAX

    @patch(_ADAPTER_PATCH)
    def test_hours_old_clamped_to_min(self, mock_scrape, mock_context):
        mock_scrape.return_value = pd.DataFrame()
        asyncio.run(scrape_jobs_tool(search_term="test", ctx=mock_context, hours_old=0))
        assert mock_scrape.call_args.kwargs["hours_old"] == HOURS_OLD_MIN

    @patch(_ADAPTER_PATCH)
    def test_hours_old_clamped_to_max(self, mock_scrape, mock_context):
        mock_scrape.return_value = pd.DataFrame()
        asyncio.run(scrape_jobs_tool(search_term="test", ctx=mock_context, hours_old=200))
        assert mock_scrape.call_args.kwargs["hours_old"] == HOURS_OLD_MAX

    @patch(_ADAPTER_PATCH)
    def test_hours_old_default_is_24(self, mock_scrape, mock_context):
        mock_scrape.return_value = pd.DataFrame()
        asyncio.run(scrape_jobs_tool(search_term="test", ctx=mock_context))
        assert mock_scrape.call_args.kwargs["hours_old"] == HOURS_OLD_DEFAULT

    @patch(_ADAPTER_PATCH)
    def test_offset_clamped_to_min(self, mock_scrape, mock_context):
        mock_scrape.return_value = pd.DataFrame()
        asyncio.run(scrape_jobs_tool(search_term="test", ctx=mock_context, offset=-1))
        assert mock_scrape.call_args.kwargs["offset"] == OFFSET_MIN

    @patch(_ADAPTER_PATCH)
    def test_offset_clamped_to_max(self, mock_scrape, mock_context):
        mock_scrape.return_value = pd.DataFrame()
        asyncio.run(scrape_jobs_tool(search_term="test", ctx=mock_context, offset=5000))
        assert mock_scrape.call_args.kwargs["offset"] == OFFSET_MAX

    def test_site_name_empty_rejected(self, mock_context):
        result = asyncio.run(scrape_jobs_tool(search_term="test", ctx=mock_context, site_name=[]))
        payload = _parse_envelope(result)
        assert payload["ok"] is False
        assert "At least 1 site" in payload["error"]["message"]

    def test_site_name_too_many_rejected(self, mock_context):
        result = asyncio.run(
            scrape_jobs_tool(search_term="test", ctx=mock_context, site_name=VALID_SITES[: SITES_MAX + 1])
        )
        payload = _parse_envelope(result)
        assert payload["ok"] is False
        assert f"Maximum {SITES_MAX} sites" in payload["error"]["message"]

    def test_work_mode_invalid_rejected(self, mock_context):
        result = asyncio.run(scrape_jobs_tool(search_term="test", ctx=mock_context, work_mode="office"))
        payload = _parse_envelope(result)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "validation_error"
        assert "Invalid work_mode" in payload["error"]["message"]

    @patch(_ADAPTER_PATCH)
    def test_work_mode_valid_forwarded(self, mock_scrape, mock_context):
        mock_scrape.return_value = pd.DataFrame()
        asyncio.run(scrape_jobs_tool(search_term="test", ctx=mock_context, work_mode=WORK_MODES[0]))
        assert mock_scrape.call_args.kwargs["work_mode"] == WORK_MODES[0]


# ── normalised payload tests ─────────────────────────────────────────────────

class TestNormalizedJobsPayload:
    EXPECTED_JOB_KEYS = {
        "id",
        "company_name",
        "role_title",
        "description",
        "description_source",
        "job_type",
        "job_url",
        "location",
        "work_mode",
        "language",
        "source_platform",
        "scraped_at",
        "content_hash",
    }

    @patch(_ADAPTER_PATCH)
    def test_job_payload_has_expected_fields(self, mock_scrape, mock_context, sample_jobs_df):
        mock_scrape.return_value = sample_jobs_df
        result = asyncio.run(scrape_jobs_tool(search_term="android", ctx=mock_context))
        jobs = _parse_envelope(result)["jobs"]
        assert len(jobs) == 2
        for job in jobs:
            assert set(job.keys()) == self.EXPECTED_JOB_KEYS

    def test_job_type_inferred_from_description_when_missing(self):
        jobs_df = pd.DataFrame(
            [
                {
                    "title": "Software Engineer",
                    "company": "Acme",
                    "site": "linkedin",
                    "job_url": "https://www.linkedin.com/jobs/view/1234567890",
                    "description": "This is a full time role with backend ownership.",
                    "description_source": "detail_page",
                    "location": "Berlin",
                    "job_type": None,
                    "work_mode": None,
                }
            ]
        )
        payload = build_jobs_json_payload(jobs_df)
        assert payload[0]["job_type"] == "fulltime"

    def test_work_mode_normalized_in_output(self):
        jobs_df = pd.DataFrame(
            [
                {
                    "title": "Platform Engineer",
                    "company": "Acme",
                    "site": "indeed",
                    "job_url": "https://indeed.com/viewjob?jk=abcdef",
                    "description": "Role description",
                    "description_source": "listing api",
                    "location": "Munich",
                    "job_type": "contract",
                    "work_mode": "Work from office",
                }
            ]
        )
        payload = build_jobs_json_payload(jobs_df)
        assert payload[0]["work_mode"] == "on-site"
