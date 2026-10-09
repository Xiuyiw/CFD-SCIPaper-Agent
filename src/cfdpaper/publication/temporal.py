"""Bounded calculations on saved samples, without interpolation or time conversion."""

import math

TEMPORAL_FIELDS = {
    "sample_count",
    "duration",
    "start_value",
    "end_value",
    "change",
    "minimum",
    "maximum",
    "peak_time",
    "time_mean",
    "integral",
    "first_crossing_time",
}
TIME_FIELDS = {"duration", "peak_time", "first_crossing_time"}


def validate_temporal_options(units, time_window, value_kind, threshold, direction):
    if (
        not isinstance(units, dict)
        or set(units) != {"time", "value"}
        or units["time"] != "s"
        or not isinstance(units["value"], str)
    ):
        raise ValueError("Temporal calculation requires time unit s and declared value unit")
    if value_kind not in {"instantaneous", "cumulative"}:
        raise ValueError("temporal_value_kind must be instantaneous or cumulative")
    if direction not in {"at-or-above", "at-or-below"}:
        raise ValueError("Unknown crossing_direction")
    if threshold is not None and (
        type(threshold) not in (int, float) or not math.isfinite(threshold)
    ):
        raise ValueError("Temporal threshold must be finite")
    if time_window is not None and (
        not isinstance(time_window, (list, tuple))
        or len(time_window) != 2
        or any(type(t) not in (int, float) or not math.isfinite(t) for t in time_window)
        or time_window[0] >= time_window[1]
    ):
        raise ValueError("time_window requires two finite, strictly increasing endpoints")


def select_temporal_window(items, time_column, time_window):
    times = [row[time_column] for _, row in items]
    if len(times) < 2:
        raise ValueError("Temporal calculation requires at least two saved samples per group")
    if any(t is None or not math.isfinite(t) for t in times):
        raise ValueError("Temporal time samples must be finite and nonmissing")
    if any(a >= b for a, b in zip(times[:-1], times[1:], strict=True)):
        raise ValueError("Temporal time samples must be strictly increasing in source order")
    if time_window is None:
        return items
    start, end = time_window
    if start < times[0] or end > times[-1]:
        raise ValueError("time_window exceeds saved-sample coverage")
    if start not in times or end not in times:
        raise ValueError("time_window endpoints must be exact saved samples; no interpolation")
    return items[times.index(start) : times.index(end) + 1]


def temporal_summary(times, values, *, value_kind, threshold, direction):
    """Trapezoids use actual sample spacing; cumulative inputs are never integrated."""
    start, end = times[0], times[-1]
    maximum = max(values)
    first = next(
        (
            t
            for t, v in zip(times, values, strict=True)
            if threshold is not None
            and (v >= threshold if direction == "at-or-above" else v <= threshold)
        ),
        None,
    )
    result = {
        "sample_count": len(times),
        "duration": end - start,
        "start_value": values[0],
        "end_value": values[-1],
        "change": values[-1] - values[0],
        "minimum": min(values),
        "maximum": maximum,
        "peak_time": times[values.index(maximum)],
        "time_mean": None,
        "integral": None,
        "first_crossing_time": first,
    }
    try:
        if value_kind == "instantaneous":
            result["integral"] = math.fsum(
                (left / 2 + right / 2) * (b - a)
                for a, b, left, right in zip(
                    times[:-1], times[1:], values[:-1], values[1:], strict=True
                )
            )
            result["time_mean"] = result["integral"] / result["duration"]
    except OverflowError as exc:
        raise ValueError("Temporal calculation produced a nonfinite result") from exc
    if any(v is not None and not math.isfinite(v) for v in result.values()):
        raise ValueError("Temporal calculation produced a nonfinite result")
    return result


def temporal_unit(field, value_unit, quantity_kind):
    if field in TIME_FIELDS:
        return "s"
    if field == "sample_count":
        return ""
    if field == "change" and quantity_kind == "absolute-temperature":
        return "K"
    if field == "integral":
        return {"W": "J", "kW": "kJ", "MW": "MJ", "kg/s": "kg"}.get(
            value_unit, f"{value_unit or '1'}·s"
        )
    return value_unit
