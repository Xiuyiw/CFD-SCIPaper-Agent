"""Original face temperatures linked to their exact regional change composition."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path

import numpy as np

from .diagnostic_figures import (
    _COLORS,
    _axes_style,
    _plot_partition_contribution,
    _read_panels,
    _rows,
    _source,
    _write_csv,
)
from .render_figure import PlotStyle
from .surface_figures import _export, _read_study
from .table_evidence import display_unit


def _selection(study, cases, diagnostic_path, panel_id):
    """Bind by original source and array identity, never by display labels."""
    if study["unit"] != "K":
        raise ValueError("Surface partition figures require absolute temperature with unit K")
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    panels = [panel for panel in diagnostic.get("panels", []) if panel.get("id") == panel_id]
    if len(panels) != 1 or panels[0].get("kind") != "partition_contribution":
        raise ValueError("Select one existing partition_contribution panel")
    panel = panels[0]
    series = panel.get("series", [])
    if len(series) not in (1, 2):
        raise ValueError("Surface partition figures require one or two explicit comparisons")
    arrays = study["arrays"]
    if any(
        arrays[key] != expected
        for key, expected in (
            ("vertices", "vertices_m"),
            ("connectivity", "faces_connectivity"),
            ("starts", "face_starts"),
        )
    ):
        raise ValueError("Surface geometry arrays must match the original polygon-clip geometry")
    declarations = diagnostic.get("field_calculations", [])
    bindings, selected = [], []
    axes = {"xyz"[axis] for axis in study["projection_axes"]}
    for item in series:
        found = [entry for entry in declarations if entry.get("id") == item.get("calculation_id")]
        if len(found) != 1 or found[0].get("operation") != "partition_change":
            raise ValueError("Surface panel calculation must match one partition_change")
        declaration = found[0]
        options = declaration["field_options"]
        if declaration.get("quantity_kind") != "absolute-temperature":
            raise ValueError("Surface partition figures require absolute-temperature calculations")
        if options.get("region_assignment") != "polygon-clip":
            raise ValueError("Surface region outlines require polygon-clip partitions")
        if declaration["units"] != {"value": study["unit"], "measure": "m2"}:
            raise ValueError("Surface and partition value/physical-area units must match exactly")
        current = _source(diagnostic_path.parent, declaration["source"])
        reference = (current.parent / options["reference_source"]).resolve()
        binding = {"calculation_id": declaration["id"], "label": item["label"]}
        for role, source, columns, regions in (
            (
                "reference",
                reference,
                options.get("reference_columns", declaration["columns"]),
                options.get("reference_regions", options["regions"]),
            ),
            ("comparison", current, declaration["columns"], options["regions"]),
        ):
            matches = [case for case in cases if case["path"] == source]
            if len(matches) != 1:
                raise ValueError(f"Partition {role} source must match one exact surface case")
            if columns != {"value": arrays["values"], "measure": arrays["weights"]}:
                raise ValueError(f"Partition {role} value/area columns must match displayed arrays")
            if any(set(region.get("bounds", {})) != axes for region in regions):
                raise ValueError("Partition bounds must match the displayed projection axes")
            case = matches[0]
            binding[role] = {
                "case_id": case["id"],
                "source": case["source"],
                "diagnostic_source": os.path.relpath(source, diagnostic_path.parent).replace(
                    "\\", "/"
                ),
                "columns": deepcopy(columns),
                "units": deepcopy(declaration["units"]),
                "regions": deepcopy(regions),
            }
            selected.append((case, binding[role], declaration["id"], role))
        binding.update(
            support_mode=options.get("support_mode"),
            physical_definition=deepcopy(options),
            support=deepcopy(declaration.get("support", {})),
        )
        bindings.append(binding)
    if len({case["id"] for case, *_ in selected}) != len(selected):
        raise ValueError("Surface partition comparisons require two or four distinct source cases")
    return panel, bindings, selected


def _region_outlines(ax, regions, axes, group_codes, style):
    from matplotlib import patheffects
    from matplotlib.patches import Rectangle

    names = ["xyz"[axis] for axis in axes]
    for region in regions:
        if region.get("complement", False):
            continue
        x, y = (region["bounds"][name] for name in names)
        code, index = group_codes[region["id"]]
        outline = Rectangle(
            (x[0], y[0]),
            x[1] - x[0],
            y[1] - y[0],
            fill=False,
            edgecolor=_COLORS[index % len(_COLORS)],
            linewidth=1.0,
            linestyle="--",
            zorder=3,
            path_effects=[
                patheffects.Stroke(linewidth=2.1, foreground="white"),
                patheffects.Normal(),
            ],
        )
        ax.add_patch(outline)
        ax.annotate(
            code,
            (max(x[0], ax.get_xlim()[0]), min(y[1], ax.get_ylim()[1])),
            xytext=(3, -3),
            textcoords="offset points",
            ha="left",
            va="top",
            fontsize=style.annotation_pt,
            color="#243744",
            path_effects=[patheffects.withStroke(linewidth=2, foreground="white")],
            zorder=4,
        )


def _write_script(study_path, diagnostic_path, output, panel_id, style):
    script = output / "plot.py"
    if script.exists():
        return
    study = os.path.relpath(study_path, output).replace("\\", "/")
    diagnostic = os.path.relpath(diagnostic_path, output).replace("\\", "/")
    script.write_text(
        '"""Author-local original-surface/partition figure; retain local style edits."""\n'
        "import argparse\nfrom pathlib import Path\n"
        "from cfdpaper.publication.render_figure import PlotStyle\n"
        "from cfdpaper.publication.surface_partition_figure import render_surface_partition\n\n"
        f"STYLE = PlotStyle(**{style.model_dump()!r})\n\n"
        "if __name__ == '__main__':\n"
        "    root = Path(__file__).resolve().parent\n"
        "    parser = argparse.ArgumentParser()\n"
        f"    parser.add_argument('--study', type=Path, default=root / {study!r})\n"
        f"    parser.add_argument('--config', type=Path, default=root / {diagnostic!r})\n"
        "    parser.add_argument('--output', type=Path, default=root)\n"
        "    args = parser.parse_args()\n"
        "    render_surface_partition(args.study, args.config, args.output, "
        f"panel_id={panel_id!r}, style=STYLE)\n",
        encoding="utf-8",
    )


def render_surface_partition(
    study_path, diagnostic_path, output_dir, *, panel_id, style=None
) -> dict:
    """Render two/four original Kelvin fields above their temperature composition.

    Paths in the returned workspace figure record are relative to ``output_dir``.
    Existing local ``plot.py`` is never overwritten. The plot uses original face
    values; all regional reductions remain in the existing partition_change path.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    from matplotlib.colors import Normalize

    study_path, diagnostic_path, output = (
        Path(path).resolve() for path in (study_path, diagnostic_path, output_dir)
    )
    study, cases = _read_study(study_path)
    panel, bindings, selected = _selection(study, cases, diagnostic_path, panel_id)
    diagnostic, computed = _read_panels(diagnostic_path, [panel_id])
    _, entries = computed[0]
    for binding in bindings:
        report = next(
            entry["report"]
            for entry in entries
            if entry["declaration"]["id"] == binding["calculation_id"]
        )
        binding.update(
            results=[
                {key: deepcopy(group[key]) for key in ("group", "status", "result")}
                for group in report["groups"]
            ],
            result_ref={"calculation_id": binding["calculation_id"]},
            result_units=deepcopy(report["result_units"]),
            interpretation=report["interpretation"],
            closure_error=report["closure_error"],
        )
    group_ids = [entry["group"] for entry in entries if entry["series_index"] == 0]
    group_codes = {identity: (f"R{index + 1}", index) for index, identity in enumerate(group_ids)}
    display_panel = deepcopy(panel)
    labels = panel.get("group_labels", {})
    display_panel["group_labels"] = {
        identity: f"{group_codes[identity][0]}: {labels.get(identity, identity)}"
        for identity in group_ids
    }
    style = style or PlotStyle(
        width_mm=160,
        height_mm=195 if len(selected) == 4 else 125,
        font_family="Times New Roman",
        font_pt=9,
        axis_label_pt=9,
        title_pt=10,
        tick_pt=8.5,
        legend_pt=8.5,
        annotation_pt=8.5,
    )
    limits = [
        min(float(case["values"].min()) for case, *_ in selected),
        max(float(case["values"].max()) for case, *_ in selected),
    ]
    normalization = (
        Normalize(*limits)
        if limits[0] != limits[1]
        else Normalize(limits[0] - 0.5, limits[1] + 0.5)
    )
    vertices = np.concatenate([polygon for case, *_ in selected for polygon in case["polygons"]])
    low, high = vertices.min(axis=0), vertices.max(axis=0)
    output.mkdir(parents=True, exist_ok=True)
    rc = {
        "font.family": [style.font_family, "serif"],
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "font.size": style.font_pt,
        "axes.labelsize": style.axis_label_pt,
        "axes.titlesize": style.title_pt,
        "xtick.labelsize": style.tick_pt,
        "ytick.labelsize": style.tick_pt,
        "legend.fontsize": style.legend_pt,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "mathtext.fontset": "stix",
    }
    with plt.rc_context(rc):
        fig = plt.figure(
            figsize=(style.width_mm / 25.4, style.height_mm / 25.4), layout="constrained"
        )
        try:
            fields, contribution = fig.subfigures(
                2, 1, height_ratios=[2.6 if len(selected) == 4 else 1.4, 1], hspace=0.04
            )
            grid = fields.add_gridspec(len(selected) // 2, 3, width_ratios=[1, 1, 0.045])
            field_axes = []
            for index, (case, binding, _, _) in enumerate(selected):
                ax = fields.add_subplot(grid[index // 2, index % 2])
                field_axes.append(ax)
                collection = PolyCollection(
                    case["polygons"],
                    array=case["values"],
                    cmap="cividis",
                    norm=normalization,
                    edgecolors="none",
                    antialiaseds=False,
                )
                ax.add_collection(collection)
                ax.set(xlim=(low[0], high[0]), ylim=(low[1], high[1]), aspect="equal")
                ax.set_title(f"({chr(97 + index)}) {case['label']}", loc="left", pad=7)
                ax.set_xlabel(f"{'xyz'[study['projection_axes'][0]]} (m)")
                ax.set_ylabel(f"{'xyz'[study['projection_axes'][1]]} (m)")
                ax.tick_params(length=3, width=0.6)
                ax.locator_params(axis="both", nbins=3)
                _region_outlines(
                    ax, binding["regions"], study["projection_axes"], group_codes, style
                )
            colorbar = fields.colorbar(collection, cax=fields.add_subplot(grid[:, -1]))
            colorbar.set_label(f"{study['quantity']} ({display_unit(study['unit'])})")
            (ax,) = _plot_partition_contribution(contribution, display_panel, entries, style)
            _axes_style(ax)
            ax.set_title(
                f"({chr(97 + len(selected))}) Area-weighted temperature change", loc="left", pad=32
            )
            fig.canvas.draw()
            # Match the colorbar to the actual equal-aspect face boxes, not empty grid space.
            position = colorbar.ax.get_position()
            positions = [axis.get_position() for axis in field_axes]
            bottom, top = min(p.y0 for p in positions), max(p.y1 for p in positions)
            fig.set_layout_engine("none")
            colorbar.ax.set_position([position.x0, bottom, position.width, top - bottom])
            checks = _export(fig, output, panel_id, style)
        finally:
            plt.close(fig)
    rows = _rows(entries)
    _write_csv(output / f"{panel_id}-source-data.csv", rows)
    field_rows = [
        {
            "case_id": case["id"],
            "source": case["source"],
            "calculation_id": calculation_id,
            "role": role,
            "array_index": index,
            "value_array": study["arrays"]["values"],
            "area_array": study["arrays"]["weights"],
            "value": float(value),
            "value_unit": study["unit"],
            "area": float(area),
            "area_unit": "m2",
        }
        for case, _, calculation_id, role in selected
        for index, (value, area) in enumerate(zip(case["values"], case["weights"], strict=True))
    ]
    _write_csv(output / f"{panel_id}-field-source-data.csv", field_rows)
    selection = {
        "panel_id": panel_id,
        "case_ids": [case["id"] for case, *_ in selected],
        "calculation_ids": [binding["calculation_id"] for binding in bindings],
    }
    definitions = [
        {
            "panel_label": chr(97 + index),
            "kind": "original_surface",
            "calculation_id": calculation_id,
            "role": role,
            **binding,
        }
        for index, (_, binding, calculation_id, role) in enumerate(selected)
    ]
    definitions.append(
        {
            "panel_label": chr(97 + len(selected)),
            **deepcopy(panel),
            "display_group_labels": display_panel["group_labels"],
        }
    )
    caption = (
        "Original face temperatures share one color scale. Region codes link the drawn bounds "
        "to the regional contributions below; complementary regions are not outlined twice. "
        "Contributions in K compose the area-weighted comparison-minus-reference temperature "
        "change, not heat or an independent causal pathway. Open diamonds show the directly "
        "reduced whole-surface mean change. "
    )
    if any(binding["support_mode"] == "moving" for binding in bindings):
        caption += "Moving regions use each case's declared bounds, not the same physical location."
    else:
        caption += "Fixed regions occupy the same declared locations on the common surface."
    reading = {
        "panel_id": panel_id,
        "operation": "partition_change",
        "selection": selection,
        "comparisons": bindings,
        "panel_definitions": definitions,
        "region_labels": display_panel["group_labels"],
        "shared_color_limits": [float(normalization.vmin), float(normalization.vmax)],
        "field_quantity": study["quantity"],
        "field_unit": study["unit"],
        "evidence_role": "same-solution-temperature-composition",
    }
    figure = {
        "id": panel_id,
        "path": f"{panel_id}.png",
        "caption": caption,
        "description": caption,
        "sizing": {
            key: checks[key]
            for key in ("source_width_mm", "target_width_mm", "minimum_source_font_pt")
        },
        "evidence_ids": diagnostic.get("evidence_ids", []),
        "source_ids": selection["case_ids"],
        "calculation_ids": selection["calculation_ids"],
        "panel_definitions": definitions,
        "selection": selection,
        "reading": reading,
    }
    checks.update(panel_ids=[panel_id], selection=selection)
    (output / "diagnostic-checks.json").write_text(
        json.dumps({panel_id: checks}, indent=2), encoding="utf-8"
    )
    (output / "diagnostic-figures.json").write_text(
        json.dumps(
            {"figures": [figure], "style": style.model_dump(), "visual_review": "required"},
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_script(study_path, diagnostic_path, output, panel_id, style)
    return figure
