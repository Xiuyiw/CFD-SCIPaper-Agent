"""Strict, read-only parser for canonical observation tables."""

from __future__ import annotations

import csv
import hashlib
import io
import math
from pathlib import Path

from pydantic import ValidationError

from cfdpaper.scientific.units import canonical_unit, convert_value, units_compatible

from .models import ExpectedMember, ObservationRow, ObservationTable

_REQUIRED_COLUMNS = {
    "case_id",
    "coordinate_name",
    "coordinate_value",
    "coordinate_unit",
    "variable",
    "value",
    "value_role",
    "unit",
    "scope",
    "source_locator",
}
_OPTIONAL_COLUMNS = {"aggregation", "statistical_window", "note"}
_ALLOWED_COLUMNS = _REQUIRED_COLUMNS | _OPTIONAL_COLUMNS


class ObservationInputError(ValueError):
    def __init__(self, issue_code: str, message: str) -> None:
        super().__init__(message)
        self.issue_code = issue_code


def _parse_number(text: str, *, row_number: int, field: str) -> float:
    try:
        value = float(text)
    except ValueError as error:
        raise ObservationInputError(
            "invalid-number", f"Row {row_number} has an invalid {field}."
        ) from error
    if not math.isfinite(value):
        raise ObservationInputError("invalid-number", f"Row {row_number} has a nonfinite {field}.")
    return value


def load_observations(path: Path) -> ObservationTable:
    """Read a canonical UTF-8 CSV without modifying it or inferring operators."""

    source = path.expanduser().resolve()
    raw = source.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ObservationInputError("invalid-encoding", "Observation CSV must be UTF-8.") from error
    reader = csv.DictReader(io.StringIO(text, newline=""))
    headers = reader.fieldnames
    if headers is None:
        raise ObservationInputError("missing-required-column", "Observation CSV has no header.")
    if len(headers) != len(set(headers)):
        raise ObservationInputError("duplicate-column", "Observation CSV repeats a header.")
    missing = sorted(_REQUIRED_COLUMNS - set(headers))
    if missing:
        raise ObservationInputError(
            "missing-required-column", f"Missing required column: {missing[0]}."
        )
    unknown = sorted(set(headers) - _ALLOWED_COLUMNS)
    if unknown:
        raise ObservationInputError("unknown-column", f"Unknown column: {unknown[0]}.")

    rows: list[ObservationRow] = []
    keys: set[tuple[str, str, float, str, str]] = set()
    for row_number, raw_row in enumerate(reader, start=2):
        if None in raw_row:
            raise ObservationInputError(
                "unexpected-row-column",
                f"Row {row_number} contains data beyond the declared columns.",
            )
        missing_values = sorted(field for field in _REQUIRED_COLUMNS if raw_row.get(field) is None)
        if missing_values:
            raise ObservationInputError(
                "missing-required-value",
                f"Row {row_number} has no value for required column {missing_values[0]}.",
            )
        locator = (raw_row.get("source_locator") or "").strip()
        if not locator:
            raise ObservationInputError(
                "missing-source-locator", f"Row {row_number} has no source locator."
            )
        coordinate_unit = raw_row["coordinate_unit"].strip()
        unit = raw_row["unit"].strip()
        try:
            canonical_unit(coordinate_unit)
            canonical_unit(unit)
        except ValueError as error:
            raise ObservationInputError("unknown-unit", f"Row {row_number}: {error}") from error
        if (
            raw_row["value_role"].strip() == "declared-aggregate"
            and not (raw_row.get("aggregation") or "").strip()
        ):
            raise ObservationInputError(
                "missing-aggregation", f"Row {row_number} aggregate has no definition."
            )
        values = {
            "case_id": raw_row["case_id"],
            "coordinate_name": raw_row["coordinate_name"],
            "coordinate_value": _parse_number(
                raw_row["coordinate_value"], row_number=row_number, field="coordinate value"
            ),
            "coordinate_unit": coordinate_unit,
            "variable": raw_row["variable"],
            "value": _parse_number(raw_row["value"], row_number=row_number, field="value"),
            "value_role": raw_row["value_role"],
            "unit": unit,
            "scope": raw_row["scope"],
            "source_locator": locator,
            "aggregation": raw_row.get("aggregation"),
            "statistical_window": raw_row.get("statistical_window"),
            "note": raw_row.get("note"),
        }
        try:
            parsed = ObservationRow.model_validate(values)
        except ValidationError as error:
            raise ObservationInputError(
                "invalid-observation", f"Row {row_number} is invalid: {error.errors()[0]['msg']}"
            ) from error
        key = (
            parsed.case_id,
            parsed.coordinate_name,
            parsed.coordinate_value,
            parsed.variable,
            parsed.scope,
        )
        if key in keys:
            raise ObservationInputError(
                "duplicate-observation", f"Row {row_number} duplicates a scientific observation."
            )
        keys.add(key)
        rows.append(parsed)

    return ObservationTable(
        source_uri=path.as_posix(),
        source_sha256=hashlib.sha256(raw).hexdigest(),
        rows=tuple(rows),
    )


def _matches(row: ObservationRow, expected: ExpectedMember) -> bool:
    try:
        coordinate = convert_value(
            row.coordinate_value, row.coordinate_unit, expected.coordinate_unit
        )
        value_units_match = units_compatible(row.unit, expected.unit)
    except ValueError:
        return False
    return (
        row.case_id == expected.case_id
        and row.coordinate_name == expected.coordinate_name
        and math.isclose(coordinate, expected.coordinate_value, rel_tol=1e-12, abs_tol=1e-15)
        and row.variable == expected.variable
        and value_units_match
        and row.scope == expected.scope
    )


def validate_expected_membership(
    rows: tuple[ObservationRow, ...],
    expected: tuple[ExpectedMember, ...],
) -> tuple[ObservationRow, ...]:
    """Return rows in expected scientific order or raise the first membership error."""

    ordered: list[ObservationRow] = []
    used: set[int] = set()
    for member in expected:
        matches = [index for index, row in enumerate(rows) if _matches(row, member)]
        if not matches:
            raise ObservationInputError(
                "missing-expected-member",
                f"Case {member.case_id} is missing from the declared sequence.",
            )
        if len(matches) != 1:
            raise ObservationInputError(
                "duplicate-expected-member",
                f"Case {member.case_id} appears more than once in the declared sequence.",
            )
        used.add(matches[0])
        ordered.append(rows[matches[0]])
    if len(used) != len(rows):
        raise ObservationInputError(
            "unexpected-member", "The observation table contains an unexpected scientific member."
        )
    return tuple(ordered)
