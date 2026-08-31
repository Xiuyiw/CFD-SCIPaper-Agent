from __future__ import annotations

from itertools import product

import pytest
from pydantic import ValidationError

from cfdpaper.contracts import (
    BoundaryRecord,
    CaseRecord,
    ClaimRecord,
    ClaimStatus,
    EvidenceRecord,
    QoIRecord,
)
from cfdpaper.scientific import (
    ClaimCeiling,
    EvidenceMaturity,
    MaturityAssessment,
)
from cfdpaper.topic_generation.models import (
    ScientificRelationFrame,
    make_qoi_definition_assessment,
)
from cfdpaper.topic_generation.opportunities import (
    OpportunityDiscoveryResult,
    ResearchOpportunity,
    _controlling_maturity,
    _effective_ceiling,
    _linked_supported_claims,
    discover_research_opportunities,
)
from cfdpaper.topic_generation.snapshot import (
    CaseNumericalAssessmentInput,
    NamedScalar,
    ScientificAssessmentSet,
    ScientificRecordSnapshot,
    build_scientific_snapshot,
)

SOURCE_URI = "synthetic-science.json"
SOURCE_HASH = "1" * 64
QOI_SOURCE_URI = "synthetic-qoi-values.json"
QOI_SOURCE_HASH = "2" * 64
DEFINITION_SOURCE_URI = "synthetic-qoi-definitions.json"
DEFINITION_SOURCE_HASH = "3" * 64


def _source(*, stale: bool = False) -> dict[str, object]:
    return {
        "source_uri": SOURCE_URI,
        "source_hash": SOURCE_HASH,
        "stale": stale,
    }


def _assessment(
    case_id: str,
    *,
    strong: bool = True,
    conservation_pass: bool = True,
    validation: bool = False,
    engineering: bool = False,
    sensitivity: bool = False,
) -> CaseNumericalAssessmentInput:
    suffix = case_id.removeprefix("case-")
    return CaseNumericalAssessmentInput(
        case_id=case_id,
        residuals=(NamedScalar(name="response", value=1.0e-6 if strong else 1.0e-2),),
        residual_targets=(NamedScalar(name="response", value=1.0e-5),),
        qoi_relative_span=0.001 if strong else 0.1,
        conservation_inflow=10.0,
        conservation_outflow=9.99 if conservation_pass else 8.0,
        conservation_tolerance=0.01,
        case_evidence_ids=(f"evidence-case-{suffix}",),
        convergence_evidence_ids=(f"evidence-convergence-{suffix}",),
        conservation_evidence_ids=(f"evidence-conservation-{suffix}",),
        independent_validation_evidence_ids=(f"evidence-validation-{suffix}",)
        if validation
        else (),
        engineering_evidence_ids=(f"evidence-engineering-{suffix}",) if engineering else (),
        sensitivity_evidence_ids=(f"evidence-sensitivity-{suffix}",) if sensitivity else (),
    )


