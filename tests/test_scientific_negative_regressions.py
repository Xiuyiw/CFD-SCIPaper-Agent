"""Synthetic regressions for general scientific-reasoning failure classes.

The values and case identities are invented and contain no project or private fixture data.
"""

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
    detect_trend,
    grade_convergence,
)
from cfdpaper.topic_generation.opportunities import discover_research_opportunities
from tests.topic_generation.test_opportunities import synthetic_snapshot


def test_incomparable_cases_are_blocked() -> None:
    a = CaseDefinition("case-a", {"load": (100.0, "%"), "inlet_velocity": (10.0, "m/s")})
    b = CaseDefinition("case-b", {"load": (50.0, "%"), "inlet_velocity": (10.0, "m/s")})

    assert not check_case_comparability(a, b, required=("load", "inlet_velocity")).comparable


def test_false_monotonic_claim_is_blocked_by_interior_peak() -> None:
    trend = detect_trend([0.0, 0.5, 1.0], [1.0, 1.8, 1.3])

    assert trend.kind == "interior-peak"
    assert not trend.supports("monotonic-increasing")


def test_weak_convergence_and_missing_qoi_block_verification() -> None:
    convergence = grade_convergence(
        residuals={"continuity": 1e-2},
        residual_targets={"continuity": 1e-4},
        qoi_relative_span=None,
    )
    qoi = check_qoi_definition(
        QoIDefinition(
            name="undefined performance index",
            unit=None,
            formula=None,
            spatial_scope=None,
            reduction=None,
        )
    )
    maturity = assess_evidence_maturity(
        has_provenance=True,
        comparable=True,
        convergence=convergence,
        conservation=assess_conservation(10.0, 10.0),
        qoi=qoi,
    )

    assert convergence.grade == ConvergenceGrade.WEAK
    assert not qoi.valid
    assert maturity.level == EvidenceMaturity.SCREENED
    assert "convergence" in " ".join(maturity.blockers)
    assert "QoI" in " ".join(maturity.blockers)


def test_author_approval_cannot_override_failed_science_checks() -> None:
    maturity = assess_evidence_maturity(
        has_provenance=False,
        comparable=False,
        convergence=grade_convergence({}, {}, qoi_relative_span=None),
        conservation=assess_conservation(0.0, 0.0),
        qoi=check_qoi_definition(QoIDefinition(name="q", unit=None)),
        approved_by="Dr. Reviewer",
    )
    ceiling = assess_claim_ceiling(maturity=maturity, independent_validation=False)

    assert maturity.level == EvidenceMaturity.RAW
    assert maturity.approval_rejected
    assert ceiling.ceiling == ClaimCeiling.OBSERVATION
    assert not ceiling.allows(ClaimCeiling.MECHANISM)


def test_monotonic_claim_with_reverse_increment_cannot_be_validated() -> None:
    convergence = grade_convergence(
        {"continuity": 1e-5}, {"continuity": 1e-4}, qoi_relative_span=0.001
    )
    qoi = check_qoi_definition(
        QoIDefinition("synthetic index", "1", "a/b", "domain", "volume mean")
    )
    trend = detect_trend([0.0, 0.5, 1.0], [1.0, 1.8, 1.3])
    maturity = assess_evidence_maturity(
        has_provenance=True,
        comparable=True,
        convergence=convergence,
        conservation=assess_conservation(10.0, 10.0),
        qoi=qoi,
        trend=trend,
        claimed_trend="monotonic-increasing",
        approved_by="Dr. Reviewer",
    )

    ceiling = assess_claim_ceiling(maturity=maturity, independent_validation=True)

    assert maturity.trend_contradiction
    assert not ceiling.allows(ClaimCeiling.VALIDATION)


def test_incomplete_comparison_blocks_false_publication_conclusions() -> None:
    snapshot = synthetic_snapshot(
        values=(1.0, 2.0, 3.0),
        qoi_values=(1.0, 1.8, 1.3),
        comparable=False,
        strong=False,
        definition=False,
    )

    result = discover_research_opportunities(snapshot)

    assert all(not item.defensible for item in result.opportunities)
    assert all(item.trend_type != "monotonic-increasing" for item in result.opportunities)
    assert all(
        item.claim_ceiling not in {"mechanism", "validation", "engineering"}
        for item in result.opportunities
    )
    prohibited = {text for item in result.opportunities for text in item.prohibited_inferences}
    assert {"continuous optimum", "stable operating window"}.issubset(prohibited)
