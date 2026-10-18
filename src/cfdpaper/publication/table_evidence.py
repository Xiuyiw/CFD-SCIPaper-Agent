"""Small, explicit calculations on exported tables; no solver or physics inference."""

import csv
import math
import re
import statistics
from bisect import bisect_left, bisect_right
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from cfdpaper.publication.temporal import (
    TEMPORAL_FIELDS,
    TIME_FIELDS,
    select_temporal_window,
    temporal_differences,
    temporal_summary,
    temporal_unit,
    validate_temporal_difference_options,
    validate_temporal_options,
)

REFERENCE_RANGE_FIELDS = {
    "value",
    "reference_value",
    "reference_lower",
    "reference_upper",
    "difference",
    "outside_distance",
}
REFERENCE_KINDS = {"reported-range", "figure-reading-envelope", "declared-bound"}
_TABLE_DECLARATION_KEYS = {
    "operation",
    "columns",
    "group_by",
    "pair_by",
    "reference",
    "comparison",
    "units",
    "quantity_kind",
    "temperature_reference",
    "weight_kind",
    "region_fraction",
    "region_complement",
    "row_filters",
    "unit_column",
    "time_window",
    "temporal_value_kind",
    "threshold",
    "crossing_direction",
    "exceedance_relation",
    "reference_kind",
}


def calculate_declared_table(path, declaration: dict) -> dict:
    """Forward calculation options only, without adding report identity or metadata."""
    if declaration["operation"] in {"field_integral", "field_difference", "energy_budget"}:
        from .field_diagnostics import calculate_field_diagnostic

        result = calculate_field_diagnostic(path, declaration)
    else:
        result = calculate_table(
            path,
            **{key: value for key, value in declaration.items() if key in _TABLE_DECLARATION_KEYS},
        )
    if declaration.get("support") is not None:
        result["support"] = declaration["support"]
    return result


def display_unit(unit: str) -> str:
    """Typeset supported unit labels without converting their numerical scale."""
    scaled = re.fullmatch(r"10\^([+-]?\d+)\s+(.+)", unit)
    if scaled:
        suffix = scaled[2]
        shown = display_unit(suffix)
        # Only labels already supported below, or these explicit SI atoms.
        # Unknown source descriptions must not become a guessed unit grammar.
        if shown != suffix or suffix in {"W", "kW", "MW", "J", "kJ", "Pa", "kPa", "K"}:
            power = scaled[1].translate(str.maketrans("+-0123456789", "⁺⁻⁰¹²³⁴⁵⁶⁷⁸⁹"))
            return f"× 10{power} {shown}"
    molar_rate = re.fullmatch(r"(kgmol|kmol|mol)/s", unit)
    if molar_rate:
        return f"{molar_rate[1]}·s⁻¹"
    if unit == "degC":
        return "°C"
    area = re.fullmatch(r"(m|cm|mm)(?:\^?2|²)", unit)
    if area:
        return f"{area[1]}²"
    volume = re.fullmatch(r"(m|cm|mm)(?:\^?3|³)", unit)
    if volume:
        return f"{volume[1]}³"
    heat_flux = re.fullmatch(r"(W|kW|MW)/(m|cm|mm)(?:\^?2|²)", unit)
    if heat_flux:
        return f"{heat_flux[1]} {heat_flux[2]}⁻²"
    match = re.fullmatch(r"\(([^()]+)\)/\((m|cm|mm)(?:\^?2|²)\)", unit)
    if match:
        return f"{match[1]} {match[2]}⁻²"
    return unit


