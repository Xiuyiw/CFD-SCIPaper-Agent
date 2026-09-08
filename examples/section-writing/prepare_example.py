"""Create an analytical, synthetic two-figure example; not CFD validation data."""

# ruff: noqa: E501 -- Scientific prose literals are kept as complete sentences.

from __future__ import annotations

import csv
import json
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def prepare(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, root / "prepare_example.py")
    # Fully developed circular-pipe reference, constant properties, uniform wall heat flux.
    diameter, length, viscosity, density = 0.01, 1.0, 0.001, 1000.0
    velocities = [0.02, 0.04, 0.06]
    pressures = [32 * viscosity * length * u / diameter**2 for u in velocities]
    reynolds = [density * u * diameter / viscosity for u in velocities]
    nusselt = [4.36] * len(velocities)
    with (root / "source-data.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["case_id", "velocity_m_s", "Re", "pressure_drop_Pa", "Nu"])
        writer.writerows(
            zip(["A", "B", "C"], velocities, reynolds, pressures, nusselt, strict=True)
        )
    for name, values, ylabel in (
        ("pressure", pressures, "Pressure drop (Pa)"),
        ("heat", nusselt, "Nusselt number (–)"),
    ):
        fig, ax = plt.subplots(figsize=(5.6, 3.4), layout="constrained")
        for x, y, marker, color in zip(
            velocities, values, ["o", "s", "^"], ["#356887", "#b4764f", "#637d58"], strict=True
        ):
            ax.plot(x, y, marker=marker, color=color, linestyle="none", markersize=7)
        ax.set(xlabel="Mean velocity (m s⁻¹)", ylabel=ylabel)
        ax.grid(axis="y", color="0.85", linewidth=0.5)
        ax.set_axisbelow(True)
        if name == "heat":
            ax.set_ylim(0, 6)
        for extension in ("png", "svg", "pdf", "tiff"):
            with matplotlib.rc_context({"svg.fonttype": "none", "pdf.fonttype": 42}):
                fig.savefig(root / f"{name}.{extension}", dpi=240)
        plt.close(fig)
    evidence = [
        {
            "id": "model",
            "kind": "interpretation",
            "text": "Analytical synthetic reference: steady incompressible fully developed laminar circular-pipe flow; constant properties; uniform wall heat flux. Delta p = 32 mu L U / D^2; Nu = 4.36. Entry effects and property changes excluded.",
            "source": "prepare_example.py: prepare; declared reference model, not a CFD experiment",
        },
        {
            "id": "pressure-trend",
            "kind": "observation",
            "text": "At fixed geometry and viscosity the analytical pressure drop increases linearly with mean velocity.",
            "source": "source-data.csv: pressure_drop_Pa, cases A-C",
        },
        {
            "id": "thermal-trend",
            "kind": "observation",
            "text": "The fully developed constant-property, uniform-heat-flux model gives unchanged Nu across the three cases.",
            "source": "source-data.csv: Nu, cases A-C",
        },
    ]
    for i, case in enumerate(["A", "B", "C"]):
        for variable, value, unit in (
            ("dp", f"{pressures[i]:.1f}", "Pa"),
            ("re", f"{reynolds[i]:.0f}", ""),
            ("nu", "4.36", ""),
        ):
            evidence.append(
                {
                    "id": f"{variable}-{case}",
                    "kind": "metric",
                    "text": f"Case {case}: {variable}",
                    "value": value,
                    "unit": unit,
                    "source": f"source-data.csv: case {case}, "
                    + {"dp": "pressure_drop_Pa", "re": "Re", "nu": "Nu"}[variable],
                }
            )
    payload = {
        "section_id": "fully-developed-reference",
        "title": "Hydraulic and thermal responses in a fully developed reference model",
        "question": "Why does increasing flow raise pressure drop without changing Nu in this specified model?",
        "context": "Explicitly synthetic analytical tutorial, not measured or solved CFD results. Geometry and properties fixed. No literature excerpts supplied; do not invent citations.",
        "figures": [
            {
                "id": "1",
                "path": "pressure.png",
                "caption": "Analytical pressure drop at three prescribed velocities.",
                "description": "Independent discrete reference values, not an inferred stability range.",
            },
            {
                "id": "2",
                "path": "heat.png",
                "caption": "Fully developed Nusselt number for uniform wall heat flux.",
                "description": "Constant-property reference result, not general heat-exchanger performance.",
            },
        ],
        "evidence": evidence,
        "duties": [
            {
                "purpose": "Explain hydraulic response using fixed-geometry viscous transport.",
                "evidence_ids": ["model", "pressure-trend", "dp-A", "dp-C"],
                "figure_ids": ["1"],
            },
            {
                "purpose": "Contrast thermal response and connect its different definition to model assumptions.",
                "evidence_ids": ["model", "thermal-trend", "nu-A"],
                "figure_ids": ["2"],
            },
        ],
    }
    draft = {
        "title": payload["title"],
        "paragraphs": [
            {
                "text": "The analytical reference separates hydraulic resistance from the fully developed thermal response. In {{figure:1}}, the pressure drop increases from {{value:dp-A}} to {{value:dp-C}} as the prescribed mean velocity increases. With geometry and viscosity fixed, the laminar momentum balance gives pressure drop proportional to mean velocity: the larger axial pressure gradient balances the increased viscous wall stress.",
                "evidence_ids": ["model", "pressure-trend", "dp-A", "dp-C"],
                "figure_ids": ["1"],
            },
            {
                "text": "By contrast, {{figure:2}} retains a Nusselt number of {{value:nu-A}} across the cases. This is the constant-property, thermally fully developed result for a circular pipe with uniform wall heat flux. The normalized thermal profile has the same shape, so increasing bulk velocity does not change this particular wall-transfer coefficient. This conclusion does not describe entrance-region development or temperature-dependent properties.",
                "evidence_ids": ["model", "thermal-trend", "nu-A"],
                "figure_ids": ["2"],
            },
            {
                "text": "Read together, {{figure:1}} and {{figure:2}} demonstrate why a hydraulic trend is not by itself a thermal-performance ranking. The pressure response follows the viscous momentum balance, whereas the reported thermal quantity is constrained by the fully developed heat-transfer model. Their different responses are therefore compatible within this specified analytical reference.",
                "evidence_ids": ["model", "pressure-trend", "thermal-trend"],
                "figure_ids": ["1", "2"],
            },
        ],
        "captions": {
            "1": "Analytical pressure drop versus prescribed mean velocity for a fixed circular pipe under fully developed laminar flow.",
            "2": "Analytical Nusselt number at the same prescribed velocities under constant properties and uniform wall heat flux.",
        },
        "evidence_notes": [
            "Synthetic analytical example, not CFD or experimental validation. The included sample draft is authored tutorial text; the CLI assembles it rather than generating this interpretation."
        ],
        "image_observations": {"1": "author-provided", "2": "author-provided"},
    }
    for name, data in (("input.json", payload), ("sample-draft.json", draft)):
        (root / name).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    prepare(Path(sys.argv[1]))
