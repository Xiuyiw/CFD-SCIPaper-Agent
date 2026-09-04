from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from cfdpaper.planning import PlanApproval
from cfdpaper.qualification.artifacts import (
    candidate_qoi_contract_path,
    load_json_model,
    locked_qoi_contract_path,
    qoi_results_path,
    scientific_input_fingerprint,
    write_json_atomic,
)
from cfdpaper.qualification.claims import (
    assess_v03_claim_ceiling,
    build_candidate_figure_contract,
)
from cfdpaper.qualification.comparison import propose_qoi_contract, qualify_comparison
from cfdpaper.qualification.models import (
    AuthorApproval,
    CandidateQoIContract,
    CaseDifference,
    ConservationObservation,
    ConvergenceObservation,
    DiscreteTrend,
    ExpectedMember,
    LockedQoIContract,
    ObservationRow,
    ObservationTable,
    OperandSelector,
    QoIAnalysis,
    QoIProposal,
    ThresholdBasis,
    ValueRole,
    VNVStatus,
)
from cfdpaper.qualification.qoi import analyze_qoi, lock_qoi_contract


def _status(label: str = "demonstrated") -> VNVStatus:
    return VNVStatus(
        state=label,
        summary=f"{label} for the intended numerical comparison",
        evidence_ids=(f"evidence-{label}",) if label != "not-demonstrated" else (),
        basis="located numerical evidence" if label != "not-demonstrated" else None,
        source_locator="verification.md#result" if label != "not-demonstrated" else None,
    )


def _threshold(kind: type[ConvergenceObservation], metric: str):
    return kind(
        metric=metric,
        observed_value=0.001,
        unit="1",
        threshold=ThresholdBasis(
            metric=metric,
            operator="<=",
            value=0.01,
            unit="1",
            basis="declared numerical criterion",
            source_locator=f"records.json#/thresholds/{metric}",
            consequence="blocking",
        ),
        evidence_id=f"evidence-{metric}",
        source_locator=f"solver.txt#{metric}",
    )


def _table(
    values: tuple[float, ...] = (10.0, 20.0, 40.0),
    coordinates: tuple[float, ...] = (0.2, 0.5, 1.1),
    *,
    unit: str = "Pa",
    value_role: ValueRole = ValueRole.PRECOMPUTED_QOI,
    extra_rows: tuple[ObservationRow, ...] = (),
) -> ObservationTable:
    rows = tuple(
        ObservationRow(
            case_id=f"C{index}",
            coordinate_name="flow_rate",
            coordinate_value=coordinate,
            coordinate_unit="kg/s",
            variable="pressure_drop",
            value=value,
            value_role=value_role,
            unit=unit,
            scope="inlet-to-outlet",
            source_locator=f"observations.csv#row={index + 1}",
        )
        for index, (coordinate, value) in enumerate(zip(coordinates, values, strict=True), start=1)
    )
    return ObservationTable(
        source_uri="observations.csv",
        source_sha256="a" * 64,
        rows=rows + extra_rows,
    )


def _qualification(table: ObservationTable, *, status: str = "eligible"):
    if status == "insufficient":
        differences = (
            CaseDifference(
                name="geometry",
                reference="A",
                candidate="B",
                role="blocking",
            ),
        )
    elif status == "restricted":
        differences = (
            CaseDifference(
                name="flow rate",
                reference="low",
                candidate="high",
                role="intended-study-factor",
            ),
            CaseDifference(
                name="roughness",
                reference="reported",
                candidate="unreported",
                role="unresolved-nuisance",
            ),
        )
    else:
        differences = (
            CaseDifference(
                name="flow rate",
                reference="low",
                candidate="high",
                role="intended-study-factor",
            ),
        )
    return qualify_comparison(
        differences=differences,
        verification=_status(),
        validation=_status(),
        convergence=(_threshold(ConvergenceObservation, "monitor-drift"),),
        conservation=(_threshold(ConservationObservation, "mass-imbalance"),),
        observation_table=table,
    )


