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


def _read_panels(config_path):
    from cfdpaper.publication.field_diagnostics import calculate_field_diagnostic

    data = json.loads(config_path.read_text(encoding="utf-8"))
    declarations = {}
    for declaration in data.get("field_calculations", []):
        identity = declaration["id"]
        if identity in declarations:
            raise ValueError(f"Duplicate diagnostic calculation: {identity}")
        declarations[identity] = declaration
    panels, identities, reports = [], set(), {}
    for panel in data.get("panels", []):
        identity, kind = panel.get("id"), panel.get("kind")
        if (
            not isinstance(identity, str)
            or not identity
            or any(
                character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                for character in identity
            )
            or identity in identities
            or kind not in _OPERATIONS
            or not isinstance(panel.get("title"), str)
            or not panel["title"].strip()
        ):
            raise ValueError("Diagnostic panels require unique portable id, kind and title")
        identities.add(identity)
        if kind == "signed_flux" and not str(panel.get("sign_convention", "")).strip():
            raise ValueError("signed_flux requires a reader-visible sign_convention")
        series = panel.get("series", [])
        if not isinstance(series, list) or not 1 <= len(series) <= 4:
            raise ValueError("A diagnostic panel requires one to four labelled series")
        entries = []
        for index, item in enumerate(series):
            declaration = declarations.get(item.get("calculation_id"))
            if declaration is None or declaration["operation"] != _OPERATIONS[kind]:
                raise ValueError("Panel calculation operation is missing or incompatible")
            if not isinstance(item.get("label"), str) or not item["label"].strip():
                raise ValueError("Diagnostic series require a label")
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
                [group for group in available if group != "all"] if kind == "regional" else ["all"]
            )
            groups = item.get("groups", default_groups or ["all"])
            if not isinstance(groups, list) or not groups or len(set(groups)) != len(groups):
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


def _plot_signed(fig, panel, entries, style):
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

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


def _plot_pair(fig, panel, entries, style):
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
    return f"{panel['title']} on {domains}. {description}"


def _write_script(config_path, output_dir, style):
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
        "    render_diagnostic_figures(args.config, args.output, style=STYLE)\n",
        encoding="utf-8",
    )


def render_diagnostic_figures(config_path, output_dir, style=None) -> list[dict]:
    """Calculate declared fields and render focused figures with exact source rows.

    Author-edited ``plot.py`` remains the refresh entry and is never overwritten.
    Returned records follow the existing research workspace figure format.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    config_path, output_dir = Path(config_path).resolve(), Path(output_dir).resolve()
    data, panels = _read_panels(config_path)
    style = style or PlotStyle(
        width_mm=160,
        height_mm=80,
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
    with plt.rc_context(rc):
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
    _write_script(config_path, output_dir, style)
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
