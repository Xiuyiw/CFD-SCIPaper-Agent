"""Complementary region, signed-transfer and budget plots from field declarations."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import numpy as np

from cfdpaper.publication.render_figure import PlotStyle
from cfdpaper.publication.surface_figures import _export
from cfdpaper.publication.table_evidence import display_unit

_COLORS = ("#305B78", "#A66B45", "#607C64", "#876F94")
_MARKERS = ("o", "s", "^", "D")
_OPERATIONS = {
    "regional": "field_integral",
    "signed_flux": "field_integral",
    "budget": "energy_budget",
    "matched_difference": "field_difference",
}


def _source(root, name):
    relative = Path(name)
    source = (root / relative).resolve()
    if relative.is_absolute() or ".." in relative.parts or not source.is_relative_to(root):
        raise ValueError("Diagnostic sources must stay relative to the config directory")
    if not source.is_file():
        raise ValueError(f"Diagnostic source does not exist: {name}")
    return source


def _read_panels(config_path, panel_ids: list[str] | None = None):
    from cfdpaper.publication.field_diagnostics import calculate_field_diagnostic

    data = json.loads(config_path.read_text(encoding="utf-8"))
    declarations = {}
    for declaration in data.get("field_calculations", []):
        identity = declaration["id"]
        if identity in declarations:
            raise ValueError(f"Duplicate diagnostic calculation: {identity}")
        declarations[identity] = declaration
    configured = {}
    for panel in data.get("panels", []):
        identity, kind = panel.get("id"), panel.get("kind")
        if (
            not isinstance(identity, str)
            or not identity
            or any(
                character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                for character in identity
            )
            or identity in configured
            or kind not in _OPERATIONS
            or not isinstance(panel.get("title"), str)
            or not panel["title"].strip()
        ):
            raise ValueError("Diagnostic panels require unique portable id, kind and title")
        configured[identity] = panel
    if panel_ids is not None and (
        not isinstance(panel_ids, list)
        or not panel_ids
        or any(
            not isinstance(identity, str) or identity not in configured for identity in panel_ids
        )
        or len(set(panel_ids)) != len(panel_ids)
    ):
        raise ValueError("panel_ids must select unique existing diagnostic panel IDs")
    selected = configured.values() if panel_ids is None else (configured[key] for key in panel_ids)
    panels, reports = [], {}
    for panel in selected:
        kind = panel["kind"]
        if kind == "signed_flux" and not str(panel.get("sign_convention", "")).strip():
            raise ValueError("signed_flux requires a reader-visible sign_convention")
        series = panel.get("series", [])
        if not isinstance(series, list) or not 1 <= len(series) <= 4:
            raise ValueError("A diagnostic panel requires one to four labelled series")
        view = panel.get("view")
        if view is not None and (kind, view) not in {
            ("regional", "paired_change"),
            ("budget", "decomposition"),
        }:
            raise ValueError("Diagnostic view is incompatible with the panel kind")
        if view == "paired_change":
            pairs = {}
            for item in series:
                pair, role = item.get("pair_id"), item.get("role")
                if (
                    not isinstance(pair, str)
                    or not pair.strip()
                    or role not in {"reference", "comparison"}
                ):
                    raise ValueError("Paired changes require explicit pair_id and role")
                if role in pairs.setdefault(pair, set()):
                    raise ValueError("Paired changes require one reference and comparison")
                pairs[pair].add(role)
            if any(roles != {"reference", "comparison"} for roles in pairs.values()):
                raise ValueError("Paired changes require one reference and comparison")
        layers = panel.get("layers")
        if layers is not None:
            if (
                kind != "signed_flux"
                or not isinstance(layers, list)
                or not layers
                or any(
                    not isinstance(layer, dict)
                    or any(
                        not isinstance(layer.get(key), str) or not layer[key].strip()
                        for key in ("id", "label")
                    )
                    or layer.get("id") == "all"
                    for layer in layers
                )
                or len({layer["id"] for layer in layers}) != len(layers)
            ):
                raise ValueError("Signed-flux layers require unique nonempty ids and labels")
            totals = [bool(item.get("calculation_id")) for item in series]
            if any(totals) and not all(totals):
                raise ValueError("Full-height calculations must be supplied for every series")
        entries = []
        for index, item in enumerate(series):
            if not isinstance(item.get("label"), str) or not item["label"].strip():
                raise ValueError("Diagnostic series require a label")
            if layers is None:
                calculations = [(None, None, item.get("calculation_id"))]
            else:
                mapping = item.get("calculation_ids")
                if not isinstance(mapping, dict) or set(mapping) != {
                    layer["id"] for layer in layers
                }:
                    raise ValueError("Each signed-flux series must map the same exact layers")
                calculations = [
                    (layer["id"], layer["label"], mapping[layer["id"]]) for layer in layers
                ]
                if item.get("calculation_id"):
                    calculations.append(("all", "Full height", item["calculation_id"]))
            for layer_id, layer_label, calculation_id in calculations:
                declaration = declarations.get(calculation_id)
                if declaration is None or declaration["operation"] != _OPERATIONS[kind]:
                    raise ValueError("Panel calculation operation is missing or incompatible")
                identity = declaration["id"]
                if identity not in reports:
                    reports[identity] = calculate_field_diagnostic(
                        _source(config_path.parent, declaration["source"]), declaration
                    )
                report = reports[identity]
                if kind == "signed_flux" and report.get("result_units", {}).get("net") not in {
                    "W",
                    "kW",
                    "MW",
                }:
                    raise ValueError("signed_flux requires an integrated power unit")
                available = {group["group"]: group for group in report["groups"]}
                default_groups = (
                    [group for group in available if group != "all"]
                    if kind == "regional"
                    else ["all"]
                )
                groups = item.get("groups", default_groups or ["all"])
                if (
                    not isinstance(groups, list)
                    or not groups
                    or len(set(groups)) != len(groups)
                    or (layers is not None and groups != ["all"])
                ):
                    raise ValueError("Panel groups must select unique computed groups")
                for name in groups:
                    group = available.get(name)
                    if group is None or group["status"] != "computed":
                        raise ValueError(f"Diagnostic group is unavailable: {name}")
                    entry = {
                        "series_index": index,
                        "label": item["label"],
                        "group": name,
                        "declaration": declaration,
                        "report": report,
                        "computed": group,
                        "result": group["result"],
                        "total_measure": available["all"]["result"].get("measure"),
                    }
                    for key in ("pair_id", "role"):
                        if key in item:
                            entry[key] = item[key]
                    if layers is not None:
                        entry.update(
                            layer_id=layer_id,
                            layer_label=layer_label,
                            case_id=item.get("case_id", ""),
                        )
                    entries.append(entry)
        if len(entries) > 16:
            raise ValueError("Use focused diagnostic panels with at most sixteen displayed groups")
        panels.append((panel, entries))
    if not panels:
        raise ValueError("At least one diagnostic panel is required")
    return data, panels


def _unit(entry, field):
    units = entry["report"].get("result_units", {})
    if field not in units:
        units = entry["computed"].get("result_units", units)
    if field not in units:
        raise ValueError(f"Diagnostic result is missing its unit: {field}")
    return units[field]


def _rows(entries):
    rows = []
    for entry in entries:
        declaration, group = entry["declaration"], entry["computed"]
        record = {
            "series": entry["label"],
            "group": entry["group"],
            "calculation_id": declaration["id"],
            "operation": declaration["operation"],
            "source": declaration["source"],
            "domain": declaration.get("domain", ""),
            "columns": json.dumps(declaration["columns"], sort_keys=True),
            "input_units": json.dumps(declaration["units"], sort_keys=True),
            "physical_definition": json.dumps(declaration.get("field_options", {}), sort_keys=True),
            "result_units": json.dumps(entry["report"].get("result_units", {}), sort_keys=True),
            "array_indices": json.dumps(group.get("array_indices", [])),
            "csv_records": json.dumps(group.get("csv_records", [])),
            "reference_source": entry["report"].get("reference_source", ""),
            "reference_array_indices": json.dumps(group.get("reference_array_indices", [])),
            "reference_csv_records": json.dumps(group.get("reference_csv_records", [])),
            **entry["result"],
        }
        if "layer_id" in entry:
            record.update({key: entry[key] for key in ("layer_id", "layer_label", "case_id")})
        record.update({key: entry[key] for key in ("pair_id", "role") if key in entry})
        if entry["total_measure"]:
            record["measure_fraction"] = entry["result"]["measure"] / entry["total_measure"]
        rows.append(record)
    return rows


def _write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _axes_style(ax):
    ax.grid(axis="x", color="#DEE3E7", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(length=3, width=0.6)
    ax.locator_params(axis="x", nbins=4)
    for edge in ("top", "right"):
        ax.spines[edge].set_visible(False)


def _labels(entries):
    return [
        entry["label"] if entry["group"] == "all" else f"{entry['label']} / {entry['group']}"
        for entry in entries
    ]


def _plot_regional(fig, panel, entries, style):
    if panel.get("view") == "paired_change":
        return _plot_regional_change(fig, panel, entries, style)
    left, right = fig.subplots(1, 2, gridspec_kw={"width_ratios": [2.2, 1]})
    groups = list(dict.fromkeys(entry["group"] for entry in entries))
    count = len({entry["series_index"] for entry in entries})
    positions = {name: index for index, name in enumerate(groups)}
    for entry in entries:
        index = entry["series_index"]
        y = positions[entry["group"]] + (index - (count - 1) / 2) * 0.15
        first = entry["group"] == groups[0]
        left.plot(
            entry["result"]["weighted_mean"],
            y,
            marker=_MARKERS[index],
            markersize=4.5,
            color=_COLORS[index],
            markerfacecolor="white",
            markeredgewidth=0.9,
            linestyle="none",
            label=entry["label"] if first else None,
        )
        if not entry["total_measure"]:
            raise ValueError("Regional plots require a positive physical area or volume")
        share = 100 * entry["result"]["measure"] / entry["total_measure"]
        right.barh(
            y,
            share,
            height=0.13,
            color=_COLORS[index],
            alpha=0.65,
            edgecolor="white",
            linewidth=0.4,
            hatch=("", "//", "..", "\\\\")[index],
        )
    left.set_yticks(range(len(groups)), [panel.get("group_labels", {}).get(g, g) for g in groups])
    left.invert_yaxis()
    left.set_xlabel(f"Regional mean ({display_unit(_unit(entries[0], 'weighted_mean'))})")
    right.set_xlabel("Domain share (%)")
    right.set_xlim(0, 100)
    left.legend(
        loc="lower left",
        bbox_to_anchor=(0, 1.02),
        frameon=False,
        ncol=2,
        borderaxespad=0,
        columnspacing=1.0,
        handletextpad=0.4,
    )
    left.set_ylim(len(groups) - 0.5, -0.7)
    right.set_ylim(left.get_ylim())
    right.set_yticks([])
    return (left, right)


def _paired_rows(entries):
    """Pair declared regional readings, without implying same-coordinate subtraction."""
    pairs = list(dict.fromkeys(entry["pair_id"] for entry in entries))
    groups = list(dict.fromkeys(entry["group"] for entry in entries))
    rows = []
    for pair in pairs:
        for group in groups:
            selected = [e for e in entries if e["pair_id"] == pair and e["group"] == group]
            roles = {e["role"]: e for e in selected}
            if len(selected) != 2 or set(roles) != {"reference", "comparison"}:
                raise ValueError("Paired regional series must select exactly the same groups")
            reference, comparison = roles["reference"], roles["comparison"]
            first, second = (entry["result"]["weighted_mean"] for entry in (reference, comparison))
            rows.append(
                {
                    "pair_id": pair,
                    "group": group,
                    "reference_calculation_id": reference["declaration"]["id"],
                    "comparison_calculation_id": comparison["declaration"]["id"],
                    "reference_mean": first,
                    "comparison_mean": second,
                    "difference": second - first,
                    "unit": _unit(reference, "weighted_mean"),
                }
            )
    return rows


def _style_index(panel, entry):
    pairs = list(dict.fromkeys(item.get("pair_id") for item in panel["series"]))
    return pairs.index(entry["pair_id"]) if entry.get("pair_id") else entry["series_index"]


def _plot_regional_change(fig, panel, entries, style):
    ax = fig.subplots()
    rows = _paired_rows(entries)
    pairs = list(dict.fromkeys(row["pair_id"] for row in rows))
    groups = list(dict.fromkeys(row["group"] for row in rows))
    for row in rows:
        index = pairs.index(row["pair_id"])
        y = groups.index(row["group"]) + (index - (len(pairs) - 1) / 2) * 0.24
        ax.hlines(y, 0, row["difference"], color=_COLORS[index], linewidth=1.1)
        ax.plot(
            row["difference"],
            y,
            marker=_MARKERS[index],
            linestyle="none",
            color=_COLORS[index],
            markerfacecolor="white",
            markersize=5,
            markeredgewidth=1.1,
            label=row["pair_id"] if row["group"] == groups[0] else None,
            clip_on=False,
        )
        ax.annotate(
            f"{row['difference']:+.2f}",
            (row["difference"], y),
            xytext=(7 if row["difference"] >= 0 else -7, 0),
            textcoords="offset points",
            ha="left" if row["difference"] >= 0 else "right",
            va="center" if len(pairs) == 1 else ("bottom" if index == 0 else "top"),
            fontsize=style.annotation_pt,
            color=_COLORS[index],
        )
    values = [row["difference"] for row in rows]
    extent = max(max(abs(value) for value in values), 0.1)
    ax.set_xlim(min(0, min(values)) - extent * 0.35, max(0, max(values)) + extent * 0.35)
    ax.set_ylim(len(groups) - 0.5, -0.65)
    ax.set_yticks(range(len(groups)), [panel.get("group_labels", {}).get(g, g) for g in groups])
    ax.axvline(0, color="#7C858D", linewidth=0.8, linestyle="--", zorder=0)
    ax.set_xlabel(
        panel.get("change_label", f"Comparison − reference ({display_unit(rows[0]['unit'])})")
    )
    ax.legend(
        loc="lower left",
        bbox_to_anchor=(0, 1.025),
        ncol=len(pairs),
        frameon=False,
        borderaxespad=0,
        handletextpad=0.4,
        columnspacing=1.5,
    )
    return (ax,)


def _plot_budget_decomposition(fig, panel, entries, style):
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    ax = fig.subplots()
    for y, entry in enumerate(entries):
        result = entry["result"]
        color = _COLORS[_style_index(panel, entry)]
        output = result["output"] + result["storage"]
        incoming = result["input"] + result["source"]
        ax.barh(y, output, height=0.48, color=color, alpha=0.83, edgecolor="white", linewidth=0.5)
        ax.barh(
            y,
            result["residual"],
            left=output,
            height=0.48,
            color=color,
            alpha=0.25,
            edgecolor=color,
            hatch="///",
            linewidth=0.6,
        )
        ax.plot(
            incoming,
            y,
            marker="D",
            markerfacecolor="white",
            color=color,
            markeredgewidth=1,
            markersize=4,
            linestyle="none",
            zorder=3,
        )
        ax.text(
            output / 2,
            y,
            f"{output:.2f}",
            va="center",
            ha="center",
            fontsize=style.annotation_pt,
            color="white",
        )
        ax.text(
            output + result["residual"] / 2,
            y,
            f"{result['residual']:.2f}",
            va="center",
            ha="center",
            fontsize=style.annotation_pt,
            color="#253540",
        )
        ax.annotate(
            f"{incoming:.2f}",
            (incoming, y),
            xytext=(7, 0),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=style.annotation_pt,
            color=color,
        )
    ax.set_yticks(range(len(entries)), _labels(entries))
    ax.set_ylim(len(entries) - 0.5, -0.65)
    endpoints = [0.0]
    for entry in entries:
        result = entry["result"]
        endpoints.extend((result["output"] + result["storage"], result["input"] + result["source"]))
    minimum, maximum = min(endpoints), max(endpoints)
    margin = (maximum - minimum or 1.0) * 0.18
    ax.set_xlim(minimum - margin if minimum < 0 else 0, maximum + margin)
    ax.set_xlabel(
        panel.get("quantity_label", f"Heat rate ({display_unit(_unit(entries[0], 'residual'))})")
    )
    labels = panel.get("component_labels", {})
    output_label = labels.get("output", "Output + storage")
    input_label = labels.get("input", "Input + source")
    if any(entry["result"]["storage"] != 0 for entry in entries) and (
        "output" in labels or "storage" in labels
    ):
        output_label = f"{labels.get('output', 'Output')} + {labels.get('storage', 'storage')}"
    if any(entry["result"]["source"] != 0 for entry in entries) and (
        "input" in labels or "source" in labels
    ):
        input_label = f"{labels.get('input', 'Input')} + {labels.get('source', 'source')}"
    ax.legend(
        handles=[
            Patch(facecolor="#607580", alpha=0.83, label=output_label),
            Patch(
                facecolor="white",
                edgecolor="#607580",
                hatch="///",
                label=labels.get("residual", "Residual"),
            ),
            Line2D(
                [],
                [],
                color="#607580",
                marker="D",
                markerfacecolor="white",
                linestyle="none",
                markersize=4,
                label=input_label,
            ),
        ],
        loc="lower left",
        bbox_to_anchor=(0, 1.025),
        frameon=False,
        ncol=3,
        borderaxespad=0,
        handlelength=1.4,
        handletextpad=0.5,
        columnspacing=1.3,
    )
    roles = [entry.get("role") for entry in entries]
    for y in range(1, len(entries)):
        if roles[y] is not None and roles[y] != roles[y - 1]:
            ax.axhline(y - 0.5, color="#CBD3D8", linewidth=0.6)
    return (ax,)


def _plot_signed(fig, panel, entries, style):
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    if panel.get("layers") is not None:
        return _plot_layered_signed(fig, panel, entries, style)
    ax = fig.subplots()
    y = np.arange(len(entries))
    for position, entry in zip(y, entries, strict=True):
        result = entry["result"]
        color = _COLORS[entry["series_index"]]
        ax.barh(position, result["positive"], height=0.4, color=color, alpha=0.7)
        ax.barh(
            position,
            result["negative"],
            height=0.4,
            color=color,
            alpha=0.35,
            hatch="///",
            edgecolor=color,
            linewidth=0.6,
        )
        ax.plot(
            result["net"],
            position,
            marker="D",
            color="#30383E",
            markerfacecolor="white",
            markersize=4.5,
            markeredgewidth=1.0,
            linestyle="none",
        )
    ax.axvline(0, color="#7C858D", linewidth=0.8)
    ax.set_yticks(y, _labels(entries))
    ax.set_ylim(len(entries) - 0.5, -0.7)
    ax.set_xlabel(f"Signed transfer ({display_unit(_unit(entries[0], 'net'))})")
    handles = [
        Patch(facecolor="#8798A1", alpha=0.7, label="Positive"),
        Patch(facecolor="white", edgecolor="#8798A1", hatch="///", label="Negative"),
        Line2D(
            [],
            [],
            color="#30383E",
            marker="D",
            markerfacecolor="white",
            markersize=4.5,
            linestyle="none",
            label="Net",
        ),
    ]
    ax.legend(
        handles=handles,
        loc="lower left",
        bbox_to_anchor=(0, 1.02),
        ncol=3,
        frameon=False,
        borderaxespad=0,
        handlelength=1.2,
        columnspacing=1.2,
    )
    return (ax,)


def _plot_layered_signed(fig, panel, entries, style):
    """Matched declared layers, with exact small negative/net readings beside the bars."""
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    ax, readings = fig.subplots(1, 2, gridspec_kw={"width_ratios": [4, 1.7], "wspace": 0.08})
    layers = list(dict.fromkeys(entry["layer_id"] for entry in entries))
    positions = {layer: index for index, layer in enumerate(layers)}
    series = {entry["series_index"]: entry["label"] for entry in entries}
    count = len(series)
    height = min(0.22, 0.7 / count)
    for entry in entries:
        index, result = entry["series_index"], entry["result"]
        y = positions[entry["layer_id"]] + (index - (count - 1) / 2) * (height + 0.14)
        color = _COLORS[index]
        ax.barh(y, result["positive"], height=height, color=color, alpha=0.72)
        ax.barh(
            y,
            result["negative"],
            height=height,
            color=color,
            alpha=0.4,
            hatch="///",
            edgecolor=color,
            linewidth=0.5,
        )
        ax.plot(
            result["net"],
            y,
            marker="D",
            color=color,
            markerfacecolor="white",
            markersize=3.8,
            markeredgewidth=0.9,
            linestyle="none",
            zorder=3,
        )
        for x, field in ((0.49, "negative"), (0.99, "net")):
            readings.text(
                x,
                y,
                f"{result[field]:+.2f}",
                transform=readings.get_yaxis_transform(),
                ha="right",
                va="center",
                fontsize=style.annotation_pt,
                color=color,
            )
    labels = {entry["layer_id"]: entry["layer_label"] for entry in entries}
    ax.set_yticks(range(len(layers)), [labels[layer] for layer in layers])
    ax.set_ylim(len(layers) - 0.45, -0.65)
    readings.set_ylim(ax.get_ylim())
    readings.set_xticks([])
    readings.set_yticks([])
    readings.set_axis_off()
    ax.set_ylabel(panel.get("layer_label", "Declared layer"))
    unit = display_unit(_unit(entries[0], "net"))
    ax.set_xlabel(f"Signed transfer ({unit})")
    ax.axvline(0, color="#7C858D", linewidth=0.8)
    if "all" in positions:
        ax.axhline(positions["all"] - 0.5, color="#B8C1C7", linewidth=0.6)
    for x, label in ((0.49, f"Negative ({unit})"), (0.99, f"Net ({unit})")):
        readings.text(
            x,
            1.025,
            label,
            transform=readings.transAxes,
            ha="right",
            va="bottom",
            fontsize=style.annotation_pt,
            color="#46545E",
        )
    handles = [
        Patch(facecolor=_COLORS[index], alpha=0.72, label=label) for index, label in series.items()
    ]
    handles.extend(
        [
            Patch(facecolor="#8798A1", alpha=0.72, label="Positive"),
            Patch(facecolor="white", edgecolor="#8798A1", hatch="///", label="Negative"),
            Line2D(
                [],
                [],
                color="#46545E",
                marker="D",
                markerfacecolor="white",
                markersize=3.8,
                linestyle="none",
                label="Net",
            ),
        ]
    )
    ax.legend(
        handles=handles,
        loc="lower left",
        bbox_to_anchor=(0, 1.025),
        ncol=3,
        frameon=False,
        borderaxespad=0,
        handlelength=1.15,
        columnspacing=1.0,
        handletextpad=0.45,
    )
    return (ax, readings)


def _plot_pair(fig, panel, entries, style):
    if panel.get("view") == "decomposition":
        return _plot_budget_decomposition(fig, panel, entries, style)
    budget = panel["kind"] == "budget"
    left, right = fig.subplots(1, 2, gridspec_kw={"width_ratios": [2, 1]})
    for y, entry in enumerate(entries):
        result, index = entry["result"], entry["series_index"]
        if budget:
            first, second = result["input"] + result["source"], result["output"] + result["storage"]
            delta, metric = result["residual"], "residual"
        else:
            first, second = result["reference_weighted_mean"], result["comparison_weighted_mean"]
            delta, metric = result["weighted_mean"], "weighted_mean"
        left.plot([first, second], [y, y], color=_COLORS[index], linewidth=1.1)
        for value, fill in ((first, "white"), (second, _COLORS[index])):
            left.plot(
                value,
                y,
                marker=_MARKERS[index],
                color=_COLORS[index],
                markerfacecolor=fill,
                markersize=4.5,
                markeredgewidth=0.9,
                linestyle="none",
            )
        right.hlines(y, 0, delta, color=_COLORS[index], linewidth=1.0)
        right.plot(
            delta,
            y,
            marker=_MARKERS[index],
            color=_COLORS[index],
            markerfacecolor="white",
            markersize=4.5,
            linestyle="none",
        )
    left.set_yticks(range(len(entries)), _labels(entries))
    left.set_ylim(len(entries) - 0.5, -0.7)
    right.set_ylim(left.get_ylim())
    right.set_yticks([])
    unit = display_unit(_unit(entries[0], metric))
    left.set_xlabel(f"{'Budget terms' if budget else 'Original means'} ({unit})")
    right.set_xlabel(f"{'Residual' if budget else 'Difference'} ({unit})")
    right.axvline(0, color="#7C858D", linewidth=0.8)
    from matplotlib.lines import Line2D

    labels = ("Input + source", "Output + storage") if budget else ("Reference", "Comparison")
    handles = [
        Line2D(
            [],
            [],
            marker="o",
            color="#55636C",
            markerfacecolor=fill,
            markersize=4.5,
            linestyle="none",
            label=label,
        )
        for label, fill in zip(labels, ("white", "#55636C"), strict=True)
    ]
    left.legend(
        handles=handles,
        loc="lower left",
        bbox_to_anchor=(0, 1.02),
        frameon=False,
        borderaxespad=0,
        ncol=2,
        columnspacing=1.0,
        handletextpad=0.4,
    )
    return (left, right)


def _caption(panel, entries):
    domains = "; ".join(
        dict.fromkeys(entry["declaration"].get("domain", "declared domain") for entry in entries)
    )
    description = {
        "regional": (
            "Area- or volume-weighted regional means and each region's share of the complete "
            "declared domain. Region membership follows the supplied physical definition; "
            "the domain share is not a heat-transfer fraction."
        ),
        "signed_flux": (
            "Positive and negative integrated exchanges are retained separately; diamonds "
            "show their signed sum. " + panel.get("sign_convention", "")
        ),
        "budget": (
            "Open and filled markers compare input + source with output + storage; the "
            "adjacent residual is input + source − output − storage. These are quantities "
            "from one declared control-volume budget."
        ),
        "matched_difference": (
            "Original weighted means and their same-location comparison minus reference "
            "difference. Spatial identity is checked before subtraction; derived differences "
            "are complementary diagnostics of the same solutions."
        ),
    }[panel["kind"]]
    if panel.get("view") == "paired_change":
        description = (
            "Differences are comparison minus reference regional weighted means, paired by "
            "the declared pair_id. Regions retain each source's supplied definition; "
            "source-following regional changes are not fixed-coordinate field differences. "
            "The complete-domain mean uses the full supplied physical measure."
        )
    elif panel.get("view") == "decomposition":
        description = (
            "Solid segments show output + storage; hatched segments show the algebraic "
            "remainder (input + source − output − storage); diamonds mark input + source. "
            "Numbers retain the same units as the horizontal axis. The remainder is derived "
            "from the two displayed budget sides, not an independent path measurement."
        )
    return f"{panel['title']} on {domains}. {description}"


def _write_script(
    config_path,
    output_dir,
    style,
    *,
    combine=False,
    figure_id="diagnostic-composite",
    panel_ids=None,
):
    script = output_dir / "plot.py"
    if script.exists():
        return
    relative = os.path.relpath(config_path, output_dir).replace("\\", "/")
    script.write_text(
        '"""Author-local plotting entry; edit STYLE here and run this file to refresh."""\n'
        "import argparse\nfrom pathlib import Path\n"
        "from cfdpaper.publication.diagnostic_figures import render_diagnostic_figures\n"
        "from cfdpaper.publication.render_figure import PlotStyle\n\n"
        f"STYLE = PlotStyle(**{style.model_dump()!r})\n\n"
        "if __name__ == '__main__':\n"
        "    root = Path(__file__).resolve().parent\n"
        "    parser = argparse.ArgumentParser()\n"
        f"    parser.add_argument('--config', type=Path, default=root / {relative!r})\n"
        "    parser.add_argument('--output', type=Path, default=root)\n"
        "    args = parser.parse_args()\n"
        "    render_diagnostic_figures(args.config, args.output, style=STYLE, "
        f"combine={combine!r}, figure_id={figure_id!r}, panel_ids={panel_ids!r})\n",
        encoding="utf-8",
    )


def _combined_caption(panel, entries):
    """Reader-facing encodings; full support definitions remain in the source rows."""
    title = panel["title"]
    if panel.get("view") == "paired_change":
        return (
            f"{title}: changes in regional weighted means are comparison minus reference, "
            "with each region retaining its declared spatial definition."
        )
    if panel["kind"] == "budget":
        labels = panel.get("component_labels", {})
        incoming = labels.get("input", "input")
        outgoing = labels.get("output", "output")
        if any(entry["result"]["source"] != 0 for entry in entries):
            incoming += f" + {labels.get('source', 'source')}"
        if any(entry["result"]["storage"] != 0 for entry in entries):
            outgoing += f" + {labels.get('storage', 'storage')}"
        input_expression = f"({incoming})" if " + " in incoming else incoming
        output_expression = f"({outgoing})" if " + " in outgoing else outgoing
        remainder = labels.get("residual", "remainder")
        if panel.get("view") == "decomposition":
            return (
                f"{title}: solid segments show {outgoing}, hatched segments show {remainder}, "
                f"and diamonds mark {incoming}; {remainder} = "
                f"{input_expression} − {output_expression}."
            )
        return (
            f"{title}: open and filled markers compare {incoming} with {outgoing}; "
            f"the adjacent residual is {input_expression} − {output_expression}."
        )
    description = {
        "regional": "regional weighted means and each region's share of the complete domain",
        "signed_flux": (
            "solid and hatched bars retain positive and negative exchanges; "
            "diamonds show their signed sum"
        ),
        "matched_difference": (
            "open and filled markers show reference and comparison weighted means; "
            "the adjacent difference is comparison minus reference at matching locations"
        ),
    }[panel["kind"]]
    caption = f"{title}: {description}."
    if panel["kind"] == "signed_flux":
        caption += " " + panel["sign_convention"]
    return caption


def _render_combined(data, panels, config_path, output_dir, style, figure_id, panel_ids=None):
    import matplotlib.pyplot as plt

    if not 2 <= len(panels) <= 3:
        raise ValueError("A diagnostic composite requires two or three focused panels")
    if not figure_id or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        for c in figure_id
    ):
        raise ValueError("Composite figure_id must be a portable identifier")
    fig = plt.figure(figsize=(style.width_mm / 25.4, style.height_mm / 25.4), layout="constrained")
    rows, differences, captions, panel_axes = [], [], [], []
    try:
        for index, ((panel, entries), subfigure) in enumerate(
            zip(panels, np.atleast_1d(fig.subfigures(len(panels), 1, hspace=0.06)), strict=True)
        ):
            metric = (
                "residual"
                if panel["kind"] == "budget"
                else ("net" if panel["kind"] == "signed_flux" else "weighted_mean")
            )
            if len({_unit(entry, metric) for entry in entries}) != 1:
                raise ValueError("Diagnostic panel series must have the same physical unit")
            function = {
                "regional": _plot_regional,
                "signed_flux": _plot_signed,
                "budget": _plot_pair,
                "matched_difference": _plot_pair,
            }[panel["kind"]]
            axes = function(subfigure, panel, entries, style)
            panel_axes.append(axes)
            for ax in axes:
                _axes_style(ax)
            axes[0].set_title(f"({chr(97 + index)}) {panel['title']}", loc="left", pad=32)
            rows.extend({"panel_id": panel["id"], **row} for row in _rows(entries))
            if panel.get("view") == "paired_change":
                differences.extend(
                    {"panel_id": panel["id"], **row} for row in _paired_rows(entries)
                )
            captions.append(f"({chr(97 + index)}) {_combined_caption(panel, entries)}")
        fig.canvas.draw()
        # Single-axis panels share the same physical data-box edges despite different labels.
        if all(len(axes) == 1 for axes in panel_axes):
            positions = [axes[0].get_position() for axes in panel_axes]
            left, right = max(p.x0 for p in positions), min(p.x1 for p in positions)
            for axes, position in zip(panel_axes, positions, strict=True):
                axes[0].set_position([left, position.y0, right - left, position.height])
            fig.set_layout_engine("none")
        checks = _export(fig, output_dir, figure_id, style)
    finally:
        plt.close(fig)
    _write_csv(output_dir / f"{figure_id}-source-data.csv", rows)
    if differences:
        _write_csv(output_dir / f"{figure_id}-differences.csv", differences)
    caption = " ".join(captions)
    figure = {
        "id": figure_id,
        "path": f"{figure_id}.png",
        "caption": caption,
        "description": caption,
        "sizing": {
            key: checks[key]
            for key in ("source_width_mm", "target_width_mm", "minimum_source_font_pt")
        },
        "evidence_ids": data.get("evidence_ids", []),
    }
    checks["panel_ids"] = [panel["id"] for panel, _ in panels]
    (output_dir / "diagnostic-checks.json").write_text(
        json.dumps({figure_id: checks}, indent=2), encoding="utf-8"
    )
    (output_dir / "diagnostic-figures.json").write_text(
        json.dumps(
            {"figures": [figure], "style": style.model_dump(), "visual_review": "required"},
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_script(
        config_path, output_dir, style, combine=True, figure_id=figure_id, panel_ids=panel_ids
    )
    return [figure]


def render_diagnostic_figures(
    config_path,
    output_dir,
    style=None,
    *,
    combine=False,
    figure_id="diagnostic-composite",
    panel_ids: list[str] | None = None,
) -> list[dict]:
    """Calculate declared fields and render focused figures with exact source rows.

    Author-edited ``plot.py`` remains the refresh entry and is never overwritten.
    ``panel_ids`` selects an ordered subset from the same canonical config.
    Returned records follow the existing research workspace figure format.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    config_path, output_dir = Path(config_path).resolve(), Path(output_dir).resolve()
    data, panels = _read_panels(config_path, panel_ids)
    style = style or PlotStyle(
        width_mm=160,
        height_mm=116 if combine else 80,
        font_family="Times New Roman",
        font_pt=9,
        axis_label_pt=9,
        title_pt=10,
        tick_pt=8,
        legend_pt=8,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    figures, checks = [], {}
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
    if combine:
        rc["mathtext.fontset"] = "stix"
    with plt.rc_context(rc):
        if combine:
            return _render_combined(
                data, panels, config_path, output_dir, style, figure_id, panel_ids
            )
        for panel, entries in panels:
            # Mixing units in one axis must be corrected in the scientific declarations.
            metric = {
                "regional": "weighted_mean",
                "signed_flux": "net",
                "budget": "residual",
                "matched_difference": "weighted_mean",
            }[panel["kind"]]
            if len({_unit(entry, metric) for entry in entries}) != 1:
                raise ValueError("Diagnostic panel series must have the same physical unit")
            rows = (
                len({entry["group"] for entry in entries})
                if panel["kind"] == "regional"
                else len(entries)
            )
            height = min(style.height_mm, max(36, 28 + rows * 8))
            fig = plt.figure(figsize=(style.width_mm / 25.4, height / 25.4), layout="constrained")
            try:
                function = {
                    "regional": _plot_regional,
                    "signed_flux": _plot_signed,
                    "budget": _plot_pair,
                    "matched_difference": _plot_pair,
                }[panel["kind"]]
                axes = function(fig, panel, entries, style)
                for ax in axes:
                    _axes_style(ax)
                checks[panel["id"]] = _export(fig, output_dir, panel["id"], style)
            finally:
                plt.close(fig)
            _write_csv(output_dir / f"{panel['id']}-source-data.csv", _rows(entries))
            if panel.get("view") == "paired_change":
                _write_csv(output_dir / f"{panel['id']}-differences.csv", _paired_rows(entries))
            caption = _caption(panel, entries)
            figures.append(
                {
                    "id": panel["id"],
                    "path": f"{panel['id']}.png",
                    "caption": caption,
                    "description": caption,
                    "sizing": {
                        key: checks[panel["id"]][key]
                        for key in ("source_width_mm", "target_width_mm", "minimum_source_font_pt")
                    },
                    "evidence_ids": data.get("evidence_ids", []),
                }
            )
    _write_script(config_path, output_dir, style, panel_ids=panel_ids)
    (output_dir / "diagnostic-checks.json").write_text(
        json.dumps(checks, indent=2), encoding="utf-8"
    )
    (output_dir / "diagnostic-figures.json").write_text(
        json.dumps(
            {"figures": figures, "style": style.model_dump(), "visual_review": "required"}, indent=2
        ),
        encoding="utf-8",
    )
    return figures
