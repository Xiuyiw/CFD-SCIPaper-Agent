"""Temperature composition uses signed components, never inferred heat-flow arrows."""

import csv
import json

import pytest

from cfdpaper.publication import diagnostic_figures
from tests.publication.test_partition_change import declaration, surface


def fixture(tmp_path, *, second=(313, 297), combine=False):
    calculations = []
    series = []
    region_series = []
    for name, reference, comparison in (
        ("A", [320, 300], [316, 302]),
        ("B", [315, 299], second),
    ):
        for role, values in (("reference", reference), ("comparison", comparison)):
            surface(tmp_path / f"{name}-{role}.npz", values)
            field = declaration()
            field["id"] = f"field-{name}-{role}"
            field["source"] = f"{name}-{role}.npz"
            field["operation"] = "field_integral"
            calculations.append(field)
            region_series.append(
                {
                    "calculation_id": field["id"],
                    "label": f"Structure {name} {role}",
                    "pair_id": f"Structure {name}",
                    "role": role,
                    "groups": ["hot", "rest", "all"],
                }
            )
        change = declaration(reference_source=f"{name}-reference.npz")
        change["id"] = f"change-{name}"
        change["source"] = f"{name}-comparison.npz"
        calculations.append(change)
        series.append({"label": f"Structure {name}", "calculation_id": change["id"]})
    panel = {
        "id": "contributions",
        "kind": "partition_contribution",
        "title": "Regional contributions to the complete-wall change",
        "group_labels": {"hot": "Heated footprint", "rest": "Remaining wall"},
        "series": series,
    }
    panels = [panel]
    if combine:
        panels.insert(
            0,
            {
                "id": "regional",
                "kind": "regional",
                "view": "paired_change",
                "title": "Original regional temperature changes",
                "series": region_series,
            },
        )
    data = {"field_calculations": calculations, "panels": panels}
    path = tmp_path / "diagnostics.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data


@pytest.mark.parametrize("second", [(313, 297), (315, 299)])
def test_signed_temperature_contributions_and_whole_change_have_exact_values(
    tmp_path, monkeypatch, second
):
    path, _ = fixture(tmp_path, second=second)
    export = diagnostic_figures._export
    seen = []

    def inspect(fig, output, identity, style):
        ax = fig.axes[0]
        assert [tick.get_text() for tick in ax.get_yticklabels()] == ["Structure A", "Structure B"]
        expected = [-1.0, 1.5, -0.5, -1.5] if second == (313, 297) else [-1.0, 1.5, 0.0, 0.0]
        assert [bar.get_width() for bar in ax.patches] == pytest.approx(expected)
        # Each sign starts at zero. The two negative B parts accumulate leftward.
        assert [bar.get_x() for bar in ax.patches] == pytest.approx(
            [0, 0, 0, -0.5] if second == (313, 297) else [0, 0, 0, 0]
        )
        diamonds = [line for line in ax.lines if line.get_marker() == "D"]
        assert [float(line.get_xdata()[0]) for line in diamonds] == pytest.approx(
            [0.5, -2.0] if second == (313, 297) else [0.5, 0.0]
        )
        assert "(K)" in ax.get_xlabel()
        assert ax.get_xlim()[0] < min(0, *expected)
        assert ax.get_xlim()[1] > 1.5
        fig.canvas.draw()
        bounds = fig.bbox
        assert all(bounds.contains(*text.get_window_extent().get_points()[0]) for text in ax.texts)
        seen.append(True)
        return export(fig, output, identity, style)

    monkeypatch.setattr(diagnostic_figures, "_export", inspect)
    output = tmp_path / "figures"
    figures = diagnostic_figures.render_diagnostic_figures(path, output)
    assert seen and len(figures) == 1
    with (output / "contributions-source-data.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 4
    assert {row["group"] for row in rows} == {"hot", "rest"}
    assert float(rows[0]["reference_mean"]) == 320
    assert float(rows[0]["reference_weight"]) == 0.25
    assert float(rows[0]["contribution"]) == -1
    assert float(rows[0]["whole_reference_mean"]) == 305
    assert float(rows[0]["whole_comparison_mean"]) == 305.5
    assert float(rows[0]["whole_difference"]) == 0.5
    caption = figures[0]["caption"]
    assert "area-weighted temperature" in caption
    assert "not heat" in caption and "diamonds" in caption
    assert "independent" in caption
    assert "<text" in (output / "contributions.svg").read_text(encoding="utf-8")
    for suffix in ("png", "svg", "pdf", "tiff"):
        assert (output / f"contributions.{suffix}").stat().st_size > 0


def test_partition_contribution_composes_with_existing_regional_panel_and_local_script(tmp_path):
    path, _ = fixture(tmp_path, combine=True)
    output = tmp_path / "figures"
    diagnostic_figures.render_diagnostic_figures(path, output, combine=True)
    assert (output / "diagnostic-composite.png").is_file()
    script = output / "plot.py"
    script.write_text(
        script.read_text(encoding="utf-8") + "\n# Author style retained\n", encoding="utf-8"
    )
    original = script.read_bytes()
    result = diagnostic_figures.render_diagnostic_figures(path, output, combine=True)
    assert script.read_bytes() == original
    assert "(a)" in result[0]["caption"] and "(b)" in result[0]["caption"]


@pytest.mark.parametrize("groups", [["hot"], ["hot", "rest", "all"]])
def test_partial_or_duplicate_whole_partition_cannot_be_drawn_as_complete_composition(
    tmp_path, groups
):
    path, data = fixture(tmp_path)
    data["panels"][0]["series"][0]["groups"] = groups
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="all non-total partition groups"):
        diagnostic_figures.render_diagnostic_figures(path, tmp_path / "figures")
