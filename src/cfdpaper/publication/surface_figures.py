"""Exact face fields and area-exceedance distributions from declared surface exports."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import numpy as np

from cfdpaper.publication.render_figure import PlotStyle
from cfdpaper.publication.table_evidence import (
    calculate_table,
    display_unit,
    weighted_exceedance_curve,
)

_COLORS = ("#305B78", "#A66B45", "#607C64", "#876F94")
_MARKERS = ("o", "s", "^", "D")
_ARRAY_KEYS = {"values", "weights", "vertices", "connectivity", "starts"}


def _load_case(root, case, arrays, axes):
    relative = Path(case["source"])
    source = (root / relative).resolve()
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or relative.parts[:1] != ("sources",)
        or not source.is_relative_to(root)
        or source.suffix.lower() != ".npz"
        or not source.is_file()
    ):
        raise ValueError("Surface source must be an existing relative sources/ NPZ file")
    with np.load(source, allow_pickle=False) as bundle:
        values, weights, vertices, connectivity, starts = (
            np.array(bundle[arrays[key]], copy=True)
            for key in ("values", "weights", "vertices", "connectivity", "starts")
        )
    if (
        values.ndim != 1
        or not len(values)
        or weights.shape != values.shape
        or starts.shape != values.shape
        or vertices.ndim != 2
        or vertices.shape[1] != 3
        or connectivity.ndim != 1
    ):
        raise ValueError("Face values, areas, starts and vertex geometry must align")
    if (
        not np.issubdtype(values.dtype, np.number)
        or np.iscomplexobj(values)
        or not np.issubdtype(weights.dtype, np.number)
        or np.iscomplexobj(weights)
        or not np.issubdtype(vertices.dtype, np.number)
        or np.iscomplexobj(vertices)
        or not np.isfinite(values).all()
        or not np.isfinite(weights).all()
        or not np.isfinite(vertices).all()
        or not (weights > 0).all()
    ):
        raise ValueError("Surface values/vertices must be finite and areas strictly positive")
    if not all(np.issubdtype(a.dtype, np.integer) for a in (connectivity, starts)):
        raise ValueError("Packed connectivity and face starts must contain integer indices")
    polygons, cursor = [], 0
    for start in starts:
        if int(start) != cursor or cursor >= len(connectivity):
            raise ValueError("Face starts must exactly partition the packed connectivity")
        count = int(connectivity[cursor])
        stop = cursor + count + 1
        if count < 3 or stop > len(connectivity):
            raise ValueError("Each face requires at least three valid vertex indices")
        indices = connectivity[cursor + 1 : stop]
        if (indices < 0).any() or (indices >= len(vertices)).any() or len(set(indices)) < 3:
            raise ValueError("Face connectivity contains invalid or repeated vertex indices")
        polygon = vertices[indices][:, axes]
        # Only reject an edge-on/degenerate projection; the supplied physical areas
        # remain authoritative and are never reconstructed from projected geometry.
        centered = polygon - polygon[0]
        twice_area = np.sum(
            centered[:, 0] * np.roll(centered[:, 1], -1)
            - centered[:, 1] * np.roll(centered[:, 0], -1)
        )
        if twice_area == 0:
            raise ValueError("Face has zero projected area; choose valid projection_axes")
        polygons.append(polygon)
        cursor = stop
    if cursor != len(connectivity):
        raise ValueError("Face starts do not cover the packed connectivity")
    return {**case, "path": source, "values": values, "weights": weights, "polygons": polygons}


def _read_study(config_path):
    data = json.loads(config_path.read_text(encoding="utf-8"))
    for key in ("domain", "quantity", "unit"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"Surface study requires a declared {key}")
    if data.get("coordinate_unit") != "m":
        raise ValueError("Surface vertices must be declared in m; no unit conversion is inferred")
    axes = data.get("projection_axes")
    if (
        not isinstance(axes, list)
        or len(axes) != 2
        or any(type(axis) is not int or axis not in (0, 1, 2) for axis in axes)
        or axes[0] == axes[1]
    ):
        raise ValueError("projection_axes must select two distinct coordinate indices")
    arrays = data.get("arrays")
    if (
        not isinstance(arrays, dict)
        or not _ARRAY_KEYS <= arrays.keys()
        or any(not isinstance(arrays[key], str) or not arrays[key] for key in _ARRAY_KEYS)
    ):
        raise ValueError("Declare the values, weights, vertices, connectivity and starts arrays")
    cases = data.get("cases")
    if (
        not isinstance(cases, list)
        or not 2 <= len(cases) <= 4
        or any(
            not isinstance(case, dict)
            or any(
                not isinstance(case.get(key), str) or not case[key].strip()
                for key in ("id", "label", "source")
            )
            for case in cases
        )
    ):
        raise ValueError("Surface study requires two to four identified and labelled cases")
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Surface case IDs must be unique")
    relation = data.get("exceedance_relation", "above")
    if relation not in {"above", "at-or-above"}:
        raise ValueError("exceedance_relation must be above or at-or-above")
    thresholds = data.get("thresholds")
    if (
        not isinstance(thresholds, list)
        or not thresholds
        or any(type(value) not in (int, float) or not np.isfinite(value) for value in thresholds)
    ):
        raise ValueError("Surface thresholds must be explicitly declared finite numbers")
    return data, [_load_case(config_path.parent, case, arrays, axes) for case in cases]


def _write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _source_rows(data, cases):
    rows, thresholds, curves = [], [], []
    relation = data.get("exceedance_relation", "above")
    limits = [
        min(float(case["values"].min()) for case in cases),
        max(float(case["values"].max()) for case in cases),
    ]
    extent = max(limits[1] - limits[0], abs(limits[0]) * 0.01, 1.0)
    curve_limits = (
        min(limits[0], *data["thresholds"]) - extent * 0.02,
        max(limits[1], *data["thresholds"]) + extent * 0.02,
    )
    for case in cases:
        common = {
            "case_id": case["id"],
            "case_label": case["label"],
            "source": case["source"],
            "value_unit": data["unit"],
            "area_unit": "m^2",
        }
        rows.extend(
            {**common, "array_index": index, "value": float(value), "area": float(area)}
            for index, (value, area) in enumerate(zip(case["values"], case["weights"], strict=True))
        )
        for threshold in data["thresholds"]:
            report = calculate_table(
                case["path"],
                operation="weighted_exceedance",
                columns={"value": data["arrays"]["values"], "weight": data["arrays"]["weights"]},
                units={"value": data["unit"], "weight": "m^2"},
                weight_kind="area",
                quantity_kind=data.get(
                    "quantity_kind",
                    "absolute-temperature"
                    if data["unit"] in {"K", "degC", "°C", "C"}
                    else "ordinary",
                ),
                threshold=threshold,
                exceedance_relation=relation,
            )
            group = report["groups"][0]
            if group["status"] != "computed":
                raise ValueError(f"Surface threshold is unavailable for case {case['id']}")
            thresholds.append(
                {**common, "threshold": threshold, "relation": relation, **group["result"]}
            )
        knots = np.unique(np.concatenate((case["values"], data["thresholds"], curve_limits)))
        result = weighted_exceedance_curve(case["values"], case["weights"], knots, relation)
        curves.extend({**common, "relation": relation, **row} for row in result)
    return rows, thresholds, curves, limits, curve_limits


def _export(fig, output, figure_id, style):
    from matplotlib.transforms import Bbox
    from PIL import Image

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    texts = []
    for ax in fig.axes:
        current = [ax.title, ax._left_title, ax.xaxis.label, ax.yaxis.label]
        current.extend(ax.texts)
        for positions, labels, limits in (
            (ax.get_xticks(), ax.get_xticklabels(), ax.get_xlim()),
            (ax.get_yticks(), ax.get_yticklabels(), ax.get_ylim()),
        ):
            current.extend(
                label
                for position, label in zip(positions, labels, strict=True)
                if min(limits) <= position <= max(limits)
            )
        if ax.get_legend() is not None:
            current.extend(ax.get_legend().get_texts())
        texts.extend(text for text in current if text.get_visible() and text.get_text())
    boxes = [text.get_window_extent(renderer) for text in texts]
    inside = all(
        box.x0 >= 0 and box.y0 >= 0 and box.x1 <= fig.bbox.width and box.y1 <= fig.bbox.height
        for box in boxes
    )
    collisions = [
        (texts[i].get_text(), texts[j].get_text())
        for i, left in enumerate(boxes)
        for j, right in enumerate(boxes)
        if j > i and left.overlaps(right)
    ]
    minimum = min(text.get_fontsize() for text in texts)
    if not inside or collisions:
        outside = [
            text.get_text()
            for text, box in zip(texts, boxes, strict=True)
            if box.x0 < 0 or box.y0 < 0 or box.x1 > fig.bbox.width or box.y1 > fig.bbox.height
        ]
        raise ValueError(
            f"Surface figure labels overlap or leave canvas: {collisions}; outside: {outside}"
        )
    if minimum < 8:
        raise ValueError("Surface figures require at least 8 pt at the declared final width")
    export_options = {}
    if figure_id == "field":
        # Equal-aspect fields may occupy only a short band of the requested canvas.
        # Keep the full declared width and font sizes; remove only unused vertical space.
        tight = fig.get_tightbbox(renderer)
        export_options["bbox_inches"] = Bbox.from_extents(
            0,
            max(0, tight.y0 - 0.05),
            fig.get_figwidth(),
            min(fig.get_figheight(), tight.y1 + 0.05),
        )
        # Freeze the checked layout so vector/raster backends use the same crop geometry.
        fig.set_layout_engine("none")
    for extension in ("svg", "pdf", "png", "tiff"):
        fig.savefig(
            output / f"{figure_id}.{extension}",
            dpi=style.dpi,
            facecolor="white",
            **export_options,
        )
    with Image.open(output / f"{figure_id}.png") as raster:
        raster.load()
        pixels = list(raster.size)
        width = raster.width / style.dpi * 25.4
        if raster.convert("RGB").getextrema() == ((255, 255),) * 3:
            raise ValueError("Surface figure raster is blank")
    with Image.open(output / f"{figure_id}.tiff") as raster:
        raster.load()
        if list(raster.size) != pixels:
            raise ValueError("Surface figure raster dimensions differ")
    return {
        "source_width_mm": width,
        "target_width_mm": style.width_mm,
        "minimum_source_font_pt": minimum,
        "canvas_pixels": pixels,
        "text_inside_canvas": inside,
        "text_nonoverlapping": not collisions,
    }


def render_surface_study(
    config_path: Path, output_dir: Path, *, style: PlotStyle | None = None
) -> list[dict]:
    """Render declared face polygons and exact area-weighted empirical distributions.

    Output paths in returned figure records are relative to ``output_dir``. A local
    author-owned wrapper supplies ``PlotStyle``; this function never writes that script.
    Input face values and actual areas retain their supplied numerical units.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    from matplotlib.colors import Normalize

    config_path, output_dir = Path(config_path).resolve(), Path(output_dir).resolve()
    data, cases = _read_study(config_path)
    rows, thresholds, curves, limits, curve_limits = _source_rows(data, cases)
    style = style or PlotStyle(
        width_mm=160,
        height_mm=110,
        font_family="Times New Roman",
        font_pt=9,
        axis_label_pt=9,
        title_pt=10,
        tick_pt=8,
        legend_pt=9,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "field-source-data.csv", rows)
    _write_csv(output_dir / "threshold-source-data.csv", thresholds)
    _write_csv(output_dir / "distribution-source-data.csv", curves)
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
    }
    all_vertices = np.concatenate([polygon for case in cases for polygon in case["polygons"]])
    low, high = all_vertices.min(axis=0), all_vertices.max(axis=0)
    span = high - low
    columns = 1 if span[0] / span[1] >= 2.5 else 2
    nrows = (len(cases) + columns - 1) // columns
    figures, checks = [], {}
    relation = data.get("exceedance_relation", "above")
    with plt.rc_context(rc):
        # Compressed layout fits the shared colorbar to the actual fixed-aspect field boxes.
        fig = plt.figure(
            figsize=(style.width_mm / 25.4, style.height_mm / 25.4), layout="compressed"
        )
        try:
            grid = fig.add_gridspec(nrows, columns + 1, width_ratios=[1] * columns + [0.045])
            normalization = (
                Normalize(*limits)
                if limits[0] != limits[1]
                else Normalize(limits[0] - 0.5, limits[1] + 0.5)
            )
            for index, case in enumerate(cases):
                ax = fig.add_subplot(grid[index // columns, index % columns])
                collection = PolyCollection(
                    case["polygons"],
                    array=case["values"],
                    cmap="cividis",
                    norm=normalization,
                    edgecolors="none",
                    antialiaseds=False,
                )
                ax.add_collection(collection)
                ax.set_xlim(low[0], high[0])
                ax.set_ylim(low[1], high[1])
                ax.set_aspect("equal", adjustable="box")
                ax.set_title(
                    f"({chr(97 + index)}) {case['label']}", loc="left", color=_COLORS[index], pad=7
                )
                ax.set_xlabel(f"{'xyz'[data['projection_axes'][0]]} (m)")
                ax.set_ylabel(f"{'xyz'[data['projection_axes'][1]]} (m)")
                ax.tick_params(length=3, width=0.6)
                ax.locator_params(axis="both", nbins=4)
            colorbar = fig.colorbar(collection, cax=fig.add_subplot(grid[:, -1]))
            colorbar.set_label(f"{data['quantity']} ({display_unit(data['unit'])})")
            # Fixed aspect can make either projected axis short, especially with fallback fonts.
            # Use Matplotlib's label-space estimate without increasing the existing tick cap.
            fig.canvas.draw()
            for ax in fig.axes[:-1]:
                ax.locator_params(axis="x", nbins=min(4, max(1, ax.xaxis.get_tick_space())))
                ax.locator_params(axis="y", nbins=min(4, max(1, ax.yaxis.get_tick_space())))
            checks["field"] = _export(fig, output_dir, "field", style)
        finally:
            plt.close(fig)
        fig, ax = plt.subplots(
            figsize=(style.width_mm / 25.4, style.height_mm / 25.4), layout="constrained"
        )
        try:
            for index, case in enumerate(cases):
                selected = [row for row in curves if row["case_id"] == case["id"]]
                ax.step(
                    [row["threshold"] for row in selected],
                    [100 * row["exceedance_fraction"] for row in selected],
                    where="post" if relation == "above" else "pre",
                    color=_COLORS[index],
                    linewidth=1.2,
                )
                selected = [row for row in thresholds if row["case_id"] == case["id"]]
                ax.plot(
                    [row["threshold"] for row in selected],
                    [100 * row["exceedance_fraction"] for row in selected],
                    linestyle="none",
                    marker=_MARKERS[index],
                    markersize=4.5,
                    color=_COLORS[index],
                    markerfacecolor="white",
                    markeredgewidth=0.9,
                    label=case["label"],
                    clip_on=False,
                )
            ax.set_xlabel(f"{data['quantity']} threshold ({display_unit(data['unit'])})")
            ax.set_ylabel("Area fraction (%)")
            ax.set_xlim(*curve_limits)
            ax.set_ylim(0, 100)
            ax.set_yticks([0, 25, 50, 75, 100])
            ax.legend(
                loc="lower left",
                bbox_to_anchor=(0, 1.02),
                borderaxespad=0,
                ncol=2,
                frameon=False,
                columnspacing=1.5,
                handletextpad=0.5,
            )
            ax.grid(color="#DEE3E7", linewidth=0.5)
            ax.set_axisbelow(True)
            for edge in ("top", "right"):
                ax.spines[edge].set_visible(False)
            checks["distribution"] = _export(fig, output_dir, "distribution", style)
        finally:
            plt.close(fig)
    captions = {
        "field": (
            f"{data['quantity']} on {data['domain']}. Original face polygons use a shared "
            f"color scale and common projected coordinates in m; values remain in "
            f"{display_unit(data['unit'])}. No spatial interpolation is applied."
        ),
        "distribution": (
            f"Area-weighted {data['quantity'].lower()} exceedance on {data['domain']}. "
            f"Step curves give the fraction of supplied face area with values "
            f"{'strictly above' if relation == 'above' else 'at or above'} each "
            "threshold; markers identify declared thresholds. The empirical steps "
            "retain every distinct face value, without fitting or smoothing."
        ),
    }
    for figure_id in ("field", "distribution"):
        figures.append(
            {
                "id": figure_id,
                "path": f"{figure_id}.png",
                "caption": captions[figure_id],
                "description": captions[figure_id],
                "sizing": {
                    key: checks[figure_id][key]
                    for key in ("source_width_mm", "target_width_mm", "minimum_source_font_pt")
                },
                "evidence_ids": data.get("evidence_ids", []),
            }
        )
    checks.update(
        {
            "value_range": limits,
            "coordinate_limits": [low.tolist(), high.tolist()],
            "projection_axes": data["projection_axes"],
            "coordinate_unit": "m",
            "value_unit": data["unit"],
            "weight_unit": "m^2",
            "face_counts": {case["id"]: len(case["values"]) for case in cases},
            "exceedance_relation": relation,
            "curve_kind": "exact-empirical-step",
            "case_colors": {case["id"]: _COLORS[index] for index, case in enumerate(cases)},
            "case_markers": {case["id"]: _MARKERS[index] for index, case in enumerate(cases)},
        }
    )
    (output_dir / "surface-checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    (output_dir / "surface-figures.json").write_text(
        json.dumps(
            {"figures": figures, "style": style.model_dump(), "visual_review": "required"}, indent=2
        ),
        encoding="utf-8",
    )
    return figures


def render_surface_composite(
    config_path: Path,
    diagnostic_path: Path,
    output_dir: Path,
    *,
    panel_id: str,
    style: PlotStyle | None = None,
) -> dict:
    """Combine two original-face maps with their declared layer-wise signed transfer.

    The finite layout reuses the surface and diagnostic renderers. A diagnostic
    series explicitly names its surface ``case_id``; matching labels or array
    order alone never establishes that relationship. Existing local plot.py is
    retained as the author's re-export entry.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    from matplotlib.colors import Normalize
    from matplotlib.lines import Line2D
    from matplotlib.patches import Rectangle

    from cfdpaper.publication.diagnostic_figures import (
        _axes_style,
        _plot_signed,
        _read_panels,
        _rows,
        _unit,
    )
    from cfdpaper.publication.diagnostic_figures import (
        _write_csv as write_diagnostic_csv,
    )

    config_path, diagnostic_path, output_dir = (
        Path(path).resolve() for path in (config_path, diagnostic_path, output_dir)
    )
    data, cases = _read_study(config_path)
    diagnostic_data, panels = _read_panels(diagnostic_path)
    selected = [(panel, entries) for panel, entries in panels if panel["id"] == panel_id]
    if len(selected) != 1:
        raise ValueError("Composite requires one exact diagnostic panel_id")
    panel, entries = selected[0]
    if panel["kind"] != "signed_flux" or not panel.get("layers") or len(cases) != 2:
        raise ValueError("Composite requires two surface cases and a layered signed_flux panel")
    case_ids = [series.get("case_id") for series in panel["series"]]
    if len(case_ids) != 2 or len(set(case_ids)) != 2 or set(case_ids) != {c["id"] for c in cases}:
        raise ValueError(
            "Composite diagnostic case_id values must match both surface cases exactly"
        )
    cases_by_id = {case["id"]: case for case in cases}
    cases = [cases_by_id[identity] for identity in case_ids]
    if len({_unit(entry, "net") for entry in entries}) != 1:
        raise ValueError("Composite diagnostic series must have the same physical unit")
    rows, _, _, limits, _ = _source_rows(data, cases)
    all_vertices = np.concatenate([polygon for case in cases for polygon in case["polygons"]])
    low, high = all_vertices.min(axis=0), all_vertices.max(axis=0)
    outline = data.get("region_outline")
    if outline is not None:
        axis_names = ["xyz"[axis] for axis in data["projection_axes"]]
        bounds = outline.get("bounds", {}) if isinstance(outline, dict) else {}
        if (
            not isinstance(outline, dict)
            or not isinstance(outline.get("label"), str)
            or not outline["label"].strip()
            or set(bounds) != set(axis_names)
            or any(
                not isinstance(bounds.get(axis), list)
                or len(bounds[axis]) != 2
                or any(
                    type(value) not in (int, float) or not np.isfinite(value)
                    for value in bounds[axis]
                )
                or not low[index] <= bounds[axis][0] < bounds[axis][1] <= high[index]
                for index, axis in enumerate(axis_names)
            )
        ):
            raise ValueError("Composite region_outline must declare bounded projected coordinates")
        outline_bounds = [bounds[axis] for axis in axis_names]
    style = style or PlotStyle(
        width_mm=160,
        height_mm=155,
        font_family="Times New Roman",
        font_pt=9,
        axis_label_pt=9,
        title_pt=10,
        tick_pt=8.5,
        legend_pt=8.5,
        annotation_pt=8.5,
    )
    figure_id = f"field-{panel_id}"
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "field-source-data.csv", rows)
    write_diagnostic_csv(output_dir / "diagnostic-source-data.csv", _rows(entries))
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
    }
    with plt.rc_context(rc):
        fig = plt.figure(
            figsize=(style.width_mm / 25.4, style.height_mm / 25.4), layout="constrained"
        )
        try:
            upper, lower = fig.subfigures(2, 1, height_ratios=[1, 1.12], hspace=0.04)
            grid = upper.add_gridspec(1, 3, width_ratios=[1, 1, 0.05], wspace=0.08)
            normalization = (
                Normalize(*limits)
                if limits[0] != limits[1]
                else Normalize(limits[0] - 0.5, limits[1] + 0.5)
            )
            field_axes = []
            for index, case in enumerate(cases):
                ax = upper.add_subplot(grid[0, index])
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
                ax.set_xlim(low[0], high[0])
                ax.set_ylim(low[1], high[1])
                ax.set_aspect("equal", adjustable="box")
                if outline is not None:
                    x, y = outline_bounds
                    ax.add_patch(
                        Rectangle(
                            (x[0], y[0]),
                            x[1] - x[0],
                            y[1] - y[0],
                            fill=False,
                            edgecolor="#8C3E36",
                            linestyle="--",
                            linewidth=1.0,
                        )
                    )
                    ax.legend(
                        handles=[
                            Line2D(
                                [],
                                [],
                                color="#8C3E36",
                                linestyle="--",
                                linewidth=1.0,
                                label=outline["label"],
                            )
                        ],
                        loc="lower left",
                        bbox_to_anchor=(0, 1.015),
                        frameon=False,
                        borderaxespad=0,
                        handlelength=1.5,
                    )
                ax.set_title(
                    f"({chr(97 + index)}) {case['label']}",
                    loc="left",
                    color=_COLORS[index],
                    pad=25 if outline is not None else 7,
                )
                ax.set_xlabel(f"{'xyz'[data['projection_axes'][0]]} (m)")
                ax.set_ylabel(f"{'xyz'[data['projection_axes'][1]]} (m)")
                ax.tick_params(length=3, width=0.6)
                ax.locator_params(axis="both", nbins=3)
            colorbar = upper.colorbar(collection, cax=upper.add_subplot(grid[0, -1]))
            colorbar.set_label(f"{data['quantity']} ({display_unit(data['unit'])})")
            axes = _plot_signed(lower, panel, entries, style)
            for ax in axes:
                _axes_style(ax)
            axes[0].set_title(f"(c) {panel['title']}", loc="left", pad=35)
            fig.canvas.draw()
            # Align the colorbar to actual equal-aspect map boxes, not their larger grid cells.
            position = colorbar.ax.get_position()
            bottom = min(ax.get_position().y0 for ax in field_axes)
            top = max(ax.get_position().y1 for ax in field_axes)
            colorbar.ax.set_position([position.x0, bottom, position.width, top - bottom])
            fig.set_layout_engine("none")
            checks = _export(fig, output_dir, figure_id, style)
        finally:
            plt.close(fig)
    caption = (
        f"{data['quantity']} on {data['domain']} and height-resolved signed transfer for the "
        "same saved solution of each declared case. Original face polygons retain common "
        f"projected coordinates in m and a shared {display_unit(data['unit'])} color scale; "
        "no spatial interpolation is applied. "
    )
    if outline is not None:
        caption += f"Dashed rectangles identify the declared {outline['label'].lower()}. "
    caption += (
        "Solid and hatched bars retain positive and negative transfers separately; diamonds "
        "show their signed net, with negative and net readings alongside. "
        + panel["sign_convention"]
        + " Layer rows preserve the selected physical bands; full-height rows, when supplied, "
        "retain their aggregate context. These are complementary diagnostics of the same "
        "numerical solutions, not independent validation."
    )
    figure = {
        "id": figure_id,
        "path": f"{figure_id}.png",
        "caption": caption,
        "description": caption,
        "sizing": {
            key: checks[key]
            for key in ("source_width_mm", "target_width_mm", "minimum_source_font_pt")
        },
        "evidence_ids": list(
            dict.fromkeys(data.get("evidence_ids", []) + diagnostic_data.get("evidence_ids", []))
        ),
    }
    checks.update(
        case_ids=case_ids,
        value_range=limits,
        projection_axes=data["projection_axes"],
        region_outline=outline,
        coordinate_unit="m",
        value_unit=data["unit"],
        diagnostic_unit=_unit(entries[0], "net"),
        layer_ids=[layer["id"] for layer in panel["layers"]],
    )
    (output_dir / "composite-checks.json").write_text(
        json.dumps(checks, indent=2), encoding="utf-8"
    )
    (output_dir / "composite-figures.json").write_text(
        json.dumps(
            {"figures": [figure], "style": style.model_dump(), "visual_review": "required"},
            indent=2,
        ),
        encoding="utf-8",
    )
    script = output_dir / "plot.py"
    if not script.exists():
        relative_study = os.path.relpath(config_path, output_dir).replace("\\", "/")
        relative_diagnostic = os.path.relpath(diagnostic_path, output_dir).replace("\\", "/")
        script.write_text(
            '"""Author-local field/diagnostic composite; refine STYLE and rerun this file."""\n'
            "from pathlib import Path\n"
            "from cfdpaper.publication.surface_figures import render_surface_composite\n"
            "from cfdpaper.publication.render_figure import PlotStyle\n\n"
            f"STYLE = PlotStyle(**{style.model_dump()!r})\n"
            "ROOT = Path(__file__).resolve().parent\n"
            "if __name__ == '__main__':\n"
            f"    render_surface_composite(ROOT / {relative_study!r},\n"
            f"        ROOT / {relative_diagnostic!r}, ROOT, panel_id={panel_id!r}, style=STYLE)\n",
            encoding="utf-8",
        )
    return figure
