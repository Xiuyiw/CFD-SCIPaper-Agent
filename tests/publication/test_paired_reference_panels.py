"""Paired range plots consume the same declared calculation as manuscript tokens."""

import csv
import json
import os
import subprocess
import sys

import numpy as np
import pytest

from cfdpaper.publication.evidence_panels import render_evidence_panels
from cfdpaper.publication.section import assemble_section, prepare_section
from cfdpaper.publication.table_evidence import (
    REFERENCE_RANGE_FIELDS,
    calculate_declared_table,
    resolve_table_result,
)


def paired_input(tmp_path, *, unit="degC", quantity_kind="absolute-temperature"):
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources/observations.csv").write_text(
        "case,state,stage,unit,model,center,low,high\n"
        f"A,baseline,old,{unit},not-numeric,100,99,101\n"
        f"A,baseline,new,{unit},105,100,99,101\n"
        f"B,changed,new,{unit},130,104,103,105\n"
        f"A,changed,new,{unit},110,104,103,105\n"
        f"B,baseline,new,{unit},120,100,99,101\n",
        encoding="utf-8",
    )
    declaration = {
        "id": "paired",
        "source": "sources/observations.csv",
        "domain": "Change between two observations of the same declared quantity",
        "operation": "paired_reference_change",
        "columns": {"value": "model", "reference": "center", "lower": "low", "upper": "high"},
        "units": dict.fromkeys(("value", "reference", "lower", "upper"), unit),
        "quantity_kind": quantity_kind,
        "group_by": "case",
        "pair_by": "state",
        "reference": "baseline",
        "comparison": "changed",
        "row_filters": {"stage": "new"},
        "unit_column": "unit",
        "reference_kind": "reported-range",
    }
    evidence = [
        {
            "id": f"p_{field}",
            "kind": "metric",
            "text": f"Paired {field}",
            "source": declaration["source"],
            "result_ref": {"calculation_id": "paired", "group": "B", "field": field},
        }
        for field in sorted(REFERENCE_RANGE_FIELDS)
    ]
    data = {
        "section_id": "paired-response",
        "title": "Paired thermal response",
        "question": "Does the observed change agree without cancelling absolute bias?",
        "table_calculations": [declaration],
        "figures": [],
        "evidence": evidence,
        "duties": [
            {
                "purpose": "Compare changes",
                "evidence_ids": [e["id"] for e in evidence],
                "figure_ids": [],
            }
        ],
    }
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    panels = [
        {
            "kind": "reference_range",
            "calculation_id": "paired",
            "title": "Paired thermal response",
            "x_label": "Temperature change",
            "y_label": "Configuration",
        }
    ]
    return path, data, declaration, panels


