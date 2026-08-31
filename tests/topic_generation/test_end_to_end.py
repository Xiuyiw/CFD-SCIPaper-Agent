from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from cfdpaper.cli import app
from cfdpaper.contracts import BoundaryRecord, CaseRecord, EvidenceRecord, QoIRecord
from cfdpaper.indexing import ProjectIndexer
from cfdpaper.planning import CandidateInput
from cfdpaper.state import initialize_project
from cfdpaper.storage import ProjectStore
from cfdpaper.topic_generation.models import make_qoi_definition_assessment
from cfdpaper.topic_generation.snapshot import (
    CaseNumericalAssessmentInput,
    NamedScalar,
    ScientificAssessmentSet,
)

_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "topic_generation"
_REQUIRED_EVIDENCE_KINDS = {
    "boundary",
    "case",
    "conservation",
    "convergence",
    "qoi",
}


def _load_fixture(name: str) -> dict[str, object]:
    return json.loads((_FIXTURE_ROOT / name).read_text("utf-8"))


def _install_mature_public_fixture(root: Path) -> ProjectStore:
    fixture = _load_fixture("mature_project.json")
    source_uri = str(fixture["source_uri"])
    source_payload = fixture["source"]
    assert isinstance(source_payload, dict)
    root.joinpath(source_uri).write_text(
        json.dumps(source_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    initialize_project(root, str(fixture["project_id"]))
    store = ProjectStore.open(root)
    ProjectIndexer(store).inspect()
    source_hash = store.get_source(source_uri).sha256
    common = {"source_uri": source_uri, "source_hash": source_hash, "stale": False}
    varied = source_payload["varied"]
    controlled = source_payload["controlled"]
    primary = source_payload["primary_response"]
    secondary = source_payload["secondary_response"]
    residual = source_payload["residual"]
    conservation = source_payload["conservation"]
    assert all(
        isinstance(values, list)
        for values in (varied, controlled, primary, secondary, residual, conservation)
    )
    assessments = []
    for index, suffix in enumerate(("a", "b", "c", "d")):
        case_id = f"case-{suffix}"
        case_locator = f"$.varied[{index}]"
        store.save_case(
            CaseRecord(case_id=case_id, locator=case_locator, state="validated", **common)
        )
        for role, values, unit in (
            ("varied", varied, "kg/s"),
            ("controlled", controlled, "m/s"),
        ):
            parameter_id = f"parameter-{role}"
            locator = f"$.{role}[{index}]"
            store.save_boundary(
                BoundaryRecord(
                    boundary_id=f"boundary-{role}-{suffix}",
                    case_id=case_id,
                    boundary_type=f"parameter:{role}",
                    values={parameter_id: float(values[index])},
                    units={parameter_id: unit},
                    locator=locator,
                    **common,
                )
            )
            store.save_evidence(
                EvidenceRecord(
                    evidence_id=f"evidence-boundary-{role}-{suffix}",
                    kind="boundary",
                    summary=f"Current {role} parameter evidence for {case_id}.",
                    maturity="verified",
                    locator=locator,
                    **common,
                )
            )
        for name, values in (("primary-response", primary), ("secondary-response", secondary)):
            qoi_id = f"qoi-{name}-{suffix}"
            locator = f"$.{name.replace('-', '_')}[{index}]"
            evidence_id = f"evidence-{name}-{suffix}"
            store.save_qoi(
                QoIRecord(
                    qoi_id=qoi_id,
                    case_id=case_id,
                    name=name,
                    value=float(values[index]),
                    unit="Pa",
                    definition=(
                        "Human-readable definition; structured definition is stored separately."
                    ),
                    status="derived",
                    locator=locator,
                    **common,
                )
            )
            store.save_evidence(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    kind="qoi",
                    summary=f"Current {name} evidence for {case_id}.",
                    maturity="verified",
                    locator=locator,
                    **common,
                )
            )
            store.save_qoi_definition_assessment(
                make_qoi_definition_assessment(
                    qoi_id=qoi_id,
                    provenance_kind="structured-import",
                    source_uri=source_uri,
                    source_hash=source_hash,
                    source_locator=locator,
                    evidence_ids=(evidence_id,),
                    name=name,
                    unit="Pa",
                    formula=f"{name}_out - {name}_in",
                    spatial_scope="measurement plane",
                    reduction="area-weighted difference",
                    temporal_scope="reported state",
                    producer_version="public-topic-fixture-v1",
                )
            )
        for kind, locator in (
            ("case", case_locator),
            ("convergence", f"$.residual[{index}]"),
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
        assessments.append(
            CaseNumericalAssessmentInput(
                case_id=case_id,
                residuals=(NamedScalar(name="response", value=float(residual[index])),),
                residual_targets=(NamedScalar(name="response", value=1.0e-5),),
                qoi_relative_span=0.001,
                conservation_inflow=10.0,
                conservation_outflow=10.0 * float(conservation[index]),
                conservation_tolerance=0.01,
                case_evidence_ids=(f"evidence-case-{suffix}",),
                convergence_evidence_ids=(f"evidence-convergence-{suffix}",),
                conservation_evidence_ids=(f"evidence-conservation-{suffix}",),
                independent_validation_evidence_ids=(),
                engineering_evidence_ids=(),
                sensitivity_evidence_ids=(),
            )
        )
    store.save_scientific_assessment_set(ScientificAssessmentSet(cases=tuple(assessments)))
    return store


def _install_incomplete_comparison_fixture(root: Path) -> ProjectStore:
    fixture = _load_fixture("incomplete_comparison_minimal.json")
    source_uri = str(fixture["source_uri"])
    source_payload = fixture["source"]
    assert isinstance(source_payload, dict)
    root.joinpath(source_uri).write_text(
        json.dumps(source_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    initialize_project(root, str(fixture["project_id"]))
    store = ProjectStore.open(root)
    ProjectIndexer(store).inspect()
    source_hash = store.get_source(source_uri).sha256
    common = {"source_uri": source_uri, "source_hash": source_hash, "stale": False}
    varied = source_payload["varied"]
    aggregate = source_payload["aggregate"]
    residual = source_payload["residual"]
    conservation = source_payload["conservation"]
    assert all(isinstance(values, list) for values in (varied, aggregate, residual, conservation))
    assessments = []
    for index, suffix in enumerate(("a", "b", "c")):
        case_id = f"case-{suffix}"
        case_locator = f"$.varied[{index}]"
        store.save_case(
            CaseRecord(case_id=case_id, locator=case_locator, state="validated", **common)
        )
        store.save_boundary(
            BoundaryRecord(
                boundary_id=f"boundary-varied-{suffix}",
                case_id=case_id,
                boundary_type="parameter:varied",
                values={"parameter-varied": float(varied[index])},
                units={"parameter-varied": "kg/s"},
                locator=case_locator,
                **common,
            )
        )
        store.save_evidence(
            EvidenceRecord(
                evidence_id=f"evidence-boundary-varied-{suffix}",
                kind="boundary",
                summary=f"Current varied parameter evidence for {case_id}.",
                maturity="verified",
                locator=case_locator,
                **common,
            )
        )
        qoi_locator = f"$.aggregate[{index}]"
        store.save_qoi(
            QoIRecord(
                qoi_id=f"qoi-aggregate-{suffix}",
                case_id=case_id,
                name="aggregate",
                value=float(aggregate[index]),
                unit="Pa",
                definition="Unverified aggregate description.",
                status="derived",
                locator=qoi_locator,
                **common,
            )
        )
        for kind, locator in (
            ("case", case_locator),
            ("convergence", f"$.residual[{index}]"),
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
        assessments.append(
            CaseNumericalAssessmentInput(
                case_id=case_id,
                residuals=(NamedScalar(name="aggregate", value=float(residual[index])),),
                residual_targets=(NamedScalar(name="aggregate", value=1.0e-5),),
                qoi_relative_span=0.2,
                conservation_inflow=10.0,
                conservation_outflow=10.0 * float(conservation[index]),
                conservation_tolerance=0.01,
                case_evidence_ids=(f"evidence-case-{suffix}",),
                convergence_evidence_ids=(f"evidence-convergence-{suffix}",),
                conservation_evidence_ids=(f"evidence-conservation-{suffix}",),
                independent_validation_evidence_ids=(),
                engineering_evidence_ids=(),
                sensitivity_evidence_ids=(),
            )
        )
    store.save_scientific_assessment_set(ScientificAssessmentSet(cases=tuple(assessments)))
    return store


def test_mature_existing_results_produce_two_to_four_useful_topics_via_cli(
    tmp_path: Path,
) -> None:
    """A mature public project must exercise the generated-topic production path."""

    fixture = _load_fixture("mature_project.json")
    store = _install_mature_public_fixture(tmp_path)

    result = CliRunner().invoke(app, ["plan", str(tmp_path), "--provider", "offline"])

    assert result.exit_code == 0, result.stdout
    generated = CandidateInput.model_validate_json(
        (tmp_path / ".cfdpaper/outputs/plan/generated-topic-candidates.json").read_text("utf-8")
    )
    assert 2 <= len(generated.candidates) <= 4
    output_root = tmp_path / ".cfdpaper/outputs/plan"
    report = json.loads((output_root / "candidate-generation-report.json").read_text("utf-8"))
    opportunities = json.loads((output_root / "research-opportunities.json").read_text("utf-8"))
    ranking = json.loads((output_root / "topic-ranking.json").read_text("utf-8"))
    assert report["generation_mode"] == "offline"
    assert report["minimum_missing_data"] == []
    assert ranking["ranking"]["outcome"] == "manuscript"
    assert ranking["approval"] is None
    opportunity_by_id = {item["opportunity_id"]: item for item in opportunities["opportunities"]}
    provenance_by_topic = {item["topic_id"]: item for item in report["candidate_provenance"]}
    topic_to_opportunity = dict(report["topic_to_opportunity"])
    actual_topics = tuple(item.topic_id for item in generated.candidates)
    assert set(actual_topics) == set(provenance_by_topic) == set(topic_to_opportunity)
    expected_patterns = set(fixture["expected_patterns"])
    evidence_by_id = {item.evidence_id: item for item in store.list_evidence()}
    seen_patterns: set[str] = set()
    for candidate in generated.candidates:
        provenance = provenance_by_topic[candidate.topic_id]
        opportunity = opportunity_by_id[topic_to_opportunity[candidate.topic_id]]
        assert set(candidate.required_evidence_kinds) == _REQUIRED_EVIDENCE_KINDS
        assert set(provenance["supporting_evidence_ids"]) == set(candidate.supporting_evidence_ids)
        assert opportunity["candidate_eligible"] is True
        assert opportunity["defensible"] is True
        assert opportunity["output_scope"] == "manuscript-topic"
        assert opportunity["pattern"] == provenance["pattern"]
        assert opportunity["relation"] == provenance["relation"]
        assert tuple(
            {
                "id": binding["parameter_id"],
                "kind": "parameter",
                "role": binding["role"],
                "case_ids": binding["case_ids"],
                "boundary_evidence_ids": binding["boundary_evidence_ids"],
            }
            for binding in opportunity["parameter_bindings"]
        ) == tuple(provenance["parameter_bindings"])
        assert opportunity["semantic_signature"]["relation"] == opportunity["relation"]
        assert opportunity["varied_parameter_ids"]
        assert opportunity["controlled_parameter_ids"]
        assert all(
            binding["boundary_evidence_ids"] for binding in opportunity["parameter_bindings"]
        )
        assert all(
            evidence_by_id[evidence_id].kind in candidate.required_evidence_kinds
            for evidence_id in candidate.supporting_evidence_ids
        )
        assert any(
            item.startswith("parameter:") for item in provenance["figure_evidence_structure"]
        )
        assert "research-question" in provenance["paper_spine_evidence_structure"]
        assert candidate.title and candidate.research_question
        seen_patterns.add(opportunity["pattern"])
    assert expected_patterns <= seen_patterns
    leading = ranking["ranking"]["ranked_topics"][0]["candidate"]["topic_id"]
    assert provenance_by_topic[leading]["pattern"] == fixture["expected_first_pattern"]
    assert provenance_by_topic[leading]["ranking_reason_codes"] == [
        "ceiling:association",
        "maturity:verified",
        "pattern:coupled-association",
    ]
    assert "source=generated" in result.stdout
    assert "approval=none" in result.stdout


def test_incomplete_comparison_never_becomes_manuscript_ready_claims(tmp_path: Path) -> None:
    _install_incomplete_comparison_fixture(tmp_path)

    result = CliRunner().invoke(app, ["plan", str(tmp_path), "--provider", "offline"])

    assert result.exit_code == 0, result.stdout
    output_root = tmp_path / ".cfdpaper/outputs/plan"
    generated = CandidateInput.model_validate_json(
        (output_root / "generated-topic-candidates.json").read_text("utf-8")
    )
    ranking = json.loads((output_root / "topic-ranking.json").read_text("utf-8"))
    report = json.loads((output_root / "candidate-generation-report.json").read_text("utf-8"))
    candidate_text = " ".join(
        f"{candidate.title} {candidate.research_question}" for candidate in generated.candidates
    ).casefold()
    assert ranking["ranking"]["outcome"] in {"missing-evidence", "analysis-note"}
    assert ranking["approval"] is None
    assert ProjectStore.open(tmp_path).status().stage == "planned"
    assert all(not item["defensible"] for item in ranking["ranking"]["ranked_topics"])
    assert "monotonic increase" not in candidate_text
    assert "stable operating window" not in candidate_text
    assert "continuous optimum" not in candidate_text
    assert report["minimum_missing_data"]


def test_readme_documents_generated_source_precedence_and_real_author_checkpoint() -> None:
    readme = (Path(__file__).resolve().parents[2] / "README.md").read_text("utf-8")
    readable = " ".join(readme.casefold().split())

    for command in (
        "cfdpaper plan PROJECT_ROOT",
        "cfdpaper plan PROJECT_ROOT --candidates AUTHOR_CANDIDATES.json",
        "cfdpaper plan PROJECT_ROOT --provider offline",
        "cfdpaper plan PROJECT_ROOT --provider auto",
        "cfdpaper plan PROJECT_ROOT --regenerate",
    ):
        assert command in readme
    for boundary in (
        "provisional",
        "author files take precedence",
        "minimum missing-data list",
        "provider transport",
        "real author approval",
    ):
        assert boundary in readable
