"""Strict immutable models for canonical CFD observations."""

from __future__ import annotations

import math
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


CaseDifferenceRole = Literal[
    "intended-study-factor",
    "demonstrated-equivalent-or-immaterial",
    "unresolved-nuisance",
    "blocking",
]
QualificationStatus = Literal["eligible", "restricted", "insufficient"]
VNVState = Literal["demonstrated", "partial", "not-demonstrated", "not-applicable"]
ThresholdOperator = Literal["<=", "<", ">=", ">"]
ThresholdConsequence = Literal["blocking", "restricting"]
QoIOperator = Literal["identity", "difference", "ratio", "relative-change"]
MissingDataPolicy = Literal["reject"]


class CaseDifference(QualificationModel):
    name: str
    reference: str
    candidate: str
    role: CaseDifferenceRole
    basis: str | None = None
    source_locator: str | None = None

    @field_validator("name", "reference", "candidate")
    @classmethod
    def difference_text_is_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("difference text must be nonblank")
        return stripped

    @field_validator("basis", "source_locator")
    @classmethod
    def difference_optional_text_is_trimmed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def demonstrated_equivalence_is_located(self) -> CaseDifference:
        if self.role == "demonstrated-equivalent-or-immaterial" and not (
            self.basis and self.source_locator
        ):
            raise ValueError("demonstrated equivalence requires basis and source locator")
        return self


class ThresholdBasis(QualificationModel):
    metric: str
    operator: ThresholdOperator
    value: float
    unit: str
    basis: str
    source_locator: str
    consequence: ThresholdConsequence

    @field_validator("metric", "unit", "basis", "source_locator")
    @classmethod
    def threshold_text_is_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("threshold text must be nonblank")
        return stripped

    @field_validator("value")
    @classmethod
    def threshold_value_is_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("threshold value must be finite")
        return value


class ConvergenceObservation(QualificationModel):
    metric: str
    observed_value: float
    unit: str
    threshold: ThresholdBasis
    evidence_id: str
    source_locator: str

    @field_validator("metric", "unit", "evidence_id", "source_locator")
    @classmethod
    def assessment_text_is_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("assessment text must be nonblank")
        return stripped

    @field_validator("observed_value")
    @classmethod
    def observed_value_is_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("observed value must be finite")
        return value

    @model_validator(mode="after")
    def threshold_targets_observed_metric(self) -> ConvergenceObservation:
        if self.metric != self.threshold.metric:
            raise ValueError("threshold metric must match observed metric")
        return self


class ConservationObservation(ConvergenceObservation):
    pass


class VNVStatus(QualificationModel):
    state: VNVState
    summary: str
    evidence_ids: tuple[str, ...] = ()
    basis: str | None = None
    source_locator: str | None = None
    comparison_exemption: bool = False

    @field_validator("summary")
    @classmethod
    def summary_is_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("summary must be nonblank")
        return stripped

    @field_validator("evidence_ids")
    @classmethod
    def evidence_ids_are_nonblank_and_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in value)
        if any(not item for item in normalized):
            raise ValueError("evidence identifiers must be nonblank")
        if len(set(normalized)) != len(normalized):
            raise ValueError("evidence identifiers must be unique")
        return normalized

    @field_validator("basis", "source_locator")
    @classmethod
    def vnv_optional_text_is_trimmed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def not_applicable_is_justified(self) -> VNVStatus:
        if self.state == "not-applicable" and not (self.basis and self.source_locator):
            raise ValueError("not-applicable requires basis and source locator")
        if self.comparison_exemption:
            if self.state != "not-applicable":
                raise ValueError("comparison exemption is only valid for not-applicable V&V")
            if not (self.evidence_ids and self.basis and self.source_locator):
                raise ValueError("comparison exemption requires located evidence")
        if self.state in {"demonstrated", "partial"} and not (
            self.evidence_ids and self.basis and self.source_locator
        ):
            raise ValueError(f"{self.state} V&V status requires located evidence")
        return self


