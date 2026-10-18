"""Replay a disclosed example host's regional and signed-transfer research draft.

The fields and separate control-volume budget are constructed inputs, not solver
results. Product APIs calculate diagnostics, render figures and assemble the draft.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from cfdpaper.publication.research_workspace import (
    attach_research_diagnostics,
    build_research_workspace,
    prepare_surface_workspace,
)


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def create_materials(root):
    sources = root / "sources"
    sources.mkdir(parents=True)
    x, y = [0.0, 0.01, 0.03, 0.04], [0.0, 0.01, 0.02]
    vertices = np.array([[xi, yi, 0.0] for yi in y for xi in x])
    faces = [
        [4, row * 4 + col, row * 4 + col + 1, (row + 1) * 4 + col + 1, (row + 1) * 4 + col]
        for row in range(2)
        for col in range(3)
    ]
    areas = np.array([1, 2, 1, 1, 2, 1], dtype=float) * 1e-4
    fields = {
        "A": ([360, 350, 330, 340, 335, 325], [1e5, -4e4, 2e4, 6e4, -1e4, 2e4]),
        "B": ([345, 345, 360, 325, 350, 355], [8e4, -6e4, 3e4, 5e4, -2e4, 4e4]),
    }
    for case, (temperature, flux) in fields.items():
        np.savez(
            sources / f"{case}.npz",
            face_value=np.array(temperature, dtype=float),
            heat_flux=np.array(flux, dtype=float),
            area_m2=areas,
            x=np.tile([0.005, 0.02, 0.035], 2),
            y=np.repeat([0.005, 0.015], 3),
            z=np.zeros(6),
            vertices_m=vertices,
            faces_connectivity=np.array(faces).ravel(),
            face_starts=np.arange(6) * 5,
        )
    (sources / "budget.csv").write_text(
        "incoming,outgoing,source,storage\n100,85,5,10\n", encoding="utf-8"
    )
    (sources / "definition.md").write_text(
        "# Constructed diagnostic inputs\n\n"
        "These are prescribed static arrays, not a CFD solution or an experiment. "
        "Both cases use the same six rectangular faces on a 0.04 m by 0.02 m plane. "
        "Column widths are 0.01, 0.02, 0.01 m and both row heights are 0.01 m. "
        "Temperatures (K) and signed normal heat-flux densities (W/m2) are constant on "
        "each original face. Supplied face areas total 0.0008 m2. Positive heat flux "
        "enters the illustrated solid; negative heat flux leaves it. Temperatures and "
        "fluxes were prescribed separately, without a constitutive transport relation.\n\n"
        "The left region is x in [0,0.015] m and y in [0,0.02] m; its boundary crosses "
        "both wider middle-column faces. Exact polygon overlap fractions, recomputed "
        "from the saved geometry, weight each face's constant value. The complementary "
        "region covers the rest of the plane. This is not centroid assignment or "
        "interpolation of a temperature gradient within a face. Paired differences "
        "refer to the same physical faces in A and B. Strict exceedance at 345 and "
        "355 K is a distribution diagnostic. Population SD denotes spatial spread.\n\n"
        "budget.csv is a separate constructed control-volume accounting example: "
        "input=100 W, output=85 W, source=5 W, storage=10 W. Storage is retained "
        "because no steady-state assumption is supplied. Its residual is input + "
        "source - output - storage; this independent accounting example does not "
        "close or validate the prescribed surface temperature and flux fields.\n",
        encoding="utf-8",
    )
    study = {
        "study_id": "constructed-physical-diagnostics",
        "title": "Regional temperature redistribution and opposing heat transfers",
        "question": (
            "How can local cooling coexist with a higher overall mean, "
            "and what does a signed net transfer hide?"
        ),
        "time_support": (
            "Prescribed static arrays; separate budget retains its supplied storage term"
        ),
        "common_conditions": [
            "Same original six-face geometry and physical areas",
            "Same temperature and signed-flux association and units",
        ],
        "definition": {
            "source": "sources/definition.md",
            "text": (
                "Constructed face fields and a separate accounting example, "
                "with explicit spatial and sign definitions."
            ),
        },
        "domain": "Complete constructed 0.04 m by 0.02 m planar interface",
        "quantity": "Temperature",
        "unit": "K",
        "coordinate_unit": "m",
        "projection_axes": [0, 1],
        "thresholds": [345, 355],
        "exceedance_relation": "above",
        "arrays": {
            "values": "face_value",
            "weights": "area_m2",
            "vertices": "vertices_m",
            "connectivity": "faces_connectivity",
            "starts": "face_starts",
        },
        "cases": [
            {"id": case, "label": f"Case {case}", "source": f"sources/{case}.npz"}
            for case in fields
        ],
    }
    calculations = []
    for case in fields:
        common = {
            "source": f"sources/{case}.npz",
            "domain": "complete planar interface",
            "operation": "field_integral",
        }
        calculations.extend(
            [
                {
                    **common,
                    "id": f"region-{case}",
                    "columns": {"value": "face_value", "measure": "area_m2"},
                    "units": {"value": "K", "measure": "m2"},
                    "field_options": {
                        "association": "face",
                        "integrand": "weighted_mean",
                        "region_assignment": "polygon-clip",
                        "partition_complete": True,
                        "regions": [
                            {"id": "left", "bounds": {"x": [0, 0.015], "y": [0, 0.02]}},
                            {
                                "id": "rest",
                                "bounds": {"x": [0, 0.015], "y": [0, 0.02]},
                                "complement": True,
                            },
                        ],
                    },
                },
                {
                    **common,
                    "id": f"flux-{case}",
                    "columns": {"value": "heat_flux", "measure": "area_m2"},
                    "units": {"value": "W/m2", "measure": "m2"},
                    "field_options": {"association": "face", "integrand": "density"},
                },
            ]
        )
    calculations.extend(
        [
            {
                "id": "paired",
                "source": "sources/B.npz",
                "domain": "same original interface faces",
                "operation": "field_difference",
                "columns": {
                    "value": "face_value",
                    "measure": "area_m2",
                    "x": "x",
                    "y": "y",
                    "z": "z",
                },
                "units": {"value": "K", "measure": "m2", "x": "m", "y": "m", "z": "m"},
                "field_options": {"association": "face", "reference_source": "A.npz"},
            },
            {
                "id": "budget",
                "source": "sources/budget.csv",
                "domain": "separate constructed control volume",
                "operation": "energy_budget",
                "columns": {
                    "input": "incoming",
                    "output": "outgoing",
                    "source": "source",
                    "storage": "storage",
                },
                "units": dict.fromkeys(["input", "output", "source", "storage"], "W"),
                "field_options": {"association": "control_volume"},
            },
        ]
    )
    diagnostics = {
        "field_calculations": calculations,
        "mechanism_questions": [
            {
                "question": (
                    "Does lower temperature in one fixed region establish whole-domain cooling?"
                ),
                "diagnostics": ["region-A", "region-B", "paired"],
                "interpretation": (
                    "Compare exact area support and the complementary region, "
                    "then inspect the original field."
                ),
            },
            {
                "question": (
                    "Does reduced net heat transfer imply weaker positive-direction exchange?"
                ),
                "diagnostics": ["flux-A", "flux-B"],
                "interpretation": (
                    "Retain the positive and negative integrated terms "
                    "before interpreting their net."
                ),
            },
        ],
        "panels": [
            {
                "id": "regions",
                "kind": "regional",
                "title": "Fixed-region temperature and area support",
                "group_labels": {"left": "Left region", "rest": "Remaining region"},
                "series": [
                    {"calculation_id": f"region-{case}", "label": f"Case {case}"} for case in fields
                ],
            },
            {
                "id": "transfers",
                "kind": "signed_flux",
                "title": "Opposing heat transfers",
                "sign_convention": (
                    "Positive heat enters the illustrated solid; negative heat leaves it."
                ),
                "series": [
                    {"calculation_id": f"flux-{case}", "label": f"Case {case}"} for case in fields
                ],
            },
            {
                "id": "paired-response",
                "kind": "matched_difference",
                "title": "Original means and matched difference",
                "series": [{"calculation_id": "paired", "label": "B relative to A"}],
            },
        ],
    }
    save(root / "study.json", study)
    save(root / "diagnostics.json", diagnostics)
    return root / "study.json", root / "diagnostics.json"


def write_recorded_host_drafts(workspace):
    """Replay provided prose; each numerical token is resolved by the product."""
    paragraphs = {
        "methods": [
            (
                "Two prescribed temperature and signed heat-flux fields share the same six-face "
                "planar interface. Their unequal physical face areas and original vertex "
                "connectivity are retained. The left region ends at x = 0.015 m, crossing "
                "the wider middle faces. Polygon intersections determine the overlapping "
                "area assigned to each region, while each original face value remains "
                "constant. The remaining region is its complement. Paired differences "
                "use the same physical faces and report Case B minus Case A.",
                ["study-definition"],
                [],
            ),
            (
                "Regional temperatures use physical area weighting. A region's domain share "
                "describes geometric support rather than heat allocation. Signed heat-flux "
                "density is multiplied by face area once; positive and negative contributions "
                "are summed separately before forming the net. Positive values denote heat "
                "entering the illustrated solid. A separate control-volume example retains "
                "its supplied storage term and computes input + source - output - storage. "
                "All arrays and this budget are constructed inputs; no transport model "
                "connects the prescribed temperatures to the prescribed heat fluxes.",
                ["study-definition"],
                [],
            ),
        ],
        "results": [
            (
                "The overall area-weighted temperature rises from {{value:A-mean}} in Case A "
                "to {{value:B-mean}} in Case B ({{table:surface-summary}}). The original "
                "maps in {{figure:field}} localize cooling toward the left side and "
                "warming toward the right. The exact area distributions in "
                "{{figure:distribution}} provide the complementary whole-domain view.",
                ["A-mean", "B-mean", "study-definition"],
                ["field", "distribution"],
            ),
            (
                "The left-region mean nevertheless falls from "
                "{{value:region-A-left-weighted_mean}} "
                "to {{value:region-B-left-weighted_mean}}, whereas the remaining-region mean "
                "rises from {{value:region-A-rest-weighted_mean}} to "
                "{{value:region-B-rest-weighted_mean}} ({{figure:regions}}). The left region "
                "occupies {{value:region-A-left-measure}} of the total "
                "{{value:region-A-all-measure}}. The comparison therefore distinguishes "
                "local cooling from a lower overall mean; the regions are fixed in space.",
                [
                    "region-A-left-weighted_mean",
                    "region-B-left-weighted_mean",
                    "region-A-rest-weighted_mean",
                    "region-B-rest-weighted_mean",
                    "region-A-left-measure",
                    "region-A-all-measure",
                ],
                ["regions"],
            ),
            (
                "Positive-direction transfer is {{value:flux-A-all-positive}} in Case A and "
                "{{value:flux-B-all-positive}} in Case B. Negative-direction transfer "
                "changes from {{value:flux-A-all-negative}} to {{value:flux-B-all-negative}}, "
                "reducing the net from {{value:flux-A-all-net}} to {{value:flux-B-all-net}} "
                "({{figure:transfers}}). Thus the smaller net reflects stronger opposing "
                "exchange in these inputs rather than reduced positive transfer.",
                [
                    "flux-A-all-positive",
                    "flux-B-all-positive",
                    "flux-A-all-negative",
                    "flux-B-all-negative",
                    "flux-A-all-net",
                    "flux-B-all-net",
                ],
                ["transfers"],
            ),
            (
                "The matched mean difference is {{value:paired-all-difference_mean}}, "
                "read alongside both original means in {{figure:paired-response}}. "
                "The separate budget has a storage rate of {{value:budget-all-storage}} "
                "and a residual of {{value:budget-all-residual}} ({{table:budget-summary}}). "
                "Its values are not an energy closure for the surface-field example.",
                ["paired-all-difference_mean", "budget-all-storage", "budget-all-residual"],
                ["paired-response"],
            ),
        ],
        "discussion": [
            (
                "The apparent disagreement between local and global temperature is resolved "
                "by spatial support: the left region cools, but warming over the larger "
                "remaining region raises the domain mean. The fixed-region means quantify "
                "the two contributions without treating a distribution curve as a "
                "pointwise map. Moving the region with an imposed heat source would answer "
                "a different question and would require a separately declared comparison.",
                [
                    "region-A-left-weighted_mean",
                    "region-B-left-weighted_mean",
                    "region-A-rest-weighted_mean",
                    "region-B-rest-weighted_mean",
                    "study-definition",
                ],
                [],
            ),
            (
                "The signed-transfer decomposition rejects the explanation that a smaller "
                "net necessarily means weaker inward transport: positive transfer is "
                "unchanged, while the outward contribution grows in magnitude. This "
                "accounting distinction is established by the supplied fluxes. It does "
                "not identify a conductivity change, altered coolant mixing or a causal "
                "relation to the temperature field, because no governing transport "
                "solution generated these prescribed arrays. The paired difference is "
                "a derived reading of the original fields, not additional independent evidence.",
                [
                    "flux-A-all-positive",
                    "flux-B-all-positive",
                    "flux-A-all-negative",
                    "flux-B-all-negative",
                    "study-definition",
                ],
                [],
            ),
        ],
        "conclusion": [
            (
                "The constructed example combines lower left-region temperature with a "
                "higher domain mean, {{value:B-mean}} versus {{value:A-mean}}. Exact "
                "region overlap and complementary-area weighting explain this spatial "
                "redistribution. Retaining opposing flux contributions also shows why "
                "a net transfer can fall from {{value:flux-A-all-net}} to "
                "{{value:flux-B-all-net}} without reduced positive-direction transfer. "
                "These are descriptive and accounting results of the declared inputs.",
                ["A-mean", "B-mean", "flux-A-all-net", "flux-B-all-net", "study-definition"],
                [],
            ),
        ],
    }
    mapping = json.loads((workspace / "drafts.json").read_text(encoding="utf-8"))
    for sid, filename in mapping.items():
        path = workspace / filename
        draft = json.loads(path.read_text(encoding="utf-8"))
        draft["paragraphs"] = [
            {"text": text, "evidence_ids": ids, "figure_ids": figures}
            for text, ids, figures in paragraphs[sid]
        ]
        if sid == "results":
            fields = ["input", "output", "source", "storage", "residual"]
            draft["tables"].append(
                {
                    "table_id": "budget-summary",
                    "caption": "Separate constructed control-volume accounting.",
                    "after_section_id": "results",
                    "numeric_columns": list(range(1, 6)),
                    "columns": ["Example", "Input", "Output", "Source", "Storage", "Residual"],
                    "rows": [
                        [
                            "Separate budget",
                            *["{{value:budget-all-" + field + "}}" for field in fields],
                        ]
                    ],
                    "evidence_ids": [f"budget-all-{field}" for field in fields],
                    "note": (
                        "Residual = input + source − output − storage; "
                        "not a surface-field energy balance."
                    ),
                }
            )
        save(path, draft)
    path = workspace / "manuscript-input.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["spine"]["central_claim_id"] = "B-mean"
    for section in manifest["spine"]["sections"]:
        if section["section_id"] == "results":
            section["required_claim_ids"] = [
                "A-mean",
                "B-mean",
                "region-A-left-weighted_mean",
                "region-B-left-weighted_mean",
                "flux-A-all-net",
                "flux-B-all-net",
            ]
            section["required_figure_ids"] = [
                "field",
                "distribution",
                "regions",
                "transfers",
                "paired-response",
            ]
            section["purpose"] = (
                "Resolve fixed-region versus global temperature and opposing signed transfers."
            )
    save(path, manifest)


def run(output, *, prepare_only=False):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    study, diagnostics = create_materials(output / "materials")
    initial = prepare_surface_workspace(study, output / "surface-workspace")
    workspace = attach_research_diagnostics(initial, diagnostics, output / "workspace")
    if prepare_only:
        return workspace
    write_recorded_host_drafts(workspace)
    return build_research_workspace(workspace, output / "candidate")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New output directory")
    parser.add_argument("--prepare-only", action="store_true", help="Leave host drafts empty")
    args = parser.parse_args()
    print(run(args.output, prepare_only=args.prepare_only))
