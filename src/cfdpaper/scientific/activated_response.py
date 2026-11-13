"""Area means of a prescribed, dimensionless thermal activation response."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation
from numbers import Integral, Real
from typing import TypedDict


class ActivatedResponseMean(TypedDict):
    group: str
    count: int
    area_m2: float
    mean: float


def _number(value: object, label: str, *, allow_zero: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal, str)):
        raise ValueError(f"{label} must be numeric")
    try:
        number = float(value)
        if number == 0 and (Decimal(value) if isinstance(value, str) else value) != 0:
            raise ValueError("nonzero input below numeric range")
    except (OverflowError, ValueError, InvalidOperation) as error:
        raise ValueError(f"{label} must be a finite representable number") from error
    if not math.isfinite(number) or number < 0 or (number == 0 and not allow_zero):
        constraint = "nonnegative" if allow_zero else "positive"
        raise ValueError(f"{label} must be finite and {constraint}")
    return number


def _identifier(value: object, label: str) -> str:
    if isinstance(value, (str, Integral)) and not isinstance(value, bool):
        if result := str(value).strip():
            return result
    raise ValueError(f"{label} must be a nonempty string or integer identifier")


def _unit(value: str) -> str:
    return value.strip().replace("³", "3").replace("^3", "3") if isinstance(value, str) else ""


def _response(
    c: float, t: float, a: float, ref: float, p: float, theta: float, q: float, label: str
) -> float:
    if a == 0 or c == 0:
        return 0.0
    # Combine powers before exponentiating: exp(-theta/T) can underflow even
    # when the requested final response is representable.
    try:
        ratio = c / ref
        log_ratio = math.log(ratio) if 0 < ratio < math.inf else math.log(c) - math.log(ref)
        log_response = q * math.fsum((math.log(a), p * log_ratio, -theta / t))
        response = math.exp(log_response)
    except (ValueError, OverflowError) as error:
        raise ValueError(f"{label}: response outside numeric range") from error
    if not math.isfinite(response) or response == 0:
        raise ValueError(f"{label}: positive response outside numeric range")
    return response


def _weighted_term(value: float, weight: float, total: float) -> float:
    # Form value * weight / total without overflowing the product or prematurely
    # underflowing the area fraction when the member areas span many decades.
    v, ve = math.frexp(value)
    w, we = math.frexp(weight)
    s, se = math.frexp(total)
    return math.ldexp(v * w / s, ve + we - se)


def activated_response_mean(
    rows: Iterable[Mapping[str, object]],
    *,
    group: str,
    member: str,
    concentration: str,
    temperature: str,
    area: str,
    prefactor: float,
    concentration_ref: float,
    concentration_power: float,
    activation_K: float,
    output_power: float,
    concentration_unit: str,
    reference_unit: str,
    temperature_unit: str,
    area_unit: str,
    concentration_basis: str | None = None,
    reference_basis: str | None = None,
) -> list[ActivatedResponseMean]:
    """Evaluate [a (c/ref)^p exp(-theta/T)]^q per member, then area-average.

    Input columns identify aligned members; areas > 0 are the selected member
    areas in square metres, not sample counts. Both exponents are positive,
    a is dimensionless and nonnegative, and theta >= 0 and T > 0 are in kelvin.
    A true zero concentration or prefactor gives a zero response, not a missing
    member. Bad data or a nonrepresentable positive member response raises.

    Concentration and positive reference must use the same concentration unit
    and physical basis. No conversions are inferred. Supply both basis labels
    to check their declared agreement; omission does not verify a common basis.
    Returns group, count, area_m2 and dimensionless mean in first-seen group order.
    """
    columns = (group, member, concentration, temperature, area)
    if not all(isinstance(key, str) and key.strip() for key in columns) or len(set(columns)) != 5:
        raise ValueError("group, member, concentration, temperature and area need distinct columns")
    unit = _unit(concentration_unit)
    if unit != _unit(reference_unit) or unit not in (
        "1",
        "%",
        "ppm",
        "ppmv",
        "ppmw",
        "mol/mol",
        "kg/kg",
        "mol/m3",
        "kmol/m3",
        "kg/m3",
        "g/m3",
    ):
        raise ValueError(
            "concentration and reference require the same supported concentration unit"
        )
    if temperature_unit != "K" or area_unit not in ("m2", "m^2", "m²"):
        raise ValueError("temperature must be in K and area in m2")
    if concentration_basis is not None or reference_basis is not None:
        if (
            not isinstance(concentration_basis, str)
            or not isinstance(reference_basis, str)
            or not concentration_basis.strip()
            or concentration_basis.strip() != reference_basis.strip()
        ):
            raise ValueError("concentration and reference need matching nonempty basis labels")
    a = _number(prefactor, "prefactor", allow_zero=True)
    ref = _number(concentration_ref, "concentration_ref")
    p = _number(concentration_power, "concentration_power")
    theta = _number(activation_K, "activation_K", allow_zero=True)
    q = _number(output_power, "output_power")

    groups: dict[str, dict[str, tuple[float, float]]] = {}
    for index, row in enumerate(rows, 1):
        label = f"row {index}"
        if not isinstance(row, Mapping):
            raise ValueError(f"{label} must be a mapping")
        for key in columns:
            if key not in row:
                raise ValueError(f"{label}: missing column {key!r}")
        name = _identifier(row[group], f"{label} group")
        key = _identifier(row[member], f"{label} member")
        members = groups.setdefault(name, {})
        if key in members:
            raise ValueError(f"{label}: duplicate member {key!r} in group {name!r}")
        c = _number(row[concentration], f"{label} concentration", allow_zero=True)
        t = _number(row[temperature], f"{label} temperature")
        weight = _number(row[area], f"{label} area")
        members[key] = weight, _response(c, t, a, ref, p, theta, q, label)
    if not groups:
        raise ValueError("at least one row is required")

    results: list[ActivatedResponseMean] = []
    for name, members in groups.items():
        try:
            total = math.fsum(weight for weight, _ in members.values())
        except OverflowError as error:
            raise ValueError(f"group {name!r}: total area outside numeric range") from error
        try:
            mean = math.fsum(_weighted_term(v, w, total) for w, v in members.values())
        except OverflowError as error:
            raise ValueError(f"group {name!r}: mean outside numeric range") from error
        if mean == 0 and any(v > 0 for _, v in members.values()):
            raise ValueError(f"group {name!r}: positive mean outside numeric range")
        results.append({"group": name, "count": len(members), "area_m2": total, "mean": mean})
    return results
