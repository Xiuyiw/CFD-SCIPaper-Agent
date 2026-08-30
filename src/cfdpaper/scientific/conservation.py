"""Conservation-closure checks."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConservationAssessment:
    signed_imbalance: float
    relative_imbalance: float | None
    tolerance: float
    passes: bool
    reason: str


def assess_conservation(
    inflow: float,
    outflow: float,
    *,
    tolerance: float = 0.01,
    zero_floor: float = 1e-15,
) -> ConservationAssessment:
    """Assess closure for positive input/output magnitudes."""

    if not math.isfinite(inflow) or not math.isfinite(outflow):
        raise ValueError("inflow and outflow must be finite")
    if inflow < 0 or outflow < 0:
        raise ValueError("inflow and outflow must be non-negative magnitudes")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and non-negative")
    if not math.isfinite(zero_floor) or zero_floor <= 0:
        raise ValueError("zero_floor must be finite and positive")
    signed = inflow - outflow
    scale = max(abs(inflow), abs(outflow))
    if scale <= zero_floor:
        return ConservationAssessment(
            signed, None, tolerance, False, "relative closure is undefined at zero throughput"
        )
    relative = abs(signed) / scale
    return ConservationAssessment(
        signed,
        relative,
        tolerance,
        relative <= tolerance,
        "closure criterion met" if relative <= tolerance else "closure criterion not met",
    )
