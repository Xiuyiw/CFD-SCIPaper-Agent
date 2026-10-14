"""Recorded synthetic tutorial: static methods, same-record contrast and finite layout."""

from __future__ import annotations

import argparse
import ast
import json
import runpy
import shutil
from pathlib import Path

from cfdpaper.analysis_suggestions import compile_analysis, prepare_analysis
from cfdpaper.materials import read_material_definitions
from cfdpaper.publication.analysis_section import build_analysis_section
from cfdpaper.publication.manuscript import assemble_manuscript
from cfdpaper.publication.manuscript_seed import prepare_manuscript_seed
from cfdpaper.publication.section import export_section_docx

EXAMPLE = Path(__file__).resolve().parent


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def proposal(locator):
    common = {
        "source": "sources/history.csv",
        "group_by": "case",
        "time_window": [0, 5],
        "domain": "Six illustrative saved states per case at common times 0–5 s",
        "member_id": ["case", "time_s"],
        "expected_groups": ["A", "B"],
        "definition_source": {"path": "sources/model.py", "locator": locator},
        "comparison": {"status": "supported", "scope": "Same-record illustrative values"},
        "interpretation_limits": ["Chosen tutorial states are not model predictions or events."],
    }
    calculations = [
        {
            **common,
            "id": key,
            "operation": "temporal",
            "quantity_kind": "absolute-temperature",
            "columns": {"time": "time_s", "value": f"{key}_K"},
            "units": {"time": "s", "value": "K"},
        }
        for key in ("front", "rear")
    ] + [
        {
            **common,
            "id": "contrast",
            "operation": "temporal_difference",
            "quantity_kind": "temperature-difference",
            "columns": {"time": "time_s", "reference": "rear_K", "comparison": "front_K"},
            "units": {"time": "s", "reference": "K", "comparison": "K"},
        }
    ]
    metrics = [
        {
            "id": f"{key}-{group}-{field}",
            "text": f"{key} {group} {field}",
            "result_ref": {"calculation_id": key, "group": group, "field": field, "places": 1},
        }
        for key in ("front", "rear", "contrast")
        for group in ("A", "B")
        for field in ("end_value", "time_mean")
    ]
    return {
        "candidates": [
            {
                "id": "results",
                "title": "Saved temperature patterns",
                "question": "Why retain original temperatures when reading their contrast?",
                "rationale": "Compare original states before interpreting a difference.",
                "presentation": "plot",
                "calculations": calculations,
                "metrics": metrics,
                "evidence_panels": [
                    {
                        "kind": "profile",
                        "calculation_id": key,
                        "title": title,
                        "x_label": "Elapsed time",
                        "y_label": label,
                    }
                    for key, title, label in (
                        ("front", "Front temperature", "Temperature"),
                        ("contrast", "Front-to-rear contrast", "Temperature difference"),
                    )
                ],
                "interpretation_limits": [
                    "This replay demonstrates software, not AI or physics quality."
                ],
            }
        ]
    }


def run(output: Path):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Use a fresh tutorial output directory")
    prepare_analysis(EXAMPLE / "inputs", output / "materials")
    definitions = read_material_definitions(
        output / "materials/sources",
        ["TutorialBalance.front_rate", "TutorialBalance.contrast"],
        paths=[Path("model.py")],
    )
    if definitions["issues"]:
        raise ValueError(definitions["issues"])
    save(output / "definitions.json", definitions)
    bounds = definitions["definitions"][1]
    compiled = compile_analysis(
        output / "materials",
        save(output / "proposal.json", proposal(f"L{bounds['start_line']}-L{bounds['end_line']}")),
        "results",
        output / "compiled",
    )
    writing = build_analysis_section(compiled, output / "analysis")
    result_input = json.loads((writing / "input.json").read_text(encoding="utf-8"))
    # Edit the generated local script, preserving fonts, widths and all source rows.
    plot = output / "analysis/figures/plot.py"
    lines = plot.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("PLOT_STYLE = "):
            style = ast.literal_eval(line.removeprefix("PLOT_STYLE = "))
            style["height_mm"] = 110
            lines[i] = f"PLOT_STYLE = {style!r}"
            break
    plot.write_text("\n".join(lines) + "\n", encoding="utf-8")
    runpy.run_path(str(plot))
    summary_path = plot.with_name("figure-summary.json")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary.update(style=style, checks=json.loads(plot.with_name("layout-checks.json").read_text()))
    save(summary_path, summary)
    shutil.copyfile(
        plot.with_name("evidence-panels.png"), writing / result_input["figures"][0]["path"]
    )
    result_input["figures"][0]["placement"] = "section-end"
    records = json.loads((EXAMPLE / "inputs/recorded.json").read_text(encoding="utf-8"))
    records["methods"]["input"]["evidence"][0]["text"] = definitions["definitions"][0]["text"]
    records["discussion"]["input"]["evidence"][0]["citation_record"] = json.loads(
        (EXAMPLE / "inputs/reference.json").read_text(encoding="utf-8")
    )
    records["results"]["input"] = result_input
    entries = []
    for sid, item in records.items():
        data, draft = item["input"], item["draft"]
        ids = [e["id"] for e in data["evidence"]]
        for paragraph in draft["paragraphs"]:
            paragraph.update(evidence_ids=ids, figure_ids=["1"] if sid == "results" else [])
        for table in draft.get("tables", []):
            table["evidence_ids"] = ids
        source = writing / "input.json" if sid == "results" else output / f"materials/{sid}.json"
        save(source, data)
        entries.append(
            {
                "section_id": sid,
                "input": source.relative_to(output).as_posix(),
                "draft": save(output / f"{sid}-draft.json", draft).relative_to(output).as_posix(),
            }
        )
    outline = {
        "title": "Reading method definitions and original temperature states",
        "spine": {
            "topic_id": "effective-methods-tutorial",
            "central_claim_id": "contrast-B-end_value",
            "sections": [
                {
                    "section_id": sid,
                    "title": sid.title(),
                    "role": sid,
                    "purpose": "Read the same illustrative comparison",
                    "required_claim_ids": ["contrast-B-end_value"] if sid == "results" else [],
                }
                for sid in records
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    print(run(parser.parse_args().output))
