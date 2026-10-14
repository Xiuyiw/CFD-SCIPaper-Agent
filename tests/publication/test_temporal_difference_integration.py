"""Declaration-bound differences survive proposal selection, prose, and profile export."""

import copy
import csv
import json
import os
import subprocess
import sys

import numpy as np
import pytest
from test_evidence_panels import panel_input, source_rows

from cfdpaper.analysis_suggestions import _Calculation, compile_analysis, prepare_analysis
from cfdpaper.publication.analysis_section import build_analysis_section
from cfdpaper.publication.evidence_panels import _FIELDS, render_evidence_panels
from cfdpaper.publication.section import _TableCalculation, assemble_section


def _difference_declaration(**options):
    return {
        "id": "difference",
        "source": "sources/history.csv",
        "operation": "temporal_difference",
        "columns": {"time": "t", "reference": "cold", "comparison": "hot"},
        "units": {"time": "s", "reference": "degC", "comparison": "degC"},
        "domain": "Same-record saved temperature difference",
        "quantity_kind": "absolute-temperature",
        "group_by": "case",
        "row_filters": {"stage": "new"},
        "time_window": [1, 3],
        "threshold": 5,
        "crossing_direction": "at-or-above",
        **options,
    }


def _profile():
    return {
        "kind": "profile",
        "calculation_id": "difference",
        "title": "Saved temperature difference",
        "x_label": "Time",
        "y_label": "Temperature difference (°C)",
    }


def _qualification():
    return {
        "definition_source": {"path": "sources/method.md", "locator": "L1-L2"},
        "comparison": {"status": "supported", "scope": "Two readings on the same saved record"},
        "member_id": ["t"],
        "expected_members": [["0"], ["1"], ["3"], ["4"]],
        "expected_groups": ["A", "B"],
        "interpretation_limits": ["Temperature difference alone is not heat flux or causal proof."],
        "missing_questions": [],
    }


@pytest.fixture
def difference_input(tmp_path):
    path, data, panels = panel_input(tmp_path)
    source = tmp_path / "sources/history.csv"
    source.write_text(
        "case,stage,t,q,cold,hot\nX,old,0,bad,bad,bad\n"
        "A,new,0,2,10,12\nB,new,0,3,30,31\n"
        "A,new,1,4,20,26\nB,new,1,7,40,42\n"
        "A,new,3,8,30,34\nB,new,3,9,50,58\n"
        "A,new,4,9,40,41\nB,new,4,10,60,69\n",
        encoding="utf-8",
    )
    (tmp_path / "sources/method.md").write_text(
        "cold and hot are absolute temperatures in degC on each saved record.\n"
        "Difference is hot minus cold in K; the selected exact saved window is 1 to 3 s.\n",
        encoding="utf-8",
    )
    data["table_calculations"][0].update(
        domain="Same saved history", row_filters={"stage": "new"}, time_window=[1, 3]
    )
    data["table_calculations"].append(_difference_declaration())
    data["evidence"].append({"id": "delta", "result_ref": {"calculation_id": "difference"}})
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data, panels


def _select(tmp_path, *, array=False, automatic=False, panels=False):
    raw = tmp_path / "sources"
    declaration = _difference_declaration()
    if array:
        with (raw / "history.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        np.savez(
            raw / "history.npz",
            **{key: [row[key] for row in rows] for key in ("case", "stage", "t", "cold", "hot")},
        )
        declaration["source"] = "sources/history.npz"
    prepared = tmp_path / "materials"
    prepare_analysis(raw, prepared, question="How do saved temperature differences vary?")
    proposal = json.loads((prepared / "proposal-example.json").read_text(encoding="utf-8"))
    selected = proposal["candidates"][0]
    selected.update(
        id="thermal-difference",
        question="How do saved temperature differences vary?",
        calculations=[{**declaration, **_qualification()}],
        metrics=[]
        if automatic
        else [
            {
                "id": key,
                "text": text,
                "result_ref": {"calculation_id": "difference", "group": group, "field": field},
            }
            for key, text, group, field in (
                ("mean-a", "Mean temperature difference in A", "A", "time_mean"),
                ("maximum-b", "Maximum temperature difference in B", "B", "maximum"),
                (
                    "cross-a",
                    "First selected sample at or above 5 K in A",
                    "A",
                    "first_crossing_time",
                ),
                (
                    "cross-b",
                    "First selected sample at or above 5 K in B",
                    "B",
                    "first_crossing_time",
                ),
            )
        ],
        presentation="prose" if automatic else "plot",
    )
    if panels:
        selected["evidence_panels"] = [_profile()]
    elif not automatic:
        selected["figure_plan"] = {
            "metric_ids": ["mean-a", "maximum-b"],
            "title": "Temperature difference",
            "y_label": "Temperature difference",
        }
    proposal_path = prepared / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    compiled = compile_analysis(prepared, proposal_path, selected["id"], tmp_path / "compiled")
    return compiled, declaration


