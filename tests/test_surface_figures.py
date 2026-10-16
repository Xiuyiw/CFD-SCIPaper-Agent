import csv
import json

import numpy as np
import pytest

from cfdpaper.publication.render_figure import PlotStyle
from cfdpaper.publication.surface_figures import _read_study, render_surface_study


def study(tmp_path, *, cases=2, relation="above", unit="K"):
    (tmp_path / "sources").mkdir()
    vertices = np.array(
        [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [4, 0, 0], [4, 1, 0]], dtype=float
    )
    data = {
        "domain": "test wall",
        "quantity": "Temperature",
        "unit": unit,
        "coordinate_unit": "m",
        "projection_axes": [0, 1],
        "thresholds": [300, 350, 400],
        "exceedance_relation": relation,
        "arrays": {
            "values": "face_value",
            "weights": "area_m2",
            "vertices": "vertices_m",
            "connectivity": "faces_connectivity",
            "starts": "face_starts",
        },
        "cases": [],
    }
    for index in range(cases):
        name = chr(65 + index)
        np.savez(
            tmp_path / f"sources/{name}.npz",
            face_value=[300.0 + 50 * index, 400.0 + 50 * index],
            area_m2=[1.0, 3.0],
            vertices_m=vertices,
            faces_connectivity=[4, 0, 1, 2, 3, 4, 1, 4, 5, 2],
            face_starts=[0, 5],
        )
        data["cases"].append({"id": name, "label": f"Case {name}", "source": f"sources/{name}.npz"})
    path = tmp_path / "study.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data


def csv_rows(output, filename):
    with (output / filename).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


@pytest.mark.parametrize("cases,y_scale", [(2, 2.0), (4, 1.0), (2, 8.0)])
def test_colorbar_matches_equal_aspect_field_bounds(tmp_path, monkeypatch, cases, y_scale):
    import cfdpaper.publication.surface_figures as surface_figures

    path, _ = study(tmp_path, cases=cases)
    for source in (tmp_path / "sources").iterdir():
        with np.load(source, allow_pickle=False) as bundle:
            arrays = {key: bundle[key].copy() for key in bundle.files}
        arrays["vertices_m"][:, 1] *= y_scale
        arrays["area_m2"] *= y_scale
        np.savez(source, **arrays)

    def inspect(fig, output, figure_id, style):
        fig.canvas.draw()
        if figure_id == "field":
            axes, colorbar = fig.axes[:-1], fig.axes[-1]
            assert len(axes) == cases
            bottom = min(ax.get_window_extent().y0 for ax in axes)
            top = max(ax.get_window_extent().y1 for ax in axes)
            assert colorbar.get_window_extent().y0 == pytest.approx(bottom, abs=0.5)
            assert colorbar.get_window_extent().y1 == pytest.approx(top, abs=0.5)
            for ax in axes:
                assert ax.get_xlim() == (0, 4)
                assert ax.get_ylim() == (0, y_scale)
                assert ax.get_aspect() == 1
            assert fig.get_figwidth() * 25.4 == pytest.approx(style.width_mm)
        return {
            "source_width_mm": style.width_mm,
            "target_width_mm": style.width_mm,
            "minimum_source_font_pt": 8,
        }

    monkeypatch.setattr(surface_figures, "_export", inspect)
    render_surface_study(path, tmp_path / "figures")


