"""Lock and evaluate evidence-bound V0.3 QoI contracts."""

from __future__ import annotations

import math
from datetime import datetime

from cfdpaper.planning import PlanApproval
from cfdpaper.scientific.trends import TrendKind, detect_trend
from cfdpaper.scientific.units import convert_value, units_compatible
from cfdpaper.topic_generation.canonical import canonical_sha256

from .artifacts import scientific_input_fingerprint
from .models import (
    AuthorApproval,
    CandidateQoIContract,
    DiscreteTrend,
    ExpectedMember,
    LockedQoIContract,
    ObservationRow,
    ObservationTable,
    OperandSelector,
    QoIAnalysis,
    QoIProposal,
    QoIValue,
    QualificationReport,
    ValueRole,
)
from .observations import ObservationInputError, validate_expected_membership


def _candidate_payload(candidate: CandidateQoIContract) -> dict[str, object]:
    proposal = QoIProposal(
        qoi_name=candidate.qoi_name,
        scientific_definition=candidate.scientific_definition,
        operator=candidate.operator,
        operands=candidate.operands,
        output_unit=candidate.output_unit,
        expected_members=candidate.expected_members,
        trend_tolerance=candidate.trend_tolerance,
        missing_data_policy=candidate.missing_data_policy,
        reference_member=candidate.reference_member,
        allow_quantitative_reporting=candidate.allow_quantitative_reporting,
    )
    return {
        "question_id": candidate.question_id,
        "topic_fingerprint": candidate.topic_fingerprint,
        "proposal": proposal,
        "qualification_fingerprint": candidate.qualification_fingerprint,
        "verification_fingerprint": candidate.verification_fingerprint,
        "validation_fingerprint": candidate.validation_fingerprint,
        "observation_input_fingerprint": candidate.observation_input_fingerprint,
        "scientific_input_fingerprint": candidate.scientific_input_fingerprint,
    }


def _candidate_fingerprint(candidate: CandidateQoIContract) -> str:
    return canonical_sha256(
        _candidate_payload(candidate), domain=b"cfdpaper-v03-candidate-qoi-contract"
    )


def lock_qoi_contract(
    candidate: CandidateQoIContract,
    *,
    candidate_fingerprint: str,
    current_input_fingerprint: str,
    topic_approval: PlanApproval,
    author: str,
    approved_at: datetime,
) -> LockedQoIContract:
    """Bind an unchanged candidate to an approved manuscript topic and author."""

    normalized_author = author.strip()
    if not normalized_author:
        raise ValueError("author must be nonblank")
    if topic_approval.scope != "manuscript-topic":
        raise ValueError("QoI locking requires manuscript-topic approval")
    if normalized_author != topic_approval.author:
        raise ValueError("author must match the manuscript-topic approval")
    if topic_approval.plan_fingerprint != candidate.topic_fingerprint:
        raise ValueError("topic fingerprint does not match the manuscript-topic approval")
    if (
        candidate_fingerprint != candidate.fingerprint
        or _candidate_fingerprint(candidate) != candidate.fingerprint
    ):
        raise ValueError("candidate fingerprint does not match candidate content")
    if current_input_fingerprint != candidate.scientific_input_fingerprint:
        raise ValueError("scientific input fingerprint changed before locking")

    approval = AuthorApproval(
        author=normalized_author,
        object_id=candidate.qoi_contract_id,
        object_fingerprint=candidate.fingerprint,
        approved_at=approved_at,
    )
    return LockedQoIContract(
        candidate=candidate,
        approval=approval,
        scientific_input_fingerprint=current_input_fingerprint,
    )


def _proposal(candidate: CandidateQoIContract) -> QoIProposal:
    return QoIProposal(
        qoi_name=candidate.qoi_name,
        scientific_definition=candidate.scientific_definition,
        operator=candidate.operator,
        operands=candidate.operands,
        output_unit=candidate.output_unit,
        expected_members=candidate.expected_members,
        trend_tolerance=candidate.trend_tolerance,
        missing_data_policy=candidate.missing_data_policy,
        reference_member=candidate.reference_member,
        allow_quantitative_reporting=candidate.allow_quantitative_reporting,
    )


def _fingerprint(value: object, domain: bytes) -> str:
    return canonical_sha256(value, domain=domain)


