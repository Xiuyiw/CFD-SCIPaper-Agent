from typer.testing import CliRunner

from cfdpaper.cli import app
from cfdpaper.publication.manuscript import assemble_manuscript, prepare_manuscript
from tests.publication.test_manuscript import fixture


def test_author_command_creates_managed_copy_and_formal_view(tmp_path):
    source, drafts = fixture(tmp_path)
    package = prepare_manuscript(source, tmp_path / "prepared")
    candidate = assemble_manuscript(package, drafts, tmp_path / "candidate")
    runner = CliRunner()
    result = runner.invoke(
        app, ["author", "--package", str(candidate), "--output", str(tmp_path / "author")]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "author/manuscript.docx").is_file()
    result = runner.invoke(
        app,
        [
            "author",
            "--package",
            str(tmp_path / "author/candidate"),
            "--format",
            "tex",
            "--profile",
            "conference",
            "--output",
            str(tmp_path / "conference.tex"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "\\begin{figure*}" in (tmp_path / "conference.tex").read_text(encoding="utf-8")


def test_author_command_rejects_a_mismatched_export_format(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "author",
            "--package",
            str(tmp_path),
            "--format",
            "tex",
            "--output",
            str(tmp_path / "wrong.docx"),
        ],
    )
    assert result.exit_code != 0
    assert not (tmp_path / "wrong.docx").exists()
