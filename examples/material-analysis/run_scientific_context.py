"""Recorded tutorial: located methods and comparisons travel with the manuscript.

Reuses invented wall-partition data and existing calculations. No solver data,
model generation or independent scientific validation is claimed by this replay.
"""

from __future__ import annotations

import argparse
import json
import runpy
from pathlib import Path

from cfdpaper.publication.manuscript import assemble_manuscript, prepare_writing_context
from cfdpaper.publication.manuscript_seed import prepare_manuscript_seed
from cfdpaper.publication.section import export_section_docx


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    tutorial = runpy.run_path(str(Path(__file__).with_name("prepare_manuscript.py")))
    baseline = tutorial["run"](output / "recorded-base").parent / "manuscript"
    manifest = json.loads((baseline / "manuscript-input.json").read_text(encoding="utf-8"))
    source = baseline / "sections/methods/sources/method.md"
    lines = source.read_text(encoding="utf-8").splitlines()
    methods, results = (entry["section_id"] for entry in manifest["sections"])
    cases = ["Reference", "Modified"]

    def fact(identifier, name, text, line, **scope):
        return {
            "id": identifier,
            "case_ids": cases,
            "section_ids": [methods, results],
            "kind": "method",
            "name": name,
            "text": text,
            **scope,
            "source": {
                "path": "sections/methods/sources/method.md",
                "locator": f"L{line}",
                "excerpt": lines[line - 1],
            },
        }

    science = {
        "cases": [{"id": cid} for cid in cases],
        "facts": [
            fact(
                "partition",
                "Wall partition",
                "Lower and upper exhaust the wetted wall.",
                2,
                domain="complete wetted wall",
            ),
            fact(
                "operator",
                "Signed heat rate",
                "Region rates are integrals into the coolant.",
                3,
                domain="lower and upper wall regions",
                operator="signed regional integral",
            ),
            fact(
                "comparison", "Matched inputs", "Geometry differs at matched stipulated inputs.", 4
            ),
            {
                "id": "local-flow",
                "case_ids": cases,
                "section_ids": [results],
                "kind": "mechanism",
                "name": "Local flow redistribution",
                "status": "unknown",
                "text": "Rate and area tables do not establish a local flow mechanism.",
            },
        ],
        "comparisons": [
            {
                "id": "geometry",
                "case_ids": cases,
                "section_ids": [methods, results],
                "fact_ids": ["partition", "operator", "comparison"],
                "text": "Compare matched wall totals and area averages separately.",
            }
        ],
    }
    save(baseline / "science.json", science)
    manifest["scientific_context"] = str(baseline / "science.json")
    for entry in manifest["sections"]:
        entry["input"] = str(baseline / entry["input"])
        entry["draft"] = str(baseline / "sections" / entry["section_id"] / "draft.json")
    save(output / "outline.json", manifest)
    prepared = prepare_manuscript_seed(output / "outline.json", output / "prepared")
    prepare_writing_context(
        prepared, results, output / "results-task", drafts_path=prepared / "drafts.json"
    )
    candidate = assemble_manuscript(prepared, prepared / "drafts.json", output / "candidate")
    export_section_docx(candidate, output / "manuscript.docx", layout="near-reference")
    return candidate


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(run(parser.parse_args().output))
