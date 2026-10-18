import csv
import json
import subprocess
import sys

import numpy as np
import pytest

from cfdpaper.publication.diagnostic_figures import render_diagnostic_figures


def make_config(tmp_path):
    (tmp_path / "sources").mkdir()
    declarations = []
    for name, temperature, flux in (
        ("A", [300.0, 320.0, 340.0], [10.0, -4.0, 2.0]),
        ("B", [310.0, 315.0, 335.0], [8.0, -6.0, 3.0]),
    ):
        np.savez(
            tmp_path / f"sources/{name}.npz",
            temperature=temperature,
            heat_flux=flux,
            area=[1.0, 2.0, 1.0],
            x=[0.0, 1.0, 2.0],
            y=[0.0, 0.0, 0.0],
            z=[0.0, 0.0, 0.0],
        )
        common = {"source": f"sources/{name}.npz", "domain": "interface faces"}
        declarations.extend(
            [
                {
                    **common,
                    "id": f"temperature-{name}",
                    "operation": "field_integral",
                    "columns": {"value": "temperature", "measure": "area", "x": "x"},
                    "units": {"value": "K", "measure": "m2", "x": "m"},
                    "field_options": {
                        "association": "face",
                        "integrand": "weighted_mean",
                        "region_assignment": "centroid",
                        "partition_complete": True,
                        "regions": [
                            {"id": "heated", "bounds": {"x": [0, 1]}},
                            {"id": "remaining", "bounds": {"x": [1, 3]}},
                        ],
                    },
                },
                {
                    **common,
                    "id": f"heat-{name}",
                    "operation": "field_integral",
                    "columns": {"value": "heat_flux", "measure": "area"},
                    "units": {"value": "W/m2", "measure": "m2"},
                    "field_options": {"association": "face", "integrand": "density"},
                },
            ]
        )
    (tmp_path / "sources/budget.csv").write_text(
        "incoming,outgoing,source,storage\n100,85,5,10\n", encoding="utf-8"
    )
    declarations.extend(
        [
            {
                "id": "budget",
                "source": "sources/budget.csv",
                "domain": "solid control volume",
                "operation": "energy_budget",
                "columns": dict(
                    zip(
                        ("input", "output", "source", "storage"),
                        ("incoming", "outgoing", "source", "storage"),
                        strict=True,
                    )
                ),
                "units": dict.fromkeys(("input", "output", "source", "storage"), "W"),
                "field_options": {"association": "control_volume"},
            },
            {
                "id": "difference",
                "source": "sources/B.npz",
                "domain": "same interface faces",
                "operation": "field_difference",
                "columns": {
                    "value": "temperature",
                    "measure": "area",
                    "x": "x",
                    "y": "y",
                    "z": "z",
                },
                "units": {"value": "K", "measure": "m2", "x": "m", "y": "m", "z": "m"},
                "field_options": {"association": "face", "reference_source": "A.npz"},
            },
        ]
    )
    config = {
        "field_calculations": declarations,
        "panels": [
            {
                "id": "regional",
                "kind": "regional",
                "title": "Regional temperature and area",
                "series": [
                    {"calculation_id": f"temperature-{name}", "label": f"Case {name}"}
                    for name in ("A", "B")
                ],
            },
            {
                "id": "exchange",
                "kind": "signed_flux",
                "title": "Opposing interface exchanges",
                "sign_convention": "Positive heat enters the solid.",
                "series": [
                    {"calculation_id": f"heat-{name}", "label": f"Case {name}"}
                    for name in ("A", "B")
                ],
            },
            {
                "id": "budget",
                "kind": "budget",
                "title": "Heat budget",
                "series": [{"calculation_id": "budget", "label": "Case A"}],
            },
            {
                "id": "difference",
                "kind": "matched_difference",
                "title": "Same-location response",
                "series": [{"calculation_id": "difference", "label": "B relative to A"}],
            },
        ],
    }
    path = tmp_path / "diagnostics.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path, config


def test_outputs_recalculate_declared_fields_and_keep_exact_sources(tmp_path):
    path, _ = make_config(tmp_path)
    output = tmp_path / "figures"
    figures = render_diagnostic_figures(path, output)
    assert [figure["id"] for figure in figures] == ["regional", "exchange", "budget", "difference"]
    for figure in figures:
        assert figure["sizing"]["source_width_mm"] == pytest.approx(160, abs=0.1)
        for suffix in ("svg", "pdf", "png", "tiff"):
            assert (output / f"{figure['id']}.{suffix}").stat().st_size > 0
        assert "<text" in (output / f"{figure['id']}.svg").read_text(encoding="utf-8")
    with (output / "exchange-source-data.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert float(rows[0]["positive"]) == 12
    assert float(rows[0]["negative"]) == -8
    assert float(rows[0]["net"]) == 4
    assert rows[0]["source"] == "sources/A.npz"
    assert json.loads(rows[0]["array_indices"]) == [0, 1, 2]
    assert "Positive heat enters the solid" in figures[1]["caption"]
    assert "same-location" in figures[3]["caption"]
    checks = json.loads((output / "diagnostic-checks.json").read_text(encoding="utf-8"))
    assert all(check["text_nonoverlapping"] for check in checks.values())


def test_local_script_recalculates_changed_source_and_is_not_overwritten(tmp_path):
    path, _ = make_config(tmp_path)
    output = tmp_path / "figures"
    render_diagnostic_figures(path, output)
    script = output / "plot.py"
    script.write_text(
        script.read_text(encoding="utf-8") + "\n# author adjustment\n", encoding="utf-8"
    )
    before = script.read_bytes()
    source = tmp_path / "sources/A.npz"
    with np.load(source, allow_pickle=False) as data:
        arrays = {key: data[key].copy() for key in data.files}
    arrays["heat_flux"] *= 2
    np.savez(source, **arrays)
    subprocess.run([sys.executable, str(script)], check=True, capture_output=True, text=True)
    assert script.read_bytes() == before
    with (output / "exchange-source-data.csv").open(encoding="utf-8", newline="") as stream:
        assert float(next(csv.DictReader(stream))["net"]) == 8


def test_flux_requires_reader_visible_sign_and_rejects_incompatible_operations(tmp_path):
    path, config = make_config(tmp_path)
    del config["panels"][1]["sign_convention"]
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="sign_convention"):
        render_diagnostic_figures(path, tmp_path / "figures")
    config["panels"][1]["sign_convention"] = "Positive heat enters."
    config["panels"][1]["series"][0]["calculation_id"] = "budget"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="operation"):
        render_diagnostic_figures(path, tmp_path / "figures")


def test_signed_flux_rejects_temperature_integrals_and_font_fallback_stays_readable(tmp_path):
    from cfdpaper.publication.render_figure import PlotStyle

    path, config = make_config(tmp_path)
    config["panels"] = [config["panels"][1]]
    config["panels"][0]["series"][0]["calculation_id"] = "temperature-A"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="power unit"):
        render_diagnostic_figures(path, tmp_path / "figures")
    config["panels"][0]["series"][0]["calculation_id"] = "heat-A"
    path.write_text(json.dumps(config), encoding="utf-8")
    figures = render_diagnostic_figures(
        path,
        tmp_path / "figures",
        style=PlotStyle(
            width_mm=160,
            height_mm=80,
            font_family="DejaVu Serif",
            font_pt=9,
            axis_label_pt=9,
            title_pt=10,
            tick_pt=8,
            legend_pt=8,
        ),
    )
    assert figures[0]["sizing"]["minimum_source_font_pt"] >= 8
