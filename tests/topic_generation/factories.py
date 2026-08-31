from __future__ import annotations

from pathlib import Path

from cfdpaper.contracts import (
    BoundaryRecord,
    CaseRecord,
    ClaimRecord,
    EvidenceRecord,
    FieldRecord,
    MeshRecord,
    QoIRecord,
)
from cfdpaper.indexing import ProjectIndexer
from cfdpaper.state import initialize_project
from cfdpaper.storage import ProjectStore
from cfdpaper.topic_generation.models import make_qoi_definition_assessment
from cfdpaper.topic_generation.snapshot import (
    CaseNumericalAssessmentInput,
    NamedScalar,
    ScientificAssessmentSet,
)

SOURCE_URI = "scientific-input.json"


def populated_scientific_store(tmp_path: Path, *, save_qoi_definition: bool = True) -> ProjectStore:
    source = tmp_path / SOURCE_URI
    source.write_text('{"parameter": [1.0, 2.0], "response": [10.0, 12.0]}\n', encoding="utf-8")
    initialize_project(tmp_path, "snapshot-project")
    store = ProjectStore.open(tmp_path)
    ProjectIndexer(store).inspect()
    source_hash = store.get_source(SOURCE_URI).sha256

    for index, suffix in enumerate(("a", "b"), start=1):
        case_id = f"case-{suffix}"
        common = {
            "source_uri": SOURCE_URI,
            "source_hash": source_hash,
            "stale": False,
        }
        store.save_case(
            CaseRecord(
                case_id=case_id,
                locator=f"$.parameter[{index - 1}]",
                state="validated",
                **common,
            )
        )
        store.save_boundary(
            BoundaryRecord(
                boundary_id=f"boundary-{suffix}",
                case_id=case_id,
                boundary_type="parameter-input",
                values={"parameter": float(index)},
                units={"parameter": "kg/s"},
                locator=f"$.parameter[{index - 1}]",
                **common,
            )
        )
        store.save_mesh(
            MeshRecord(
                mesh_id=f"mesh-{suffix}",
                case_id=case_id,
                cell_count=1000 * index,
                node_count=1200 * index,
                quality={"quality_parameter": 0.8 + index / 100},
                locator=f"$.parameter[{index - 1}]",
                **common,
            )
        )
        store.save_field(
            FieldRecord(
                field_id=f"field-{suffix}",
                case_id=case_id,
                variable="response",
                unit="Pa",
                location="measurement-plane",
                locator=f"$.response[{index - 1}]",
                **common,
            )
        )
        qoi_id = f"qoi-{suffix}"
        qoi_locator = f"$.response[{index - 1}]"
        store.save_qoi(
            QoIRecord(
                qoi_id=qoi_id,
                case_id=case_id,
                name=f"Response {suffix.upper()}",
                value=8.0 + 2.0 * index,
                unit="Pa",
                definition=(
                    "formula=response_out-response_in; scope=measurement planes; "
                    "reduction=area-weighted difference; time=reported state"
                ),
                status="derived",
                locator=qoi_locator,
                **common,
            )
        )
        evidence_ids = {
            "case": f"evidence-case-{suffix}",
            "residual": f"evidence-residual-{suffix}",
            "qoi": f"evidence-qoi-{suffix}",
            "conservation": f"evidence-conservation-{suffix}",
        }
        for kind, evidence_id in evidence_ids.items():
            locator = qoi_locator if kind == "qoi" else f"$.{kind}[{index - 1}]"
            store.save_evidence(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    kind=(
                        "case"
                        if kind == "case"
                        else "qoi"
                        if kind == "qoi"
                        else "convergence"
                        if kind == "residual"
                        else "conservation"
                    ),
                    summary=f"Current {kind} evidence for {case_id}.",
                    maturity="verified",
                    locator=locator,
                    **common,
                )
            )
        store.save_claim(
            ClaimRecord(
                claim_id=f"claim-{suffix}",
                text=f"Response evidence is available for {case_id}.",
                status="supported",
                evidence_ids=[evidence_ids["qoi"]],
            )
        )
        if save_qoi_definition:
            store.save_qoi_definition_assessment(
                make_qoi_definition_assessment(
                    qoi_id=qoi_id,
                    provenance_kind="structured-import",
                    source_uri=SOURCE_URI,
                    source_hash=source_hash,
                    source_locator=qoi_locator,
                    evidence_ids=(evidence_ids["qoi"],),
                    name=f"Response {suffix.upper()}",
                    unit="Pa",
                    formula="response_out - response_in",
                    spatial_scope="measurement planes",
                    reduction="area-weighted difference",
                    temporal_scope="reported state",
                    producer_version="structured-import 1.0",
                )
            )

    store.save_scientific_assessment_set(
        ScientificAssessmentSet(
            cases=tuple(
                CaseNumericalAssessmentInput(
                    case_id=f"case-{suffix}",
                    residuals=(NamedScalar(name="response", value=1.0e-6 * index),),
                    residual_targets=(NamedScalar(name="response", value=1.0e-5),),
                    qoi_relative_span=0.01 * index,
                    conservation_inflow=10.0 * index,
                    conservation_outflow=9.99 * index,
                    conservation_tolerance=0.01,
                    case_evidence_ids=(f"evidence-case-{suffix}",),
                    convergence_evidence_ids=(f"evidence-residual-{suffix}",),
                    conservation_evidence_ids=(f"evidence-conservation-{suffix}",),
                    independent_validation_evidence_ids=(f"evidence-qoi-{suffix}",),
                    engineering_evidence_ids=(f"evidence-conservation-{suffix}",),
                    sensitivity_evidence_ids=(f"evidence-residual-{suffix}",),
                )
                for index, suffix in enumerate(("a", "b"), start=1)
            )
        )
    )
    return store


