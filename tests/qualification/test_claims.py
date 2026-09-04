from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from cfdpaper.contracts import FigureContract
from cfdpaper.planning import PlanApproval
from cfdpaper.qualification.artifacts import (
    candidate_figure_contract_path,
    claim_ceiling_path,
    load_json_model,
    paragraph_duty_path,
    write_json_atomic,
)
from cfdpaper.qualification.claims import (
    assess_v03_claim_ceiling,
    build_candidate_figure_contract,
    lock_figure_contract,
)
from cfdpaper.qualification.comparison import propose_qoi_contract, qualify_comparison
from cfdpaper.qualification.models import (
    AuthorApproval,
    CandidateFigureContract,
    CaseDifference,
    ClaimCeilingDecision,
    DiscreteTrend,
    ExpectedMember,
    ObservationRow,
    ObservationTable,
    OperandSelector,
    QoIAnalysis,
    QoIProposal,
    QoIValue,
    QualificationReport,
    V03ClaimCeiling,
    ValueRole,
    VNVStatus,
)
from cfdpaper.qualification.qoi import analyze_qoi, lock_qoi_contract
from cfdpaper.topic_generation.canonical import canonical_sha256


def _vnv(state: str = "demonstrated", *, intended_use_supported: bool = True) -> VNVStatus:
    located = state in {"demonstrated", "partial"}
    return VNVStatus(
        state=state,
        summary=f"{state} for the intended numerical comparison",
        evidence_ids=(f"ev-{state}",) if located else (),
        basis="located evidence for the intended use" if located else None,
        source_locator="verification.md#result" if located else None,
        intended_use_supported=intended_use_supported if state == "demonstrated" else False,
    )


def _qualification(
    status: str,
    *,
    verification: str = "demonstrated",
    validation: str = "demonstrated",
    intended_use_supported: bool = True,
) -> QualificationReport:
    differences = [
        CaseDifference(
            name="mass flow",
            reference="low",
            candidate="high",
            role="intended-study-factor",
        )
    ]
    restrictions: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    if status == "restricted":
        differences.append(
            CaseDifference(
                name="roughness",
                reference="reported",
                candidate="unreported",
                role="unresolved-nuisance",
            )
        )
        restrictions = ("unresolved nuisance difference: roughness",)
    elif status == "insufficient":
        differences.append(
            CaseDifference(
                name="geometry",
                reference="A",
                candidate="B",
                role="blocking",
            )
        )
        blockers = ("blocking case difference: geometry",)
    return QualificationReport(
        status=status,
        differences=tuple(differences),
        verification=_vnv(verification, intended_use_supported=intended_use_supported),
        validation=_vnv(validation, intended_use_supported=intended_use_supported),
        blockers=blockers,
        restrictions=restrictions,
        minimum_corrections=(),
        input_fingerprint="a" * 64,
    )


def _analysis(
    count: int = 3,
    *,
    located: bool = True,
    quantitative_reporting_allowed: bool = True,
) -> QoIAnalysis:
    values = tuple(
        QoIValue(
            result_id=f"result-{index}",
            case_id=f"C{index}",
            coordinate_value=float(index),
            coordinate_unit="kg/s",
            value=float(index * 10),
            unit="Pa",
            evidence_id=f"evidence-{index}",
            source_locator=f"observations.csv#row={index + 1}" if located else "",
        )
        for index in range(1, count + 1)
    )
    return QoIAnalysis(
        qoi_contract_id="qoi-pressure-drop",
        qoi_name="pressure response",
        scientific_definition="declared pressure response over the complete sequence",
        coordinate_name="flow_rate",
        qualification_input_fingerprint="a" * 64,
        scientific_input_fingerprint="b" * 64,
        values=values,
        overall_change=values[-1].value - values[0].value if len(values) > 1 else None,
        trend=DiscreteTrend.MONOTONIC_INCREASING if count >= 3 else DiscreteTrend.OVERALL_CHANGE,
        restrictions=(),
        quantitative_reporting_allowed=quantitative_reporting_allowed,
    )