def calculate_table(
    path,
    *,
    operation,
    columns,
    group_by=None,
    pair_by=None,
    reference=None,
    comparison=None,
    units=None,
    quantity_kind="ordinary",
    temperature_reference=None,
    weight_kind=None,
    region_fraction=None,
    region_complement=False,
    row_filters: dict[str, str] | None = None,
    unit_column: str | None = None,
    time_window: list[float] | tuple[float, float] | None = None,
    temporal_value_kind="instantaneous",
    threshold: float | None = None,
    crossing_direction="at-or-above",
    exceedance_relation="above",
    reference_kind: str | None = None,
):
    """Calculate over explicitly selected records, retaining original source locations.

    Units and physical domains are declared by the caller, never inferred here.
    Filters are exact string equalities applied before numeric conversion. A unit
    column checks the declared value unit; no unit conversion is performed.
    """
    scalar_ops = {"population", "scalar_select", "paired_change"}
    range_ops = {"reference_range", "paired_reference_change"}
    paired_ops = {"paired_change", "paired_reference_change"}
    temporal_ops = {"temporal", "temporal_difference"}
    weighted_ops = {"weighted_population", "weighted_exceedance"}
    range_roles = {"value", "reference", "lower", "upper"}
    if operation in range_ops:
        if set(columns) not in (range_roles, {"value", "reference", "half_width"}):
            raise ValueError("Reference range requires value,reference,lower,upper or half_width")
        if not isinstance(reference_kind, str) or reference_kind not in REFERENCE_KINDS:
            raise ValueError("Reference range requires a declared reference_kind")
        if (
            not isinstance(units, dict)
            or set(units) != set(columns)
            or any(not isinstance(unit, str) for unit in units.values())
            or len(set(units.values())) != 1
        ):
            raise ValueError("Reference range requires identical declared units for every role")
    elif reference_kind is not None:
        raise ValueError(
            "reference_kind requires operation reference_range or paired_reference_change"
        )
    required = (
        set(columns)
        if operation in range_ops
        else {"time", "reference", "comparison"}
        if operation == "temporal_difference"
        else {"time", "value"}
        if operation == "temporal"
        else {"value", "weight"}
        if operation in weighted_ops
        else {"value"}
        if operation in scalar_ops
        else {"area", "rate"}
    )
    if (
        operation not in scalar_ops | range_ops | temporal_ops | weighted_ops | {"partition"}
        or set(columns) != required
    ):
        raise ValueError(
            "Use scalar/value, weighted_population or weighted_exceedance/value,weight, "
            "partition/area,rate "
            "or temporal/time,value or reference_range/paired_reference_change/"
            "value,reference,bounds or temporal_difference/time,reference,comparison"
        )
    if operation == "temporal_difference":
        validate_temporal_difference_options(
            units, time_window, temporal_value_kind, threshold, crossing_direction
        )
        if any(
            option is not None
            for option in (pair_by, reference, comparison, temperature_reference, weight_kind)
        ):
            raise ValueError(
                "Temporal difference does not accept paired-member, temperature_reference "
                "or weight_kind options"
            )
    elif operation == "temporal":
        validate_temporal_options(
            units, time_window, temporal_value_kind, threshold, crossing_direction
        )
    elif (
        time_window is not None
        or temporal_value_kind != "instantaneous"
        or (threshold is not None and operation != "weighted_exceedance")
        or crossing_direction != "at-or-above"
    ):
        raise ValueError("Temporal options require operation temporal or temporal_difference")
    if operation == "weighted_exceedance":
        if type(threshold) not in (int, float) or not math.isfinite(threshold):
            raise ValueError("Weighted exceedance requires a finite threshold in the value unit")
        if exceedance_relation not in {"above", "at-or-above"}:
            raise ValueError("exceedance_relation must be above or at-or-above")
        if any(
            option is not None for option in (pair_by, reference, comparison, temperature_reference)
        ):
            raise ValueError(
                "Weighted exceedance does not accept paired-member or temperature_reference options"
            )
    elif exceedance_relation != "above":
        raise ValueError("exceedance_relation requires operation weighted_exceedance")
    if operation in weighted_ops:
        if weight_kind not in {"area", "volume"}:
            raise ValueError("Weighted calculation requires weight_kind area or volume")
        if not isinstance(units, dict) or set(units) != {"value", "weight"}:
            raise ValueError("Weighted calculation requires declared value and weight units")
        measure = units["weight"]
        power = r"(?:\^?2|²)" if weight_kind == "area" else r"(?:\^?3|³)"
        if not isinstance(measure, str) or not re.fullmatch(r"(?:m|cm|mm)" + power, measure):
            raise ValueError("Weight unit must match the declared area or volume measure")
    if operation in paired_ops:
        if not all(isinstance(x, str) and x.strip() for x in (pair_by, reference, comparison)):
            raise ValueError("Paired change requires pair_by, reference and comparison")
        if reference == comparison:
            raise ValueError("Reference and comparison must differ")
    if operation in paired_ops | range_ops | temporal_ops | weighted_ops or (
        operation == "scalar_select" and quantity_kind != "ordinary"
    ):
        unit = (units or {}).get("reference" if operation == "temporal_difference" else "value")
        if not isinstance(unit, str):
            raise ValueError("Calculation requires a declared value unit")
        if quantity_kind not in {"ordinary", "absolute-temperature", "temperature-difference"}:
            raise ValueError("Unknown quantity_kind")
        if unit in {"degC", "°C", "C"} and quantity_kind != "absolute-temperature":
            raise ValueError("Celsius values require absolute-temperature semantics")
        if unit == "K" and quantity_kind == "ordinary":
            raise ValueError("Declare whether K is absolute-temperature or temperature-difference")
        if quantity_kind == "absolute-temperature" and unit not in {"degC", "°C", "C", "K"}:
            raise ValueError("Absolute temperature requires Celsius or Kelvin units")
        if (
            operation in range_ops | temporal_ops | weighted_ops | {"scalar_select"}
            and quantity_kind == "temperature-difference"
            and unit != "K"
        ):
            raise ValueError("Temperature difference requires Kelvin units")
        if temperature_reference is not None and (
            quantity_kind != "absolute-temperature"
            or type(temperature_reference) not in (float, int)
            or not math.isfinite(temperature_reference)
        ):
            raise ValueError("temperature_reference requires a finite absolute-temperature origin")
    if len(set(columns.values())) != len(columns):
        raise ValueError("Calculation roles require distinct columns")
    if region_fraction is not None:
        if (
            operation != "weighted_population"
            or not isinstance(region_fraction, str)
            or not region_fraction.strip()
        ):
            raise ValueError("A region fraction column is only supported for weighted_population")
        if region_fraction in columns.values():
            raise ValueError("Region fraction must be distinct from value and weight")
    elif region_complement:
        raise ValueError("Region complement requires a region fraction column")
    if row_filters is not None and (
        not isinstance(row_filters, dict)
        or any(
            not isinstance(key, str) or not key.strip() or not isinstance(value, str)
            for key, value in row_filters.items()
        )
    ):
        raise ValueError("row_filters must map nonempty column names to exact strings")
    if unit_column is not None and (
        not isinstance(unit_column, str)
        or not unit_column.strip()
        or "value" not in columns
        or not isinstance((units or {}).get("value"), str)
    ):
        raise ValueError("unit_column requires a column name and declared value unit")
    numeric_columns = list(columns.values()) + ([region_fraction] if region_fraction else [])
    raw_rows = read_source_records(
        path,
        [
            *numeric_columns,
            *[key for key in (group_by, pair_by, unit_column) if key],
            *(row_filters or {}),
        ],
    )
    rows = [
        (index, row)
        for index, row in enumerate(raw_rows, 2)
        if all(row[key] == value for key, value in (row_filters or {}).items())
    ]
    if not rows:
        if row_filters:
            raise ValueError(f"No records match row_filters {row_filters!r} in {path}")
        raise ValueError("Calculation table is empty")
    groups = {}
    for index, row in rows:
        if unit_column is not None and row[unit_column] != units["value"]:
            raise ValueError(
                f"Unit mismatch at {path}:{index}:{unit_column}: "
                f"expected {units['value']!r}, found {row[unit_column]!r}"
            )
        _convert_numeric_row(path, index, row, numeric_columns)
        if group_by and (group_by not in row or not str(row[group_by] or "").strip()):
            raise ValueError(f"Missing group at {path}:{index}")
        group = str(row[group_by]) if group_by else "all"
        groups.setdefault(group, []).append((index, row))
    results = []
    for name, items in groups.items():
        temporal_metadata = {}
        member_metadata = {}
        threshold_metadata = (
            {"threshold": threshold, "exceedance_relation": exceedance_relation}
            if operation == "weighted_exceedance"
            else {}
        )
        if operation in temporal_ops:
            items = select_temporal_window(items, columns["time"], time_window)
            temporal_metadata = {
                "time_window": [items[0][1][columns["time"]], items[-1][1][columns["time"]]],
                "temporal_value_kind": temporal_value_kind,
                "sampling": "saved-samples",
                "integration_method": "trapezoidal-nonuniform"
                if temporal_value_kind == "instantaneous"
                else None,
                "threshold": threshold,
                "crossing_direction": crossing_direction,
                "window_selection": "exact-sampled-endpoints"
                if time_window is not None
                else "full-saved-coverage",
            }
        if operation in {"scalar_select", "reference_range"} and len(items) != 1:
            selection = "Scalar selection" if operation == "scalar_select" else "Reference range"
            raise ValueError(
                f"{selection} requires exactly one record in group {name!r}; "
                f"found {len(items)} at {path}, source records {[n for n, _ in items]}"
            )
        if operation in paired_ops:
            chosen = []
            for member in (reference, comparison):
                matches = [(n, r) for n, r in items if r.get(pair_by) == member]
                if len(matches) != 1:
                    raise ValueError(
                        f"Group {name!r}: expected one record for {member!r}; "
                        f"found {len(matches)} at {path}, "
                        f"source records {[n for n, _ in matches]}"
                    )
                chosen.extend(matches)
            items = chosen
            if operation == "paired_reference_change":
                array_source = Path(path).suffix.lower() == ".npz"
                member_metadata = {
                    "members": {
                        role: {
                            "member": member,
                            ("array_index" if array_source else "csv_record"): n - 2
                            if array_source
                            else n,
                            "values": {key: row[column] for key, column in columns.items()},
                        }
                        for role, member, (n, row) in zip(
                            ("reference", "comparison"),
                            (reference, comparison),
                            items,
                            strict=True,
                        )
                    }
                }
        values = {key: [r[column] for _, r in items] for key, column in columns.items()}
        if operation == "temporal_difference":
            difference_values = temporal_differences(values["reference"], values["comparison"])
            array_source = Path(path).suffix.lower() == ".npz"
            temporal_metadata.update(
                difference_direction="comparison-reference",
                difference_unit="K" if quantity_kind != "ordinary" else units["reference"],
                difference_quantity_kind="temperature-difference"
                if quantity_kind != "ordinary"
                else "ordinary",
                crossing_time_kind="first-matching-saved-sample",
                samples=[
                    {
                        ("array_index" if array_source else "csv_record"): n - 2
                        if array_source
                        else n,
                        "time": row[columns["time"]],
                        "reference": row[columns["reference"]],
                        "comparison": row[columns["comparison"]],
                        "value": value,
                    }
                    for (n, row), value in zip(items, difference_values, strict=True)
                ],
            )
        if operation in weighted_ops and any(
            w is None or not math.isfinite(w) or w <= 0 for w in values["weight"]
        ):
            raise ValueError(f"Group {name!r}: weights must be finite and strictly positive")
        if operation == "reference_range":
            result = _reference_range_result(
                **{key: sequence[0] for key, sequence in values.items()}
            )
            status = "missing-values" if result is None else "computed"
        elif operation == "paired_reference_change":
            result = _paired_reference_change_result(values)
            status = "missing-values" if result is None else "computed"
        elif any(v is None for sequence in values.values() for v in sequence):
            result, status = None, "missing-values"
        elif operation in temporal_ops:
            result = temporal_summary(
                values["time"],
                difference_values if operation == "temporal_difference" else values["value"],
                value_kind=temporal_value_kind,
                threshold=threshold,
                direction=crossing_direction,
            )
            status = "computed"
        elif operation == "population":
            result, status = population_summary(values["value"]), "computed"
        elif operation == "weighted_exceedance":
            result = _weighted_exceedance_summary(
                values["value"], values["weight"], threshold, exceedance_relation
            )
            status = "computed"
        elif operation == "weighted_population":
            weights = values["weight"]
            if region_fraction:
                fractions = [r[region_fraction] for _, r in items]
                if any(f is None or not math.isfinite(f) or not 0 <= f <= 1 for f in fractions):
                    raise ValueError("Region fractions must be finite values in [0, 1]")
                weights = [
                    w * (1 - f if region_complement else f)
                    for w, f in zip(weights, fractions, strict=True)
                ]
            selected_values = [
                (v, w) for v, w in zip(values["value"], weights, strict=True) if w > 0
            ]
            if not selected_values:
                raise ValueError(f"Group {name!r}: selected region has zero measure")
            result = _weighted_population_summary(*zip(*selected_values, strict=True))
            status = "computed"
        elif operation == "scalar_select":
            result, status = {"value": values["value"][0]}, "computed"
        elif operation == "paired_change":
            baseline, compared = values["value"]
            result = _paired_result(baseline, compared, quantity_kind, temperature_reference)
            status = "computed"
        else:
            result = partition_summary(values["area"], values["rate"])
            # Temperature consistency is a separate calculation requiring more inputs.
            result.pop("temperature_status")
            result.pop("conditional_temperature")
            status = "computed"
        results.append(
            {
                "group": name,
                ("array_indices" if Path(path).suffix.lower() == ".npz" else "csv_records"): [
                    n - 2 if Path(path).suffix.lower() == ".npz" else n for n, _ in items
                ],
                "status": status,
                "result": result,
                **temporal_metadata,
                **member_metadata,
                **threshold_metadata,
            }
        )
    return {
        "rows_read": len(rows),
        "groups": results,
        **({"reference_kind": reference_kind} if operation in range_ops else {}),
    }


