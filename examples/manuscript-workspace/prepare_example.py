"""Three-section analytical tutorial, not a real CFD paper or a blind writing trial."""

# ruff: noqa: E501 -- Keep authored scientific prose readable as complete sentences.

from __future__ import annotations

import copy
import json
import runpy
import sys
from pathlib import Path


def prepare(root: Path) -> None:
    """Reuse the public pipe calculation; supply clearly labelled authored sample drafts."""
    script = Path(__file__).resolve().parents[1] / "section-writing/prepare_example.py"
    runpy.run_path(str(script))["prepare"](root)
    base = json.loads((root / "input.json").read_text(encoding="utf-8"))
    old_draft = json.loads((root / "sample-draft.json").read_text(encoding="utf-8"))
    sections = [
        ("methods", "1. Reference model and evaluation", "methods", [], ["model"]),
        (
            "hydraulics",
            "2. Hydraulic response",
            "results",
            ["1"],
            ["model", "pressure-trend", "dp-A", "dp-C"],
        ),
        (
            "thermal",
            "3. Thermal response and interpretation",
            "results",
            ["2"],
            ["model", "thermal-trend", "nu-A"],
        ),
    ]
    entries, contracts, drafts = [], [], {}
    for section_id, title, role, figures, evidence in sections:
        source = copy.deepcopy(base)
        source.update(section_id=section_id, title=title)
        source["figures"] = [fig for fig in source["figures"] if fig["id"] in figures]
        purpose = {
            "methods": "Define the analytical reference, physical assumptions and evaluated quantities without presenting numerical trends.",
            "hydraulics": "Explain the pressure-drop trend from the specified viscous-flow balance.",
            "thermal": "Explain why the selected thermal quantity is unchanged and distinguish this from overall cooling performance.",
        }[section_id]
        source["duties"] = [{"purpose": purpose, "evidence_ids": evidence, "figure_ids": figures}]
        source["question"] = purpose
        draft = {
            "title": title,
            "paragraphs": [],
            "captions": {},
            "evidence_notes": [],
            "image_observations": {},
            "tables": [],
            "equations": [],
        }
        if role == "methods":
            draft["paragraphs"] = [
                {
                    "text": "The reference considers steady, incompressible, fully developed laminar flow in a circular pipe with constant fluid properties and uniform wall heat flux. The analytical momentum balance in {{equation:1}} defines the pressure drop; μ, L, U and D denote dynamic viscosity, pipe length, mean velocity and diameter. {{table:1}} specifies the prescribed geometry, properties and velocity cases. Entry-region development and property variations are excluded. This tutorial uses analytical values rather than a solved CFD field.",
                    "evidence_ids": ["model"],
                    "figure_ids": [],
                }
            ]
            draft["equations"] = old_draft["equations"]
            draft["tables"] = [
                {
                    "table_id": "1",
                    "caption": "Prescribed analytical reference inputs.",
                    "columns": ["Quantity", "Value"],
                    "rows": [
                        ["Diameter (m)", "0.01"],
                        ["Length (m)", "1.0"],
                        ["Dynamic viscosity (Pa s)", "0.001"],
                        ["Density (kg m⁻³)", "1000"],
                        ["Mean velocity (m s⁻¹)", "0.02, 0.04, 0.06"],
                    ],
                    "after_section_id": section_id,
                    "evidence_ids": ["model"],
                    "column_widths_mm": [90, 70],
                    "numeric_columns": [],
                    "note": "Fixed properties and geometry; no mesh or convergence claim is made for an analytical reference.",
                }
            ]
        else:
            number = "1" if section_id == "hydraulics" else "2"
            text = (
                "In {{figure:1}}, the analytical pressure drop increases from {{value:dp-A}} to {{value:dp-C}} over the prescribed velocity cases. With geometry and viscosity fixed, the larger axial pressure gradient balances the increased viscous wall stress. The proportional response follows the fully developed momentum balance, rather than a change in flow regime."
                if section_id == "hydraulics"
                else "By contrast, {{figure:2}} gives a Nusselt number of {{value:nu-A}} for each prescribed case. Under the assumed uniform wall heat flux and constant properties, the thermally fully developed normalized profile is independent of bulk velocity. This explains why the thermal quantity remains unchanged while hydraulic resistance rises. It does not imply identical coolant temperature rise or general heat-exchanger performance."
            )
            draft["paragraphs"] = [{"text": text, "evidence_ids": evidence, "figure_ids": figures}]
            draft["captions"][number] = source["figures"][0]["caption"]
            # These are reference drafts, not claims that an automated image inspection ran.
            draft["image_observations"] = {number: "author-provided"}
        (root / f"{section_id}-input.json").write_text(
            json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (root / f"{section_id}-draft.json").write_text(
            json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        entries.append({"section_id": section_id, "input": f"{section_id}-input.json"})
        contracts.append(
            {
                "section_id": section_id,
                "title": title,
                "role": role,
                "purpose": purpose,
                "required_claim_ids": evidence,
                "required_figure_ids": figures,
            }
        )
        drafts[section_id] = f"{section_id}-draft.json"
    manifest = {
        "title": "Hydraulic and thermal responses of an analytical pipe reference",
        "context": "Public synthetic tutorial. Sample prose is supplied for integration testing, not generated or independently validated by the Agent.",
        "terms": {"Nu": "Nusselt number", "U": "prescribed mean velocity"},
        "spine": {
            "topic_id": "analytical-reference",
            "central_claim_id": "model",
            "sections": contracts,
        },
        "sections": entries,
    }
    (root / "manuscript-input.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (root / "drafts.json").write_text(json.dumps(drafts, indent=2), encoding="utf-8")


if __name__ == "__main__":
    prepare(Path(sys.argv[1]))