@pytest.mark.parametrize(
    (
        "qualification",
        "quantitative_allowed",
        "point_count",
        "verification",
        "validation",
        "expected",
    ),
    [
        ("insufficient", False, 3, "demonstrated", "demonstrated", "no-numerical-claim"),
        (
            "restricted",
            True,
            3,
            "demonstrated",
            "not-demonstrated",
            "qualified-numerical-observation",
        ),
        ("eligible", True, 2, "demonstrated", "demonstrated", "directional-comparison"),
        ("eligible", True, 3, "partial", "demonstrated", "qualified-numerical-observation"),
        ("eligible", True, 3, "demonstrated", "demonstrated", "supported-physical-interpretation"),
    ],
)
def test_claim_ceiling_is_closed(
    qualification: str,
    quantitative_allowed: bool,
    point_count: int,
    verification: str,
    validation: str,
    expected: str,
) -> None:
    decision = assess_v03_claim_ceiling(
        _qualification(
            qualification,
            verification=verification,
            validation=validation,
        ),
        _analysis(
            point_count,
            quantitative_reporting_allowed=quantitative_allowed,
        ),
    )

    assert decision.ceiling == V03ClaimCeiling(expected)
    assert decision.allowed_sentence_duties


def test_restricted_comparison_requires_explicit_permission_and_complete_locators() -> None:
    qualification = _qualification(
        "restricted",
        validation="not-demonstrated",
    )

    not_allowed = assess_v03_claim_ceiling(
        qualification,
        _analysis(quantitative_reporting_allowed=False),
    )
    complete = _analysis()
    unlocated_value = QoIValue.model_construct(
        **(complete.values[0].model_dump(mode="python") | {"source_locator": ""})
    )
    unlocated = assess_v03_claim_ceiling(
        qualification,
        complete.model_copy(update={"values": (unlocated_value, *complete.values[1:])}),
    )

    assert not_allowed.ceiling == V03ClaimCeiling.DIRECTIONAL_COMPARISON
    assert unlocated.ceiling == V03ClaimCeiling.DIRECTIONAL_COMPARISON


def test_locked_false_reporting_permission_survives_the_real_chain() -> None:
    rows = tuple(
        ObservationRow(
            case_id=f"C{index}",
            coordinate_name="flow_rate",
            coordinate_value=float(index),
            coordinate_unit="kg/s",
            variable="pressure_drop",
            value=float(index * 10),
            value_role=ValueRole.PRECOMPUTED_QOI,
            unit="Pa",
            scope="inlet-to-outlet",
            source_locator=f"observations.csv#row={index + 1}",
        )
        for index in range(1, 4)
    )
    observations = ObservationTable(
        source_uri="observations.csv",
        source_sha256="e" * 64,
        rows=rows,
    )
    report = qualify_comparison(
        differences=(
            CaseDifference(
                name="mass flow",
                reference="low",
                candidate="high",
                role="intended-study-factor",
            ),
        ),
        verification=_vnv(),
        validation=_vnv(),
        convergence=(),
        conservation=(),
        observation_table=observations,
    )
    members = tuple(
        ExpectedMember(
            case_id=row.case_id,
            coordinate_name=row.coordinate_name,
            coordinate_value=row.coordinate_value,
            coordinate_unit=row.coordinate_unit,
            variable=row.variable,
            unit=row.unit,
            scope=row.scope,
        )
        for row in rows
    )
    candidate = propose_qoi_contract(
        question_id="rq-pressure",
        topic_fingerprint="f" * 64,
        qualification=report,
        observations=observations,
        proposal=QoIProposal(
            qoi_name="pressure response",
            scientific_definition="pressure response over the complete sequence",
            operator="identity",
            operands=(
                OperandSelector(
                    name="pressure",
                    variable="pressure_drop",
                    value_role=ValueRole.PRECOMPUTED_QOI,
                    unit="Pa",
                    scope="inlet-to-outlet",
                    locator_policy="one located scalar per expected member",
                ),
            ),
            output_unit="Pa",
            expected_members=members,
            trend_tolerance=0.0,
            allow_quantitative_reporting=False,
        ),
    )
    locked = lock_qoi_contract(
        candidate,
        candidate_fingerprint=candidate.fingerprint,
        current_input_fingerprint=candidate.scientific_input_fingerprint,
        topic_approval=PlanApproval(
            topic_id="topic-pressure",
            author="Author A",
            scope="manuscript-topic",
            plan_fingerprint="f" * 64,
            approved_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        ),
        author="Author A",
        approved_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
    )

    analysis = analyze_qoi(locked, observations, report)
    decision = assess_v03_claim_ceiling(report, analysis)

    assert report.status == "restricted"
    assert analysis.quantitative_reporting_allowed is False
    assert decision.ceiling == V03ClaimCeiling.DIRECTIONAL_COMPARISON


