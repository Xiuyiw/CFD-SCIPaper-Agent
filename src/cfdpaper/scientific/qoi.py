"""Checks for reproducible quantity-of-interest definitions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QoIDefinition:
    name: str
    unit: str | None
    formula: str | None = None
    spatial_scope: str | None = None
    reduction: str | None = None
    temporal_scope: str | None = "steady-state"


@dataclass(frozen=True, slots=True)
class QoICheck:
    valid: bool
    missing: tuple[str, ...]


def check_qoi_definition(definition: QoIDefinition) -> QoICheck:
    """Require the minimum fields needed to reproduce a reported QoI."""

    required = ("name", "unit", "formula", "spatial_scope", "reduction", "temporal_scope")
    missing = tuple(
        field
        for field in required
        if getattr(definition, field) is None or not str(getattr(definition, field)).strip()
    )
    return QoICheck(not missing, missing)