def source_rows(output):
    with (output / "evidence-panels-source-data.csv").open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_paired_celsius_panel_source_prose_and_standalone_replay_agree(tmp_path):
    path, data, declaration, panels = paired_input(tmp_path)
    panels[0]["x_label"] += " (°C)"  # A source-scale suffix must not label a difference axis.
    original = (tmp_path / declaration["source"]).read_bytes()
    output = tmp_path / "figures"
    figure = render_evidence_panels(path, panels, output)
    rows = source_rows(output)
    assert len(rows) == 2
    assert {r["value_unit"] for r in rows} == {"K"}
    assert {r["difference_unit"] for r in rows} == {"K"}
    assert [r["source_locator"] for r in rows] == ["csv_records:3,5", "csv_records:6,4"]
    assert [r["reference_source_locator"] for r in rows] == ["csv_records:3", "csv_records:6"]
    assert [r["comparison_source_locator"] for r in rows] == ["csv_records:5", "csv_records:4"]
    assert {r["range_kind"] for r in rows} == {"reported-range"}
    assert json.loads(rows[1]["reference_source_values"]) == {
        "value": 120,
        "reference": 100,
        "lower": 99,
        "upper": 101,
    }
    assert json.loads(rows[1]["comparison_source_values"]) == {
        "value": 130,
        "reference": 104,
        "lower": 103,
        "upper": 105,
    }
    assert json.loads(rows[1]["source_units"]) == declaration["units"]
    assert json.loads(rows[1]["source_columns"]) == declaration["columns"]
    parameters = json.loads(rows[1]["source_parameters"])
    assert parameters["pair_by"] == "state"
    assert parameters["row_filters"] == {"stage": "new"}
    assert parameters["unit_column"] == "unit"
    assert parameters["quantity_kind"] == "absolute-temperature"
    assert rows[1]["reference_member"] == "baseline" and rows[1]["comparison_member"] == "changed"

    report = {
        **declaration,
        **calculate_declared_table(tmp_path / declaration["source"], declaration),
    }
    for row in rows:
        for field in REFERENCE_RANGE_FIELDS:
            bound = resolve_table_result(
                [report],
                calculation_id="paired",
                group=row["group"],
                field=field,
            )
            assert float(row[field]) == bound["raw_value"]
            assert bound["unit"] == "K"
    assert [float(r["difference"]) for r in rows] == [1, 6]
    assert [float(r["outside_distance"]) for r in rows] == [0, 4]
    assert "conservative endpoint subtraction" in figure["caption"]
    assert "not confidence intervals" in figure["caption"]
    svg = (output / "evidence-panels.svg").read_text(encoding="utf-8")
    assert "Temperature change (K)" in svg and "°C" not in svg
    assert "Model change" in svg and "Reference change" in svg
    assert "Δ = +6 K" in svg and "<text" in svg
    for extension in ("svg", "pdf", "png", "tiff"):
        assert (output / f"evidence-panels.{extension}").stat().st_size > 0
    before = (output / "evidence-panels-source-data.csv").read_bytes()
    assert "cfdpaper" not in (output / "plot.py").read_text(encoding="utf-8")
    subprocess.run(
        [sys.executable, str(output / "plot.py")],
        cwd=output,
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
        check=True,
        capture_output=True,
        timeout=60,
    )
    assert "Temperature change (K)" in (output / "evidence-panels.svg").read_text(encoding="utf-8")
    assert (output / "evidence-panels-source-data.csv").read_bytes() == before
    assert (tmp_path / declaration["source"]).read_bytes() == original
    checks = json.loads((output / "layout-checks.json").read_text(encoding="utf-8"))
    assert checks["text_inside_canvas"] and checks["text_nonoverlapping"]
    assert checks["minimum_source_font_pt"] >= 8

    data["figures"] = [{k: v for k, v in figure.items() if k != "evidence_ids"}]
    data["duties"][0]["figure_ids"] = ["1"]
    path.write_text(json.dumps(data), encoding="utf-8")
    package = prepare_section(path, tmp_path / "package")
    ids = [e["id"] for e in data["evidence"]]
    draft_path = tmp_path / "draft.json"
    draft_path.write_text(
        json.dumps(
            {
                "title": data["title"],
                "paragraphs": [
                    {
                        "text": "; ".join(
                            f"{e['text']}: {{{{value:{e['id']}}}}}" for e in data["evidence"]
                        ),
                        "evidence_ids": ids,
                        "figure_ids": ["1"],
                    }
                ],
                "captions": {"1": figure["caption"]},
                "evidence_notes": [],
                "image_observations": {"1": "author-provided"},
            }
        ),
        encoding="utf-8",
    )
    section = assemble_section(package, draft_path, tmp_path / "section")
    result = json.loads((section / "section.json").read_text(encoding="utf-8"))
    for field in REFERENCE_RANGE_FIELDS:
        binding = result["resolved_values"][f"p_{field}"]
        assert binding["raw_value"] == float(rows[1][field])
        assert binding["unit"] == "K" and binding["csv_records"] == [6, 4]
        assert f"{binding['value']} K" in result["paragraphs"][0]["text"]


@pytest.mark.parametrize(
    "unit,quantity_kind", [("Pa", "ordinary"), ("K", "temperature-difference")]
)
def test_paired_panel_uses_declared_difference_scale_and_exact_group_selection(
    tmp_path,
    unit,
    quantity_kind,
):
    path, _, _, panels = paired_input(tmp_path, unit=unit, quantity_kind=quantity_kind)
    panels[0].update(groups=["B"], x_label="Observation change")
    render_evidence_panels(path, panels, tmp_path / "figures")
    rows = source_rows(tmp_path / "figures")
    assert len(rows) == 1 and rows[0]["group"] == "B"
    assert rows[0]["value_unit"] == unit and rows[0]["difference_unit"] == unit
    assert float(rows[0]["value"]) == 10 and float(rows[0]["reference_value"]) == 4


def test_paired_npz_half_width_source_indices_and_input_roles_survive(tmp_path):
    path, data, declaration, panels = paired_input(tmp_path, unit="K")
    np.savez(
        tmp_path / "sources/observations.npz",
        case=["A", "A"],
        state=["changed", "baseline"],
        stage=["new", "new"],
        unit=["K", "K"],
        model=[383.15, 378.15],
        center=[377.15, 373.15],
        width=[2, 1],
    )
    declaration.update(
        source="sources/observations.npz",
        columns={"value": "model", "reference": "center", "half_width": "width"},
        units=dict.fromkeys(("value", "reference", "half_width"), "K"),
        reference_kind="figure-reading-envelope",
    )
    path.write_text(json.dumps(data), encoding="utf-8")
    render_evidence_panels(path, panels, tmp_path / "figures")
    row = source_rows(tmp_path / "figures")[0]
    assert row["reference_source_locator"] == "array_indices:1"
    assert row["comparison_source_locator"] == "array_indices:0"
    assert row["source_locator"] == "array_indices:1,0"
    assert json.loads(row["reference_source_values"])["half_width"] == 1
    assert json.loads(row["comparison_source_values"])["half_width"] == 2
    assert float(row["reference_lower"]) == pytest.approx(1)
    assert float(row["reference_upper"]) == pytest.approx(7)
    assert row["range_kind"] == "figure-reading-envelope"


def test_missing_paired_bounds_do_not_generate_a_zero_envelope(tmp_path):
    path, _, declaration, panels = paired_input(tmp_path)
    source = tmp_path / declaration["source"]
    source.write_text(
        source.read_text(encoding="utf-8").replace("110,104,103,105", "110,104,,105"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unavailable"):
        render_evidence_panels(path, panels, tmp_path / "figures")
    assert not (tmp_path / "figures/evidence-panels.png").exists()
