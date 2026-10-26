"""Discrete response panels reuse the calculation/prose results and exact case IDs."""

import csv
import json
import os
import subprocess
import sys

import pytest

from cfdpaper.publication.evidence_panels import render_evidence_panels
from cfdpaper.publication.table_evidence import calculate_declared_table, resolve_table_result


def response_input(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "flow.csv").write_text("case,flow\nhigh,3\nlow,1\nmid,2\n", encoding="utf-8")
    (sources / "thermal.csv").write_text(
        "case,mean,peak\nhigh,310,312\nlow,320,325\nmid,314,318\n", encoding="utf-8"
    )
    (sources / "pressure.csv").write_text(
        "case,section,static,total\n"
        "high,inlet,100,120\nhigh,outlet,30,40\n"
        "low,inlet,20,22\nlow,outlet,4,5\n"
        "mid,inlet,50,60\nmid,outlet,10,15\n",
        encoding="utf-8",
    )
    declarations = [
        {
            "id": identifier,
            "source": source,
            "operation": "scalar_select",
            "columns": {"value": column},
            "units": {"value": unit},
            "group_by": "case",
        }
        for identifier, source, column, unit in (
            ("flow", "sources/flow.csv", "flow", "L/min"),
            ("mean", "sources/thermal.csv", "mean", "K"),
            ("peak", "sources/thermal.csv", "peak", "K"),
        )
    ]
    declarations.extend(
        {
            "id": identifier,
            "source": "sources/pressure.csv",
            "operation": "paired_change",
            "columns": {"value": column},
            "units": {"value": "Pa"},
            "group_by": "case",
            "pair_by": "section",
            "reference": "outlet",
            "comparison": "inlet",
        }
        for identifier, column in (("static", "static"), ("total", "total"))
    )
    data = {
        "table_calculations": declarations,
        "evidence": [
            {"id": f"e_{item['id']}", "result_ref": {"calculation_id": item["id"]}}
            for item in declarations
        ],
    }
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    panels = [
        {
            "kind": "response",
            "title": "Interface temperature",
            "x_label": "Volume flow rate",
            "y_label": "Temperature",
            "x_calculation_id": "flow",
            "series": [
                {"calculation_id": "mean", "label": "Area-weighted mean"},
                {"calculation_id": "peak", "label": "Facet maximum"},
            ],
        },
        {
            "kind": "response",
            "title": "Inlet–outlet pressure",
            "x_label": "Volume flow rate",
            "y_label": "Pressure difference",
            "x_calculation_id": "flow",
            "series": [
                {"calculation_id": "static", "field": "difference", "label": "Static pressure"},
                {"calculation_id": "total", "field": "difference", "label": "Total pressure"},
            ],
        },
    ]
    return path, data, panels


def source_rows(output):
    with (output / "evidence-panels-source-data.csv").open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_two_column_response_has_exact_bound_results_sources_and_standalone_script(tmp_path):
    path, data, panels = response_input(tmp_path)
    originals = {source: source.read_bytes() for source in (tmp_path / "sources").iterdir()}
    output = tmp_path / "figures"
    figure = render_evidence_panels(path, panels, output, columns=2)
    rows = source_rows(output)
    assert len(rows) == 12
    reports = [
        {**item, **calculate_declared_table(tmp_path / item["source"], item)}
        for item in data["table_calculations"]
    ]
    for row in rows:
        assert row["kind"] == "response" and row["group"] in {"high", "low", "mid"}
        for axis in ("x", "y"):
            bound = resolve_table_result(
                reports,
                calculation_id=row[f"{axis}_calculation_id"],
                group=row["group"],
                field=row[f"{axis}_field"],
            )
            assert float(row[axis]) == bound["raw_value"]
            assert row[f"{axis}_unit"] == bound["unit"]
            assert row[f"{axis}_source"] == bound["source"]
            assert row[f"{axis}_source_locator"] == "csv_records:" + ",".join(
                str(record) for record in bound["csv_records"]
            )
    assert {r["series_label"] for r in rows[:6]} == {"Area-weighted mean", "Facet maximum"}
    assert {r["y_unit"] for r in rows[:6]} == {"K"}
    assert {r["y_unit"] for r in rows[6:]} == {"Pa"}
    assert {r["x_unit"] for r in rows} == {"L/min"}
    assert figure["evidence_ids"] == ["e_flow", "e_mean", "e_peak", "e_static", "e_total"]
    assert "straight guides" not in figure["caption"]
    assert figure["sizing"]["source_width_mm"] == pytest.approx(160, abs=0.1)
    assert figure["sizing"]["minimum_source_font_pt"] >= 8
    summary = json.loads((output / "figure-summary.json").read_text(encoding="utf-8"))
    assert summary["checks"]["panel_layout"] == {"rows": 1, "columns": 2}
    assert summary["checks"]["text_inside_canvas"]
    assert summary["checks"]["text_nonoverlapping"]
    for extension in ("svg", "pdf", "png", "tiff"):
        assert (output / f"evidence-panels.{extension}").stat().st_size > 0
    svg = (output / "evidence-panels.svg").read_text(encoding="utf-8")
    assert "Temperature (K)" in svg and "Pressure difference (Pa)" in svg
    assert "Volume flow rate (L/min)" in svg and "<text" in svg
    script = (output / "plot.py").read_text(encoding="utf-8")
    assert "cfdpaper" not in script and "COLUMNS = 2" in script
    before = (output / "evidence-panels-source-data.csv").read_bytes()
    subprocess.run(
        [sys.executable, str(output / "plot.py")],
        cwd=output,
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
        check=True,
        capture_output=True,
        timeout=60,
    )
    assert (output / "evidence-panels-source-data.csv").read_bytes() == before
    assert all(source.read_bytes() == original for source, original in originals.items())