def synthetic_snapshot(
    values: tuple[float, ...] = (1.0, 2.0, 3.0),
    *,
    factor_declared: bool = True,
    comparable: bool = True,
    qoi_values: tuple[float, ...] | None = None,
    second_qoi_values: tuple[float, ...] | None = None,
    qoi_status: str = "derived",
    qoi_name: str = "response",
    qoi_names: tuple[str, ...] | None = None,
    qoi_unit: str | None = "Pa",
    qoi_units: tuple[str, ...] | None = None,
    definition_units: tuple[str, ...] | None = None,
    definition: bool = True,
    evidence_stale: bool = False,
    strong: bool = True,
    conservation_pass: bool = True,
    include_primary: bool = True,
    validation: bool = False,
    engineering: bool = False,
    sensitivity: bool = False,
    claim_status: ClaimStatus | None = None,
    claim_ceiling: str = "mechanism",
    claim_binding: str = "full",
    approved_evidence_maturity: str = "verified",
    separate_definition_provenance: bool = False,
    validation_maturity: str = "verified",
    engineering_maturity: str = "author-approved",
    sensitivity_maturity: str = "verified",
) -> ScientificRecordSnapshot:
    qoi_values = qoi_values or tuple(10.0 + value for value in values)
    cases: list[CaseRecord] = []
    boundaries: list[BoundaryRecord] = []
    qois: list[QoIRecord] = []
    evidence: list[EvidenceRecord] = []
    definitions = []
    assessments = []
    qoi_evidence_ids: list[str] = []

    for index, factor in enumerate(values):
        suffix = chr(ord("a") + index)
        case_id = f"case-{suffix}"
        common = _source()
        cases.append(
            CaseRecord(
                case_id=case_id,
                locator=f"$.cases[{index}]",
                state="validated",
                **common,
            )
        )
        factor_boundary = BoundaryRecord(
            boundary_id=f"boundary-factor-{suffix}",
            case_id=case_id,
            boundary_type="parameter:varied" if factor_declared else "parameter:unclassified",
            values={"parameter-varied": factor},
            units={"parameter-varied": "kg/s"},
            locator=f"$.factor[{index}]",
            **common,
        )
        control_boundary = BoundaryRecord(
            boundary_id=f"boundary-control-{suffix}",
            case_id=case_id,
            boundary_type="parameter:controlled",
            values={"parameter-control": 1.0 if comparable or index == 0 else 2.0},
            units={"parameter-control": "m/s"},
            locator=f"$.control[{index}]",
            **common,
        )
        boundaries.extend((factor_boundary, control_boundary))
        for role, boundary in (
            ("factor", factor_boundary),
            ("control", control_boundary),
        ):
            evidence.append(
                EvidenceRecord(
                    evidence_id=f"evidence-boundary-{role}-{suffix}",
                    kind="boundary",
                    summary=f"Structured {role} boundary for {case_id}",
                    maturity="verified",
                    locator=boundary.locator,
                    **common,
                )
            )
        for evidence_kind in ("case", "convergence", "conservation"):
            evidence.append(
                EvidenceRecord(
                    evidence_id=f"evidence-{evidence_kind}-{suffix}",
                    kind=evidence_kind,
                    summary=f"Current {evidence_kind} evidence for {case_id}",
                    maturity="verified",
                    locator=f"$.{evidence_kind}[{index}]",
                    **common,
                )
            )
        qoi_id = f"qoi-response-{suffix}"
        qoi_locator = f"$.response[{index}]"
        current_qoi_name = qoi_names[index] if qoi_names is not None else qoi_name
        current_qoi_unit = qoi_units[index] if qoi_units is not None else qoi_unit
        current_definition_unit = definition_units[index] if definition_units is not None else "Pa"
        qoi_source = (
            {
                "source_uri": QOI_SOURCE_URI,
                "source_hash": QOI_SOURCE_HASH,
                "stale": False,
            }
            if separate_definition_provenance
            else common
        )
        definition_source_uri = (
            DEFINITION_SOURCE_URI if separate_definition_provenance else SOURCE_URI
        )
        definition_source_hash = (
            DEFINITION_SOURCE_HASH if separate_definition_provenance else SOURCE_HASH
        )
        definition_locator = (
            f"$.definitions[{index}]" if separate_definition_provenance else qoi_locator
        )
        qois.append(
            QoIRecord(
                qoi_id=qoi_id,
                case_id=case_id,
                name=current_qoi_name,
                value=qoi_values[index] if qoi_status != "missing" else None,
                unit=current_qoi_unit,
                definition="human prose must not be parsed",
                status=qoi_status,
                locator=qoi_locator,
                **qoi_source,
            )
        )
        qoi_evidence_id = f"evidence-qoi-{suffix}"
        qoi_evidence_ids.append(qoi_evidence_id)
        if include_primary:
            evidence.append(
                EvidenceRecord(
                    evidence_id=qoi_evidence_id,
                    kind="qoi",
                    summary=f"Structured response for {case_id}",
                    maturity=approved_evidence_maturity,
                    locator=definition_locator,
                    source_uri=definition_source_uri,
                    source_hash=definition_source_hash,
                    stale=evidence_stale,
                )
            )
        if definition:
            definitions.append(
                make_qoi_definition_assessment(
                    qoi_id=qoi_id,
                    provenance_kind="structured-import",
                    source_uri=definition_source_uri,
                    source_hash=definition_source_hash,
                    source_locator=definition_locator,
                    evidence_ids=(qoi_evidence_id,),
                    name="response",
                    unit=current_definition_unit,
                    formula="outlet - inlet",
                    spatial_scope="measurement planes",
                    reduction="area-weighted difference",
                    temporal_scope="reported state",
                    producer_version="synthetic 1",
                )
            )
        assessments.append(
            _assessment(
                case_id,
                strong=strong,
                conservation_pass=conservation_pass,
                validation=validation,
                engineering=engineering,
                sensitivity=sensitivity,
            )
        )
        for kind, enabled in (
            ("validation", validation),
            ("engineering", engineering),
            ("sensitivity", sensitivity),
        ):
            if enabled:
                evidence.append(
                    EvidenceRecord(
                        evidence_id=f"evidence-{kind}-{suffix}",
                        kind="other" if kind == "engineering" else "qoi",
                        summary=f"Current {kind} evidence for {case_id}",
                        maturity={
                            "validation": validation_maturity,
                            "engineering": engineering_maturity,
                            "sensitivity": sensitivity_maturity,
                        }[kind],
                        locator=f"$.{kind}[{index}]",
                        **common,
                    )
                )

        if second_qoi_values is not None:
            second_id = f"qoi-secondary-{suffix}"
            second_locator = f"$.secondary[{index}]"
            second_evidence_id = f"evidence-secondary-{suffix}"
            qois.append(
                QoIRecord(
                    qoi_id=second_id,
                    case_id=case_id,
                    name="secondary response",
                    value=second_qoi_values[index],
                    unit="K",
                    definition="not a parser input",
                    status="derived",
                    locator=second_locator,
                    **common,
                )
            )
            evidence.append(
                EvidenceRecord(
                    evidence_id=second_evidence_id,
                    kind="qoi",
                    summary=f"Secondary response for {case_id}",
                    maturity=approved_evidence_maturity,
                    locator=second_locator,
                    **_source(stale=evidence_stale),
                )
            )
            definitions.append(
                make_qoi_definition_assessment(
                    qoi_id=second_id,
                    provenance_kind="structured-import",
                    source_uri=SOURCE_URI,
                    source_hash=SOURCE_HASH,
                    source_locator=second_locator,
                    evidence_ids=(second_evidence_id,),
                    name="secondary response",
                    unit="K",
                    formula="volume mean",
                    spatial_scope="measurement volume",
                    reduction="volume-weighted mean",
                    temporal_scope="reported state",
                    producer_version="synthetic 1",
                )
            )

    claims: list[ClaimRecord] = []
    if claim_status is not None:
        bound = tuple(qoi_evidence_ids)
        if claim_binding == "partial":
            bound = (*bound, "evidence-unbound")
        elif claim_binding == "empty":
            bound = ()
        claims.append(
            ClaimRecord(
                claim_id="claim-response",
                text="The sampled response relation is evidence bounded.",
                status=claim_status,
                evidence_ids=bound,
                ceiling=claim_ceiling,
            )
        )

    return build_scientific_snapshot(
        project_id="opportunity-project",
        cases=cases,
        boundaries=boundaries,
        meshes=(),
        fields=(),
        qois=qois,
        qoi_definition_assessments=definitions,
        evidence=evidence,
        claims=claims,
        assessments=ScientificAssessmentSet(cases=tuple(assessments)),
    )