def test_top_ceiling_requires_relevant_demonstrated_vnv_and_no_nuisance() -> None:
    partial_verification = assess_v03_claim_ceiling(
        _qualification("eligible", verification="partial"),
        _analysis(),
    )
    irrelevant_vnv = assess_v03_claim_ceiling(
        _qualification("eligible", intended_use_supported=False),
        _analysis(),
    )
    nuisance = assess_v03_claim_ceiling(
        _qualification("restricted"),
        _analysis(),
    )

    assert partial_verification.ceiling == V03ClaimCeiling.QUALIFIED_NUMERICAL_OBSERVATION
    assert irrelevant_vnv.ceiling == V03ClaimCeiling.QUALIFIED_NUMERICAL_OBSERVATION
    assert nuisance.ceiling == V03ClaimCeiling.QUALIFIED_NUMERICAL_OBSERVATION


def test_external_author_qa_wording_and_status_are_not_accepted_as_ceiling_inputs() -> None:
    qualification = _qualification("insufficient")
    analysis = _analysis()

    for field, value in {
        "author": "Senior Author",
        "qa_passed": True,
        "requested_wording": "This proves the physical mechanism.",
        "status_label": "approved",
    }.items():
        with pytest.raises(TypeError):
            assess_v03_claim_ceiling(qualification, analysis, **{field: value})

    decision = assess_v03_claim_ceiling(qualification, analysis)
    with pytest.raises(ValidationError):
        ClaimCeilingDecision.model_validate(
            {
                **decision.model_dump(mode="python"),
                "ceiling": "mechanism",
            }
        )


def test_assessment_binds_the_canonical_qualification_and_analysis() -> None:
    qualification = _qualification("eligible")
    analysis = _analysis()

    decision = assess_v03_claim_ceiling(qualification, analysis)

    assert decision.qualification_fingerprint == canonical_sha256(
        qualification, domain=b"cfdpaper-v03-qualification-report"
    )
    assert decision.analysis_fingerprint == canonical_sha256(
        analysis, domain=b"cfdpaper-v03-qoi-analysis"
    )
    assert decision.scientific_input_fingerprint == analysis.scientific_input_fingerprint
    assert decision.fingerprint == canonical_sha256(
        decision.model_dump(mode="python", exclude={"fingerprint"}),
        domain=b"cfdpaper-v03-claim-ceiling-decision",
    )


def test_assessment_rejects_a_cross_project_qualification_analysis_pair() -> None:
    old_analysis = _analysis().model_copy(update={"qualification_input_fingerprint": "f" * 64})

    with pytest.raises(ValueError, match="qualification input fingerprint"):
        assess_v03_claim_ceiling(_qualification("eligible"), old_analysis)


@pytest.mark.parametrize(
    ("update", "expected"),
    [
        ({"restrictions": ("unexpected restriction",)}, "qualified-numerical-observation"),
        (
            {"minimum_corrections": ("unresolved correction",)},
            "qualified-numerical-observation",
        ),
    ],
)
def test_eligible_label_with_internal_limits_cannot_reach_the_top_ceiling(
    update: dict[str, tuple[str, ...]], expected: str
) -> None:
    qualification = _qualification("eligible").model_copy(update=update)

    decision = assess_v03_claim_ceiling(qualification, _analysis())

    assert decision.ceiling == V03ClaimCeiling(expected)


def test_top_ceiling_requires_an_interpretable_trend_and_change() -> None:
    analysis = _analysis().model_copy(update={"trend": None, "overall_change": None})

    decision = assess_v03_claim_ceiling(_qualification("eligible"), analysis)

    assert decision.ceiling == V03ClaimCeiling.QUALIFIED_NUMERICAL_OBSERVATION


@pytest.mark.parametrize(
    ("ceiling", "quantitative"),
    [
        ("no-numerical-claim", True),
        ("directional-comparison", True),
        ("qualified-numerical-observation", False),
        ("supported-physical-interpretation", False),
    ],
)
def test_ceiling_model_rejects_an_inconsistent_quantitative_flag(
    ceiling: str, quantitative: bool
) -> None:
    payload = {
        "ceiling": ceiling,
        "reasons": ("located reason",),
        "allowed_sentence_duties": ("bounded duty",),
        "quantitative_reporting_allowed": quantitative,
        "qualification_fingerprint": "a" * 64,
        "analysis_fingerprint": "b" * 64,
        "scientific_input_fingerprint": "c" * 64,
    }
    with pytest.raises(ValidationError):
        ClaimCeilingDecision.model_validate(
            payload
            | {
                "fingerprint": canonical_sha256(
                    payload, domain=b"cfdpaper-v03-claim-ceiling-decision"
                )
            }
        )


