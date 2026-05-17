from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pipeline.cli import app
from pipeline.models import SubmitJobsResult


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