def _by_pattern(result: OpportunityDiscoveryResult, pattern: str) -> ResearchOpportunity:
    matches = [item for item in result.opportunities if item.pattern == pattern]
    assert len(matches) == 1, (pattern, result)
    return matches[0]


def _rebuild(
    snapshot: ScientificRecordSnapshot,
    *,
    boundaries: tuple[BoundaryRecord, ...] | None = None,
    evidence: tuple[EvidenceRecord, ...] | None = None,
) -> ScientificRecordSnapshot:
    return build_scientific_snapshot(
        project_id=snapshot.project_id,
        cases=snapshot.cases,
        boundaries=boundaries if boundaries is not None else snapshot.boundaries,
        meshes=snapshot.meshes,
        fields=snapshot.fields,
        qois=snapshot.qois,
        qoi_definition_assessments=snapshot.qoi_definition_assessments,
        evidence=evidence if evidence is not None else snapshot.evidence,
        claims=snapshot.claims,
        assessments=snapshot.assessments,
    )


def test_matched_comparison_requires_declared_factor_and_control_comparability() -> None:
    matched = discover_research_opportunities(synthetic_snapshot(values=(1.0, 2.0)))
    missing_factor = discover_research_opportunities(
        synthetic_snapshot(values=(1.0, 2.0), factor_declared=False)
    )
    incomparable = discover_research_opportunities(
        synthetic_snapshot(values=(1.0, 2.0), comparable=False)
    )

    opportunity = _by_pattern(matched, "matched-comparison")
    assert opportunity.comparability == "verified"
    assert opportunity.relation == ScientificRelationFrame(
        relation_class="difference",
        polarity="increase",
        comparison_direction="variant-vs-reference",
        quantifier="pairwise",
    )
    assert "comparison-factor-missing" in missing_factor.gaps
    assert "case-comparability-unverified" in incomparable.gaps


def test_matched_comparison_converts_compatible_qoi_units_before_direction() -> None:
    result = discover_research_opportunities(
        synthetic_snapshot(
            values=(1.0, 2.0),
            qoi_values=(1000.0, 2.0),
            qoi_units=("Pa", "kPa"),
            definition_units=("Pa", "kPa"),
        )
    )

    opportunity = _by_pattern(result, "matched-comparison")
    assert opportunity.relation.polarity == "increase"
    assert opportunity.candidate_eligible


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ((1.0, 2.0, 3.0), "monotonic-increasing"),
        ((3.0, 2.0, 1.0), "monotonic-decreasing"),
        ((1.0, 3.0, 2.0), "interior-peak"),
        ((3.0, 1.0, 2.0), "interior-trough"),
        ((1.0, 2.0, 2.0, 2.0), "plateau"),
    ],
)
def test_ordered_response_uses_existing_discrete_trend_detector(
    values: tuple[float, ...], expected: str
) -> None:
    opportunity = _by_pattern(
        discover_research_opportunities(
            synthetic_snapshot(
                values=tuple(float(i + 1) for i in range(len(values))), qoi_values=values
            )
        ),
        "ordered-parameter-response",
    )
    assert opportunity.trend_type == expected
    expected_polarity = {
        "monotonic-increasing": "increase",
        "monotonic-decreasing": "decrease",
        "interior-peak": "non-monotonic",
        "interior-trough": "non-monotonic",
        "plateau": "plateau",
    }[expected]
    assert opportunity.relation == ScientificRelationFrame(
        relation_class="ordered-response",
        polarity=expected_polarity,
        comparison_direction="parameter-ascending",
        quantifier="sampled-series-only",
    )
    assert "continuous optimum" in opportunity.prohibited_inferences