def _members(table: ObservationTable, *, variable: str = "pressure_drop"):
    return tuple(
        ExpectedMember(
            case_id=row.case_id,
            coordinate_name=row.coordinate_name,
            coordinate_value=row.coordinate_value,
            coordinate_unit=row.coordinate_unit,
            variable=variable,
            unit=row.unit,
            scope=row.scope,
        )
        for row in table.rows
        if row.variable == variable
    )


def _candidate(
    table: ObservationTable,
    *,
    operator: str = "identity",
    operands: tuple[OperandSelector, ...] | None = None,
    output_unit: str = "Pa",
    reference_member: str | None = None,
    trend_tolerance: float = 0.0,
    qualification_status: str = "eligible",
    expected_members: tuple[ExpectedMember, ...] | None = None,
    allow_quantitative_reporting: bool = True,
) -> tuple[CandidateQoIContract, object]:
    proposal = QoIProposal(
        qoi_name="pressure response",
        scientific_definition="declared pressure response over the complete sequence",
        operator=operator,
        operands=operands
        or (
            OperandSelector(
                name="pressure",
                variable="pressure_drop",
                value_role=ValueRole.PRECOMPUTED_QOI,
                unit="Pa",
                scope="inlet-to-outlet",
                locator_policy="one located scalar per expected member",
            ),
        ),
        output_unit=output_unit,
        expected_members=expected_members or _members(table),
        trend_tolerance=trend_tolerance,
        reference_member=reference_member,
        allow_quantitative_reporting=allow_quantitative_reporting,
    )
    report = _qualification(table, status=qualification_status)
    return (
        propose_qoi_contract(
            question_id="rq-pressure",
            topic_fingerprint="b" * 64,
            qualification=report,
            observations=table,
            proposal=proposal,
        ),
        report,
    )


def _approval(*, scope: str = "manuscript-topic", author: str = "A. Author") -> PlanApproval:
    return PlanApproval(
        topic_id="topic-pressure",
        author=author,
        scope=scope,
        plan_fingerprint="b" * 64,
        approved_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )


def _lock(candidate: CandidateQoIContract, *, author: str = "A. Author") -> LockedQoIContract:
    return lock_qoi_contract(
        candidate,
        candidate_fingerprint=candidate.fingerprint,
        current_input_fingerprint=candidate.scientific_input_fingerprint,
        topic_approval=_approval(author=author),
        author=author,
        approved_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
    )


def test_lock_requires_exact_manuscript_topic_and_author_binding() -> None:
    candidate, _ = _candidate(_table())

    with pytest.raises(ValueError, match="manuscript-topic"):
        lock_qoi_contract(
            candidate,
            candidate_fingerprint=candidate.fingerprint,
            current_input_fingerprint=candidate.scientific_input_fingerprint,
            topic_approval=_approval(scope="direction-only"),
            author="A. Author",
            approved_at=datetime.now(timezone.utc),
        )
    with pytest.raises(ValueError, match="author"):
        lock_qoi_contract(
            candidate,
            candidate_fingerprint=candidate.fingerprint,
            current_input_fingerprint=candidate.scientific_input_fingerprint,
            topic_approval=_approval(),
            author="Different Author",
            approved_at=datetime.now(timezone.utc),
        )
    with pytest.raises(ValueError, match="candidate fingerprint"):
        lock_qoi_contract(
            candidate,
            candidate_fingerprint="c" * 64,
            current_input_fingerprint=candidate.scientific_input_fingerprint,
            topic_approval=_approval(),
            author="A. Author",
            approved_at=datetime.now(timezone.utc),
        )
    with pytest.raises(ValidationError, match="timezone-aware"):
        lock_qoi_contract(
            candidate,
            candidate_fingerprint=candidate.fingerprint,
            current_input_fingerprint=candidate.scientific_input_fingerprint,
            topic_approval=_approval(),
            author="A. Author",
            approved_at=datetime(2026, 9, 2),
        )


