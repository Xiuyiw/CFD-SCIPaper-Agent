"""Discrete trend diagnostics that do not imply unsampled continuity."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum


class TrendKind(str, Enum):
    MONOTONIC_INCREASING = "monotonic-increasing"
    MONOTONIC_DECREASING = "monotonic-decreasing"
    INTERIOR_PEAK = "interior-peak"
    INTERIOR_TROUGH = "interior-trough"
    PLATEAU = "plateau"
    MIXED = "mixed"


@dataclass(frozen=True, slots=True)
class TrendAssessment:
    kind: TrendKind
    peak_x: float | None = None
    plateau_start_x: float | None = None
    note: str = "discrete sampled-case diagnostic"
    has_increase: bool = False
    has_decrease: bool = False

    def supports(self, claim: TrendKind | str) -> bool:
        try:
            claimed_kind = TrendKind(claim)
        except ValueError:
            return False
        return self.kind == claimed_kind

    def contradicts(self, claim: TrendKind | str) -> bool:
        if claim == TrendKind.MONOTONIC_INCREASING:
            return self.kind == TrendKind.MONOTONIC_DECREASING or self.has_decrease
        if claim == TrendKind.MONOTONIC_DECREASING:
            return self.kind == TrendKind.MONOTONIC_INCREASING or self.has_increase
        return False


def detect_trend(
    x: Sequence[float],
    y: Sequence[float],
    *,
    tolerance: float = 0.0,
) -> TrendAssessment:
    """Classify monotonic, interior-extremum, plateau, or mixed sampled trends."""

    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and non-negative")
    if len(x) != len(y) or len(x) < 2:
        raise ValueError("x and y must have equal length of at least two")
    if any(not math.isfinite(float(value)) for value in (*x, *y)):
        raise ValueError("trend inputs must be finite")
    if any(right <= left for left, right in zip(x, x[1:], strict=False)):
        raise ValueError("x must be strictly increasing")
    differences = [right - left for left, right in zip(y, y[1:], strict=False)]
    has_increase = any(value > tolerance for value in differences)
    has_decrease = any(value < -tolerance for value in differences)
    peak_index = max(range(len(y)), key=lambda index: y[index])
    if 0 < peak_index < len(y) - 1:
        if y[peak_index] - y[0] > tolerance and y[peak_index] - y[-1] > tolerance:
            return TrendAssessment(
                TrendKind.INTERIOR_PEAK,
                peak_x=float(x[peak_index]),
                has_increase=has_increase,
                has_decrease=has_decrease,
            )
    trough_index = min(range(len(y)), key=lambda index: y[index])
    if 0 < trough_index < len(y) - 1:
        if y[0] - y[trough_index] > tolerance and y[-1] - y[trough_index] > tolerance:
            return TrendAssessment(
                TrendKind.INTERIOR_TROUGH,
                peak_x=float(x[trough_index]),
                has_increase=has_increase,
                has_decrease=has_decrease,
            )
    minimum_tail_points = 3
    for index in range(1, len(y) - minimum_tail_points + 1):
        tail = y[index:]
        tail_span = max(tail) - min(tail)
        if tail_span <= tolerance and abs(y[index] - y[0]) > tolerance:
            return TrendAssessment(
                TrendKind.PLATEAU,
                plateau_start_x=float(x[index]),
                has_increase=has_increase,
                has_decrease=has_decrease,
            )
    if all(value >= -tolerance for value in differences) and y[-1] - y[0] > tolerance:
        return TrendAssessment(
            TrendKind.MONOTONIC_INCREASING,
            has_increase=has_increase,
            has_decrease=has_decrease,
        )
    if all(value <= tolerance for value in differences) and y[0] - y[-1] > tolerance:
        return TrendAssessment(
            TrendKind.MONOTONIC_DECREASING,
            has_increase=has_increase,
            has_decrease=has_decrease,
        )
    if len(y) >= minimum_tail_points and max(y) - min(y) <= tolerance:
        return TrendAssessment(
            TrendKind.PLATEAU,
            plateau_start_x=float(x[0]),
            has_increase=has_increase,
            has_decrease=has_decrease,
        )
    return TrendAssessment(TrendKind.MIXED, has_increase=has_increase, has_decrease=has_decrease)
