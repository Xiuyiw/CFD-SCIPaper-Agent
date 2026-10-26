"""Complementary, declaration-bound numerical panels; no inferred evidence."""

from __future__ import annotations

import csv
import inspect
import json
from pathlib import Path

from cfdpaper.publication.render_figure import PlotStyle
from cfdpaper.publication.table_evidence import (
    calculate_declared_table,
    display_unit,
    read_source_records,
    resolve_table_result,
)
from cfdpaper.scientific.units import unit_is_known

_FIELDS = (
    "panel",
    "kind",
    "calculation_id",
    "group",
    "source",
    "source_locator",
    "time",
    "time_unit",
    "value",
    "value_unit",
    "reference_value",
    "reference_lower",
    "reference_upper",
    "difference",
    "difference_unit",
    "outside_distance",
    "reference_kind",
    "time_window",
    "temporal_value_kind",
)

_PAIRED_FIELDS = (
    "operation",
    "range_kind",
    "pair_by",
    "reference_member",
    "comparison_member",
    "reference_source_locator",
    "comparison_source_locator",
    "reference_source_values",
    "comparison_source_values",
    "source_columns",
    "source_units",
    "source_parameters",
)

_DIFFERENCE_FIELDS = (
    "reference_original",
    "comparison_original",
    "difference_direction",
    "crossing_time_kind",
)

_RESPONSE_FIELDS = (
    "series",
    "series_label",
    "x",
    "x_unit",
    "y",
    "y_unit",
    "x_calculation_id",
    "y_calculation_id",
    "x_field",
    "y_field",
    "x_source",
    "y_source",
    "x_source_locator",
    "y_source_locator",
)


def _response_rows(declarations, root, panel, index):
    """Join resolved scalar observations by exact group identity, never by row order."""
    allowed = {
        "kind",
        "title",
        "x_label",
        "y_label",
        "x_calculation_id",
        "series",
        "groups",
        "connect",
    }
    if set(panel) - allowed or any(
        not isinstance(panel.get(key), str) or not panel[key].strip()
        for key in ("title", "x_label", "y_label", "x_calculation_id")
    ):
        raise ValueError(
            "Response panel requires title, x_label, y_label, x_calculation_id and series"
        )
    if type(panel.get("connect", False)) is not bool:
        raise ValueError("Response panel connect must be a boolean")
    series = panel.get("series")
    if not isinstance(series, list) or not series:
        raise ValueError("Response panel series must be a nonempty list")
    for item in series:
        if (
            not isinstance(item, dict)
            or set(item) - {"calculation_id", "label", "field"}
            or any(
                not isinstance(item.get(key), str) or not item[key].strip()
                for key in ("calculation_id", "label")
            )
            or not isinstance(item.get("field", "value"), str)
            or not item.get("field", "value").strip()
        ):
            raise ValueError("Response series requires calculation_id, label and optional field")

    def load(calculation_id, operations):
        declaration = declarations.get(calculation_id)
        if declaration is None or declaration["operation"] not in operations:
            raise ValueError("Response calculation is missing or has an incompatible operation")
        relative = Path(declaration["source"])
        source = (root / relative).resolve()
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[:1] != ("sources",)
            or not source.is_relative_to(root.resolve())
            or not source.is_file()
        ):
            raise ValueError("Evidence panel source must be an existing relative sources/ file")
        report = {**declaration, **calculate_declared_table(source, declaration)}
        return report, {group["group"]: group for group in report["groups"]}

    x_report, x_groups = load(panel["x_calculation_id"], {"scalar_select"})
    selected = panel.get("groups", list(x_groups))
    if (
        not isinstance(selected, list)
        or not selected
        or any(not isinstance(group, str) for group in selected)
        or len(set(selected)) != len(selected)
        or set(selected) - x_groups.keys()
    ):
        raise ValueError("Response panel groups must select unique available x groups")

    def resolve(report, group, field):
        return resolve_table_result([report], calculation_id=report["id"], group=group, field=field)

    def locator(bound):
        key = "array_indices" if "array_indices" in bound else "csv_records"
        return f"{key}:" + ",".join(str(record) for record in bound[key])

    x_values = {group: resolve(x_report, group, "value") for group in selected}
    rows, y_units = [], set()
    for series_index, item in enumerate(series, 1):
        y_report, y_groups = load(item["calculation_id"], {"scalar_select", "paired_change"})
        if set(selected) - y_groups.keys() or (
            "groups" not in panel and x_groups.keys() != y_groups.keys()
        ):
            raise ValueError("Response panel calculations must have matching exact case groups")
        field = item.get("field", "value")
        for group in selected:
            x, y = x_values[group], resolve(y_report, group, field)
            y_units.add(y["unit"])
            if len(y_units) != 1:
                raise ValueError("Response series must use the same resolved y unit in one panel")
            rows.append(
                {
                    "panel": index,
                    "kind": "response",
                    "calculation_id": y["calculation_id"],
                    "group": group,
                    "series": series_index,
                    "series_label": item["label"],
                    "operation": y_report["operation"],
                    "source": y["source"],
                    "source_locator": locator(y),
                    "source_columns": json.dumps(y_report["columns"], sort_keys=True),
                    "source_units": json.dumps(y_report["units"], sort_keys=True),
                    "source_parameters": json.dumps(
                        {
                            key: y_report[key]
                            for key in (
                                "group_by",
                                "pair_by",
                                "reference",
                                "comparison",
                                "row_filters",
                                "unit_column",
                                "quantity_kind",
                                "temperature_reference",
                            )
                            if key in y_report
                        },
                        sort_keys=True,
                    ),
                    **{f"{axis}": bound["raw_value"] for axis, bound in (("x", x), ("y", y))},
                    **{
                        f"{axis}_{key}": bound[key]
                        for axis, bound in (("x", x), ("y", y))
                        for key in ("unit", "calculation_id", "field", "source")
                    },
                    "x_source_locator": locator(x),
                    "y_source_locator": locator(y),
                }
            )
    return rows