def test_lock_preserves_candidate_and_rejects_any_stale_scientific_input() -> None:
    candidate, _ = _candidate(_table())
    locked = _lock(candidate)

    assert locked.candidate == candidate
    assert locked.approval.object_id == candidate.qoi_contract_id
    assert locked.approval.object_fingerprint == candidate.fingerprint
    assert locked.approval.approved_at.utcoffset() is not None

    with pytest.raises(ValueError, match="scientific input"):
        lock_qoi_contract(
            candidate,
            candidate_fingerprint=candidate.fingerprint,
            current_input_fingerprint="d" * 64,
            topic_approval=_approval(),
            author="A. Author",
            approved_at=datetime.now(timezone.utc),
        )


def test_loaded_locked_contract_cannot_detach_approval_from_candidate() -> None:
    candidate, _ = _candidate(_table())
    locked = _lock(candidate)
    payload = locked.model_dump(mode="python")
    payload["approval"]["object_id"] = "qoi-other"

    with pytest.raises(ValidationError, match="approval.*candidate"):
        LockedQoIContract.model_validate(payload)


def test_lock_rejects_forged_candidate_content_and_insufficient_comparison() -> None:
    candidate, _ = _candidate(_table())
    forged = candidate.model_dump(mode="python")
    forged["qoi_name"] = "changed after qualification"
    forged_candidate = CandidateQoIContract.model_validate(forged)
    with pytest.raises(ValueError, match="candidate fingerprint"):
        _lock(forged_candidate)

    with pytest.raises(ValueError, match="insufficient"):
        _candidate(_table(), qualification_status="insufficient")


def test_identity_converts_units_and_preserves_nonuniform_coordinates() -> None:
    table = _table(values=(1000.0, 2000.0, 4000.0))
    candidate, report = _candidate(table, output_unit="kPa")

    result = analyze_qoi(_lock(candidate), table, report)

    assert [item.coordinate_value for item in result.values] == [0.2, 0.5, 1.1]
    assert [item.value for item in result.values] == pytest.approx([1.0, 2.0, 4.0])
    assert all(item.unit == "kPa" for item in result.values)
    assert result.overall_change == pytest.approx(3.0)
    assert result.trend == DiscreteTrend.MONOTONIC_INCREASING


def test_analysis_preserves_locked_reporting_and_axis_semantics() -> None:
    table = _table()
    candidate, report = _candidate(table, allow_quantitative_reporting=False)

    result = analyze_qoi(_lock(candidate), table, report)

    assert result.quantitative_reporting_allowed is False
    assert result.coordinate_name == "flow_rate"
    assert result.qoi_name == "pressure response"
    assert result.scientific_definition == "declared pressure response over the complete sequence"


def test_analysis_normalizes_compatible_coordinate_units_without_interpolation() -> None:
    table = _table()
    members = (
        ExpectedMember(
            case_id="C1",
            coordinate_name="flow_rate",
            coordinate_value=0.2,
            coordinate_unit="kg/s",
            variable="pressure_drop",
            unit="Pa",
            scope="inlet-to-outlet",
        ),
        ExpectedMember(
            case_id="C2",
            coordinate_name="flow_rate",
            coordinate_value=500.0,
            coordinate_unit="g/s",
            variable="pressure_drop",
            unit="Pa",
            scope="inlet-to-outlet",
        ),
        ExpectedMember(
            case_id="C3",
            coordinate_name="flow_rate",
            coordinate_value=1.1,
            coordinate_unit="kg/s",
            variable="pressure_drop",
            unit="Pa",
            scope="inlet-to-outlet",
        ),
    )
    candidate, report = _candidate(table, expected_members=members)

    result = analyze_qoi(_lock(candidate), table, report)

    assert tuple(value.coordinate_value for value in result.values) == (0.2, 0.5, 1.1)
    assert {value.coordinate_unit for value in result.values} == {"kg/s"}
    assert tuple(value.case_id for value in result.values) == ("C1", "C2", "C3")

    decision = assess_v03_claim_ceiling(report, result)
    figure = build_candidate_figure_contract(
        analysis=result,
        qualification=report,
        ceiling=decision,
        figure_id="fig-compatible-coordinate-units",
        author="A. Author",
    )

    assert figure.panels[0].x_values == (0.2, 0.5, 1.1)
    assert figure.panels[0].x_unit == "kg/s"


