"""Seven-section analytical software tutorial with local literature and owner bindings."""

# ruff: noqa: E501 -- Authored sample prose is kept as complete sentences.

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare(root: Path) -> None:
    """Generate a fresh source directory, retaining the existing reference calculations."""
    root = Path(root)
    script = Path(__file__).resolve().parents[1] / "manuscript-workspace/prepare_example.py"
    runpy.run_path(str(script))["prepare"](root)
    manifest = _read(root / "manuscript-input.json")
    drafts = _read(root / "drafts.json")
    entries = {entry["section_id"]: entry for entry in manifest["sections"]}
    contracts = {entry["section_id"]: entry for entry in manifest["spine"]["sections"]}

    # Keep the original three sections, table, equation and plots; titles need no literal numbering.
    for sid, title in (
        ("methods", "Reference model and evaluation"),
        ("hydraulics", "Hydraulic response"),
        ("thermal", "Thermal response and interpretation"),
    ):
        for suffix in ("input", "draft"):
            path = root / f"{sid}-{suffix}.json"
            data = _read(path)
            data["title"] = title
            _write(path, data)
        contracts[sid]["title"] = title
    entries["hydraulics"]["depends_on"] = ["methods"]
    entries["thermal"]["depends_on"] = ["methods"]

    bindings = {
        "dp-first": "hydraulics/dp-A",
        "dp-last": "hydraulics/dp-C",
        "nu-reference": "thermal/nu-A",
        "model-scope": "methods/model",
    }
    # Check the inherited evidence IDs instead of relying on a guessed or copied numeric value.
    for target in bindings.values():
        sid, eid = target.split("/")
        assert eid in {e["id"] for e in _read(root / f"{sid}-input.json")["evidence"]}

    library_dir = root / "literature"
    library_dir.mkdir()
    model_excerpt = (
        "This software example specifies steady, incompressible, fully developed laminar flow "
        "in a circular pipe with constant properties. Its pressure drop is assigned by "
        "Delta p = 32 mu L U / D^2. Under thermally fully developed uniform wall heat flux, "
        "the example assigns Nu = 4.36 at every prescribed velocity."
    )
    scope_excerpt = (
        "The pressure response and the Nusselt number describe different quantities under "
        "the stated assumptions. A larger pressure drop alongside unchanged Nu is compatible "
        "with this analytical construction and is not a general ranking of cooling performance. "
        "The example contains no solved CFD field or experiment and makes no novelty claim."
    )
    (library_dir / "analytical-note.md").write_text(
        "# Analytical reference note supplied with the software example\n\n"
        "This is a local explanatory note, not a published research article.\n\n"
        "## Model definition\n\n" + model_excerpt + "\n\n"
        "## Interpretation scope\n\n" + scope_excerpt + "\n",
        encoding="utf-8",
    )
    _write(
        library_dir / "references.json",
        [
            {
                "id": "analytical-note",
                "type": "report",
                "title": "Analytical reference note supplied with the software example",
                "genre": "Local software-example note, not a published paper",
            }
        ],
    )
    supports = []
    for sid, eid, excerpt, locator, claim, role in (
        (
            "introduction",
            "model-note",
            model_excerpt,
            "Model definition, paragraph 1",
            "The example prescribes pressure drop and Nu using its stated fully developed model.",
            "model basis",
        ),
        (
            "introduction",
            "scope-note",
            scope_excerpt,
            "Interpretation scope, paragraph 1",
            "The tutorial examines compatible hydraulic and thermal responses, not a new scientific gap.",
            "background and scope",
        ),
        (
            "discussion",
            "scope-note",
            scope_excerpt,
            "Interpretation scope, paragraph 1",
            "Unchanged Nu does not establish unchanged overall cooling performance.",
            "interpretation boundary",
        ),
    ):
        supports.append(
            {
                "section_id": sid,
                "evidence_id": eid,
                "reference_id": "analytical-note",
                "source": "analytical-note.md",
                "locator": locator,
                "excerpt": excerpt,
                "claim": claim,
                "role": role,
                "status": "supported",
            }
        )
    _write(
        library_dir / "literature.json", {"bibliography": "references.json", "supports": supports}
    )

    new_sections = [
        (
            "abstract",
            "Abstract",
            "Summarize the model-specific question, results and implication without adding new findings.",
            ["hydraulics", "thermal", "discussion"],
            bindings,
            [
                (
                    "Hydraulic and thermal metrics need not respond alike to a change in prescribed flow. This analytical software tutorial compares a circular-pipe reference at fixed geometry and properties under fully developed laminar flow and uniform wall heat flux. Across the prescribed velocity cases, pressure drop increases from {{value:dp-first}} to {{value:dp-last}}, whereas the Nusselt number remains {{value:nu-reference}}. The pressure response follows the viscous momentum balance; the unchanged thermal metric follows the imposed fully developed heat-transfer model. Their coexistence demonstrates why a hydraulic trend alone cannot rank thermal performance outside these assumptions.",
                    list(bindings),
                ),
            ],
        ),
        (
            "introduction",
            "Introduction",
            "Introduce the tutorial question and its analytical scope without inventing a literature gap or novelty claim.",
            ["methods"],
            {},
            [
                (
                    "Interpreting transport results requires distinguishing the physical quantities being compared. The accompanying analytical note specifies a fixed-property circular-pipe model in which the pressure drop depends on prescribed mean velocity, while the fully developed Nusselt number is assigned independently of that velocity {{cite:model-note}}. The useful question here is how these different responses can coexist within the same model, rather than whether one metric alone indicates better cooling.",
                    ["model-note"],
                ),
                (
                    "This tutorial addresses that question through the model definition, separate hydraulic and thermal results, and their joint interpretation. It uses a known analytical construction to demonstrate evidence-linked manuscript assembly, not to claim an unresolved literature gap, a new transport mechanism or independent CFD validation {{cite:scope-note}}.",
                    ["scope-note"],
                ),
            ],
        ),
        (
            "discussion",
            "Discussion",
            "Explain the complementary responses and their interpretation boundary using current Results and the supplied note.",
            ["methods", "hydraulics", "thermal"],
            bindings,
            [
                (
                    "The pressure-drop change from {{value:dp-first}} to {{value:dp-last}} and the unchanged Nusselt number of {{value:nu-reference}} answer different questions. With the dimensions and viscosity fixed, the momentum balance in {{equation:methods/1}} relates greater prescribed velocity to a larger pressure gradient. The thermal result instead follows a fully developed normalized temperature profile under uniform wall heat flux. The two results are therefore compatible, rather than evidence of a transition between flow regimes.",
                    list(bindings),
                ),
                (
                    "The scope of this comparison follows the supplied analytical note {{cite:scope-note}}: it does not determine coolant temperature rise, entrance-region behavior or whole-device performance. Those questions require additional quantities or a different model. The joint reading is useful because it identifies which assumption controls each reported response without treating the note as independent validation of the example.",
                    ["model-scope", "scope-note"],
                ),
            ],
        ),
        (
            "conclusion",
            "Conclusions",
            "Answer the stated question using the established results and maintain the model-specific claim boundary.",
            ["hydraulics", "thermal", "discussion"],
            bindings,
            [
                (
                    "Within the prescribed analytical reference, pressure drop rises from {{value:dp-first}} to {{value:dp-last}}, while the Nusselt number remains {{value:nu-reference}}. The former reflects the velocity-dependent viscous momentum balance; the latter is constrained by the assumed fully developed uniform-heat-flux model. Thus, different hydraulic and thermal responses do not by themselves conflict. Their definitions and assumptions must be read together before drawing a performance conclusion.",
                    list(bindings),
                ),
            ],
        ),
    ]
    for sid, title, purpose, dependencies, section_bindings, paragraphs in new_sections:
        ids = list(dict.fromkeys(eid for _, evidence_ids in paragraphs for eid in evidence_ids))
        section = {
            "section_id": sid,
            "title": title,
            "question": purpose,
            "context": "Public analytical software tutorial with static authored sample prose; no new CFD solution, blind-writing result or research novelty is claimed.",
            "figures": [],
            "evidence": [],
            "duties": [{"purpose": purpose, "evidence_ids": ids, "figure_ids": []}],
        }
        draft = {
            "title": title,
            "paragraphs": [
                {"text": text, "evidence_ids": evidence_ids, "figure_ids": []}
                for text, evidence_ids in paragraphs
            ],
            "captions": {},
            "image_observations": {},
            "tables": [],
            "equations": [],
            "evidence_notes": [
                "Authored software-example draft. The local analytical note is not external literature validation. Source bindings update numbers; a host must reconsider interpretations after source changes."
            ],
        }
        _write(root / f"{sid}-input.json", section)
        _write(root / f"{sid}-draft.json", draft)
        entries[sid] = {
            "section_id": sid,
            "input": f"{sid}-input.json",
            "depends_on": dependencies,
            "evidence_bindings": section_bindings,
        }
        contracts[sid] = {
            "section_id": sid,
            "title": title,
            "role": sid,
            "purpose": purpose,
            "required_claim_ids": ids,
            "required_figure_ids": [],
        }
        drafts[sid] = f"{sid}-draft.json"

    order = [
        "abstract",
        "introduction",
        "methods",
        "hydraulics",
        "thermal",
        "discussion",
        "conclusion",
    ]
    manifest["title"] = "Compatible hydraulic and thermal responses in an analytical pipe reference"
    manifest["keywords"] = [
        "analytical reference",
        "laminar pipe flow",
        "source-bound writing",
        "software tutorial",
    ]
    manifest["context"] = (
        "Seven-section public analytical software example. The supplied static sample drafts are not an AI blind-writing trial or a publication-ready research paper. The shared analytical note is part of this example, not a published source."
    )
    manifest["literature"] = "literature/literature.json"
    manifest["sections"] = [entries[sid] for sid in order]
    manifest["spine"]["sections"] = [contracts[sid] for sid in order]
    _write(root / "manuscript-input.json", manifest)
    _write(root / "drafts.json", {sid: drafts[sid] for sid in order})


if __name__ == "__main__":
    prepare(Path(sys.argv[1]))
