"""Synthetic original-face comparison, author style continuation and explicit revision.

All prose is supplied by this example host. Product APIs calculate, bind, redraw,
request interpretation review and export; they do not discover a physical mechanism.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np

from cfdpaper import host_tools

FIGURE_ID = "surface-change"
FIGURE_DIR = Path("sections/results/figures/diagnostics")
CHANGE_ID = "regional-change-all-difference_mean"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def create_materials(root):
    """Prescribe two 64-face fields; no solver output or private data is used."""
    sources = root / "sources"
    sources.mkdir(parents=True)
    vertices, connectivity, starts, centers = [], [], [], []
    for j in range(8):
        for i in range(8):
            x, y, size = i * 0.005, j * 0.005, 0.005
            first = len(vertices)
            vertices.extend(
                [[x, y, 0], [x + size, y, 0], [x + size, y + size, 0], [x, y + size, 0]]
            )
            starts.append(len(connectivity))
            connectivity.extend([4, first, first + 1, first + 2, first + 3])
            centers.append([x + size / 2, y + size / 2])
    x, y = np.asarray(centers).T
    reference = 300 + 10 * x / 0.04 + 6 * y / 0.04
    reference += 30 * np.exp(-((x - 0.01) ** 2 + (y - 0.01) ** 2) / 0.009**2)
    footprint = (x < 0.02) & (y < 0.02)
    comparison = reference + np.where(footprint, -4.0, 2.0)
    for name, values in (("reference", reference), ("comparison", comparison)):
        np.savez(
            sources / f"{name}.npz",
            face_value=values,
            area_m2=np.full(64, 0.005**2),
            vertices_m=vertices,
            faces_connectivity=connectivity,
            face_starts=starts,
        )
    (sources / "definition.md").write_text(
        "# Constructed planar temperatures\n\n"
        "Two prescribed 8 by 8 original-face fields cover the same 0.04 by 0.04 m plane. "
        "Every face has physical area 0.000025 m2; its temperature is constant on that face. "
        "The fixed footprint is 0 <= x <= 0.02 m and 0 <= y <= 0.02 m; its complement "
        "is the remaining surface. These boundaries coincide with original face edges. "
        "Polygon clipping and physical-area weighting reduce the original arrays, with no "
        "display interpolation. Comparison temperatures initially differ from reference "
        "by -4 K in the footprint and +2 K elsewhere. The continuation subtracts 1 K "
        "from the comparison's derived working copy, leaving the initial materials intact. "
        "These are static synthetic fields, not a transport solution or validation data. "
        "Regional contributions compose a mean-temperature change in K, not heat in W.\n",
        encoding="utf-8",
    )
    study = {
        "study_id": "synthetic-linked-surface",
        "title": "Fixed-region contributions to a surface-temperature change",
        "question": "Which fixed-region contribution determines the whole-surface response?",
        "time_support": "Prescribed static original-face fields",
        "common_conditions": ["Identical original polygons, physical areas and fixed regions"],
        "definition": {
            "source": "sources/definition.md",
            "text": "Constructed face temperatures and fixed physical-area partitions",
        },
        "domain": "complete 0.04 by 0.04 m planar surface at z=0",
        "quantity": "Temperature",
        "unit": "K",
        "coordinate_unit": "m",
        "projection_axes": [0, 1],
        "thresholds": [320],
        "selected_figures": [],
        "arrays": {
            "values": "face_value",
            "weights": "area_m2",
            "vertices": "vertices_m",
            "connectivity": "faces_connectivity",
            "starts": "face_starts",
        },
        "cases": [
            {"id": name, "label": name.title(), "source": f"sources/{name}.npz"}
            for name in ("reference", "comparison")
        ],
    }
    box = {"x": [0, 0.02], "y": [0, 0.02]}
    diagnostics = {
        "field_calculations": [
            {
                "id": "regional-change",
                "source": "sources/comparison.npz",
                "domain": study["domain"],
                "operation": "partition_change",
                "quantity_kind": "absolute-temperature",
                "columns": {"value": "face_value", "measure": "area_m2"},
                "units": {"value": "K", "measure": "m2"},
                "field_options": {
                    "association": "face",
                    "integrand": "weighted_mean",
                    "region_assignment": "polygon-clip",
                    "partition_complete": True,
                    "regions": [
                        {"id": "footprint", "bounds": box},
                        {"id": "rest", "bounds": box, "complement": True},
                    ],
                    "reference_source": "reference.npz",
                    "support_mode": "fixed",
                    "common_support": study["domain"] + "; prescribed static support",
                },
            }
        ],
        "panels": [
            {
                "id": FIGURE_ID,
                "kind": "partition_contribution",
                "title": "Fixed-region temperature contributions",
                "group_labels": {"footprint": "Fixed footprint", "rest": "Remaining surface"},
                "series": [{"calculation_id": "regional-change", "label": "Comparison"}],
            }
        ],
    }
    write(root / "study.json", study)
    return root / "study.json", diagnostics


def write_host_drafts(workspace):
    """Supply initial host prose with persistent paragraph and figure identities."""
    prose = {
        "methods": (
            "Two constructed static temperature fields share 64 original square faces. "
            "The fixed footprint occupies one quarter of the complete surface. Physical-area "
            "means and fixed-region contributions use the original values and polygons; "
            "the fields are displayed without interpolation.",
            ["study-definition"],
        ),
        "results": (
            "The whole-surface mean rises from {{value:reference-mean}} to "
            "{{value:comparison-mean}}; the signed comparison-minus-reference change is "
            "{{value:regional-change-all-difference_mean}}. In {{figure:surface-change}}, "
            "the footprint contribution is {{value:regional-change-footprint-contribution}} "
            "and the remaining-surface contribution is "
            "{{value:regional-change-rest-contribution}}. "
            "The positive remaining-surface contribution outweighs footprint cooling.",
            [
                "reference-mean",
                "comparison-mean",
                CHANGE_ID,
                "regional-change-footprint-contribution",
                "regional-change-rest-contribution",
            ],
        ),
        "discussion": (
            "Regional contributions separate the two fixed spatial supports. Their sum is "
            "the same-field whole-surface temperature change, not an independent heat balance "
            "or evidence of a causal transport mechanism.",
            ["study-definition"],
        ),
        "conclusion": (
            "Original fields and signed contributions answer different parts of the comparison: "
            "where the temperature changes and how fixed areas compose the overall mean. "
            "The interpretation is supplied by the example host.",
            ["study-definition"],
        ),
    }
    for sid, relative in read(workspace / "drafts.json").items():
        path, (text, ids) = workspace / relative, prose[sid]
        draft = read(path)
        draft["paragraphs"] = [
            {
                "paragraph_id": f"{sid}-argument",
                "text": text,
                "evidence_ids": ids,
                "figure_ids": [FIGURE_ID] if sid == "results" else [],
            }
        ]
        draft["tables"] = []
        if sid == "results":
            draft["paragraphs"].append(
                {
                    "paragraph_id": "unchanged-scope",
                    "text": "The fixed footprint and its complement cover "
                    "the original surface exactly.",
                    "evidence_ids": ["study-definition"],
                    "figure_ids": [],
                }
            )
            draft["block_order"] = [
                "paragraph:results-argument",
                f"figure:{FIGURE_ID}",
                "paragraph:unchanged-scope",
            ]
            draft["captions"][FIGURE_ID] = (
                "Original face temperatures on a shared Kelvin scale (a,b), with fixed footprint "
                "R1 and remaining surface R2. Signed contributions in K (c) sum to the "
                "whole-surface mean change (open diamond), not a heat budget. "
                "Remaining-surface warming exceeds footprint cooling, giving a positive net change."
            )
            draft["image_observations"][FIGURE_ID] = "not-viewed"
            draft.setdefault("observation_notes", {})[FIGURE_ID] = (
                "The example host prescribes cooling in the footprint and warming elsewhere. "
                "This specification is not a visual review of a particular execution."
            )
        write(path, draft)


def run(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    study, diagnostics = create_materials(output / "materials")
    host_tools.research_task(output / "prepared", study=study)
    attached = host_tools.research_task(
        output / "workspace",
        workspace=output / "prepared",
        diagnostics=diagnostics,
        diagnostic_figure={
            "surface_partition_panel": FIGURE_ID,
            "style": {
                "width_mm": 160,
                "height_mm": 110,
                "font_family": "Times New Roman",
                "font_pt": 9,
                "axis_label_pt": 9,
                "title_pt": 10,
                "tick_pt": 8.5,
                "legend_pt": 8.5,
                "annotation_pt": 8.5,
            },
        },
    )
    write(output / "attached-response.json", attached)
    write_host_drafts(output / "workspace")
    host_tools.research_task(output / "candidate", workspace=output / "workspace")

    # Continue from the returned workspace, not from a regenerated template.
    working = output / "author-working"
    shutil.copytree(output / "candidate/workspace", working)
    script = working / FIGURE_DIR / "plot.py"
    original = script.read_text(encoding="utf-8")
    script.write_text(
        original.replace(
            "if __name__ == '__main__':",
            "# Author-local style adjustment retained across refresh\nSTYLE.tick_pt = 9.0\n\n"
            "if __name__ == '__main__':",
        ),
        encoding="utf-8",
    )
    source = working / "sections/results/sources/comparison.npz"
    with np.load(source, allow_pickle=False) as bundle:
        arrays = {key: bundle[key].copy() for key in bundle.files}
    arrays["face_value"] -= 1.0
    np.savez(source, **arrays)
    refreshed = host_tools.research_task(
        output / "refreshed",
        workspace=working,
        baseline=output / "candidate",
    )
    write(output / "refreshed-response.json", refreshed)

    # Values are current but the retained interpretation needs the host's decision.
    current = read(output / "refreshed/workspace/sections/results/draft.json")
    paragraph = current["paragraphs"][0]
    revised_text = (
        paragraph["text"]
        .replace("mean rises", "mean falls")
        .replace(
            "The positive remaining-surface contribution outweighs footprint cooling.",
            "The negative footprint contribution now outweighs remaining-surface warming.",
        )
    )
    caption = current["captions"][FIGURE_ID]
    proposal = {
        "paragraphs": [
            {
                "section_id": "results",
                "paragraph_id": paragraph["paragraph_id"],
                "before": paragraph["text"],
                "text": revised_text,
            }
        ],
        "captions": [
            {
                "section_id": "results",
                "figure_id": FIGURE_ID,
                "before": caption,
                "text": caption.replace(
                    "Remaining-surface warming exceeds footprint cooling, "
                    "giving a positive net change.",
                    "Footprint cooling exceeds remaining-surface warming in magnitude, "
                    "giving a negative net change.",
                ),
                "image_observation": "not-viewed",
                "observation_note": "Host-supplied numerical interpretation; "
                "inspect this run's preview.",
            }
        ],
    }
    write(output / "host-revision.json", proposal)
    host_tools.research_task(
        output / "revised-workspace",
        workspace=output / "refreshed/workspace",
        revision=proposal,
    )
    revised = host_tools.research_task(
        output / "revised",
        workspace=output / "revised-workspace",
        baseline=output / "refreshed",
    )
    write(output / "revised-response.json", revised)
    return output / "revised/manuscript.docx"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="A new output directory")
    print(run(parser.parse_args().output))