def test_difference_uses_two_named_scalar_roles_after_unit_conversion() -> None:
    base = _table(values=(1200.0, 2500.0, 4200.0))
    baseline_rows = tuple(
        ObservationRow(
            case_id=row.case_id,
            coordinate_name=row.coordinate_name,
            coordinate_value=row.coordinate_value,
            coordinate_unit=row.coordinate_unit,
            variable="baseline_pressure",
            value=value,
            value_role=ValueRole.DECLARED_AGGREGATE,
            unit="kPa",
            scope=row.scope,
            aggregation="area-weighted mean",
            source_locator=f"baseline.csv#row={index + 1}",
        )
        for index, (row, value) in enumerate(zip(base.rows, (1.0, 2.0, 3.0), strict=True), start=1)
    )
    table = _table(values=(1200.0, 2500.0, 4200.0), extra_rows=baseline_rows)
    operands = (
        OperandSelector(
            name="total",
            variable="pressure_drop",
            value_role=ValueRole.PRECOMPUTED_QOI,
            unit="Pa",
            scope="inlet-to-outlet",
            locator_policy="one located scalar per expected member",
        ),
        OperandSelector(
            name="baseline",
            variable="baseline_pressure",
            value_role=ValueRole.DECLARED_AGGREGATE,
            unit="kPa",
            scope="inlet-to-outlet",
            locator_policy="one located scalar per expected member",
        ),
    )
    candidate, report = _candidate(
        table,
        operator="difference",
        operands=operands,
        output_unit="Pa",
    )

    result = analyze_qoi(_lock(candidate), table, report)

    assert [item.value for item in result.values] == pytest.approx([200.0, 500.0, 1200.0])


@pytest.mark.parametrize(
    ("operator", "expected"),
    [
        ("difference", (5.0, 10.0, 20.0)),
        ("ratio", (2.0, 2.0, 2.0)),
    ],
)
def test_multi_operand_operator_distinguishes_roles_with_same_variable_and_scope(
    operator: str, expected: tuple[float, ...]
) -> None:
    primary = _table(values=(10.0, 20.0, 40.0))
    aggregate_rows = tuple(
        ObservationRow(
            case_id=row.case_id,
            coordinate_name=row.coordinate_name,
            coordinate_value=row.coordinate_value,
            coordinate_unit=row.coordinate_unit,
            variable=row.variable,
            value=value,
            value_role=ValueRole.DECLARED_AGGREGATE,
            unit=row.unit,
            scope=row.scope,
            aggregation="area-weighted mean",
            source_locator=f"aggregate.csv#row={index + 1}",
        )
        for index, (row, value) in enumerate(
            zip(primary.rows, (5.0, 10.0, 20.0), strict=True), start=1
        )
    )
    table = _table(values=(10.0, 20.0, 40.0), extra_rows=aggregate_rows)
    operands = (
        OperandSelector(
            name="primary",
            variable="pressure_drop",
            value_role=ValueRole.PRECOMPUTED_QOI,
            unit="Pa",
            scope="inlet-to-outlet",
            locator_policy="one located scalar per expected member",
        ),
        OperandSelector(
            name="aggregate",
            variable="pressure_drop",
            value_role=ValueRole.DECLARED_AGGREGATE,
            unit="Pa",
            scope="inlet-to-outlet",
            locator_policy="one located scalar per expected member",
        ),
    )
    candidate, report = _candidate(
        table,
        operator=operator,
        operands=operands,
        output_unit="Pa" if operator == "difference" else "1",
        expected_members=_members(primary),
    )

    result = analyze_qoi(_lock(candidate), table, report)

    assert [item.value for item in result.values] == pytest.approx(expected)