def test_ordered_response_converts_compatible_qoi_units_before_trend_detection() -> None:
    opportunity = _by_pattern(
        discover_research_opportunities(
            synthetic_snapshot(
                qoi_values=(1000.0, 2.0, 3000.0),
                qoi_units=("Pa", "kPa", "Pa"),
                definition_units=("Pa", "kPa", "Pa"),
            )
        ),
        "ordered-parameter-response",
    )

    assert opportunity.trend_type == "monotonic-increasing"
    assert opportunity.relation.polarity == "increase"


def test_qoi_series_names_use_task3_strip_and_casefold_grouping() -> None:
    opportunity = _by_pattern(
        discover_research_opportunities(
            synthetic_snapshot(qoi_names=(" Response ", "response", "RESPONSE"))
        ),
        "ordered-parameter-response",
    )

    assert opportunity.trend_type == "monotonic-increasing"
    assert opportunity.candidate_eligible


def test_incompatible_cross_case_qoi_units_emit_gap_without_quantitative_candidate() -> None:
    result = discover_research_opportunities(
        synthetic_snapshot(
            qoi_values=(1000.0, 300.0, 2000.0),
            qoi_units=("Pa", "K", "Pa"),
            definition_units=("Pa", "K", "Pa"),
        )
    )

    assert "qoi-series-unit-incompatible:response" in result.gaps
    assert not any(
        item.pattern in {"matched-comparison", "ordered-parameter-response", "coupled-association"}
        for item in result.opportunities
    )


def test_coupled_association_is_capped_and_never_causal() -> None:
    opportunity = _by_pattern(
        discover_research_opportunities(
            synthetic_snapshot(second_qoi_values=(300.0, 320.0, 340.0))
        ),
        "coupled-association",
    )
    assert opportunity.claim_ceiling == "association"
    assert opportunity.relation == ScientificRelationFrame(
        relation_class="coupled-association",
        polarity="positive",
        comparison_direction="symmetric",
        quantifier="sampled-cases-only",
    )
    assert "causation" in opportunity.prohibited_inferences


def test_coupled_association_normalizes_each_qoi_series_before_sign_detection() -> None:
    opportunity = _by_pattern(
        discover_research_opportunities(
            synthetic_snapshot(
                qoi_values=(1000.0, 2.0, 3000.0),
                qoi_units=("Pa", "kPa", "Pa"),
                definition_units=("Pa", "kPa", "Pa"),
                second_qoi_values=(300.0, 320.0, 340.0),
            )
        ),
        "coupled-association",
    )

    assert opportunity.relation.polarity == "positive"


def test_coupled_association_requires_two_nonconstant_paired_series() -> None:
    result = discover_research_opportunities(
        synthetic_snapshot(second_qoi_values=(300.0, 300.0, 300.0))
    )

    assert not any(item.pattern == "coupled-association" for item in result.opportunities)


def test_convergence_or_mesh_alone_cannot_become_scientific_topic() -> None:
    result = discover_research_opportunities(
        synthetic_snapshot(qoi_status="missing", definition=False, include_primary=False)
    )
    assert result.opportunities == ()
    assert "scientific-qoi-required" in result.gaps


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown-unit",
        "incompatible-unit",
        "stale-evidence",
        "weak-convergence",
        "failed-conservation",
        "missing-qoi",
        "invalid-qoi",
        "missing-qoi-definition",
        "qoi-name-mismatch",
    ],
)
def test_quantitative_vetoes_never_enter_supporting_evidence(mutation: str) -> None:
    options: dict[str, object] = {}
    if mutation == "unknown-unit":
        options["qoi_unit"] = "mystery"
    elif mutation == "incompatible-unit":
        options["qoi_unit"] = "K"
    elif mutation == "stale-evidence":
        options["evidence_stale"] = True
    elif mutation == "weak-convergence":
        options["strong"] = False
    elif mutation == "failed-conservation":
        options["conservation_pass"] = False
    elif mutation == "missing-qoi":
        options["qoi_status"] = "missing"
    elif mutation == "invalid-qoi":
        options["qoi_status"] = "invalid"
    elif mutation == "missing-qoi-definition":
        options["definition"] = False
    else:
        options["qoi_name"] = "reported response"
    result = discover_research_opportunities(synthetic_snapshot(**options))
    assert all(not item.defensible for item in result.opportunities)
    assert all(
        set(item.supporting_evidence_ids).isdisjoint(item.constraint_provenance_evidence_ids)
        for item in result.opportunities
    )
    if mutation in {
        "unknown-unit",
        "incompatible-unit",
        "stale-evidence",
        "missing-qoi-definition",
        "qoi-name-mismatch",
    }:
        assert all(not item.supporting_evidence_ids for item in result.opportunities)
    assert result.gaps


def test_candidate_eligibility_has_three_non_interchangeable_states() -> None:
    defensible = _by_pattern(
        discover_research_opportunities(synthetic_snapshot()), "ordered-parameter-response"
    )
    direction = _by_pattern(
        discover_research_opportunities(synthetic_snapshot(strong=False)),
        "ordered-parameter-response",
    )
    no_primary = _by_pattern(
        discover_research_opportunities(synthetic_snapshot(include_primary=False)),
        "ordered-parameter-response",
    )
    no_definition = _by_pattern(
        discover_research_opportunities(synthetic_snapshot(definition=False)),
        "ordered-parameter-response",
    )
    assert (defensible.candidate_eligible, defensible.defensible) == (True, True)
    assert (direction.candidate_eligible, direction.defensible) == (True, False)
    assert direction.output_scope in {"direction-only", "analysis-note"}
    assert no_primary.candidate_eligible is False
    assert no_definition.candidate_eligible is False


