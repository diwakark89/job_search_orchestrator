from __future__ import annotations

import sys
from pathlib import Path

from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import main as main_cli


runner = CliRunner()


def test_root_help_shows_new_commands() -> None:
    result = runner.invoke(main_cli.app, ["--help"])

    assert result.exit_code == 0
    assert "job-manage" in result.stdout
    assert "job-search" in result.stdout
    assert "scraping" not in result.stdout


def test_job_manage_help_shows_subgroups() -> None:
    result = runner.invoke(main_cli.app, ["job-manage", "--help"])

    assert result.exit_code == 0
    assert "table" in result.stdout
    assert "pipeline" in result.stdout
    assert "enricher" in result.stdout


def test_job_search_delegates_to_scraping_command(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_cmd_search(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(main_cli, "cmd_search", fake_cmd_search)

    result = runner.invoke(
        main_cli.app,
        [
            "job-search",
            "software engineer",
            "--cities",
            "Munich,Berlin",
            "--sites",
            "indeed,linkedin",
            "--results",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert captured["search_term"] == "software engineer"
    assert captured["cities"] == "Munich,Berlin"
    assert captured["sites"] == "indeed,linkedin"
    assert captured["results"] == 5