def test_multi_operand_operator_cannot_reuse_one_scientific_scalar_role() -> None:
    table = _table()
    same_role_twice = (
        OperandSelector(
            name="left",
            variable="pressure_drop",
            value_role=ValueRole.PRECOMPUTED_QOI,
            unit="Pa",
            scope="inlet-to-outlet",
            locator_policy="one located scalar per expected member",
        ),
        OperandSelector(
            name="right",
            variable="pressure_drop",
            value_role=ValueRole.PRECOMPUTED_QOI,
            unit="kPa",
            scope="inlet-to-outlet",
            locator_policy="one located scalar per expected member",
        ),
    )
    candidate, report = _candidate(
        table,
        operator="difference",
        operands=same_role_twice,
        output_unit="Pa",
    )

    with pytest.raises(ValueError, match="distinct scalar roles"):
        analyze_qoi(_lock(candidate), table, report)


def test_ratio_and_relative_change_are_dimensionless_and_reject_zero_reference() -> None:
    denominator_rows = tuple(
        ObservationRow(
            case_id=f"C{index}",
            coordinate_name="flow_rate",
            coordinate_value=coordinate,
            coordinate_unit="kg/s",
            variable="reference_pressure",
            value=value,
            value_role=ValueRole.DECLARED_AGGREGATE,
            unit="kPa",
            scope="inlet-to-outlet",
            aggregation="area-weighted mean",
            source_locator=f"reference.csv#row={index + 1}",
        )
        for index, (coordinate, value) in enumerate(
            zip((0.2, 0.5, 1.1), (0.01, 0.01, 0.02), strict=True), start=1
        )
    )
    ratio_table = _table(values=(10.0, 20.0, 40.0), extra_rows=denominator_rows)
    ratio_operands = (
        OperandSelector(
            name="response",
            variable="pressure_drop",
            value_role=ValueRole.PRECOMPUTED_QOI,
            unit="Pa",
            scope="inlet-to-outlet",
            locator_policy="one located scalar per expected member",
        ),
        OperandSelector(
            name="reference",
            variable="reference_pressure",
            value_role=ValueRole.DECLARED_AGGREGATE,
            unit="kPa",
            scope="inlet-to-outlet",
            locator_policy="one located scalar per expected member",
        ),
    )
    ratio_candidate, ratio_report = _candidate(
        ratio_table,
        operator="ratio",
        operands=ratio_operands,
        output_unit="1",
    )
    ratio = analyze_qoi(_lock(ratio_candidate), ratio_table, ratio_report)
    assert [item.value for item in ratio.values] == pytest.approx([1.0, 2.0, 2.0])
    assert all(item.unit == "1" for item in ratio.values)

    change_table = _table(values=(10.0, 15.0, 20.0))
    change_candidate, change_report = _candidate(
        change_table,
        operator="relative-change",
        output_unit="%",
        reference_member="C1",
    )
    change = analyze_qoi(_lock(change_candidate), change_table, change_report)
    assert [item.value for item in change.values] == pytest.approx([0.0, 50.0, 100.0])
    assert all(item.unit == "%" for item in change.values)

    zero_table = _table(values=(0.0, 15.0, 20.0))
    zero_candidate, zero_report = _candidate(
        zero_table,
        operator="relative-change",
        output_unit="1",
        reference_member="C1",
    )
    with pytest.raises(ValueError, match="reference.*zero"):
        analyze_qoi(_lock(zero_candidate), zero_table, zero_report)


