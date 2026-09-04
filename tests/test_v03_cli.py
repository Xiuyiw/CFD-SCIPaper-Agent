from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cfdpaper.cli import app
from cfdpaper.state import initialize_project

runner = CliRunner()


def test_v03_delivered_commands_have_real_help() -> None:
    for command in ("qualify", "analyze", "figure", "write"):
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0
        assert "not implemented" not in result.stdout

    help_text = runner.invoke(app, ["qualify", "--help"]).stdout
    for option in (
        "--records",
        "--observations",
        "--question",
        "--guided",
        "--approve-qoi-contract",
        "--author",
    ):
        assert option in help_text


def test_cli_maps_missing_checkpoint_to_input_exit_without_traceback(tmp_path: Path) -> None:
    initialize_project(tmp_path, "missing-checkpoint")

    result = runner.invoke(app, ["analyze", str(tmp_path)])

    assert result.exit_code == 2
    assert "Complete the qualify prerequisite" in result.stdout
    assert "Traceback" not in result.stdout


def test_qualify_rejects_mixed_file_and_guided_intake(tmp_path: Path) -> None:
    initialize_project(tmp_path, "mixed-intake")
    result = runner.invoke(
        app,
        [
            "qualify",
            str(tmp_path),
            "--records",
            str(tmp_path / "records.json"),
            "--observations",
            str(tmp_path / "observations.csv"),
            "--question",
            str(tmp_path / "question.json"),
            "--guided",
        ],
    )

    assert result.exit_code == 2
    assert "Choose either --records or --guided" in result.stdout
    assert "Traceback" not in result.stdout


def test_review_remains_a_roadmap_command() -> None:
    result = runner.invoke(app, ["review"])
    assert result.exit_code == 2
    assert "not implemented" in result.stdout
