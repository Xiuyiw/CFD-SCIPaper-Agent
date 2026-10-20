"""Portable author-return replay using public analytical pipe values.

The supplied prose and scripted edits are an automation demonstration, not a
new host-AI writing attempt or a human scientific approval.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from cfdpaper.publication.author_workspace import (
    import_author_manuscript,
    prepare_author_manuscript,
)
from cfdpaper.publication.formal_export import export_formal_manuscript
from cfdpaper.publication.manuscript import assemble_manuscript, prepare_manuscript
from cfdpaper.publication.word_return import read_word_return


def save(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def pressure_rows(path: Path, viscosity: float) -> None:
    """Steady fully developed pipe reference, D=0.01 m and L=1 m."""
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["case", "velocity_m_s", "pressure_drop_Pa"])
        for case, velocity in (("A", 0.02), ("B", 0.04), ("C", 0.06)):
            writer.writerow([case, velocity, 32 * viscosity * velocity / 0.01**2])


def prepare_source(root: Path) -> Path:
    root.mkdir()
    (root / "sources").mkdir()
    pressure_rows(root / "sources/pressure.csv", 0.001)
    (root / "sources/method.md").write_text(
        "Analytical tutorial, not solved CFD. Steady incompressible fully developed "
        "laminar circular-pipe flow with constant properties. D=0.01 m, L=1 m, "
        "mu=0.001 Pa s; Delta p=32 mu L U / D^2. Each row is one prescribed case.\n",
        encoding="utf-8",
    )
    sections, contracts, drafts = [], [], {}
    for sid, role, title in (
        ("methods", "methods", "1. Analytical model"),
        ("response", "results", "2. Pressure response"),
    ):
        evidence = [
            {
                "id": "model",
                "kind": "interpretation",
                "text": "Fully developed constant-property laminar pipe reference.",
                "source": "sources/method.md:L1",
            }
        ]
        for case in ("A", "C"):
            evidence.append(
                {
                    "id": "dp-" + case,
                    "kind": "metric",
                    "text": "Analytical pressure drop in case " + case,
                    "source": "sources/pressure.csv: case " + case,
                    "result_ref": {
                        "calculation_id": "pressure",
                        "group": case,
                        "field": "mean",
                        "places": 2,
                    },
                }
            )
        purpose = (
            "Define the model and its assumptions."
            if sid == "methods"
            else "Explain the pressure response within the prescribed laminar reference."
        )
        claim_ids = [item["id"] for item in evidence]
        save(
            root / f"{sid}-input.json",
            {
                "section_id": sid,
                "title": title,
                "question": purpose,
                "context": "Public analytical tutorial, not CFD or experimental validation.",
                "source_files": ["sources/pressure.csv", "sources/method.md"],
                "figures": [],
                "evidence": evidence,
                "table_calculations": [
                    {
                        "id": "pressure",
                        "source": "sources/pressure.csv",
                        "operation": "population",
                        "columns": {"value": "pressure_drop_Pa"},
                        "units": {"value": "Pa"},
                        "domain": "One analytical pressure-drop row per prescribed case.",
                        "group_by": "case",
                    }
                ],
                "duties": [{"purpose": purpose, "evidence_ids": claim_ids, "figure_ids": []}],
            },
        )
        text = (
            "The analytical reference assumes steady incompressible fully developed laminar "
            "flow in a circular pipe with constant properties. The prescribed diameter is "
            "0.01 m and the length is 1 m. {{equation:balance}} gives the pressure "
            "drop, where mu is dynamic viscosity, L is pipe length, U is mean velocity "
            "and D is pipe diameter. Entry effects and property variations are excluded."
            if sid == "methods"
            else "For the prescribed cases, the analytical pressure drop rises from "
            "{{value:dp-A}} to {{value:dp-C}}. With geometry and viscosity fixed, the "
            "larger axial pressure gradient balances the increased viscous wall stress. "
            "{{table:pressures}} gives the selected endpoint values. This linear "
            "response does not demonstrate the performance of an entrance-region flow."
        )
        draft = {
            "title": title,
            "paragraphs": [{"text": text, "evidence_ids": claim_ids, "figure_ids": []}],
            "captions": {},
            "tables": [],
            "equations": [],
            "evidence_notes": [],
            "image_observations": {},
        }
        if sid == "methods":
            draft["equations"] = [
                {
                    "equation_id": "balance",
                    "evidence_ids": ["model"],
                    "expression": {
                        "kind": "row",
                        "children": [
                            {"kind": "symbol", "text": "Δp"},
                            {"kind": "text", "text": " = "},
                            {
                                "kind": "fraction",
                                "children": [
                                    {"kind": "symbol", "text": "32μLU"},
                                    {
                                        "kind": "sup",
                                        "children": [
                                            {"kind": "symbol", "text": "D"},
                                            {"kind": "text", "text": "2"},
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                }
            ]
        else:
            draft["tables"] = [
                {
                    "table_id": "pressures",
                    "caption": "Analytical endpoint pressure drops.",
                    "columns": ["Case", "Pressure drop"],
                    "rows": [[case, "{{value:dp-" + case + "}}"] for case in ("A", "C")],
                    "evidence_ids": ["dp-A", "dp-C"],
                    "after_section_id": sid,
                    "numeric_columns": [1],
                    "column_widths_mm": [35, 95],
                }
            ]
        save(root / f"{sid}-draft.json", draft)
        sections.append({"section_id": sid, "input": f"{sid}-input.json"})
        contracts.append(
            {
                "section_id": sid,
                "title": title,
                "role": role,
                "purpose": purpose,
                "required_claim_ids": claim_ids,
                "required_figure_ids": [],
            }
        )
        drafts[sid] = f"{sid}-draft.json"
    save(root / "drafts.json", drafts)
    return save(
        root / "manuscript-input.json",
        {
            "title": "Pressure response in a fully developed pipe reference",
            "context": "Public analytical author-collaboration replay with supplied prose.",
            "spine": {
                "topic_id": "pipe-reference",
                "central_claim_id": "model",
                "sections": contracts,
            },
            "sections": sections,
        },
    )


def automation_edit(original: Path, returned: Path) -> None:
    """Add one prose edit and one comment; do not call this a human edit."""
    doc = Document(original)
    text = next(
        node
        for node in doc._element.iter(qn("w:t"))
        if node.text and "For the prescribed cases, " in node.text
    )
    text.text = text.text.replace("For the prescribed cases, ", "Across the prescribed cases, ", 1)
    run = text.getparent()
    for tag, insert in (("commentRangeStart", run.addprevious), ("commentRangeEnd", run.addnext)):
        marker = OxmlElement("w:" + tag)
        marker.set(qn("w:id"), "0")
        insert(marker)
    ref_run, ref = OxmlElement("w:r"), OxmlElement("w:commentReference")
    ref.set(qn("w:id"), "0")
    ref_run.append(ref)
    run.getnext().addnext(ref_run)
    comments, comment = OxmlElement("w:comments"), OxmlElement("w:comment")
    comment.set(qn("w:id"), "0")
    comment.set(qn("w:author"), "Automation example")
    paragraph, comment_run, comment_text = (
        OxmlElement("w:p"),
        OxmlElement("w:r"),
        OxmlElement("w:t"),
    )
    comment_text.text = "Check the explanation after the source update. Automation example only."
    comment_run.append(comment_text)
    paragraph.append(comment_run)
    comment.append(paragraph)
    comments.append(comment)
    part = Part(
        PackURI("/word/comments.xml"),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml",
        etree.tostring(comments),
        doc.part.package,
    )
    doc.part.relate_to(part, RT.COMMENTS)
    doc.save(returned)


def run(output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=False)
    inputs = prepare_source(output / "inputs")
    prepared = prepare_manuscript(inputs, output / "prepared")
    baseline = assemble_manuscript(prepared, inputs.parent / "drafts.json", output / "baseline")
    author = prepare_author_manuscript(baseline, output / "author")
    edited = output / "automation-return.docx"
    automation_edit(author / "manuscript.docx", edited)

    # Separate current-source change while the saved author baseline stays intact.
    # This is a numerical input correction, not a change of operator or domain.
    for sid in ("methods", "response"):
        pressure_rows(author / f"candidate/sections/{sid}/sources/pressure.csv", 0.0011)
        method = author / f"candidate/sections/{sid}/sources/method.md"
        method.write_text(
            method.read_text(encoding="utf-8").replace("mu=0.001 Pa s", "mu=0.0011 Pa s"),
            encoding="utf-8",
        )
    current = assemble_manuscript(
        author / "candidate", author / "candidate/drafts.json", output / "current"
    )
    recovered = import_author_manuscript(edited, current, output / "recovered")
    report = json.loads((recovered / "merge.json").read_text(encoding="utf-8"))
    if report["conflicts"]:
        raise RuntimeError(f"Unexpected merge conflicts; inspect {recovered / 'merge.json'}")
    final = read_word_return(recovered / "manuscript.docx")
    if final["conflicts"] or len(final["comments"]) != 1:
        raise RuntimeError("Returned text/comment anchors were not preserved")
    response = next(
        b for b in final["blocks"] if b["kind"] == "paragraph" and b["section_id"] == "response"
    )
    if "Across the prescribed cases" not in response["rendered_text"]:
        raise RuntimeError("Automation prose edit did not survive")
    if "7.04" not in response["rendered_text"] or "21.12" not in response["rendered_text"]:
        raise RuntimeError("New source values were not bound into the returned prose")
    for profile, extension in (("report", "docx"), ("research", "md"), ("conference", "tex")):
        export_formal_manuscript(
            recovered / "candidate", output / f"{profile}.{extension}", profile=profile
        )
    save(
        output / "example-result.json",
        {
            "scenario": "scripted-automation-replay",
            "human_author_approval": False,
            "conflicts": report["conflicts"],
            "scientific_changes": report["scientific_changes"],
            "comments": len(final["comments"]),
            "old_endpoint_pressure_Pa": [6.4, 19.2],
            "current_endpoint_pressure_Pa": [7.04, 21.12],
        },
    )
    return recovered / "manuscript.docx"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New output directory")
    args = parser.parse_args()
    print(run(args.output.resolve()))
