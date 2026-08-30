from __future__ import annotations

import pytest

from cfdpaper.scientific import (
    CaseDefinition,
    ClaimCeiling,
    ConvergenceGrade,
    EvidenceMaturity,
    QoIDefinition,
    assess_claim_ceiling,
    assess_conservation,
    assess_evidence_maturity,
    check_case_comparability,
    check_qoi_definition,
    convert_value,
    detect_trend,
    grade_convergence,
    units_compatible,
)


def test_units_check_dimensions_and_convert_scale() -> None:
    assert units_compatible("kPa", "Pa")
    assert not units_compatible("K", "Pa")
    assert not units_compatible(None, None)
    assert convert_value(1.5, "kPa", "Pa") == pytest.approx(1500.0)


def test_case_comparability_requires_matching_operating_conditions() -> None:
    reference = CaseDefinition(
        case_id="baseline",
        conditions={"load": (100.0, "%"), "inlet_temperature": (300.0, "K")},
    )
    candidate = CaseDefinition(
        case_id="changed-load",
        conditions={"load": (40.0, "%"), "inlet_temperature": (300.0, "K")},
    )

    result = check_case_comparability(reference, candidate, required=("load", "inlet_temperature"))

    assert not result.comparable
    assert any("load" in blocker for blocker in result.blockers)


def test_case_comparability_blocks_identical_unregistered_units() -> None:
    reference = CaseDefinition("a", {"rotation": (1500.0, "rpm")})
    candidate = CaseDefinition("b", {"rotation": (1500.0, "rpm")})

    result = check_case_comparability(reference, candidate)

    assert not result.comparable
    assert "unknown unit" in result.blockers[0]


def test_case_comparability_blocks_missing_units_with_reason() -> None:
    reference = CaseDefinition("a", {"load": (100.0, None)})
    candidate = CaseDefinition("b", {"load": (100.0, None)})

    result = check_case_comparability(reference, candidate)

    assert not result.comparable
    assert "missing unit" in result.blockers[0]


def test_case_comparability_rejects_nonfinite_values() -> None:
    reference = CaseDefinition("a", {"load": (float("inf"), "%")})
    candidate = CaseDefinition("b", {"load": (float("inf"), "%")})

    result = check_case_comparability(reference, candidate)

    assert not result.comparable
    assert "finite" in result.blockers[0]


@pytest.mark.parametrize(
    ("relative_tolerance", "absolute_tolerance"),
    [(float("nan"), 0.0), (0.0, float("inf")), (-1.0, 0.0)],
)
def test_case_comparability_rejects_invalid_tolerances(
    relative_tolerance: float, absolute_tolerance: float
) -> None:
    reference = CaseDefinition("a", {"load": (100.0, "%")})

    with pytest.raises(ValueError, match="tolerance.*finite and non-negative"):
        check_case_comparability(
            reference,
            reference,
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        )


def test_case_definition_mappings_are_defensive_and_immutable() -> None:
    conditions = {"load": (100.0, "%")}
    case = CaseDefinition("a", conditions)
    conditions["load"] = (50.0, "%")

    assert case.conditions["load"] == (100.0, "%")
    with pytest.raises(TypeError):
        case.conditions["load"] = (50.0, "%")  # type: ignore[index]


def test_convergence_grading_requires_residual_and_monitor_evidence() -> None:
    weak = grade_convergence(
        residuals={"continuity": 2e-3, "energy": 5e-5},
        residual_targets={"continuity": 1e-4, "energy": 1e-6},
        qoi_relative_span=None,
    )
    strong = grade_convergence(
        residuals={"continuity": 5e-5, "energy": 5e-7},
        residual_targets={"continuity": 1e-4, "energy": 1e-6},
        qoi_relative_span=0.002,
    )

    assert weak.grade == ConvergenceGrade.WEAK
    assert strong.grade == ConvergenceGrade.STRONG


