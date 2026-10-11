import csv
import json
import runpy

import numpy as np
import pytest

from cfdpaper.publication.evidence_panels import render_evidence_panels
from cfdpaper.publication.render_figure import PlotStyle


def panel_input(tmp_path):
    (tmp_path / "sources").mkdir(exist_ok=True)
    (tmp_path / "sources/history.csv").write_text(
        "case,t,q\nA,0,2\nB,0,3\nA,1,4\nB,1,7\nA,3,8\nB,3,9\n", encoding="utf-8"
    )
    (tmp_path / "sources/ranges.csv").write_text(
        "case,model,center,low,high\nA,11,10,8,12\nB,15,10,8,12\n", encoding="utf-8"
    )
    data = {
        "table_calculations": [
            {
                "id": "history",
                "source": "sources/history.csv",
                "operation": "temporal",
                "columns": {"time": "t", "value": "q"},
                "units": {"time": "s", "value": "W"},
                "group_by": "case",
                "time_window": [0, 1],
                "threshold": 100,
            },
            {
                "id": "range",
                "source": "sources/ranges.csv",
                "operation": "reference_range",
                "columns": {
                    "value": "model",
                    "reference": "center",
                    "lower": "low",
                    "upper": "high",
                },
                "units": {key: "s" for key in ("value", "reference", "lower", "upper")},
                "group_by": "case",
                "reference_kind": "reported-range",
            },
        ],
        "evidence": [
            {"id": "a", "result_ref": {"calculation_id": "history"}},
            {"id": "b", "result_ref": {"calculation_id": "range"}},
        ],
    }
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    panels = [
        {
            "kind": "profile",
            "calculation_id": "history",
            "title": "Saved power history",
            "x_label": "Time",
            "y_label": "Power",
        },
        {
            "kind": "reference_range",
            "calculation_id": "range",
            "title": "Event timing",
            "x_label": "Time",
            "y_label": "Configuration",
        },
    ]
    return path, data, panels


def source_rows(output):
    with (output / "evidence-panels-source-data.csv").open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def test_complementary_render_exact_sources_units_and_standalone_replay(tmp_path):
    path, _, panels = panel_input(tmp_path)
    original = (tmp_path / "sources/history.csv").read_bytes()
    output = tmp_path / "figures"
    figure = render_evidence_panels(path, panels, output)
    assert figure["id"] == "1"  # Standalone sections print IDs as publication labels.
    rows = source_rows(output)
    assert len(rows) == 6
    assert [float(r["time"]) for r in rows[:4]] == [0, 1, 0, 1]
    assert [r["source_locator"] for r in rows[:4]] == [
        "csv_records:2",
        "csv_records:4",
        "csv_records:3",
        "csv_records:5",
    ]
    assert [float(r["difference"]) for r in rows[4:]] == [1, 5]
    assert [float(r["outside_distance"]) for r in rows[4:]] == [0, 3]
    assert {r["value_unit"] for r in rows[:4]} == {"W"}
    assert {r["value_unit"] for r in rows[4:]} == {"s"}
    assert figure["sizing"]["source_width_mm"] == pytest.approx(160, abs=0.1)
    assert figure["sizing"]["minimum_source_font_pt"] >= 8
    assert figure["evidence_ids"] == ["a", "b"]
    assert "not confidence intervals" in figure["caption"]
    for extension in ("svg", "pdf", "png", "tiff"):
        assert (output / f"evidence-panels.{extension}").stat().st_size > 0
    assert "<text" in (output / "evidence-panels.svg").read_text(encoding="utf-8")
    script = output / "plot.py"
    assert "cfdpaper" not in script.read_text(encoding="utf-8")
    runpy.run_path(str(script))
    assert (tmp_path / "sources/history.csv").read_bytes() == original
    checks = json.loads((output / "layout-checks.json").read_text())
    assert checks["text_inside_canvas"] and checks["text_nonoverlapping"]


def test_group_selection_cumulative_and_npz_locations(tmp_path):
    path, data, panels = panel_input(tmp_path)
    np.savez(tmp_path / "sources/history.npz", t=[0, 2, 5], q=[1, 4, 10])
    data["table_calculations"][0].update(
        source="sources/history.npz",
        time_window=[2, 5],
        group_by=None,
        temporal_value_kind="cumulative",
        units={"time": "s", "value": "J"},
    )
    path.write_text(json.dumps(data))
    panels[0]["groups"] = ["all"]
    output = tmp_path / "figures"
    render_evidence_panels(path, panels[:1], output)
    rows = source_rows(output)
    assert [r["source_locator"] for r in rows] == ["array_indices:1", "array_indices:2"]
    assert [float(r["value"]) for r in rows] == [4, 10]
    assert {r["temporal_value_kind"] for r in rows} == {"cumulative"}


def test_missing_range_or_profile_is_not_drawn_as_zero(tmp_path):
    path, _, panels = panel_input(tmp_path)
    (tmp_path / "sources/ranges.csv").write_text(
        "case,model,center,low,high\nA,11,10,,12\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="unavailable"):
        render_evidence_panels(path, panels, tmp_path / "figures")
    assert not (tmp_path / "figures/evidence-panels.png").exists()


def test_temperature_range_difference_keeps_kelvin_and_supplied_half_width(tmp_path):
    path, data, panels = panel_input(tmp_path)
    (tmp_path / "sources/ranges.csv").write_text(
        "case,model,center,width\nA,105,100,3\n", encoding="utf-8"
    )
    data["table_calculations"][1].update(
        columns={"value": "model", "reference": "center", "half_width": "width"},
        units={"value": "degC", "reference": "degC", "half_width": "degC"},
        quantity_kind="absolute-temperature",
        reference_kind="figure-reading-envelope",
    )
    path.write_text(json.dumps(data), encoding="utf-8")
    figure = render_evidence_panels(path, panels[1:], tmp_path / "figures")
    row = source_rows(tmp_path / "figures")[0]
    assert row["value_unit"] == "degC" and row["difference_unit"] == "K"
    assert float(row["reference_lower"]) == 97 and float(row["reference_upper"]) == 103
    assert float(row["difference"]) == 5 and float(row["outside_distance"]) == 2
    assert "figure-reading-envelope" in figure["caption"]


@pytest.mark.parametrize(
    "change,match",
    [
        ({"kind": "schematic"}, "Unsupported"),
        ({"calculation_id": "range"}, "incompatible"),
        ({"groups": ["missing"]}, "groups"),
        ({"smooth": True}, "requires"),
    ],
)
def test_unsupported_panels_reject_explicitly(tmp_path, change, match):
    path, _, panels = panel_input(tmp_path)
    panels[0].update(change)
    with pytest.raises(ValueError, match=match):
        render_evidence_panels(path, panels, tmp_path / "figures")


def test_author_script_is_never_overwritten(tmp_path):
    path, _, panels = panel_input(tmp_path)
    output = tmp_path / "figures"
    output.mkdir()
    (output / "plot.py").write_text("# author edits", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Preserve"):
        render_evidence_panels(path, panels, output)
    assert (output / "plot.py").read_text() == "# author edits"


def test_missing_font_uses_serif_fallback_and_small_fonts_rejected(tmp_path):
    path, _, panels = panel_input(tmp_path)
    render_evidence_panels(
        path,
        panels,
        tmp_path / "figures",
        style=PlotStyle(width_mm=160, height_mm=130, font_family="Missing test font"),
    )
    with pytest.raises(ValueError, match="8 pt"):
        render_evidence_panels(
            path,
            panels,
            tmp_path / "small",
            style=PlotStyle(width_mm=160, height_mm=130, tick_pt=7),
        )