def _assemble_all(package, output):
    data = json.loads((package / "input.json").read_text(encoding="utf-8"))
    evidence_ids = [e["id"] for e in data["evidence"]]
    figures = {figure["id"]: figure["caption"] for figure in data["figures"]}
    draft = {
        "title": data["title"],
        "paragraphs": [
            {
                "text": "; ".join(f"{key}: {{{{value:{key}}}}}" for key in evidence_ids),
                "evidence_ids": evidence_ids,
                "figure_ids": list(figures),
            }
        ],
        "captions": figures,
        "evidence_notes": [],
        "image_observations": dict.fromkeys(figures, "not-viewed"),
    }
    draft_path = output.parent / "draft.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    result = assemble_section(package, draft_path, output)
    return json.loads((result / "section.json").read_text(encoding="utf-8"))


def test_selected_proposal_scalar_plot_and_bound_prose_use_exact_difference_window(
    tmp_path, difference_input
):
    source_before = (tmp_path / "sources/history.csv").read_bytes()
    compiled, declaration = _select(tmp_path)
    data = json.loads(compiled.read_text(encoding="utf-8"))
    selected = data["table_calculations"][0]
    for key in ("operation", "columns", "units", "quantity_kind", "row_filters", "time_window"):
        assert selected[key] == declaration[key]
    assert selected["threshold"] == 5 and selected["crossing_direction"] == "at-or-above"
    reports = json.loads((compiled.parent / "table-results.json").read_text(encoding="utf-8"))
    assert [g["csv_records"] for g in reports[0]["groups"]] == [[5, 7], [6, 8]]
    assert all(g["time_window"] == [1, 3] for g in reports[0]["groups"])
    package = build_analysis_section(compiled, tmp_path / "output")
    plotted = []
    for number in (1, 2):
        with (package.parent / f"figures/analysis-{number}-source-data.csv").open(
            encoding="utf-8", newline=""
        ) as stream:
            plotted.extend(csv.DictReader(stream))
    assert [float(r["raw_value"]) for r in plotted] == [5, 8]
    assert [r["csv_records"] for r in plotted] == ["[5, 7]", "[6, 8]"]
    result = _assemble_all(package, tmp_path / "section")
    values = result["resolved_values"]
    assert (values["mean-a"]["raw_value"], values["mean-a"]["unit"]) == (5, "K")
    assert (values["maximum-b"]["raw_value"], values["maximum-b"]["unit"]) == (8, "K")
    assert (values["cross-a"]["raw_value"], values["cross-a"]["unit"]) == (1, "s")
    assert (values["cross-b"]["raw_value"], values["cross-b"]["unit"]) == (3, "s")
    assert values["mean-a"]["csv_records"] == values["cross-a"]["csv_records"] == [5, 7]
    assert values["maximum-b"]["csv_records"] == values["cross-b"]["csv_records"] == [6, 8]
    assert "5.000 K" in result["paragraphs"][0]["text"]
    assert "3.000 s" in result["paragraphs"][0]["text"]
    assert (tmp_path / "sources/history.csv").read_bytes() == source_before


def test_profile_csv_keeps_both_original_readings_and_legacy_header_compatibility(
    tmp_path, difference_input
):
    path, data, panels = difference_input
    original = (tmp_path / "sources/history.csv").read_bytes()
    old_output = tmp_path / "old-figures"
    render_evidence_panels(path, panels[:1], old_output)
    with (old_output / "evidence-panels-source-data.csv").open(encoding="utf-8") as stream:
        assert tuple(next(csv.reader(stream))) == _FIELDS
    output = tmp_path / "mixed-figures"
    figure = render_evidence_panels(path, [panels[0], _profile()], output)
    rows = source_rows(output)
    old_rows, difference_rows = rows[:4], rows[4:]
    assert [float(r["value"]) for r in old_rows] == [4, 8, 7, 9]
    assert {r["value_unit"] for r in old_rows} == {"W"}
    assert all(r["reference_original"] == r["comparison_original"] == "" for r in old_rows)
    assert [float(r["value"]) for r in difference_rows] == [6, 4, 2, 8]
    assert [float(r["reference_original"]) for r in difference_rows] == [20, 30, 40, 50]
    assert [float(r["comparison_original"]) for r in difference_rows] == [26, 34, 42, 58]
    assert [r["source_locator"] for r in difference_rows] == [
        "csv_records:5",
        "csv_records:7",
        "csv_records:6",
        "csv_records:8",
    ]
    assert {r["value_unit"] for r in difference_rows} == {"K"}
    assert {r["time_unit"] for r in difference_rows} == {"s"}
    assert all(json.loads(r["time_window"]) == [1, 3] for r in difference_rows)
    assert {r["difference_direction"] for r in difference_rows} == {"comparison-reference"}
    assert {r["crossing_time_kind"] for r in difference_rows} == {"first-matching-saved-sample"}
    declaration = data["table_calculations"][-1]
    assert all(json.loads(r["source_units"]) == declaration["units"] for r in difference_rows)
    assert all(json.loads(r["source_columns"]) == declaration["columns"] for r in difference_rows)
    assert "comparison minus reference" in figure["caption"]
    svg = (output / "evidence-panels.svg").read_text(encoding="utf-8")
    assert "Temperature difference (K)" in svg and "°C" not in svg and "<text" in svg
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
    assert (output / "evidence-panels-source-data.csv").read_bytes() == before
    assert (tmp_path / "sources/history.csv").read_bytes() == original
    checks = json.loads((output / "layout-checks.json").read_text(encoding="utf-8"))
    assert checks["text_inside_canvas"] and checks["text_nonoverlapping"]