@pytest.mark.parametrize(
    "residuals,residual_targets,qoi_span,strong_tolerance,moderate_tolerance",
    [
        ({"continuity": float("nan")}, {"continuity": 1e-4}, 0.001, 0.005, 0.01),
        ({"continuity": -1e-5}, {"continuity": 1e-4}, 0.001, 0.005, 0.01),
        ({"continuity": 1e-5}, {"continuity": 1e-4}, float("inf"), 0.005, 0.01),
        ({"continuity": 1e-5}, {"continuity": 0.0}, 0.001, 0.005, 0.01),
        ({"continuity": 1e-5}, {"continuity": 1e-4}, 0.001, -0.1, 0.01),
    ],
)
def test_convergence_invalid_numeric_inputs_never_grade_strong(
    residuals: dict[str, float],
    residual_targets: dict[str, float],
    qoi_span: float,
    strong_tolerance: float,
    moderate_tolerance: float,
) -> None:
    result = grade_convergence(
        residuals,
        residual_targets,
        qoi_relative_span=qoi_span,
        strong_monitor_tolerance=strong_tolerance,
        moderate_monitor_tolerance=moderate_tolerance,
    )

    assert result.grade == ConvergenceGrade.INVALID
    assert result.reasons


def test_conservation_reports_signed_and_relative_closure() -> None:
    result = assess_conservation(inflow=10.0, outflow=9.98, tolerance=0.005)

    assert result.signed_imbalance == pytest.approx(0.02)
    assert result.relative_imbalance == pytest.approx(0.002)
    assert result.passes


def test_zero_throughput_cannot_be_declared_closed() -> None:
    result = assess_conservation(inflow=0.0, outflow=0.0)

    assert not result.passes
    assert "undefined" in result.reason


@pytest.mark.parametrize(
    "inflow,outflow,tolerance,zero_floor",
    [
        (float("nan"), 1.0, 0.01, 1e-15),
        (1.0, float("inf"), 0.01, 1e-15),
        (1.0, 1.0, float("nan"), 1e-15),
        (1.0, 1.0, -0.1, 1e-15),
        (1.0, 1.0, 0.01, 0.0),
    ],
)
def test_conservation_rejects_nonfinite_values_and_invalid_tolerances(
    inflow: float, outflow: float, tolerance: float, zero_floor: float
) -> None:
    with pytest.raises(ValueError, match="finite|non-negative|positive"):
        assess_conservation(
            inflow,
            outflow,
            tolerance=tolerance,
            zero_floor=zero_floor,
        )


def test_qoi_definition_requires_reproducible_scope_and_reduction() -> None:
    incomplete = QoIDefinition(
        name="recirculation strength",
        unit="W",
        formula=None,
        spatial_scope="X/D=1",
        reduction=None,
    )

    result = check_qoi_definition(incomplete)

    assert not result.valid
    assert result.missing == ("formula", "reduction")


def test_trend_detector_distinguishes_monotonic_peak_and_plateau() -> None:
    increasing = detect_trend([0, 1, 2], [1.0, 2.0, 3.0])
    peak = detect_trend([0, 1, 2], [1.0, 3.0, 2.0])
    plateau = detect_trend([0, 1, 2, 3], [1.0, 2.0, 2.001, 2.0005], tolerance=0.002)

    assert increasing.kind == "monotonic-increasing"
    assert peak.kind == "interior-peak"
    assert peak.peak_x == 1
    assert plateau.kind == "plateau"
    assert plateau.plateau_start_x == 1


def test_small_positive_steps_with_cumulative_drift_are_not_a_plateau() -> None:
    trend = detect_trend(
        [0, 1, 2, 3],
        [1.0, 1.0015, 1.0030, 1.0045],
        tolerance=0.002,
    )

    assert trend.kind == "monotonic-increasing"
    assert trend.contradicts("monotonic-decreasing")


def test_cumulative_small_negative_drift_contradicts_increasing_claim() -> None:
    trend = detect_trend(
        [0, 1, 2, 3],
        [1.0045, 1.0030, 1.0015, 1.0],
        tolerance=0.002,
    )

    assert trend.kind == "monotonic-decreasing"
    assert trend.contradicts("monotonic-increasing")


def test_two_flat_tail_points_are_insufficient_to_declare_a_plateau() -> None:
    trend = detect_trend([0, 1, 2, 3], [1.0, 2.0, 3.0, 3.0001], tolerance=0.001)

    assert trend.kind == "monotonic-increasing"


def test_two_constant_points_are_insufficient_to_declare_a_plateau() -> None:
    trend = detect_trend([0, 1], [2.0, 2.0], tolerance=0.001)

    assert trend.kind == "mixed"


@pytest.mark.parametrize("tolerance", [float("nan"), float("inf"), -0.1])
def test_trend_detector_rejects_invalid_tolerance(tolerance: float) -> None:
    with pytest.raises(ValueError, match="tolerance must be finite and non-negative"):
        detect_trend([0, 1], [1.0, 2.0], tolerance=tolerance)


