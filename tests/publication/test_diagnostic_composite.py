"""Regional responses and local budgets are complementary, explicitly paired evidence."""

import csv
import json
import shutil
import subprocess
import sys

import numpy as np
import pytest

from cfdpaper.publication import diagnostic_figures


def comparison_input(tmp_path):
    (tmp_path / "sources").mkdir()
    declarations, temperatures, budgets = [], [], []
    for case, pair, role, values, output in (
        ("a0", "Structure A", "reference", [330, 310], 20),
        ("a1", "Structure A", "comparison", [328, 314], 35),
        ("b0", "Structure B", "reference", [325, 305], 30),
        ("b1", "Structure B", "comparison", [324, 308], 25),
    ):
        np.savez(tmp_path / f"sources/{case}.npz", temperature=values, area=[1, 3], x=[0, 2])
        declarations.append(
            {
                "id": f"temperature-{case}",
                "operation": "field_integral",
                "source": f"sources/{case}.npz",
                "domain": "complete interface",
                "columns": {"value": "temperature", "measure": "area", "x": "x"},
                "units": {"value": "K", "measure": "m2", "x": "m"},
                "field_options": {
                    "association": "face",
                    "integrand": "weighted_mean",
                    "region_assignment": "centroid",
                    "partition_complete": True,
                    "regions": [
                        {"id": "hot", "bounds": {"x": [-1, 1]}},
                        {"id": "rest", "bounds": {"x": [1, 3]}},
                    ],
                },
            }
        )
        (tmp_path / f"sources/{case}.csv").write_text(
            f"incoming,outgoing,zero\n50,{output},0\n", encoding="utf-8"
        )
        declarations.append(
            {
                "id": f"budget-{case}",
                "operation": "energy_budget",
                "source": f"sources/{case}.csv",
                "domain": "local solid column",
                "columns": {
                    "input": "incoming",
                    "output": "outgoing",
                    "source": "zero",
                    "storage": "zero",
                },
                "units": dict.fromkeys(("input", "output", "source", "storage"), "W"),
                "field_options": {"association": "control_volume"},
            }
        )
        common = {"label": f"{pair} / {role}", "pair_id": pair, "role": role}
        temperatures.append(
            {**common, "calculation_id": f"temperature-{case}", "groups": ["hot", "rest", "all"]}
        )
        budgets.append({**common, "calculation_id": f"budget-{case}"})
    config = {
        "field_calculations": declarations,
        "panels": [
            {
                "id": "temperature",
                "kind": "regional",
                "view": "paired_change",
                "title": "Regional response",
                "series": temperatures,
                "group_labels": {
                    "hot": "Heated footprint",
                    "rest": "Remaining interface",
                    "all": "Whole interface",
                },
            },
            {
                "id": "budget",
                "kind": "budget",
                "view": "decomposition",
                "title": "Local transfer budget",
                "series": budgets,
            },
        ],
    }
    path = tmp_path / "diagnostics.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path, config


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_composite_retains_originals_exact_changes_and_final_size(tmp_path, monkeypatch):
    path, _ = comparison_input(tmp_path)
    originals = {p: p.read_bytes() for p in (tmp_path / "sources").iterdir()}
    export = diagnostic_figures._export
    inspected = []

    def inspect(fig, output, figure_id, style):
        assert len(fig.axes) == 2
        first, second = fig.axes
        assert first.get_position().x0 == pytest.approx(second.get_position().x0)
        assert first.get_position().x1 == pytest.approx(second.get_position().x1)
        assert len(second.patches) == 8  # Four outputs, four derived remainders.
        assert [p.get_width() for p in second.patches[::2]] == [20, 35, 30, 25]
        assert {line.get_marker() for line in first.lines if line.get_marker() != "None"} >= {
            "o",
            "s",
        }
        inspected.append(True)
        return export(fig, output, figure_id, style)

    monkeypatch.setattr(diagnostic_figures, "_export", inspect)
    output = tmp_path / "figures"
    figures = diagnostic_figures.render_diagnostic_figures(path, output, combine=True)
    assert inspected and len(figures) == 1
    assert figures[0]["sizing"]["source_width_mm"] == pytest.approx(160, abs=0.1)
    assert figures[0]["sizing"]["minimum_source_font_pt"] >= 8
    for extension in ("svg", "pdf", "png", "tiff"):
        assert (output / f"diagnostic-composite.{extension}").stat().st_size > 0
    assert "<text" in (output / "diagnostic-composite.svg").read_text(encoding="utf-8")
    raw = read_rows(output / "diagnostic-composite-source-data.csv")
    changes = read_rows(output / "diagnostic-composite-differences.csv")
    assert len(raw) == 16 and len(changes) == 6
    assert [float(r["difference"]) for r in changes] == [-2, 4, 2.5, -1, 3, 2]
    assert float(changes[2]["reference_mean"]) == 315
    assert all(p.read_bytes() == contents for p, contents in originals.items())
    caption = figures[0]["caption"]
    assert "comparison minus reference" in caption
    assert "declared spatial definition" in caption
    assert "remainder = input − output" in caption
    assert "complete interface" not in caption and "local solid column" not in caption
    assert " + storage" not in caption and " + source" not in caption
    assert len(caption.split()) < 100


