"""Evidence grading for steady CFD convergence."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class ConvergenceGrade(str, Enum):
    INVALID = "invalid"
    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


@dataclass(frozen=True, slots=True)
class ConvergenceAssessment:
    grade: ConvergenceGrade
    residuals_pass: bool
    monitor_pass: bool
    reasons: tuple[str, ...]


def grade_convergence(
    residuals: Mapping[str, float],
    residual_targets: Mapping[str, float],
    *,
    qoi_relative_span: float | None,
    strong_monitor_tolerance: float = 0.005,
    moderate_monitor_tolerance: float = 0.01,
) -> ConvergenceAssessment:
    """Grade residual and monitored-QoI evidence without inferring missing history."""

    invalid: list[str] = []
    for name, value in residuals.items():
        if not math.isfinite(value) or value < 0:
            invalid.append(f"residual {name} must be finite and non-negative")
    for name, value in residual_targets.items():
        if not math.isfinite(value) or value <= 0:
            invalid.append(f"residual tolerance {name} must be finite and positive")
    if qoi_relative_span is not None and (
        not math.isfinite(qoi_relative_span) or qoi_relative_span < 0
    ):
        invalid.append("QoI relative span must be finite and non-negative")
    for name, value in (
        ("strong monitor tolerance", strong_monitor_tolerance),
        ("moderate monitor tolerance", moderate_monitor_tolerance),
    ):
        if not math.isfinite(value) or value <= 0:
            invalid.append(f"{name} must be finite and positive")
    if strong_monitor_tolerance > moderate_monitor_tolerance:
        invalid.append("strong monitor tolerance cannot exceed moderate monitor tolerance")
    if invalid:
        return ConvergenceAssessment(ConvergenceGrade.INVALID, False, False, tuple(invalid))
    if not residuals or not residual_targets:
        return ConvergenceAssessment(
            ConvergenceGrade.NONE,
            False,
            False,
            ("residual history or criteria are missing", "monitored QoI stability is missing"),
        )
    missing = tuple(sorted(set(residual_targets) - set(residuals)))
    residuals_pass = not missing and all(
        residuals[name] <= target for name, target in residual_targets.items()
    )
    monitor_pass = qoi_relative_span is not None and qoi_relative_span <= moderate_monitor_tolerance
    reasons: list[str] = []
    if missing:
        reasons.append(f"residuals missing for: {', '.join(missing)}")
    if not residuals_pass:
        reasons.append("one or more residual criteria are not met")
    if qoi_relative_span is None:
        reasons.append("monitored QoI stability is missing")
    elif not monitor_pass:
        reasons.append("monitored QoI remains variable")
    if residuals_pass and qoi_relative_span is not None:
        if qoi_relative_span <= strong_monitor_tolerance:
            grade = ConvergenceGrade.STRONG
        elif monitor_pass:
            grade = ConvergenceGrade.MODERATE
        else:
            grade = ConvergenceGrade.WEAK
    elif residuals_pass:
        grade = ConvergenceGrade.MODERATE
    else:
        grade = ConvergenceGrade.WEAK
    return ConvergenceAssessment(grade, residuals_pass, monitor_pass, tuple(reasons))
