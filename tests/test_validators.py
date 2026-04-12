"""Unit tests for validators.py — no network, no environment required."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow running without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.validators import (
    validate_job_approvals_rows,
    validate_job_decisions_rows,
    validate_job_metrics_patch,
    validate_jobs_enriched_rows,
    validate_jobs_final_rows,
    validate_jobs_raw_rows,
    validate_shared_links_rows,
)


# ── jobs_final ────────────────────────────────────────────────────────────────

class TestJobsFinalValidator:
    def test_minimal_valid_row(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000001"}]
        result = validate_jobs_final_rows(rows)
        assert len(result) == 1
        assert result[0]["job_id"] == "aaaaaaaa-0000-0000-0000-000000000001"

    def test_defaults_applied(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000002"}]
        result = validate_jobs_final_rows(rows)
        assert result[0].get("match_score") == 90
        assert result[0].get("language") == "English"
        assert result[0].get("is_deleted") is False

    def test_valid_job_status_display_form(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000003", "job_status": "Resume-Rejected"}]
        result = validate_jobs_final_rows(rows)
        assert result[0]["job_status"] == "Resume-Rejected"

    def test_valid_job_status_legacy_uppercase(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000004", "job_status": "INTERVIEW_REJECTED"}]
        validate_jobs_final_rows(rows)  # should not raise

    def test_invalid_job_status(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000005", "job_status": "UNKNOWN_STATUS"}]
        with pytest.raises(Exception):
            validate_jobs_final_rows(rows)

    def test_epoch_ms_timestamp_normalised(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000006", "saved_at": 1743674410421}]
        result = validate_jobs_final_rows(rows)
        assert result[0]["saved_at"].endswith("Z"), "saved_at must be ISO-8601 UTC"

    def test_extra_field_rejected(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000007", "unknown_column": "bad"}]
        with pytest.raises(Exception):
            validate_jobs_final_rows(rows)

    def test_missing_job_id_raises(self):
        rows = [{"company_name": "Acme"}]
        with pytest.raises(Exception):
            validate_jobs_final_rows(rows)

    def test_all_job_status_display_values(self):
        allowed = ["Saved", "Applied", "Interview", "Interviewing", "Offer", "Resume-Rejected", "Interview-Rejected"]
        for status in allowed:
            rows = [{"job_id": f"aaaaaaaa-0000-0000-0000-{str(allowed.index(status)).zfill(12)}", "job_status": status}]
            validate_jobs_final_rows(rows)  # must not raise


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


# ── jobs_raw ──────────────────────────────────────────────────────────────────

class TestJobsRawValidator:
    VALID = {
        "company_name": "Acme",
        "role_title": "Engineer",
        "job_url": "https://example.com/job/1",
    }

    def test_valid_minimal_row(self):
        result = validate_jobs_raw_rows([self.VALID])
        assert result[0]["company_name"] == "Acme"

    def test_defaults(self):
        result = validate_jobs_raw_rows([self.VALID])
        assert result[0].get("job_status") == "SCRAPED"
        assert result[0].get("is_deleted") is False

    def test_invalid_job_status(self):
        row = {**self.VALID, "job_status": "GHOSTED"}
        with pytest.raises(Exception):
            validate_jobs_raw_rows([row])

    def test_scraped_job_status_valid(self):
        row = {**self.VALID, "job_status": "SCRAPED"}
        result = validate_jobs_raw_rows([row])
        assert result[0]["job_status"] == "SCRAPED"

    def test_enriched_job_status_valid(self):
        row = {**self.VALID, "job_status": "ENRICHED"}
        result = validate_jobs_raw_rows([row])
        assert result[0]["job_status"] == "ENRICHED"

    def test_pipeline_stage_rejected(self):
        row = {**self.VALID, "pipeline_stage": "SCRAPED"}
        with pytest.raises(Exception):
            validate_jobs_raw_rows([row])

    def test_scrape_run_id_rejected(self):
        row = {**self.VALID, "scrape_run_id": "run-001"}
        with pytest.raises(Exception):
            validate_jobs_raw_rows([row])

    def test_source_platform_allowed(self):
        row = {**self.VALID, "source_platform": "indeed"}
        result = validate_jobs_raw_rows([row])
        assert result[0]["source_platform"] == "indeed"

    def test_extra_field_rejected(self):
        row = {**self.VALID, "bogus": "value"}
        with pytest.raises(Exception):
            validate_jobs_raw_rows([row])


# ── jobs_enriched ─────────────────────────────────────────────────────────────

class TestJobsEnrichedValidator:
    def test_minimal_valid(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000010"}]
        result = validate_jobs_enriched_rows(rows)
        assert result[0]["job_id"] == "aaaaaaaa-0000-0000-0000-000000000010"

    def test_full_row(self):
        rows = [{
            "job_id": "aaaaaaaa-0000-0000-0000-000000000011",
            "tech_stack": ["Kotlin", "Room"],
            "experience_level": "Senior",
            "remote_type": "Hybrid",
            "visa_sponsorship": False,
            "english_friendly": True,
        }]
        result = validate_jobs_enriched_rows(rows)
        assert result[0]["tech_stack"] == ["Kotlin", "Room"]

    def test_extra_field_rejected(self):
        rows = [{"job_id": "aaaaaaaa-0000-0000-0000-000000000012", "extra": "bad"}]
        with pytest.raises(Exception):
            validate_jobs_enriched_rows(rows)


# ── job_decisions ─────────────────────────────────────────────────────────────

class TestJobDecisionsValidator:
    VALID = {"job_id": "aaaaaaaa-0000-0000-0000-000000000020", "decision": "AUTO_APPROVE"}

    def test_valid_auto_approve(self):
        result = validate_job_decisions_rows([self.VALID])
        assert result[0]["decision"] == "AUTO_APPROVE"

    def test_valid_review(self):
        validate_job_decisions_rows([{**self.VALID, "decision": "REVIEW"}])

    def test_valid_reject(self):
        validate_job_decisions_rows([{**self.VALID, "decision": "REJECT"}])

    def test_invalid_decision(self):
        with pytest.raises(Exception):
            validate_job_decisions_rows([{**self.VALID, "decision": "APPROVE"}])

    def test_with_optional_fields(self):
        rows = [{**self.VALID, "match_score": 0.87, "reason": "Good match", "confidence": 0.91}]
        result = validate_job_decisions_rows(rows)
        assert result[0]["match_score"] == 0.87


# ── job_approvals ─────────────────────────────────────────────────────────────

class TestJobApprovalsValidator:
    VALID = {
        "job_id": "aaaaaaaa-0000-0000-0000-000000000030",
        "decision_id": "bbbbbbbb-0000-0000-0000-000000000001",
        "user_action": "APPROVED",
    }

    def test_valid_approved(self):
        result = validate_job_approvals_rows([self.VALID])
        assert result[0]["user_action"] == "APPROVED"

    def test_valid_rejected(self):
        validate_job_approvals_rows([{**self.VALID, "user_action": "REJECTED"}])

    def test_valid_pending(self):
        validate_job_approvals_rows([{**self.VALID, "user_action": "PENDING"}])

    def test_invalid_user_action(self):
        with pytest.raises(Exception):
            validate_job_approvals_rows([{**self.VALID, "user_action": "MAYBE"}])

    def test_epoch_approved_at_normalised(self):
        rows = [{**self.VALID, "approved_at": 1743674410421}]
        result = validate_job_approvals_rows(rows)
        assert result[0]["approved_at"].endswith("Z")

    def test_missing_decision_id_raises(self):
        row = {"job_id": self.VALID["job_id"], "user_action": "APPROVED"}
        with pytest.raises(Exception):
            validate_job_approvals_rows([row])


# ── job_metrics ───────────────────────────────────────────────────────────────

class TestJobMetricsValidator:
    def test_valid_full_patch(self):
        payload = {"total_scraped": 100, "total_approved": 20, "total_rejected": 60}
        result = validate_job_metrics_patch(payload)
        assert result["total_scraped"] == 100

    def test_partial_patch_allowed(self):
        payload = {"total_scraped": 50}
        result = validate_job_metrics_patch(payload)
        assert "total_approved" not in result

    def test_negative_counter_rejected(self):
        with pytest.raises(Exception):
            validate_job_metrics_patch({"total_scraped": -1})

    def test_zero_counter_allowed(self):
        validate_job_metrics_patch({"total_scraped": 0})

    def test_extra_field_rejected(self):
        with pytest.raises(Exception):
            validate_job_metrics_patch({"total_scraped": 10, "bogus": 99})

    def test_epoch_updated_at_normalised(self):
        payload = {"total_scraped": 5, "updated_at": 1743674410421}
        result = validate_job_metrics_patch(payload)
        assert result["updated_at"].endswith("Z")
