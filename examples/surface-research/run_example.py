"""Build a synthetic face-field study and a supplied four-section research draft.

This is a reproducible workflow example, not CFD data or a new host/model trial.
The product calculates, plots and assembles; the prose below is the example host's input.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from cfdpaper.publication.research_workspace import (
    build_research_workspace,
    prepare_surface_workspace,
)


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def create_materials(root):
    """Prescribe six unequal rectangular faces; do not calculate manuscript metrics here."""
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
        "A": [320.0, 330.0, 340.0, 330.0, 340.0, 350.0],
        "B": [310.0, 320.0, 335.0, 320.0, 335.0, 370.0],
    }
    for case, values in fields.items():
        np.savez(
            sources / f"{case}.npz",
            face_value=values,
            area_m2=areas,
            vertices_m=vertices,
            faces_connectivity=np.array(faces).ravel(),
            face_starts=np.arange(6) * 5,
        )
    (sources / "definition.md").write_text(
        "# Synthetic surface definition\n\n"
        "These are prescribed piecewise-constant fields, not solver or experimental results.\n"
        "Both cases cover the same planar 0.04 m by 0.02 m rectangle at z = 0.\n"
        "Rows advance in y; faces within a row advance in x. The column widths are\n"
        "0.01, 0.02 and 0.01 m; each row is 0.01 m tall. Supplied areas are exact\n"
        "rectangle areas: [1, 2, 1, 1, 2, 1] x 10^-4 m^2, totaling 8 x 10^-4 m^2.\n"
        "Case A temperatures are [320, 330, 340, 330, 340, 350] K;\n"
        "Case B temperatures are [310, 320, 335, 320, 335, 370] K.\n"
        "Each value is constant over its associated face. There are no point values,\n"
        "time samples, boundary conditions, transport model or uncertainty estimates.\n"
        "The mean and population SD use physical face area. Exceedance is the sum of\n"
        "areas whose temperature is strictly above the declared threshold, divided by\n"
        "total area. Equality is excluded. Thresholds are distribution diagnostics.\n"
        "The polygon map and area distribution are complementary views of this same field.\n",
        encoding="utf-8",
    )
    study = {
        "study_id": "synthetic-surface",
        "title": "Synthetic surface-temperature comparison",
        "question": "Does a lower area-weighted mean also imply a more uniform surface field?",
        "time_support": "Prescribed static synthetic fields; no physical time support",
        "common_conditions": [
            "Same complete planar domain and six-face partition",
            "Same physical face areas and piecewise-constant association",
        ],
        "definition": {
            "source": "sources/definition.md",
            "text": "Prescribed face temperatures in K with exact rectangular face areas in m^2.",
        },
        "domain": "Complete synthetic 0.04 m by 0.02 m planar surface",
        "quantity": "Temperature",
        "unit": "K",
        "coordinate_unit": "m",
        "projection_axes": [0, 1],
        "thresholds": [335.0, 350.0],
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
    save(root / "study.json", study)
    return root / "study.json"


def write_example_drafts(workspace):
    """Supply fixed, disclosed host prose using the product's existing local evidence IDs."""
    paragraphs = {
        "methods": [
            (
                "This illustrative study compares two prescribed synthetic temperature fields "
                "on the same planar surface. Six rectangular faces retain their original "
                "connectivity, face-associated values and unequal physical areas. The values "
                "are constant within each face. These inputs are a constructed mathematical "
                "example, not a CFD simulation or an experiment; no transport model or "
                "physical time dependence is assigned.",
                ["study-definition"],
                [],
            ),
            (
                "The area-weighted mean is the sum of face temperature times face area divided "
                "by total area. The population standard deviation is the square root of the "
                "area-weighted squared deviation from that mean. It describes spatial spread, "
                "not uncertainty in the mean. The exceedance fraction sums only faces strictly "
                "above a threshold and divides by total area, excluding equality. Readings at "
                "{{value:threshold-1}} and {{value:threshold-2}} are reported as percentages. "
                "These thresholds sample the distribution; they are not safety limits. The "
                "field maps use the original polygons and a common color scale, while the "
                "distribution retains exact steps without interpolation.",
                ["study-definition", "threshold-1", "threshold-2"],
                [],
            ),
        ],
        "results": [
            (
                "The area-weighted mean decreases from {{value:A-mean}} in Case A to "
                "{{value:B-mean}} in Case B, whereas the spatial standard deviation increases "
                "from {{value:A-std}} to {{value:B-std}} ({{table:surface-summary}}). Thus the "
                "lower mean does not imply a more uniform field. In {{figure:field}}, the "
                "lower temperatures over most of Case B coexist with a hotter upper-right "
                "face. The maps preserve location and face size, which are not encoded by "
                "a mean alone.",
                ["A-mean", "B-mean", "A-std", "B-std", "study-definition"],
                ["field"],
            ),
            (
                "The area above {{value:threshold-1}} changes from {{value:A-exceedance-1}} "
                "to {{value:B-exceedance-1}}, while the area above {{value:threshold-2}} "
                "changes from {{value:A-exceedance-2}} to {{value:B-exceedance-2}}. The "
                "opposing comparisons at these thresholds are resolved by the crossing "
                "distributions in {{figure:distribution}}. A single threshold would hide "
                "part of this difference. Each step reflects a finite face-area contribution, "
                "not a continuous thermal response inferred between simulated cases.",
                [
                    "threshold-1",
                    "threshold-2",
                    "A-exceedance-1",
                    "B-exceedance-1",
                    "A-exceedance-2",
                    "B-exceedance-2",
                ],
                ["distribution"],
            ),
        ],
        "discussion": [
            (
                "The combined reading separates average level from spatial concentration. "
                "Area weighting matters because the wider faces contribute twice the area "
                "of the narrower faces. The higher Case B spread, {{value:B-std}} compared "
                "with {{value:A-std}}, is compatible with its lower mean: the warmest facet "
                "need not dominate the total-area average. The map localizes this facet; "
                "the exceedance distribution states how much area lies above each temperature. "
                "They are complementary representations of the same field, not independent "
                "evidence for a causal mechanism.",
                ["study-definition", "A-std", "B-std"],
                [],
            ),
            (
                "Because the fields were prescribed, the contrast does not identify a heat "
                "transfer mechanism, improved design, converged solution or validated model. "
                "A real application would need the actual boundary conditions, common spatial "
                "and time support, solver and mesh evidence, and relevant physical validation. "
                "The present example establishes only the descriptive contrast supported by "
                "the supplied arrays. A changed source or threshold requires revisiting this "
                "interpretation even when every bound number has refreshed successfully.",
                ["study-definition"],
                [],
            ),
        ],
        "conclusion": [
            (
                "In these synthetic fields, Case B has a lower mean temperature "
                "({{value:B-mean}} versus {{value:A-mean}}) but a larger spatial standard "
                "deviation ({{value:B-std}} versus {{value:A-std}}). Mean level, spatial "
                "location and threshold-dependent area therefore answer different questions. "
                "The original-face map, exact area distribution and bound summary table "
                "provide a consistent descriptive comparison, without establishing a "
                "physical performance ranking.",
                ["study-definition", "A-mean", "B-mean", "A-std", "B-std"],
                [],
            )
        ],
    }
    mapping = json.loads((workspace / "drafts.json").read_text(encoding="utf-8"))
    for sid, name in mapping.items():
        path = workspace / name
        draft = json.loads(path.read_text(encoding="utf-8"))
        draft["paragraphs"] = [
            {"text": text, "evidence_ids": evidence, "figure_ids": figures}
            for text, evidence, figures in paragraphs[sid]
        ]
        if sid == "results":
            draft["captions"] = {
                "field": "Prescribed synthetic face temperatures on the common surface. "
                "Original polygons share one temperature scale; no interpolated field is used.",
                "distribution": "Exact area-exceedance distributions for the prescribed fields. "
                "Markers identify strict exceedance at {{value:threshold-1}} and "
                "{{value:threshold-2}}; equality is excluded. These are diagnostic thresholds.",
            }
            # A replay does not inspect each new render on behalf of its user.
            draft["image_observations"] = {key: "not-viewed" for key in draft["captions"]}
            draft["tables"][0]["caption"] = "Area-weighted observations of the synthetic fields."
            draft["tables"][0]["note"] = (
                "Population SD describes spatial spread. Area fractions use strict exceedance."
            )
        save(path, draft)
    # The host selects the actual argument; the product's scope placeholder is not a finding.
    path = workspace / "manuscript-input.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["spine"]["central_claim_id"] = "B-std"
    for section in manifest["spine"]["sections"]:
        if section["section_id"] == "results":
            section["required_claim_ids"] = ["A-mean", "B-mean", "A-std", "B-std"]
            section["purpose"] = "Distinguish average level from spatial concentration."
    save(path, manifest)


def run(output, *, prepare_only=False):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    study = create_materials(output / "materials")
    workspace = prepare_surface_workspace(study, output / "workspace")
    if prepare_only:
        return workspace
    write_example_drafts(workspace)
    return build_research_workspace(workspace, output / "candidate")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="New directory; existing content is never replaced"
    )
    parser.add_argument(
        "--prepare-only", action="store_true", help="Leave host draft templates empty"
    )
    arguments = parser.parse_args()
    print(run(arguments.output, prepare_only=arguments.prepare_only))
