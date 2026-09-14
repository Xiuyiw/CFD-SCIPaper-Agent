"""Weighted exported records reach ordinary analysis and writing workflows."""

import json
import shutil

import pytest

from cfdpaper.analysis_suggestions import _Calculation, compile_analysis, prepare_analysis
from cfdpaper.publication.analysis_section import build_analysis_section
from cfdpaper.publication.section import (
    _TableCalculation,
    assemble_section,
    export_section_docx,
)


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def weighted_definition():
    return dict(
        id="temperature",
        source="sources/elements.csv",
        operation="weighted_population",
        columns={"value": "T [degC]", "weight": "area [m2]"},
        units={"value": "degC", "weight": "m2"},
        weight_kind="area",
        quantity_kind="absolute-temperature",
        domain="Non-overlapping supplied wall facets",
        group_by="case",
    )


def test_weighted_definition_round_trip_retains_semantics():
    definition = weighted_definition()
    saved = _TableCalculation.model_validate(definition).model_dump()
    assert saved == definition
    assert _TableCalculation.model_validate(saved).model_dump() == saved


@pytest.mark.parametrize(
    "change",
    [
        {"weight_kind": None},
        {"temperature_reference": 20},
        {"pair_by": "geometry"},
    ],
)
def test_weighted_model_requires_own_definition_not_pair_selectors(change):
    with pytest.raises(ValueError):
        _TableCalculation.model_validate({**weighted_definition(), **change})


@pytest.mark.parametrize(
    "change", [{"weight_kind": "area"}, {"quantity_kind": "absolute-temperature"}]
)
def test_equal_record_proposal_does_not_silently_drop_spatial_semantics(change):
    with pytest.raises(ValueError):
        _Calculation.model_validate(
            dict(
                id="records",
                source="sources/values.csv",
                operation="population",
                columns={"value": "x"},
                units={"value": "Pa"},
                domain="Supplied records",
                definition_source={"path": "sources/method.md", "locator": "L1"},
                comparison={"status": "supported", "scope": "Same records"},
                member_id=["id"],
                interpretation_limits=["Equal-record statistics"],
                **change,
            )
        )


def prepared_analysis(tmp_path):
    source = tmp_path / "raw"
    source.mkdir()
    (source / "elements.csv").write_text(
        "case,facet,T [degC],area [m2]\nA,1,40,1\nA,2,44,3\nB,1,41,1\nB,2,43,3\n",
        encoding="utf-8",
    )
    (source / "method.md").write_text(
        "Synthetic piecewise-constant wall values on two disjoint facets per case.\n"
        "T [degC] is absolute temperature; area [m2] is the positive facet measure.\n"
        "Both cases use the same declared domain; no within-facet variation is resolved.\n",
        encoding="utf-8",
    )
    package = tmp_path / "analysis"
    prepare_analysis(source, package, question="How do mean and spatial spread differ?")
    calc = {
        **weighted_definition(),
        "definition_source": {"path": "sources/method.md", "locator": "L1-L3"},
        "comparison": {"status": "supported", "scope": "Same synthetic wall facet domain"},
        "member_id": ["facet"],
        "expected_members": [["1"], ["2"]],
        "expected_groups": ["A", "B"],
        "interpretation_limits": ["Spatial SD of supplied values, not uncertainty."],
    }
    candidate = dict(
        id="weighted-wall",
        title="Wall temperature distribution",
        question="How do mean and spread differ?",
        rationale="Compare complementary responses.",
        presentation="table",
        presentation_reason="A compact exact comparison is sufficient.",
        calculations=[calc],
        interpretation_limits=["Synthetic evidence, not a CFD validation."],
    )
    write_json(package / "chosen.json", {"candidates": [candidate]})
    return source, package


def test_weighted_analysis_relocation_section_table_and_word(tmp_path):
    source, package = prepared_analysis(tmp_path)
    moved = tmp_path / "moved"
    shutil.move(str(package), moved)
    shutil.rmtree(source)
    result = compile_analysis(moved, moved / "chosen.json", "weighted-wall", tmp_path / "compiled")
    data = json.loads(result.read_text(encoding="utf-8"))
    assert {e["result_ref"]["field"] for e in data["evidence"]} == {
        "weighted_mean",
        "weighted_std",
        "weight_sum",
    }
    saved = json.loads((result.parent / "selected-analysis.json").read_text())
    assert saved["calculations"][0]["comparison"]["status"] == "supported"
    assert "comparison" not in data["table_calculations"][0]
    section = build_analysis_section(result, tmp_path / "writing")
    ids = {(e["result_ref"]["group"], e["result_ref"]["field"]): e["id"] for e in data["evidence"]}
    mean, sd = ids["A", "weighted_mean"], ids["A", "weighted_std"]
    draft = dict(
        title=data["title"],
        paragraphs=[
            dict(
                text=f"The area-weighted mean is {{{{value:{mean}}}}} and "
                f"the spatial SD is {{{{value:{sd}}}}}.",
                evidence_ids=[e["id"] for e in data["evidence"]],
                figure_ids=[],
            )
        ],
        captions={},
        evidence_notes=[],
        image_observations={},
        tables=[
            dict(
                table_id="1",
                caption="Synthetic facet statistics",
                after_section_id="weighted-wall",
                columns=["Mean", "SD"],
                rows=[[f"{{{{value:{mean}}}}}", f"{{{{value:{sd}}}}}"]],
                evidence_ids=[mean, sd],
            )
        ],
    )
    draft_path = write_json(tmp_path / "draft.json", draft)
    assembled = assemble_section(section, draft_path, tmp_path / "candidate")
    text = (assembled / "section.md").read_text(encoding="utf-8")
    assert "43.000" in text and "1.732" in text
    # Reassembly consumes the current copied raw records, not the old computed report.
    csv_path = section / "sources/elements.csv"
    csv_path.write_text(csv_path.read_text().replace("A,2,44,3", "A,2,48,3"))
    updated = assemble_section(section, draft_path, tmp_path / "updated")
    assert "46.000" in (updated / "section.md").read_text(encoding="utf-8")
    assert "43.000" in (assembled / "section.md").read_text(encoding="utf-8")
    docx = pytest.importorskip("docx")
    output = export_section_docx(updated, tmp_path / "weighted.docx")
    document = docx.Document(output)
    assert len(document.tables) == 1
    assert "46.000" in document.tables[0].cell(1, 0).text
    assert "°C" in document.tables[0].cell(1, 0).text
    assert "K" in document.tables[0].cell(1, 1).text
    assert not document.inline_shapes  # Do not create a full-page two-point chart.


@pytest.mark.parametrize("change", ["duplicate", "unit-conflict", "missing-value"])
def test_weighted_proposal_keeps_existing_scientific_input_checks(tmp_path, change):
    _, package = prepared_analysis(tmp_path)
    path = package / "sources/elements.csv"
    raw = path.read_text()
    if change == "duplicate":
        path.write_text(raw + "A,1,40,1\n")
    elif change == "missing-value":
        path.write_text(raw.replace("A,1,40,1", "A,1,,1"))
    else:
        data = json.loads((package / "chosen.json").read_text())
        data["candidates"][0]["calculations"][0]["units"]["weight"] = "mm2"
        write_json(package / "chosen.json", data)
    with pytest.raises(ValueError):
        compile_analysis(package, package / "chosen.json", "weighted-wall", tmp_path / "bad")
    assert not (tmp_path / "bad").exists()