def _verify_inputs(
    contract: LockedQoIContract,
    observations: ObservationTable,
    qualification: QualificationReport,
) -> None:
    candidate = contract.candidate
    if qualification.status == "insufficient":
        raise ValueError("an insufficient comparison cannot be analyzed")
    if _candidate_fingerprint(candidate) != candidate.fingerprint:
        raise ValueError("candidate fingerprint does not match candidate content")
    if (
        _fingerprint(qualification, b"cfdpaper-v03-qualification-report")
        != candidate.qualification_fingerprint
    ):
        raise ValueError("qualification fingerprint changed before analysis")
    if (
        _fingerprint(qualification.verification, b"cfdpaper-v03-verification-status")
        != candidate.verification_fingerprint
        or _fingerprint(qualification.validation, b"cfdpaper-v03-validation-status")
        != candidate.validation_fingerprint
    ):
        raise ValueError("verification or validation fingerprint changed before analysis")
    if (
        _fingerprint(observations, b"cfdpaper-v03-observation-input")
        != candidate.observation_input_fingerprint
    ):
        raise ValueError("observation fingerprint changed before analysis")
    current = scientific_input_fingerprint(
        observation_table=observations,
        expected_members=candidate.expected_members,
        qualification=qualification,
        topic_fingerprint=candidate.topic_fingerprint,
        components={"proposal": _proposal(candidate)},
    )
    if (
        current != candidate.scientific_input_fingerprint
        or current != contract.scientific_input_fingerprint
    ):
        raise ValueError("scientific input fingerprint changed before analysis")


def _selector_rows(
    observations: ObservationTable,
    members: tuple[ExpectedMember, ...],
    selector: OperandSelector,
) -> tuple[ObservationRow, ...]:
    relevant = tuple(
        row
        for row in observations.rows
        if row.variable == selector.variable
        and row.scope == selector.scope
        and row.value_role == selector.value_role
    )
    if any(not units_compatible(row.unit, selector.unit) for row in relevant):
        raise ValueError(f"operand {selector.name!r} has incompatible units")
    expected = tuple(
        ExpectedMember(
            case_id=member.case_id,
            coordinate_name=member.coordinate_name,
            coordinate_value=member.coordinate_value,
            coordinate_unit=member.coordinate_unit,
            variable=selector.variable,
            unit=selector.unit,
            scope=selector.scope,
        )
        for member in members
    )
    try:
        ordered = validate_expected_membership(relevant, expected)
    except ObservationInputError as error:
        raise ValueError(f"{error.issue_code}: {error}") from error
    return ordered


def _ordered_operands(
    candidate: CandidateQoIContract, observations: ObservationTable
) -> tuple[tuple[ObservationRow, ...], ...]:
    bindings = tuple(
        (selector.variable, selector.value_role, selector.scope) for selector in candidate.operands
    )
    names = tuple(selector.name for selector in candidate.operands)
    if len(set(bindings)) != len(bindings) or len(set(names)) != len(names):
        raise ValueError("operand selectors must bind distinct scalar roles")
    declared_roles: dict[tuple[str, str], set[ValueRole]] = {}
    for variable, value_role, scope in bindings:
        declared_roles.setdefault((variable, scope), set()).add(value_role)
    for row in observations.rows:
        allowed_roles = declared_roles.get((row.variable, row.scope))
        if allowed_roles is not None and row.value_role not in allowed_roles:
            expected = ", ".join(sorted(role.value for role in allowed_roles))
            raise ValueError(
                f"observation {row.source_locator!r} has undeclared value role "
                f"{row.value_role.value!r}; expected one of: {expected}"
            )
    ordered = tuple(
        _selector_rows(observations, candidate.expected_members, selector)
        for selector in candidate.operands
    )
    consumed = {id(row) for rows in ordered for row in rows}
    if consumed != {id(row) for row in observations.rows}:
        raise ValueError("unexpected scientific member outside the declared operand sequence")
    return ordered


def _converted(row: ObservationRow, selector: OperandSelector) -> float:
    try:
        return convert_value(row.value, row.unit, selector.unit)
    except ValueError as error:
        raise ValueError(f"operand {selector.name!r} has incompatible units") from error


def _evaluate_values(
    candidate: CandidateQoIContract,
    operand_rows: tuple[tuple[ObservationRow, ...], ...],
) -> tuple[float, ...]:
    operands = tuple(
        tuple(_converted(row, selector) for row in rows)
        for selector, rows in zip(candidate.operands, operand_rows, strict=True)
    )
    if candidate.operator == "identity":
        try:
            return tuple(
                convert_value(value, candidate.operands[0].unit, candidate.output_unit)
                for value in operands[0]
            )
        except ValueError as error:
            raise ValueError("identity output unit is incompatible with its operand") from error
    if candidate.operator == "difference":
        if not units_compatible(candidate.operands[0].unit, candidate.operands[1].unit):
            raise ValueError("difference operands have incompatible units")
        try:
            left = tuple(
                convert_value(value, candidate.operands[0].unit, candidate.output_unit)
                for value in operands[0]
            )
            right = tuple(
                convert_value(value, candidate.operands[1].unit, candidate.output_unit)
                for value in operands[1]
            )
        except ValueError as error:
            raise ValueError("difference output unit is incompatible with its operands") from error
        return tuple(a - b for a, b in zip(left, right, strict=True))
    if candidate.operator == "ratio":
        if not units_compatible(candidate.operands[0].unit, candidate.operands[1].unit):
            raise ValueError("ratio operands have incompatible units")
        denominator = tuple(
            convert_value(value, candidate.operands[1].unit, candidate.operands[0].unit)
            for value in operands[1]
        )
        if any(value == 0 for value in denominator):
            raise ValueError("ratio denominator must not be zero")
        ratios = tuple(a / b for a, b in zip(operands[0], denominator, strict=True))
        try:
            return tuple(convert_value(value, "1", candidate.output_unit) for value in ratios)
        except ValueError as error:
            raise ValueError("ratio output unit must be dimensionless") from error

    reference_matches = tuple(
        index
        for index, member in enumerate(candidate.expected_members)
        if member.case_id == candidate.reference_member
    )
    if len(reference_matches) != 1:
        raise ValueError("relative-change reference member must identify exactly one case")
    reference = operands[0][reference_matches[0]]
    if reference == 0:
        raise ValueError("relative-change reference must not be zero")
    changes = tuple((value - reference) / reference for value in operands[0])
    try:
        return tuple(convert_value(value, "1", candidate.output_unit) for value in changes)
    except ValueError as error:
        raise ValueError("relative-change output unit must be dimensionless") from error


