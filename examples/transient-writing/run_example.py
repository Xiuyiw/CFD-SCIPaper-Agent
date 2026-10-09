"""Prepare a portable transient task, or replay explicitly recorded tutorial prose."""

import argparse
import json
import runpy
import shutil
from pathlib import Path

from cfdpaper.publication.section import (
    assemble_section,
    export_section_docx,
    prepare_section,
)

EXAMPLE = Path(__file__).resolve().parent
HOST_TASK = """

## Host-neutral transient writing task

Read input.json, sources/method.md, the complete sources/history.csv, table-results.json and
skills/cfd-evidence-writing/SKILL.md. Follow its temporal reference and open figures/1.png
if your host can view images. Write draft.json matching draft-template.json. Explain how sampled
threshold timing and peak magnitude differ, then compare saved-rate integration with the independent
cumulative ledgers. Use result_ref-bound tokens; do not infer a causal thermal mechanism.
The dataset is invented and no literature was supplied; do not invent citations.

With local Python/filesystem tools, assemble this package and export a fresh DOCX using the commands
in README.md. A web/file-review host may read the attached files and return JSON; unless it actually
has a local execution/image tool, it must not claim it calculated, viewed or exported artifacts.
Transfer the returned draft to a local operator for assembly. This package has no provider SDK.
Do not read the recorded tutorial draft before an independent host attempt.
"""


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def metric(identifier, calculation, group, field, places=1):
    return {
        "id": identifier,
        "kind": "metric",
        "text": f"{group}: {field}",
        "source": f"sources/history.csv: case {group}; {field} on the observed 0–12 s window",
        "result_ref": {
            "calculation_id": calculation,
            "group": group,
            "field": field,
            "places": places,
        },
    }


def prepare(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    source = output / "section-input"
    source.mkdir()
    shutil.copytree(EXAMPLE / "inputs", source / "sources")
    plot = runpy.run_path(str(EXAMPLE / "plot_history.py"))["run"]
    artwork = plot(source / "sources/history.csv", source / "sources/figure")
    calculations = []
    for identifier, column, unit, kind in (
        ("temperature", "temperature_K", "K", "instantaneous"),
        ("heat-rate", "heat_rate_W", "W", "instantaneous"),
        ("heat-ledger", "cumulative_heat_J", "J", "cumulative"),
    ):
        calculation = {
            "id": identifier,
            "source": "sources/history.csv",
            "operation": "temporal",
            "columns": {"time": "time_s", "value": column},
            "units": {"time": "s", "value": unit},
            "group_by": "case",
            "time_window": [0, 12],
            "temporal_value_kind": kind,
            "domain": "Invented illustrative thermal domain; shared observed 0–12 s window",
        }
        if identifier == "temperature":
            calculation.update(
                quantity_kind="absolute-temperature",
                threshold=400,
                crossing_direction="at-or-above",
            )
        calculations.append(calculation)
    evidence = [
        {
            "id": "definition",
            "kind": "interpretation",
            "text": "Invented tutorial series; saved rates and independent cumulative ledger.",
            "source": "sources/method.md",
        }
    ]
    for case in ("A", "B"):
        for suffix, field in (
            ("max", "maximum"),
            ("peak", "peak_time"),
            ("crossing", "first_crossing_time"),
            ("mean", "time_mean"),
        ):
            evidence.append(metric(f"{case}-{suffix}", "temperature", case, field))
        evidence.append(metric(f"{case}-integral", "heat-rate", case, "integral"))
        evidence.append(metric(f"{case}-ledger", "heat-ledger", case, "change"))
    data = {
        "section_id": "transient-thermal-response",
        "title": "Saved-sample timing and thermal response in invented histories",
        "question": "How do timing and magnitude relate, and what does saved-rate integration add?",
        "context": "Invented software tutorial, not CFD, experimental or battery validation.",
        "style": {
            "font_family": "Times New Roman",
            "body_first_line_indent_chars": 2,
            "body_space_before_pt": 0,
            "body_space_after_pt": 0,
        },
        "source_files": [
            p.relative_to(source).as_posix() for p in sorted(source.rglob("*")) if p.is_file()
        ],
        "table_calculations": calculations,
        "figures": [
            {
                "id": "1",
                "path": artwork.relative_to(source).as_posix() + "/history.png",
                "caption": "Invented temperature, heat-rate and cumulative heat histories.",
                "description": "Three aligned temporal panels with nonuniform saved samples.",
                "sizing": {
                    "source_width_mm": 160,
                    "target_width_mm": 160,
                    "minimum_source_font_pt": 8,
                },
            }
        ],
        "evidence": evidence,
        "duties": [
            {
                "purpose": "Separate sampled timing, temperature response and heat accounting",
                "evidence_ids": [e["id"] for e in evidence],
                "figure_ids": ["1"],
            }
        ],
    }
    package = prepare_section(save(source / "input.json", data), output / "writing")
    task = package / "TASK.md"
    task.write_text(task.read_text(encoding="utf-8") + HOST_TASK, encoding="utf-8")
    shutil.copyfile(EXAMPLE / "README.md", package / "README.md")
    return package


def run(output):
    output = Path(output)
    package = prepare(output)
    draft = output / "recorded-tutorial-draft.json"
    shutil.copyfile(EXAMPLE / "recorded/draft.json", draft)
    section = assemble_section(package, draft, output / "section")
    export_section_docx(section, output / "section.docx", layout="near-reference")
    return section


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    print(prepare(args.output) if args.prepare_only else run(args.output))
