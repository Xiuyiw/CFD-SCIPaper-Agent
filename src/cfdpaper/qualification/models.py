"""Strict immutable models for canonical CFD observations."""

from __future__ import annotations

import math
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cfdpaper.topic_generation.canonical import canonical_sha256


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


class DiscreteTrend(str, Enum):
    MONOTONIC_INCREASING = "monotonic-increasing"
    MONOTONIC_DECREASING = "monotonic-decreasing"
    INTERIOR_PEAK = "interior-peak"
    PLATEAU = "plateau"
    OVERALL_CHANGE = "overall-change"


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
    intended_use_supported: bool = False

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
        if self.intended_use_supported and self.state != "demonstrated":
            raise ValueError("intended-use support requires demonstrated V&V")
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


class AuthorApproval(QualificationModel):
    author: str
    object_id: str
    object_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_at: datetime

    @field_validator("author", "object_id")
    @classmethod
    def approval_text_is_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("approval text must be nonblank")
        return stripped

    @field_validator("approved_at")
    @classmethod
    def approval_time_is_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("approved_at must be timezone-aware")
        return value


class LockedQoIContract(QualificationModel):
    candidate: CandidateQoIContract
    approval: AuthorApproval
    scientific_input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def approval_is_bound_to_candidate(self) -> LockedQoIContract:
        if (
            self.approval.object_id != self.candidate.qoi_contract_id
            or self.approval.object_fingerprint != self.candidate.fingerprint
        ):
            raise ValueError("approval must remain bound to the locked candidate")
        if self.scientific_input_fingerprint != self.candidate.scientific_input_fingerprint:
            raise ValueError("locked scientific input must match the candidate")
        return self


class QoIValue(QualificationModel):
    result_id: str
    case_id: str
    coordinate_value: float
    coordinate_unit: str
    value: float
    unit: str
    evidence_id: str
    source_locator: str

    @field_validator(
        "result_id", "case_id", "coordinate_unit", "unit", "evidence_id", "source_locator"
    )
    @classmethod
    def qoi_value_text_is_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("QoI value text must be nonblank")
        return stripped

    @field_validator("coordinate_value", "value")
    @classmethod
    def qoi_numbers_are_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("QoI values must be finite")
        return value


class QoIAnalysis(QualificationModel):
    qoi_contract_id: str
    qoi_name: str
    scientific_definition: str
    coordinate_name: str
    qualification_input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    scientific_input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    values: tuple[QoIValue, ...]
    overall_change: float | None
    trend: DiscreteTrend | None
    restrictions: tuple[str, ...]
    quantitative_reporting_allowed: bool

    @field_validator("qoi_contract_id", "qoi_name", "scientific_definition", "coordinate_name")
    @classmethod
    def analysis_text_is_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("analysis text must be nonblank")
        return stripped

    @field_validator("overall_change")
    @classmethod
    def overall_change_is_finite(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("overall change must be finite")
        return value


class V03ClaimCeiling(str, Enum):
    NO_NUMERICAL_CLAIM = "no-numerical-claim"
    DIRECTIONAL_COMPARISON = "directional-comparison"
    QUALIFIED_NUMERICAL_OBSERVATION = "qualified-numerical-observation"
    SUPPORTED_PHYSICAL_INTERPRETATION = "supported-physical-interpretation"


class ClaimCeilingDecision(QualificationModel):
    ceiling: V03ClaimCeiling
    reasons: tuple[str, ...]
    allowed_sentence_duties: tuple[str, ...]
    quantitative_reporting_allowed: bool
    qualification_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    analysis_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    scientific_input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("reasons", "allowed_sentence_duties")
    @classmethod
    def decision_text_is_nonblank_and_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in value)
        if not normalized or any(not item for item in normalized):
            raise ValueError("claim-ceiling text must be nonblank")
        if len(set(normalized)) != len(normalized):
            raise ValueError("claim-ceiling text must be unique")
        return normalized

    @model_validator(mode="after")
    def quantitative_flag_matches_ceiling(self) -> ClaimCeilingDecision:
        numerical = self.ceiling in {
            V03ClaimCeiling.QUALIFIED_NUMERICAL_OBSERVATION,
            V03ClaimCeiling.SUPPORTED_PHYSICAL_INTERPRETATION,
        }
        if self.quantitative_reporting_allowed != numerical:
            raise ValueError("quantitative reporting flag must match the claim ceiling")
        payload = self.model_dump(mode="python", exclude={"fingerprint"})
        expected = canonical_sha256(payload, domain=b"cfdpaper-v03-claim-ceiling-decision")
        if self.fingerprint != expected:
            raise ValueError("claim-ceiling fingerprint must match its canonical content")
        return self