def test_qoi_definition_evidence_can_use_distinct_source_and_locator() -> None:
    opportunity = _by_pattern(
        discover_research_opportunities(synthetic_snapshot(separate_definition_provenance=True)),
        "ordered-parameter-response",
    )

    assert opportunity.candidate_eligible
    assert opportunity.defensible
    evidence_by_id = {
        item.evidence_id: item
        for item in synthetic_snapshot(separate_definition_provenance=True).evidence
    }
    assert {"evidence-qoi-a", "evidence-qoi-b", "evidence-qoi-c"} <= set(
        opportunity.supporting_evidence_ids
    )
    assert {evidence_by_id[item].kind for item in opportunity.supporting_evidence_ids} == {
        "boundary",
        "case",
        "conservation",
        "convergence",
        "qoi",
    }


@pytest.mark.parametrize(
    "evidence_kind,evidence_id",
    (
        ("boundary", "evidence-boundary-factor-a"),
        ("case", "evidence-case-a"),
        ("convergence", "evidence-convergence-a"),
        ("conservation", "evidence-conservation-a"),
    ),
)
@pytest.mark.parametrize("mutation", ("missing", "stale", "wrong-kind", "wrong-source"))
def test_required_evidence_bindings_block_manuscript_promotion(
    evidence_kind: str,
    evidence_id: str,
    mutation: str,
) -> None:
    snapshot = synthetic_snapshot()
    evidence = list(snapshot.evidence)
    index = next(index for index, item in enumerate(evidence) if item.evidence_id == evidence_id)
    if mutation == "missing":
        evidence.pop(index)
    elif mutation == "stale":
        evidence[index] = evidence[index].model_copy(update={"stale": True})
    elif mutation == "wrong-kind":
        evidence[index] = evidence[index].model_copy(update={"kind": "other"})
    else:
        evidence[index] = evidence[index].model_copy(update={"source_hash": "f" * 64})

    result = discover_research_opportunities(_rebuild(snapshot, evidence=tuple(evidence)))

    assert all(not item.defensible for item in result.opportunities)
    assert all(item.output_scope != "manuscript-topic" for item in result.opportunities)
    if evidence_kind == "boundary":
        assert any(
            gap.code.startswith("boundary-evidence-")
            for opportunity in result.opportunities
            for gap in opportunity.gaps
        ) or any(gap.startswith("boundary-evidence-") for gap in result.gaps)
    else:
        assert any(
            gap.code.startswith("assessment-evidence-")
            for opportunity in result.opportunities
            for gap in opportunity.gaps
        )


def test_qoi_name_binding_matches_task3_strip_and_casefold_semantics() -> None:
    opportunity = _by_pattern(
        discover_research_opportunities(synthetic_snapshot(qoi_name="  ReSpOnSe  ")),
        "ordered-parameter-response",
    )

    assert opportunity.candidate_eligible
    assert opportunity.defensible
    assert not any(gap.code.startswith("qoi-name-mismatch:") for gap in opportunity.gaps)


def test_complete_parameter_binding_is_sorted_unique_and_provenance_bound() -> None:
    opportunity = _by_pattern(
        discover_research_opportunities(synthetic_snapshot()), "ordered-parameter-response"
    )
    assert opportunity.parameter_ids == ("parameter-control", "parameter-varied")
    assert opportunity.varied_parameter_ids == ("parameter-varied",)
    assert opportunity.controlled_parameter_ids == ("parameter-control",)
    assert all(
        binding.case_ids and binding.boundary_evidence_ids
        for binding in opportunity.parameter_bindings
    )
    bindings = {item.parameter_id: item for item in opportunity.parameter_bindings}
    assert bindings["parameter-varied"].boundary_evidence_ids == (
        "evidence-boundary-factor-a",
        "evidence-boundary-factor-b",
        "evidence-boundary-factor-c",
    )
    assert bindings["parameter-control"].boundary_evidence_ids == (
        "evidence-boundary-control-a",
        "evidence-boundary-control-b",
        "evidence-boundary-control-c",
    )
    assert all(
        evidence_id.startswith("evidence-boundary-")
        for binding in opportunity.parameter_bindings
        for evidence_id in binding.boundary_evidence_ids
    )
    assert {item.role for item in opportunity.parameter_bindings} == {"varied", "controlled"}