def _reference_range_result(value, reference, *, lower=None, upper=None, half_width=None):
    """Compare one observation to declared bounds, without a statistical/model verdict."""
    if half_width is not None:
        if half_width < 0:
            raise ValueError("Reference range half_width must be nonnegative")
        if reference is not None:
            lower, upper = reference - half_width, reference + half_width
    if lower is not None and upper is not None and lower > upper:
        raise ValueError("Reference range lower bound exceeds upper bound")
    if reference is not None and (
        (lower is not None and reference < lower) or (upper is not None and reference > upper)
    ):
        raise ValueError("Reference value must lie within its declared bounds")
    if any(number is None for number in (value, reference, lower, upper)):
        return None
    relation = "below" if value < lower else "above" if value > upper else "inside"
    result = {
        "value": value,
        "reference_value": reference,
        "reference_lower": lower,
        "reference_upper": upper,
        "difference": value - reference,
        "outside_distance": value - lower
        if relation == "below"
        else value - upper
        if relation == "above"
        else 0.0,
    }
    if any(not math.isfinite(number) for number in result.values()):
        raise ValueError("Reference range calculation produced a nonfinite result")
    return {**result, "reference_relation": relation}


def _paired_reference_change_result(values):
    """Subtract matched observations with a conservative, non-statistical endpoint envelope."""
    # Validate both declared ranges, including an invalid side opposite a missing one.
    members = [
        _reference_range_result(**{role: sequence[i] for role, sequence in values.items()})
        for i in range(2)
    ]
    if any(member is None for member in members):
        return None
    baseline, compared = members
    return _reference_range_result(
        compared["value"] - baseline["value"],
        compared["reference_value"] - baseline["reference_value"],
        lower=compared["reference_lower"] - baseline["reference_upper"],
        upper=compared["reference_upper"] - baseline["reference_lower"],
    )