class BoundedClaim(QualificationModel):
    claim_id: str
    text: str
    ceiling: V03ClaimCeiling
    evidence_ids: tuple[str, ...]
    numeric_backlink_ids: tuple[str, ...]

    @field_validator("claim_id", "text")
    @classmethod
    def bounded_claim_text_is_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("bounded claim text must be nonblank")
        return stripped


class CandidateFigurePanel(QualificationModel):
    panel_id: str
    encoding: Literal["discrete-marker-line"] = "discrete-marker-line"
    x_variable: str
    x_unit: str
    x_values: tuple[float, ...]
    y_variable: str
    y_definition: str
    y_unit: str
    case_order: tuple[str, ...]

    @field_validator("panel_id", "x_variable", "x_unit", "y_variable", "y_definition", "y_unit")
    @classmethod
    def panel_text_is_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("panel text must be nonblank")
        return stripped

    @field_validator("x_values")
    @classmethod
    def panel_coordinates_are_finite(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        if not value or any(not math.isfinite(item) for item in value):
            raise ValueError("panel coordinates must be finite and nonempty")
        return value

    @model_validator(mode="after")
    def panel_membership_is_exact(self) -> CandidateFigurePanel:
        if not self.case_order or len(self.case_order) != len(self.x_values):
            raise ValueError("panel cases and coordinates must be nonempty and aligned")
        if len(set(self.case_order)) != len(self.case_order):
            raise ValueError("panel case order must be unique")
        return self


class ParagraphDuty(QualificationModel):
    claim_id: str
    duty: str
    evidence_ids: tuple[str, ...]
    numeric_backlink_ids: tuple[str, ...]
    prohibited_inferences: tuple[str, ...]

    @field_validator("claim_id", "duty")
    @classmethod
    def paragraph_text_is_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("paragraph duty text must be nonblank")
        return stripped


class CandidateFigureContract(QualificationModel):
    figure_id: str
    qualification_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    analysis_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    scientific_input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    claim_ceiling_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    author: str
    primary_claim: BoundedClaim
    evidence_ids: tuple[str, ...]
    numeric_backlink_ids: tuple[str, ...]
    panels: tuple[CandidateFigurePanel, ...]
    paragraph_duty: ParagraphDuty
    caption_duty: str
    prohibited_inferences: tuple[str, ...]
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["candidate"] = "candidate"

    @field_validator("figure_id", "author", "caption_duty")
    @classmethod
    def candidate_figure_text_is_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("candidate figure text must be nonblank")
        return stripped

    @model_validator(mode="after")
    def candidate_is_one_discrete_bounded_panel(self) -> CandidateFigureContract:
        if len(self.panels) != 1:
            raise ValueError("V0.3 candidate figure requires exactly one panel")
        required = {
            "interpolation",
            "continuous optimum",
            "stability boundary",
            "unsampled prediction",
        }
        if set(self.prohibited_inferences) != required:
            raise ValueError("candidate figure must retain all prohibited inferences")
        if self.primary_claim.evidence_ids != self.evidence_ids:
            raise ValueError("primary claim evidence must match the figure evidence")
        if self.primary_claim.numeric_backlink_ids != self.numeric_backlink_ids:
            raise ValueError("primary claim backlinks must match the figure backlinks")
        if self.paragraph_duty.claim_id != self.primary_claim.claim_id:
            raise ValueError("paragraph duty must target the primary claim")
        if self.paragraph_duty.evidence_ids != self.evidence_ids:
            raise ValueError("paragraph duty evidence must match the candidate")
        if self.paragraph_duty.numeric_backlink_ids != self.numeric_backlink_ids:
            raise ValueError("paragraph duty backlinks must match the candidate")
        if self.paragraph_duty.prohibited_inferences != self.prohibited_inferences:
            raise ValueError("paragraph duty prohibited inferences must match the candidate")
        return self
