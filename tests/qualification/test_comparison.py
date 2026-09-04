from __future__ import annotations

import pytest
from pydantic import ValidationError

from cfdpaper.qualification.comparison import propose_qoi_contract, qualify_comparison
from cfdpaper.qualification.models import (
    CaseDifference,
    ConservationObservation,
    ConvergenceObservation,
    ExpectedMember,
    ObservationRow,
    ObservationTable,
    OperandSelector,
    QoIProposal,
    ThresholdBasis,
    ValueRole,
    VNVStatus,
)


def _table() -> ObservationTable:
    return ObservationTable(
        source_uri="observations.csv",
        source_sha256="a" * 64,
        rows=tuple(
            ObservationRow(
                case_id=case_id,
                coordinate_name="mean_velocity",
                coordinate_value=velocity,
                coordinate_unit="m/s",
                variable="pressure_drop",
                value=pressure_drop,
                value_role=ValueRole.PRECOMPUTED_QOI,
                unit="Pa",
                scope="inlet-to-outlet pressure difference",
                source_locator=f"observations.csv#row={row_number}",
            )
            for row_number, (case_id, velocity, pressure_drop) in enumerate(
                (("P1", 0.25, 1.0), ("P2", 0.50, 4.0), ("P3", 0.75, 9.0)),
                start=2,
            )
        ),
    )


def _status(state: str = "demonstrated") -> VNVStatus:
    return VNVStatus(
        state=state,
        summary=f"{state} for the declared numerical comparison",
        evidence_ids=(f"evidence-{state}",),
        basis="located numerical evidence",
        source_locator=f"project-records.json#/models/0/{state}",
    )


def _observation(
    kind: type[ConvergenceObservation] | type[ConservationObservation],
    *,
    metric: str,
    observed: float,
    threshold: float,
    consequence: str = "blocking",
) -> ConvergenceObservation | ConservationObservation:
    return kind(
        metric=metric,
        observed_value=observed,
        unit="1",
        threshold=ThresholdBasis(
            metric=metric,
            operator="<=",
            value=threshold,
            unit="1",
            basis="project numerical acceptance criterion",
            source_locator=f"project-records.json#/thresholds/{metric}",
            consequence=consequence,
        ),
        evidence_id=f"evidence-{metric}",
        source_locator=f"solver-report.txt#{metric}",
    )


def _qualify(
    differences: tuple[CaseDifference, ...],
    *,
    verification: VNVStatus | None = None,
    validation: VNVStatus | None = None,
    convergence: tuple[ConvergenceObservation, ...] | None = None,
    conservation: tuple[ConservationObservation, ...] | None = None,
):
    return qualify_comparison(
        differences=differences,
        verification=verification or _status(),
        validation=validation or _status(),
        convergence=(
            _observation(
                ConvergenceObservation,
                metric="monitor-drift",
                observed=0.002,
                threshold=0.01,
            ),
        )
        if convergence is None
        else convergence,
        conservation=(
            _observation(
                ConservationObservation,
                metric="mass-imbalance",
                observed=0.001,
                threshold=0.01,
            ),
        )
        if conservation is None
        else conservation,
        observation_table=_table(),
    )


def test_comparison_models_enforce_closed_scientific_roles_and_evidence() -> None:
    with pytest.raises(ValidationError, match="basis.*source locator"):
        CaseDifference(
            name="roughness",
            reference="smooth",
            candidate="nominally smooth",
            role="demonstrated-equivalent-or-immaterial",
        )
    with pytest.raises(ValidationError):
        CaseDifference(name="roughness", reference="a", candidate="b", role="author-approved")

    with pytest.raises(ValidationError, match="finite"):
        ThresholdBasis(
            metric="mass-imbalance",
            operator="<=",
            value=float("nan"),
            unit="1",
            basis="declared criterion",
            source_locator="records.json#/threshold",
            consequence="blocking",
        )
    with pytest.raises(ValidationError):
        ThresholdBasis(
            metric="mass-imbalance",
            operator="==",
            value=0.01,
            unit="1",
            basis="declared criterion",
            source_locator="records.json#/threshold",
            consequence="blocking",
        )
    with pytest.raises(ValidationError, match="basis.*source locator"):
        VNVStatus(state="not-applicable", summary="not applicable")
    with pytest.raises(ValidationError, match="demonstrated.*located evidence"):
        VNVStatus(state="demonstrated", summary="unsupported status text")


