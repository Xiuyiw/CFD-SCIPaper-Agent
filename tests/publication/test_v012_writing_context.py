"""Current, bounded writing context; these are not scientific quality tests."""

import json
import shutil

import pytest

from cfdpaper.publication.manuscript import prepare_manuscript, prepare_writing_context
from tests.publication.test_manuscript import fixture, read, write


def task(tmp_path):
    source, drafts = fixture(tmp_path)
    manifest = read(source)
    manifest["keywords"] = ["heat transfer", "inherited study label"]
    manifest["sections"][1]["depends_on"] = ["methods"]
    write(source, manifest)
    package = prepare_manuscript(source, tmp_path / "package")
    return package, drafts


def test_partial_drafts_provide_current_dependency_without_unrelated_text(tmp_path):
    package, drafts = task(tmp_path)
    write(drafts, {"methods": "methods/draft.json"})
    target = prepare_writing_context(package, "response", tmp_path / "context", drafts_path=drafts)
    result = read(target / "context.json")
    assert set(result["sections"]) == {"methods", "response"}
    assert result["keywords"] == ["heat transfer", "inherited study label"]
    assert (
        read(target / "sections/response/manuscript-context.json")["keywords"] == result["keywords"]
    )
    assert "out-of-scope terms" in (package / "TASK.md").read_text(encoding="utf-8")
    assert result["missing_dependency_drafts"] == []
    assert result["sections"]["response"]["draft"] is None
    assert result["sections"]["methods"]["draft"] == read(tmp_path / "methods/draft.json")
    assert result["sections"]["methods"]["evidence"]["metric"]["resolved"]["raw_value"] == 2
    assert "transport" not in result["sections"]
    assert (target / "sections/methods/sources/values.csv").is_file()
    changed = read(tmp_path / "methods/draft.json")
    changed["paragraphs"][0]["text"] += " Author changed this passage."
    write(tmp_path / "methods/draft.json", changed)
    (package / "sections/methods/sources/values.csv").write_text("case,value\na,3\na,5\n")
    new = prepare_writing_context(package, "response", tmp_path / "new", drafts_path=drafts)
    assert read(new / "context.json")["sections"]["methods"]["draft"] == changed
    assert (
        read(new / "context.json")["sections"]["methods"]["evidence"]["metric"]["resolved"][
            "raw_value"
        ]
        == 4
    )
    assert read(target / "context.json") == result


def test_missing_drafts_are_explicit_and_sources_portable(tmp_path):
    package, _ = task(tmp_path)
    output = prepare_writing_context(package, "response", tmp_path / "context")
    payload = read(output / "context.json")
    assert payload["missing_dependency_drafts"] == ["methods"]
    moved = tmp_path / "relocated"
    shutil.move(output, moved)
    for name in (
        "cfd-paper-workflow",
        "cfd-qoi-physics",
        "cfd-evidence-intake",
        "cfd-figure-production",
        "cfd-evidence-writing",
    ):
        assert (moved / "skills" / name / "SKILL.md").is_file()
        assert (package / "skills" / name / "SKILL.md").is_file()
    assert (moved / "skills/cfd-evidence-writing/references/methods-sections.md").is_file()
    for entry in payload["sections"].values():
        path = moved / entry["input"]
        source = read(path)
        assert all((path.parent / name).is_file() for name in source["source_files"])
        assert all((path.parent / fig["path"]).is_file() for fig in source["figures"])


def test_unknown_task_or_draft_is_rejected(tmp_path):
    package, drafts = task(tmp_path)
    with pytest.raises(ValueError, match="Unknown section"):
        prepare_writing_context(package, "missing", tmp_path / "no")
    write(drafts, {"wrong": "methods/draft.json"})
    with pytest.raises(ValueError, match="Draft section"):
        prepare_writing_context(package, "response", tmp_path / "no", drafts_path=drafts)


def test_context_cli_with_optional_partial_drafts(tmp_path):
    from typer.testing import CliRunner

    from cfdpaper.cli import app

    package, drafts = task(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "write",
            str(tmp_path),
            "--artifact",
            "manuscript",
            "--package",
            str(package),
            "--context-for",
            "response",
            "--draft",
            str(drafts),
            "--output",
            str(tmp_path / "ctx"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads((tmp_path / "ctx/context.json").read_text())["target_section"] == "response"
