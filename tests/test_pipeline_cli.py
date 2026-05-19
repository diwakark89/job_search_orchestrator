from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pipeline.cli import app
from pipeline.models import SubmitJobsResult
from scraping.service import JobSearchResult


runner = CliRunner()


def test_pipeline_cli_submit_outputs_expected_payload_without_shared_links_count() -> None:
    fake_result = SubmitJobsResult(
        submitted_row_count=1,
        accepted_ids=["id-1"],
        accepted_urls=["https://example.com/jobs/1"],
        rejected_row_indexes=[],
        errors=[],
        jobs_final_row_count=1,
    )

    with (
        patch("pipeline.cli.load_config", MagicMock(return_value=object())),
        patch("pipeline.cli.PostgrestClient", MagicMock(return_value=object())),
        patch("pipeline.cli.SupabaseRepository", MagicMock(return_value=object())),
        patch("pipeline.cli.submit_jobs_for_enrichment", MagicMock(return_value=fake_result)),
    ):
        with runner.isolated_filesystem():
            payload_file = Path("payload.json")
            payload_file.write_text(
                json.dumps({"jobs": [{"job_url": "https://example.com/jobs/1"}]}),
                encoding="utf-8",
            )
            result = runner.invoke(app, ["submit", str(payload_file)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["submitted_row_count"] == 1
    assert payload["accepted"] == {"count": 1, "ids": ["id-1"]}
    assert payload["queued"] == {"count": 1, "ids": ["id-1"]}
    assert payload["rejected_row_indexes"] == []
    assert payload["errors"] == []
    assert payload["jobs_final_row_count"] == 1
    assert "shared_links_row_count" not in payload


def test_pipeline_cli_daily_submit_applies_daily_cap_and_outputs_run_summary() -> None:
    scraped_jobs = [{"job_url": f"https://example.com/jobs/{i}"} for i in range(1, 16)]
    fake_search_result = JobSearchResult(
        search_term="python developer",
        jobs=scraped_jobs,
        site_errors=[{"site": "indeed", "error": "rate_limited"}],
    )
    fake_submit_result = SubmitJobsResult(
        submitted_row_count=10,
        accepted_ids=[f"id-{i}" for i in range(1, 11)],
        accepted_urls=[job["job_url"] for job in scraped_jobs[:10]],
        rejected_row_indexes=[],
        errors=[],
        jobs_final_row_count=10,
    )

    with (
        patch("pipeline.cli.load_config", MagicMock(return_value=object())),
        patch("pipeline.cli.PostgrestClient", MagicMock(return_value=object())),
        patch("pipeline.cli.SupabaseRepository", MagicMock(return_value=object())),
        patch("pipeline.cli.search_jobs", MagicMock(return_value=fake_search_result)),
        patch("pipeline.cli.submit_jobs_for_enrichment", MagicMock(return_value=fake_submit_result)) as submit_mock,
    ):
        result = runner.invoke(
            app,
            [
                "daily-submit",
                "--search-term",
                "python developer",
                "--sites",
                "linkedin,indeed",
                "--requested-results",
                "25",
                "--daily-cap",
                "10",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["run_id"].startswith("daily-")
    assert payload["search_term"] == "python developer"
    assert payload["scraped_count"] == 15
    assert payload["submitted_count"] == 10
    assert payload["daily_cap"] == 10
    assert payload["accepted"]["count"] == 10
    assert payload["jobs_final_row_count"] == 10
    assert payload["site_errors"] == [{"site": "indeed", "error": "rate_limited"}]

    submitted_rows = submit_mock.call_args.kwargs["rows"]
    assert len(submitted_rows) == 10
    assert submitted_rows[0]["job_url"].endswith("/1")
    assert submitted_rows[-1]["job_url"].endswith("/10")