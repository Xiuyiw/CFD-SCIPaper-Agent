"""Replay a clearly labelled synthetic host choice through the real public APIs.

For a new project the host writes the proposal and draft after reading materials;
the recorded responses below make installation and output reproducible offline.
"""

import argparse
import json
from pathlib import Path

from cfdpaper.analysis_suggestions import compile_analysis, prepare_analysis
from cfdpaper.publication.analysis_section import build_analysis_section
from cfdpaper.publication.section import assemble_section, export_section_docx


def run(output: Path, *, pdf=False, presentation="table"):
    if presentation not in {"table", "plot"}:
        raise ValueError("Example presentation must be table or plot")
    source = Path(__file__).with_name("inputs")
    if output.exists():
        raise FileExistsError(f"Use a new example output directory: {output}")
    prepare_analysis(source, output / "materials", question="Distinguish rate from mean flux")
    candidate = {
        "id": "area-flux",
        "title": "Area and transfer intensity",
        "question": "Does the larger integral imply higher transfer per unit area?",
        "rationale": "Separate wetted-area change from mean transport intensity.",
        "presentation": presentation,
        "presentation_reason": (
            "A compact table puts area, integrated heat rate and mean flux side by side "
            "for the two configurations; six values are enough to expose the relationship."
            if presentation == "table"
            else "Demonstrate the existing discrete renderer with separate quantity axes; "
            "the compact table is the preferred presentation for this small comparison."
        ),
        "interpretation_limits": ["Synthetic example; the identity does not establish causality."],
        "calculations": [
            {
                "id": "wall",
                "source": "sources/regions.csv",
                "operation": "partition",
                "columns": {"area": "area [m2]", "rate": "rate [W]"},
                "units": {"area": "m2", "rate": "W"},
                "group_by": "case",
                "domain": "Non-overlapping complete wall partition; heat entering coolant positive",
                "definition_source": {"path": "sources/method.md", "locator": "L2-L4"},
                "comparison": {"status": "supported", "scope": "Geometry at common boundaries"},
                "member_id": ["region"],
                "expected_members": [["lower"], ["upper"]],
                "expected_groups": ["Reference", "Modified"],
                "interpretation_limits": ["Does not establish a local heat-transfer coefficient."],
            }
        ],
        "metrics": [
            {
                "id": f"{field}-{group}",
                "text": f"{field} for {group}",
                "result_ref": {
                    "calculation_id": "wall",
                    "group": group,
                    "field": field,
                    "places": 2,
                },
            }
            for field in ("area", "rate", "mean_flux")
            for group in ("Reference", "Modified")
        ],
    }
    proposal = output / "recorded-host-proposal.json"
    proposal.write_text(json.dumps({"candidates": [candidate]}, indent=2), encoding="utf-8")
    payload = compile_analysis(output / "materials", proposal, "area-flux", output / "compiled")
    writing = build_analysis_section(payload, output / "section-input")
    data = json.loads((writing / "input.json").read_text(encoding="utf-8"))
    reference = (
        "{{table:1}}" if presentation == "table" else "{{figure:1}}, {{figure:2}} and {{figure:3}}"
    )
    draft = {
        "title": candidate["title"],
        "paragraphs": [
            {
                "text": "The modified configuration has a larger wetted area "
                "({{value:area-Modified}} compared with {{value:area-Reference}}) "
                "and carries a larger integrated heat rate "
                "({{value:rate-Modified}} compared with {{value:rate-Reference}}), "
                "yet its area-averaged heat flux is lower "
                "({{value:mean_flux-Modified}} versus {{value:mean_flux-Reference}}; "
                + reference
                + "). The increase in total "
                "transfer therefore does not imply intensified transfer per unit area. "
                "For this synthetic partition, the larger wetted area accommodates the "
                "higher integral despite the lower average flux. A transport-mechanism "
                "explanation would require flow or thermal-field evidence beyond this identity.",
                "evidence_ids": [e["id"] for e in data["evidence"]],
                "figure_ids": [f["id"] for f in data["figures"]],
            }
        ],
        "captions": (
            {
                "1": "Complete wetted-wall area for the two synthetic configurations.",
                "2": "Integrated heat rate for the two synthetic configurations.",
                "3": "Heat rate divided by the corresponding complete wetted-wall area.",
            }
            if presentation == "plot"
            else {}
        ),
        "image_observations": {f["id"]: "not-viewed" for f in data["figures"]},
        "evidence_notes": ["Recorded demonstration response, not an autonomous-host benchmark."],
    }
    if presentation == "table":
        draft["tables"] = [
            {
                "table_id": "1",
                "caption": "Wetted-wall area and heat transfer for the synthetic configurations.",
                "after_section_id": data["section_id"],
                "columns": [
                    "Configuration",
                    "Wetted area",
                    "Integrated heat rate",
                    "Mean heat flux",
                ],
                "rows": [
                    [
                        group,
                        *[
                            f"{{{{value:{field}-{group}}}}}"
                            for field in ("area", "rate", "mean_flux")
                        ],
                    ]
                    for group in ("Reference", "Modified")
                ],
                "evidence_ids": [metric["id"] for metric in candidate["metrics"]],
                "column_widths_mm": [32, 33, 45, 50],
                "numeric_columns": [1, 2, 3],
                "note": "The complete wall comprises the non-overlapping lower and upper "
                "regions. Heat entering the coolant is positive; mean heat flux is the "
                "integrated heat rate divided by wetted area.",
            }
        ]
    draft_path = output / "recorded-host-draft.json"
    draft_path.write_text(json.dumps(draft, indent=2), encoding="utf-8")
    section = assemble_section(writing, draft_path, output / "section")
    docx = export_section_docx(section, output / "section.docx", layout="near-reference")
    if pdf:
        from cfdpaper.publication.preview import preview_docx

        preview_docx(docx)
    return docx


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pdf", action="store_true", help="Optional LibreOffice preview")
    parser.add_argument(
        "--presentation",
        choices=("table", "plot"),
        default="table",
        help="Compact native table (default), or existing discrete comparison plots",
    )
    args = parser.parse_args()
    print(run(args.output, pdf=args.pdf, presentation=args.presentation))
