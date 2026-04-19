from __future__ import annotations

from typer.testing import CliRunner

from scraping.cli import app
from scraping.service import JobSearchResult
import scraping.cli as scraping_cli

runner = CliRunner()


def test_scraping_cli_search_success(monkeypatch) -> None:
    monkeypatch.setattr(
        scraping_cli,
        "search_jobs",
        lambda _request: JobSearchResult(
            search_term="python engineer",
            jobs=[
                {
                    "role_title": "Python Engineer",
                    "company_name": "Acme",
                    "job_url": "https://example.com/jobs/1",
                }
            ],
            site_errors=None,
        ),
    )

    result = runner.invoke(app, ["python engineer", "--sites", "linkedin", "--output-format", "json"])

    assert result.exit_code == 0
    assert '"ok": true' in result.stdout.lower()
    assert 'Python Engineer' in result.stdout


def test_scraping_cli_invalid_remote_filter_returns_error() -> None:
    result = runner.invoke(app, ["python engineer", "--remote-filter", "sometimes"])

    assert result.exit_code == 1
    assert 'validation_error' in result.stdout
    assert 'remote-filter' in result.stdout
