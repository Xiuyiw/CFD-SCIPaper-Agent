"""Small, explicit calculations on exported tables; no solver or physics inference."""

import csv
import math
import re
import statistics
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path


def display_unit(unit: str) -> str:
    """Typeset supported unit labels without converting their numerical scale."""
    if unit == "degC":
        return "°C"
    area = re.fullmatch(r"(m|cm|mm)(?:\^?2|²)", unit)
    if area:
        return f"{area[1]}²"
    volume = re.fullmatch(r"(m|cm|mm)(?:\^?3|³)", unit)
    if volume:
        return f"{volume[1]}³"
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
):
    """Apply an explicit calculation to every CSV row, retaining source row locations.

    Units and physical domains are declared by the caller, never inferred here.
    No rows are silently excluded and no unit conversion is performed.
    """
    scalar_ops = {"population", "scalar_select", "paired_change"}
    required = (
        {"value", "weight"}
        if operation == "weighted_population"
        else {"value"}
        if operation in scalar_ops
        else {"area", "rate"}
    )
    if (
        operation not in scalar_ops | {"partition", "weighted_population"}
        or set(columns) != required
    ):
        raise ValueError(
            "Use scalar/value, weighted_population/value,weight or partition/area,rate"
        )
    if operation == "weighted_population":
        if weight_kind not in {"area", "volume"}:
            raise ValueError("Weighted population requires weight_kind area or volume")
        if not isinstance(units, dict) or set(units) != {"value", "weight"}:
            raise ValueError("Weighted population requires declared value and weight units")
        measure = units["weight"]
        power = r"(?:\^?2|²)" if weight_kind == "area" else r"(?:\^?3|³)"
        if not isinstance(measure, str) or not re.fullmatch(r"(?:m|cm|mm)" + power, measure):
            raise ValueError("Weight unit must match the declared area or volume measure")
    if operation == "paired_change":
        if not all(isinstance(x, str) and x.strip() for x in (pair_by, reference, comparison)):
            raise ValueError("Paired change requires pair_by, reference and comparison")
        if reference == comparison:
            raise ValueError("Reference and comparison must differ")
    if operation in {"paired_change", "weighted_population"}:
        unit = (units or {}).get("value")
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
            operation == "weighted_population"
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
    numeric_columns = list(columns.values()) + ([region_fraction] if region_fraction else [])
    rows = read_numeric_table(
        path, numeric_columns, extra_columns=[key for key in (group_by, pair_by) if key]
    )
    if not rows:
        raise ValueError("Calculation table is empty")
    groups = {}
    for index, row in enumerate(rows, 2):
        if group_by and (group_by not in row or not str(row[group_by] or "").strip()):
            raise ValueError(f"Missing group at {path}:{index}")
        group = str(row[group_by]) if group_by else "all"
        groups.setdefault(group, []).append((index, row))
    results = []
    for name, items in groups.items():
        if operation == "scalar_select" and len(items) != 1:
            raise ValueError(f"Scalar selection requires exactly one record in group {name!r}")
        if operation == "paired_change":
            chosen = []
            for member in (reference, comparison):
                matches = [(n, r) for n, r in items if r.get(pair_by) == member]
                if len(matches) != 1:
                    raise ValueError(f"Group {name!r}: expected one record for {member!r}")
                chosen.extend(matches)
            items = chosen
        values = {key: [r[column] for _, r in items] for key, column in columns.items()}
        if operation == "weighted_population" and any(
            w is None or not math.isfinite(w) or w <= 0 for w in values["weight"]
        ):
            raise ValueError(f"Group {name!r}: weights must be finite and strictly positive")
        if any(v is None for sequence in values.values() for v in sequence):
            result, status = None, "missing-values"
        elif operation == "population":
            result, status = population_summary(values["value"]), "computed"
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
            delta = compared - baseline
            denominator = baseline
            if quantity_kind == "absolute-temperature":
                denominator = (
                    None if temperature_reference is None else baseline - temperature_reference
                )
            ratio = delta / denominator if denominator else None
            if not math.isfinite(delta) or (ratio is not None and not math.isfinite(ratio)):
                raise ValueError("Paired calculation produced a nonfinite result")
            result = {
                "difference": delta,
                "relative_change": ratio,
                "relative_reduction": -ratio if ratio is not None else None,
            }
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
            }
        )
    return {"rows_read": len(rows), "groups": results}


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
        for column in columns:
            raw = row[column]
            value = None if raw is None or not raw.strip() else float(raw)
            if value is not None and not math.isfinite(value):
                raise ValueError(f"Nonfinite value at {path}:{line}:{column}")
            row[column] = value
    return rows


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
    fields = {
        "population": {"count", "sum", "mean", "cv"},
        "weighted_population": {"weighted_mean", "weighted_std", "weight_sum"},
        "scalar_select": {"value"},
        "paired_change": {"difference", "relative_change", "relative_reduction"},
        "partition": {"area", "rate", "mean_flux", "regional_flux", "shares"},
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
    if percentage and field not in {"cv", "shares", "relative_change", "relative_reduction"}:
        raise ValueError(f"{location}: percentage is only supported for relative quantities")
    groups = [item for item in report["groups"] if item.get("group") == group]
    if len(groups) != 1:
        raise ValueError(f"{location}: expected one exact group, found {len(groups)}")
    selected = groups[0]
    result = selected.get("result")
    if selected.get("status") != "computed" or not isinstance(result, dict):
        raise ValueError(f"{location}: result unavailable ({selected.get('status')})")
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
        if operation == "weighted_population"
        else {"area", "rate"}
        if operation == "partition"
        else {"value"}
    )
    if any(not isinstance(units.get(role), str) for role in required_units):
        raise ValueError(f"{location}: missing declared role units")
    if field in {"count", "cv", "shares", "relative_change", "relative_reduction"}:
        unit = ""
    elif field in {"sum", "mean", "value", "difference", "weighted_mean", "weighted_std"}:
        unit = units["value"]
        if (
            field in {"difference", "weighted_std"}
            and report.get("quantity_kind") == "absolute-temperature"
        ) or (field == "weighted_std" and report.get("quantity_kind") == "temperature-difference"):
            unit = "K"
    elif field == "weight_sum":
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