def test_only_intended_factor_with_demonstrated_evidence_is_eligible() -> None:
    report = _qualify(
        (
            CaseDifference(
                name="mean velocity",
                reference="0.25 m/s",
                candidate="0.75 m/s",
                role="intended-study-factor",
            ),
        )
    )

    assert report.status == "eligible"
    assert report.blockers == ()
    assert report.restrictions == ()
    assert report.verification.state == "demonstrated"
    assert report.validation.state == "demonstrated"
    assert report.verification.model_dump() != report.validation.model_dump() or (
        report.verification is not report.validation
    )


def test_nuisance_and_validation_absence_restrict_without_erasing_comparison() -> None:
    report = _qualify(
        (
            CaseDifference(
                name="mean velocity",
                reference="0.25 m/s",
                candidate="0.75 m/s",
                role="intended-study-factor",
            ),
            CaseDifference(
                name="roughness",
                reference="smooth",
                candidate="unreported",
                role="unresolved-nuisance",
            ),
        ),
        validation=_status("not-demonstrated"),
    )

    assert report.status == "restricted"
    assert any("roughness" in item for item in report.restrictions)
    assert any("validation" in item for item in report.restrictions)
    assert report.blockers == ()
    assert report.verification.state == "demonstrated"
    assert report.validation.state == "not-demonstrated"


def test_not_applicable_vnv_without_explicit_comparison_exemption_restricts() -> None:
    report = _qualify(
        (
            CaseDifference(
                name="mean velocity",
                reference="0.25 m/s",
                candidate="0.75 m/s",
                role="intended-study-factor",
            ),
        ),
        validation=VNVStatus(
            state="not-applicable",
            summary="validation was declared outside the requested comparison",
            basis="author-declared scope statement",
            source_locator="project-records.json#/models/0/validation",
        ),
    )

    assert report.status == "restricted"
    assert any("validation" in item and "not-applicable" in item for item in report.restrictions)


def test_evidence_complete_not_applicable_exemption_can_preserve_eligibility() -> None:
    report = _qualify(
        (
            CaseDifference(
                name="mean velocity",
                reference="0.25 m/s",
                candidate="0.75 m/s",
                role="intended-study-factor",
            ),
        ),
        validation=VNVStatus(
            state="not-applicable",
            summary="external validation is not required for this numerical verification check",
            evidence_ids=("evidence-comparison-scope",),
            basis="the declared question is limited to a manufactured-solution verification",
            source_locator="verification-plan.md#scope",
            comparison_exemption=True,
        ),
    )

    assert report.status == "eligible"
    assert report.validation.comparison_exemption is True


def test_not_applicable_comparison_exemption_requires_located_evidence() -> None:
    with pytest.raises(ValidationError, match="comparison exemption requires located evidence"):
        VNVStatus(
            state="not-applicable",
            summary="not applicable",
            basis="declared scope",
            source_locator="verification-plan.md#scope",
            comparison_exemption=True,
        )


def test_blocking_difference_cannot_be_overridden_by_author_metadata() -> None:
    differences = (
        CaseDifference(
            name="diameter",
            reference="0.01 m",
            candidate="0.02 m",
            role="blocking",
        ),
    )
    report = _qualify(differences)

    assert report.status == "insufficient"
    assert any("diameter" in item for item in report.blockers)
    with pytest.raises(TypeError, match="author"):
        qualify_comparison(
            differences=differences,
            verification=_status(),
            validation=_status(),
            convergence=(),
            conservation=(),
            observation_table=_table(),
            author="cannot override science",  # type: ignore[call-arg]
        )


@pytest.mark.parametrize(
    ("consequence", "expected_status"),
    (("blocking", "insufficient"), ("restricting", "restricted")),
)
def test_exceeded_threshold_obeys_declared_consequence(
    consequence: str, expected_status: str
) -> None:
    report = _qualify(
        (
            CaseDifference(
                name="mean velocity",
                reference="0.25 m/s",
                candidate="0.75 m/s",
                role="intended-study-factor",
            ),
        ),
        convergence=(
            _observation(
                ConvergenceObservation,
                metric="monitor-drift",
                observed=0.02,
                threshold=0.01,
                consequence=consequence,
            ),
        ),
    )

    assert report.status == expected_status
    destination = report.blockers if consequence == "blocking" else report.restrictions
    assert any("monitor-drift" in item for item in destination)


