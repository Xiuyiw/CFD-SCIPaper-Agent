"""Spatial threshold definitions survive proposal, plotting inputs, and writing."""

import json
import shutil

import numpy as np
import pytest

from cfdpaper.analysis_suggestions import _Calculation, compile_analysis, prepare_analysis
from cfdpaper.publication.analysis_section import _points, build_analysis_section
from cfdpaper.publication.section import (
    _TableCalculation,
    assemble_section,
    export_section_docx,
)


def definition(**overrides):
    return {
        "id": "hot-area",
        "source": "sources/wall.npz",
        "operation": "weighted_exceedance",
        "columns": {"value": "temperature", "weight": "area"},
        "units": {"value": "K", "weight": "m2"},
        "weight_kind": "area",
        "quantity_kind": "absolute-temperature",
        "threshold": 310.0,
        "exceedance_relation": "above",
        "domain": "Supplied element-constant wall faces",
        **overrides,
    }


def proposal_calculation(**overrides):
    return {
        **definition(**overrides),
        "definition_source": {"path": "sources/method.md", "locator": "L1-L2"},
        "comparison": {"status": "supported", "scope": "Same declared wall faces"},
        "member_id": ["__index__"],
        "expected_members": [["0"], ["1"]],
        "interpretation_limits": ["Diagnostic threshold, not a safety boundary."],
    }


@pytest.mark.parametrize("model", [_TableCalculation, _Calculation])
@pytest.mark.parametrize("threshold", [True, "310"])
def test_exceedance_threshold_cannot_be_silently_coerced(model, threshold):
    data = definition(threshold=threshold)
    if model is _Calculation:
        data = proposal_calculation(threshold=threshold)
    with pytest.raises(ValueError, match="threshold"):
        model.model_validate(data)


@pytest.mark.parametrize("relation", ["above", "at-or-above"])
def test_definition_round_trip_keeps_spatial_threshold_and_no_temporal_options(relation):
    calculation = _Calculation.model_validate(proposal_calculation(exceedance_relation=relation))
    saved = calculation.model_dump()
    assert _Calculation.model_validate(saved).model_dump() == saved
    table = calculation.table_calculation().model_dump()
    assert _TableCalculation.model_validate(table).model_dump() == table
    assert table["threshold"] == 310.0
    assert table["exceedance_relation"] == relation
    assert table["weight_kind"] == "area"
    assert table["quantity_kind"] == "absolute-temperature"
    assert not {"time_window", "temporal_value_kind", "crossing_direction"} & table.keys()


def prepared_proposal(tmp_path, *, threshold=310.0, relation="above", metrics=None):
    raw = tmp_path / "raw"
    raw.mkdir()
    np.savez(raw / "wall.npz", temperature=[300.0, 320.0], area=[1.0, 3.0])
    (raw / "method.md").write_text(
        "Synthetic nonoverlapping wall faces have temperatures in K and areas in m2.\n"
        "Supplied temperatures are element-constant; the threshold is a diagnostic only.\n",
        encoding="utf-8",
    )
    package = tmp_path / "analysis"
    prepare_analysis(raw, package)
    population = proposal_calculation(id="spatial", operation="weighted_population")
    population.pop("threshold")
    population.pop("exceedance_relation")
    candidate = {
        "id": "wall",
        "title": "Wall temperature distribution",
        "question": "How much wall area exceeds the diagnostic threshold?",
        "rationale": "Read the distribution together with its mean and spatial spread.",
        "presentation": "table",
        "calculations": [
            population,
            proposal_calculation(threshold=threshold, exceedance_relation=relation),
        ],
        "interpretation_limits": ["Synthetic wall example, not solver validation."],
    }
    if metrics is not None:
        candidate["metrics"] = metrics
    (package / "chosen.json").write_text(json.dumps({"candidates": [candidate]}), encoding="utf-8")
    return package


def test_automatic_metrics_compile_plot_inputs_relocate_and_bind_word(tmp_path):
    package = prepared_proposal(tmp_path)
    compiled = compile_analysis(package, package / "chosen.json", "wall", tmp_path / "compiled")
    data = json.loads(compiled.read_text(encoding="utf-8"))
    fields = {item["result_ref"]["field"]: item for item in data["evidence"]}
    assert set(fields) == {
        "weighted_mean",
        "weighted_std",
        "weight_sum",
        "measure_above",
        "exceedance_fraction",
    }
    assert fields["exceedance_fraction"]["result_ref"]["percentage"] is True
    points = {point["evidence_id"]: point for point in _points(data, compiled.parent)}
    fraction_id = fields["exceedance_fraction"]["id"]
    assert points[fraction_id]["raw_value"] == 0.75
    assert points[fraction_id]["value"] == "75.000"
    assert points[fraction_id]["unit"] == "%"
    assert points[fraction_id]["array_indices"] == [0, 1]
    assert points[fields["weighted_mean"]["id"]]["raw_value"] == 315.0
    assert points[fields["weighted_std"]["id"]]["raw_value"] == pytest.approx(75**0.5)
    writing = build_analysis_section(compiled, tmp_path / "writing")
    moved = tmp_path / "relocated"
    shutil.move(str(writing.parent), moved)
    writing = moved / writing.name
    ids = [
        fields[field]["id"] for field in ("weighted_mean", "weighted_std", "exceedance_fraction")
    ]
    tokens = [f"{{{{value:{identifier}}}}}" for identifier in ids]
    draft = {
        "title": "Wall temperature distribution",
        "paragraphs": [
            {
                "text": f"Mean {tokens[0]}, spatial SD {tokens[1]}, "
                f"and threshold area {tokens[2]}.",
                "evidence_ids": [item["id"] for item in data["evidence"]],
                "figure_ids": [],
            }
        ],
        "captions": {},
        "evidence_notes": [],
        "image_observations": {},
        "tables": [
            {
                "table_id": "1",
                "caption": "Synthetic wall statistics",
                "after_section_id": "wall",
                "columns": ["Mean", "Spatial SD", "Threshold area"],
                "rows": [tokens],
                "evidence_ids": ids,
            }
        ],
    }
    draft_path = tmp_path / "draft.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    first = assemble_section(writing, draft_path, tmp_path / "first")
    assert "75.000 %" in (first / "section.md").read_text(encoding="utf-8")
    np.savez(writing / "sources/wall.npz", temperature=[315.0, 320.0], area=[1.0, 3.0])
    updated = assemble_section(writing, draft_path, tmp_path / "updated")
    assert "100.000 %" in (updated / "section.md").read_text(encoding="utf-8")
    assert "75.000 %" in (first / "section.md").read_text(encoding="utf-8")
    docx = pytest.importorskip("docx")
    document = docx.Document(export_section_docx(updated, tmp_path / "wall.docx"))
    assert document.tables[0].cell(1, 2).text.replace("\u00a0", " ") == "100.000 %"


@pytest.mark.parametrize(
    "field", ["weighted_mean", "mean", "weighted_std", "count", "measure_above"]
)
def test_proposal_rejects_percentage_for_nonfraction_or_wrong_operation_fields(tmp_path, field):
    package = prepared_proposal(
        tmp_path,
        metrics=[
            {
                "id": "invalid",
                "text": "Invalid percentage",
                "result_ref": {
                    "calculation_id": "hot-area",
                    "group": "all",
                    "field": field,
                    "percentage": True,
                },
            }
        ],
    )
    with pytest.raises(ValueError, match="unsupported field|percentage"):
        compile_analysis(package, package / "chosen.json", "wall", tmp_path / "bad")
    assert not (tmp_path / "bad").exists()
