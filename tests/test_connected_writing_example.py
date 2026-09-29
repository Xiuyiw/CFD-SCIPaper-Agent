"""The recorded public example remains portable and recomputes bound evidence."""

import json
import runpy
import shutil
from pathlib import Path

import pytest

from cfdpaper.publication.manuscript import assemble_manuscript, prepare_writing_context


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_connected_example_relocates_and_updates_cross_section_values(tmp_path):
    docx = pytest.importorskip("docx")
    script = Path(__file__).resolve().parents[1] / "examples/connected-writing/run_example.py"
    candidate = runpy.run_path(str(script))["run"](tmp_path / "example")
    text = (candidate / "manuscript.md").read_text(encoding="utf-8")
    assert "315.00 and 310.50" in text
    assert "-4.50 K" in text and "25.00 Pa" in text
    assert "Recorded" in text and "synthetic" in text
    assert not read(candidate / "section.json")["references"]
    document = docx.Document(candidate.parent / "manuscript.docx")
    assert len(document.tables) == 1 and not document.inline_shapes
    assert "310.50\u00a0K" in document.tables[0].cell(1, 2).text
    context = read(candidate.parent / "contexts/discussion/context.json")
    assert set(context["sections"]) == {"methods", "results", "discussion"}
    assert context["sections"]["results"]["draft"]["paragraphs"][0]["shared_unit"] == "K"
    assert context["sections"]["discussion"]["draft"] is None
    assert context["missing_dependency_drafts"] == []

    moved = tmp_path / "portable"
    shutil.move(str(candidate), moved)
    source = moved / "sections/results/sources/metrics.csv"
    raw = source.read_text(encoding="utf-8")
    source.write_text(
        raw.replace("310.5,K", "308.5,K").replace("125,Pa", "130,Pa"), encoding="utf-8"
    )
    updated = assemble_manuscript(moved, moved / "drafts.json", tmp_path / "updated")
    new = (updated / "manuscript.md").read_text(encoding="utf-8")
    assert "315.00 and 308.50" in new
    assert "-6.50 K" in new and "30.00 Pa" in new
    assert (moved / "manuscript.md").read_text(encoding="utf-8") == text
    reports = read(updated / "sections/results/table-results.json")
    assert reports[0]["groups"][0]["csv_records"] == [3]
    assert reports[0]["groups"][1]["csv_records"] == [5]
    refreshed = prepare_writing_context(
        moved, "discussion", tmp_path / "refreshed", drafts_path=moved / "drafts.json"
    )
    evidence = read(refreshed / "context.json")["sections"]["discussion"]["evidence"]
    assert evidence["temperature-change"]["resolved"]["raw_value"] == -6.5
    assert evidence["pressure-change"]["resolved"]["raw_value"] == 30
