"""The public invented tutorial exercises actual SDK plumbing, not AI writing quality."""

import csv
import json
import runpy
import shutil
from pathlib import Path

import pytest

from cfdpaper.publication.manuscript import assemble_manuscript

EXAMPLE = Path(__file__).resolve().parents[2] / "examples/effective-methods"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_public_static_difference_seed_word_and_portable_source_refresh(tmp_path):
    docx = pytest.importorskip("docx")
    output = tmp_path / "tutorial"
    source_before = (EXAMPLE / "inputs/history.csv").read_bytes()
    artifact = runpy.run_path(str(EXAMPLE / "run_example.py"))["run"](output)
    definitions = read(output / "definitions.json")
    assert definitions["issues"] == []
    assert [d["qualified_name"] for d in definitions["definitions"]] == [
        "TutorialBalance.front_rate",
        "TutorialBalance.contrast",
    ]
    assert all(
        d["complete"] and "line:" in d["source"]["locator"] for d in definitions["definitions"]
    )
    # The source guard would abort any accidental import or execution.
    assert "raise RuntimeError" in (EXAMPLE / "inputs/model.py").read_text(encoding="utf-8")
    assert source_before == (EXAMPLE / "inputs/history.csv").read_bytes()
    assert (
        source_before == (output / "manuscript/sections/results/sources/history.csv").read_bytes()
    )
    figure_root = output / "analysis/figures"
    with (figure_root / "evidence-panels-source-data.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 24
    differences = [r for r in rows if r["operation"] == "temporal_difference"]
    assert len(differences) == 12
    with (EXAMPLE / "inputs/history.csv").open(encoding="utf-8", newline="") as stream:
        original = {(r["case"], float(r["time_s"])): r for r in csv.DictReader(stream)}
    for row in differences:
        source_row = original[(row["group"], float(row["time"]))]
        assert float(row["comparison_original"]) == float(source_row["front_K"])
        assert float(row["reference_original"]) == float(source_row["rear_K"])
    assert all(
        float(r["value"]) == float(r["comparison_original"]) - float(r["reference_original"])
        for r in differences
    )
    assert {r["value_unit"] for r in differences} == {"K"}
    last = next(r for r in differences if r["group"] == "B" and float(r["time"]) == 5)
    assert (
        float(last["comparison_original"]),
        float(last["reference_original"]),
        float(last["value"]),
    ) == (350, 305, 45)
    summary = read(figure_root / "figure-summary.json")
    assert summary["style"]["width_mm"] == 160
    assert summary["style"]["height_mm"] == 110
    assert summary["checks"]["minimum_source_font_pt"] >= 8
    assert summary["checks"]["text_nonoverlapping"] is True
    for extension in ("svg", "pdf", "png", "tiff"):
        assert (figure_root / f"evidence-panels.{extension}").stat().st_size > 0
    assert "PLOT_STYLE" in (figure_root / "plot.py").read_text(encoding="utf-8")
    data = read(output / "manuscript/section.json")
    assert [p["section_id"] for p in data["paragraphs"] if "section_heading" in p] == [
        "methods",
        "results",
        "discussion",
        "conclusion",
    ]
    assert len(data["tables"]) == len(data["equations"]) == len(data["figures"]) == 1
    assert data["figures"][0]["placement"] == "section-end"
    reference = data["references"][0]
    assert "Synthetic tutorial reference" in reference["text"]
    claim = "Retain both original temperatures before interpreting their difference."
    assert claim not in reference["text"]
    assert any(e["text"] == claim for e in data["evidence"])
    text = (output / "manuscript/manuscript.md").read_text(encoding="utf-8")
    assert "{{" not in text and "45.0 K" in text and "22.5 K" in text
    document = docx.Document(artifact)
    paragraphs = [p.text for p in document.paragraphs]
    assert (
        paragraphs.index("Discussion")
        > next(i for i, p in enumerate(paragraphs) if p.startswith("Figure 1."))
        > next(i for i, p in enumerate(paragraphs) if p.startswith("The original readings"))
    )
    assert len(document.tables) == 1 and document._element.xpath(".//m:oMath")
    body = next(p for p in document.paragraphs if p.text.startswith("We statically read"))
    assert body.paragraph_format.space_before.pt == body.paragraph_format.space_after.pt == 0
    assert (
        body._p.xpath("./w:pPr/w:ind")[0].get(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}firstLineChars"
        )
        == "200"
    )
    assert claim not in next(p for p in paragraphs if p.startswith("[1]"))
    moved = tmp_path / "relocated"
    shutil.copytree(output / "manuscript", moved)
    config = moved / "sections/methods/sources/config.json"
    values = read(config)
    values["capacity_J_K"] = 125
    config.write_text(json.dumps(values), encoding="utf-8")
    source = moved / "sections/results/sources/history.csv"
    source.write_text(
        source.read_text(encoding="utf-8").replace("B,5,350,305", "B,5,355,305"), encoding="utf-8"
    )
    refreshed = assemble_manuscript(moved, moved / "drafts.json", tmp_path / "refreshed")
    refreshed_data = read(refreshed / "section.json")
    bound = list(refreshed_data["resolved_values"].values())
    assert any(v["raw_value"] == 125 and v.get("json_pointer") == "/capacity_J_K" for v in bound)
    assert any(v["raw_value"] == 50 and v.get("field") == "end_value" for v in bound)
    assert "50.0 K" in (refreshed / "manuscript.md").read_text(encoding="utf-8")
    assert "45.0 K" in text and "100 J/K" in text
    assert (
        source_before == (output / "manuscript/sections/results/sources/history.csv").read_bytes()
    )
    # Reassembly refreshes numerical text, not the author's figure; do not export
    # this altered-source candidate until that separate figure refresh is done.


def test_example_selects_an_original_profile_and_same_record_difference_profile():
    candidate = runpy.run_path(str(EXAMPLE / "run_example.py"))["proposal"]("L11-L13")[
        "candidates"
    ][0]
    assert [p["calculation_id"] for p in candidate["evidence_panels"]] == ["front", "contrast"]
    contrast = next(c for c in candidate["calculations"] if c["id"] == "contrast")
    assert contrast["operation"] == "temporal_difference"
    assert contrast["columns"] == {"time": "time_s", "reference": "rear_K", "comparison": "front_K"}