@pytest.mark.parametrize("connect", [False, True])
def test_response_connections_are_opt_in_sorted_straight_guides(tmp_path, monkeypatch, connect):
    from matplotlib.axes import Axes

    path, _, panels = response_input(tmp_path)
    panels[0]["connect"] = connect
    calls = []
    original_plot = Axes.plot

    def record_plot(self, x, y, **kwargs):
        calls.append((list(x), list(y), kwargs))
        return original_plot(self, x, y, **kwargs)

    monkeypatch.setattr(Axes, "plot", record_plot)
    figure = render_evidence_panels(path, panels[:1], tmp_path / "figures")
    assert len(calls) == 2
    assert calls[0][:2] == ([1, 2, 3], [320, 314, 310])
    assert calls[1][:2] == ([1, 2, 3], [325, 318, 312])
    assert all(call[2]["linestyle"] == ("-" if connect else "None") for call in calls)
    assert calls[0][2]["marker"] != calls[1][2]["marker"]
    if connect:
        assert "straight guides" in figure["caption"] and "not fits" in figure["caption"]
    else:
        assert "straight guides" not in figure["caption"]


@pytest.mark.parametrize("groups", [None, ["low", "mid"]])
def test_response_does_not_silently_intersect_missing_case_groups(tmp_path, groups):
    path, data, panels = response_input(tmp_path)
    (tmp_path / "sources/peak.csv").write_text("case,peak\nhigh,312\nlow,325\n")
    data["table_calculations"][2]["source"] = "sources/peak.csv"
    path.write_text(json.dumps(data), encoding="utf-8")
    if groups is not None:
        panels[0]["groups"] = groups
    with pytest.raises(ValueError, match="groups"):
        render_evidence_panels(path, panels[:1], tmp_path / "figures")
    assert not (tmp_path / "figures/evidence-panels.png").exists()


def test_response_explicit_group_subset_and_npz_source_indices(tmp_path):
    np = pytest.importorskip("numpy")
    path, data, panels = response_input(tmp_path)
    np.savez(tmp_path / "sources/flow.npz", case=["high", "low", "mid"], flow=[3, 1, 2])
    data["table_calculations"][0]["source"] = "sources/flow.npz"
    path.write_text(json.dumps(data), encoding="utf-8")
    panels[0]["groups"] = ["mid", "low"]
    render_evidence_panels(path, panels[:1], tmp_path / "figures")
    rows = source_rows(tmp_path / "figures")
    assert [r["group"] for r in rows] == ["mid", "low", "mid", "low"]
    assert [r["x_source_locator"] for r in rows] == [
        "array_indices:2",
        "array_indices:1",
        "array_indices:2",
        "array_indices:1",
    ]


