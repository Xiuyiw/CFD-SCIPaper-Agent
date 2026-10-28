"""Replay a small source-bound research unit from constructed, redistributable inputs.

The example author supplies the question, figure selection and prose. Product APIs
calculate observations, render one composite and export an editable Word document.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np

from cfdpaper.publication.research_workspace import (
    attach_research_diagnostics,
    build_research_workspace,
    prepare_surface_workspace,
)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def create_materials(root):
    sources = root / "sources"
    sources.mkdir(parents=True)
    # Two original unequal-area faces; the fixed footprint is the first face.
    vertices = [
        [0, 0, 0],
        [0.01, 0, 0],
        [0.04, 0, 0],
        [0, 0.01, 0],
        [0.01, 0.01, 0],
        [0.04, 0.01, 0],
    ]
    specifications = (
        ("A0", "Structure A", "reference", [334, 312], 40),
        ("A1", "Structure A", "comparison", [331, 316], 55),
        ("B0", "Structure B", "reference", [329, 309], 50),
        ("B1", "Structure B", "comparison", [328, 312], 45),
    )
    calculations, temperatures, budgets = [], [], []
    for case, pair, role, values, outgoing in specifications:
        np.savez(
            sources / f"{case}.npz",
            face_value=np.array(values, dtype=float),
            area_m2=[0.0001, 0.0003],
            x=[0.005, 0.025],
            y=[0.005, 0.005],
            z=[0, 0],
            vertices_m=vertices,
            faces_connectivity=[4, 0, 1, 4, 3, 4, 1, 2, 5, 4],
            face_starts=[0, 5],
        )
        (sources / f"budget-{case}.csv").write_text(
            f"incoming,outgoing,source,storage\n100,{outgoing},0,0\n", encoding="utf-8"
        )
        calculations.extend(
            [
                {
                    "id": f"temperature-{case}",
                    "source": f"sources/{case}.npz",
                    "domain": "same complete two-face planar interface",
                    "operation": "field_integral",
                    "columns": {"value": "face_value", "measure": "area_m2", "x": "x"},
                    "units": {"value": "K", "measure": "m2", "x": "m"},
                    "field_options": {
                        "association": "face",
                        "integrand": "weighted_mean",
                        "region_assignment": "centroid",
                        "partition_complete": True,
                        "regions": [
                            {"id": "footprint", "bounds": {"x": [0, 0.01]}},
                            {"id": "rest", "bounds": {"x": [0.01, 0.04]}},
                        ],
                    },
                },
                {
                    "id": f"budget-{case}",
                    "source": f"sources/budget-{case}.csv",
                    "domain": "separate prescribed local control volume",
                    "operation": "energy_budget",
                    "columns": {
                        "input": "incoming",
                        "output": "outgoing",
                        "source": "source",
                        "storage": "storage",
                    },
                    "units": dict.fromkeys(("input", "output", "source", "storage"), "W"),
                    "field_options": {"association": "control_volume"},
                },
            ]
        )
        common = {"label": f"{pair} / {role}", "pair_id": pair, "role": role}
        temperatures.append(
            {
                **common,
                "calculation_id": f"temperature-{case}",
                "groups": ["footprint", "rest", "all"],
            }
        )
        budgets.append({**common, "calculation_id": f"budget-{case}"})
    for pair in ("A", "B"):
        calculations.append(
            {
                "id": f"paired-{pair}",
                "source": f"sources/{pair}1.npz",
                "domain": "same original two-face interface",
                "operation": "field_difference",
                "columns": {
                    "value": "face_value",
                    "measure": "area_m2",
                    "x": "x",
                    "y": "y",
                    "z": "z",
                },
                "units": {"value": "K", "measure": "m2", "x": "m", "y": "m", "z": "m"},
                "field_options": {"association": "face", "reference_source": f"{pair}0.npz"},
            }
        )
    (sources / "definition.md").write_text(
        "# Constructed research-expression inputs\n\n"
        "All arrays and budgets are synthetic, not solver results or experiments. "
        "Each case has the same two constant-value rectangular faces on a 0.04 m by "
        "0.01 m interface. Areas are 0.0001 and 0.0003 m2. The footprint ends exactly "
        "at the shared x=0.01 m face edge; centroid assignment therefore selects "
        "complete faces rather than approximating a cut region. The rest is its "
        "complement. Means use physical face area; paired changes use comparison "
        "minus reference at identical original faces. Spatial support is fixed.\n\n"
        "The four local budgets are separately prescribed accounting examples. "
        "Positive input enters the local volume; positive output leaves it. "
        "Source and storage are explicitly zero. Remainder=input-output is the "
        "unresolved local transfer required by this accounting, not a measured "
        "lateral flux or a numerical convergence residual. No transport relation "
        "connects the temperatures to the local budgets. They cannot establish "
        "a causal heat-transfer mechanism or validate a device.\n",
        encoding="utf-8",
    )
    write(
        root / "study.json",
        {
            "study_id": "synthetic-research-expression",
            "title": "Regional temperature response and a local energy remainder",
            "question": "Can footprint cooling coexist with whole-interface warming?",
            "time_support": "Prescribed static fields and separate zero-storage budget examples",
            "common_conditions": [
                "Same original face geometry and physical areas",
                "Same fixed regions and declared operators",
            ],
            "definition": {
                "source": "sources/definition.md",
                "text": "Constructed paired face temperatures and separate local budgets",
            },
            "domain": "complete two-face planar interface",
            "quantity": "Temperature",
            "unit": "K",
            "coordinate_unit": "m",
            "projection_axes": [0, 1],
            "thresholds": [320],
            "exceedance_relation": "above",
            # Retain original diagnostics without putting every output in the paper.
            "selected_figures": [],
            "arrays": {
                "values": "face_value",
                "weights": "area_m2",
                "vertices": "vertices_m",
                "connectivity": "faces_connectivity",
                "starts": "face_starts",
            },
            "cases": [
                {"id": case, "label": f"{pair} / {role}", "source": f"sources/{case}.npz"}
                for case, pair, role, _, _ in specifications
            ],
        },
    )
    write(
        root / "diagnostics.json",
        {
            "field_calculations": calculations,
            "panels": [
                {
                    "id": "regional-change",
                    "kind": "regional",
                    "view": "paired_change",
                    "title": "Fixed-region temperature response",
                    "series": temperatures,
                    "group_labels": {
                        "footprint": "Heated footprint",
                        "rest": "Remaining interface",
                        "all": "Whole interface",
                    },
                },
                {
                    "id": "local-budget",
                    "kind": "budget",
                    "view": "decomposition",
                    "title": "Local energy accounting",
                    "series": budgets,
                    "component_labels": {
                        "input": "input",
                        "output": "output",
                        "residual": "remainder",
                    },
                },
            ],
        },
    )
    return root / "study.json", root / "diagnostics.json"


def write_host_drafts(workspace):
    """Disclosed example-author prose, not an automatically inferred explanation."""
    paragraphs = {
        "methods": [
            (
                "Two prescribed reference–comparison pairs share the same two-face interface. "
                "The heated footprint occupies one quarter of its area; the remaining region "
                "occupies three quarters. All means use physical area. Regional boundaries "
                "coincide with original face edges, and paired changes retain those faces. "
                "Separate local budgets prescribe input, output and zero source/storage. "
                "Their remainder is input minus output; it is an accounting requirement, "
                "not an independently extracted flux.",
                ["study-definition"],
                [],
            )
        ],
        "results": [
            (
                "The whole-interface mean rises from {{value:A0-mean}} to {{value:A1-mean}} "
                "for Structure A and from {{value:B0-mean}} to {{value:B1-mean}} for Structure B. "
                "The source-bound original means and their differences are retained in "
                "{{table:paired-means}}; the changes are {{value:paired-A-all-difference_mean}} "
                "and {{value:paired-B-all-difference_mean}}, respectively.",
                [
                    "A0-mean",
                    "A1-mean",
                    "B0-mean",
                    "B1-mean",
                    "paired-A-all-difference_mean",
                    "paired-B-all-difference_mean",
                ],
                [],
            ),
            (
                "In contrast, the footprint mean in Structure A falls from "
                "{{value:temperature-A0-footprint-weighted_mean}} to "
                "{{value:temperature-A1-footprint-weighted_mean}}. The corresponding "
                "remaining-region mean rises from {{value:temperature-A0-rest-weighted_mean}} "
                "to {{value:temperature-A1-rest-weighted_mean}}. {{figure:thermal-budget}} "
                "places these fixed-region changes beside the separately prescribed local budgets. "
                "{{table:local-budget}} retains their original inputs and derived remainders.",
                [
                    "temperature-A0-footprint-weighted_mean",
                    "temperature-A1-footprint-weighted_mean",
                    "temperature-A0-rest-weighted_mean",
                    "temperature-A1-rest-weighted_mean",
                ],
                ["thermal-budget"],
            ),
        ],
        "discussion": [
            (
                "Footprint cooling does not establish whole-interface cooling: warming over "
                "the larger remaining area raises the overall mean in both constructed pairs. "
                "The local budgets distinguish output from the remainder required by their "
                "declared accounting. Because these budgets and temperatures were prescribed "
                "separately, their juxtaposition does not identify lateral conduction, mixing "
                "or another causal mechanism. The paired differences are derived readings "
                "of the original fields, not additional independent evidence.",
                ["study-definition"],
                [],
            )
        ],
        "conclusion": [
            (
                "The example separates local temperature response, whole-interface response "
                "and local accounting. Its fixed supports and source-bound arithmetic make "
                "the comparison reproducible; the host author remains responsible for the "
                "research question, interpretation and final manuscript selection.",
                ["study-definition"],
                [],
            )
        ],
    }
    for sid, name in read(workspace / "drafts.json").items():
        path = workspace / name
        draft = read(path)
        draft["paragraphs"] = [
            {"text": text, "evidence_ids": ids, "figure_ids": figures}
            for text, ids, figures in paragraphs[sid]
        ]
        if sid == "results":
            for paragraph, identity in zip(
                draft["paragraphs"], ("whole-response", "regional-budget"), strict=True
            ):
                paragraph["paragraph_id"] = identity
            draft["block_order"] = [
                "paragraph:whole-response",
                "table:paired-means",
                "paragraph:regional-budget",
                "figure:thermal-budget",
                "table:local-budget",
            ]
            paired_ids = [
                f"paired-{pair}-all-{field}"
                for pair in ("A", "B")
                for field in ("reference_mean", "comparison_mean", "difference_mean")
            ]
            budget_ids = [
                f"budget-{case}-all-{field}"
                for case in ("A0", "A1", "B0", "B1")
                for field in ("input", "output", "residual")
            ]
            draft["tables"] = [
                {
                    "table_id": "paired-means",
                    "caption": "Original whole-interface means and changes.",
                    "after_section_id": "results",
                    "columns": ["Pair", "Reference (K)", "Comparison (K)", "Change (K)"],
                    "column_units": [None, "K", "K", "K"],
                    "numeric_columns": [1, 2, 3],
                    "evidence_ids": paired_ids,
                    "rows": [
                        [
                            f"Structure {pair}",
                            *[
                                "{{value:paired-" + pair + "-all-" + field + "}}"
                                for field in (
                                    "reference_mean",
                                    "comparison_mean",
                                    "difference_mean",
                                )
                            ],
                        ]
                        for pair in ("A", "B")
                    ],
                    "note": "Physical-area means; change = comparison minus reference.",
                },
                {
                    "table_id": "local-budget",
                    "caption": "Separate prescribed local energy budgets.",
                    "after_section_id": "results",
                    "columns": ["Case", "Input (W)", "Output (W)", "Remainder (W)"],
                    "column_units": [None, "W", "W", "W"],
                    "numeric_columns": [1, 2, 3],
                    "evidence_ids": budget_ids,
                    "rows": [
                        [
                            case,
                            *[
                                "{{value:budget-" + case + "-all-" + field + "}}"
                                for field in ("input", "output", "residual")
                            ],
                        ]
                        for case in ("A0", "A1", "B0", "B1")
                    ],
                    "note": "0 denotes reference, 1 comparison. Source and storage are zero; "
                    "remainder = input − output, not a measured lateral flux.",
                },
            ]
            draft["image_observations"]["thermal-budget"] = "author-provided"
            draft.setdefault("observation_notes", {})["thermal-budget"] = (
                "Example-author specification: both footprints cool while the larger "
                "remaining regions warm. Budget rows are separate constructed accounting."
            )
        write(path, draft)
    path = workspace / "manuscript-input.json"
    manifest = read(path)
    for section in manifest["spine"]["sections"]:
        if section["section_id"] == "results":
            section["required_figure_ids"] = ["thermal-budget"]
    write(path, manifest)


def run(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    study, diagnostics = create_materials(output / "materials")
    prepared = prepare_surface_workspace(study, output / "surface-workspace")
    workspace = attach_research_diagnostics(
        prepared, diagnostics, output / "workspace", combine=True, figure_id="thermal-budget"
    )
    write_host_drafts(workspace)
    candidate = build_research_workspace(workspace, output / "candidate")

    # Continue only in a separate author copy; raw materials and first candidate are unchanged.
    working = output / "author-working"
    shutil.copytree(candidate / "workspace", working)
    local = working / "sections/results"
    script = local / "figures/diagnostics/plot.py"
    text = script.read_text(encoding="utf-8")
    text = text.replace(
        "if __name__ == '__main__':",
        "# Example author style adjustment\nSTYLE.tick_pt = 8.5\n\nif __name__ == '__main__':",
    )
    script.write_text(text, encoding="utf-8")
    source = local / "sources/A1.npz"
    with np.load(source, allow_pickle=False) as data:
        arrays = {key: data[key].copy() for key in data.files}
    arrays["face_value"] += 1.0
    np.savez(source, **arrays)
    refreshed = build_research_workspace(working, output / "refreshed", baseline_dir=candidate)
    return refreshed / "manuscript.docx"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New output directory; never an author workspace")
    print(run(parser.parse_args().output))
