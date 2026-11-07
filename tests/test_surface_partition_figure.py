"""Original-face maps and exact partition contributions share one explicit selection."""

import csv
import json
from copy import deepcopy

import numpy as np
import pytest

from cfdpaper.publication import surface_partition_figure as module
from tests.publication.test_partition_change import declaration, surface


@pytest.mark.parametrize("sign", [-1, 1])
def test_small_component_label_points_to_its_own_segment(sign):
    import matplotlib.pyplot as plt

    from cfdpaper.publication.diagnostic_figures import _plot_partition_contribution
    from cfdpaper.publication.render_figure import PlotStyle

    report = {"groups": [{"group": "all", "result": {"difference_mean": 5.7 * sign}}]}
    entries = [
        {
            "group": name,
            "series_index": 0,
            "label": "Pair",
            "report": report,
            "result": {"contribution": value * sign},
        }
        for name, value in (("small", 0.35), ("large", 5.35))
    ]
    fig = plt.figure()
    try:
        (ax,) = _plot_partition_contribution(fig, {}, entries, PlotStyle())
        label = next(text for text in ax.texts if text.get_text() == f"{0.35 * sign:+.2f}")
        assert label.arrow_patch is not None
        assert label.xy == pytest.approx((0.175 * sign, 0))
        assert label.get_position()[1] < 0
        assert [patch.get_width() for patch in ax.patches] == pytest.approx(
            [0.35 * sign, 5.35 * sign]
        )
    finally:
        plt.close(fig)


def fixture(tmp_path, pairs=1):
    sources = tmp_path / "sources"
    sources.mkdir()
    cases, calculations, series = [], [], []
    for index in range(pairs):
        name = chr(65 + index)
        for role, values in (
            ("reference", [320, 300, 300, 300] if index == 0 else [315, 299, 299, 299]),
            ("comparison", [302, 302, 302, 318] if index == 0 else [298, 298, 298, 313]),
        ):
            identity = f"{name}-{role}"
            source = sources / f"{identity}.npz"
            surface(source, values, widths=(1, 1, 1, 1))
            with np.load(source) as bundle:
                arrays = {key: bundle[key].copy() for key in bundle.files}
            arrays["vertices_m"][:, 1] *= 4
            arrays["area"] *= 4
            np.savez(source, **arrays)
            cases.append(
                {"id": identity, "label": f"{name} / {role}", "source": f"sources/{identity}.npz"}
            )
        calc = declaration(reference_source=f"{name}-reference.npz", support_mode="moving")
        calc["id"], calc["source"] = f"change-{name}", f"sources/{name}-comparison.npz"
        for region in calc["field_options"]["regions"]:
            region["bounds"]["y"] = [0, 4]
        calc["field_options"]["reference_regions"] = deepcopy(calc["field_options"]["regions"])
        for region in calc["field_options"]["regions"]:
            region["bounds"]["x"] = [3, 4]
        calculations.append(calc)
        series.append({"calculation_id": calc["id"], "label": f"Structure {name}"})
    study = {
        "study_id": "surface-test",
        "domain": "one original planar wall",
        "quantity": "Temperature",
        "unit": "K",
        "coordinate_unit": "m",
        "projection_axes": [0, 1],
        "thresholds": [310],
        "arrays": {
            "values": "temperature",
            "weights": "area",
            "vertices": "vertices_m",
            "connectivity": "faces_connectivity",
            "starts": "face_starts",
        },
        "cases": cases,
    }
    diagnostic = {
        "field_calculations": calculations,
        "panels": [
            {
                "id": "contributions",
                "kind": "partition_contribution",
                "title": "Regional temperature-change contributions",
                "group_labels": {"hot": "Heated footprint", "rest": "Remaining wall"},
                "series": series,
            }
        ],
    }
    study_path, diagnostic_path = tmp_path / "study.json", tmp_path / "diagnostics.json"
    study_path.write_text(json.dumps(study), encoding="utf-8")
    diagnostic_path.write_text(json.dumps(diagnostic), encoding="utf-8")
    return study_path, diagnostic_path, study, diagnostic


