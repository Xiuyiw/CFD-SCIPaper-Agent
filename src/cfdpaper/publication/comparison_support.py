"""Compare the declared physical supports used by an actual result comparison."""

from __future__ import annotations

import copy
import math


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def compare_observation_support(
    reference, comparison, *, purpose="same-state", fixed_conditions=()
):
    """Return located conflicts or missing definitions, without inferring conditions.

    Different cases/design variables are allowed. Only named fixed conditions and
    the spatial/operator/time support needed by the requested use are compared.
    Compatibility means compatible declarations, not physical model validation.
    """
    if purpose not in {"same-state", "event-relative", "event-timing"}:
        raise ValueError("Unknown comparison purpose")
    if isinstance(fixed_conditions, str) or any(
        not isinstance(key, str) or not key.strip() for key in fixed_conditions
    ):
        raise ValueError("fixed_conditions must contain named physical conditions")
    missing, conflicts = [], []
    left = reference if isinstance(reference, dict) else {}
    right = comparison if isinstance(comparison, dict) else {}

    def match(key, first, second):
        if first is None or second is None or first == "" or second == "":
            missing.append(key)
        elif first != second:
            conflicts.append(key)

    for role, support in (("reference", left), ("comparison", right)):
        if not isinstance(support.get("case_id"), str) or not support["case_id"].strip():
            missing.append(f"{role}.case_id")
    for key in ("association", "spatial_domain", "operator"):
        match(key, left.get(key), right.get(key))
    for key in fixed_conditions:
        first = left.get("conditions", {}).get(key)
        second = right.get("conditions", {}).get(key)
        if not isinstance(first, dict) or not isinstance(second, dict):
            missing.append(f"condition.{key}")
            continue
        if "value" not in first or "value" not in second:
            missing.append(f"condition.{key}.value")
        elif first["value"] != second["value"]:
            conflicts.append(f"condition.{key}.value")
        if "unit" not in first or "unit" not in second:
            missing.append(f"condition.{key}.unit")
        elif first["unit"] != second["unit"]:
            conflicts.append(f"condition.{key}.unit")

    first = left.get("time") if isinstance(left.get("time"), dict) else {}
    second = right.get("time") if isinstance(right.get("time"), dict) else {}
    kinds = first.get("kind"), second.get("kind")
    if purpose == "event-relative":
        if kinds != ("own-event", "own-event"):
            conflicts.append("time.kind: event-relative use requires own-event observations")
        match("time.event", first.get("event"), second.get("event"))
        match("time.origin", first.get("origin"), second.get("origin"))
        if not all(_number(time.get("offset_s")) for time in (first, second)):
            missing.append("time.offset_s")
        elif first["offset_s"] != second["offset_s"]:
            conflicts.append("time.offset_s")
        if not all(_number(time.get("time_s")) for time in (first, second)):
            missing.append("time.time_s")
    elif purpose == "event-timing":
        allowed = {"native-event", "sampled-event"}
        if any(kind not in allowed for kind in kinds) or kinds[0] != kinds[1]:
            conflicts.append("time.kind: native and saved-sample events differ")
        match("time.event", first.get("event"), second.get("event"))
        match("time.origin", first.get("origin"), second.get("origin"))
    elif kinds == ("steady", "steady"):
        pass
    elif "window" in kinds:
        if kinds != ("window", "window"):
            conflicts.append("time.kind")
        match("time.origin", first.get("origin"), second.get("origin"))
        for time in (first, second):
            window = time.get("window_s")
            if (
                not isinstance(window, (list, tuple))
                or len(window) != 2
                or not all(_number(value) for value in window)
                or window[0] >= window[1]
            ):
                missing.append("time.window_s")
        if "time.window_s" not in missing and list(first["window_s"]) != list(second["window_s"]):
            conflicts.append("time.window_s")
    elif all(kind in {"fixed", "own-event"} for kind in kinds):
        match("time.origin", first.get("origin"), second.get("origin"))
        if not all(_number(time.get("time_s")) for time in (first, second)):
            missing.append("time.time_s")
        elif first["time_s"] != second["time_s"]:
            conflicts.append("time.time_s: different physical observation times")
    elif None in kinds or "unknown" in kinds:
        missing.append("time.kind")
    else:
        conflicts.append("time.kind: no common state or window")
    return {
        "status": "not-comparable" if conflicts else "unknown" if missing else "compatible",
        "purpose": purpose,
        "fixed_conditions": list(fixed_conditions),
        "conflicts": list(dict.fromkeys(conflicts)),
        "missing": list(dict.fromkeys(missing)),
        "reference": copy.deepcopy(left),
        "comparison": copy.deepcopy(right),
    }
