"""Connect selected table analyses to editable figures and the section writer."""

from __future__ import annotations

import csv
import json
import shutil
from collections import OrderedDict
from pathlib import Path

from cfdpaper.publication.render_figure import PlotStyle
from cfdpaper.publication.section import _stage, _write, prepare_section
from cfdpaper.publication.table_evidence import calculate_table, display_unit, resolve_table_result

_LABELS = {
    "mean": "Mean",
    "cv": "Population coefficient of variation",
    "area": "Partition area",
    "rate": "Integrated rate",
    "mean_flux": "Area-averaged flux",
    "regional_flux": "Regional average flux",
    "shares": "Signed rate fraction",
    "sum": "Sum of observations",
    "count": "Observation count",
    "value": "Selected value",
    "difference": "Comparison minus reference",
    "relative_change": "Relative change from reference",
    "relative_reduction": "Relative reduction from reference",
    "weighted_mean": "Measure-weighted mean",
    "weighted_std": "Measure-weighted spatial standard deviation",
    "weight_sum": "Total supplied measure",
}


def _source(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or relative.parts[:1] != ("sources",):
        raise ValueError("Analysis source paths must be relative to sources/")
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ValueError(f"Missing analysis source: {name}")
    return resolved


def _points(data: dict, root: Path) -> list[dict]:
    reports = [
        {
            **item,
            **calculate_table(
                _source(root, item["source"]),
                operation=item["operation"],
                columns=item["columns"],
                group_by=item.get("group_by"),
                pair_by=item.get("pair_by"),
                reference=item.get("reference"),
                comparison=item.get("comparison"),
                units=item.get("units"),
                quantity_kind=item.get("quantity_kind", "ordinary"),
                temperature_reference=item.get("temperature_reference"),
                weight_kind=item.get("weight_kind"),
            ),
        }
        for item in data["table_calculations"]
    ]
    available = {e["id"]: e for e in data["evidence"] if e.get("result_ref")}
    plan = data.get("figure_plan") or {}
    selected = plan.get("metric_ids") or list(available)
    if not selected or len(set(selected)) != len(selected) or set(selected) - available.keys():
        raise ValueError("Figure metric IDs must select unique computed evidence")
    return [
        {"evidence_id": key, **resolve_table_result(reports, **available[key]["result_ref"])}
        for key in selected
    ]


def render_analysis_figures(input_path: Path, *, style: PlotStyle | None = None) -> list[dict]:
    """Recompute original tables; plot only like quantities together, without interpolation.

    Called by the supplied local plotting script. This explicit call updates its
    figure exports; preparation itself always uses a new output directory.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    style = style or PlotStyle(width_mm=160, height_mm=95, font_family="Times New Roman")
    input_path = Path(input_path)
    root = input_path.parent
    data = json.loads(input_path.read_text(encoding="utf-8"))
    points = _points(data, root)
    groups = OrderedDict()
    # Even equal units do not make different quantities or statistical domains interchangeable.
    for point in points:
        key = (point["calculation_id"], point["field"], point["unit"])
        groups.setdefault(key, []).append(point)
    figures = []
    output = root / "figures"
    output.mkdir(exist_ok=True)
    plan = data.get("figure_plan") or {}
    rc = {
        "font.family": style.font_family,
        "font.size": style.font_pt,
        "axes.labelsize": style.axis_label_pt,
        "axes.titlesize": style.title_pt,
        "xtick.labelsize": style.tick_pt,
        "ytick.labelsize": style.tick_pt,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    }
    with plt.rc_context(rc):
        for index, ((calculation_id, field, unit), rows) in enumerate(groups.items(), 1):
            fid = str(index)
            stem = f"analysis-{index}"
            label = _LABELS[field]
            title = plan.get("title") if len(groups) == 1 else None
            y_label = plan.get("y_label") if len(groups) == 1 else None
            # A host label describes the quantity, never replaces the computed unit.
            display = display_unit(unit) or "–"
            y_label = y_label or label
            if not y_label.endswith(f"({display})"):
                y_label = f"{y_label} ({display})"
            values = [r["raw_value"] * (100 if unit == "%" else 1) for r in rows]
            category_labels = plan.get("category_labels") or {}
            categories = [category_labels.get(r["evidence_id"], r["group"]) for r in rows]
            if len(set(categories)) != len(categories):
                raise ValueError(
                    "Repeated group labels: supply distinct category_labels for regional metrics"
                )
            fig, ax = plt.subplots(
                figsize=(style.width_mm / 25.4, style.height_mm / 25.4), layout="constrained"
            )
            try:
                ax.scatter(
                    range(len(rows)),
                    values,
                    s=38,
                    facecolor="white",
                    edgecolor="#305B78",
                    linewidth=1.1,
                    zorder=3,
                )
                ax.set_xticks(range(len(rows)), categories)
                ax.set_xlabel(plan.get("x_label") or "Group")
                ax.set_ylabel(y_label)
                ax.set_title(title or label)
                ax.grid(axis="y", color="#DEE3E7", linewidth=0.6)
                ax.set_axisbelow(True)
                ax.margins(x=0.15, y=0.18)
                for edge in ("top", "right"):
                    ax.spines[edge].set_visible(False)
                fig.canvas.draw()
                renderer = fig.canvas.get_renderer()
                ticks_in_view = [
                    label
                    for positions, labels, limits in (
                        (ax.get_xticks(), ax.get_xticklabels(), ax.get_xlim()),
                        (ax.get_yticks(), ax.get_yticklabels(), ax.get_ylim()),
                    )
                    for position, label in zip(positions, labels, strict=True)
                    if min(limits) <= position <= max(limits)
                ]
                texts = [ax.title, ax.xaxis.label, ax.yaxis.label, *ticks_in_view]
                boxes = [t.get_window_extent(renderer) for t in texts if t.get_text()]
                inside = all(
                    b.x0 >= 0 and b.y0 >= 0 and b.x1 <= fig.bbox.width and b.y1 <= fig.bbox.height
                    for b in boxes
                )
                ticks = [t.get_window_extent(renderer) for t in ax.get_xticklabels()]
                collision = any(a.overlaps(b) for i, a in enumerate(ticks) for b in ticks[i + 1 :])
                if not inside or collision:
                    raise ValueError(
                        f"Figure {fid}: labels do not fit; "
                        "shorten group labels or adjust plot style"
                    )
                for extension in ("svg", "pdf", "png", "tiff"):
                    fig.savefig(output / f"{stem}.{extension}", dpi=style.dpi, facecolor="white")
                with (output / f"{stem}-source-data.csv").open(
                    "w", encoding="utf-8", newline=""
                ) as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                minimum_pt = min(t.get_fontsize() for t in texts if t.get_text())
                caption = (
                    f"{title or label} by group. Values were calculated from the declared "
                    f"{calculation_id} table definition; points denote separate groups."
                )
                figures.append(
                    {
                        "id": fid,
                        "path": f"figures/{stem}.png",
                        "caption": caption,
                        "description": caption,
                        "sizing": {
                            "source_width_mm": style.width_mm,
                            "target_width_mm": style.width_mm,
                            "minimum_source_font_pt": minimum_pt,
                        },
                        "evidence_ids": [r["evidence_id"] for r in rows],
                    }
                )
            finally:
                plt.close(fig)
    _write(
        output / "figure-summary.json",
        {
            "figures": figures,
            "style": style.model_dump(),
            "checks": {"text_inside_canvas": True, "x_labels_nonoverlapping": True},
            "visual_review": "required",
        },
    )
    return figures


def build_analysis_section(input_path: Path, output_dir: Path) -> Path:
    """Prepare a real writing package from compiled analysis without replacing author assets."""
    input_path, output_dir = Path(input_path), Path(output_dir)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    with _stage(output_dir) as staged:
        for name in data["source_files"]:
            destination = staged / name
            source = _source(input_path.parent, name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        _write(staged / "analysis-input.json", data)
        presentation = data.get("presentation", "plot")
        if presentation not in {"plot", "prose", "table", "custom"}:
            raise ValueError("Unknown analysis presentation")
        figures = (
            render_analysis_figures(staged / "analysis-input.json")
            if presentation == "plot"
            else []
        )
        existing = data.get("figures", [])
        ids = [fig["id"].casefold() for fig in [*figures, *existing]]
        if len(ids) != len(set(ids)):
            raise ValueError("Existing and calculated figures must use different IDs")
        if presentation == "plot":
            _write_plot_script(staged)
        used = {key for fig in figures for key in fig["evidence_ids"]}
        duties = [
            {
                "purpose": f"Use {fig['id']} to address: {data['question']}",
                "evidence_ids": fig["evidence_ids"],
                "figure_ids": [fig["id"]],
            }
            for fig in figures
        ]
        supporting = [e for e in data["evidence"] if e["kind"] != "metric"]
        unplotted = [
            e["id"] for e in data["evidence"] if e["kind"] == "metric" and e["id"] not in used
        ]
        if existing or supporting or unplotted:
            duties.append(
                {
                    "purpose": "Connect supplied observations and definitions to the analysis.",
                    "evidence_ids": [e["id"] for e in supporting] + unplotted or sorted(used),
                    "figure_ids": [fig["id"] for fig in existing]
                    or ([figures[0]["id"]] if figures else []),
                }
            )
        section_input = {
            k: data[k]
            for k in (
                "section_id",
                "title",
                "question",
                "context",
                "source_files",
                "table_calculations",
            )
        }
        intent = {
            "plot": "Comparison plots are preliminary; assess their scientific usefulness.",
            "prose": "Present the computed contrast in prose; do not manufacture a figure.",
            "table": (
                "Present selected computed values in a native table in draft.json; "
                "no table has yet been written."
            ),
            "custom": (
                "Custom figure production remains pending. Use the evidence to design it; "
                "no replacement default plot was drawn. Do not claim figure completion."
            ),
        }[presentation]
        section_input["context"] += "\nPresentation: " + intent
        if "style" in data:
            section_input["style"] = data["style"]
        if data.get("presentation_reason"):
            section_input["context"] += "\nReason: " + data["presentation_reason"]
        section_input.update(
            figures=[{k: v for k, v in fig.items() if k != "evidence_ids"} for fig in figures]
            + existing,
            evidence=data["evidence"],
            duties=duties,
        )
        _write(staged / "input.json", section_input)
        prepare_section(staged / "input.json", staged / "writing")
    return output_dir / "writing"


def _write_plot_script(staged: Path) -> None:
    (staged / "plot_analysis.py").write_text(
        '"""Local plot entry point: edit STYLE here; raw tables remain unchanged."""\n'
        "from pathlib import Path\n"
        "from cfdpaper.publication.analysis_section import render_analysis_figures\n"
        "from cfdpaper.publication.render_figure import PlotStyle\n\n"
        'STYLE = PlotStyle(width_mm=160, height_mm=95, font_family="Times New Roman")\n'
        "render_analysis_figures(\n"
        '    Path(__file__).with_name("analysis-input.json"), style=STYLE)\n',
        encoding="utf-8",
    )