def test_evidence_maturity_and_claim_ceiling_require_scientific_prerequisites() -> None:
    convergence = grade_convergence(
        residuals={"continuity": 5e-5},
        residual_targets={"continuity": 1e-4},
        qoi_relative_span=0.002,
    )
    conservation = assess_conservation(10.0, 9.98)
    qoi = check_qoi_definition(
        QoIDefinition(
            name="pressure drop",
            unit="Pa",
            formula="p_in - p_out",
            spatial_scope="area-averaged inlet and outlet",
            reduction="difference of area means",
        )
    )

    maturity = assess_evidence_maturity(
        has_provenance=True,
        comparable=True,
        convergence=convergence,
        conservation=conservation,
        qoi=qoi,
        approved_by="Dr. Author",
    )
    ceiling = assess_claim_ceiling(maturity=maturity, independent_validation=False)

    assert maturity.level == EvidenceMaturity.AUTHOR_APPROVED
    assert ceiling.ceiling == ClaimCeiling.MECHANISM
    assert not ceiling.allows(ClaimCeiling.VALIDATION)


def test_reversed_increment_blocks_monotonic_claim_ceiling() -> None:
    convergence = grade_convergence(
        {"continuity": 5e-5},
        {"continuity": 1e-4},
        qoi_relative_span=0.002,
    )
    qoi = check_qoi_definition(
        QoIDefinition("pressure drop", "Pa", "p_in-p_out", "inlet/outlet", "difference")
    )
    trend = detect_trend([0, 1, 2], [1.0, 1.8, 1.3])

    maturity = assess_evidence_maturity(
        has_provenance=True,
        comparable=True,
        convergence=convergence,
        conservation=assess_conservation(10.0, 9.99),
        qoi=qoi,
        trend=trend,
        claimed_trend="monotonic-increasing",
        approved_by="Dr. Author",
    )
    ceiling = assess_claim_ceiling(maturity=maturity, independent_validation=True)

    assert maturity.trend_contradiction
    assert maturity.level == EvidenceMaturity.SCREENED
    assert not ceiling.allows(ClaimCeiling.VALIDATION)


@pytest.mark.parametrize(
    ("trend_values", "claimed_trend", "expected_reason", "is_contradiction"),
    [
        (None, "monotonic-increasing", "requires trend evidence", False),
        ([1.0, 2.0, 2.0, 2.0], "monotonic-increasing", "does not support", False),
        ([1.0, 2.0, 3.0], "not-a-trend", "invalid claimed trend", False),
    ],
)
def test_claimed_trend_requires_valid_kind_and_exact_support(
    trend_values: list[float] | None,
    claimed_trend: str,
    expected_reason: str,
    is_contradiction: bool,
) -> None:
    convergence = grade_convergence(
        {"continuity": 1e-5}, {"continuity": 1e-4}, qoi_relative_span=0.001
    )
    qoi = check_qoi_definition(QoIDefinition("q", "Pa", "p", "outlet", "area mean"))
    trend = (
        detect_trend(list(range(len(trend_values))), trend_values)
        if trend_values is not None
        else None
    )

    maturity = assess_evidence_maturity(
        has_provenance=True,
        comparable=True,
        convergence=convergence,
        conservation=assess_conservation(1.0, 1.0),
        qoi=qoi,
        trend=trend,
        claimed_trend=claimed_trend,
    )

    assert maturity.level == EvidenceMaturity.SCREENED
    assert maturity.trend_claim_blocked
    assert maturity.trend_contradiction is is_contradiction
    assert expected_reason in " ".join(maturity.blockers)


@pytest.mark.parametrize("approved_by", ["   ", True])
def test_approval_requires_nonempty_author_identity(approved_by: object) -> None:
    convergence = grade_convergence(
        {"continuity": 5e-5},
        {"continuity": 1e-4},
        qoi_relative_span=0.002,
    )
    qoi = check_qoi_definition(QoIDefinition("q", "Pa", "p", "outlet", "area mean"))

    with pytest.raises(ValueError, match="author identity"):
        assess_evidence_maturity(
            has_provenance=True,
            comparable=True,
            convergence=convergence,
            conservation=assess_conservation(1.0, 1.0),
            qoi=qoi,
            approved_by=approved_by,  # type: ignore[arg-type]
        )
