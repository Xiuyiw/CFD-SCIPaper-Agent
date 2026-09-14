"""The review route works without a project database or a model provider."""

import json
import runpy
import shutil
from pathlib import Path

from rich.text import Text
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
    result = runner.invoke(
        app, ["review", "--help"], color=False, terminal_width=150, env={"FORCE_COLOR": "1"}
    )
    assert result.exit_code == 0
    # Rich may emit ANSI spans despite Click's color=False on CI terminals.
    help_text = Text.from_ansi(result.stdout).plain
    assert "complete returned report" in help_text
    assert "--actions" in help_text


def test_review_actions_cli_rejects_simultaneous_report_and_actions(tmp_path):
    output = tmp_path / "output"
    result = runner.invoke(
        app,
        [
            "review",
            str(tmp_path),
            "--package",
            str(tmp_path),
            "--output",
            str(output),
            "--report",
            "report.md",
            "--actions",
            "actions.json",
        ],
    )
    assert result.exit_code != 0
    assert "not both" in result.stdout + result.stderr
    assert not output.exists()


def test_selected_task_moves_then_reassembles_without_changing_other_drafts(tmp_path):
    """Synthetic review exercises editing mechanics, not independent scientific approval."""
    from cfdpaper.publication.manuscript_review import (
        import_manuscript_review,
        prepare_manuscript_review,
    )

    script = (
        Path(__file__).resolve().parents[1] / "examples/literature-manuscript/prepare_example.py"
    )
    source = tmp_path / "source"
    runpy.run_path(str(script))["prepare"](source)
    prepared = prepare_manuscript(source / "manuscript-input.json", tmp_path / "prepared")
    candidate = assemble_manuscript(prepared, source / "drafts.json", tmp_path / "candidate")
    original_reading = (candidate / "manuscript.md").read_bytes()
    review = tmp_path / "review"
    packet = prepare_manuscript_review(candidate, review)
    quote = "the analytical pressure drop increases"
    report = tmp_path / "synthetic-review.md"
    report.write_text("Synthetic test review. Prefer 'rises' to 'increases'.", encoding="utf-8")
    returned = tmp_path / "returned"
    import_manuscript_review(review, report, returned)
    actions = tmp_path / "actions.json"
    actions.write_text(
        json.dumps(
            {
                "package_id": packet["package_id"],
                "actions": [
                    {
                        "id": "wording",
                        "decision": "accept",
                        "report_quote": "Prefer 'rises' to 'increases'.",
                        "rationale": "A synthetic wording-only edit for integration testing.",
                        "instruction": "Replace increases with rises in this clause only.",
                        "targets": [{"section_id": "hydraulics", "paragraph": 1, "quote": quote}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    edit = tmp_path / "edit"
    result = runner.invoke(
        app,
        [
            "review",
            str(tmp_path),
            "--package",
            str(returned),
            "--actions",
            str(actions),
            "--output",
            str(edit),
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Selected editing task ready" in result.stdout
    moved = tmp_path / "moved-edit"
    shutil.move(edit, moved)
    working = moved / "working"
    mapping = json.loads((working / "drafts.json").read_text(encoding="utf-8"))
    before = {sid: (working / path).read_bytes() for sid, path in mapping.items()}
    draft_path = working / mapping["hydraulics"]
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    draft["paragraphs"][0]["text"] = draft["paragraphs"][0]["text"].replace(
        quote, "the analytical pressure drop rises"
    )
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    output = tmp_path / "edited-candidate"
    assembled = runner.invoke(
        app,
        [
            "write",
            str(tmp_path),
            "--artifact",
            "manuscript",
            "--package",
            str(working),
            "--draft",
            str(working / "drafts.json"),
            "--output",
            str(output),
        ],
    )
    assert assembled.exit_code == 0, assembled.stdout + assembled.stderr
    assert "the analytical pressure drop rises" in (output / "manuscript.md").read_text(
        encoding="utf-8"
    )
    for sid, path in mapping.items():
        if sid != "hydraulics":
            assert (working / path).read_bytes() == before[sid]
            original = json.loads(before[sid])
            assert json.loads((output / path).read_text(encoding="utf-8")) == original
    assert (candidate / "manuscript.md").read_bytes() == original_reading