class QualificationReport(QualificationModel):
    status: QualificationStatus
    differences: tuple[CaseDifference, ...]
    verification: VNVStatus
    validation: VNVStatus
    blockers: tuple[str, ...]
    restrictions: tuple[str, ...]
    minimum_corrections: tuple[str, ...]
    input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class OperandSelector(QualificationModel):
    name: str
    variable: str
    value_role: ValueRole
    unit: str
    scope: str
    locator_policy: str

    @field_validator("name", "variable", "unit", "scope", "locator_policy")
    @classmethod
    def selector_text_is_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("operand selector text must be nonblank")
        return stripped


class QoIProposal(QualificationModel):
    qoi_name: str
    scientific_definition: str
    operator: QoIOperator
    operands: tuple[OperandSelector, ...]
    output_unit: str
    expected_members: tuple[ExpectedMember, ...]
    trend_tolerance: float
    missing_data_policy: MissingDataPolicy = "reject"
    reference_member: str | None = None
    allow_quantitative_reporting: bool = True

    @field_validator("qoi_name", "scientific_definition", "output_unit")
    @classmethod
    def qoi_text_is_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("QoI text must be nonblank")
        return stripped

    @field_validator("reference_member")
    @classmethod
    def reference_member_is_trimmed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("trend_tolerance")
    @classmethod
    def trend_tolerance_is_finite_and_nonnegative(cls, value: float) -> float:
        if not math.isfinite(value) or value < 0:
            raise ValueError("trend tolerance must be finite and nonnegative")
        return value

    @model_validator(mode="after")
    def operator_grammar_and_membership_are_closed(self) -> QoIProposal:
        expected_operands = {
            "identity": 1,
            "difference": 2,
            "ratio": 2,
            "relative-change": 1,
        }[self.operator]
        if len(self.operands) != expected_operands:
            raise ValueError(f"{self.operator} requires exactly {expected_operands} operand(s)")
        if self.operator == "relative-change" and self.reference_member is None:
            raise ValueError("relative-change requires a reference member")
        if self.operator != "relative-change" and self.reference_member is not None:
            raise ValueError("reference member is only valid for relative-change")
        keys = tuple(
            (item.case_id, item.coordinate_name, item.coordinate_value)
            for item in self.expected_members
        )
        if not keys:
            raise ValueError("expected membership must not be empty")
        if len(set(keys)) != len(keys):
            raise ValueError("expected membership must be unique")
        return self


class CandidateQoIContract(QualificationModel):
    qoi_contract_id: str
    question_id: str
    topic_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    qoi_name: str
    scientific_definition: str
    operator: QoIOperator
    operands: tuple[OperandSelector, ...]
    output_unit: str
    expected_members: tuple[ExpectedMember, ...]
    trend_tolerance: float
    missing_data_policy: MissingDataPolicy
    reference_member: str | None = None
    allow_quantitative_reporting: bool
    qualification_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    verification_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation_input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    scientific_input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["candidate"] = "candidate"

    @field_validator("qoi_contract_id", "question_id", "qoi_name", "scientific_definition")
    @classmethod
    def candidate_text_is_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("candidate contract text must be nonblank")
        return stripped

    @field_validator("trend_tolerance")
    @classmethod
    def candidate_tolerance_is_finite_and_nonnegative(cls, value: float) -> float:
        if not math.isfinite(value) or value < 0:
            raise ValueError("trend tolerance must be finite and nonnegative")
        return value

    @model_validator(mode="after")
    def candidate_operator_grammar_is_closed(self) -> CandidateQoIContract:
        expected_operands = {
            "identity": 1,
            "difference": 2,
            "ratio": 2,
            "relative-change": 1,
        }[self.operator]
        if len(self.operands) != expected_operands:
            raise ValueError(f"{self.operator} requires exactly {expected_operands} operand(s)")
        if self.operator == "relative-change" and self.reference_member is None:
            raise ValueError("relative-change requires a reference member")
        if self.operator != "relative-change" and self.reference_member is not None:
            raise ValueError("reference member is only valid for relative-change")
        keys = tuple(
            (item.case_id, item.coordinate_name, item.coordinate_value)
            for item in self.expected_members
        )
        if not keys:
            raise ValueError("expected membership must not be empty")
        if len(set(keys)) != len(keys):
            raise ValueError("expected membership must be unique")
        return self
