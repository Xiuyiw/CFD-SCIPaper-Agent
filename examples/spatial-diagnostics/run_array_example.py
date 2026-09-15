"""Replay explicit array/region definitions through the public analysis/writing API.

Synthetic piecewise-constant elements, not CFD results or an autonomous host run.
No intermediate CSV or external model is required.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from cfdpaper.analysis_suggestions import compile_analysis, prepare_analysis
from cfdpaper.publication.analysis_section import build_analysis_section
from cfdpaper.publication.section import assemble_section


def save(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    raw = output / "inputs"
    raw.mkdir()
    np.savez(raw / "wall.npz", temperature=[300.0, 320.0], area=[1.0, 3.0], overlap=[1.0, 0.25])
    (raw / "method.md").write_text(
        "Two disjoint synthetic wall elements have constant temperatures of 300 and 320 K.\n"
        "Their areas are 1 and 3 m2. Region R overlaps all of element 0 and one quarter of 1.\n"
        "The dimensionless overlap array supplies exact area fractions, not centroid flags.\n"
        "The complement uses 1 minus overlap. Sub-element variations are unresolved.\n",
        encoding="utf-8",
    )
    package = output / "materials"
    prepare_analysis(raw, package, question="Compare whole-wall, region and complement means.")
    calculations, metrics = [], []
    for name in ("whole", "region", "complement"):
        calc = dict(
            id=name,
            source="sources/wall.npz",
            operation="weighted_population",
            columns={"value": "temperature", "weight": "area"},
            units={"value": "K", "weight": "m2"},
            weight_kind="area",
            quantity_kind="absolute-temperature",
            domain=f"Synthetic wall: {name}",
            member_id=["__index__"],
            expected_members=[["0"], ["1"]],
            definition_source={"path": "sources/method.md", "locator": "L1-L4"},
            comparison={"status": "supported", "scope": "Same piecewise-constant wall field"},
            interpretation_limits=["No resolved sub-element temperature variation"],
        )
        if name != "whole":
            calc["region_fraction"] = "overlap"
            calc["region_complement"] = name == "complement"
        calculations.append(calc)
        metrics.append(
            dict(
                id=name,
                text=f"{name.capitalize()} area-weighted temperature",
                result_ref=dict(calculation_id=name, group="all", field="weighted_mean", places=3),
            )
        )
    candidate = dict(
        id="regional-temperature",
        title="Regional temperature contrast",
        question="How do regional temperatures combine into the whole-wall mean?",
        rationale="Compare disjoint region and complement with exact area-overlap weights.",
        presentation="table",
        calculations=calculations,
        metrics=metrics,
        interpretation_limits=["Synthetic element-constant field, not a transport mechanism"],
    )
    proposal = save(output / "proposal.json", {"candidates": [candidate]})
    compiled = compile_analysis(package, proposal, candidate["id"], output / "compiled")
    writing = build_analysis_section(compiled, output / "section-input")
    draft = dict(
        title=candidate["title"],
        paragraphs=[
            dict(
                text="The regional mean is {{value:region}}, compared with {{value:complement}} "
                "in its complement and {{value:whole}} over the whole wall ({{table:1}}). "
                "The region contains the cooler element and part of the warmer element; its "
                "complement contains only the warmer element. The whole-wall mean lies between "
                "the two regional means because they partition the same area-weighted field.",
                evidence_ids=["region", "complement", "whole"],
                figure_ids=[],
            )
        ],
        captions={},
        image_observations={},
        evidence_notes=[],
        tables=[
            dict(
                table_id="1",
                caption="Area-weighted temperatures in the prescribed wall field.",
                after_section_id=candidate["id"],
                columns=["Domain", "Mean temperature"],
                rows=[
                    [name.capitalize(), "{{value:" + name + "}}"]
                    for name in ("whole", "region", "complement")
                ],
                evidence_ids=["whole", "region", "complement"],
                column_widths_mm=[80, 80],
                numeric_columns=[1],
                note="Regional weights equal element area times the supplied overlap fraction. "
                "Temperatures are constant within each element.",
            )
        ],
    )
    return assemble_section(writing, save(output / "draft.json", draft), output / "section")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    print(run(parser.parse_args().output))
