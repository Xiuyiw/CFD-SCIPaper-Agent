"""Recorded scientific-text replay: bound JSON methods and paired observation contrasts."""

from __future__ import annotations

import argparse
import ast
import json
import runpy
import shutil
from pathlib import Path

from cfdpaper.analysis_suggestions import compile_analysis, prepare_analysis
from cfdpaper.publication.analysis_section import build_analysis_section
from cfdpaper.publication.manuscript import assemble_manuscript
from cfdpaper.publication.manuscript_seed import prepare_manuscript_seed
from cfdpaper.publication.section import export_section_docx

EXAMPLE = Path(__file__).resolve().parent


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def proposal():
    common = {
        "source": "sources/temperatures.csv",
        "columns": {
            "value": "model_K",
            "reference": "reference_K",
            "lower": "lower_K",
            "upper": "upper_K",
        },
        "units": {key: "K" for key in ("value", "reference", "lower", "upper")},
        "quantity_kind": "absolute-temperature",
        "reference_kind": "declared-bound",
        "domain": "Heated/rear observations at the same stipulated 5 s state",
        "member_id": ["case", "side"],
        "definition_source": {"path": "sources/method.md", "locator": "L2-L6"},
        "comparison": {
            "status": "supported",
            "scope": "Paired same-state illustrative observations",
        },
        "interpretation_limits": [
            "Invented endpoints are not confidence intervals or model validation."
        ],
    }
    absolute = {
        **common,
        "id": "absolute",
        "operation": "reference_range",
        "group_by": "observation",
        "expected_groups": ["A-heated", "A-rear", "B-heated", "B-rear"],
    }
    contrast = {
        **common,
        "id": "contrast",
        "operation": "paired_reference_change",
        "group_by": "case",
        "paired_selector": {"pair_by": "side", "reference": "rear", "comparison": "heated"},
        "expected_groups": ["A", "B"],
    }
    metrics = []
    for cid, groups, fields in (
        ("absolute", absolute["expected_groups"], ["value", "reference_value", "difference"]),
        ("contrast", ["A", "B"], ["value", "reference_value", "difference", "outside_distance"]),
    ):
        for group in groups:
            for field in fields:
                metrics.append(
                    {
                        "id": f"{cid}-{group}-{field}",
                        "text": f"{group} {cid} {field}",
                        "result_ref": {
                            "calculation_id": cid,
                            "group": group,
                            "field": field,
                            "places": 1,
                        },
                    }
                )
    return {
        "candidates": [
            {
                "id": "paired",
                "title": "Absolute and paired temperature comparisons",
                "question": "Can an agreeing temperature contrast conceal offsets?",
                "rationale": "Read the paired contrast together with the original temperatures.",
                "presentation": "plot",
                "presentation_reason": "A compact paired panel with an absolute-state table.",
                "calculations": [absolute, contrast],
                "metrics": metrics,
                "evidence_panels": [
                    {
                        "kind": "reference_range",
                        "calculation_id": "contrast",
                        "title": "Heated-to-rear temperature contrast",
                        "x_label": "Temperature difference",
                        "y_label": "Case",
                    }
                ],
                "interpretation_limits": [
                    "Invented scalars do not establish a physical transport mechanism."
                ],
            }
        ]
    }


def draft(title, text, ids, *, figure=False):
    return {
        "title": title,
        "paragraphs": [{"text": text, "evidence_ids": ids, "figure_ids": ["1"] if figure else []}],
        "captions": {
            "1": "Heated-minus-rear model and reference temperature contrasts. Spans use "
            "conservative subtraction of the declared source endpoints, not confidence intervals. "
            "Absolute temperatures are reported in {{table:temperatures}}."
        }
        if figure
        else {},
        "image_observations": {"1": "not-viewed"} if figure else {},
        "evidence_notes": ["Invented recorded tutorial, not AI quality or physical validation."],
    }


