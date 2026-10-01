"""Bridge the public material-analysis replay into Methods and Results.

Recorded tutorial prose, not a model-writing benchmark or a CFD validation.
"""

from __future__ import annotations

import argparse
import json
import runpy
from pathlib import Path

from cfdpaper.publication.manuscript import assemble_manuscript
from cfdpaper.publication.manuscript_seed import prepare_manuscript_seed
from cfdpaper.publication.section import export_section_docx


def save(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def run(output: Path) -> Path:
    """Reuse the existing calculation and bindings; require a fresh output directory."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    replay = runpy.run_path(str(Path(__file__).with_name("run_example.py")))
    replay["run"](output / "analysis", presentation="table")
    writing = output / "analysis/section-input/writing"
    results_input = json.loads((writing / "input.json").read_text(encoding="utf-8"))
    results_draft = json.loads(
        (output / "analysis/recorded-host-draft.json").read_text(encoding="utf-8")
    )
    results_id = results_input["section_id"]
    results_title = "Results of the synthetic wall partition"
    results_draft["title"] = results_title
    # Retain the generated Results input without rewriting any numeric evidence.
    methods_title = "Methods for the synthetic wall comparison"
    methods_input = {
        "section_id": "methods",
        "title": methods_title,
        "question": "Define the partition and mean flux before interpreting the integral.",
        "figures": [],
        "evidence": [
            {
                "id": "definitions",
                "kind": "observation",
                "text": "Complete wall partition and signed integrated heat-rate definitions.",
                "source": "sources/method.md:L1-L6",
            }
        ],
        "source_files": ["sources/method.md"],
        "duties": [
            {
                "purpose": "Define the supplied domain, sign and comparison basis.",
                "evidence_ids": ["definitions"],
                "figure_ids": [],
            }
        ],
    }
    methods_draft = {
        "title": methods_title,
        "paragraphs": [
            {
                "text": "This recorded tutorial uses invented data to demonstrate traceable "
                "document assembly, not simulated or measured results. Lower and upper regions "
                "are non-overlapping and exhaust the wetted wall. Region areas and integrated "
                "heat rates are summed within each configuration; heat entering the coolant is "
                "positive. Mean heat flux is defined by {{math:mean-flux}}, where Q is the "
                "summed heat rate and A is the summed area. Reference and Modified have the "
                "same stipulated inlet and wall boundary conditions, while geometry differs. "
                "The decomposition distinguishes area from average intensity but does not "
                "identify a causal flow mechanism.",
                "evidence_ids": ["definitions"],
                "figure_ids": [],
                "inline_math": {
                    "mean-flux": {
                        "kind": "row",
                        "children": [
                            {"kind": "overbar", "children": [{"kind": "symbol", "text": "q"}]},
                            {"kind": "text", "text": " = "},
                            {
                                "kind": "fraction",
                                "children": [
                                    {"kind": "symbol", "text": "Q"},
                                    {"kind": "symbol", "text": "A"},
                                ],
                            },
                        ],
                    }
                },
            }
        ],
        "captions": {},
        "image_observations": {},
        "evidence_notes": ["Recorded tutorial response; no solver verification is claimed."],
    }
    save(writing / "methods-input.json", methods_input)
    evidence_ids = [item["id"] for item in results_input["evidence"]]
    manifest = {
        "title": "Synthetic wall area and heat transfer tutorial",
        "context": "Recorded Methods and Results replay over public synthetic data. "
        "The example tests software connections, not autonomous scientific reasoning.",
        "spine": {
            "topic_id": "material-analysis-tutorial",
            "central_claim_id": "rate-Modified",
            "sections": [
                {
                    "section_id": "methods",
                    "title": methods_title,
                    "role": "methods",
                    "purpose": methods_input["question"],
                    "required_claim_ids": ["definitions"],
                },
                {
                    "section_id": results_id,
                    "title": results_title,
                    "role": "results",
                    "purpose": results_input["question"],
                    "required_claim_ids": evidence_ids,
                },
            ],
        },
        "sections": [
            {
                "section_id": "methods",
                "input": "analysis/section-input/writing/methods-input.json",
                "draft": "methods-draft.json",
            },
            {
                "section_id": results_id,
                "input": "analysis/section-input/writing/input.json",
                "draft": "results-draft.json",
                "depends_on": ["methods"],
            },
        ],
    }
    source = save(output / "outline.json", manifest)
    save(output / "methods-draft.json", methods_draft)
    save(output / "results-draft.json", results_draft)
    package = prepare_manuscript_seed(source, output / "workspace")
    candidate = assemble_manuscript(package, package / "drafts.json", output / "manuscript")
    return export_section_docx(candidate, output / "manuscript.docx", layout="near-reference")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="Fresh output directory; existing paths are refused"
    )
    print(run(parser.parse_args().output))
