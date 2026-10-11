"""Replay connected recorded prose over invented data through the public APIs."""

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
STYLE = {
    "font_family": "Times New Roman",
    "body_first_line_indent_chars": 2,
    "body_space_before_pt": 0,
    "body_space_after_pt": 0,
}


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def proposal():
    definitions = [
        {
            "id": "history",
            "source": "sources/history.csv",
            "operation": "temporal",
            "columns": {"time": "time_s", "value": "temperature_K"},
            "units": {"time": "s", "value": "K"},
            "quantity_kind": "absolute-temperature",
            "time_window": [0, 5],
            "member_id": ["time_s"],
        },
        {
            "id": "timing",
            "source": "sources/timing.csv",
            "operation": "reference_range",
            "columns": {
                "value": "model_s",
                "reference": "reference_s",
                "lower": "lower_s",
                "upper": "upper_s",
            },
            "units": {key: "s" for key in ("value", "reference", "lower", "upper")},
            "reference_kind": "reported-range",
            "member_id": ["case"],
        },
        {
            "id": "temperature",
            "source": "sources/temperature.csv",
            "operation": "reference_range",
            "columns": {
                "value": "model_K",
                "reference": "reference_K",
                "half_width": "half_width_K",
            },
            "units": {key: "K" for key in ("value", "reference", "half_width")},
            "reference_kind": "declared-bound",
            "quantity_kind": "absolute-temperature",
            "member_id": ["case"],
        },
    ]
    for item in definitions:
        item.update(
            group_by="case",
            expected_groups=["A", "B"],
            domain="Invented common-condition response variants",
            definition_source={"path": "sources/method.md", "locator": "L2-L8"},
            comparison={"status": "supported", "scope": "Same declared observation"},
            interpretation_limits=["Invented records do not establish physical validation."],
        )
    metrics = []
    for calculation, fields in (
        ("history", ["time_mean"]),
        ("timing", ["difference", "outside_distance"]),
        ("temperature", ["difference", "outside_distance"]),
    ):
        for group in ("A", "B"):
            for field in fields:
                metrics.append(
                    {
                        "id": f"{calculation}-{field}-{group}",
                        "text": f"{calculation} {field} for {group}",
                        "result_ref": {
                            "calculation_id": calculation,
                            "group": group,
                            "field": field,
                            "places": 1,
                        },
                    }
                )
    return {
        "candidates": [
            {
                "id": "observations",
                "title": "Timing and temperature observations",
                "question": "Does event timing agreement also establish temperature agreement?",
                "rationale": "Use independent timing and temperature observations "
                "to test the same inference.",
                "presentation": "plot",
                "style": STYLE,
                "presentation_reason": "The saved profile and two unlike-unit interval "
                "comparisons reveal the conflict.",
                "interpretation_limits": [
                    "No physical cause can be identified from invented scalar records."
                ],
                "calculations": definitions,
                "metrics": metrics,
                "evidence_panels": [
                    {
                        "kind": "profile",
                        "calculation_id": "history",
                        "title": "Saved temperature response",
                        "x_label": "Time",
                        "y_label": "Temperature",
                    },
                    {
                        "kind": "reference_range",
                        "calculation_id": "timing",
                        "title": "Event timing",
                        "x_label": "Event time",
                        "y_label": "Variant",
                    },
                    {
                        "kind": "reference_range",
                        "calculation_id": "temperature",
                        "title": "Temperature at 5 s",
                        "x_label": "Temperature",
                        "y_label": "Variant",
                    },
                ],
            }
        ]
    }


def draft(title, text, evidence_ids, *, figure=False):
    return {
        "title": title,
        "paragraphs": [
            {
                "text": text,
                "evidence_ids": evidence_ids,
                "figure_ids": ["1"] if figure else [],
            }
        ],
        "captions": {
            "1": "Invented saved temperature profiles over 0 to 5 s, "
            "independent event times, and temperature at 5 s. Timing spans are supplied "
            "illustrative reported ranges; temperature spans are declared bounds. Neither "
            "is a confidence interval. Lines connect saved samples only; signed differences "
            "are model minus center."
        }
        if figure
        else {},
        "image_observations": {"1": "not-viewed"} if figure else {},
        "evidence_notes": ["Recorded tutorial replay, not an AI performance evaluation."],
    }


