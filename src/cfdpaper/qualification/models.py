"""Strict immutable models for canonical CFD observations."""

from __future__ import annotations

import math
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class QualificationModel(BaseModel):
    """Frozen internal model; public contracts remain controller-owned."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ValueRole(str, Enum):
    RAW_SAMPLE = "raw-sample"
    DECLARED_AGGREGATE = "declared-aggregate"
    PRECOMPUTED_QOI = "precomputed-qoi"


class ObservationRow(QualificationModel):
    case_id: str
    coordinate_name: str
    coordinate_value: float
    coordinate_unit: str
    variable: str
    value: float
    value_role: ValueRole
    unit: str
    scope: str
    source_locator: str
    aggregation: str | None = None
    statistical_window: str | None = None
    note: str | None = None

    @field_validator(
        "case_id",
        "coordinate_name",
        "coordinate_unit",
        "variable",
        "unit",
        "scope",
        "source_locator",
    )
    @classmethod
    def required_text_is_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("required text must be nonblank")
        return stripped

    @field_validator("aggregation", "statistical_window", "note")
    @classmethod
    def optional_text_is_trimmed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("coordinate_value", "value")
    @classmethod
    def numeric_values_are_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("value must be finite")
        return value

    @model_validator(mode="after")
    def aggregation_matches_value_role(self) -> ObservationRow:
        if self.value_role == ValueRole.DECLARED_AGGREGATE and self.aggregation is None:
            raise ValueError("declared aggregate requires aggregation")
        if self.value_role != ValueRole.DECLARED_AGGREGATE and self.aggregation is not None:
            raise ValueError("aggregation is only valid for a declared aggregate")
        return self


class ObservationTable(QualificationModel):
    source_uri: str
    source_sha256: str
    rows: tuple[ObservationRow, ...]
    guidance: tuple[str, ...] = ()

    @field_validator("source_uri", "source_sha256")
    @classmethod
    def table_text_is_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must be nonblank")
        return stripped


class ExpectedMember(QualificationModel):
    case_id: str
    coordinate_name: str
    coordinate_value: float
    coordinate_unit: str
    variable: str
    unit: str
    scope: str

    @field_validator("case_id", "coordinate_name", "coordinate_unit", "variable", "unit", "scope")
    @classmethod
    def expected_text_is_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must be nonblank")
        return stripped

    @field_validator("coordinate_value")
    @classmethod
    def coordinate_is_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("coordinate value must be finite")
        return value
