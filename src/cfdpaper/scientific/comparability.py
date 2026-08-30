"""Case comparability checks for controlled CFD comparisons."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .units import convert_value, unit_is_known, units_compatible


@dataclass(frozen=True, slots=True)
class CaseDefinition:
    case_id: str
    conditions: Mapping[str, tuple[float, str | None]]
    models: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        copied_conditions = {
            name: (float(value), unit) for name, (value, unit) in self.conditions.items()
        }
        object.__setattr__(self, "conditions", MappingProxyType(copied_conditions))
        object.__setattr__(self, "models", MappingProxyType(dict(self.models)))


@dataclass(frozen=True, slots=True)
class ComparabilityResult:
    comparable: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...] = ()


def check_case_comparability(
    reference: CaseDefinition,
    candidate: CaseDefinition,
    *,
    required: tuple[str, ...] | None = None,
    relative_tolerance: float = 1e-6,
    absolute_tolerance: float = 1e-12,
) -> ComparabilityResult:
    """Check that controlled operating conditions and declared models match."""

    for name, tolerance in (
        ("relative tolerance", relative_tolerance),
        ("absolute tolerance", absolute_tolerance),
    ):
        if not math.isfinite(tolerance) or tolerance < 0:
            raise ValueError(f"{name} must be finite and non-negative")
    names = required or tuple(sorted(set(reference.conditions) | set(candidate.conditions)))
    blockers: list[str] = []
    for name in names:
        if name not in reference.conditions or name not in candidate.conditions:
            blockers.append(f"missing required condition: {name}")
            continue
        reference_value, reference_unit = reference.conditions[name]
        candidate_value, candidate_unit = candidate.conditions[name]
        if not math.isfinite(reference_value) or not math.isfinite(candidate_value):
            blockers.append(f"condition {name} values must be finite")
            continue
        if reference_unit is None or candidate_unit is None:
            blockers.append(f"missing unit for quantitative condition: {name}")
            continue
        if not unit_is_known(reference_unit) or not unit_is_known(candidate_unit):
            blockers.append(
                f"unknown unit for quantitative condition {name}: "
                f"{reference_unit!r} versus {candidate_unit!r}"
            )
            continue
        if not units_compatible(reference_unit, candidate_unit):
            blockers.append(
                f"incompatible units for {name}: {reference_unit!r} versus {candidate_unit!r}"
            )
            continue
        converted = convert_value(candidate_value, candidate_unit, reference_unit)
        if not math.isfinite(converted):
            blockers.append(f"converted condition {name} must be finite")
            continue
        if not math.isclose(
            reference_value,
            converted,
            rel_tol=relative_tolerance,
            abs_tol=absolute_tolerance,
        ):
            blockers.append(
                f"operating condition {name} differs: {reference_value:g} {reference_unit or ''} "
                f"versus {converted:g} {reference_unit or ''}"
            )
    for model_name in sorted(set(reference.models) | set(candidate.models)):
        if reference.models.get(model_name) != candidate.models.get(model_name):
            blockers.append(f"model setting differs: {model_name}")
    return ComparabilityResult(not blockers, tuple(blockers))