@pytest.mark.parametrize("second_comparison", [[328, 312], [329, 312]])
def test_paired_change_equal_or_close_labels_do_not_overlap_data(
    tmp_path, monkeypatch, second_comparison
):
    path, _ = comparison_input(tmp_path)
    for case, values in (
        ("a0", [334, 312]),
        ("a1", [331, 316]),
        ("b0", [329, 309]),
        ("b1", second_comparison),
    ):
        np.savez(tmp_path / f"sources/{case}.npz", temperature=values, area=[1, 3], x=[0, 2])
    export = diagnostic_figures._export

    def inspect(fig, output, figure_id, style):
        fig.canvas.draw()
        ax = fig.axes[0]
        renderer = fig.canvas.get_renderer()
        labels = [text.get_window_extent(renderer) for text in ax.texts]
        assert all(
            not first.overlaps(second)
            for index, first in enumerate(labels)
            for second in labels[index + 1 :]
        )
        markers = [line for line in ax.lines if line.get_marker() in {"o", "s"}]
        assert all(
            not label.overlaps(marker.get_window_extent(renderer))
            for label in labels
            for marker in markers
        )
        assert [float(line.get_ydata()[0]) for line in markers] == pytest.approx(
            [-0.12, 0.88, 1.88, 0.12, 1.12, 2.12]
        )
        assert [float(line.get_xdata()[0]) for line in markers] == pytest.approx(
            [-3, 4, 2.25, second_comparison[0] - 329, 3, (second_comparison[0] - 329 + 9) / 4]
        )
        assert ax.get_xlim() == pytest.approx((-4.4, 5.4))
        assert ax.get_ylim() == pytest.approx((2.5, -0.65))
        assert list(ax.get_yticks()) == [0, 1, 2]
        return export(fig, output, figure_id, style)

    monkeypatch.setattr(diagnostic_figures, "_export", inspect)
    diagnostic_figures.render_diagnostic_figures(path, tmp_path / "figures", combine=True)


def test_combined_caption_uses_quantity_labels_and_only_active_budget_terms():
    panel = {
        "kind": "budget",
        "view": "decomposition",
        "title": "Local heat balance",
        "component_labels": {
            "output": "heat release",
            "residual": "lateral remainder",
            "input": "interface input",
        },
    }
    entries = [{"result": {"source": 0, "storage": 0}}]
    caption = diagnostic_figures._combined_caption(panel, entries)
    assert "solid segments show heat release" in caption
    assert "hatched segments show lateral remainder" in caption
    assert "diamonds mark interface input" in caption
    assert "lateral remainder = interface input − heat release" in caption
    assert "source" not in caption and "storage" not in caption
    entries[0]["result"].update(source=5, storage=2)
    active_caption = diagnostic_figures._combined_caption(panel, entries)
    assert "interface input + source" in active_caption
    assert "heat release + storage" in active_caption
    assert "(interface input + source) − (heat release + storage)" in active_caption