def test_parameter_binding_errors_never_become_candidates() -> None:
    missing_factor = discover_research_opportunities(synthetic_snapshot(factor_declared=False))
    incomparable = discover_research_opportunities(synthetic_snapshot(comparable=False))
    assert all(not item.candidate_eligible for item in missing_factor.opportunities)
    assert all(not item.defensible for item in incomparable.opportunities)
    assert all(item.output_scope != "manuscript-topic" for item in incomparable.opportunities)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-varied",
        "missing-controlled",
        "stale",
        "mismatched",
        "duplicate",
        "role-swapped",
        "incompatible-unit",
    ],
)
def test_incomplete_or_conflicting_parameter_provenance_is_ineligible(mutation: str) -> None:
    snapshot = synthetic_snapshot()
    boundaries = list(snapshot.boundaries)
    evidence = list(snapshot.evidence)
    factor_index = next(
        index for index, item in enumerate(boundaries) if item.boundary_id == "boundary-factor-b"
    )
    factor_evidence_index = next(
        index
        for index, item in enumerate(evidence)
        if item.evidence_id == "evidence-boundary-factor-b"
    )
    if mutation in {"missing-varied", "missing-controlled"}:
        missing_id = (
            "evidence-boundary-factor-b"
            if mutation == "missing-varied"
            else "evidence-boundary-control-b"
        )
        evidence = [item for item in evidence if item.evidence_id != missing_id]
    elif mutation == "stale":
        evidence[factor_evidence_index] = evidence[factor_evidence_index].model_copy(
            update={"stale": True}
        )
    elif mutation == "mismatched":
        evidence[factor_evidence_index] = evidence[factor_evidence_index].model_copy(
            update={"locator": "$.wrong-factor[1]"}
        )
    elif mutation == "duplicate":
        evidence.append(
            evidence[factor_evidence_index].model_copy(
                update={"evidence_id": "evidence-boundary-factor-b-duplicate"}
            )
        )
    elif mutation == "role-swapped":
        boundaries[factor_index] = boundaries[factor_index].model_copy(
            update={"boundary_type": "parameter:controlled"}
        )
    else:
        boundaries[factor_index] = boundaries[factor_index].model_copy(
            update={"units": {"parameter-varied": "K"}}
        )

    result = discover_research_opportunities(
        _rebuild(
            snapshot,
            boundaries=tuple(boundaries),
            evidence=tuple(evidence),
        )
    )

    assert all(not item.candidate_eligible for item in result.opportunities)
    assert any(
        code.startswith(
            (
                "boundary-evidence-",
                "parameter-binding-",
                "parameter-role-",
                "parameter-unit-",
            )
        )
        for code in result.gaps
    )


def test_declared_varied_parameter_must_actually_vary() -> None:
    result = discover_research_opportunities(synthetic_snapshot(values=(1.0, 1.0, 1.0)))

    assert all(not item.candidate_eligible for item in result.opportunities)
    assert "varied-parameter-not-varying:parameter-varied" in result.gaps


@pytest.mark.parametrize(
    ("base_level", "evidence_level"),
    list(product(tuple(EvidenceMaturity), repeat=2)),
)
def test_controlling_maturity_is_minimum_of_linked_current_evidence(
    base_level: EvidenceMaturity,
    evidence_level: EvidenceMaturity,
) -> None:
    base = MaturityAssessment(
        base_level,
        (),
        approved_by="author" if base_level == EvidenceMaturity.AUTHOR_APPROVED else None,
    )
    evidence = EvidenceRecord(
        evidence_id="evidence-current",
        kind="qoi",
        summary="current",
        maturity=evidence_level.value,
        locator="$.qoi",
        **_source(),
    )
    expected = min(
        (base_level, evidence_level),
        key={level: index for index, level in enumerate(EvidenceMaturity)}.__getitem__,
    )
    controlled = _controlling_maturity(base, (evidence,))
    assert controlled.level == expected
    assert controlled.approved_by == (
        "author" if expected == EvidenceMaturity.AUTHOR_APPROVED else None
    )


def test_controlling_maturity_is_raw_for_empty_or_all_stale_primary_evidence() -> None:
    base = MaturityAssessment(EvidenceMaturity.VERIFIED, ())
    stale = EvidenceRecord(
        evidence_id="evidence-stale",
        kind="qoi",
        summary="stale",
        maturity="author-approved",
        locator="$.qoi",
        **_source(stale=True),
    )
    assert _controlling_maturity(base, ()).level == EvidenceMaturity.RAW
    assert _controlling_maturity(base, (stale,)).level == EvidenceMaturity.RAW


@pytest.mark.parametrize(
    ("maturity_field", "maturity_value", "expected_maturity", "expected_ceiling"),
    [
        ("validation_maturity", "screened", "screened", "association"),
        ("engineering_maturity", "raw", "raw", "observation"),
    ],
)
def test_low_maturity_extra_support_controls_validation_opportunity(
    maturity_field: str,
    maturity_value: str,
    expected_maturity: str,
    expected_ceiling: str,
) -> None:
    options: dict[str, object] = {
        "validation": True,
        "engineering": True,
        "claim_status": ClaimStatus.SUPPORTED,
        "claim_ceiling": "engineering",
        maturity_field: maturity_value,
    }

    opportunity = _by_pattern(
        discover_research_opportunities(synthetic_snapshot(**options)),
        "validation-robustness",
    )

    assert opportunity.evidence_maturity == expected_maturity
    assert opportunity.claim_ceiling == expected_ceiling
    assert not opportunity.defensible


