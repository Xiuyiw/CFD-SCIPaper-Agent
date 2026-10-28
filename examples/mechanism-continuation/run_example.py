"""Continue the constructed research-expression example without regenerating its study.

The example author supplies the diagram and interpretation. Product APIs provide
current evidence, candidate attachment, recomputation and editable Word assembly.
"""

from __future__ import annotations

import argparse
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from matplotlib.font_manager import findfont
from PIL import Image, ImageDraw, ImageFont

from cfdpaper.publication.figure_tasks import import_figure_task, prepare_figure_task
from cfdpaper.publication.research_workspace import (
    attach_imported_figure,
    build_research_workspace,
    research_question_context,
)

FIGURE_ID = "observation-support"
DELTA_ID = "paired-A-all-difference_mean"
EVIDENCE_IDS = [
    "paired-A-all-reference_mean",
    "paired-A-all-comparison_mean",
    DELTA_ID,
    *[
        f"temperature-A{case}-{region}-weighted_mean"
        for case in (0, 1)
        for region in ("footprint", "rest")
    ],
]
QUESTION = "How does the same original interface support local and whole-interface comparisons?"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def context(workspace):
    return research_question_context(
        workspace, question=QUESTION, section_id="results", evidence_ids=EVIDENCE_IDS
    )


def draw_support(destination, material, reading):
    """Use the same original-face primitives for editable SVG and raster preview."""
    width, height = 1900, 1100
    ink, muted = "#263e48", "#526771"
    fills = ("#c7dedb", "#e9dfce")
    image = Image.new("RGB", (width, height), "white")
    painter = ImageDraw.Draw(image)
    svg = ET.Element(
        "svg",
        xmlns="http://www.w3.org/2000/svg",
        width="160mm",
        height=f"{160 * height / width:g}mm",
        viewBox=f"0 0 {width} {height}",
    )
    ET.SubElement(svg, "title").text = "Original-face support for a paired temperature contrast"
    font_path = findfont("DejaVu Sans")

    def text(x, y, value, size=38, *, anchor="start", color=ink):
        font = ImageFont.truetype(font_path, size)
        painter.text(
            (x, y), value, font=font, fill=color, anchor={"start": "lt", "middle": "mt"}[anchor]
        )
        element = ET.SubElement(
            svg,
            "text",
            x=str(x),
            y=str(y),
            fill=color,
            **{
                "font-family": "DejaVu Sans, sans-serif",
                "font-size": str(size),
                "text-anchor": anchor,
                "dominant-baseline": "text-before-edge",
            },
        )
        element.text = value

    def polygon(points, fill, stroke=ink, line_width=3):
        painter.polygon(points, fill=fill, outline=stroke, width=line_width)
        ET.SubElement(
            svg,
            "polygon",
            points=" ".join(f"{x:g},{y:g}" for x, y in points),
            fill=fill,
            stroke=stroke,
            **{"stroke-width": str(line_width)},
        )

    text(70, 38, "A fixed interface, two complementary readings", 52)
    text(70, 112, "Structure A | original faces and physical-area weighting", 38, color=muted)
    for x, fill, label in ((90, fills[0], "Footprint"), (1050, fills[1], "Remaining interface")):
        polygon([(x, 182), (x + 42, 182), (x + 42, 220), (x, 220)], fill)
        text(x + 62, 180, label)
    means = {item["id"]: item["resolved"]["raw_value"] for item in reading["evidence"]}
    for case, x, label in (("A0", 90, "Reference"), ("A1", 1050, "Comparison")):
        with np.load(material / f"{case}.npz", allow_pickle=False) as source:
            vertices = source["vertices_m"][:, :2]
            connectivity, starts = source["faces_connectivity"], source["face_starts"]
            values, areas = source["face_value"], source["area_m2"]
        span = np.ptp(vertices, axis=0)
        scale = 760 / span[0]
        origin = vertices.min(axis=0)
        text(x, 245, f"{case} / {label}", 42)
        for face, start in enumerate(starts):
            count = int(connectivity[start])
            indices = connectivity[start + 1 : start + 1 + count]
            points = [
                (x + (p[0] - origin[0]) * scale, 300 + (span[1] - p[1] + origin[1]) * scale)
                for p in vertices[indices]
            ]
            polygon(points, fills[face])
            center = sum(p[0] for p in points) / len(points)
            text(center, 332, f"Face {face + 1}", 36, anchor="middle")
            text(center, 395, f"{values[face]:g} K", 42, anchor="middle")
            text(center, 525, f"{areas[face] * 1e6:g} mm²", 36, anchor="middle", color=muted)
        mean_field = "reference_mean" if case == "A0" else "comparison_mean"
        text(x + 380, 620, "Whole-interface mean", 38, anchor="middle")
        text(x + 380, 680, f"{means['paired-A-all-' + mean_field]:.3f} K", 48, anchor="middle")
    polygon(
        [(900, 386), (983, 386), (983, 366), (1015, 400), (983, 434), (983, 414), (900, 414)], ink
    )
    text(950, 480, "Paired", 36, anchor="middle", color=muted)
    text(950, 525, "contrast", 36, anchor="middle", color=muted)
    text(950, 795, "Mean change = comparison mean − reference mean", 42, anchor="middle")
    text(950, 865, f"{means[DELTA_ID]:+.3f} K", 58, anchor="middle")
    text(950, 970, "The same 1:3 area ratio weights both original faces.", 38, anchor="middle")
    text(
        950,
        1040,
        "Constructed static fields; the arrow denotes comparison, not heat flow.",
        36,
        anchor="middle",
        color=muted,
    )
    ET.indent(svg)
    ET.ElementTree(svg).write(destination / "figure.svg", encoding="utf-8", xml_declaration=True)
    image.save(destination / "figure.png", dpi=(301.6, 301.6))