@pytest.mark.parametrize("pairs", [1, 2])
def test_original_fields_exact_moving_regions_contributions_and_bbox(tmp_path, monkeypatch, pairs):
    study_path, diagnostic_path, study, _ = fixture(tmp_path, pairs)
    originals = {path: path.read_bytes() for path in tmp_path.rglob("*.npz")}
    original_export = module._export
    seen = []

    def inspect(fig, output, identity, style):
        from matplotlib.collections import PolyCollection
        from matplotlib.patches import Rectangle

        maps = [ax for ax in fig.axes if any(isinstance(c, PolyCollection) for c in ax.collections)]
        assert len(maps) == 2 * pairs
        norms = []
        for ax, case in zip(maps, study["cases"], strict=True):
            collection = next(c for c in ax.collections if isinstance(c, PolyCollection))
            with np.load(tmp_path / case["source"]) as bundle:
                np.testing.assert_array_equal(collection.get_array(), bundle["temperature"])
            norms.append((collection.norm.vmin, collection.norm.vmax))
            boxes = [patch for patch in ax.patches if isinstance(patch, Rectangle)]
            assert len(boxes) == 1  # The complementary region must not duplicate the box.
            assert boxes[0].get_xy() == (0 if "reference" in case["id"] else 3, 0)
            assert boxes[0].get_width() == 1 and boxes[0].get_height() == 4
            assert ax.get_xlim() == (0, 4) and ax.get_ylim() == (0, 4)
            assert ax.get_aspect() == 1
        assert len(set(norms)) == 1
        contribution = fig.axes[-1]
        expected = [-0.5, 1.5] + ([-0.5, -0.75] if pairs == 2 else [])
        assert [bar.get_width() for bar in contribution.patches] == pytest.approx(expected)
        diamonds = [line for line in contribution.lines if line.get_marker() == "D"]
        assert [line.get_xdata()[0] for line in diamonds] == pytest.approx(
            [1.0] + ([-1.25] if pairs == 2 else [])
        )
        assert "R1" in contribution.get_legend().get_texts()[0].get_text()
        seen.append(True)
        return original_export(fig, output, identity, style)

    monkeypatch.setattr(module, "_export", inspect)
    output = tmp_path / "figures"
    result = module.render_surface_partition(
        study_path, diagnostic_path, output, panel_id="contributions"
    )
    assert seen and result["id"] == "contributions"
    assert result["reading"]["operation"] == "partition_change"
    assert result["reading"]["selection"]["case_ids"] == [case["id"] for case in study["cases"]]
    first = result["reading"]["comparisons"][0]
    assert first["calculation_id"] == "change-A"
    assert first["reference"]["source"] == "sources/A-reference.npz"
    assert first["reference"]["diagnostic_source"] == "sources/A-reference.npz"
    assert "source_path" not in first["reference"]
    assert first["comparison"]["columns"] == {"value": "temperature", "measure": "area"}
    assert first["reference"]["regions"][0]["bounds"]["x"] == [0, 1]
    assert first["comparison"]["regions"][0]["bounds"]["x"] == [3, 4]
    assert first["results"][0]["result"]["difference_mean"] == 1
    assert all(set(group) == {"group", "status", "result"} for group in first["results"])
    assert first["result_ref"] == {"calculation_id": "change-A"}
    assert "not heat" in result["caption"]
    assert "directly reduced" in result["caption"]
    checks = json.loads((output / "diagnostic-checks.json").read_text())["contributions"]
    assert checks["text_inside_canvas"] and checks["text_nonoverlapping"]
    assert checks["minimum_source_font_pt"] >= 8.5
    assert checks["source_width_mm"] == pytest.approx(160, abs=0.1)
    for extension in ("png", "svg", "pdf", "tiff"):
        assert (output / f"contributions.{extension}").stat().st_size > 0
    assert "<text" in (output / "contributions.svg").read_text(encoding="utf-8")
    with (output / "contributions-source-data.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2 * pairs
    assert float(rows[0]["contribution"]) == -0.5
    with (output / "contributions-field-source-data.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        assert len(list(csv.DictReader(stream))) == 8 * pairs
    assert all(path.read_bytes() == content for path, content in originals.items())


@pytest.mark.parametrize("mismatch", ["source", "value", "measure", "unit", "reference_value"])
def test_mismatched_surface_source_columns_or_units_are_rejected(tmp_path, mismatch):
    study_path, diagnostic_path, study, diagnostic = fixture(tmp_path)
    calc = diagnostic["field_calculations"][0]
    if mismatch == "source":
        study["cases"][1]["source"] = "sources/A-reference.npz"
        study_path.write_text(json.dumps(study), encoding="utf-8")
    elif mismatch in {"value", "measure"}:
        calc["columns"][mismatch] = "not-the-displayed-array"
    elif mismatch == "reference_value":
        calc["field_options"]["reference_columns"] = {
            "value": "not-the-displayed-array",
            "measure": "area",
        }
    else:
        calc["units"]["value"] = "degC"
    diagnostic_path.write_text(json.dumps(diagnostic), encoding="utf-8")
    with pytest.raises(ValueError, match="match|unit"):
        module.render_surface_partition(
            study_path, diagnostic_path, tmp_path / "figures", panel_id="contributions"
        )


def test_author_local_script_is_runnable_and_preserved(tmp_path):
    import subprocess
    import sys

    study_path, diagnostic_path, _, _ = fixture(tmp_path)
    output = tmp_path / "figures"
    module.render_surface_partition(study_path, diagnostic_path, output, panel_id="contributions")
    script = output / "plot.py"
    script.write_text(
        script.read_text(encoding="utf-8") + "\n# Author local edit\n", encoding="utf-8"
    )
    original = script.read_bytes()
    subprocess.run([sys.executable, str(script)], check=True, capture_output=True, text=True)
    assert script.read_bytes() == original
    metadata = json.loads((output / "diagnostic-figures.json").read_text(encoding="utf-8"))
    assert metadata["figures"][0]["reading"]["panel_id"] == "contributions"
    assert metadata["visual_review"] == "required"


@pytest.mark.parametrize(
    "unit,kind", [("Pa", "ordinary"), ("K", "ordinary"), ("degC", "absolute-temperature")]
)
def test_renderer_is_explicitly_limited_to_absolute_temperature_in_kelvin(tmp_path, unit, kind):
    study_path, diagnostic_path, study, diagnostic = fixture(tmp_path)
    study["unit"] = unit
    diagnostic["field_calculations"][0]["quantity_kind"] = kind
    diagnostic["field_calculations"][0]["units"]["value"] = unit
    study_path.write_text(json.dumps(study), encoding="utf-8")
    diagnostic_path.write_text(json.dumps(diagnostic), encoding="utf-8")
    with pytest.raises(ValueError, match="absolute.temperature"):
        module.render_surface_partition(
            study_path, diagnostic_path, tmp_path / "figures", panel_id="contributions"
        )