@pytest.mark.parametrize(
    ("status", "binding"),
    [
        (ClaimStatus.DRAFT, "full"),
        (ClaimStatus.REJECTED, "full"),
        (ClaimStatus.NEEDS_EVIDENCE, "full"),
        (ClaimStatus.SUPPORTED, "partial"),
    ],
)
def test_only_fully_bound_supported_current_claim_can_raise_pattern_cap(
    status: ClaimStatus, binding: str
) -> None:
    claim = ClaimRecord(
        claim_id="claim-high",
        text="High ceiling claim",
        status=status,
        evidence_ids=("evidence-current", "evidence-unbound")
        if binding == "partial"
        else ("evidence-current",),
        ceiling="engineering",
    )
    assert _linked_supported_claims((claim,), ("evidence-current",)) == ()


def test_fully_bound_supported_current_claim_can_raise_pattern_cap() -> None:
    claim = ClaimRecord(
        claim_id="claim-high",
        text="High ceiling claim",
        status="supported",
        evidence_ids=("evidence-current",),
        ceiling="mechanism",
    )
    linked = _linked_supported_claims((claim,), ("evidence-current",))
    ceiling = _effective_ceiling(
        pattern="matched-comparison",
        maturity=MaturityAssessment(EvidenceMaturity.VERIFIED, ()),
        supporting_claims=linked,
        independent_validation=False,
        engineering_evidence=False,
    )
    assert ceiling == ClaimCeiling.MECHANISM


@pytest.mark.parametrize(
    ("status", "binding", "stale"),
    [
        (ClaimStatus.DRAFT, "full", False),
        (ClaimStatus.REJECTED, "full", False),
        (ClaimStatus.NEEDS_EVIDENCE, "full", False),
        (ClaimStatus.SUPPORTED, "partial", False),
        (ClaimStatus.SUPPORTED, "full", True),
    ],
)
def test_claim_negative_matrix_cannot_raise_discovered_ceiling(
    status: ClaimStatus,
    binding: str,
    stale: bool,
) -> None:
    result = discover_research_opportunities(
        synthetic_snapshot(
            values=(1.0, 2.0),
            claim_status=status,
            claim_ceiling="engineering",
            claim_binding=binding,
            evidence_stale=stale,
        )
    )
    opportunity = _by_pattern(result, "matched-comparison")
    assert opportunity.claim_ceiling in {"observation", "association"}
    assert any(gap.code.startswith("claim-") for gap in opportunity.gaps)


def test_fully_bound_supported_claim_raises_discovered_pattern_cap_only_to_mechanism() -> None:
    result = discover_research_opportunities(
        synthetic_snapshot(
            values=(1.0, 2.0),
            claim_status=ClaimStatus.SUPPORTED,
            claim_ceiling="engineering",
        )
    )
    opportunity = _by_pattern(result, "matched-comparison")
    assert opportunity.claim_ceiling == "mechanism"


def test_validation_and_engineering_require_all_prerequisites() -> None:
    verified_claim = ClaimRecord(
        claim_id="claim-validation",
        text="Bound validation claim",
        status="supported",
        evidence_ids=("evidence-current",),
        ceiling="engineering",
    )
    linked = (verified_claim,)
    assert (
        _effective_ceiling(
            pattern="validation-robustness",
            maturity=MaturityAssessment(EvidenceMaturity.VERIFIED, ()),
            supporting_claims=linked,
            independent_validation=True,
            engineering_evidence=False,
        )
        == ClaimCeiling.VALIDATION
    )
    assert (
        _effective_ceiling(
            pattern="validation-robustness",
            maturity=MaturityAssessment(EvidenceMaturity.AUTHOR_APPROVED, (), approved_by="author"),
            supporting_claims=linked,
            independent_validation=True,
            engineering_evidence=True,
        )
        == ClaimCeiling.ENGINEERING
    )
    assert _effective_ceiling(
        pattern="validation-robustness",
        maturity=MaturityAssessment(EvidenceMaturity.VERIFIED, ()),
        supporting_claims=linked,
        independent_validation=False,
        engineering_evidence=True,
    ).value in {"mechanism", "association"}


def test_opportunity_ceiling_uses_controlling_maturity_and_pattern_cap() -> None:
    coupled = _by_pattern(
        discover_research_opportunities(
            synthetic_snapshot(
                second_qoi_values=(300.0, 320.0, 340.0),
                claim_status=ClaimStatus.SUPPORTED,
                claim_ceiling="engineering",
            )
        ),
        "coupled-association",
    )
    matched = _by_pattern(
        discover_research_opportunities(
            synthetic_snapshot(
                values=(1.0, 2.0),
                claim_status=ClaimStatus.SUPPORTED,
                claim_ceiling="mechanism",
            )
        ),
        "matched-comparison",
    )
    validation = _by_pattern(
        discover_research_opportunities(
            synthetic_snapshot(
                validation=True,
                sensitivity=True,
                claim_status=ClaimStatus.SUPPORTED,
                claim_ceiling="validation",
            )
        ),
        "validation-robustness",
    )

    assert coupled.claim_ceiling == "association"
    assert matched.claim_ceiling == "mechanism"
    assert validation.claim_ceiling == "validation"
    assert all(
        item.evidence_maturity != "author-approved" for item in (coupled, matched, validation)
    )