def artwork_package(workspace, output, reading):
    """Prepare, return and import an example-author schematic through public APIs."""
    inputs = output / "input"
    material = inputs / "materials"
    material.mkdir(parents=True)
    for name in ("A0.npz", "A1.npz", "definition.md"):
        shutil.copy2(workspace / "sections/results/sources" / name, material / name)
    write(inputs / "context.json", reading)
    delta = next(
        item["resolved"]["raw_value"] for item in reading["evidence"] if item["id"] == DELTA_ID
    )
    write(
        inputs / "task.json",
        {
            "figure_id": FIGURE_ID,
            "kind": "schematic",
            "purpose": "Define the original faces, area weighting and paired observation support.",
            "claim_ceiling": (
                "Constructed-data comparison and arithmetic only; no causal transport claim."
            ),
            "sources": [
                {
                    "id": name.split(".")[0],
                    "path": f"materials/{name}",
                    "role": "context",
                    "description": "Original constructed geometry, values or study definition.",
                }
                for name in ("A0.npz", "A1.npz", "definition.md")
            ]
            + [
                {
                    "id": "reading",
                    "path": "context.json",
                    "role": "context",
                    "description": "Current product-resolved selected evidence.",
                }
            ],
            "labels": [
                {"text": "Original face temperature and whole-interface change", "unit": "K"}
            ],
            "relationships": [
                {
                    "from": "A0",
                    "to": "A1",
                    "meaning": "Same-face comparison minus reference, not heat transfer",
                    "status": "method",
                }
            ],
            "final_width_mm": 160,
        },
    )
    prepared = prepare_figure_task(inputs / "task.json", output / "prepared")
    returned = output / "returned"
    returned.mkdir()
    draw_support(returned, material, reading)
    (returned / "author-notes.md").write_text(
        "Example-author note: colors identify fixed regions, not temperature magnitude.\n",
        encoding="utf-8",
    )
    caption = (
        "Original-face observation support for Structure A. Geometry, areas and face temperatures "
        "come from the constructed NPZ arrays; means use physical face area. "
        f"Whole-interface change (A1 − A0) = {delta:+.3f} K. "
        "The arrow denotes paired comparison, not heat flow; the independent local budgets "
        "do not establish a causal heat-transfer mechanism."
    )
    delivery = read(prepared / "delivery-template.json")
    delivery.update(
        figure_id=FIGURE_ID,
        title="Original-face support and paired temperature contrast",
        legend="Region colors identify fixed support; the arrow denotes comparison, not heat flow.",
        editable_sources=["figure.svg"],
        preview="figure.png",
        caption=caption,
        body_reference="{{figure:observation-support}} defines the original-face support and "
        "area weighting behind the positive whole-interface change "
        "{{value:paired-A-all-difference_mean}}. Its comparison arrow is not a heat-flow pathway.",
        exports=["author-notes.md"],
        notes=[
            "Example-author artwork and interpretation from constructed inputs; "
            "no solver validation."
        ],
        sizing={"source_width_mm": 160, "target_width_mm": 160, "minimum_source_font_pt": 8.5},
    )
    write(returned / "delivery.json", delivery)
    return import_figure_task(prepared, returned / "delivery.json", output / "imported")