def test_eligible_status_string_cannot_override_a_blocking_difference() -> None:
    report = _qualification("insufficient").model_copy(update={"status": "eligible"})

    decision = assess_v03_claim_ceiling(report, _analysis())

    assert decision.ceiling == V03ClaimCeiling.NO_NUMERICAL_CLAIM


def test_candidate_figure_contract_is_discrete_complete_and_bounded() -> None:
    analysis = _analysis()
    qualification = _qualification("eligible")
    ceiling = assess_v03_claim_ceiling(qualification, analysis)

    candidate = build_candidate_figure_contract(
        analysis=analysis,
        qualification=qualification,
        ceiling=ceiling,
        figure_id="fig-pressure-drop",
        author="Author A",
    )

    assert candidate.status == "candidate"
    assert candidate.author == "Author A"
    assert candidate.analysis_fingerprint
    assert candidate.qualification_fingerprint == ceiling.qualification_fingerprint
    assert candidate.claim_ceiling_fingerprint == ceiling.fingerprint
    assert len(candidate.panels) == 1
    panel = candidate.panels[0]
    assert panel.encoding == "discrete-marker-line"
    assert panel.case_order == ("C1", "C2", "C3")
    assert panel.x_variable == "flow_rate"
    assert panel.y_variable == "pressure response"
    assert panel.y_definition == "declared pressure response over the complete sequence"
    assert panel.x_unit == "kg/s"
    assert panel.y_unit == "Pa"
    assert candidate.evidence_ids == ("evidence-1", "evidence-2", "evidence-3")
    assert candidate.numeric_backlink_ids == ("result-1", "result-2", "result-3")
    assert candidate.paragraph_duty.numeric_backlink_ids == candidate.numeric_backlink_ids
    assert candidate.caption_duty
    assert candidate.prohibited_inferences == (
        "interpolation",
        "continuous optimum",
        "stability boundary",
        "unsampled prediction",
    )
    assert candidate.primary_claim.ceiling == ceiling.ceiling


@pytest.mark.parametrize("encoding", ["smooth-line", "polynomial-fit"])
def test_candidate_panel_rejects_smoothed_or_fit_encodings(encoding: str) -> None:
    analysis = _analysis()
    qualification = _qualification("eligible")
    candidate = build_candidate_figure_contract(
        analysis=analysis,
        qualification=qualification,
        ceiling=assess_v03_claim_ceiling(qualification, analysis),
        figure_id="fig-pressure-drop",
        author="Author A",
    )
    payload = candidate.model_dump(mode="python")
    payload["panels"][0]["encoding"] = encoding

    with pytest.raises(ValidationError):
        CandidateFigureContract.model_validate(payload)


def test_candidate_rejects_a_decision_from_an_old_analysis() -> None:
    qualification = _qualification("eligible")
    current = _analysis()
    old = current.model_copy(update={"qoi_name": "old pressure response"})
    old_decision = assess_v03_claim_ceiling(qualification, old)

    with pytest.raises(ValueError, match="analysis fingerprint"):
        build_candidate_figure_contract(
            analysis=current,
            qualification=qualification,
            ceiling=old_decision,
            figure_id="fig-pressure-drop",
            author="Author A",
        )


def test_candidate_rejects_a_decision_from_another_qualification() -> None:
    current_qualification = _qualification("eligible")
    analysis = _analysis()
    other_qualification = current_qualification.model_copy(update={"verification": _vnv("partial")})
    other_decision = assess_v03_claim_ceiling(other_qualification, analysis)

    with pytest.raises(ValueError, match="qualification fingerprint"):
        build_candidate_figure_contract(
            analysis=analysis,
            qualification=current_qualification,
            ceiling=other_decision,
            figure_id="fig-pressure-drop",
            author="Author A",
        )


def test_candidate_rejects_a_raised_and_canonically_resigned_ceiling() -> None:
    qualification = _qualification("restricted")
    analysis = _analysis()
    decision = assess_v03_claim_ceiling(qualification, analysis)
    payload = decision.model_dump(mode="python", exclude={"fingerprint"}) | {
        "ceiling": "supported-physical-interpretation",
        "quantitative_reporting_allowed": True,
    }
    forged = ClaimCeilingDecision.model_validate(
        payload
        | {"fingerprint": canonical_sha256(payload, domain=b"cfdpaper-v03-claim-ceiling-decision")}
    )

    with pytest.raises(ValueError, match="canonical decision"):
        build_candidate_figure_contract(
            analysis=analysis,
            qualification=qualification,
            ceiling=forged,
            figure_id="fig-pressure-drop",
            author="Author A",
        )


