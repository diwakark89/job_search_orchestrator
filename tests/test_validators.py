"""Unit tests for validators.py — no network, no environment required."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow running without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.validators import (
    validate_jobs_final_rows,
    validate_shared_links_rows,
)


# ── jobs_final ────────────────────────────────────────────────────────────────

class TestJobsFinalValidator:
    def test_minimal_valid_row(self):
        rows = [{"company_name": "Acme"}]
        result = validate_jobs_final_rows(rows)
        assert len(result) == 1
        assert result[0]["company_name"] == "Acme"

    def test_job_id_optional(self):
        """job_id defaults to None (DB generates it via gen_random_uuid)."""
        rows = [{"company_name": "Acme"}]
        result = validate_jobs_final_rows(rows)
        assert "job_id" not in result[0]

    def test_explicit_job_id_preserved(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000001"}]
        result = validate_jobs_final_rows(rows)
        assert result[0]["job_id"] == "aaaaaaaa-0000-0000-0000-000000000001"

    def test_defaults_applied(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000002"}]
        result = validate_jobs_final_rows(rows)
        assert result[0].get("match_score") == 90
        assert result[0].get("language") == "English"
        assert result[0].get("is_deleted") is False
        assert result[0].get("job_status") == "SAVED"

    def test_display_form_normalised_to_uppercase(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000003", "job_status": "Resume-Rejected"}]
        result = validate_jobs_final_rows(rows)
        assert result[0]["job_status"] == "RESUME_REJECTED"

    def test_uppercase_preserved(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000004", "job_status": "INTERVIEW_REJECTED"}]
        result = validate_jobs_final_rows(rows)
        assert result[0]["job_status"] == "INTERVIEW_REJECTED"

    def test_case_insensitive_status_accepted(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000008", "job_status": "saved"}]
        result = validate_jobs_final_rows(rows)
        assert result[0]["job_status"] == "SAVED"

    def test_invalid_job_status(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000005", "job_status": "UNKNOWN_STATUS"}]
        with pytest.raises(Exception):
            validate_jobs_final_rows(rows)

    def test_scraped_job_status_valid(self):
        rows = [{"job_url": "https://example.com/1", "job_status": "SCRAPED"}]
        result = validate_jobs_final_rows(rows)
        assert result[0]["job_status"] == "SCRAPED"

    def test_enriched_job_status_valid(self):
        rows = [{"job_url": "https://example.com/2", "job_status": "ENRICHED"}]
        result = validate_jobs_final_rows(rows)
        assert result[0]["job_status"] == "ENRICHED"

    def test_epoch_ms_timestamp_normalised(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000006", "saved_at": 1743674410421}]
        result = validate_jobs_final_rows(rows)
        assert result[0]["saved_at"].endswith("Z"), "saved_at must be ISO-8601 UTC"

    def test_extra_field_rejected(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000007", "unknown_column": "bad"}]
        with pytest.raises(Exception):
            validate_jobs_final_rows(rows)

    def test_all_display_forms_normalise_to_uppercase(self):
        cases = {
            "Saved": "SAVED",
            "Applied": "APPLIED",
            "Interview": "INTERVIEW",
            "Interviewing": "INTERVIEWING",
            "Offer": "OFFER",
            "Resume-Rejected": "RESUME_REJECTED",
            "Interview-Rejected": "INTERVIEW_REJECTED",
        }
        for display, expected in cases.items():
            rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000009", "job_status": display}]
            result = validate_jobs_final_rows(rows)
            assert result[0]["job_status"] == expected, f"{display} should normalise to {expected}"

    def test_valid_decision(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000020", "decision": "AUTO_APPROVE"}]
        result = validate_jobs_final_rows(rows)
        assert result[0]["decision"] == "AUTO_APPROVE"

    def test_invalid_decision(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000021", "decision": "APPROVE"}]
        with pytest.raises(Exception):
            validate_jobs_final_rows(rows)

    def test_valid_user_action(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000030", "user_action": "APPROVED"}]
        result = validate_jobs_final_rows(rows)
        assert result[0]["user_action"] == "APPROVED"

    def test_invalid_user_action(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000031", "user_action": "MAYBE"}]
        with pytest.raises(Exception):
            validate_jobs_final_rows(rows)

    def test_approved_at_epoch_normalised(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000032", "approved_at": 1743674410421}]
        result = validate_jobs_final_rows(rows)
        assert result[0]["approved_at"].endswith("Z")

    def test_enrichment_fields_accepted(self):
        rows = [{
            "job_id": "aaaaaaaa-0000-0000-0000-000000000040",
            "tech_stack": ["Python", "FastAPI"],
            "experience_level": "Senior",
            "remote_type": "Hybrid",
            "visa_sponsorship": False,
            "english_friendly": True,
        }]
        result = validate_jobs_final_rows(rows)
        assert result[0]["tech_stack"] == ["Python", "FastAPI"]

    def test_source_platform_allowed(self):
        rows = [{"job_url": "https://example.com/3", "source_platform": "indeed"}]
        result = validate_jobs_final_rows(rows)
        assert result[0]["source_platform"] == "indeed"


# ── shared_links ──────────────────────────────────────────────────────────────

class TestSharedLinksValidator:
    def test_minimal_valid_row(self):
        rows = [{"url": "https://www.linkedin.com/jobs/view/123"}]
        result = validate_shared_links_rows(rows)
        assert result[0]["source"] == "android-share-intent"
        assert result[0]["url"] == "https://www.linkedin.com/jobs/view/123"

    def test_valid_source_web_extension(self):
        rows = [{"url": "https://example.com", "source": "web-extension"}]
        validate_shared_links_rows(rows)

    def test_invalid_source_raises(self):
        rows = [{"url": "https://example.com", "source": "telegram-bot"}]
        with pytest.raises(Exception):
            validate_shared_links_rows(rows)

    def test_missing_url_raises(self):
        rows = [{"source": "manual"}]
        with pytest.raises(Exception):
            validate_shared_links_rows(rows)

    def test_extra_field_rejected(self):
        rows = [{"url": "https://example.com", "extra": "bad"}]
        with pytest.raises(Exception):
            validate_shared_links_rows(rows)
