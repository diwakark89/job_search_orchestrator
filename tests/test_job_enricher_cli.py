from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from job_enricher.cli import app
from service.enricher import EnrichmentBucket, EnrichmentSummary


runner = CliRunner()


def test_cli_enrich_dry_run_success() -> None:
    with (
        patch("job_enricher.cli.load_config"),
        patch("job_enricher.cli.load_copilot_config"),
        patch("job_enricher.cli.PostgrestClient") as postgrest_cls,
        patch("job_enricher.cli.SupabaseRepository") as repo_cls,
        patch("job_enricher.cli.CopilotClient") as copilot_cls,
        patch("job_enricher.cli.enrich_jobs") as enrich_jobs_mock,
    ):
        postgrest_cls.return_value = MagicMock()
        repo_cls.return_value = MagicMock()
        copilot_cls.return_value = MagicMock()
        enrich_jobs_mock.return_value = EnrichmentSummary(
            processed=EnrichmentBucket(count=4, ids=["id-1", "id-2", "id-3", "id-4"]),
            enriched=EnrichmentBucket(count=3, ids=["id-1", "id-2", "id-3"]),
            skipped=EnrichmentBucket(count=1, ids=["id-4"]),
            failed=EnrichmentBucket(count=0, ids=[]),
            errors=[],
        )

        result = runner.invoke(app, ["--limit", "4", "--dry-run"])

    assert result.exit_code == 0
    assert "processed=4" in result.stdout
    enrich_jobs_mock.assert_called_once()
