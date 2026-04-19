"""Unit tests for the scrape-to-jobs_final mapper (TEST-002)."""
from __future__ import annotations

import pytest

from service.mappers.scrape_to_jobs_final import (
    map_scraped_job_to_jobs_final,
    map_scraped_jobs_to_jobs_final,
)


def _minimal_job(**overrides) -> dict:
    base = {
        "company_name": "Acme Corp",
        "role_title": "Software Engineer",
        "job_url": "https://example.com/job/1",
        "description": "Some description",
        "job_type": "fulltime",
        "work_mode": "remote",
        "location": "Berlin",
        "source_platform": "linkedin",
        "language": "English",
        "content_hash": "abc123",
        "scraped_at": "2024-01-15T10:00:00Z",
        # These should be dropped by the mapper
        "id": "some-uuid",
        "description_source": "detail_page",
    }
    base.update(overrides)
    return base


class TestMapScrapedJobToJobsFinal:
    def test_maps_required_fields(self):
        result = map_scraped_job_to_jobs_final(_minimal_job())

        assert result["company_name"] == "Acme Corp"
        assert result["role_title"] == "Software Engineer"
        assert result["job_url"] == "https://example.com/job/1"
        assert result["description"] == "Some description"

    def test_maps_scraped_at_to_saved_at(self):
        result = map_scraped_job_to_jobs_final(_minimal_job())
        assert result["saved_at"] == "2024-01-15T10:00:00Z"
        assert "scraped_at" not in result

    def test_sets_job_status_to_scraped(self):
        result = map_scraped_job_to_jobs_final(_minimal_job())
        assert result["job_status"] == "SCRAPED"

    def test_sets_is_deleted_false(self):
        result = map_scraped_job_to_jobs_final(_minimal_job())
        assert result["is_deleted"] is False

    def test_drops_scrape_uuid_id(self):
        result = map_scraped_job_to_jobs_final(_minimal_job())
        assert "id" not in result

    def test_drops_description_source(self):
        result = map_scraped_job_to_jobs_final(_minimal_job())
        assert "description_source" not in result

    def test_maps_optional_fields(self):
        result = map_scraped_job_to_jobs_final(_minimal_job())
        assert result["job_type"] == "fulltime"
        assert result["work_mode"] == "remote"
        assert result["location"] == "Berlin"
        assert result["source_platform"] == "linkedin"
        assert result["language"] == "English"
        assert result["content_hash"] == "abc123"

    def test_missing_language_defaults_to_english(self):
        job = _minimal_job()
        del job["language"]
        result = map_scraped_job_to_jobs_final(job)
        assert result["language"] == "English"

    def test_none_optional_fields_are_none(self):
        job = _minimal_job(company_name=None, role_title=None, description=None)
        result = map_scraped_job_to_jobs_final(job)
        assert result["company_name"] is None
        assert result["role_title"] is None
        assert result["description"] is None

    def test_job_url_whitespace_stripped(self):
        job = _minimal_job(job_url="  https://example.com/job/1  ")
        result = map_scraped_job_to_jobs_final(job)
        assert result["job_url"] == "https://example.com/job/1"

    def test_missing_job_url_raises_value_error(self):
        job = _minimal_job()
        del job["job_url"]
        with pytest.raises(ValueError, match="job_url"):
            map_scraped_job_to_jobs_final(job)

    def test_empty_job_url_raises_value_error(self):
        with pytest.raises(ValueError, match="job_url"):
            map_scraped_job_to_jobs_final(_minimal_job(job_url=""))

    def test_whitespace_only_job_url_raises_value_error(self):
        with pytest.raises(ValueError, match="job_url"):
            map_scraped_job_to_jobs_final(_minimal_job(job_url="   "))


class TestMapScrapedJobsToJobsFinal:
    def test_all_valid_returns_all_mapped(self):
        jobs = [_minimal_job(job_url=f"https://example.com/job/{i}") for i in range(3)]
        mapped, errors = map_scraped_jobs_to_jobs_final(jobs)
        assert len(mapped) == 3
        assert errors == []

    def test_invalid_row_collected_in_errors(self):
        jobs = [
            _minimal_job(job_url="https://example.com/job/1"),
            _minimal_job(job_url=""),  # invalid
            _minimal_job(job_url="https://example.com/job/3"),
        ]
        mapped, errors = map_scraped_jobs_to_jobs_final(jobs)
        assert len(mapped) == 2
        assert len(errors) == 1
        assert errors[0][0] == 1  # original index

    def test_all_invalid_returns_empty_mapped(self):
        jobs = [_minimal_job(job_url="") for _ in range(3)]
        mapped, errors = map_scraped_jobs_to_jobs_final(jobs)
        assert mapped == []
        assert len(errors) == 3

    def test_empty_input_returns_empty_output(self):
        mapped, errors = map_scraped_jobs_to_jobs_final([])
        assert mapped == []
        assert errors == []
