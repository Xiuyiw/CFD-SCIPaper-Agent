"""A native face map and matched height-resolved transfers share one reusable figure."""

import csv
import json
import subprocess
import sys

import numpy as np
import pytest

from cfdpaper.publication import surface_figures
from cfdpaper.publication.diagnostic_figures import render_diagnostic_figures


def composite_input(tmp_path):
    (tmp_path / "sources").mkdir()
    vertices = np.array(
        [
            [-0.02, -0.02, 0],
            [0, -0.02, 0],
            [0, 0.02, 0],
            [-0.02, 0.02, 0],
            [0.02, -0.02, 0],
            [0.02, 0.02, 0],
        ],
        dtype=float,
    )
    cases = []
    for name, values in (("A", [350, 390]), ("B", [345, 385])):
        np.savez(
            tmp_path / f"sources/{name}.npz",
            face_value=values,
            area_m2=[0.0008, 0.0008],
            vertices_m=vertices,
            faces_connectivity=[4, 0, 1, 2, 3, 4, 1, 4, 5, 2],
            face_starts=[0, 5],
        )
        cases.append({"id": name, "label": f"Case {name}", "source": f"sources/{name}.npz"})
    study = {
        "domain": "complete solid interface",
        "quantity": "Interface temperature",
        "unit": "K",
        "coordinate_unit": "m",
        "projection_axes": [0, 1],
        "thresholds": [373.15],
        "arrays": {
            "values": "face_value",
            "weights": "area_m2",
            "vertices": "vertices_m",
            "connectivity": "faces_connectivity",
            "starts": "face_starts",
        },
        "cases": cases,
        "region_outline": {
            "label": "Heated footprint",
            "bounds": {"x": [0.005, 0.015], "y": [0.005, 0.015]},
        },
    }
    (tmp_path / "sources/layers.csv").write_text(
        "case,band,positive,negative,area\n"
        "A,base,40,-0.01,1\nA,lower,4,-1,1\nA,upper,0.1,-0.8,1\nA,uppermost,0.3,-0.4,1\n"
        "B,base,42,-0.02,1\nB,lower,2,-1.5,1\nB,upper,0.05,-1.1,1\nB,uppermost,0.02,-0.5,1\n",
        encoding="utf-8",
    )
    layers = [
        {"id": key, "label": label}
        for key, label in (
            ("base", "−2 to 0"),
            ("lower", "0 to 6"),
            ("upper", "6 to 12"),
            ("uppermost", "12 to 18"),
        )
    ]
    declarations, series = [], []
    for case in ("A", "B"):
        mapping = {}
        for band in ("all", "base", "lower", "upper", "uppermost"):
            identifier = f"transfer-{case}-{band}"
            filters = {"case": case, **({"band": band} if band != "all" else {})}
            declarations.append(
                {
                    "id": identifier,
                    "source": "sources/layers.csv",
                    "operation": "field_integral",
                    "columns": {"positive": "positive", "negative": "negative", "measure": "area"},
                    "units": {"positive": "W", "negative": "W", "measure": "mm2"},
                    "domain": "solid side planes",
                    "field_options": {
                        "association": "integrated_region",
                        "integrand": "signed_totals",
                        "row_filters": filters,
                        "orientation": 1,
                    },
                }
            )
            if band != "all":
                mapping[band] = identifier
        series.append(
            {
                "case_id": case,
                "label": f"Case {case}",
                "calculation_id": f"transfer-{case}-all",
                "calculation_ids": mapping,
            }
        )
    diagnostics = {
        "field_calculations": declarations,
        "panels": [
            {
                "id": "layered-transfer",
                "kind": "signed_flux",
                "title": "Height-resolved lateral transfer",
                "sign_convention": "Positive is outward; negative is inward.",
                "layer_label": "Height band (mm)",
                "layers": layers,
                "series": series,
            }
        ],
    }
    study_path, diagnostic_path = tmp_path / "study.json", tmp_path / "diagnostics.json"
    study_path.write_text(json.dumps(study), encoding="utf-8")
    diagnostic_path.write_text(json.dumps(diagnostics), encoding="utf-8")
    return study_path, diagnostic_path, study, diagnostics


def rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_composite_exact_faces_layered_values_shared_scale_and_all_formats(tmp_path, monkeypatch):
    study_path, diagnostic_path, _, _ = composite_input(tmp_path)
    original = {p: p.read_bytes() for p in (tmp_path / "sources").iterdir()}
    checked = []
    export = surface_figures._export

    def inspect(fig, output, figure_id, style):
        fig.canvas.draw()
        maps = [
            ax
            for ax in fig.axes
            if any(
                hasattr(c, "get_array") and c.get_array() is not None and len(c.get_array()) == 2
                for c in ax.collections
            )
        ]
        assert len(maps) == 2 and all(ax.get_aspect() == 1 for ax in maps)
        norms = [ax.collections[0].norm for ax in maps]
        assert norms[0] is norms[1] and (norms[0].vmin, norms[0].vmax) == (345, 390)
        assert all(ax.get_xlim() == (-0.02, 0.02) and ax.get_ylim() == (-0.02, 0.02) for ax in maps)
        assert all(len(ax.patches) == 1 for ax in maps)
        signed = next(ax for ax in fig.axes if "Signed transfer" in ax.get_xlabel())
        assert "−2 to 0" in [label.get_text() for label in signed.get_yticklabels()]
        assert "Full height" in [label.get_text() for label in signed.get_yticklabels()]
        assert "-1.05" in [text.get_text() for ax in fig.axes for text in ax.texts]
        colorbar = next(ax for ax in fig.axes if ax.get_ylabel() == "Interface temperature (K)")
        assert colorbar.get_window_extent().y0 == pytest.approx(
            min(ax.get_window_extent().y0 for ax in maps), abs=0.5
        )
        assert colorbar.get_window_extent().y1 == pytest.approx(
            max(ax.get_window_extent().y1 for ax in maps), abs=0.5
        )
        checked.append(True)
        return export(fig, output, figure_id, style)

    monkeypatch.setattr(surface_figures, "_export", inspect)
    output = tmp_path / "combined"
    figure = surface_figures.render_surface_composite(
        study_path, diagnostic_path, output, panel_id="layered-transfer"
    )
    assert checked and figure["id"] == "field-layered-transfer"
    assert figure["sizing"]["source_width_mm"] == pytest.approx(160, abs=0.1)
    assert figure["sizing"]["minimum_source_font_pt"] >= 8
    for extension in ("svg", "pdf", "png", "tiff"):
        assert (output / f"field-layered-transfer.{extension}").stat().st_size > 0
    field = rows(output / "field-source-data.csv")
    assert [float(row["value"]) for row in field] == [350, 390, 345, 385]
    diagnostic = rows(output / "diagnostic-source-data.csv")
    assert len(diagnostic) == 10
    assert {row["layer_id"] for row in diagnostic} == {"base", "lower", "upper", "uppermost", "all"}
    upper_b = next(
        row for row in diagnostic if row["case_id"] == "B" and row["layer_id"] == "upper"
    )
    assert float(upper_b["net"]) == pytest.approx(-1.05)
    assert json.loads(upper_b["csv_records"]) == [8]
    assert all(p.read_bytes() == content for p, content in original.items())
    assert "same saved solution" in figure["caption"]
    assert "<text" in (output / "field-layered-transfer.svg").read_text(encoding="utf-8")


def test_layered_signed_flux_also_works_through_existing_diagnostic_entry(tmp_path):
    _, diagnostic_path, _, _ = composite_input(tmp_path)
    figures = render_diagnostic_figures(diagnostic_path, tmp_path / "diagnostic")
    assert figures[0]["id"] == "layered-transfer"
    assert len(rows(tmp_path / "diagnostic/layered-transfer-source-data.csv")) == 10


def test_composite_local_script_preserves_author_edits_and_refreshes_sources(tmp_path):
    study_path, diagnostic_path, _, _ = composite_input(tmp_path)
    output = tmp_path / "combined"
    surface_figures.render_surface_composite(
        study_path, diagnostic_path, output, panel_id="layered-transfer"
    )
    script = output / "plot.py"
    script.write_text(
        script.read_text(encoding="utf-8") + "\n# Author adjustment\n", encoding="utf-8"
    )
    before = script.read_bytes()
    source = tmp_path / "sources/layers.csv"
    source.write_text(source.read_text().replace("B,upper,0.05,-1.1", "B,upper,0.05,-1.3"))
    subprocess.run([sys.executable, str(script)], check=True, capture_output=True, timeout=60)
    assert script.read_bytes() == before
    data = rows(output / "diagnostic-source-data.csv")
    upper_b = next(row for row in data if row["case_id"] == "B" and row["layer_id"] == "upper")
    assert float(upper_b["net"]) == pytest.approx(-1.25)


@pytest.mark.parametrize("defect", ["layer", "case", "unit"])
def test_composite_does_not_silently_drop_layers_or_join_other_cases(tmp_path, defect):
    study_path, diagnostic_path, _, diagnostics = composite_input(tmp_path)
    if defect == "layer":
        del diagnostics["panels"][0]["series"][1]["calculation_ids"]["upper"]
    elif defect == "case":
        diagnostics["panels"][0]["series"][1]["case_id"] = "C"
    else:
        diagnostics["field_calculations"][-1]["units"].update(positive="kW", negative="kW")
    diagnostic_path.write_text(json.dumps(diagnostics), encoding="utf-8")
    with pytest.raises(ValueError):
        surface_figures.render_surface_composite(
            study_path, diagnostic_path, tmp_path / "combined", panel_id="layered-transfer"
        )