def _panel_rows(data, root, panels):
    declarations = {item["id"]: item for item in data["table_calculations"]}
    rows = []
    for index, panel in enumerate(panels, 1):
        if panel.get("kind") == "response":
            rows.extend(_response_rows(declarations, root, panel, index))
            continue
        allowed = {"kind", "calculation_id", "title", "x_label", "y_label", "groups"}
        if set(panel) - allowed or any(
            not isinstance(panel.get(key), str) or not panel[key].strip()
            for key in ("kind", "calculation_id", "title", "x_label", "y_label")
        ):
            raise ValueError("Panel requires kind, calculation_id, title, x_label and y_label")
        expected = {
            "profile": {"temporal", "temporal_difference"},
            "reference_range": {"reference_range", "paired_reference_change"},
        }
        if panel["kind"] not in expected:
            raise ValueError("Unsupported evidence panel kind")
        declaration = declarations.get(panel["calculation_id"])
        if declaration is None or declaration["operation"] not in expected[panel["kind"]]:
            raise ValueError("Panel calculation is missing or has an incompatible operation")
        relative = Path(declaration["source"])
        source = (root / relative).resolve()
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[:1] != ("sources",)
            or not source.is_relative_to(root.resolve())
            or not source.is_file()
        ):
            raise ValueError("Evidence panel source must be an existing relative sources/ file")
        report = calculate_declared_table(source, declaration)
        available = {item["group"]: item for item in report["groups"]}
        selected = panel.get("groups", list(available))
        if (
            not isinstance(selected, list)
            or not selected
            or any(not isinstance(group, str) for group in selected)
            or len(set(selected)) != len(selected)
            or set(selected) - available.keys()
        ):
            raise ValueError("Panel groups must select unique available groups")
        columns = declaration["columns"]
        raw = (
            read_source_records(source, list(columns.values()))
            if panel["kind"] == "profile" and declaration["operation"] == "temporal"
            else []
        )
        for name in selected:
            group = available[name]
            if group["status"] != "computed":
                raise ValueError(f"Panel {index}: group {name!r} has unavailable values")
            location_key = "array_indices" if "array_indices" in group else "csv_records"
            locations = group[location_key]
            common = {
                "panel": index,
                "kind": panel["kind"],
                "calculation_id": declaration["id"],
                "group": name,
                "source": declaration["source"],
                "value_unit": group["difference_unit"]
                if declaration["operation"] == "temporal_difference"
                else declaration["units"]["value"],
            }
            if panel["kind"] == "profile":
                if declaration["operation"] == "temporal_difference":
                    for sample in group["samples"]:
                        location = sample.get("array_index", sample.get("csv_record"))
                        rows.append(
                            {
                                **common,
                                "source_locator": f"{location_key}:{location}",
                                "time": sample["time"],
                                "time_unit": "s",
                                "value": sample["value"],
                                "time_window": json.dumps(group["time_window"]),
                                "temporal_value_kind": group["temporal_value_kind"],
                                "operation": declaration["operation"],
                                "reference_original": sample["reference"],
                                "comparison_original": sample["comparison"],
                                "difference_direction": group["difference_direction"],
                                "crossing_time_kind": group["crossing_time_kind"],
                                "source_columns": json.dumps(columns, sort_keys=True),
                                "source_units": json.dumps(declaration["units"], sort_keys=True),
                            }
                        )
                    continue
                for location in locations:
                    record = raw[location if location_key == "array_indices" else location - 2]
                    rows.append(
                        {
                            **common,
                            "source_locator": f"{location_key}:{location}",
                            "time": float(record[columns["time"]]),
                            "time_unit": "s",
                            "value": float(record[columns["value"]]),
                            "time_window": json.dumps(group["time_window"]),
                            "temporal_value_kind": group["temporal_value_kind"],
                        }
                    )
            else:
                result = group["result"]
                bound_report = {**declaration, **report}
                value_unit = resolve_table_result(
                    [bound_report],
                    calculation_id=declaration["id"],
                    group=name,
                    field="value",
                )["unit"]
                difference_unit = resolve_table_result(
                    [bound_report],
                    calculation_id=declaration["id"],
                    group=name,
                    field="difference",
                )["unit"]
                paired = {}
                if declaration["operation"] == "paired_reference_change":
                    paired = {
                        "operation": declaration["operation"],
                        "range_kind": report["reference_kind"],
                        "pair_by": declaration["pair_by"],
                        "source_columns": json.dumps(columns, sort_keys=True),
                        "source_units": json.dumps(declaration["units"], sort_keys=True),
                        "source_parameters": json.dumps(
                            {
                                key: declaration[key]
                                for key in (
                                    "group_by",
                                    "pair_by",
                                    "reference",
                                    "comparison",
                                    "row_filters",
                                    "unit_column",
                                    "quantity_kind",
                                    "temperature_reference",
                                )
                                if key in declaration
                            },
                            sort_keys=True,
                        ),
                    }
                    for role, member in group["members"].items():
                        member_location = member[
                            "array_index" if location_key == "array_indices" else "csv_record"
                        ]
                        paired[f"{role}_member"] = member["member"]
                        paired[f"{role}_source_locator"] = f"{location_key}:{member_location}"
                        paired[f"{role}_source_values"] = json.dumps(
                            member["values"], sort_keys=True
                        )
                # Missing bounds stay absent: a model/center can still be shown, never a fake span.
                rows.append(
                    {
                        **common,
                        "source_locator": f"{location_key}:"
                        + ",".join(str(location) for location in locations),
                        "value_unit": value_unit,
                        **{
                            key: result[key]
                            for key in (
                                "value",
                                "reference_value",
                                "reference_lower",
                                "reference_upper",
                                "difference",
                                "outside_distance",
                            )
                        },
                        "difference_unit": difference_unit,
                        "reference_kind": report["reference_kind"],
                        **paired,
                    }
                )
    return rows