def test_field_vertical_crop_preserves_width_and_distribution_size(tmp_path, monkeypatch):
    from matplotlib.figure import Figure
    from PIL import Image

    path, _ = study(tmp_path)
    for source in (tmp_path / "sources").iterdir():
        with np.load(source, allow_pickle=False) as bundle:
            arrays = {key: bundle[key].copy() for key in bundle.files}
        arrays["vertices_m"][:, 1] *= 2
        arrays["area_m2"] *= 2
        np.savez(source, **arrays)
    data_heights = []
    savefig = Figure.savefig

    def capture(self, filename, *args, **kwargs):
        if str(filename).endswith("field.png"):
            data_heights.append(self.axes[0].get_window_extent().height / self.dpi)
        return savefig(self, filename, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", capture)
    output = tmp_path / "figures"
    figures = render_surface_study(path, output)
    with Image.open(output / "field.png") as field:
        assert field.width / 300 * 25.4 == pytest.approx(160, abs=0.1)
        assert field.height / 300 * 25.4 < 60
        assert data_heights[0] * 300 / field.height > 0.55
    with Image.open(output / "distribution.png") as distribution:
        assert distribution.width / 300 * 25.4 == pytest.approx(160, abs=0.1)
        assert distribution.height / 300 * 25.4 == pytest.approx(110, abs=0.1)
    assert figures[0]["sizing"]["minimum_source_font_pt"] == 8


def test_exact_polygons_shared_scale_units_sources_and_formats(tmp_path, monkeypatch):
    from matplotlib.collections import PolyCollection

    path, _ = study(tmp_path)
    originals = {file: file.read_bytes() for file in (tmp_path / "sources").iterdir()}
    collections = []
    original = PolyCollection.__init__

    def capture(self, verts, *args, **kwargs):
        if "array" in kwargs and len(verts) == 2:
            collections.append((np.array(verts), np.array(kwargs["array"]), kwargs["norm"]))
        original(self, verts, *args, **kwargs)

    monkeypatch.setattr(PolyCollection, "__init__", capture)
    output = tmp_path / "figures"
    output.mkdir()
    (output / "plot.py").write_text("# author-owned wrapper", encoding="utf-8")
    figures = render_surface_study(path, output)
    assert [figure["id"] for figure in figures] == ["field", "distribution"]
    assert [figure["path"] for figure in figures] == ["field.png", "distribution.png"]
    for figure in figures:
        assert figure["sizing"]["source_width_mm"] == pytest.approx(160, abs=0.1)
        assert figure["sizing"]["minimum_source_font_pt"] >= 8
        for extension in ("svg", "pdf", "png", "tiff"):
            assert (output / f"{figure['id']}.{extension}").stat().st_size > 0
    assert len(collections) == 2
    assert collections[0][0].tolist() == [
        [[0, 0], [1, 0], [1, 1], [0, 1]],
        [[1, 0], [4, 0], [4, 1], [1, 1]],
    ]
    assert collections[0][1].tolist() == [300, 400]
    assert collections[0][2] is collections[1][2]
    assert (collections[0][2].vmin, collections[0][2].vmax) == (300, 450)
    source = csv_rows(output, "field-source-data.csv")
    assert [float(row["area"]) for row in source] == [1, 3, 1, 3]
    assert [int(row["array_index"]) for row in source] == [0, 1, 0, 1]
    assert [float(row["value"]) for row in source] == [300, 400, 350, 450]
    assert {row["value_unit"] for row in source} == {"K"}
    assert {row["area_unit"] for row in source} == {"m^2"}
    threshold = csv_rows(output, "threshold-source-data.csv")
    a = [row for row in threshold if row["case_id"] == "A"]
    assert [float(row["exceedance_fraction"]) for row in a] == [0.75, 0.75, 0]
    assert [float(row["measure_above"]) for row in a] == [3, 3, 0]
    assert all(float(row["weight_sum"]) == 4 for row in threshold)
    svg = (output / "field.svg").read_text(encoding="utf-8")
    assert "<text" in svg and "Temperature (K)" in svg and "x (m)" in svg
    distribution = (output / "distribution.svg").read_text(encoding="utf-8")
    assert "Temperature threshold (K)" in distribution and "Area fraction (%)" in distribution
    checks = json.loads((output / "surface-checks.json").read_text(encoding="utf-8"))
    assert checks["value_range"] == [300, 450]
    assert checks["curve_kind"] == "exact-empirical-step"
    assert checks["case_markers"] == {"A": "o", "B": "s"}
    for name in ("field", "distribution"):
        assert checks[name]["text_inside_canvas"] and checks[name]["text_nonoverlapping"]
    assert (output / "plot.py").read_text() == "# author-owned wrapper"
    assert all(file.read_bytes() == content for file, content in originals.items())


def test_inclusive_exact_steps_and_four_case_font_fallback(tmp_path, monkeypatch):
    from matplotlib.axes import Axes

    path, data = study(tmp_path, cases=4, relation="at-or-above")
    data["unrelated_metadata"] = {"ignored": True}
    path.write_text(json.dumps(data))
    steps = []
    original = Axes.step

    def capture(self, x, y, *args, **kwargs):
        steps.append((x, y, kwargs["where"]))
        return original(self, x, y, *args, **kwargs)

    monkeypatch.setattr(Axes, "step", capture)
    output = tmp_path / "figures"
    render_surface_study(
        path,
        output,
        style=PlotStyle(
            width_mm=160,
            height_mm=185,
            font_family="Nonexistent test font",
            font_pt=9,
            axis_label_pt=9,
            title_pt=10,
            tick_pt=8,
            legend_pt=9,
        ),
    )
    assert len(steps) == 4
    assert all(step[2] == "pre" for step in steps)
    first = dict(zip(steps[0][0], steps[0][1], strict=True))
    assert first[300] == 100 and first[350] == 75 and first[400] == 75
    assert 450 in steps[1][0]  # A raw value, even though not a configured threshold.
    curve = csv_rows(output, "distribution-source-data.csv")
    assert any(float(row["threshold"]) == 450 for row in curve if row["case_id"] == "B")


@pytest.mark.parametrize(
    "key,value,match",
    [
        ("face_value", [300.0], "align"),
        ("area_m2", [1.0, -1.0], "positive"),
        ("area_m2", [1.0, np.nan], "finite"),
        ("face_value", [300.0, np.inf], "finite"),
        ("face_starts", [0, 4], "partition"),
        ("faces_connectivity", [4, 0, 1, 2, 3, 4, 1, 4, 90, 2], "indices"),
        ("faces_connectivity", [4.0, 0, 1, 2, 3, 4, 1, 4, 5, 2], "integer"),
    ],
)
def test_bad_geometry_or_weights_rejected_before_output(tmp_path, key, value, match):
    path, _ = study(tmp_path)
    source = tmp_path / "sources/A.npz"
    with np.load(source, allow_pickle=False) as bundle:
        arrays = {name: bundle[name] for name in bundle.files}
    arrays[key] = value
    np.savez(source, **arrays)
    with pytest.raises(ValueError, match=match):
        render_surface_study(path, tmp_path / "figures")
    assert not (tmp_path / "figures").exists()


@pytest.mark.parametrize(
    "change,match",
    [
        ({"coordinate_unit": "mm"}, "declared in m"),
        ({"projection_axes": [0, 2]}, "zero projected area"),
        ({"projection_axes": [1, 1]}, "distinct"),
        ({"thresholds": []}, "thresholds"),
        ({"exceedance_relation": "below"}, "exceedance_relation"),
    ],
)
def test_invalid_declarations_rejected(tmp_path, change, match):
    path, data = study(tmp_path)
    path.write_text(json.dumps({**data, **change}))
    with pytest.raises(ValueError, match=match):
        _read_study(path)


def test_non_temperature_and_permuted_projection_retain_declared_units(tmp_path):
    path, data = study(tmp_path, unit="Pa")
    data.update(quantity="Pressure", projection_axes=[1, 0])
    path.write_text(json.dumps(data))
    output = tmp_path / "figures"
    render_surface_study(path, output)
    svg = (output / "field.svg").read_text(encoding="utf-8")
    assert "Pressure (Pa)" in svg
    rows = csv_rows(output, "field-source-data.csv")
    assert [float(row["value"]) for row in rows] == [300, 400, 350, 450]