def test_lower_bound_failure_uses_operator_neutral_threshold_language() -> None:
    lower_bound = ConvergenceObservation(
        metric="sample-count",
        observed_value=8.0,
        unit="1",
        threshold=ThresholdBasis(
            metric="sample-count",
            operator=">=",
            value=10.0,
            unit="1",
            basis="minimum samples required by the project analysis plan",
            source_locator="analysis-plan.md#sample-count",
            consequence="restricting",
        ),
        evidence_id="evidence-sample-count",
        source_locator="solver-report.txt#sample-count",
    )

    report = _qualify(
        (
            CaseDifference(
                name="mean velocity",
                reference="0.25 m/s",
                candidate="0.75 m/s",
                role="intended-study-factor",
            ),
        ),
        convergence=(lower_bound,),
    )

    assert report.status == "restricted"
    assert any(
        item == "sample-count does not satisfy its located restricting threshold"
        for item in report.restrictions
    )
    assert all("exceeds" not in item for item in report.restrictions)


def test_missing_convergence_threshold_remains_a_named_gap() -> None:
    report = _qualify(
        (
            CaseDifference(
                name="mean velocity",
                reference="0.25 m/s",
                candidate="0.75 m/s",
                role="intended-study-factor",
            ),
        ),
        convergence=(),
    )

    assert report.status == "restricted"
    assert "missing-convergence-threshold" in report.minimum_corrections


def test_empty_observation_input_is_insufficient() -> None:
    report = qualify_comparison(
        differences=(
            CaseDifference(
                name="mean velocity",
                reference="0.25 m/s",
                candidate="0.75 m/s",
                role="intended-study-factor",
            ),
        ),
        verification=_status(),
        validation=_status(),
        convergence=(
            _observation(
                ConvergenceObservation,
                metric="monitor-drift",
                observed=0.002,
                threshold=0.01,
            ),
        ),
        conservation=(
            _observation(
                ConservationObservation,
                metric="mass-imbalance",
                observed=0.001,
                threshold=0.01,
            ),
        ),
        observation_table=ObservationTable(
            source_uri="observations.csv", source_sha256="a" * 64, rows=()
        ),
    )

    assert report.status == "insufficient"
    assert "missing-observations" in report.minimum_corrections


def test_incomplete_threshold_basis_cannot_form_an_eligible_report() -> None:
    with pytest.raises(ValidationError):
        ThresholdBasis(
            metric="monitor-drift",
            operator="<=",
            value=0.01,
            unit="1",
            basis=" ",
            source_locator="solver.txt#monitor",
            consequence="blocking",
        )
    with pytest.raises(ValidationError):
        ThresholdBasis(
            metric="monitor-drift",
            operator="<=",
            value=0.01,
            unit="1",
            basis="declared criterion",
            source_locator=" ",
            consequence="blocking",
        )


def test_candidate_qoi_contract_is_candidate_ordered_and_deterministic() -> None:
    report = _qualify(
        (
            CaseDifference(
                name="mean velocity",
                reference="0.25 m/s",
                candidate="0.75 m/s",
                role="intended-study-factor",
            ),
        )
    )
    members = tuple(
        ExpectedMember(
            case_id=case_id,
            coordinate_name="mean_velocity",
            coordinate_value=velocity,
            coordinate_unit="m/s",
            variable="pressure_drop",
            unit="Pa",
            scope="inlet-to-outlet pressure difference",
        )
        for case_id, velocity in (("P1", 0.25), ("P2", 0.50), ("P3", 0.75))
    )
    proposal = QoIProposal(
        qoi_name="pressure drop",
        scientific_definition="exported inlet-to-outlet pressure difference",
        operator="identity",
        operands=(
            OperandSelector(
                name="pressure_drop",
                variable="pressure_drop",
                value_role=ValueRole.PRECOMPUTED_QOI,
                unit="Pa",
                scope="inlet-to-outlet pressure difference",
                locator_policy="one located scalar per expected member",
            ),
        ),
        output_unit="Pa",
        expected_members=members,
        trend_tolerance=0.01,
        missing_data_policy="reject",
    )

    first = propose_qoi_contract(
        question_id="rq-pressure-velocity",
        topic_fingerprint="b" * 64,
        qualification=report,
        observations=_table(),
        proposal=proposal,
    )
    second = propose_qoi_contract(
        question_id="rq-pressure-velocity",
        topic_fingerprint="b" * 64,
        qualification=report,
        observations=_table(),
        proposal=proposal,
    )

    assert first == second
    assert first.status == "candidate"
    assert [member.case_id for member in first.expected_members] == ["P1", "P2", "P3"]
    assert first.qoi_contract_id.startswith("qoi-")
    assert len(first.fingerprint) == 64

    inconsistent = first.model_dump(mode="python")
    inconsistent["operator"] = "difference"
    with pytest.raises(ValidationError, match="difference requires exactly 2 operand"):
        type(first).model_validate(inconsistent)
