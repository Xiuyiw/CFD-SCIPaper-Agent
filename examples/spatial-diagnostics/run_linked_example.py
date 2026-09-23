"""Compare computed mean and spatial SD using existing synthetic wall records.

Recorded descriptive prose, not a model-generated manuscript or CFD validation.
No new plot is needed for these two scalar contrasts; use the companion field map.
"""

import argparse
import json
from pathlib import Path

from cfdpaper.analysis_suggestions import compile_analysis, prepare_analysis
from cfdpaper.publication.analysis_section import build_analysis_section
from cfdpaper.publication.section import assemble_section


def save(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return path


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    example = Path(__file__).parent
    materials = output / "materials"
    prepare_analysis(example / "inputs", materials)
    candidate = json.loads((example / "recorded/proposal.json").read_text(encoding="utf-8"))[
        "candidates"
    ][0]
    original = candidate["calculations"][0]
    candidate.update(
        presentation="table",
        presentation_reason="A compact table displays complementary mean and spread changes.",
        result_comparisons=[],
    )
    candidate["supporting_evidence"] = [
        item for item in candidate["supporting_evidence"] if item["id"] != "spatial-order"
    ]
    for name, field in (("mean-change", "weighted_mean"), ("spread-change", "weighted_std")):
        candidate["result_comparisons"].append(
            {
                "id": name,
                "reference": {
                    "calculation_id": original["id"],
                    "group": "Reference",
                    "field": field,
                },
                "comparison": {
                    "calculation_id": original["id"],
                    "group": "Modified",
                    "field": field,
                },
                "domain": original["domain"],
                "definition_source": "sources/method.md:L3-L10",
                "comparison_scope": original["comparison"]["scope"],
                "status": "supported",
            }
        )
        candidate["metrics"].append(
            {
                "id": name,
                "text": "Modified minus Reference: " + field,
                "result_ref": {
                    "calculation_id": name,
                    "group": "all",
                    "field": "difference",
                    "places": 3,
                },
            }
        )
    proposal = save(output / "proposal.json", {"candidates": [candidate]})
    compiled = compile_analysis(materials, proposal, candidate["id"], output / "compiled")
    writing = build_analysis_section(compiled, output / "section-input")
    identifiers = [
        "reference-mean",
        "modified-mean",
        "reference-sd",
        "modified-sd",
        "mean-change",
        "spread-change",
    ]
    draft = {
        "title": "Mean temperature and spatial variation",
        "paragraphs": [
            {
                "text": "The Modified field has a lower area-weighted mean "
                "({{value:modified-mean}} versus {{value:reference-mean}}), but greater spatial "
                "variation ({{value:modified-sd}} versus {{value:reference-sd}}). "
                "The signed changes are {{value:mean-change}} and {{value:spread-change}}, "
                "respectively ({{table:1}}). These complementary statistics distinguish the "
                "overall temperature level from its spatial uniformity; neither alone establishes "
                "a cooling-performance improvement or explains the transport mechanism.",
                "evidence_ids": identifiers + ["wall-definition", "physical-ceiling"],
                "figure_ids": [],
            }
        ],
        "captions": {},
        "image_observations": {},
        "evidence_notes": [],
        "tables": [
            {
                "table_id": "1",
                "caption": "Whole-wall statistics of prescribed analytical fields.",
                "after_section_id": candidate["id"],
                "columns": ["Quantity", "Reference", "Modified", "Signed change"],
                "rows": [
                    [
                        "Area-weighted mean",
                        "{{value:reference-mean}}",
                        "{{value:modified-mean}}",
                        "{{value:mean-change}}",
                    ],
                    [
                        "Spatial standard deviation",
                        "{{value:reference-sd}}",
                        "{{value:modified-sd}}",
                        "{{value:spread-change}}",
                    ],
                ],
                "evidence_ids": identifiers,
                "numeric_columns": [1, 2, 3],
                "column_widths_mm": [55, 35, 35, 35],
                "note": "Temperature differences and spatial standard deviations use K. "
                "Statistics describe the complete, shared synthetic wall, "
                "not measurement uncertainty.",
            }
        ],
    }
    return assemble_section(writing, save(output / "draft.json", draft), output / "section")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    print(run(parser.parse_args().output))