@pytest.mark.parametrize(
    "incoming,outgoing,source,storage",
    [(100, 20, 0, -30), (20, 30, -40, 0), (100, 120, 0, 0), (100, 20, 0, 0)],
)
def test_budget_decomposition_retains_all_signed_endpoints(
    tmp_path, incoming, outgoing, source, storage
):
    from matplotlib.figure import Figure

    path, config = comparison_input(tmp_path)
    for declaration in config["field_calculations"]:
        if declaration["operation"] != "energy_budget":
            continue
        declaration["columns"] = {key: key for key in ("input", "output", "source", "storage")}
        (tmp_path / declaration["source"]).write_text(
            f"input,output,source,storage\n{incoming},{outgoing},{source},{storage}\n",
            encoding="utf-8",
        )
    path.write_text(json.dumps(config), encoding="utf-8")
    _, [(panel, entries)] = diagnostic_figures._read_panels(path, panel_ids=["budget"])
    fig = Figure()
    try:
        ax = diagnostic_figures._plot_budget_decomposition(
            fig, panel, entries, diagnostic_figures.PlotStyle()
        )[0]
        low, high = ax.get_xlim()
        solid_end, input_end = outgoing + storage, incoming + source
        assert low <= min(0, solid_end, input_end)
        assert high >= max(0, solid_end, input_end)
        assert low < high
        assert [patch.get_width() for patch in ax.patches[::2]] == [solid_end] * 4
        assert [patch.get_width() for patch in ax.patches[1::2]] == [input_end - solid_end] * 4
        assert [float(line.get_xdata()[0]) for line in ax.lines if line.get_marker() == "D"] == [
            input_end
        ] * 4
        if (incoming, outgoing, source, storage) == (100, 20, 0, 0):
            assert ax.get_xlim() == pytest.approx((0, 118))
    finally:
        fig.clear()


@pytest.mark.parametrize("source,storage", [(0, 0), (5, 2)])
@pytest.mark.parametrize("named_terms", [False, True])
def test_budget_custom_legend_names_the_actual_active_sums(source, storage, named_terms):
    from matplotlib.figure import Figure

    labels = {"input": "interface input", "output": "oil rejection", "residual": "remainder"}
    if named_terms:
        labels.update(source="internal generation", storage="stored heat")
    panel = {
        "kind": "budget",
        "view": "decomposition",
        "title": "Local balance",
        "component_labels": labels,
        "series": [{}],
    }
    entries = [
        {
            "series_index": 0,
            "label": "Case",
            "group": "all",
            "result": {
                "input": 100,
                "output": 20,
                "source": source,
                "storage": storage,
                "residual": 100 + source - 20 - storage,
            },
            "report": {"result_units": {"residual": "W"}},
        }
    ]
    fig = Figure()
    try:
        ax = diagnostic_figures._plot_budget_decomposition(
            fig, panel, entries, diagnostic_figures.PlotStyle()
        )[0]
        outgoing = "oil rejection" + (f" + {labels.get('storage', 'storage')}" if storage else "")
        incoming = "interface input" + (f" + {labels.get('source', 'source')}" if source else "")
        assert [text.get_text() for text in ax.get_legend().get_texts()] == [
            outgoing,
            "remainder",
            incoming,
        ]
        caption = diagnostic_figures._combined_caption(panel, entries)
        assert f"solid segments show {outgoing}" in caption
        assert f"diamonds mark {incoming}" in caption
    finally:
        fig.clear()


def test_composite_local_script_refreshes_values_without_overwriting_author(tmp_path):
    path, _ = comparison_input(tmp_path)
    output = tmp_path / "figures"
    diagnostic_figures.render_diagnostic_figures(path, output, combine=True, figure_id="response")
    script = output / "plot.py"
    script.write_text(
        script.read_text(encoding="utf-8") + "\n# Author adjustment\n", encoding="utf-8"
    )
    before = script.read_bytes()
    np.savez(tmp_path / "sources/a1.npz", temperature=[327, 315], area=[1, 3], x=[0, 2])
    subprocess.run([sys.executable, str(script)], check=True, capture_output=True, timeout=60)
    assert script.read_bytes() == before
    changes = read_rows(output / "response-differences.csv")
    assert [float(r["difference"]) for r in changes[:3]] == [-3, 5, 3]


