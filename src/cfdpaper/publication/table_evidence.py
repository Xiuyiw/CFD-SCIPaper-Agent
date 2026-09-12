"""Small, explicit calculations on exported tables; no solver or physics inference."""

import csv
import math
import statistics
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path


def calculate_table(path, *, operation, columns, group_by=None):
    """Apply an explicit calculation to every CSV row, retaining source row locations.

    Units and physical domains are declared by the caller, never inferred here.
    No rows are silently excluded and no unit conversion is performed.
    """
    required = {"value"} if operation == "population" else {"area", "rate"}
    if operation not in {"population", "partition"} or set(columns) != required:
        raise ValueError("Use population/value or partition/area,rate columns")
    if len(set(columns.values())) != len(columns):
        raise ValueError("Calculation roles require distinct columns")
    rows = read_numeric_table(path, list(columns.values()))
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
        values = {key: [r[column] for _, r in items] for key, column in columns.items()}
        if any(v is None for sequence in values.values() for v in sequence):
            result, status = None, "missing-values"
        elif operation == "population":
            result, status = population_summary(values["value"]), "computed"
        else:
            result = partition_summary(values["area"], values["rate"])
            # Temperature consistency is a separate calculation requiring more inputs.
            result.pop("temperature_status")
            result.pop("conditional_temperature")
            status = "computed"
        results.append(
            {
                "group": name,
                "csv_records": [n for n, _ in items],
                "status": status,
                "result": result,
            }
        )
    return {"rows_read": len(rows), "groups": results}


def read_numeric_table(path: Path, columns: list[str]) -> list[dict]:
    """Read every row; blank numeric cells remain None, invalid cells raise."""
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(columns) <= set(reader.fieldnames or []):
            raise ValueError("Missing requested numeric columns")
        rows = list(reader)
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
    if percentage and field not in {"cv", "shares"}:
        raise ValueError(f"{location}: percentage is only supported for cv and shares")
    groups = [item for item in report["groups"] if item.get("group") == group]
    if len(groups) != 1:
        raise ValueError(f"{location}: expected one exact group, found {len(groups)}")
    selected = groups[0]
    result = selected.get("result")
    if selected.get("status") != "computed" or not isinstance(result, dict):
        raise ValueError(f"{location}: result unavailable ({selected.get('status')})")
    records = selected.get("csv_records")
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
    required_units = {"value"} if operation == "population" else {"area", "rate"}
    if any(not isinstance(units.get(role), str) for role in required_units):
        raise ValueError(f"{location}: missing declared role units")
    if field in {"count", "cv", "shares"}:
        unit = ""
    elif field in {"sum", "mean"}:
        unit = units["value"]
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
        "csv_records": supporting_records,
        "calculation_id": calculation_id,
        "group": group,
        "field": field,
        "source_record": source_record,
    }
