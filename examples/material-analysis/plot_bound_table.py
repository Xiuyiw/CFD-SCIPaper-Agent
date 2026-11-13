"""Author-local discrete comparison. Run on the sibling named result table."""

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

folder = Path(__file__).parent
with (folder / "display.csv").open(encoding="utf-8", newline="") as stream:
    rows = list(csv.DictReader(stream))
colors = {"Reference": "#4b5563", "Modified": "#166b70"}
markers = {"Reference": "o", "Modified": "s"}
with plt.rc_context({"svg.fonttype": "none", "font.family": "DejaVu Serif"}):
    fig, ax = plt.subplots(figsize=(3.8, 2.2), layout="constrained")
    for row in rows:
        ax.plot(
            [float(row["reading"])],
            [row["case"]],
            marker=markers[row["case"]],
            mec=colors[row["case"]],
            mfc="white",
            mew=1.6,
            ms=8,
            linestyle="none",
        )
    ax.set_xlabel(sys.argv[1])
    ax.margins(y=0.4)
    ax.grid(axis="x", color="#dddddd", linewidth=0.5)
    ax.spines[["top", "right"]].set_visible(False)
    for ext in ("png", "svg"):
        fig.savefig(folder / f"comparison.{ext}", dpi=220)
    plt.close(fig)