@pytest.mark.parametrize("combine", [False, True])
def test_panel_selection_preserves_requested_subset_and_order(tmp_path, combine):
    path, config = comparison_input(tmp_path)
    config["panels"].append({**config["panels"][1], "id": "other-budget"})
    path.write_text(json.dumps(config), encoding="utf-8")
    output = tmp_path / "figures"
    figures = diagnostic_figures.render_diagnostic_figures(
        path, output, combine=combine, panel_ids=["budget", "temperature"]
    )
    if combine:
        checks = json.loads((output / "diagnostic-checks.json").read_text(encoding="utf-8"))
        assert checks["diagnostic-composite"]["panel_ids"] == ["budget", "temperature"]
        rows = read_rows(output / "diagnostic-composite-source-data.csv")
        assert list(dict.fromkeys(row["panel_id"] for row in rows)) == [
            "budget",
            "temperature",
        ]
    else:
        assert [figure["id"] for figure in figures] == ["budget", "temperature"]
    assert not (output / "other-budget.png").exists()
    assert "panel_ids=['budget', 'temperature']" in (output / "plot.py").read_text(encoding="utf-8")


def test_selected_local_script_refreshes_canonical_sources_after_relocation(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    path, _ = comparison_input(original)
    output = original / "figures"
    diagnostic_figures.render_diagnostic_figures(path, output, panel_ids=["budget"])
    script = output / "plot.py"
    script.write_text(
        script.read_text(encoding="utf-8") + "\n# Author adjustment\n", encoding="utf-8"
    )
    before = script.read_bytes()
    moved = tmp_path / "moved"
    shutil.copytree(original, moved)
    (moved / "sources/a0.csv").write_text("incoming,outgoing,zero\n50,22,0\n", encoding="utf-8")
    # The original retains output=20; using it instead of the moved source fails below.
    subprocess.run(
        [sys.executable, str(moved / "figures/plot.py")],
        check=True,
        capture_output=True,
        timeout=60,
        cwd=tmp_path,
    )
    assert (moved / "figures/plot.py").read_bytes() == before
    rows = read_rows(moved / "figures/budget-source-data.csv")
    assert float(rows[0]["output"]) == 22
    figures = json.loads((moved / "figures/diagnostic-figures.json").read_text(encoding="utf-8"))
    assert [figure["id"] for figure in figures["figures"]] == ["budget"]
    assert not (moved / "figures/temperature.png").exists()


@pytest.mark.parametrize("selected", [[], ["missing"], ["budget", "budget"], "budget", [1]])
def test_panel_selection_rejects_empty_unknown_duplicate_or_nonlist_ids(tmp_path, selected):
    path, _ = comparison_input(tmp_path)
    output = tmp_path / "figures"
    with pytest.raises(ValueError, match="panel_ids"):
        diagnostic_figures.render_diagnostic_figures(path, output, panel_ids=selected)
    assert not output.exists()


@pytest.mark.parametrize("defect", ["unpaired", "duplicate", "groups", "units"])
def test_composite_never_guesses_pairing_or_comparison_support(tmp_path, defect):
    path, config = comparison_input(tmp_path)
    if defect == "unpaired":
        del config["panels"][0]["series"][0]["pair_id"]
    elif defect == "duplicate":
        config["panels"][0]["series"][1]["role"] = "reference"
    elif defect == "groups":
        config["panels"][0]["series"][1]["groups"] = ["hot", "rest"]
    else:
        config["field_calculations"][2]["units"]["value"] = "degC"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="[Pp]air|groups|unit"):
        diagnostic_figures.render_diagnostic_figures(path, tmp_path / "figures", combine=True)
