from __future__ import annotations

import json

import pytest

from scraping.preferences import RuntimePreferenceDefaults, SearchPreferences
from scraping.service import JobSearchRequest, render_search_result, search_jobs
import scraping.service as scraping_service


def test_search_jobs_invalid_site_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Invalid site names"):
        search_jobs(JobSearchRequest(search_term="python engineer", site_name=["monster"]))


def test_search_jobs_uses_defaults_and_builds_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        scraping_service,
        "load_search_preferences",
        lambda _: SearchPreferences(
            roles=["python engineer"],
            job_types=[],
            locations=["Berlin"],
            min_salary_eur=0,
            seniority=None,
        ),
    )
    monkeypatch.setattr(
        scraping_service,
        "derive_runtime_defaults",
        lambda _: RuntimePreferenceDefaults(
            default_search_term="python engineer",
            default_cities=["Berlin"],
            default_country_indeed="germany",
            prefer_remote=True,
            prefer_hybrid=False,
            min_salary_eur=0,
            seniority=None,
        ),
    )

    # Inject a mock adapter so the test does not touch the vendored scraper.
    class _MockAdapter:
        def search(self, **_: object) -> tuple[list[dict], list[dict] | None]:
            return (
                [{"role_title": "Python Engineer", "company_name": "Acme", "job_url": "https://example.com/jobs/1"}],
                [{"site": "linkedin", "message": "partial failure"}],
            )

    result = search_jobs(JobSearchRequest(site_name=["linkedin"]), adapter=_MockAdapter())

    assert result.search_term == "python engineer"
    assert result.jobs == [
        {"role_title": "Python Engineer", "company_name": "Acme", "job_url": "https://example.com/jobs/1"}
    ]
    rendered = render_search_result(result, output_format="json", indent=2)
    payload = json.loads(rendered)
    assert payload["ok"] is True
    assert payload["jobs"][0]["role_title"] == "Python Engineer"
    assert payload["site_errors"][0]["site"] == "linkedin"