def revise_interpretation(workspace):
    """Explicit example-author revisions, not text inferred by the change detector."""
    drafts = read(workspace / "drafts.json")
    method = read(workspace / drafts["methods"])
    method["paragraphs"][0]["text"] += (
        " In the isolated continuation, both prescribed A1 face temperatures are reduced "
        "uniformly by 4 K; geometry, areas, definitions and the independent budgets remain "
        "unchanged. This is a constructed software-change demonstration, not a new CFD solution."
    )
    write(workspace / drafts["methods"], method)
    results = read(workspace / drafts["results"])
    results["paragraphs"][0]["text"] = (
        "After the uniform shift, the whole-interface mean for Structure A falls from "
        "{{value:A0-mean}} to {{value:A1-mean}}, giving a comparison-minus-reference change "
        "of {{value:paired-A-all-difference_mean}}. Structure B retains its original rise "
        "from {{value:B0-mean}} to {{value:B1-mean}} and change "
        "{{value:paired-B-all-difference_mean}}. {{table:paired-means}} retains the original "
        "means rather than treating their differences as independent evidence."
    )
    results["paragraphs"][1]["text"] = (
        "The Structure A footprint mean falls from "
        "{{value:temperature-A0-footprint-weighted_mean}} to "
        "{{value:temperature-A1-footprint-weighted_mean}}, while its remaining-region mean "
        "is unchanged at {{value:temperature-A1-rest-weighted_mean}}. "
        "{{figure:thermal-budget}} retains the regional comparison beside the separately "
        "prescribed budgets in {{table:local-budget}}; the budgets themselves did not change."
    )
    results["paragraphs"][2]["text"] = (
        "{{figure:observation-support}} retains the same original faces and area weighting "
        "while showing the now negative whole-interface change "
        "{{value:paired-A-all-difference_mean}}. The cooler footprint and unchanged remaining "
        "region account for that arithmetic; the comparison arrow is not a heat-flow pathway."
    )
    results["observation_notes"]["thermal-budget"] = (
        "Example-author reading after the constructed shift: Structure A's footprint cools "
        "and its remaining region is unchanged; budgets remain independent prescribed values."
    )
    write(workspace / drafts["results"], results)
    interpretations = {
        "discussion": (
            "The changed Structure A fields no longer support the earlier local-cooling versus "
            "whole-interface-warming contrast: its footprint cools and the remaining region "
            "is unchanged, so the physical-area mean falls. The unmodified Structure B pair "
            "still exhibits that contrast. This difference follows from the observed support "
            "and arithmetic, not a demonstrated change in conduction or mixing. Independent "
            "prescribed budgets cannot explain the temperature shift or establish a causal "
            "heat-transfer mechanism; a transport-linked observation would be needed."
        ),
        "conclusion": (
            "The constructed continuation distinguishes a changed whole-interface response "
            "from unchanged geometry, area weights and local accounting. The source-driven "
            "direction change requires a different interpretation for Structure A, not a new "
            "device ranking. Keeping local and global support explicit prevents footprint "
            "cooling from being used alone as evidence of whole-interface cooling."
        ),
    }
    for sid, paragraph in interpretations.items():
        draft = read(workspace / drafts[sid])
        draft["paragraphs"][0]["text"] = paragraph
        write(workspace / drafts[sid], draft)


