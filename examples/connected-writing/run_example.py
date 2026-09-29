"""Recorded three-section writing replay over a synthetic mixed-unit long table.

No model call, solver, experimental validation or literature claim is made.
"""

import argparse
import json
from pathlib import Path

from cfdpaper.analysis_suggestions import compile_analysis, prepare_analysis
from cfdpaper.publication.analysis_section import build_analysis_section
from cfdpaper.publication.manuscript import (
    assemble_manuscript,
    prepare_manuscript,
    prepare_writing_context,
)
from cfdpaper.publication.section import export_section_docx


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def proposal():
    calculations, metrics = [], []
    for quantity, metric, unit, domain, kind in (
        (
            "temperature",
            "wall_temperature",
            "K",
            "Whole-wall area-weighted mean temperature",
            "absolute-temperature",
        ),
        (
            "pressure",
            "pressure_drop",
            "Pa",
            "Device inlet-to-outlet pressure difference",
            "ordinary",
        ),
    ):
        common = {
            "source": "sources/metrics.csv",
            "columns": {"value": "value"},
            "units": {"value": unit},
            "quantity_kind": kind,
            "domain": domain,
            "row_filters": {"metric": metric, "domain": "device"},
            "unit_column": "unit",
            "definition_source": {"path": "sources/method.md", "locator": "L1-L5"},
            "comparison": {"status": "supported", "scope": "Same prescribed synthetic basis"},
            "member_id": ["record_id"],
            "interpretation_limits": ["Prescribed scalars, not a solved or validated CFD field."],
        }
        calculations.extend(
            [
                {
                    **common,
                    "id": quantity,
                    "operation": "scalar_select",
                    "group_by": "case",
                    "expected_groups": ["base", "modified"],
                },
                {
                    **common,
                    "id": quantity + "-pair",
                    "operation": "paired_change",
                    "paired_selector": {
                        "pair_by": "case",
                        "reference": "base",
                        "comparison": "modified",
                    },
                },
            ]
        )
        for case in ("base", "modified"):
            metrics.append(
                {
                    "id": quantity + "-" + case,
                    "text": domain + ": " + case,
                    "result_ref": {
                        "calculation_id": quantity,
                        "group": case,
                        "field": "value",
                        "places": 2,
                    },
                }
            )
        metrics.append(
            {
                "id": quantity + "-change",
                "text": "Modified minus base: " + domain,
                "result_ref": {
                    "calculation_id": quantity + "-pair",
                    "group": "all",
                    "field": "difference",
                    "places": 2,
                },
            }
        )
    return {
        "candidates": [
            {
                "id": "results",
                "title": "2. Coupled scalar responses",
                "question": "Do lower mean temperature and lower pressure drop coincide?",
                "rationale": "Compare thermal level and hydraulic cost with distinct units.",
                "presentation": "table",
                "presentation_reason": "A compact two-row table is sufficient.",
                "calculations": calculations,
                "metrics": metrics,
                "interpretation_limits": [
                    "No spatial field or controlled mechanism test is supplied."
                ],
            }
        ]
    }


def recorded_drafts():
    common = {"captions": {}, "image_observations": {}, "evidence_notes": []}
    methods = {
        **common,
        "title": "1. Synthetic comparison definitions",
        "paragraphs": [
            {
                "text": "Recorded tutorial: all values are prescribed synthetic scalars, not CFD "
                "or experimental results. Temperature denotes the whole-wall area-weighted "
                "mean; pressure drop denotes the device inlet-to-outlet difference. The "
                "reference and modified cases share the stipulated wall domain, heat input "
                "and volumetric flow. Differences are modified minus reference. The long "
                "table retains separate metric and unit fields; no temperature percentage "
                "or spatial distribution is inferred.",
                "evidence_ids": ["definitions"],
                "figure_ids": [],
            }
        ],
    }
    results = {
        **common,
        "title": "2. Coupled scalar responses",
        "paragraphs": [
            {
                "text": "The wall-mean temperatures (K) are {{value:temperature-base}} and "
                "{{value:temperature-modified}} for the reference and modified cases, "
                "respectively. The modified case has the lower mean temperature.",
                "shared_unit": "K",
                "evidence_ids": ["temperature-base", "temperature-modified"],
                "figure_ids": [],
            },
            {
                "text": "Pressure drops (Pa) are {{value:pressure-base}} and "
                "{{value:pressure-modified}}, respectively. Thus the lower mean "
                "temperature coincides with a larger hydraulic pressure requirement "
                "({{table:1}}), rather than a simultaneous reduction of both responses.",
                "shared_unit": "Pa",
                "evidence_ids": ["pressure-base", "pressure-modified"],
                "figure_ids": [],
            },
            {
                "text": "The corresponding signed changes are {{value:temperature-change}} "
                "and {{value:pressure-change}}. These summarize the same two contrasts "
                "and are not additional independent mechanism evidence.",
                "evidence_ids": ["temperature-change", "pressure-change"],
                "figure_ids": [],
            },
        ],
        "tables": [
            {
                "table_id": "1",
                "caption": "Prescribed synthetic device responses.",
                "after_section_id": "results",
                "columns": ["Response", "Reference", "Modified"],
                "rows": [
                    [
                        "Wall-mean temperature",
                        "{{value:temperature-base}}",
                        "{{value:temperature-modified}}",
                    ],
                    ["Pressure drop", "{{value:pressure-base}}", "{{value:pressure-modified}}"],
                ],
                "evidence_ids": [
                    "temperature-base",
                    "temperature-modified",
                    "pressure-base",
                    "pressure-modified",
                ],
                "numeric_columns": [1, 2],
                "column_widths_mm": [80, 35, 35],
            }
        ],
    }
    discussion = {
        **common,
        "title": "3. Interpretation of the coupled response",
        "paragraphs": [
            {
                "text": "The temperature change of {{value:temperature-change}} must be read "
                "alongside the pressure-drop change of {{value:pressure-change}}. At the "
                "stipulated common volumetric flow, a higher pressure drop implies a "
                "higher hydraulic power requirement. Lower wall-mean temperature therefore "
                "does not by itself establish a net design advantage. The supplied scalars "
                "cannot identify whether the thermal change arises from redistribution "
                "or altered local transfer; a shared-scale wall field and relevant local "
                "transport evidence would distinguish these explanations. The present "
                "comparison establishes a coupled response, not its causal mechanism.",
                "evidence_ids": ["temperature-change", "pressure-change"],
                "figure_ids": [],
            }
        ],
    }
    return {"methods": methods, "results": results, "discussion": discussion}


