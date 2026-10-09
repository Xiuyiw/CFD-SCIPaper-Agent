"""Reproduce an invented, nonuniform thermal-history figure from portable CSV."""

import argparse
import csv
import json
import math
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

FONT_FAMILIES = ("Times New Roman", "DejaVu Serif")
HEADER_GAP_PT = 3

STYLE = {
    "font.family": "Times New Roman",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "legend.fontsize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
}
CASES = {"A": ("#416c86", "o"), "B": ("#aa7854", "s")}


def select_font():
    """Choose an available serif explicitly rather than silently falling back to sans."""
    for family in FONT_FAMILIES:
        try:
            font_manager.findfont(
                font_manager.FontProperties(family=family), fallback_to_default=False
            )
        except ValueError:
            continue
        return family
    raise ValueError("The figure requires Times New Roman or Matplotlib's DejaVu Serif")


def cumulative_trapezoids(times, values):
    return [0.0] + [
        math.fsum(
            (values[i] / 2 + values[i + 1] / 2) * (times[i + 1] - times[i]) for i in range(end)
        )
        for end in range(1, len(times))
    ]


def run(source, output):
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    with source.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    font_family = select_font()
    with plt.rc_context({**STYLE, "font.family": font_family}):
        fig, axes = plt.subplots(3, 1, figsize=(160 / 25.4, 155 / 25.4), sharex=True)
        fig.subplots_adjust(left=0.13, right=0.985, bottom=0.09, top=0.89, hspace=0.8)
        for case, (color, marker) in CASES.items():
            selected = [r for r in rows if r["case"] == case]
            times = [float(r["time_s"]) for r in selected]
            temperature = [float(r["temperature_K"]) for r in selected]
            rate = [float(r["heat_rate_W"]) for r in selected]
            ledger = [float(r["cumulative_heat_J"]) for r in selected]
            for ax, values in zip(axes[:2], (temperature, rate), strict=True):
                ax.plot(
                    times,
                    values,
                    color=color,
                    marker=marker,
                    markersize=4.8,
                    markerfacecolor="white",
                    markeredgewidth=1,
                    linewidth=1.1,
                    label=case,
                    clip_on=False,
                )
            axes[2].plot(
                times,
                ledger,
                color=color,
                marker=marker,
                markersize=4.8,
                markerfacecolor="white",
                linewidth=1.1,
                label=f"{case}: ledger",
                clip_on=False,
            )
            axes[2].plot(
                times,
                cumulative_trapezoids(times, rate),
                color=color,
                linewidth=1.1,
                linestyle="--",
                alpha=0.7,
                label=f"{case}: rate integral",
            )
        axes[0].axhline(400, color="0.55", linewidth=0.7, linestyle=":")
        axes[0].text(11.8, 402, "400 K", ha="right", va="bottom", color="0.4", fontsize=8)
        titles = [
            "(a) Thermal magnitude and saved-sample timing",
            "(b) Instantaneous heat-input histories",
            "(c) Rate reconstruction and independent cumulative ledgers",
        ]
        labels = ["Temperature (K)", "Heat-input rate (W)", "Cumulative heat (J)"]
        headers = []
        for ax, title, label in zip(axes, titles, labels, strict=True):
            headers.append(ax.set_title(title, loc="left", y=1.43, pad=0))
            ax.set_ylabel(label, labelpad=7)
            ax.legend(
                loc="lower left",
                bbox_to_anchor=(0, 1.01),
                ncols=2,
                frameon=False,
                borderaxespad=0,
                handlelength=1.8,
                columnspacing=1.6,
            )
            ax.spines[["top", "right"]].set_visible(False)
            ax.grid(axis="y", color="0.88", linewidth=0.5)
            ax.set_axisbelow(True)
            ax.set_xlim(0, 12)
            ax.tick_params(direction="out", length=3)
        axes[0].set_ylim(290, 435)
        axes[1].set_ylim(-1, 23)
        axes[2].set_ylim(-5, 140)
        axes[2].set_xlabel("Time (s)")
        axes[2].set_xticks([0, 1, 3, 6, 8, 12])
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        # Title placement follows the rendered legend height, which changes with fonts.
        # A fixed axes-fraction offset can collide with a two-row fallback-font legend.
        gap_px = HEADER_GAP_PT * fig.dpi / 72
        for ax, title in zip(axes, headers, strict=True):
            title_box = title.get_window_extent(renderer)
            legend_box = ax.get_legend().get_window_extent(renderer)
            x, y = title.get_position()
            title.set_position(
                (
                    x,
                    y
                    + (legend_box.y1 + gap_px - title_box.y0)
                    / ax.get_window_extent(renderer).height,
                )
            )
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        checks = []
        for ax, title in zip(axes, headers, strict=True):
            title_box = title.get_window_extent(renderer)
            legend_box = ax.get_legend().get_window_extent(renderer)
            gap = title_box.y0 - legend_box.y1
            if gap <= 0:
                raise ValueError("Panel title overlaps legend; adjust the header space")
            checks.append({"title_legend_gap_px": gap, "font_family": font_family})
        for upper, lower in zip(axes[:-1], axes[1:], strict=True):
            if lower.get_tightbbox(renderer).y1 >= upper.get_window_extent(renderer).y0:
                raise ValueError("Adjacent panels overlap")
        for extension in ("png", "svg", "pdf", "tiff"):
            fig.savefig(output / f"history.{extension}", dpi=300)
        plt.close(fig)
    shutil.copyfile(source, output / "source-data.csv")
    shutil.copyfile(__file__, output / "plot_history.py")
    (output / "layout-checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(run(args.source, args.output))
