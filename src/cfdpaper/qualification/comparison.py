"""Deterministic scientific qualification for exported CFD comparisons."""

from __future__ import annotations

from typing import Any

from cfdpaper.scientific.units import convert_value, units_compatible
from cfdpaper.topic_generation.canonical import canonical_sha256

from .artifacts import scientific_input_fingerprint
from .models import (
    CandidateQoIContract,
    CaseDifference,
    ConservationObservation,
    ConvergenceObservation,
    ObservationTable,
    QoIProposal,
    QualificationReport,
    VNVStatus,
)


def _threshold_is_met(observation: ConvergenceObservation) -> bool:
    if not units_compatible(observation.unit, observation.threshold.unit):
        raise ValueError(
            f"threshold unit for {observation.metric!r} is incompatible with observed unit"
        )
    observed = convert_value(
        observation.observed_value, observation.unit, observation.threshold.unit
    )
    threshold = observation.threshold.value
    return {
        "<=": observed <= threshold,
        "<": observed < threshold,
        ">=": observed >= threshold,
        ">": observed > threshold,
    }[observation.threshold.operator]


def _assessment_failures(
    observations: tuple[ConvergenceObservation, ...] | tuple[ConservationObservation, ...],
) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    restrictions: list[str] = []
    for observation in observations:
        try:
            passed = _threshold_is_met(observation)
        except ValueError as error:
            blockers.append(f"{observation.metric}: {error}")
            continue
        if passed:
            continue
        message = (
            f"{observation.metric} does not satisfy its located "
            f"{observation.threshold.consequence} threshold"
        )
        if observation.threshold.consequence == "blocking":
            blockers.append(message)
        else:
            restrictions.append(message)
    return blockers, restrictions


def qualify_comparison(
    *,
    differences: tuple[CaseDifference, ...],
    verification: VNVStatus,
    validation: VNVStatus,
    convergence: tuple[ConvergenceObservation, ...],
    conservation: tuple[ConservationObservation, ...],
    observation_table: ObservationTable,
) -> QualificationReport:
    """Qualify one declared comparison from located scientific evidence only."""

    blockers = [
        f"blocking case difference: {difference.name}"
        for difference in differences
        if difference.role == "blocking"
    ]
    restrictions = [
        f"unresolved nuisance difference: {difference.name}"
        for difference in differences
        if difference.role == "unresolved-nuisance"
    ]
    minimum_corrections: list[str] = []

    if not observation_table.rows:
        blockers.append("observation input contains no scientific members")
        minimum_corrections.append("missing-observations")
    if not differences:
        blockers.append("no declared case differences")
        minimum_corrections.append("declare-case-differences")
    if not any(item.role == "intended-study-factor" for item in differences):
        blockers.append("no intended study factor")
        minimum_corrections.append("declare-intended-study-factor")

    if not convergence:
        restrictions.append("convergence threshold evidence is unavailable")
        minimum_corrections.append("missing-convergence-threshold")
    if not conservation:
        restrictions.append("conservation threshold evidence is unavailable")
        minimum_corrections.append("missing-conservation-threshold")

    for label, status in (("verification", verification), ("validation", validation)):
        if status.state in {"partial", "not-demonstrated"}:
            restrictions.append(f"{label} is {status.state}")
            minimum_corrections.append(f"{label}-{status.state}")
        elif status.state == "not-applicable" and not status.comparison_exemption:
            restrictions.append(f"{label} is not-applicable without a comparison exemption")
            minimum_corrections.append(f"{label}-not-applicable-unresolved")

    for observations in (convergence, conservation):
        assessment_blockers, assessment_restrictions = _assessment_failures(observations)
        blockers.extend(assessment_blockers)
        restrictions.extend(assessment_restrictions)

    status = "insufficient" if blockers else "restricted" if restrictions else "eligible"
    fingerprint = scientific_input_fingerprint(
        observation_table=observation_table,
        components={
            "differences": differences,
            "verification": verification,
            "validation": validation,
            "convergence": convergence,
            "conservation": conservation,
        },
    )
    return QualificationReport(
        status=status,
        differences=differences,
        verification=verification,
        validation=validation,
        blockers=tuple(blockers),
        restrictions=tuple(restrictions),
        minimum_corrections=tuple(dict.fromkeys(minimum_corrections)),
        input_fingerprint=fingerprint,
    )


def _fingerprint(value: Any, domain: bytes) -> str:
    return canonical_sha256(value, domain=domain)


def propose_qoi_contract(
    *,
    question_id: str,
    topic_fingerprint: str,
    qualification: QualificationReport,
    observations: ObservationTable,
    proposal: QoIProposal,
) -> CandidateQoIContract:
    """Create an immutable candidate; checkpoint 1 is required before execution."""

    question = question_id.strip()
    if not question:
        raise ValueError("question_id must be nonblank")
    if qualification.status == "insufficient":
        raise ValueError("cannot propose a QoI contract for an insufficient comparison")

    qualification_fingerprint = _fingerprint(qualification, b"cfdpaper-v03-qualification-report")
    verification_fingerprint = _fingerprint(
        qualification.verification, b"cfdpaper-v03-verification-status"
    )
    validation_fingerprint = _fingerprint(
        qualification.validation, b"cfdpaper-v03-validation-status"
    )
    observation_input_fingerprint = _fingerprint(observations, b"cfdpaper-v03-observation-input")
    scientific_fingerprint = scientific_input_fingerprint(
        observation_table=observations,
        expected_members=proposal.expected_members,
        qualification=qualification,
        topic_fingerprint=topic_fingerprint,
        components={"proposal": proposal},
    )
    body = {
        "question_id": question,
        "topic_fingerprint": topic_fingerprint,
        "proposal": proposal,
        "qualification_fingerprint": qualification_fingerprint,
        "verification_fingerprint": verification_fingerprint,
        "validation_fingerprint": validation_fingerprint,
        "observation_input_fingerprint": observation_input_fingerprint,
        "scientific_input_fingerprint": scientific_fingerprint,
    }
    fingerprint = _fingerprint(body, b"cfdpaper-v03-candidate-qoi-contract")
    return CandidateQoIContract(
        qoi_contract_id=f"qoi-{fingerprint[:16]}",
        question_id=question,
        topic_fingerprint=topic_fingerprint,
        qoi_name=proposal.qoi_name,
        scientific_definition=proposal.scientific_definition,
        operator=proposal.operator,
        operands=proposal.operands,
        output_unit=proposal.output_unit,
        expected_members=proposal.expected_members,
        trend_tolerance=proposal.trend_tolerance,
        missing_data_policy=proposal.missing_data_policy,
        reference_member=proposal.reference_member,
        allow_quantitative_reporting=proposal.allow_quantitative_reporting,
        qualification_fingerprint=qualification_fingerprint,
        verification_fingerprint=verification_fingerprint,
        validation_fingerprint=validation_fingerprint,
        observation_input_fingerprint=observation_input_fingerprint,
        scientific_input_fingerprint=scientific_fingerprint,
        fingerprint=fingerprint,
    )
