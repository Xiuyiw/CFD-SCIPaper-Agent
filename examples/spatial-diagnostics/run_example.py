"""Replay a recorded host response with weighted data and a portable field figure.

The inputs are analytical fields, not CFD results. For a fresh host attempt, use
--prepare-only and give materials/host-task.md to the host before sharing recorded/.
"""

import argparse
import json
import runpy
import shutil
from pathlib import Path

from cfdpaper.analysis_suggestions import compile_analysis, prepare_analysis
from cfdpaper.publication.analysis_section import build_analysis_section
from cfdpaper.publication.figure_tasks import import_figure_task, prepare_figure_task
from cfdpaper.publication.section import assemble_section


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def prepare(output):
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Use a new output directory: {output}")
    prepare_analysis(
        Path(__file__).with_name("inputs"),
        output / "materials",
        question="Compare wall thermal exposure and spatial distribution for Reference and "
        "Modified. Select useful diagnostics and explain their relationship. The separate "
        "volume data exercise another measure and do not explain the wall field.",
    )
    return output


def make_figure(output):
    source = output / "figure-input"
    source.mkdir()
    example = Path(__file__).parent
    shutil.copytree(example / "inputs", source / "inputs")
    shutil.copyfile(example / "plot_wall.py", source / "plot_wall.py")
    task = {
        "figure_id": "1",
        "kind": "data",
        "final_width_mm": 160,
        "purpose": "Compare wall temperature location and extent on a common scale.",
        "claim_ceiling": "Prescribed analytical fields, not simulated transport mechanisms.",
        "sources": [
            {
                "id": "wall",
                "path": "inputs/wall.csv",
                "role": "data",
                "description": "Physical facet bounds, temperatures and areas",
            },
            {
                "id": "method",
                "path": "inputs/method.md",
                "role": "context",
                "description": "Field definitions and physical domain",
            },
            {
                "id": "renderer",
                "path": "plot_wall.py",
                "role": "editable_source",
                "description": "Reproducible piecewise-constant field renderer",
            },
        ],
        "labels": [{"text": "Position", "unit": "mm"}, {"text": "Temperature", "unit": "degC"}],
    }
    package = prepare_figure_task(write_json(source / "task.json", task), output / "figure-task")
    plot = runpy.run_path(str(package / "sources/plot_wall.py"))["run"]
    produced = package / "artwork"
    plot(package / "sources/inputs/wall.csv", produced)
    caption = (
        "Prescribed wall temperature fields for Reference and Modified. Facets are "
        "piecewise constant on the full rectangular wall, with exact physical boundaries "
        "and a common temperature scale. No interpolation is applied."
    )
    delivery = {
        "figure_id": "1",
        "editable_sources": ["artwork/plot_wall.py", "artwork/wall.svg"],
        "preview": "artwork/wall.png",
        "caption": caption,
        "exports": ["artwork/wall.pdf", "artwork/wall.tiff", "artwork/source-data.csv"],
        "notes": ["Analytical teaching example. Inspect the final document at its intended width."],
    }
    return import_figure_task(
        package, write_json(package / "returned.json", delivery), output / "figure-delivery"
    )


def prepare_writing(output, *, proposal=None, candidate="wall-exposure-distribution"):
    output = prepare(output)
    example = Path(__file__).parent
    proposal = Path(proposal) if proposal else example / "recorded/proposal.json"
    payload = compile_analysis(output / "materials", proposal, candidate, output / "compiled")
    compile_analysis(
        output / "materials", proposal, "volume-operator-check", output / "volume-check"
    )
    delivery = make_figure(output)
    # Compose existing supported inputs; the imported figure is not a new solver adapter.
    data = json.loads(payload.read_text(encoding="utf-8"))
    target = payload.parent / "sources/field-figure"
    shutil.copytree(delivery, target)
    data["source_files"] += [
        path.relative_to(payload.parent).as_posix()
        for path in sorted(target.rglob("*"))
        if path.is_file() and "skills" not in path.parts
    ]
    data["figures"] = [
        {
            "id": "1",
            "path": "sources/field-figure/artwork/wall.png",
            "caption": json.loads((delivery / "delivery.json").read_text())["caption"],
            "description": "Two piecewise-constant wall fields on the same physical domain.",
            "sizing": {"source_width_mm": 160, "target_width_mm": 160, "minimum_source_font_pt": 9},
        }
    ]
    write_json(payload, data)
    writing = build_analysis_section(payload, output / "section-input")
    shutil.copyfile(proposal, output / "recorded-host-proposal.json")
    return writing


def run(output, *, proposal=None, draft=None, candidate="wall-exposure-distribution"):
    writing = prepare_writing(output, proposal=proposal, candidate=candidate)
    output = Path(output)
    draft = Path(draft) if draft else Path(__file__).parent / "recorded/draft.json"
    shutil.copyfile(draft, output / "recorded-host-draft.json")
    assembled = assemble_section(writing, draft, output / "section")
    return assembled


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--writing-only", action="store_true")
    parser.add_argument("--proposal", type=Path)
    parser.add_argument("--draft", type=Path)
    parser.add_argument("--candidate", default="wall-exposure-distribution")
    args = parser.parse_args()
    print(
        prepare(args.output)
        if args.prepare_only
        else prepare_writing(args.output, proposal=args.proposal, candidate=args.candidate)
        if args.writing_only
        else run(args.output, proposal=args.proposal, draft=args.draft, candidate=args.candidate)
    )