def test_ratio_rejects_zero_denominator_and_incompatible_units() -> None:
    def second_rows(unit: str, values: tuple[float, ...]) -> tuple[ObservationRow, ...]:
        return tuple(
            ObservationRow(
                case_id=f"C{index}",
                coordinate_name="flow_rate",
                coordinate_value=coordinate,
                coordinate_unit="kg/s",
                variable="reference_pressure",
                value=value,
                value_role=ValueRole.DECLARED_AGGREGATE,
                unit=unit,
                scope="inlet-to-outlet",
                aggregation="area-weighted mean",
                source_locator=f"reference.csv#row={index + 1}",
            )
            for index, (coordinate, value) in enumerate(
                zip((0.2, 0.5, 1.1), values, strict=True), start=1
            )
        )

    operands = (
        OperandSelector(
            name="response",
            variable="pressure_drop",
            value_role=ValueRole.PRECOMPUTED_QOI,
            unit="Pa",
            scope="inlet-to-outlet",
            locator_policy="one located scalar per expected member",
        ),
        OperandSelector(
            name="reference",
            variable="reference_pressure",
            value_role=ValueRole.DECLARED_AGGREGATE,
            unit="Pa",
            scope="inlet-to-outlet",
            locator_policy="one located scalar per expected member",
        ),
    )
    zero_table = _table(extra_rows=second_rows("Pa", (5.0, 0.0, 10.0)))
    candidate, report = _candidate(zero_table, operator="ratio", operands=operands, output_unit="1")
    with pytest.raises(ValueError, match="denominator.*zero"):
        analyze_qoi(_lock(candidate), zero_table, report)

    bad_table = _table(extra_rows=second_rows("m", (5.0, 6.0, 7.0)))
    bad_candidate, bad_report = _candidate(
        bad_table, operator="ratio", operands=operands, output_unit="1"
    )
    with pytest.raises(ValueError, match="incompatible"):
        analyze_qoi(_lock(bad_candidate), bad_table, bad_report)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            "wrong-role",
            "undeclared value role 'raw-sample'; expected one of: precomputed-qoi",
        ),
        ("missing", "missing"),
        ("unexpected", "unexpected"),
        ("duplicate-coordinate", "duplicate"),
    ],
)
def test_complete_membership_and_operand_roles_are_strict(mutation: str, message: str) -> None:
    original = _table()
    original_members = _members(original)
    rows = list(original.rows)
    if mutation == "wrong-role":
        payload = rows[0].model_dump(mode="python")
        payload["value_role"] = ValueRole.RAW_SAMPLE
        rows[0] = ObservationRow.model_validate(payload)
    elif mutation == "missing":
        rows.pop()
    elif mutation == "unexpected":
        payload = rows[-1].model_dump(mode="python")
        payload["case_id"] = "C4"
        payload["coordinate_value"] = 1.5
        payload["source_locator"] = "observations.csv#row=5"
        rows.append(ObservationRow.model_validate(payload))
    else:
        payload = rows[-1].model_dump(mode="python")
        payload["case_id"] = rows[-2].case_id
        payload["coordinate_value"] = rows[-2].coordinate_value
        payload["source_locator"] = "observations.csv#row=5"
        rows.append(ObservationRow.model_validate(payload))
    changed = ObservationTable(
        source_uri=original.source_uri,
        source_sha256="c" * 64,
        rows=tuple(rows),
    )
    candidate, report = _candidate(changed, expected_members=original_members)

    with pytest.raises(ValueError, match=message):
        analyze_qoi(_lock(candidate), changed, report)


def test_changed_qualification_and_observation_fingerprints_are_rejected() -> None:
    table = _table()
    candidate, report = _candidate(table)
    changed_report = _qualification(table, status="restricted")
    with pytest.raises(ValueError, match="qualification"):
        analyze_qoi(_lock(candidate), table, changed_report)

    changed_table = ObservationTable(
        source_uri=table.source_uri,
        source_sha256="e" * 64,
        rows=table.rows,
    )
    with pytest.raises(ValueError, match="observation"):
        analyze_qoi(_lock(candidate), changed_table, report)