def _draw_panels(rows, panels, output, style, columns=1):
    """Self-contained renderer copied into the author's standalone local plot.py."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image

    colors = ["#305B78", "#A66B45", "#607C64", "#876F94"]
    markers = ["o", "s", "^", "D"]
    rc = {
        "font.family": [style["font_family"], "serif"],
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "font.size": style["font_pt"],
        "axes.labelsize": style["axis_label_pt"],
        "axes.titlesize": style["title_pt"],
        "xtick.labelsize": style["tick_pt"],
        "ytick.labelsize": style["tick_pt"],
        "legend.fontsize": style["legend_pt"],
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    }
    with plt.rc_context(rc):
        columns = min(columns, len(panels))
        row_count = (len(panels) + columns - 1) // columns
        fig, axes = plt.subplots(
            row_count,
            columns,
            squeeze=False,
            layout="constrained",
            figsize=(style["width_mm"] / 25.4, style["height_mm"] / 25.4),
        )
        try:
            visible_axes = list(axes.flat)[: len(panels)]
            for ax in list(axes.flat)[len(panels) :]:
                ax.set_axis_off()
            for index, (panel, ax) in enumerate(zip(panels, visible_axes, strict=True), 1):
                selected = [r for r in rows if int(r["panel"]) == index]
                groups = list(dict.fromkeys(r["group"] for r in selected))
                if panel["kind"] == "response":
                    series = list(dict.fromkeys(int(row["series"]) for row in selected))
                    for n, series_index in enumerate(series):
                        samples = sorted(
                            [row for row in selected if int(row["series"]) == series_index],
                            key=lambda row: float(row["x"]),
                        )
                        marker = markers[n % len(markers)]
                        ax.plot(
                            [float(row["x"]) for row in samples],
                            [float(row["y"]) for row in samples],
                            label=samples[0]["series_label"],
                            color=colors[n % len(colors)],
                            marker=marker,
                            markersize={"o": 4.2, "s": 3.8, "^": 4.6, "D": 3.7}[marker],
                            markerfacecolor="white",
                            markeredgewidth=0.9,
                            linestyle="-" if panel.get("connect", False) else "None",
                            linewidth=1.0,
                            zorder=3,
                        )
                    ax.margins(x=0.08, y=0.12)
                elif panel["kind"] == "profile":
                    for n, group in enumerate(groups):
                        samples = [r for r in selected if r["group"] == group]
                        ax.plot(
                            [float(r["time"]) for r in samples],
                            [float(r["value"]) for r in samples],
                            label=group,
                            color=colors[n % len(colors)],
                            marker=markers[n % len(markers)],
                            markevery=max(1, len(samples) // 12),
                            markersize=3.8,
                            markerfacecolor="white",
                            markeredgewidth=0.8,
                            linewidth=1.0,
                        )
                else:
                    paired_change = selected[0].get("operation") == "paired_reference_change"
                    for n, row in enumerate(selected):
                        low, high = row.get("reference_lower"), row.get("reference_upper")
                        if low not in (None, "") and high not in (None, ""):
                            ax.plot(
                                [float(low), float(high)],
                                [n, n],
                                color="#8B9BA7",
                                linewidth=3,
                                solid_capstyle="butt",
                                label=(
                                    "Reference-change range" if paired_change else "Supplied range"
                                )
                                if n == 0
                                else None,
                            )
                        ax.scatter(
                            float(row["reference_value"]),
                            n,
                            marker="|",
                            s=65,
                            color="#52616C",
                            label=("Reference change" if paired_change else "Reference center")
                            if n == 0
                            else None,
                        )
                        ax.scatter(
                            float(row["value"]),
                            n,
                            marker="o",
                            s=24,
                            facecolor="white",
                            edgecolor=colors[0],
                            linewidth=1,
                            label=("Model change" if paired_change else "Model")
                            if n == 0
                            else None,
                            zorder=3,
                        )
                        ax.text(
                            1.02,
                            n,
                            f"Δ = {float(row['difference']):+.3g} {row['difference_unit']}",
                            transform=ax.get_yaxis_transform(),
                            va="center",
                            fontsize=style["annotation_pt"],
                            color="#52616C",
                        )
                    ax.set_yticks(range(len(groups)), groups)
                    ax.margins(y=0.4)
                title_pad = (
                    10 + len(series) * style["legend_pt"] * 1.2
                    if panel["kind"] == "response"
                    else 32
                )
                ax.set_title(f"({chr(96 + index)}) {panel['title']}", loc="left", pad=title_pad)
                ax.set_xlabel(panel["x_label"])
                ax.set_ylabel(panel["y_label"])
                ax.legend(
                    loc="lower left",
                    bbox_to_anchor=(0, 1.01),
                    borderaxespad=0,
                    ncol=1
                    if panel["kind"] == "response"
                    else min(3, len(ax.get_legend_handles_labels()[0])),
                    handlelength=1.5,
                    columnspacing=1.1,
                    frameon=False,
                )
                ax.grid(
                    axis="both" if panel["kind"] in {"profile", "response"} else "x",
                    color="#DEE3E7",
                    linewidth=0.5,
                )
                ax.set_axisbelow(True)
                for edge in ("top", "right"):
                    ax.spines[edge].set_visible(False)
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
            boxes, texts = [], []
            for ax in visible_axes:
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
                current.extend(ax.get_legend().get_texts())
                texts.extend(t for t in current if t.get_text())
                boxes.extend(t.get_window_extent(renderer) for t in current if t.get_text())
            inside = all(
                b.x0 >= 0 and b.y0 >= 0 and b.x1 <= fig.bbox.width and b.y1 <= fig.bbox.height
                for b in boxes
            )
            overlaps = any(a.overlaps(b) for n, a in enumerate(boxes) for b in boxes[n + 1 :])
            if not inside or overlaps:
                raise ValueError(
                    "Evidence panel labels overlap or leave canvas; adjust labels/style"
                )
            minimum = min(t.get_fontsize() for t in texts)
            if minimum < 8:
                raise ValueError(
                    "Evidence panels require at least 8 pt at the declared final width"
                )
            for extension in ("svg", "pdf", "png", "tiff"):
                fig.savefig(
                    output / f"evidence-panels.{extension}", dpi=style["dpi"], facecolor="white"
                )
            with Image.open(output / "evidence-panels.png") as image:
                image.load()
                width = image.width / style["dpi"] * 25.4
                canvas = list(image.size)
                if image.convert("RGB").getextrema() == ((255, 255),) * 3:
                    raise ValueError("Evidence panel raster is blank")
            with Image.open(output / "evidence-panels.tiff") as image:
                image.load()
                if list(image.size) != canvas:
                    raise ValueError("Evidence panel raster dimensions differ")
            return {
                "source_width_mm": width,
                "target_width_mm": style["width_mm"],
                "minimum_source_font_pt": minimum,
                "canvas_pixels": canvas,
                "text_inside_canvas": inside,
                "text_nonoverlapping": not overlaps,
                "panel_layout": {"rows": row_count, "columns": columns},
            }
        finally:
            plt.close(fig)


def render_evidence_panels(
    input_path: Path, panels: list[dict], output_dir: Path, *, style=None, columns: int = 1
):
    """Render finite complementary panels from the same declarations used by prose."""
    input_path, output_dir = Path(input_path).resolve(), Path(output_dir).resolve()
    if not output_dir.is_relative_to(input_path.parent):
        raise ValueError("Evidence panel output must remain within the input package")
    if not panels:
        raise ValueError("At least one evidence panel is required")
    if type(columns) is not int or columns < 1:
        raise ValueError("Evidence panel columns must be a positive integer")
    script = output_dir / "plot.py"
    if script.exists():
        raise FileExistsError("Preserve the existing local plot.py; run it for author re-export")
    data = json.loads(input_path.read_text(encoding="utf-8"))
    rows = _panel_rows(data, input_path.parent, panels)
    row_count = (len(panels) + min(columns, len(panels)) - 1) // min(columns, len(panels))
    style = style or PlotStyle(
        width_mm=160,
        height_mm=(75 if any(p["kind"] == "response" for p in panels) else 65) * row_count,
        font_family="Times New Roman",
    )
    # Units come from the bound calculation, never from the host's axis wording.
    prepared = []
    for index, panel in enumerate(panels, 1):
        row = next(r for r in rows if r["panel"] == index)
        labels = dict(panel)
        if panel["kind"] == "response":
            # Recognize exact common/source unit suffixes, not arbitrary parenthetical qualifiers.
            known_units = {
                unit
                for declaration in data["table_calculations"]
                for unit in declaration.get("units", {}).values()
            }
            known_units.update(display_unit(unit) for unit in tuple(known_units))
            for axis in ("x", "y"):
                key, unit = f"{axis}_label", row[f"{axis}_unit"]
                stem, separator, suffix = labels[key].rpartition(" (")
                if (
                    separator
                    and suffix.endswith(")")
                    and (suffix[:-1] in known_units or unit_is_known(suffix[:-1]))
                ):
                    if suffix[:-1] not in {unit, display_unit(unit)}:
                        raise ValueError(
                            f"Response {axis} axis label unit conflicts with result unit"
                        )
                    labels[key] = stem
                if unit:
                    labels[key] += f" ({display_unit(unit)})"
            prepared.append(labels)
            continue
        if row.get("operation") == "paired_reference_change":
            input_unit = json.loads(row["source_units"])["value"]
            for source_unit in {input_unit, display_unit(input_unit)}:
                suffix = f" ({source_unit})"
                if labels["x_label"].endswith(suffix):
                    labels["x_label"] = labels["x_label"][: -len(suffix)]
        if row.get("operation") == "temporal_difference":
            input_unit = json.loads(row["source_units"])["reference"]
            for source_unit in {input_unit, display_unit(input_unit)}:
                suffix = f" ({source_unit})"
                if labels["y_label"].endswith(suffix):
                    labels["y_label"] = labels["y_label"][: -len(suffix)]
        for key, unit in (
            ("x_label", row["time_unit"] if panel["kind"] == "profile" else row["value_unit"]),
            ("y_label", row["value_unit"] if panel["kind"] == "profile" else ""),
        ):
            suffix = f" ({display_unit(unit)})" if unit else ""
            if suffix and not labels[key].endswith(suffix):
                labels[key] += suffix
        prepared.append(labels)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_data = output_dir / "evidence-panels-source-data.csv"
    with source_data.open("w", encoding="utf-8", newline="") as stream:
        fields = _FIELDS + _PAIRED_FIELDS if any("operation" in row for row in rows) else _FIELDS
        if any(row.get("operation") == "temporal_difference" for row in rows):
            fields += _DIFFERENCE_FIELDS
        if any(row["kind"] == "response" for row in rows):
            fields += _RESPONSE_FIELDS
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    script.write_text(
        '"""Author-editable standalone re-export; source-data.csv retains declared evidence."""\n'
        "import csv\nimport json\nfrom pathlib import Path\n\n"
        + inspect.getsource(_draw_panels)
        + f"\nPLOT_STYLE = {style.model_dump()!r}\nPANELS = {prepared!r}\nCOLUMNS = {columns!r}\n"
        + "OUTPUT = Path(__file__).parent\n"
        + "SOURCE_DATA = OUTPUT / 'evidence-panels-source-data.csv'\n"
        + "with SOURCE_DATA.open(encoding='utf-8', newline='') as stream:\n"
        + "    ROWS = list(csv.DictReader(stream))\n"
        + "CHECKS = _draw_panels(ROWS, PANELS, OUTPUT, PLOT_STYLE, columns=COLUMNS)\n"
        + "(OUTPUT / 'layout-checks.json').write_text(\n"
        + "    json.dumps(CHECKS, indent=2), encoding='utf-8')\n",
        encoding="utf-8",
    )
    checks = _draw_panels(rows, prepared, output_dir, style.model_dump(), columns=columns)
    (output_dir / "layout-checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    range_kinds = sorted({r["reference_kind"] for r in rows if "reference_kind" in r})
    caption = "; ".join(p["title"] for p in panels) + ". "
    if any(p["kind"] == "profile" for p in panels):
        caption += (
            "Profiles connect saved samples within the declared exact window, without smoothing. "
        )
    if any(p["kind"] == "response" for p in panels):
        caption += "Response markers show declared case-wise scalar results. "
        if any(p["kind"] == "response" and p.get("connect", False) for p in panels):
            caption += (
                "Connecting lines are straight guides through x-sorted discrete cases, not fits. "
            )
    if any(row.get("operation") == "temporal_difference" for row in rows):
        caption += (
            "Differences are comparison minus reference at each saved record; "
            "the source table retains both original readings. "
        )
    if range_kinds:
        paired_change = any(r.get("operation") == "paired_reference_change" for r in rows)
        if paired_change:
            caption += (
                "Paired-change intervals use conservative endpoint subtraction of the two "
                "supplied envelopes; Δ denotes model change minus reference change. "
            )
        caption += (
            ("Source envelopes are supplied " if paired_change else "Intervals are supplied ")
            + ", ".join(range_kinds)
            + ", not confidence intervals."
        )
    ids = set()
    for panel in panels:
        if panel["kind"] == "response":
            ids.add(panel["x_calculation_id"])
            ids.update(item["calculation_id"] for item in panel["series"])
        else:
            ids.add(panel["calculation_id"])
    figure = {
        "id": "1",
        "path": str((output_dir / "evidence-panels.png").relative_to(input_path.parent)).replace(
            "\\", "/"
        ),
        "caption": caption.strip(),
        "description": caption.strip(),
        "sizing": {
            key: checks[key]
            for key in ("source_width_mm", "target_width_mm", "minimum_source_font_pt")
        },
        "evidence_ids": [
            e["id"]
            for e in data.get("evidence", [])
            if e.get("result_ref", {}).get("calculation_id") in ids
        ],
    }
    (output_dir / "figure-summary.json").write_text(
        json.dumps(
            {
                "figures": [figure],
                "style": style.model_dump(),
                "checks": checks,
                "visual_review": "required",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return figure