def run(output):
    """Create a fresh portable candidate and DOCX; never overwrite an existing run."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    raw = output / "raw"
    raw.mkdir()
    (raw / "metrics.csv").write_text(
        "record_id,case,metric,domain,value,unit\n"
        "t-base,base,status,device,recorded,text\n"
        "t-base,base,wall_temperature,device,315,K\n"
        "p-base,base,pressure_drop,device,100,Pa\n"
        "t-modified,modified,wall_temperature,device,310.5,K\n"
        "p-modified,modified,pressure_drop,device,125,Pa\n",
        encoding="utf-8",
    )
    (raw / "method.md").write_text(
        "These are prescribed synthetic records for software demonstration, not CFD data.\n"
        "wall_temperature is whole-wall area-weighted mean absolute temperature in K.\n"
        "pressure_drop is device inlet-to-outlet pressure difference in Pa.\n"
        "The base and modified cases stipulate identical wall domain, heat input and flow.\n"
        "The shared flow is volumetric; differences are modified minus base, without ratios.\n",
        encoding="utf-8",
    )
    materials = output / "materials"
    prepare_analysis(raw, materials)
    compiled = compile_analysis(
        materials, save(output / "proposal.json", proposal()), "results", output / "compiled"
    )
    results = build_analysis_section(compiled, output / "section-entry")
    definitions = {
        "id": "definitions",
        "kind": "observation",
        "text": "Definitions and stipulated comparison conditions",
        "source": "sources/method.md:L1-L5",
    }
    for sid, title, evidence, sources, ids in (
        (
            "methods",
            "1. Synthetic comparison definitions",
            [definitions],
            ["sources/method.md"],
            ["definitions"],
        ),
        (
            "discussion",
            "3. Interpretation of the coupled response",
            [],
            [],
            ["temperature-change", "pressure-change"],
        ),
    ):
        save(
            results / f"{sid}-input.json",
            {
                "section_id": sid,
                "title": title,
                "question": title,
                "figures": [],
                "evidence": evidence,
                "source_files": sources,
                "duties": [{"purpose": title, "evidence_ids": ids, "figure_ids": []}],
            },
        )
    entries = [
        {"section_id": "methods", "input": "section-entry/writing/methods-input.json"},
        {
            "section_id": "results",
            "input": "section-entry/writing/input.json",
            "depends_on": ["methods"],
        },
        {
            "section_id": "discussion",
            "input": "section-entry/writing/discussion-input.json",
            "depends_on": ["methods", "results"],
            "evidence_bindings": {
                key: "results/" + key for key in ("temperature-change", "pressure-change")
            },
        },
    ]
    drafts = recorded_drafts()
    required = {
        "methods": ["definitions"],
        "results": [metric["id"] for metric in proposal()["candidates"][0]["metrics"]],
        "discussion": ["temperature-change", "pressure-change"],
    }
    manifest = save(
        output / "manuscript-input.json",
        {
            "title": "Recorded synthetic example: thermal response and hydraulic cost",
            "context": "Does a lower wall-mean temperature coincide with lower pressure drop? "
            "Recorded drafts demonstrate software wiring, not automatic scientific writing.",
            "spine": {
                "topic_id": "synthetic-connected",
                "central_claim_id": "temperature-change",
                "sections": [
                    {
                        "section_id": sid,
                        "role": sid,
                        "title": draft["title"],
                        "purpose": draft["title"],
                        "required_claim_ids": required[sid],
                    }
                    for sid, draft in drafts.items()
                ],
            },
            "sections": entries,
        },
    )
    recorded = output / "recorded"
    recorded.mkdir()
    for sid, draft in drafts.items():
        save(recorded / f"{sid}.json", draft)
    mapping = {sid: f"{sid}.json" for sid in drafts}
    all_drafts = save(recorded / "drafts.json", mapping)
    package = prepare_manuscript(manifest, output / "workspace")
    contexts = output / "contexts"
    contexts.mkdir()
    for target, dependencies in (("results", ["methods"]), ("discussion", ["methods", "results"])):
        partial = save(
            recorded / f"before-{target}.json", {sid: mapping[sid] for sid in dependencies}
        )
        prepare_writing_context(package, target, contexts / target, drafts_path=partial)
    candidate = assemble_manuscript(package, all_drafts, output / "manuscript")
    export_section_docx(candidate, output / "manuscript.docx", layout="near-reference")
    return candidate


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Fresh output directory")
    print(run(parser.parse_args().output))
