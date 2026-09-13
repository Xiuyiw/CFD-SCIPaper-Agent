"""The review route works without a project database or a model provider."""

import json
import runpy
from pathlib import Path

from typer.testing import CliRunner

from cfdpaper.cli import app
from cfdpaper.publication.manuscript import assemble_manuscript, prepare_manuscript

runner = CliRunner()


def test_review_cli_exports_and_retains_complete_unicode_report(tmp_path):
    script = (
        Path(__file__).resolve().parents[1] / "examples/literature-manuscript/prepare_example.py"
    )
    source = tmp_path / "source"
    runpy.run_path(str(script))["prepare"](source)
    prepared = prepare_manuscript(source / "manuscript-input.json", tmp_path / "prepared")
    candidate = assemble_manuscript(prepared, source / "drafts.json", tmp_path / "candidate")
    before = (candidate / "manuscript.md").read_bytes()
    package = tmp_path / "review"
    exported = runner.invoke(
        app, ["review", str(tmp_path), "--package", str(candidate), "--output", str(package)]
    )
    assert exported.exit_code == 0, exported.stdout + exported.stderr
    assert "review package ready" in exported.stdout
    report = tmp_path / "完整评审.md"
    payload = "# 全部意见 A–F\n\nA. Definitions\n\nF. 最后的重要意见，不得省略。\n".encode()
    report.write_bytes(payload)
    returned = tmp_path / "returned"
    imported = runner.invoke(
        app,
        [
            "review",
            str(tmp_path),
            "--package",
            str(package),
            "--report",
            str(report),
            "--output",
            str(returned),
        ],
    )
    assert imported.exit_code == 0, imported.stdout + imported.stderr
    assert "manuscript unchanged" in imported.stdout
    assert any(path.read_bytes() == payload for path in returned.rglob(report.name))
    assert (candidate / "manuscript.md").read_bytes() == before
    assert not (tmp_path / ".cfdpaper/project.db").exists()


def test_review_cli_rejects_changed_manuscript_before_export(tmp_path):
    script = (
        Path(__file__).resolve().parents[1] / "examples/manuscript-workspace/prepare_example.py"
    )
    source = tmp_path / "source"
    runpy.run_path(str(script))["prepare"](source)
    package = prepare_manuscript(source / "manuscript-input.json", tmp_path / "prepared")
    candidate = assemble_manuscript(package, source / "drafts.json", tmp_path / "candidate")
    mapping = json.loads((candidate / "drafts.json").read_text(encoding="utf-8"))
    draft_path = candidate / next(iter(mapping.values()))
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    draft["paragraphs"][0]["text"] += " Updated author text."
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    output = tmp_path / "review"
    result = runner.invoke(
        app, ["review", str(tmp_path), "--package", str(candidate), "--output", str(output)]
    )
    assert result.exit_code != 0
    assert "reassemble" in (result.stdout + result.stderr).lower()
    assert not output.exists()


def test_review_help_explains_report_option():
    result = runner.invoke(app, ["review", "--help"], color=False, terminal_width=150)
    assert result.exit_code == 0
    assert "complete returned report" in result.stdout