def test_npz_selected_profile_and_prose_preserve_original_array_indices(tmp_path, difference_input):
    compiled, declaration = _select(tmp_path, array=True, panels=True)
    original = (tmp_path / declaration["source"]).read_bytes()
    package = build_analysis_section(compiled, tmp_path / "output")
    rows = source_rows(package.parent / "figures")
    assert [r["source_locator"] for r in rows] == [
        "array_indices:3",
        "array_indices:5",
        "array_indices:4",
        "array_indices:6",
    ]
    assert [float(r["reference_original"]) for r in rows] == [20, 30, 40, 50]
    assert [float(r["comparison_original"]) for r in rows] == [26, 34, 42, 58]
    result = _assemble_all(package, tmp_path / "section")
    assert result["resolved_values"]["mean-a"]["array_indices"] == [3, 5]
    assert result["resolved_values"]["cross-b"]["array_indices"] == [4, 6]
    assert result["resolved_values"]["mean-a"]["unit"] == "K"
    assert result["resolved_values"]["cross-b"]["raw_value"] == 3
    assert (tmp_path / declaration["source"]).read_bytes() == original


def test_automatic_metrics_include_new_operation_without_manual_values(tmp_path, difference_input):
    compiled, _ = _select(tmp_path, automatic=True)
    data = json.loads(compiled.read_text(encoding="utf-8"))
    evidence = data["evidence"]
    assert len(evidence) == 10
    assert {e["result_ref"]["calculation_id"] for e in evidence} == {"difference"}
    assert {e["result_ref"]["field"] for e in evidence} == {
        "start_value",
        "end_value",
        "change",
        "maximum",
        "time_mean",
    }
    assert all(e.get("value") is None and e.get("unit", "") == "" for e in evidence)
    assert all(e["source"] == "sources/history.csv" for e in evidence)


@pytest.mark.parametrize(
    "table_options,proposal_options",
    [
        ({"temporal_value_kind": "cumulative"}, {"temporal_value_kind": "cumulative"}),
        ({"temperature_reference": 20}, {"temperature_reference": 20}),
        ({"weight_kind": "area"}, {"weight_kind": "area"}),
        ({"unit_column": "unit"}, {"unit_column": "unit"}),
        ({"region_fraction": "fraction"}, {"region_fraction": "fraction"}),
        ({"region_complement": True}, {"region_complement": True}),
        ({"reference_kind": "reported-range"}, {"reference_kind": "reported-range"}),
        (
            {"pair_by": "state", "reference": "cold", "comparison": "hot"},
            {"paired_selector": {"pair_by": "state", "reference": "cold", "comparison": "hot"}},
        ),
        (
            {"units": {"time": "s", "reference": "degC", "comparison": "K"}},
            {"units": {"time": "s", "reference": "degC", "comparison": "K"}},
        ),
    ],
)
def test_inapplicable_options_fail_in_both_declaration_models(table_options, proposal_options):
    declaration = _difference_declaration()
    before = copy.deepcopy(declaration)
    with pytest.raises(ValueError):
        _TableCalculation.model_validate({**declaration, **table_options})
    with pytest.raises(ValueError):
        _Calculation.model_validate({**declaration, **_qualification(), **proposal_options})
    assert declaration == before


@pytest.mark.parametrize("options", [{"percentage": True}, {"source_record": 5}])
def test_proposal_metric_cannot_turn_difference_scalar_into_percentage_or_one_record(
    tmp_path, difference_input, options
):
    compiled, _ = _select(tmp_path)
    prepared = tmp_path / "materials"
    proposal_path = prepared / "proposal.json"
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    proposal["candidates"][0]["metrics"][0]["result_ref"].update(options)
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    with pytest.raises(ValueError, match="percentage|source_record"):
        compile_analysis(
            prepared, proposal_path, "thermal-difference", compiled.parent / "rejected"
        )
