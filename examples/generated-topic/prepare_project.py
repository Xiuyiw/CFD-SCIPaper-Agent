"""Prepare a synthetic project for the v0.2 topic-generation walkthrough."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cfdpaper.contracts import BoundaryRecord, CaseRecord, EvidenceRecord, QoIRecord
from cfdpaper.indexing import ProjectIndexer
from cfdpaper.state import initialize_project
from cfdpaper.storage import ProjectStore
from cfdpaper.topic_generation.models import make_qoi_definition_assessment
from cfdpaper.topic_generation.snapshot import (
    CaseNumericalAssessmentInput,
    NamedScalar,
    ScientificAssessmentSet,
)

SOURCE_URI = "structured-results.json"


def prepare_project(root: Path) -> None:
    """Create mature structured records; values are illustrative, not solver results."""
    root.mkdir(parents=True, exist_ok=True)
    source = root / SOURCE_URI
    source.write_text(
        json.dumps(
            {
                "mass_flow_kg_s": [1.0, 2.0, 3.0, 4.0],
                "hydraulic_diameter_m": [0.10, 0.10, 0.10, 0.10],
                "pressure_drop_pa": [10.0, 12.0, 14.0, 16.0],
                "flow_uniformity": [0.82, 0.85, 0.87, 0.88],
                "scaled_residual": [1.0e-6, 1.0e-6, 1.0e-6, 1.0e-6],
                "mass_out_kg_s": [0.999, 1.998, 2.997, 3.996],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    initialize_project(root, "generated-topic-example")
    store = ProjectStore.open(root)
    ProjectIndexer(store).inspect()
    source_hash = store.get_source(SOURCE_URI).sha256
    common = {"source_uri": SOURCE_URI, "source_hash": source_hash, "stale": False}

    for index, suffix in enumerate(("a", "b", "c", "d")):
        case_id = f"case-{suffix}"
        factor = float(index + 1)
        case_locator = f"$.mass_flow_kg_s[{index}]"
        qoi_locator = f"$.pressure_drop_pa[{index}]"

        store.save_case(
            CaseRecord(case_id=case_id, locator=case_locator, state="validated", **common)
        )
        for role, value, unit, parameter_id, locator in (
            ("varied", factor, "kg/s", "mass-flow", case_locator),
            (
                "controlled",
                0.10,
                "m",
                "hydraulic-diameter",
                f"$.hydraulic_diameter_m[{index}]",
            ),
        ):
            boundary_id = f"boundary-{role}-{suffix}"
            store.save_boundary(
                BoundaryRecord(
                    boundary_id=boundary_id,
                    case_id=case_id,
                    boundary_type=f"parameter:{role}",
                    values={parameter_id: value},
                    units={parameter_id: unit},
                    locator=locator,
                    **common,
                )
            )
            store.save_evidence(
                EvidenceRecord(
                    evidence_id=f"evidence-{boundary_id}",
                    kind="boundary",
                    summary=f"Structured {role} boundary for {case_id}.",
                    maturity="verified",
                    locator=locator,
                    **common,
                )
            )

        for qoi_key, qoi_name, values, unit, formula, locator in (
            (
                "pressure-drop",
                "pressure drop",
                (10.0, 12.0, 14.0, 16.0),
                "Pa",
                "p_in - p_out",
                qoi_locator,
            ),
            (
                "flow-uniformity",
                "flow uniformity",
                (0.82, 0.85, 0.87, 0.88),
                "1",
                "1 - area_weighted_velocity_deviation",
                f"$.flow_uniformity[{index}]",
            ),
        ):
            qoi_id = f"qoi-{qoi_key}-{suffix}"
            qoi_evidence_id = f"evidence-{qoi_key}-{suffix}"
            store.save_qoi(
                QoIRecord(
                    qoi_id=qoi_id,
                    case_id=case_id,
                    name=qoi_name,
                    value=values[index],
                    unit=unit,
                    definition=f"Structured definition for {qoi_name}.",
                    status="derived",
                    locator=locator,
                    **common,
                )
            )
            store.save_evidence(
                EvidenceRecord(
                    evidence_id=qoi_evidence_id,
                    kind="qoi",
                    summary=f"Structured {qoi_name} result for {case_id}.",
                    maturity="verified",
                    locator=locator,
                    **common,
                )
            )
            store.save_qoi_definition_assessment(
                make_qoi_definition_assessment(
                    qoi_id=qoi_id,
                    provenance_kind="structured-import",
                    source_uri=SOURCE_URI,
                    source_hash=source_hash,
                    source_locator=locator,
                    evidence_ids=(qoi_evidence_id,),
                    name=qoi_name,
                    unit=unit,
                    formula=formula,
                    spatial_scope="inlet and outlet planes",
                    reduction="area-weighted diagnostic",
                    temporal_scope="reported steady state",
                    producer_version="generated-topic-example 1.0",
                )
            )

        for kind, locator in (
            ("case", case_locator),
            ("convergence", f"$.scaled_residual[{index}]"),
            ("conservation", f"$.mass_out_kg_s[{index}]"),
        ):
            store.save_evidence(
                EvidenceRecord(
                    evidence_id=f"evidence-{kind}-{suffix}",
                    kind=kind,
                    summary=f"Structured {kind} evidence for {case_id}.",
                    maturity="verified",
                    locator=locator,
                    **common,
                )
            )

    store.save_scientific_assessment_set(
        ScientificAssessmentSet(
            cases=tuple(
                CaseNumericalAssessmentInput(
                    case_id=f"case-{suffix}",
                    residuals=(NamedScalar(name="scaled-residual", value=1.0e-6),),
                    residual_targets=(NamedScalar(name="scaled-residual", value=1.0e-5),),
                    qoi_relative_span=0.001,
                    conservation_inflow=float(index),
                    conservation_outflow=0.999 * float(index),
                    conservation_tolerance=0.01,
                    case_evidence_ids=(f"evidence-case-{suffix}",),
                    convergence_evidence_ids=(f"evidence-convergence-{suffix}",),
                    conservation_evidence_ids=(f"evidence-conservation-{suffix}",),
                    independent_validation_evidence_ids=(),
                    engineering_evidence_ids=(),
                    sensitivity_evidence_ids=(),
                )
                for index, suffix in enumerate(("a", "b", "c", "d"), start=1)
            )
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", type=Path)
    args = parser.parse_args()
    prepare_project(args.project_root.resolve())


if __name__ == "__main__":
    main()