def run(output: Path):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Use a fresh tutorial output directory")
    prepare_analysis(
        EXAMPLE / "inputs",
        output / "materials",
        question="Read absolute and paired temperature observations",
    )
    compiled = compile_analysis(
        output / "materials",
        save(output / "proposal.json", proposal()),
        "paired",
        output / "compiled",
    )
    writing = build_analysis_section(compiled, output / "analysis")
    result_input = json.loads((writing / "input.json").read_text(encoding="utf-8"))
    # A two-case tutorial panel needs less height; retain the generated local script,
    # original source data, width and font sizes instead of resizing the bitmap.
    plot = output / "analysis/figures/plot.py"
    lines = plot.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.startswith("PLOT_STYLE = "):
            style = ast.literal_eval(line.removeprefix("PLOT_STYLE = "))
            style["height_mm"] = 35
            lines[index] = f"PLOT_STYLE = {style!r}"
            break
    plot.write_text("\n".join(lines) + "\n", encoding="utf-8")
    runpy.run_path(str(plot))
    summary_path = plot.with_name("figure-summary.json")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["style"] = style
    summary["checks"] = json.loads(plot.with_name("layout-checks.json").read_text())
    save(summary_path, summary)
    shutil.copyfile(
        plot.with_name("evidence-panels.png"), writing / result_input["figures"][0]["path"]
    )
    sid = result_input["section_id"]
    params = [
        {
            "id": "max-step",
            "kind": "metric",
            "text": "Declared maximum solver step",
            "source": "Illustrative configuration",
            "json_value_ref": {
                "source": "sources/config.json",
                "pointer": "/solver/max_step_s",
                "unit": "s",
                "unit_pointer": "/units/max_step_s",
                "places": 2,
            },
        },
        {
            "id": "cells",
            "kind": "metric",
            "text": "Declared cell count",
            "source": "Illustrative configuration",
            "json_value_ref": {
                "source": "sources/config.json",
                "pointer": "/solver/cell_count",
                "unit": "",
                "unit_pointer": "/units/cell_count",
                "places": 0,
            },
        },
    ]
    methods_input = {
        "section_id": "methods",
        "title": "Comparison methods",
        "question": "Define the matched observations and reference envelope",
        "figures": [],
        "evidence": params,
        "duties": [
            {
                "purpose": "Explain comparison settings",
                "evidence_ids": [p["id"] for p in params],
                "figure_ids": [],
            }
        ],
    }
    methods_path = save(output / "materials/methods-input.json", methods_input)
    methods = draft(
        "Comparison methods",
        "We use invented observations to distinguish absolute-temperature agreement from "
        "agreement in a paired contrast. The declared configuration has {{value:cells}} cells "
        "and a maximum step of {{value:max-step}}, as summarized in {{table:settings}}. Both "
        "temperatures describe the same stipulated 5 s state. We define {{math:contrast}} and "
        "form reference endpoints by conservative subtraction of the supplied bounds.",
        [p["id"] for p in params],
    )
    methods["paragraphs"][0]["inline_math"] = {
        "contrast": {
            "kind": "row",
            "children": [
                {"kind": "symbol", "text": "ΔT"},
                {"kind": "text", "text": " = "},
                {
                    "kind": "sub",
                    "children": [
                        {"kind": "symbol", "text": "T"},
                        {"kind": "text", "text": "heated"},
                    ],
                },
                {"kind": "text", "text": " − "},
                {
                    "kind": "sub",
                    "children": [{"kind": "symbol", "text": "T"}, {"kind": "text", "text": "rear"}],
                },
            ],
        }
    }
    methods["tables"] = [
        {
            "table_id": "settings",
            "after_section_id": "methods",
            "caption": "Declared numerical settings",
            "columns": ["Parameter", "Value"],
            "rows": [["Cells", "{{value:cells}}"], ["Maximum step", "{{value:max-step}}"]],
            "evidence_ids": [p["id"] for p in params],
        }
    ]
    ids = [e["id"] for e in result_input["evidence"]]
    results = draft(
        "Absolute and contrast results",
        "In case A, both absolute temperatures exceed their centers by "
        "{{value:absolute-A-heated-difference}} and {{value:absolute-A-rear-difference}}, "
        "respectively ({{table:temperatures}}). Nevertheless, the model and reference contrasts "
        "in {{figure:1}} are both {{value:contrast-A-value}}. Case B yields a model contrast of "
        "{{value:contrast-B-value}} against {{value:contrast-B-reference_value}}, with a signed "
        "outside-range distance of {{value:contrast-B-outside_distance}} below the lower endpoint.",
        ids,
        figure=True,
    )
    results["tables"] = [
        {
            "table_id": "temperatures",
            "after_section_id": sid,
            "caption": "Original absolute-temperature comparison",
            "columns": ["Observation", "Model", "Reference", "Offset"],
            "rows": [
                [
                    g,
                    f"{{{{value:absolute-{g}-value}}}}",
                    f"{{{{value:absolute-{g}-reference_value}}}}",
                    f"{{{{value:absolute-{g}-difference}}}}",
                ]
                for g in ("A-heated", "A-rear", "B-heated", "B-rear")
            ],
            "evidence_ids": ids,
        }
    ]
    discussion_input = {
        "section_id": "discussion",
        "title": "Interpreting paired agreement",
        "question": "Read contrast cancellation",
        "figures": [],
        "evidence": [],
        "duties": [
            {
                "purpose": "Interpret the paired result",
                "evidence_ids": ["offset", "matched"],
                "figure_ids": [],
            }
        ],
    }
    discussion = draft(
        "Interpreting paired agreement",
        "The matching contrast in A does not establish its absolute states: the common "
        "{{value:offset}} offset cancels under subtraction, leaving a contrast mismatch of "
        "{{value:matched}}. The original temperatures therefore discriminate common offset "
        "from full agreement. Physical attribution requires resolved fields or a matched "
        "perturbation.",
        ["offset", "matched"],
    )
    conclusion_input = {**discussion_input, "section_id": "conclusion", "title": "Conclusions"}
    conclusion = draft(
        "Conclusions",
        "An agreeing paired contrast can conceal absolute offsets. The original temperatures "
        "must therefore accompany the contrast when assessing model–reference agreement.",
        ["offset", "matched"],
    )
    section_inputs = {
        "methods": methods_path,
        sid: writing / "input.json",
        "discussion": save(writing / "discussion-input.json", discussion_input),
        "conclusion": save(writing / "conclusion-input.json", conclusion_input),
    }
    drafts = {"methods": methods, sid: results, "discussion": discussion, "conclusion": conclusion}
    entries = []
    for name in drafts:
        p = save(output / f"{name}-draft.json", drafts[name])
        entries.append(
            {
                "section_id": name,
                "input": section_inputs[name].relative_to(output).as_posix(),
                "draft": p.relative_to(output).as_posix(),
                "depends_on": [] if name == "methods" else ["methods"] if name == sid else [sid],
                "evidence_bindings": {
                    "offset": f"{sid}/absolute-A-heated-difference",
                    "matched": f"{sid}/contrast-A-difference",
                }
                if name in {"discussion", "conclusion"}
                else {},
            }
        )
    outline = {
        "title": "Reading absolute states and paired contrasts",
        "spine": {
            "topic_id": "paired-tutorial",
            "central_claim_id": "contrast-B-difference",
            "sections": [
                {
                    "section_id": name,
                    "title": drafts[name]["title"],
                    "role": "results" if name == sid else name,
                    "purpose": "Define and read the same paired comparison",
                    "required_claim_ids": ["contrast-B-difference"] if name == sid else [],
                }
                for name in drafts
            ],
        },
        "sections": entries,
    }
    workspace = prepare_manuscript_seed(
        save(output / "outline.json", outline), output / "workspace"
    )
    assembled = assemble_manuscript(workspace, workspace / "drafts.json", output / "manuscript")
    return export_section_docx(assembled, output / "manuscript.docx", layout="near-reference")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    print(run(p.parse_args().output))