@pytest.mark.parametrize(
    "defect, message",
    [
        ("missing-value", "unavailable"),
        ("mixed-unit", "same resolved y unit"),
        ("field", "unsupported field"),
        ("x-operation", "incompatible operation"),
        ("y-operation", "incompatible operation"),
    ],
)
def test_response_rejects_unavailable_values_incompatible_units_and_operations(
    tmp_path, defect, message
):
    path, data, panels = response_input(tmp_path)
    if defect == "missing-value":
        source = tmp_path / "sources/thermal.csv"
        source.write_text(source.read_text().replace("320,325", "320,"))
    elif defect == "mixed-unit":
        data["table_calculations"][2]["units"] = {"value": "Pa"}
    elif defect == "field":
        panels[0]["series"][0]["field"] = "mean"
    elif defect == "x-operation":
        panels[0]["x_calculation_id"] = "static"
    else:
        data["table_calculations"][1]["operation"] = "population"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        render_evidence_panels(path, panels[:1], tmp_path / "figures")
    assert not (tmp_path / "figures/evidence-panels.png").exists()


@pytest.mark.parametrize("field, unit", [("difference", "K"), ("relative_change", "")])
def test_response_field_units_follow_resolved_temperature_change_not_input_labels(
    tmp_path, field, unit
):
    path, data, panels = response_input(tmp_path)
    for declaration in data["table_calculations"][3:]:
        declaration.update(
            units={"value": "degC"}, quantity_kind="absolute-temperature", temperature_reference=0
        )
    for series in panels[1]["series"]:
        series["field"] = field
    panels[1].update(title="Matched observation change", y_label="Observation change")
    path.write_text(json.dumps(data), encoding="utf-8")
    render_evidence_panels(path, panels[1:], tmp_path / "figures")
    rows = source_rows(tmp_path / "figures")
    assert {row["y_unit"] for row in rows} == {unit}
    assert {row["y_field"] for row in rows} == {field}
    if field == "difference":
        assert [float(row["y"]) for row in rows] == [70, 16, 40, 80, 17, 45]
    else:
        assert float(rows[0]["y"]) == pytest.approx(70 / 30)


@pytest.mark.parametrize(
    "bad",
    [
        [],
        [{"calculation_id": "mean"}],
        [{"calculation_id": "mean", "label": "Mean", "smooth": True}],
    ],
)
def test_response_requires_explicit_nonempty_series_without_extra_operations(tmp_path, bad):
    path, _, panels = response_input(tmp_path)
    panels[0]["series"] = bad
    with pytest.raises(ValueError, match="series"):
        render_evidence_panels(path, panels[:1], tmp_path / "figures")


def test_response_unit_suffix_uses_results_and_preserves_physical_qualifiers(tmp_path):
    path, _, panels = response_input(tmp_path)
    panels[0]["y_label"] = "Temperature (interface)"
    render_evidence_panels(path, panels[:1], tmp_path / "figures")
    svg = (tmp_path / "figures/evidence-panels.svg").read_text(encoding="utf-8")
    assert "Temperature (interface) (K)" in svg
    panels[0]["y_label"] = "Temperature (Pa)"
    with pytest.raises(ValueError, match="unit"):
        render_evidence_panels(path, panels[:1], tmp_path / "wrong-unit")


@pytest.mark.parametrize("columns", [0, -1, True, 1.5])
def test_response_columns_are_a_positive_integer(tmp_path, columns):
    path, _, panels = response_input(tmp_path)
    with pytest.raises(ValueError, match="columns"):
        render_evidence_panels(path, panels, tmp_path / "figures", columns=columns)


def test_response_author_script_is_preserved(tmp_path):
    path, _, panels = response_input(tmp_path)
    output = tmp_path / "figures"
    output.mkdir()
    script = output / "plot.py"
    script.write_text("# Author's local refinement\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Preserve"):
        render_evidence_panels(path, panels, output, columns=2)
    assert script.read_text(encoding="utf-8") == "# Author's local refinement\n"


def test_dimensionless_axes_keep_an_explicit_unit_without_empty_parentheses(tmp_path):
    path, data, panels = response_input(tmp_path)
    for declaration in data["table_calculations"][:3]:
        declaration["units"]["value"] = "1"
    path.write_text(json.dumps(data), encoding="utf-8")
    panel = {**panels[0], "x_label": "Control index", "y_label": "Response ratio"}
    render_evidence_panels(path, [panel], tmp_path / "figures")
    svg = (tmp_path / "figures/evidence-panels.svg").read_text(encoding="utf-8")
    assert "Control index (1)" in svg and "Response ratio (1)" in svg
    assert "Response ratio ()" not in svg