def test_opportunity_ids_and_signatures_are_order_independent_and_domain_separated() -> None:
    snapshot = synthetic_snapshot()
    original = discover_research_opportunities(snapshot)
    reordered = build_scientific_snapshot(
        project_id=snapshot.project_id,
        cases=tuple(reversed(snapshot.cases)),
        boundaries=tuple(reversed(snapshot.boundaries)),
        meshes=snapshot.meshes,
        fields=snapshot.fields,
        qois=tuple(reversed(snapshot.qois)),
        qoi_definition_assessments=tuple(reversed(snapshot.qoi_definition_assessments)),
        evidence=tuple(reversed(snapshot.evidence)),
        claims=tuple(reversed(snapshot.claims)),
        assessments=ScientificAssessmentSet(cases=tuple(reversed(snapshot.assessments.cases))),
    )
    second = discover_research_opportunities(reordered)
    assert original == second
    assert all(item.opportunity_id.startswith("opp-") for item in original.opportunities)
    assert len({item.opportunity_id for item in original.opportunities}) == len(
        original.opportunities
    )
    from cfdpaper.topic_generation.canonical import canonical_sha256

    for opportunity in original.opportunities:
        wrong_domain = (
            "opp-"
            + canonical_sha256(
                opportunity.semantic_signature,
                domain=b"cfdpaper-scientific-component-v1",
            )[:16]
        )
        assert opportunity.opportunity_id != wrong_domain


def test_pattern_relation_combinations_are_locked() -> None:
    opportunity = _by_pattern(
        discover_research_opportunities(synthetic_snapshot()), "ordered-parameter-response"
    )
    with pytest.raises(ValidationError):
        ResearchOpportunity.model_validate(
            {
                **opportunity.model_dump(mode="python"),
                "relation": {
                    "relation_class": "coupled-association",
                    "polarity": "positive",
                    "comparison_direction": "symmetric",
                    "quantifier": "sampled-cases-only",
                },
            }
        )


def test_duplicate_parameter_binding_is_rejected_even_with_recomputed_identity() -> None:
    opportunity = _by_pattern(
        discover_research_opportunities(synthetic_snapshot()),
        "ordered-parameter-response",
    )
    payload = opportunity.model_dump(mode="python")
    duplicate = (*payload["parameter_bindings"], payload["parameter_bindings"][0])
    payload["parameter_bindings"] = duplicate
    payload["semantic_signature"] = {
        **payload["semantic_signature"],
        "parameter_bindings": duplicate,
    }
    from cfdpaper.topic_generation.canonical import canonical_sha256

    payload["opportunity_id"] = (
        "opp-"
        + canonical_sha256(payload["semantic_signature"], domain=b"cfdpaper-opportunity-v1")[:16]
    )
    with pytest.raises(ValidationError):
        ResearchOpportunity.model_validate(payload, strict=True)


@pytest.mark.parametrize(
    "relation",
    [
        {
            "relation_class": "ordered-response",
            "polarity": "increase",
            "comparison_direction": "symmetric",
            "quantifier": "sampled-series-only",
        },
        {
            "relation_class": "ordered-response",
            "polarity": "positive",
            "comparison_direction": "parameter-ascending",
            "quantifier": "sampled-series-only",
        },
        {
            "relation_class": "ordered-response",
            "polarity": "increase",
            "comparison_direction": "parameter-ascending",
            "quantifier": "sampled-cases-only",
        },
    ],
)
def test_relation_direction_polarity_and_quantifier_are_all_locked(
    relation: dict[str, str],
) -> None:
    opportunity = _by_pattern(
        discover_research_opportunities(synthetic_snapshot()),
        "ordered-parameter-response",
    )
    payload = opportunity.model_dump(mode="python")
    payload["relation"] = relation
    payload["semantic_signature"] = {
        **payload["semantic_signature"],
        "relation": relation,
    }
    from cfdpaper.topic_generation.canonical import canonical_sha256

    payload["opportunity_id"] = (
        "opp-"
        + canonical_sha256(payload["semantic_signature"], domain=b"cfdpaper-opportunity-v1")[:16]
    )
    with pytest.raises(ValidationError):
        ResearchOpportunity.model_validate(payload, strict=True)


def test_validation_opportunity_requires_scientific_qoi_and_explicit_links() -> None:
    with_links = discover_research_opportunities(
        synthetic_snapshot(validation=True, sensitivity=True)
    )
    without_qoi = discover_research_opportunities(
        synthetic_snapshot(
            qoi_status="missing",
            definition=False,
            include_primary=False,
            validation=True,
            sensitivity=True,
        )
    )
    opportunity = _by_pattern(with_links, "validation-robustness")
    assert opportunity.independent_validation_linked
    assert opportunity.claim_ceiling in {"association", "validation"}
    assert not any(item.pattern == "validation-robustness" for item in without_qoi.opportunities)
    assert "scientific-qoi-required" in without_qoi.gaps