def run(output: Path, *, docx=True) -> Path:
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Use a fresh tutorial output directory")
    prepare_analysis(
        EXAMPLE / "inputs",
        output / "materials",
        question="Does timing agreement extend to temperature response?",
    )
    proposal_path = save(output / "recorded-proposal.json", proposal())
    compiled = compile_analysis(
        output / "materials", proposal_path, "observations", output / "compiled"
    )
    writing = build_analysis_section(compiled, output / "analysis")
    # Demonstrate the generated local style entry point at the final manuscript size.
    # Only this new tutorial's script is edited; original CSVs and evidence stay unchanged.
    plot = output / "analysis/figures/plot.py"
    lines = plot.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.startswith("PLOT_STYLE = "):
            plot_style = ast.literal_eval(line.removeprefix("PLOT_STYLE = "))
            plot_style["height_mm"] = 135
            lines[index] = f"PLOT_STYLE = {plot_style!r}"
            break
    plot.write_text("\n".join(lines) + "\n", encoding="utf-8")
    runpy.run_path(str(plot))
    summary_path = plot.with_name("figure-summary.json")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["style"] = plot_style
    summary["checks"] = json.loads(plot.with_name("layout-checks.json").read_text(encoding="utf-8"))
    save(summary_path, summary)
    result_input = json.loads((writing / "input.json").read_text(encoding="utf-8"))
    shutil.copyfile(
        output / "analysis/figures/evidence-panels.png",
        writing / result_input["figures"][0]["path"],
    )
    result_ids = [e["id"] for e in result_input["evidence"]]
    result_sid = result_input["section_id"]
    titles = {
        "methods": "Comparison methods",
        result_sid: "Timing and temperature results",
        "discussion": "Interpreting the observation mismatch",
        "conclusion": "Conclusions",
    }
    results = draft(
        titles[result_sid],
        "Both event times lie within their supplied timing intervals, with signed differences "
        "of {{value:timing-difference-A}} and {{value:timing-difference-B}} for A and B. "
        "Temperature at 5 s gives a different assessment: A differs from its center by "
        "{{value:temperature-difference-A}}, while B differs by {{value:temperature-difference-B}} "
        "and exceeds the upper bound by {{value:temperature-outside_distance-B}}. "
        "The saved profile in {{figure:1}} shows the growing separation before that "
        "comparison time. The time-weighted means are {{value:history-time_mean-A}} and "
        "{{value:history-time_mean-B}} over the same window.",
        result_ids,
        figure=True,
    )
    source_input = {
        "section_id": "methods",
        "title": titles["methods"],
        "question": "Define the observation windows and comparisons.",
        "figures": [],
        "source_files": ["sources/method.md"],
        "style": STYLE,
        "evidence": [
            {
                "id": "definition",
                "kind": "observation",
                "source": "sources/method.md:L2-L8",
                "text": "Invented response and comparison definitions.",
            }
        ],
        "duties": [
            {"purpose": "Define the comparison", "evidence_ids": ["definition"], "figure_ids": []}
        ],
    }
    inputs = {result_sid: writing / "input.json"}
    drafts = {result_sid: save(output / "results-draft.json", results)}
    methods = draft(
        titles["methods"],
        "We use invented response records to illustrate a joint comparison of event timing and "
        "temperature. A and B start at 300 K under the same stipulated forcing and boundaries. "
        "Instantaneous saved temperatures are compared over the exact 0 to 5 s window, excluding "
        "the later 9 s samples. The temporal mean uses nonuniform trapezoidal spacing. "
        "Independently "
        "supplied event times are not threshold crossings inferred from this curve. Temperature "
        "is compared at 5 s against a 430 K center with a declared 10 K half width. Signed "
        "differences follow {{math:delta}}, with x denoting either event time or temperature. "
        "The illustrative intervals are not confidence intervals.",
        ["definition"],
    )
    methods["paragraphs"][0]["inline_math"] = {
        "delta": {
            "kind": "row",
            "children": [
                {"kind": "symbol", "text": "δ"},
                {"kind": "text", "text": " = "},
                {
                    "kind": "sub",
                    "children": [
                        {"kind": "symbol", "text": "x"},
                        {"kind": "text", "text": "model"},
                    ],
                },
                {"kind": "text", "text": " − "},
                {
                    "kind": "sub",
                    "children": [
                        {"kind": "symbol", "text": "x"},
                        {"kind": "text", "text": "reference"},
                    ],
                },
            ],
        }
    }
    texts = {
        "discussion": "Agreement in timing does not constrain the temperature state sufficiently "
        "in this constructed example. B's temperature is {{value:temperature-gap}} above its "
        "reference center despite its event time remaining within the supplied range. The "
        "temperature profile discriminates this interpretation from a claim of overall agreement. "
        "Timing and temperature could respond differently to heat input or heat removal, but these "
        "records contain no transport fields or reaction law to distinguish those explanations. "
        "A state-resolved thermal budget at the comparison time would be the next "
        "discriminating evidence.",
        "conclusion": "Event timing alone does not establish joint agreement. The constructed "
        "example retains timing agreement for both variants while B exceeds its temperature "
        "bound by {{value:outside-gap}}. Comparing observations on their declared supports "
        "reveals the mismatch without combining unlike units into a single model score.",
    }
    sections = []
    for sid in ("methods", result_sid, "discussion", "conclusion"):
        bindings = {}
        if sid != result_sid:
            local = dict(source_input, section_id=sid, title=titles[sid])
            inputs[sid] = save(writing / f"{sid}-input.json", local)
            if sid == "methods":
                recorded = methods
            else:
                metric_id = "temperature-gap" if sid == "discussion" else "outside-gap"
                target = (
                    "temperature-difference-B"
                    if sid == "discussion"
                    else "temperature-outside_distance-B"
                )
                bindings = {metric_id: f"{result_sid}/{target}"}
                recorded = draft(titles[sid], texts[sid], ["definition", metric_id])
            drafts[sid] = save(output / f"{sid}-draft.json", recorded)
        sections.append(
            {
                "section_id": sid,
                "input": inputs[sid].relative_to(output).as_posix(),
                "draft": drafts[sid].relative_to(output).as_posix(),
                "depends_on": []
                if sid == "methods"
                else ["methods"]
                if sid == result_sid
                else [result_sid],
                "evidence_bindings": bindings,
            }
        )
    outline = {
        "title": "Joint timing and temperature comparison with invented records",
        "context": "Recorded tutorial prose replay, not model-writing or experimental validation.",
        "terms": {
            "event time": "Independently supplied synthetic event record",
            "temperature": "Saved instantaneous temperature in K",
        },
        "spine": {
            "topic_id": "multi-observation-tutorial",
            "central_claim_id": "temperature-outside_distance-B",
            "sections": [
                {
                    "section_id": s["section_id"],
                    "title": titles[s["section_id"]],
                    "role": "results" if s["section_id"] == result_sid else s["section_id"],
                    "purpose": "Define, compare and interpret the same observations.",
                    "required_claim_ids": ["temperature-outside_distance-B"]
                    if s["section_id"] == result_sid
                    else [],
                }
                for s in sections
            ],
        },
        "sections": sections,
    }
    package = prepare_manuscript_seed(save(output / "outline.json", outline), output / "workspace")
    candidate = assemble_manuscript(package, package / "drafts.json", output / "manuscript")
    return (
        export_section_docx(candidate, output / "manuscript.docx", layout="near-reference")
        if docx
        else candidate
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Fresh output directory")
    parser.add_argument(
        "--no-docx",
        action="store_true",
        help="Assemble first; export with a separate document runtime",
    )
    args = parser.parse_args()
    print(run(args.output, docx=not args.no_docx))