_TREND_MAP = {
    TrendKind.MONOTONIC_INCREASING: DiscreteTrend.MONOTONIC_INCREASING,
    TrendKind.MONOTONIC_DECREASING: DiscreteTrend.MONOTONIC_DECREASING,
    TrendKind.INTERIOR_PEAK: DiscreteTrend.INTERIOR_PEAK,
    TrendKind.PLATEAU: DiscreteTrend.PLATEAU,
    TrendKind.INTERIOR_TROUGH: DiscreteTrend.OVERALL_CHANGE,
    TrendKind.MIXED: DiscreteTrend.OVERALL_CHANGE,
}


def _trend(candidate: CandidateQoIContract, values: tuple[float, ...]) -> DiscreteTrend:
    members = candidate.expected_members
    if len(members) < 2:
        raise ValueError("QoI analysis requires at least two expected members")
    coordinate_name = members[0].coordinate_name
    coordinate_unit = members[0].coordinate_unit
    if any(member.coordinate_name != coordinate_name for member in members):
        raise ValueError("all expected members must use one coordinate")
    try:
        coordinates = tuple(
            convert_value(member.coordinate_value, member.coordinate_unit, coordinate_unit)
            for member in members
        )
    except ValueError as error:
        raise ValueError("expected-member coordinate units are incompatible") from error
    if len(set(coordinates)) != len(coordinates):
        raise ValueError("duplicate coordinate in expected membership")
    if len(coordinates) == 2:
        return DiscreteTrend.OVERALL_CHANGE
    assessment = detect_trend(coordinates, values, tolerance=candidate.trend_tolerance)
    return _TREND_MAP[assessment.kind]


def analyze_qoi(
    contract: LockedQoIContract,
    observations: ObservationTable,
    qualification: QualificationReport,
) -> QoIAnalysis:
    """Evaluate one unchanged, complete discrete QoI sequence without interpolation."""

    _verify_inputs(contract, observations, qualification)
    candidate = contract.candidate
    operand_rows = _ordered_operands(candidate, observations)
    evaluated = _evaluate_values(candidate, operand_rows)
    if any(not math.isfinite(value) for value in evaluated):
        raise ValueError("QoI operator produced a nonfinite value")
    trend = _trend(candidate, evaluated)

    values: list[QoIValue] = []
    for index, (member, value) in enumerate(
        zip(candidate.expected_members, evaluated, strict=True), start=1
    ):
        rows = tuple(group[index - 1] for group in operand_rows)
        locators = tuple(row.source_locator for row in rows)
        evidence_id = canonical_sha256(
            {"source_sha256": observations.source_sha256, "locators": locators},
            domain=b"cfdpaper-v03-qoi-evidence",
        )
        result_id = canonical_sha256(
            {
                "qoi_contract_id": candidate.qoi_contract_id,
                "case_id": member.case_id,
                "coordinate": (member.coordinate_value, member.coordinate_unit),
            },
            domain=b"cfdpaper-v03-qoi-result",
        )
        values.append(
            QoIValue(
                result_id=f"qoi-result-{result_id[:16]}",
                case_id=member.case_id,
                coordinate_value=member.coordinate_value,
                coordinate_unit=member.coordinate_unit,
                value=value,
                unit=candidate.output_unit,
                evidence_id=f"observation-{evidence_id[:16]}",
                source_locator=" | ".join(locators),
            )
        )
    return QoIAnalysis(
        qoi_contract_id=candidate.qoi_contract_id,
        scientific_input_fingerprint=contract.scientific_input_fingerprint,
        values=tuple(values),
        overall_change=evaluated[-1] - evaluated[0],
        trend=trend,
        restrictions=qualification.restrictions,
    )