def test_no_numerical_ceiling_cannot_generate_a_figure_candidate() -> None:
    qualification = _qualification("insufficient")
    analysis = _analysis()

    with pytest.raises(ValueError, match="no-numerical-claim"):
        build_candidate_figure_contract(
            analysis=analysis,
            qualification=qualification,
            ceiling=assess_v03_claim_ceiling(qualification, analysis),
            figure_id="fig-pressure-drop",
            author="Author A",
        )


@pytest.mark.parametrize("figure_id", ["../escape", "nested/figure", "https:figure"])
def test_candidate_rejects_figure_ids_that_cannot_form_a_safe_output_path(
    figure_id: str,
) -> None:
    qualification = _qualification("eligible")
    analysis = _analysis()

    with pytest.raises(ValueError, match="safe path segment"):
        build_candidate_figure_contract(
            analysis=analysis,
            qualification=qualification,
            ceiling=assess_v03_claim_ceiling(qualification, analysis),
            figure_id=figure_id,
            author="Author A",
        )


def test_lock_figure_contract_converts_exact_fields() -> None:
    analysis = _analysis()
    qualification = _qualification("eligible")
    candidate = build_candidate_figure_contract(
        analysis=analysis,
        qualification=qualification,
        ceiling=assess_v03_claim_ceiling(qualification, analysis),
        figure_id="fig-pressure-drop",
        author="Author A",
    )
    approval = AuthorApproval(
        author="Author A",
        object_id=candidate.figure_id,
        object_fingerprint=candidate.fingerprint,
        approved_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    locked = lock_figure_contract(
        candidate,
        approval=approval,
        current_qualification=qualification,
        current_analysis=analysis,
        current_input_fingerprint=analysis.scientific_input_fingerprint,
        source_data_uri=".cfdpaper/outputs/figure/fig-pressure-drop/source-data.csv",
    )

    assert isinstance(locked, FigureContract)
    assert locked.figure_id == candidate.figure_id
    assert locked.primary_claim_id == candidate.primary_claim.claim_id
    assert locked.evidence_ids == list(candidate.evidence_ids)
    assert locked.panels == [candidate.panels[0].panel_id]
    assert locked.prohibited_inferences == list(candidate.prohibited_inferences)


@pytest.mark.parametrize("failure", ["wrong-author", "wrong-fingerprint", "stale", "unapproved"])
def test_lock_figure_contract_rejects_unbound_or_stale_approval(failure: str) -> None:
    analysis = _analysis()
    qualification = _qualification("eligible")
    candidate = build_candidate_figure_contract(
        analysis=analysis,
        qualification=qualification,
        ceiling=assess_v03_claim_ceiling(qualification, analysis),
        figure_id="fig-pressure-drop",
        author="Author A",
    )
    author = "Author B" if failure == "wrong-author" else "Author A"
    object_id = "different-candidate" if failure == "unapproved" else candidate.figure_id
    fingerprint = "c" * 64 if failure == "wrong-fingerprint" else candidate.fingerprint
    current = (
        analysis.model_copy(update={"qoi_name": "stale response"})
        if failure == "stale"
        else analysis
    )
    approval = AuthorApproval(
        author=author,
        object_id=object_id,
        object_fingerprint=fingerprint,
        approved_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError):
        lock_figure_contract(
            candidate,
            approval=approval,
            current_qualification=qualification,
            current_analysis=current,
            current_input_fingerprint=current.scientific_input_fingerprint,
            source_data_uri=".cfdpaper/outputs/figure/fig-pressure-drop/source-data.csv",
        )


def test_lock_rejects_a_changed_qualification_with_an_old_analysis() -> None:
    analysis = _analysis()
    qualification = _qualification("eligible")
    candidate = build_candidate_figure_contract(
        analysis=analysis,
        qualification=qualification,
        ceiling=assess_v03_claim_ceiling(qualification, analysis),
        figure_id="fig-pressure-drop",
        author="Author A",
    )
    approval = AuthorApproval(
        author="Author A",
        object_id=candidate.figure_id,
        object_fingerprint=candidate.fingerprint,
        approved_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    changed = qualification.model_copy(update={"restrictions": ("new restriction",)})

    with pytest.raises(ValueError, match="qualification"):
        lock_figure_contract(
            candidate,
            approval=approval,
            current_qualification=changed,
            current_analysis=analysis,
            current_input_fingerprint=analysis.scientific_input_fingerprint,
            source_data_uri=".cfdpaper/outputs/figure/fig-pressure-drop/source-data.csv",
        )


def test_lock_rejects_changed_upstream_input_with_an_old_analysis() -> None:
    analysis = _analysis()
    qualification = _qualification("eligible")
    candidate = build_candidate_figure_contract(
        analysis=analysis,
        qualification=qualification,
        ceiling=assess_v03_claim_ceiling(qualification, analysis),
        figure_id="fig-pressure-drop",
        author="Author A",
    )
    approval = AuthorApproval(
        author="Author A",
        object_id=candidate.figure_id,
        object_fingerprint=candidate.fingerprint,
        approved_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="current scientific input"):
        lock_figure_contract(
            candidate,
            approval=approval,
            current_qualification=qualification,
            current_analysis=analysis,
            current_input_fingerprint="f" * 64,
            source_data_uri=".cfdpaper/outputs/figure/fig-pressure-drop/source-data.csv",
        )


@pytest.mark.parametrize(
    "source_data_uri",
    [
        "https://example.test/source-data.csv",
        "../source-data.csv",
        ".cfdpaper/outputs/figure/fig-pressure-drop/source-data.json",
        ".cfdpaper/outputs/figure/another-figure/source-data.csv",
        "source-data.csv",
    ],
)
def test_lock_rejects_nondeterministic_or_unsafe_source_data_paths(
    source_data_uri: str,
) -> None:
    analysis = _analysis()
    qualification = _qualification("eligible")
    candidate = build_candidate_figure_contract(
        analysis=analysis,
        qualification=qualification,
        ceiling=assess_v03_claim_ceiling(qualification, analysis),
        figure_id="fig-pressure-drop",
        author="Author A",
    )
    approval = AuthorApproval(
        author="Author A",
        object_id=candidate.figure_id,
        object_fingerprint=candidate.fingerprint,
        approved_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="deterministic figure output path"):
        lock_figure_contract(
            candidate,
            approval=approval,
            current_qualification=qualification,
            current_analysis=analysis,
            current_input_fingerprint=analysis.scientific_input_fingerprint,
            source_data_uri=source_data_uri,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_ids", ("other-evidence",)),
        ("numeric_backlink_ids", ("other-result",)),
        ("prohibited_inferences", ("interpolation",)),
    ],
)
def test_candidate_requires_paragraph_duty_to_match_the_bound_claim(
    field: str, value: tuple[str, ...]
) -> None:
    analysis = _analysis()
    qualification = _qualification("eligible")
    candidate = build_candidate_figure_contract(
        analysis=analysis,
        qualification=qualification,
        ceiling=assess_v03_claim_ceiling(qualification, analysis),
        figure_id="fig-pressure-drop",
        author="Author A",
    )
    payload = candidate.model_dump(mode="python")
    payload["paragraph_duty"][field] = value

    with pytest.raises(ValidationError, match="paragraph duty"):
        CandidateFigureContract.model_validate(payload)


def test_claim_candidate_and_paragraph_artifacts_are_distinct_and_strict(
    tmp_path: Path,
) -> None:
    analysis = _analysis()
    qualification = _qualification("eligible")
    ceiling = assess_v03_claim_ceiling(qualification, analysis)
    candidate = build_candidate_figure_contract(
        analysis=analysis,
        qualification=qualification,
        ceiling=ceiling,
        figure_id="fig-pressure-drop",
        author="Author A",
    )

    write_json_atomic(tmp_path, claim_ceiling_path(tmp_path).name, ceiling)
    write_json_atomic(tmp_path, candidate_figure_contract_path(tmp_path).name, candidate)
    write_json_atomic(tmp_path, paragraph_duty_path(tmp_path).name, candidate.paragraph_duty)

    assert claim_ceiling_path(tmp_path) != candidate_figure_contract_path(tmp_path)
    assert candidate_figure_contract_path(tmp_path) != paragraph_duty_path(tmp_path)
    assert load_json_model(tmp_path, "claim-ceiling.json", ClaimCeilingDecision) == ceiling
    assert (
        load_json_model(tmp_path, "candidate-figure-contract.json", CandidateFigureContract)
        == candidate
    )
    assert paragraph_duty_path(tmp_path).is_file()
