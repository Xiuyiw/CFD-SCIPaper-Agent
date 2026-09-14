"""Render the prescribed synthetic wall fields without spatial interpolation.

Usage: python plot_wall.py SOURCE OUTPUT
SOURCE is wall.csv, or a directory containing wall.csv or inputs/wall.csv.
The exported local copy can be rerun with source-data.csv as SOURCE. The field
contract is inputs/method.md: each facet spans y = 0--1 mm, with constant T.
These are analytical fields, not CFD or experimental validation.
"""

from __future__ import annotations

import argparse
import csv
import math
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors, font_manager
from matplotlib.cm import ScalarMappable
from matplotlib.patches import Rectangle
from matplotlib.text import Text

WIDTH_MM = 160.0
HEIGHT_MM = 63.0
DPI = 300
CASES = ("Reference", "Modified")
FONT_SIZE = 9.0


def _read_facets(source: Path) -> tuple[Path, dict[str, list[dict[str, float]]]]:
    if source.is_dir():
        source = next(
            (p for p in (source / "wall.csv", source / "inputs/wall.csv") if p.is_file()),
            source / "wall.csv",
        )
    with source.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if {row["case"] for row in rows} != set(CASES):
        raise ValueError("Expected exactly Reference and Modified fields.")
    fields = {}
    for case in CASES:
        facets = [
            {
                "x0": float(row["x0 [mm]"]),
                "x1": float(row["x1 [mm]"]),
                "temperature": float(row["T [degC]"]),
                "area": float(row["area [mm2]"]),
            }
            for row in rows
            if row["case"] == case
        ]
        facets.sort(key=lambda facet: facet["x0"])
        if len(facets) != 6:
            raise ValueError(f"{case}: expected six facets from the declared method.")
        boundary = 0.0
        for facet in facets:
            if not all(math.isfinite(value) for value in facet.values()):
                raise ValueError(f"{case}: nonfinite facet value.")
            width = facet["x1"] - facet["x0"]
            if (
                width <= 0
                or not math.isclose(facet["x0"], boundary, abs_tol=1e-10)
                or not math.isclose(facet["area"], width, abs_tol=1e-10)
            ):
                raise ValueError(f"{case}: facets must tile the 1 mm wide wall exactly.")
            boundary = facet["x1"]
        if not math.isclose(boundary, 10.0, abs_tol=1e-10):
            raise ValueError(f"{case}: wall must extend from x = 0 to 10 mm.")
        fields[case] = facets
    return source, fields


def _check_layout(fig: plt.Figure, axes: list[plt.Axes]) -> None:
    """Check full-canvas text containment and separation of the two map boxes."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    canvas = fig.bbox
    for artist in fig.findobj(Text):
        if not artist.get_visible() or not artist.get_text().strip():
            continue
        box = artist.get_window_extent(renderer)
        if (
            box.width
            and box.height
            and not (
                box.x0 >= canvas.x0
                and box.y0 >= canvas.y0
                and box.x1 <= canvas.x1
                and box.y1 <= canvas.y1
            )
        ):
            raise ValueError(f"Text outside the fixed canvas: {artist.get_text()!r}")
    if axes[0].get_tightbbox(renderer).overlaps(axes[1].get_tightbbox(renderer)):
        raise ValueError("Map labels or data boxes overlap.")


def run(source: Path, output: Path) -> Path:
    """Create four exports, an unmodified source CSV and an editable local script.

    Existing outputs may be regenerated from the exported local script. A distinct
    existing local script is never silently replaced by this master copy.
    """
    source, fields = _read_facets(Path(source))
    output = Path(output)
    local_script = output / "plot_wall.py"
    script = Path(__file__).resolve()
    if (
        local_script.exists()
        and local_script.resolve() != script
        and local_script.read_bytes() != script.read_bytes()
    ):
        raise FileExistsError(f"Preserve local edits: run {local_script} or use a fresh output.")
    output.mkdir(parents=True, exist_ok=True)
    installed_fonts = {font.name for font in font_manager.fontManager.ttflist}
    font = "Times New Roman" if "Times New Roman" in installed_fonts else "DejaVu Serif"
    style = {
        "font.family": "serif",
        "font.serif": [font, "DejaVu Serif"],
        "font.size": FONT_SIZE,
        "axes.labelsize": FONT_SIZE,
        "axes.titlesize": FONT_SIZE,
        "xtick.labelsize": FONT_SIZE,
        "ytick.labelsize": FONT_SIZE,
        "axes.linewidth": 0.6,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "savefig.bbox": None,
    }
    temperatures = [facet["temperature"] for facets in fields.values() for facet in facets]
    norm = colors.Normalize(vmin=min(temperatures), vmax=max(temperatures))
    cmap = matplotlib.colormaps["cividis"]
    with plt.rc_context(style):
        fig = plt.figure(figsize=(WIDTH_MM / 25.4, HEIGHT_MM / 25.4), dpi=DPI)
        axes = []
        # 126 mm map width and 12.6 mm height preserve the physical 10:1 ratio.
        for index, case in enumerate(CASES):
            ax = fig.add_axes([0.095, 0.64 - index * 0.34, 0.7875, 0.20])
            axes.append(ax)
            for facet in fields[case]:
                ax.add_patch(
                    Rectangle(
                        (facet["x0"], 0),
                        facet["x1"] - facet["x0"],
                        1,
                        facecolor=cmap(norm(facet["temperature"])),
                        edgecolor="none",
                        antialiased=False,
                    )
                )
            ax.set(xlim=(0, 10), ylim=(0, 1), aspect="equal")
            ax.set_xticks([0, 2, 4, 6, 8, 10])
            ax.set_yticks([0, 1])
            ax.tick_params(direction="out", length=2.5, width=0.6, pad=2)
            ax.set_ylabel("y (mm)", labelpad=5)
            ax.set_title(f"({chr(97 + index)}) {case}", loc="left", pad=5)
            if index == 0:
                ax.tick_params(labelbottom=False)
            else:
                ax.set_xlabel("x (mm)", labelpad=4)
        color_axis = fig.add_axes([0.915, 0.30, 0.014, 0.54])
        colorbar = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=color_axis)
        colorbar.set_ticks([37, 44, 51, 58])
        colorbar.ax.tick_params(direction="out", length=2.5, width=0.6, pad=2)
        colorbar.ax.set_title("T (°C)", fontsize=FONT_SIZE, pad=6)
        colorbar.outline.set_linewidth(0.6)
        _check_layout(fig, axes)
        for extension in ("svg", "pdf", "png", "tiff"):
            fig.savefig(output / f"wall.{extension}", dpi=DPI, facecolor="white")
        plt.close(fig)
    target_csv = output / "source-data.csv"
    if source.resolve() != target_csv.resolve():
        shutil.copy2(source, target_csv)
    if script != local_script.resolve():
        shutil.copy2(script, local_script)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(run(args.source, args.output))