def mature_ordered_scientific_store(tmp_path: Path) -> ProjectStore:
    """Persist one complete, public three-case ordered-response fixture."""

    source = tmp_path / SOURCE_URI
    source.write_text(
        "{"
        '"parameter": [1.0, 2.0, 3.0], '
        '"factor": [1.0, 2.0, 3.0], '
        '"control": [1.0, 1.0, 1.0], '
        '"response": [10.0, 12.0, 14.0], '
        '"convergence": [0.000001, 0.000001, 0.000001], '
        '"conservation": [0.999, 0.999, 0.999]'
        "}\n",
        encoding="utf-8",
    )
    initialize_project(tmp_path, "mature-ordered-project")
    store = ProjectStore.open(tmp_path)
    ProjectIndexer(store).inspect()
    source_hash = store.get_source(SOURCE_URI).sha256
    common = {"source_uri": SOURCE_URI, "source_hash": source_hash, "stale": False}

    for index, suffix in enumerate(("a", "b", "c")):
        case_id = f"case-{suffix}"
        case_locator = f"$.parameter[{index}]"
        qoi_locator = f"$.response[{index}]"
        store.save_case(
            CaseRecord(case_id=case_id, locator=case_locator, state="validated", **common)
        )
        for role, value, unit in (
            ("factor", float(index + 1), "kg/s"),
            ("control", 1.0, "m/s"),
        ):
            locator = f"$.{role}[{index}]"
            boundary_type = "parameter:varied" if role == "factor" else "parameter:controlled"
            parameter_id = "parameter-varied" if role == "factor" else "parameter-control"
            store.save_boundary(
                BoundaryRecord(
                    boundary_id=f"boundary-{role}-{suffix}",
                    case_id=case_id,
                    boundary_type=boundary_type,
                    values={parameter_id: value},
                    units={parameter_id: unit},
                    locator=locator,
                    **common,
                )
            )
            store.save_evidence(
                EvidenceRecord(
                    evidence_id=f"evidence-boundary-{role}-{suffix}",
                    kind="boundary",
                    summary=f"Bound {role} parameter for {case_id}.",
                    maturity="verified",
                    locator=locator,
                    **common,
                )
            )
        qoi_id = f"qoi-response-{suffix}"
        store.save_qoi(
            QoIRecord(
                qoi_id=qoi_id,
                case_id=case_id,
                name="response",
                value=10.0 + 2.0 * index,
                unit="Pa",
                definition="Human-readable only; structured definition is stored separately.",
                status="derived",
                locator=qoi_locator,
                **common,
            )
        )
        store.save_evidence(
            EvidenceRecord(
                evidence_id=f"evidence-qoi-{suffix}",
                kind="qoi",
                summary=f"Structured response for {case_id}.",
                maturity="verified",
                locator=qoi_locator,
                **common,
            )
        )
        store.save_qoi_definition_assessment(
            make_qoi_definition_assessment(
                qoi_id=qoi_id,
                provenance_kind="structured-import",
                source_uri=SOURCE_URI,
                source_hash=source_hash,
                source_locator=qoi_locator,
                evidence_ids=(f"evidence-qoi-{suffix}",),
                name="response",
                unit="Pa",
                formula="response_out - response_in",
                spatial_scope="measurement planes",
                reduction="area-weighted difference",
                temporal_scope="reported state",
                producer_version="public-fixture 1.0",
            )
        )
        for kind, locator in (
            ("case", case_locator),
            ("convergence", f"$.convergence[{index}]"),
            ("conservation", f"$.conservation[{index}]"),
        ):
            store.save_evidence(
                EvidenceRecord(
                    evidence_id=f"evidence-{kind}-{suffix}",
                    kind=kind,
                    summary=f"Current {kind} evidence for {case_id}.",
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
                    residuals=(NamedScalar(name="response", value=1.0e-6),),
                    residual_targets=(NamedScalar(name="response", value=1.0e-5),),
                    qoi_relative_span=0.001,
                    conservation_inflow=10.0,
                    conservation_outflow=9.99,
                    conservation_tolerance=0.01,
                    case_evidence_ids=(f"evidence-case-{suffix}",),
                    convergence_evidence_ids=(f"evidence-convergence-{suffix}",),
                    conservation_evidence_ids=(f"evidence-conservation-{suffix}",),
                    independent_validation_evidence_ids=(),
                    engineering_evidence_ids=(),
                    sensitivity_evidence_ids=(),
                )
                for suffix in ("a", "b", "c")
            )
        )
    )
    return store
