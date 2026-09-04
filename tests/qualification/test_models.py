from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from cfdpaper.qualification.models import ObservationRow, ObservationTable, ValueRole


def _row(**updates: object) -> ObservationRow:
    values: dict[str, object] = {
        "case_id": "P1",
        "coordinate_name": "mean_velocity",
        "coordinate_value": 0.25,
        "coordinate_unit": "m/s",
        "variable": "pressure_drop",
        "value": 2.0,
        "value_role": ValueRole.PRECOMPUTED_QOI,
        "unit": "Pa",
        "scope": "inlet-to-outlet pressure difference",
        "source_locator": "observations.csv#row=2",
    }
    values.update(updates)
    return ObservationRow.model_validate(values)


def test_observation_row_keeps_value_role_unit_scope_and_locator() -> None:
    row = _row()

    assert row.value_role == ValueRole.PRECOMPUTED_QOI
    assert row.source_locator.endswith("row=2")
    assert row.unit == "Pa"


def test_declared_aggregate_requires_aggregation() -> None:
    with pytest.raises(ValidationError, match="aggregation"):
        _row(value_role="declared-aggregate")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("case_id", "   "),
        ("coordinate_name", ""),
        ("variable", "\t"),
        ("unit", " "),
        ("scope", ""),
        ("source_locator", "  "),
    ],
)
def test_required_strings_are_nonblank(field: str, value: str) -> None:
    with pytest.raises(ValidationError, match=field):
        _row(**{field: value})


@pytest.mark.parametrize("field", ["coordinate_value", "value"])
@pytest.mark.parametrize("number", [math.nan, math.inf, -math.inf])
def test_observation_numbers_are_finite(field: str, number: float) -> None:
    with pytest.raises(ValidationError, match="finite"):
        _row(**{field: number})


def test_unknown_value_role_is_rejected() -> None:
    with pytest.raises(ValidationError, match="value_role"):
        _row(value_role="computed-by-magic")


@pytest.mark.parametrize("role", ["raw-sample", "precomputed-qoi"])
def test_nonaggregate_roles_reject_aggregation(role: str) -> None:
    with pytest.raises(ValidationError, match="aggregation"):
        _row(value_role=role, aggregation="mean")


def test_nested_observation_sequence_is_immutable_and_defensive() -> None:
    rows = [_row()]
    table = ObservationTable(
        source_uri="observations.csv",
        source_sha256="0" * 64,
        rows=rows,
    )
    rows.clear()

    assert len(table.rows) == 1
    assert isinstance(table.rows, tuple)
    with pytest.raises(ValidationError):
        table.rows = ()  # type: ignore[misc]