def _paired_result(baseline, compared, quantity_kind, temperature_reference):
    delta = compared - baseline
    denominator = baseline
    if quantity_kind == "absolute-temperature":
        denominator = None if temperature_reference is None else baseline - temperature_reference
    if denominator is not None and not math.isfinite(denominator):
        raise ValueError("Paired calculation produced a nonfinite denominator")
    ratio = delta / denominator if denominator else None
    if not math.isfinite(delta) or (ratio is not None and not math.isfinite(ratio)):
        raise ValueError("Paired calculation produced a nonfinite result")
    return {
        "difference": delta,
        "relative_change": ratio,
        "relative_reduction": -ratio if ratio is not None else None,
    }


_COMPARABLE_FIELDS = {
    "population": {"mean", "sum"},
    "scalar_select": {"value"},
    "weighted_population": {"weighted_mean", "weighted_std", "weight_sum"},
    "partition": {"area", "rate", "mean_flux"},
    "temporal": TEMPORAL_FIELDS,
    "field_integral": {"net", "positive", "negative", "absolute", "measure", "weighted_mean"},
    "field_difference": {"reference_mean", "comparison_mean", "difference_mean"},
    "energy_budget": {"input", "output", "source", "storage", "residual"},
}


def calculate_result_comparison(
    reports,
    *,
    id,
    reference,
    comparison,
    domain,
    definition_source,
    temperature_reference=None,
    support_purpose=None,
    fixed_conditions=(),
) -> dict:
    """Compare two explicitly chosen, definition-compatible computed scalars.

    The caller establishes scientific comparability. This shallow operation checks
    declared definitions, not geometry or physical meaning, and never converts units.
    Both parents retain independent source locations; no combined CSV is invented.
    """
    for label, value in (("id", id), ("domain", domain), ("definition_source", definition_source)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Result comparison requires a nonempty {label}")
    if any(report.get("id") == id for report in reports):
        raise ValueError(f"Result comparison ID {id!r} already exists")
    if reference == comparison:
        raise ValueError("Reference and comparison must differ")
    upstream = {}
    for role, ref in (("reference", reference), ("comparison", comparison)):
        if (
            not isinstance(ref, dict)
            or set(ref) != {"calculation_id", "group", "field"}
            or any(not isinstance(value, str) or not value.strip() for value in ref.values())
        ):
            raise ValueError("Result references require only calculation_id, group and field")
        matches = [report for report in reports if report.get("id") == ref["calculation_id"]]
        if len(matches) != 1:
            raise ValueError(f"{role}: expected one calculation ID, found {len(matches)}")
        parent = matches[0]
        operation, field = parent.get("operation"), ref["field"]
        if field not in _COMPARABLE_FIELDS.get(operation, set()):
            raise ValueError(f"{role}: unsupported parent operation or scalar field")
        if parent.get("domain") != domain:
            raise ValueError(f"{role}: parent domain must match the comparison domain")
        resolved = resolve_table_result(reports, **ref)
        kind = parent.get("quantity_kind", "ordinary")
        temporal_metadata = {}
        if operation == "temporal":
            if field == "integral" and kind == "absolute-temperature":
                raise ValueError(
                    "Absolute-temperature integral comparisons depend on temperature origin"
                )
            selected = next(g for g in parent["groups"] if g["group"] == ref["group"])
            temporal_metadata = {
                key: selected.get(key)
                for key in ("time_window", "temporal_value_kind", "threshold", "crossing_direction")
            }
            temporal_metadata.update(
                input_value_unit=parent["units"]["value"], input_quantity_kind=kind
            )
            if field in TIME_FIELDS | {"sample_count", "integral"}:
                kind = "ordinary"
            elif field == "change" and kind == "absolute-temperature":
                kind = "temperature-difference"
        if field in {"weight_sum", "area", "rate", "mean_flux", "measure"}:
            kind = "ordinary"
        elif operation == "field_integral" and field != "weighted_mean":
            if kind == "absolute-temperature":
                raise ValueError(
                    "Absolute-temperature measure-integral comparisons depend on temperature origin"
                )
            kind = "ordinary"
        elif (
            operation == "field_difference"
            and field == "difference_mean"
            and kind == "absolute-temperature"
        ):
            kind = "temperature-difference"
        elif field == "weighted_std" and kind == "absolute-temperature":
            kind = "temperature-difference"
        if kind not in {"ordinary", "absolute-temperature", "temperature-difference"}:
            raise ValueError(f"{role}: unknown quantity_kind")
        unit = resolved["unit"]
        if kind == "absolute-temperature" and unit not in {"degC", "°C", "C", "K"}:
            raise ValueError(f"{role}: absolute temperature requires Celsius or Kelvin units")
        if kind == "temperature-difference" and unit != "K":
            raise ValueError(f"{role}: temperature difference requires Kelvin units")
        if kind == "ordinary" and unit in {"degC", "°C", "C", "K"}:
            raise ValueError(f"{role}: declare temperature quantity_kind")
        upstream[role] = {
            **resolved,
            "operation": operation,
            "domain": parent["domain"],
            "weight_kind": parent.get("weight_kind"),
            "quantity_kind": kind,
            "definition_source": parent.get("definition_source"),
            **({"support": parent["support"]} if parent.get("support") is not None else {}),
            **temporal_metadata,
        }
    baseline, compared = upstream["reference"], upstream["comparison"]
    support_check = None
    if support_purpose is not None or baseline.get("support") or compared.get("support"):
        from .comparison_support import compare_observation_support

        support_check = compare_observation_support(
            baseline.get("support"),
            compared.get("support"),
            purpose=support_purpose or "same-state",
            fixed_conditions=fixed_conditions,
        )
        if support_check["status"] != "compatible":
            issues = support_check["conflicts"] + support_check["missing"]
            raise ValueError(
                "Comparison support " + support_check["status"] + ": " + "; ".join(issues)
            )
    for key in ("operation", "field", "weight_kind", "quantity_kind", "unit"):
        if baseline[key] != compared[key]:
            raise ValueError(f"Result comparison requires matching {key}")
    if baseline["operation"] == "temporal":
        keys = ["time_window", "temporal_value_kind"]
        if baseline["field"] == "first_crossing_time":
            keys.extend(
                ("threshold", "crossing_direction", "input_value_unit", "input_quantity_kind")
            )
        for key in keys:
            if baseline[key] != compared[key] or baseline[key] is None:
                raise ValueError(f"Temporal result comparison requires matching {key}")
    kind = baseline["quantity_kind"]
    if temperature_reference is not None and (
        kind != "absolute-temperature"
        or type(temperature_reference) not in (int, float)
        or not math.isfinite(temperature_reference)
    ):
        raise ValueError("temperature_reference requires a finite absolute-temperature origin")
    result = _paired_result(
        baseline["raw_value"], compared["raw_value"], kind, temperature_reference
    )
    return {
        "operation": "result_comparison",
        "id": id,
        "domain": domain,
        "definition_source": definition_source,
        "units": {"value": "K" if kind == "absolute-temperature" else baseline["unit"]},
        "quantity_kind": "temperature-difference" if kind == "absolute-temperature" else kind,
        "temperature_reference": temperature_reference,
        "parents": {"reference": dict(reference), "comparison": dict(comparison)},
        "upstream": upstream,
        **({"comparison_support": support_check} if support_check is not None else {}),
        "groups": [{"group": "all", "status": "computed", "result": result}],
    }


def read_source_records(path: Path, requested: list[str]) -> list[dict]:
    """Read CSV records or explicitly selected, aligned one-dimensional NPZ arrays.

    NPZ units and meanings are supplied by the caller. __index__ is the zero-based
    element index; unrelated geometry arrays are neither flattened nor loaded.
    """
    path = Path(path)
    if path.suffix.lower() == ".npz":
        import numpy as np

        with np.load(path, allow_pickle=False) as archive:
            if "__index__" in archive.files:
                raise ValueError("NPZ __index__ is reserved for element identity")
            keys = set(requested) - {"__index__"}
            if not keys or not keys <= set(archive.files):
                raise ValueError("Missing requested NPZ array keys")
            arrays = {key: archive[key] for key in keys}
            if any(a.ndim != 1 or a.dtype.kind not in "biufUS" for a in arrays.values()):
                raise ValueError(
                    "NPZ calculation arrays must be one-dimensional numeric/text arrays"
                )
            sizes = {len(a) for a in arrays.values()}
            if len(sizes) != 1:
                raise ValueError("NPZ calculation arrays must have identical lengths")
            return [
                {**{key: str(a[i].item()) for key, a in arrays.items()}, "__index__": str(i)}
                for i in range(sizes.pop())
            ]
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(requested) <= set(reader.fieldnames or []):
            raise ValueError(
                "Missing requested numeric columns: missing columns "
                + str(sorted(set(requested) - set(reader.fieldnames or [])))
            )
        rows = list(reader)
        if any(None in row or any(v is None for v in row.values()) for row in rows):
            raise ValueError("CSV row shape does not match headers")
        return rows


def read_numeric_table(path: Path, columns: list[str], *, extra_columns=()) -> list[dict]:
    """Read every row; blank numeric cells remain None, invalid cells raise."""
    rows = read_source_records(path, [*columns, *extra_columns])
    for line, row in enumerate(rows, 2):
        _convert_numeric_row(path, line, row, columns)
    return rows


def _convert_numeric_row(path, line, row, columns):
    for column in columns:
        raw = row[column]
        try:
            value = None if raw is None or not raw.strip() else float(raw)
        except ValueError as exc:
            raise ValueError(f"Invalid numeric value at {path}:{line}:{column}: {raw!r}") from exc
        if value is not None and not math.isfinite(value):
            raise ValueError(f"Nonfinite value at {path}:{line}:{column}")
        row[column] = value


def population_summary(values):
    """Equal-observation population CV; do not drop missing observations."""
    values = list(values)
    if not values or any(v is None for v in values):
        return {"count": len(values), "sum": None, "mean": None, "cv": None}
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Nonfinite observation")
    mean = statistics.fmean(values)
    return {
        "count": len(values),
        "sum": math.fsum(values),
        "mean": mean,
        "cv": statistics.pstdev(values) / abs(mean) if mean else None,
    }


def _weighted_population_summary(values, weights):
    """Population moments of supplied element values, not within-element fluctuations."""
    try:
        total = math.fsum(weights)
        fractions = [weight / total for weight in weights]
        # Center first: small variation on a large baseline must not acquire a
        # spurious SD from rounding the reported mean. The midpoint avoids an
        # overflowing max-min range for finite values of opposite signs.
        center = min(values) / 2 + max(values) / 2
        offsets = [value - center for value in values]
        mean_offset = math.fsum(p * delta for p, delta in zip(fractions, offsets, strict=True))
        mean = center + mean_offset
        deviations = [delta - mean_offset for delta in offsets]
        if all(math.isfinite(delta) for delta in deviations):
            # Hypot avoids overflowing squared deviations when the SD is still finite.
            std = math.hypot(
                *(math.sqrt(p) * delta for p, delta in zip(fractions, deviations, strict=True))
            )
        else:
            scale = max(abs(value) for value in values)
            std = scale * math.hypot(
                *(
                    math.sqrt(p) * (value / scale - mean / scale)
                    for p, value in zip(fractions, values, strict=True)
                )
            )
    except OverflowError as exc:
        raise ValueError("Weighted calculation produced a nonfinite result") from exc
    if not all(math.isfinite(value) for value in (mean, std, total)):
        raise ValueError("Weighted calculation produced a nonfinite result")
    return {"weighted_mean": mean, "weighted_std": std, "weight_sum": total}


def _weighted_exceedance_summary(values, weights, threshold, relation):
    """Measure occupied by element values above an explicitly declared threshold."""
    result = weighted_exceedance_curve(values, weights, [threshold], relation)[0]
    result.pop("threshold")
    return result


def weighted_exceedance_curve(values, weights, thresholds, relation="above"):
    """Evaluate an element-constant weighted distribution, without interpolation.

    Sorting once and searching the suffix measures avoids rereading or reducing a
    field for each threshold. Threshold order is preserved in the returned rows.
    Values and thresholds must use the same unit; weights are positive measures.
    """
    values, weights, thresholds = list(values), list(weights), list(thresholds)
    if not values or len(values) != len(weights):
        raise ValueError("Weighted exceedance requires aligned nonempty values and weights")
    if relation not in {"above", "at-or-above"}:
        raise ValueError("exceedance_relation must be above or at-or-above")
    if any(value is None or not math.isfinite(value) for value in values):
        raise ValueError("Weighted exceedance values must be finite")
    if any(weight is None or not math.isfinite(weight) or weight <= 0 for weight in weights):
        raise ValueError("Weighted exceedance weights must be finite and strictly positive")
    if not thresholds or any(
        isinstance(threshold, bool) or not math.isfinite(threshold) for threshold in thresholds
    ):
        raise ValueError("Weighted exceedance requires finite thresholds in the value unit")
    try:
        total = math.fsum(weights)
    except OverflowError as exc:
        raise ValueError("Weighted exceedance produced a nonfinite measure") from exc
    if not math.isfinite(total):
        raise ValueError("Weighted exceedance produced a nonfinite measure")
    ordered = sorted(zip(values, weights, strict=True))
    ordered_values = [value for value, _ in ordered]
    suffix = [0.0] * (len(ordered) + 1)
    for index in range(len(ordered) - 1, -1, -1):
        # Positive cumulative measures are monotone; cap only floating-point
        # accumulation overshoot against the accurately summed whole measure.
        suffix[index] = min(total, suffix[index + 1] + ordered[index][1])
    suffix[0] = total
    search = bisect_right if relation == "above" else bisect_left
    return [
        {
            "threshold": threshold,
            "weight_sum": total,
            "measure_above": suffix[search(ordered_values, threshold)],
            "exceedance_fraction": suffix[search(ordered_values, threshold)] / total,
            "count": len(values),
        }
        for threshold in thresholds
    ]


def partition_summary(
    areas,
    rates,
    temperatures=None,
    *,
    full_temperature=None,
    temperature_basis=None,
    tolerance=0.0001,
):
    """Area/rate identities and conditional mean-temperature consistency.

    Caller must establish a non-overlapping exhaustive partition. `temperature_basis`
    is 'same-area-mean' only if scope, field and averaging are verified together.
    Missing definitions never become a successful temperature check.
    """
    areas, rates = list(areas), list(rates)
    if not areas or len(areas) != len(rates):
        raise ValueError("Area/rate lengths differ or are empty")
    if any(a is None or not math.isfinite(a) or a <= 0 for a in areas):
        raise ValueError("Areas must be finite and positive")
    if any(q is None or not math.isfinite(q) for q in rates):
        raise ValueError("Rates must be finite")
    if temperature_basis not in (None, "same-area-mean", "different"):
        raise ValueError("Unknown temperature basis")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Invalid tolerance")
    area, rate = math.fsum(areas), math.fsum(rates)
    result = {
        "area": area,
        "rate": rate,
        "mean_flux": rate / area,
        "regional_flux": [q / a for q, a in zip(rates, areas, strict=True)],
        "shares": [q / rate for q in rates] if rate else None,
        "temperature_status": "definition-missing",
        "conditional_temperature": None,
    }
    if temperature_basis == "different":
        result["temperature_status"] = "not-comparable"
        return result
    if temperatures is None or full_temperature is None:
        return result
    temperatures = list(temperatures)
    if len(temperatures) != len(areas):
        raise ValueError("Temperature/area lengths differ")
    if any(t is None for t in temperatures):
        return result
    if not all(math.isfinite(t) for t in [*temperatures, full_temperature]):
        raise ValueError("Nonfinite temperature")
    mean = math.fsum(a * t for a, t in zip(areas, temperatures, strict=True)) / area
    result.update(conditional_temperature=mean, temperature_difference=full_temperature - mean)
    consistent = abs(full_temperature - mean) <= tolerance
    if temperature_basis == "same-area-mean":
        result["temperature_status"] = "consistent" if consistent else "inconsistent"
    elif not consistent:
        result["temperature_status"] = "conditional-conflict"
    return result


def format_value(value, places: int) -> str:
    """Round once from the original value, never from a previously rounded display."""
    if value is None:
        raise ValueError("Missing value cannot be formatted as a number")
    number = Decimal(str(value))
    if not number.is_finite() or not isinstance(places, int) or not 0 <= places <= 12:
        raise ValueError("Finite value and 0–12 decimal places required")
    return format(number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN), "f")


