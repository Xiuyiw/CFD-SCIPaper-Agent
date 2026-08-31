"""Small offline unit-compatibility layer for common CFD quantities."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class _Unit:
    dimension: str
    scale: float = 1.0
    offset: float = 0.0


_UNITS = {
    "1": _Unit("dimensionless"),
    "-": _Unit("dimensionless"),
    "%": _Unit("dimensionless", 0.01),
    "ppm": _Unit("dimensionless", 1e-6),
    "pa": _Unit("pressure"),
    "kpa": _Unit("pressure", 1e3),
    "mpa": _Unit("pressure", 1e6),
    "bar": _Unit("pressure", 1e5),
    "k": _Unit("temperature"),
    "degc": _Unit("temperature", 1.0, 273.15),
    "°c": _Unit("temperature", 1.0, 273.15),
    "m": _Unit("length"),
    "mm": _Unit("length", 1e-3),
    "cm": _Unit("length", 1e-2),
    "s": _Unit("time"),
    "m/s": _Unit("velocity"),
    "kg/s": _Unit("mass-flow"),
    "w": _Unit("power"),
    "kw": _Unit("power", 1e3),
    "mw": _Unit("power", 1e6),
    "j": _Unit("energy"),
    "kj": _Unit("energy", 1e3),
    "w/m2": _Unit("heat-flux"),
    "w/m^2": _Unit("heat-flux"),
    "w/m3": _Unit("volumetric-power"),
    "w/m^3": _Unit("volumetric-power"),
    "kg/m3": _Unit("density"),
    "kg/m^3": _Unit("density"),
}

_CANONICAL_ALIASES = {
    "-": "1",
    "°c": "degc",
    "w/m^2": "w/m2",
    "w/m^3": "w/m3",
    "kg/m^3": "kg/m3",
}


def _normalize(unit: str) -> str:
    return (
        unit.strip().lower().replace(" ", "").replace("·", "").replace("²", "2").replace("³", "3")
    )


def canonical_unit(unit: str | None) -> str:
    """Return the registered canonical spelling of a unit."""

    if unit is None:
        raise ValueError("unit is required")
    normalized = _normalize(unit)
    if normalized not in _UNITS:
        raise ValueError(f"unknown unit: {unit!r}")
    return _CANONICAL_ALIASES.get(normalized, normalized)


def units_compatible(first: str | None, second: str | None) -> bool:
    """Return whether two units are dimensionally compatible.

    Missing and unknown units are never considered safe for quantitative comparison.
    """

    if first is None or second is None:
        return False
    left = _normalize(first)
    right = _normalize(second)
    left_unit = _UNITS.get(left)
    right_unit = _UNITS.get(right)
    return bool(left_unit and right_unit and left_unit.dimension == right_unit.dimension)


def unit_is_known(unit: str | None) -> bool:
    """Return whether a non-missing unit is registered with a physical dimension."""

    return unit is not None and _normalize(unit) in _UNITS


def convert_value(value: float, from_unit: str, to_unit: str) -> float:
    """Convert a scalar between registered compatible units."""

    normalized_source = _normalize(from_unit)
    normalized_target = _normalize(to_unit)
    source = _UNITS.get(normalized_source)
    target = _UNITS.get(normalized_target)
    if source is None or target is None or source.dimension != target.dimension:
        raise ValueError(f"incompatible or unsupported units: {from_unit!r} and {to_unit!r}")
    if normalized_source == normalized_target:
        return value
    base_value = value * source.scale + source.offset
    return (base_value - target.offset) / target.scale