def run(previous_output, output):
    previous_output, output = Path(previous_output).resolve(), Path(output).resolve()
    previous = previous_output / "candidate/workspace"
    if not (previous / "manuscript-input.json").is_file():
        raise ValueError(
            "Run examples/research-expression/run_example.py first and pass its output root"
        )
    if output.is_relative_to(previous_output) or previous_output.is_relative_to(output):
        raise ValueError("Use a fresh output outside the research-expression input directory")
    output.mkdir(parents=True, exist_ok=False)
    before = context(previous)
    write(output / "context-before.json", before)
    imported = artwork_package(previous, output / "artwork-before", before)
    attached = attach_imported_figure(
        previous,
        imported,
        output / "initial-workspace",
        section_id="results",
        evidence_ids=EVIDENCE_IDS,
        image_observation="author-provided",
        observation_note="Example-author schematic of the original constructed support.",
    )
    first = build_research_workspace(attached, output / "first-candidate")
    working = output / "author-working"
    shutil.copytree(first / "workspace", working)
    original_art = working / "sections/results/sources/figure-tasks" / FIGURE_ID
    notes = original_art / "author-notes.md"
    notes.write_text(
        notes.read_text(encoding="utf-8") + "Retain this author note during updates.\n",
        encoding="utf-8",
    )
    svg = original_art / "figure.svg"
    svg.write_text(
        svg.read_text(encoding="utf-8") + "\n<!-- Author-preserved region-color choice. -->\n",
        encoding="utf-8",
    )
    source = working / "sections/results/sources/A1.npz"
    with np.load(source, allow_pickle=False) as data:
        arrays = {key: data[key].copy() for key in data.files}
    arrays["face_value"] -= 4.0
    np.savez(source, **arrays)
    numerical = build_research_workspace(working, output / "numerical-refresh", baseline_dir=first)
    after = context(numerical / "workspace")
    write(output / "context-after.json", after)
    updated = artwork_package(numerical / "workspace", output / "artwork-after", after)
    art_workspace = attach_imported_figure(
        numerical / "workspace",
        updated,
        output / "artwork-updated-workspace",
        section_id="results",
        evidence_ids=EVIDENCE_IDS,
        image_observation="author-provided",
        observation_note="Example-author schematic of the same support after a uniform -4 K shift.",
        replace_existing=True,
    )
    host_workspace = output / "host-revised-workspace"
    shutil.copytree(art_workspace, host_workspace)
    revise_interpretation(host_workspace)
    final = build_research_workspace(
        host_workspace, output / "interpretation-updated", baseline_dir=numerical
    )
    write(
        output / "continuation.json",
        {
            "inputs": "Constructed research-expression fields; no new CFD or physical validation",
            "original_difference_K": before["evidence"][2]["resolved"]["raw_value"],
            "updated_difference_K": after["evidence"][2]["resolved"]["raw_value"],
            "first_document": "first-candidate/manuscript.docx",
            "direction_review": "numerical-refresh/manuscript/CHANGES.md",
            "final_document": "interpretation-updated/manuscript.docx",
            "interpretation_author": "Example-author revisions in revise_interpretation()",
        },
    )
    return final / "manuscript.docx"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "previous_output", type=Path, help="Completed research-expression output root"
    )
    parser.add_argument("output", type=Path, help="New, separate continuation output directory")
    args = parser.parse_args()
    print(run(args.previous_output, args.output))