def resolve_table_result(
    reports, *, calculation_id, group, field, source_record=None, places=3, percentage=False
) -> dict:
    """Select one current table result with its declared units and supporting records.

    Groups match exactly. Regional arrays are located by CSV record number (header
    is record 1), not by array index. Shares depend on every record in the group
    through their denominator; regional flux depends only on the selected record.
    Dimensionless results use an empty unit. Percentage display changes neither
    raw_value nor the stored report, and rounds only after multiplying by 100.
    """
    location = f"calculation {calculation_id!r}, group {group!r}, field {field!r}"
    if type(places) is not int or not 0 <= places <= 12:
        raise ValueError(f"{location}: places must be an integer from 0 to 12")
    if type(percentage) is not bool:
        raise ValueError(f"{location}: percentage must be a boolean")
    matches = [report for report in reports if report.get("id") == calculation_id]
    if len(matches) != 1:
        raise ValueError(f"{location}: expected one calculation ID, found {len(matches)}")
    report = matches[0]
    if report.get("operation") in {"field_integral", "field_difference", "energy_budget"}:
        from .field_diagnostics import resolve_field_result

        if source_record is not None:
            raise ValueError("Field diagnostic references select a group, not source_record")
        return resolve_field_result(report, group, field, places, percentage=percentage)
    fields = {
        "population": {"count", "sum", "mean", "cv"},
        "weighted_population": {"weighted_mean", "weighted_std", "weight_sum"},
        "weighted_exceedance": {"weight_sum", "measure_above", "exceedance_fraction", "count"},
        "scalar_select": {"value"},
        "paired_change": {"difference", "relative_change", "relative_reduction"},
        "partition": {"area", "rate", "mean_flux", "regional_flux", "shares"},
        "result_comparison": {"difference", "relative_change", "relative_reduction"},
        "temporal": TEMPORAL_FIELDS,
        "temporal_difference": TEMPORAL_FIELDS,
        "reference_range": REFERENCE_RANGE_FIELDS,
        "paired_reference_change": REFERENCE_RANGE_FIELDS,
    }
    operation = report.get("operation")
    if not isinstance(field, str) or field not in fields.get(operation, set()):
        raise ValueError(f"{location}: unsupported field for operation {operation!r}")
    regional = field in {"regional_flux", "shares"}
    if regional:
        if type(source_record) is not int or source_record < 2:
            raise ValueError(f"{location}: source_record must be a CSV record number >= 2")
    elif source_record is not None:
        raise ValueError(f"{location}: scalar fields do not accept source_record")
    if percentage and field not in {
        "cv",
        "shares",
        "relative_change",
        "relative_reduction",
        "exceedance_fraction",
    }:
        raise ValueError(f"{location}: percentage is only supported for relative quantities")
    groups = [item for item in report["groups"] if item.get("group") == group]
    if len(groups) != 1:
        raise ValueError(f"{location}: expected one exact group, found {len(groups)}")
    selected = groups[0]
    result = selected.get("result")
    if selected.get("status") != "computed" or not isinstance(result, dict):
        raise ValueError(f"{location}: result unavailable ({selected.get('status')})")
    if operation == "result_comparison":
        raw_value = result.get(field)
        if type(raw_value) not in (int, float) or not math.isfinite(raw_value):
            raise ValueError(f"{location}: missing or nonfinite numeric value")
        unit = report.get("units", {}).get("value") if field == "difference" else ""
        if not isinstance(unit, str):
            raise ValueError(f"{location}: missing declared role units")
        upstream = report.get("upstream")
        if not isinstance(upstream, dict) or set(upstream) != {"reference", "comparison"}:
            raise ValueError(f"{location}: missing supporting_results")
        supporting = []
        for role in ("reference", "comparison"):
            parent = upstream[role]
            if not isinstance(parent, dict):
                raise ValueError(f"{location}: missing supporting result for {role}")
            records_key = "array_indices" if "array_indices" in parent else "csv_records"
            records = parent.get(records_key)
            minimum = 0 if records_key == "array_indices" else 2
            if (
                parent.get("field") not in _COMPARABLE_FIELDS.get(parent.get("operation"), set())
                or not isinstance(parent.get("source"), str)
                or not parent["source"]
                or not isinstance(records, list)
                or not records
                or any(type(n) is not int or n < minimum for n in records)
                or len(set(records)) != len(records)
            ):
                raise ValueError(f"{location}: invalid supporting result for {role}")
            supporting.append({**parent, records_key: list(records)})
        display_value = Decimal(str(raw_value)) * 100 if percentage else raw_value
        return {
            "value": format_value(display_value, places),
            "unit": "%" if percentage else unit,
            "raw_value": raw_value,
            "calculation_id": calculation_id,
            "group": group,
            "field": field,
            "source_record": source_record,
            "supporting_results": supporting,
        }
    array_source = "array_indices" in selected
    raw_records = selected.get("array_indices" if array_source else "csv_records")
    records = (
        [i + 2 for i in raw_records]
        if array_source
        and isinstance(raw_records, list)
        and all(type(i) is int for i in raw_records)
        else raw_records
    )
    if (
        not isinstance(records, list)
        or not records
        or any(type(record) is not int or record < 2 for record in records)
        or len(set(records)) != len(records)
    ):
        raise ValueError(f"{location}: missing or invalid supporting csv_records")
    if field not in result:
        raise ValueError(f"{location}: missing result field")
    raw_value = result[field]
    supporting_records = list(records)
    if regional:
        if source_record not in records:
            raise ValueError(f"{location}: source_record {source_record} is not in this group")
        if not isinstance(raw_value, list) or len(raw_value) != len(records):
            raise ValueError(f"{location}: missing or misaligned regional values")
        raw_value = raw_value[records.index(source_record)]
        if field == "regional_flux":
            supporting_records = [source_record]
    if type(raw_value) not in (int, float) or not math.isfinite(raw_value):
        raise ValueError(f"{location}: missing or nonfinite numeric value")
    units = report.get("units", {})
    required_units = (
        {"value", "weight"}
        if operation in {"weighted_population", "weighted_exceedance"}
        else {"area", "rate"}
        if operation == "partition"
        else {"time", "value"}
        if operation == "temporal"
        else {"time", "reference", "comparison"}
        if operation == "temporal_difference"
        else {"value"}
    )
    if any(not isinstance(units.get(role), str) for role in required_units):
        raise ValueError(f"{location}: missing declared role units")
    if operation in {"reference_range", "paired_reference_change"}:
        unit = units["value"]
        if report.get("quantity_kind") in {
            "absolute-temperature",
            "temperature-difference",
        } and (
            operation == "paired_reference_change" or field in {"difference", "outside_distance"}
        ):
            unit = "K"
    elif operation == "temporal_difference":
        value_unit = (
            "K"
            if report.get("quantity_kind") in {"absolute-temperature", "temperature-difference"}
            else units["reference"]
        )
        unit = temporal_unit(field, value_unit, "ordinary")
    elif operation == "temporal":
        unit = temporal_unit(field, units["value"], report.get("quantity_kind", "ordinary"))
    elif field in {
        "count",
        "cv",
        "shares",
        "relative_change",
        "relative_reduction",
        "exceedance_fraction",
    }:
        unit = ""
    elif field in {"sum", "mean", "value", "difference", "weighted_mean", "weighted_std"}:
        unit = units["value"]
        if (
            field in {"difference", "weighted_std"}
            and report.get("quantity_kind") == "absolute-temperature"
        ) or (field == "weighted_std" and report.get("quantity_kind") == "temperature-difference"):
            unit = "K"
    elif field in {"weight_sum", "measure_above"}:
        unit = units["weight"]
    elif field in {"area", "rate"}:
        unit = units[field]
    else:
        unit = f"({units['rate'] or '1'})/({units['area'] or '1'})"
    source = report.get("source")
    if not isinstance(source, str) or not source:
        raise ValueError(f"{location}: missing CSV source path")
    display_value = Decimal(str(raw_value)) * 100 if percentage else raw_value
    return {
        "value": format_value(display_value, places),
        "unit": "%" if percentage else unit,
        "raw_value": raw_value,
        "source": source,
        ("array_indices" if array_source else "csv_records"): [n - 2 for n in supporting_records]
        if array_source
        else supporting_records,
        "calculation_id": calculation_id,
        "group": group,
        "field": field,
        "source_record": source_record,
    }