def test_two_points_are_only_overall_change_and_one_point_is_insufficient() -> None:
    two = _table(values=(1.0, 3.0), coordinates=(0.2, 1.1))
    candidate, report = _candidate(two)
    result = analyze_qoi(_lock(candidate), two, report)
    assert result.trend == DiscreteTrend.OVERALL_CHANGE
    assert result.overall_change == pytest.approx(2.0)

    one = _table(values=(1.0,), coordinates=(0.2,))
    one_candidate, one_report = _candidate(one)
    with pytest.raises(ValueError, match="at least two"):
        analyze_qoi(_lock(one_candidate), one, one_report)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ((1.0, 2.0, 3.0), DiscreteTrend.MONOTONIC_INCREASING),
        ((3.0, 2.0, 1.0), DiscreteTrend.MONOTONIC_DECREASING),
        ((1.0, 3.0, 2.0), DiscreteTrend.INTERIOR_PEAK),
        ((1.0, 2.0, 2.0, 2.0), DiscreteTrend.PLATEAU),
        ((3.0, 1.0, 2.0), DiscreteTrend.OVERALL_CHANGE),
    ],
)
def test_v03_trend_vocabulary_maps_complete_discrete_sequence(
    values: tuple[float, ...], expected: DiscreteTrend
) -> None:
    coordinates = (0.2, 0.5, 1.1) if len(values) == 3 else (0.2, 0.5, 1.1, 1.8)
    table = _table(values=values, coordinates=coordinates)
    candidate, report = _candidate(table, trend_tolerance=0.01)
    result = analyze_qoi(_lock(candidate), table, report)
    assert result.trend == expected


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
def test_trend_tolerance_must_be_explicit_finite_and_nonnegative(bad: float) -> None:
    table = _table()
    payload = {
        "qoi_name": "pressure",
        "scientific_definition": "pressure over the complete sequence",
        "operator": "identity",
        "operands": (
            OperandSelector(
                name="pressure",
                variable="pressure_drop",
                value_role=ValueRole.PRECOMPUTED_QOI,
                unit="Pa",
                scope="inlet-to-outlet",
                locator_policy="one located scalar per expected member",
            ),
        ),
        "output_unit": "Pa",
        "expected_members": _members(table),
        "trend_tolerance": bad,
    }
    with pytest.raises(ValidationError, match="finite and nonnegative"):
        QoIProposal.model_validate(payload)
    payload.pop("trend_tolerance")
    with pytest.raises(ValidationError):
        QoIProposal.model_validate(payload)


def test_checkpoint_one_artifacts_are_distinct_and_strictly_reloadable(tmp_path: Path) -> None:
    table = _table()
    candidate, report = _candidate(table)
    candidate_path = write_json_atomic(
        tmp_path, candidate_qoi_contract_path(tmp_path).name, candidate
    )
    before = candidate_path.read_bytes()
    locked = _lock(candidate)
    analysis = QoIAnalysis(
        qoi_contract_id=candidate.qoi_contract_id,
        qoi_name=candidate.qoi_name,
        scientific_definition=candidate.scientific_definition,
        coordinate_name=candidate.expected_members[0].coordinate_name,
        qualification_input_fingerprint=report.input_fingerprint,
        scientific_input_fingerprint=candidate.scientific_input_fingerprint,
        values=(),
        overall_change=None,
        trend=None,
        restrictions=("fixture only",),
        quantitative_reporting_allowed=candidate.allow_quantitative_reporting,
    )

    locked_path = write_json_atomic(tmp_path, locked_qoi_contract_path(tmp_path).name, locked)
    result_path = write_json_atomic(tmp_path, qoi_results_path(tmp_path).name, analysis)

    assert candidate_path.read_bytes() == before
    assert locked_path != candidate_path
    assert result_path != candidate_path
    assert load_json_model(tmp_path, locked_path.name, LockedQoIContract) == locked
    assert load_json_model(tmp_path, result_path.name, QoIAnalysis) == analysis


def test_scientific_fingerprint_binds_expected_members_qualification_and_topic() -> None:
    table = _table()
    candidate, report = _candidate(table)
    baseline = scientific_input_fingerprint(
        observation_table=table,
        expected_members=candidate.expected_members,
        qoi_contract=candidate,
        qualification=report,
        topic_fingerprint=candidate.topic_fingerprint,
    )
    changed_members = tuple(reversed(candidate.expected_members))
    assert baseline != scientific_input_fingerprint(
        observation_table=table,
        expected_members=changed_members,
        qoi_contract=candidate,
        qualification=report,
        topic_fingerprint=candidate.topic_fingerprint,
    )


def test_author_approval_is_immutable_and_requires_nonblank_identity() -> None:
    with pytest.raises(ValidationError, match="nonblank"):
        AuthorApproval(
            author=" ",
            object_id="qoi-1",
            object_fingerprint="a" * 64,
            approved_at=datetime.now(timezone.utc),
        )
