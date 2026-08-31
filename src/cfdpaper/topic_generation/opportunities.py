"""Domain-neutral discovery of evidence-bounded research opportunities."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from cfdpaper.contracts import ClaimRecord, ClaimStatus, EvidenceRecord
from cfdpaper.scientific import (
    CaseDefinition,
    ClaimCeiling,
    EvidenceMaturity,
    MaturityAssessment,
    QoICheck,
    QoIDefinition,
    TrendAssessment,
    TrendKind,
    assess_claim_ceiling,
    assess_conservation,
    assess_evidence_maturity,
    check_case_comparability,
    check_qoi_definition,
    convert_value,
    detect_trend,
    grade_convergence,
    unit_is_known,
    units_compatible,
)
from cfdpaper.topic_generation.canonical import canonical_json_bytes, canonical_sha256
from cfdpaper.topic_generation.models import GenerationModel, ScientificRelationFrame
from cfdpaper.topic_generation.snapshot import (
    CaseNumericalAssessmentInput,
    CaseSnapshot,
    EvidenceSnapshot,
    QoISnapshot,
    ScientificRecordSnapshot,
)

OpportunityPattern = Literal[
    "matched-comparison",
    "ordered-parameter-response",
    "coupled-association",
    "validation-robustness",
]
ComparabilityState = Literal["verified", "blocked", "unknown"]
OutputScope = Literal["manuscript-topic", "direction-only", "analysis-note", "missing-evidence"]
ParameterRole = Literal["varied", "controlled"]
TrendType = Literal[
    "monotonic-increasing",
    "monotonic-decreasing",
    "interior-peak",
    "interior-trough",
    "plateau",
    "mixed",
]

_MODEL_CONFIG = ConfigDict(
    extra="forbid",
    frozen=True,
    strict=True,
    validate_default=True,
    revalidate_instances="always",
)
_OPPORTUNITY_DOMAIN = b"cfdpaper-opportunity-v1"

_MATURITY_ORDER = {
    EvidenceMaturity.RAW: 0,
    EvidenceMaturity.SCREENED: 1,
    EvidenceMaturity.VERIFIED: 2,
    EvidenceMaturity.AUTHOR_APPROVED: 3,
}
_CEILING_ORDER = {
    ClaimCeiling.OBSERVATION: 0,
    ClaimCeiling.ASSOCIATION: 1,
    ClaimCeiling.MECHANISM: 2,
    ClaimCeiling.VALIDATION: 3,
    ClaimCeiling.ENGINEERING: 4,
}
_PATTERN_MIN_CASES = {
    "matched-comparison": 2,
    "ordered-parameter-response": 3,
    "coupled-association": 3,
    "validation-robustness": 2,
}
_RELATION_CLASS = {
    "matched-comparison": "difference",
    "ordered-parameter-response": "ordered-response",
    "coupled-association": "coupled-association",
    "validation-robustness": "robustness",
}
_PROHIBITED_INFERENCES = (
    "causation",
    "continuous optimum",
    "engineering operating boundary",
    "stable operating window",
    "unsampled continuity",
)


def _sorted_ids(value: Any, *, allow_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) for item in value):
        raise ValueError("IDs must be a list or tuple of strings")
    normalized = tuple(item.strip() for item in value)
    if any(not item for item in normalized) or len(set(normalized)) != len(normalized):
        raise ValueError("IDs must be nonblank and unique")
    if not allow_empty and not normalized:
        raise ValueError("IDs must not be empty")
    return tuple(sorted(normalized))


class UnitBinding(GenerationModel):
    model_config = _MODEL_CONFIG

    record_id: str = Field(min_length=1)
    record_kind: Literal["qoi", "parameter"]
    unit: str = Field(min_length=1)
    compatible: bool


class ScientificGap(GenerationModel):
    model_config = _MODEL_CONFIG

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ParameterBinding(GenerationModel):
    model_config = _MODEL_CONFIG

    parameter_id: str = Field(min_length=1)
    role: ParameterRole
    case_ids: tuple[str, ...] = Field(min_length=1)
    boundary_evidence_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("case_ids", "boundary_evidence_ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: Any) -> tuple[str, ...]:
        return _sorted_ids(value, allow_empty=False)


class OpportunitySemanticSignature(GenerationModel):
    model_config = _MODEL_CONFIG

    pattern: OpportunityPattern
    case_ids: tuple[str, ...]
    qoi_roles: tuple[str, ...]
    parameter_bindings: tuple[ParameterBinding, ...]
    trend_type: TrendType | None
    relation: ScientificRelationFrame
    validation_sensitivity_contrast_ids: tuple[str, ...]


class ResearchOpportunity(GenerationModel):
    model_config = _MODEL_CONFIG

    schema_version: Literal[1] = 1
    opportunity_id: str = Field(pattern=r"^opp-[0-9a-f]{16}$")
    pattern: OpportunityPattern
    case_ids: tuple[str, ...]
    current_case_ids: tuple[str, ...]
    qoi_ids: tuple[str, ...]
    primary_qoi_ids: tuple[str, ...]
    supporting_evidence_ids: tuple[str, ...]
    constraint_provenance_evidence_ids: tuple[str, ...]
    unit_bindings: tuple[UnitBinding, ...]
    comparability: ComparabilityState
    trend_type: TrendType | None
    relation: ScientificRelationFrame
    evidence_maturity: EvidenceMaturity
    claim_ceiling: ClaimCeiling
    candidate_eligible: bool
    defensible: bool
    output_scope: OutputScope
    gaps: tuple[ScientificGap, ...]
    prohibited_inferences: tuple[str, ...]
    rationale: str = Field(min_length=1)
    required_evidence_kinds: tuple[str, ...]
    parameter_ids: tuple[str, ...]
    varied_parameter_ids: tuple[str, ...]
    controlled_parameter_ids: tuple[str, ...]
    parameter_bindings: tuple[ParameterBinding, ...]
    passed_gate_count: int = Field(ge=0, le=6)
    independent_validation_linked: bool
    literature_gap_maturity: EvidenceMaturity
    semantic_signature: OpportunitySemanticSignature

    @field_validator(
        "case_ids",
        "current_case_ids",
        "qoi_ids",
        "primary_qoi_ids",
        "supporting_evidence_ids",
        "constraint_provenance_evidence_ids",
        "prohibited_inferences",
        "required_evidence_kinds",
        "parameter_ids",
        "varied_parameter_ids",
        "controlled_parameter_ids",
        mode="before",
    )
    @classmethod
    def normalize_ids(cls, value: Any) -> tuple[str, ...]:
        return _sorted_ids(value)

    @field_validator("parameter_bindings", mode="before")
    @classmethod
    def normalize_parameter_bindings(cls, value: Any) -> tuple[ParameterBinding, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("parameter bindings must be a list or tuple")
        bindings = tuple(ParameterBinding.model_validate(item, strict=True) for item in value)
        ids = [item.parameter_id for item in bindings]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate parameter binding")
        return tuple(sorted(bindings, key=lambda item: item.parameter_id))

    @field_validator("gaps", mode="before")
    @classmethod
    def normalize_gaps(cls, value: Any) -> tuple[ScientificGap, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("gaps must be a list or tuple")
        gaps = tuple(ScientificGap.model_validate(item, strict=True) for item in value)
        if len({item.code for item in gaps}) != len(gaps):
            raise ValueError("duplicate scientific gap code")
        return tuple(sorted(gaps, key=lambda item: item.code))

    @field_validator("unit_bindings", mode="before")
    @classmethod
    def normalize_units(cls, value: Any) -> tuple[UnitBinding, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("unit bindings must be a list or tuple")
        bindings = tuple(UnitBinding.model_validate(item, strict=True) for item in value)
        keys = [(item.record_kind, item.record_id) for item in bindings]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate unit binding")
        return tuple(sorted(bindings, key=lambda item: (item.record_kind, item.record_id)))

    @model_validator(mode="after")
    def validate_scientific_structure(self) -> ResearchOpportunity:
        if not set(self.current_case_ids).issubset(self.case_ids):
            raise ValueError("current cases must be a subset of assessed cases")
        if not set(self.primary_qoi_ids).issubset(self.qoi_ids):
            raise ValueError("primary QoIs must be a subset of all QoIs")
        if set(self.supporting_evidence_ids) & set(self.constraint_provenance_evidence_ids):
            raise ValueError("supporting and constraint evidence must be disjoint")
        varied = {item.parameter_id for item in self.parameter_bindings if item.role == "varied"}
        controlled = {
            item.parameter_id for item in self.parameter_bindings if item.role == "controlled"
        }
        if varied & controlled:
            raise ValueError("parameter roles cannot overlap")
        if tuple(sorted(varied | controlled)) != self.parameter_ids:
            raise ValueError("parameter binding union does not match parameter IDs")
        if tuple(sorted(varied)) != self.varied_parameter_ids:
            raise ValueError("varied parameter IDs do not match bindings")
        if tuple(sorted(controlled)) != self.controlled_parameter_ids:
            raise ValueError("controlled parameter IDs do not match bindings")
        if self.defensible and not self.candidate_eligible:
            raise ValueError("a defensible opportunity must be candidate eligible")
        if self.defensible and self.output_scope != "manuscript-topic":
            raise ValueError("defensible opportunities require manuscript-topic scope")
        if not self.candidate_eligible and self.output_scope != "missing-evidence":
            raise ValueError("candidate-ineligible opportunities require missing-evidence scope")
        if (
            self.candidate_eligible
            and not self.defensible
            and self.output_scope
            not in {
                "direction-only",
                "analysis-note",
            }
        ):
            raise ValueError("non-defensible candidates require a restricted scope")
        if self.relation.relation_class != _RELATION_CLASS[self.pattern]:
            raise ValueError("pattern and relation class do not match")
        if self.semantic_signature.pattern != self.pattern:
            raise ValueError("signature pattern does not match")
        if self.semantic_signature.case_ids != self.case_ids:
            raise ValueError("signature cases do not match")
        if self.semantic_signature.parameter_bindings != self.parameter_bindings:
            raise ValueError("signature parameter bindings do not match")
        if self.semantic_signature.trend_type != self.trend_type:
            raise ValueError("signature trend does not match")
        if self.semantic_signature.relation != self.relation:
            raise ValueError("signature relation does not match")
        expected_relation_shape = {
            "matched-comparison": (
                {"increase", "decrease", "difference-only"},
                "variant-vs-reference",
                "pairwise",
            ),
            "ordered-parameter-response": (
                {"increase", "decrease", "non-monotonic", "plateau"},
                "parameter-ascending",
                "sampled-series-only",
            ),
            "coupled-association": (
                {"positive", "negative", "not-applicable"},
                "symmetric",
                "sampled-cases-only",
            ),
            "validation-robustness": (
                {"not-applicable"},
                "not-applicable",
                "validation-set-only",
            ),
        }[self.pattern]
        allowed_polarities, direction, quantifier = expected_relation_shape
        if (
            self.relation.polarity not in allowed_polarities
            or self.relation.comparison_direction != direction
            or self.relation.quantifier != quantifier
        ):
            raise ValueError("pattern and locked relation semantics do not match")
        for binding in self.parameter_bindings:
            if not set(binding.case_ids).issubset(self.current_case_ids):
                raise ValueError("parameter binding cases must resolve to current cases")
        expected_id = (
            "opp-" + canonical_sha256(self.semantic_signature, domain=_OPPORTUNITY_DOMAIN)[:16]
        )
        if self.opportunity_id != expected_id:
            raise ValueError("opportunity ID does not match semantic signature")
        return self


class OpportunityDiscoveryResult(GenerationModel):
    model_config = _MODEL_CONFIG

    schema_version: Literal[1] = 1
    opportunities: tuple[ResearchOpportunity, ...]
    gaps: tuple[str, ...]

    @field_validator("opportunities", mode="before")
    @classmethod
    def normalize_opportunities(cls, value: Any) -> tuple[ResearchOpportunity, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("opportunities must be a list or tuple")
        items = tuple(ResearchOpportunity.model_validate(item, strict=True) for item in value)
        ids = [item.opportunity_id for item in items]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate opportunity ID")
        return tuple(sorted(items, key=lambda item: item.opportunity_id))

    @field_validator("gaps", mode="before")
    @classmethod
    def normalize_gaps(cls, value: Any) -> tuple[str, ...]:
        return _sorted_ids(value)


@dataclass(frozen=True, slots=True)
class _QoIScience:
    qoi: QoISnapshot
    check: QoICheck
    basic_valid: bool
    current_primary: tuple[EvidenceSnapshot, ...]
    constrained_evidence_ids: tuple[str, ...]
    gaps: tuple[ScientificGap, ...]


@dataclass(frozen=True, slots=True)
class _CaseScience:
    case: CaseSnapshot
    assessment: CaseNumericalAssessmentInput | None
    convergence: Any
    conservation: Any
    supporting_evidence_ids: tuple[str, ...]
    evidence_gaps: tuple[ScientificGap, ...]


@dataclass(frozen=True, slots=True)
class _ParameterContext:
    bindings: tuple[ParameterBinding, ...]
    values: Mapping[str, Mapping[str, tuple[float, str]]]
    gaps: tuple[ScientificGap, ...]


@dataclass(frozen=True, slots=True)
class _QoISeries:
    normalized_name: str
    qois: tuple[_QoIScience, ...]
    values_by_case: Mapping[str, float] | None
    gap: ScientificGap | None


def _gap(code: str, message: str) -> ScientificGap:
    return ScientificGap(code=code, message=message)


def _qoi_checks(snapshot: ScientificRecordSnapshot) -> dict[str, _QoIScience]:
    definitions = {item.qoi_id: item for item in snapshot.qoi_definition_assessments}
    evidence = {item.evidence_id: item for item in snapshot.evidence}
    checks: dict[str, _QoIScience] = {}
    for qoi in snapshot.qois:
        definition = definitions.get(qoi.qoi_id)
        gaps: list[ScientificGap] = []
        if definition is None:
            check = check_qoi_definition(QoIDefinition(qoi.name, qoi.unit))
            gaps.append(
                _gap(
                    f"qoi-structured-definition-missing:{qoi.qoi_id}",
                    "A structured QoI definition is required; human free text is not parsed.",
                )
            )
            definition_evidence_ids: tuple[str, ...] = ()
            compatible = False
            same_name = False
        else:
            check = check_qoi_definition(
                QoIDefinition(
                    name=definition.name,
                    unit=definition.unit,
                    formula=definition.formula,
                    spatial_scope=definition.spatial_scope,
                    reduction=definition.reduction,
                    temporal_scope=definition.temporal_scope,
                )
            )
            definition_evidence_ids = definition.evidence_ids
            compatible = units_compatible(qoi.unit, definition.unit)
            same_name = qoi.name.strip().casefold() == definition.name.strip().casefold()
            if not compatible:
                gaps.append(
                    _gap(
                        f"qoi-unit-incompatible:{qoi.qoi_id}",
                        "The QoI record and structured definition use incompatible units.",
                    )
                )
            if not same_name:
                gaps.append(
                    _gap(
                        f"qoi-name-mismatch:{qoi.qoi_id}",
                        "The QoI record and structured definition names do not match.",
                    )
                )
        if qoi.stale:
            gaps.append(_gap(f"qoi-source-stale:{qoi.qoi_id}", "The QoI source is stale."))
        if qoi.status not in {"reported", "derived"}:
            gaps.append(
                _gap(f"qoi-status-{qoi.status}:{qoi.qoi_id}", "The QoI status is not usable.")
            )
        numeric = isinstance(qoi.value, float) and math.isfinite(qoi.value)
        if not numeric:
            gaps.append(_gap(f"qoi-value-invalid:{qoi.qoi_id}", "The QoI value is not finite."))
        if not unit_is_known(qoi.unit):
            gaps.append(_gap(f"qoi-unit-unknown:{qoi.qoi_id}", "The QoI unit is unknown."))
        current: list[EvidenceSnapshot] = []
        constrained: list[str] = []
        for evidence_id in definition_evidence_ids:
            record = evidence.get(evidence_id)
            bound = bool(
                record
                and definition
                and record.kind == "qoi"
                and record.source_uri == definition.source_uri
                and record.source_hash == definition.source_hash
                and record.locator == definition.source_locator
            )
            if record is None:
                gaps.append(
                    _gap(
                        f"qoi-primary-evidence-missing:{qoi.qoi_id}:{evidence_id}",
                        "A structured QoI evidence reference does not resolve.",
                    )
                )
            elif record.stale or not bound:
                constrained.append(record.evidence_id)
                gaps.append(
                    _gap(
                        f"qoi-primary-evidence-blocked:{qoi.qoi_id}:{evidence_id}",
                        "QoI evidence is stale or not fully source-bound.",
                    )
                )
            else:
                current.append(record)
        if not current:
            gaps.append(
                _gap(
                    f"qoi-current-primary-evidence-missing:{qoi.qoi_id}",
                    "No current fully bound primary QoI evidence is available.",
                )
            )
        basic_valid = bool(
            definition
            and check.valid
            and compatible
            and same_name
            and not qoi.stale
            and qoi.status in {"reported", "derived"}
            and numeric
            and unit_is_known(qoi.unit)
        )
        if not basic_valid:
            constrained.extend(item.evidence_id for item in current)
            current = []
        checks[qoi.qoi_id] = _QoIScience(
            qoi=qoi,
            check=check,
            basic_valid=basic_valid,
            current_primary=tuple(sorted(current, key=lambda item: item.evidence_id)),
            constrained_evidence_ids=tuple(sorted(set(constrained))),
            gaps=tuple(sorted(gaps, key=lambda item: item.code)),
        )
    return checks


def _case_science(
    snapshot: ScientificRecordSnapshot,
    qoi_checks: Mapping[str, _QoIScience],
) -> dict[str, _CaseScience]:
    del qoi_checks
    assessments = {item.case_id: item for item in snapshot.assessments.cases}
    evidence_by_id = {item.evidence_id: item for item in snapshot.evidence}
    result: dict[str, _CaseScience] = {}
    for case in snapshot.cases:
        assessment = assessments.get(case.case_id)
        if assessment is None:
            convergence = grade_convergence({}, {}, qoi_relative_span=None)
            conservation = assess_conservation(0.0, 0.0)
            supporting_evidence_ids: tuple[str, ...] = ()
            evidence_gaps = tuple(
                _gap(
                    f"assessment-evidence-missing:{kind}:{case.case_id}",
                    f"The {kind} assessment evidence is not explicitly bound to this case.",
                )
                for kind in ("case", "convergence", "conservation")
            )
        else:
            convergence = grade_convergence(
                {item.name: item.value for item in assessment.residuals},
                {item.name: item.value for item in assessment.residual_targets},
                qoi_relative_span=assessment.qoi_relative_span,
            )
            conservation = assess_conservation(
                assessment.conservation_inflow,
                assessment.conservation_outflow,
                tolerance=assessment.conservation_tolerance,
            )
            support: list[str] = []
            gaps: list[ScientificGap] = []
            for kind, evidence_ids in (
                ("case", assessment.case_evidence_ids),
                ("convergence", assessment.convergence_evidence_ids),
                ("conservation", assessment.conservation_evidence_ids),
            ):
                if not evidence_ids:
                    gaps.append(
                        _gap(
                            f"assessment-evidence-missing:{kind}:{case.case_id}",
                            f"The {kind} assessment evidence is not explicitly bound to this case.",
                        )
                    )
                    continue
                for evidence_id in evidence_ids:
                    evidence = evidence_by_id.get(evidence_id)
                    if (
                        evidence is None
                        or evidence.kind != kind
                        or evidence.stale
                        or evidence.source_uri != case.source_uri
                        or evidence.source_hash != case.source_hash
                    ):
                        gaps.append(
                            _gap(
                                f"assessment-evidence-blocked:{kind}:{case.case_id}:{evidence_id}",
                                "Assessment evidence must be current, have the declared kind, and "
                                "share the explicitly bound case source version.",
                            )
                        )
                    else:
                        support.append(evidence_id)
            supporting_evidence_ids = tuple(sorted(set(support)))
            evidence_gaps = tuple(sorted(gaps, key=lambda item: item.code))
        result[case.case_id] = _CaseScience(
            case,
            assessment,
            convergence,
            conservation,
            supporting_evidence_ids,
            evidence_gaps,
        )
    return result


def _parameter_context(snapshot: ScientificRecordSnapshot) -> _ParameterContext:
    current_case_ids = {case.case_id for case in snapshot.cases if not case.stale}
    values: dict[str, dict[str, tuple[float, str]]] = defaultdict(dict)
    roles: dict[str, set[str]] = defaultdict(set)
    boundary_evidence_ids: dict[str, list[str]] = defaultdict(list)
    boundary_evidence = tuple(item for item in snapshot.evidence if item.kind == "boundary")
    gaps: list[ScientificGap] = []
    for boundary in snapshot.boundaries:
        if boundary.stale or boundary.case_id not in current_case_ids:
            continue
        role_text = boundary.boundary_type.strip().lower()
        role: ParameterRole | None = None
        if role_text in {"parameter:varied", "parameter-varied", "varied-parameter"}:
            role = "varied"
        elif role_text in {
            "parameter:controlled",
            "parameter-controlled",
            "controlled-parameter",
        }:
            role = "controlled"
        if role is None:
            continue
        exact_evidence = tuple(
            item
            for item in boundary_evidence
            if item.source_uri == boundary.source_uri
            and item.source_hash == boundary.source_hash
            and item.locator == boundary.locator
        )
        if not exact_evidence:
            gaps.append(
                _gap(
                    f"boundary-evidence-missing-or-mismatched:{boundary.boundary_id}",
                    "A parameter boundary lacks exactly source-bound boundary evidence.",
                )
            )
            continue
        if len(exact_evidence) != 1:
            gaps.append(
                _gap(
                    f"boundary-evidence-duplicate:{boundary.boundary_id}",
                    "A parameter boundary resolves to more than one boundary evidence record.",
                )
            )
            continue
        bound_evidence = exact_evidence[0]
        if bound_evidence.stale:
            gaps.append(
                _gap(
                    f"boundary-evidence-stale:{boundary.boundary_id}:{bound_evidence.evidence_id}",
                    "A parameter boundary is bound only to stale evidence.",
                )
            )
            continue
        for parameter_id, raw_value in boundary.values.items():
            unit = boundary.units.get(parameter_id)
            if (
                not isinstance(raw_value, (int, float))
                or isinstance(raw_value, bool)
                or not math.isfinite(float(raw_value))
                or not unit_is_known(unit)
            ):
                gaps.append(
                    _gap(
                        f"parameter-binding-invalid:{parameter_id}:{boundary.boundary_id}",
                        "A declared parameter lacks a finite value or known unit.",
                    )
                )
                continue
            roles[parameter_id].add(role)
            values[parameter_id][boundary.case_id] = (float(raw_value), str(unit))
            boundary_evidence_ids[parameter_id].append(bound_evidence.evidence_id)
    bindings: list[ParameterBinding] = []
    for parameter_id in sorted(roles):
        if len(roles[parameter_id]) != 1:
            gaps.append(
                _gap(
                    f"parameter-role-conflict:{parameter_id}",
                    "A parameter cannot be both varied and controlled.",
                )
            )
            continue
        if set(values[parameter_id]) != current_case_ids:
            gaps.append(
                _gap(
                    f"parameter-binding-incomplete:{parameter_id}",
                    "The parameter is not bound to every current case.",
                )
            )
            continue
        role = next(iter(roles[parameter_id]))
        ordered_values = tuple(
            values[parameter_id][case_id] for case_id in sorted(current_case_ids)
        )
        reference_unit = ordered_values[0][1]
        if any(not units_compatible(reference_unit, unit) for _, unit in ordered_values[1:]):
            gaps.append(
                _gap(
                    f"parameter-unit-incompatible:{parameter_id}",
                    "A declared parameter uses incompatible units across cases.",
                )
            )
            continue
        normalized_values = tuple(
            convert_value(value, unit, reference_unit) for value, unit in ordered_values
        )
        if role == "varied" and len(set(normalized_values)) < 2:
            gaps.append(
                _gap(
                    f"varied-parameter-not-varying:{parameter_id}",
                    "A declared varied parameter has no discrete sampled contrast.",
                )
            )
            continue
        bindings.append(
            ParameterBinding(
                parameter_id=parameter_id,
                role=role,
                case_ids=tuple(sorted(current_case_ids)),
                boundary_evidence_ids=tuple(sorted(boundary_evidence_ids[parameter_id])),
            )
        )
    if not any(item.role == "varied" for item in bindings):
        gaps.append(
            _gap(
                "comparison-factor-missing",
                "No fully traceable declared varied parameter is available.",
            )
        )
    return _ParameterContext(
        bindings=tuple(bindings),
        values={key: dict(value) for key, value in values.items()},
        gaps=tuple(sorted(gaps, key=lambda item: item.code)),
    )


def _case_definition(
    case: CaseSnapshot,
    parameters: _ParameterContext,
) -> CaseDefinition:
    conditions = {
        parameter_id: by_case[case.case_id]
        for parameter_id, by_case in parameters.values.items()
        if case.case_id in by_case
    }
    models = {
        key: value
        for key, value in {"solver": case.solver, "solver-version": case.solver_version}.items()
        if value is not None
    }
    return CaseDefinition(case.case_id, conditions, models)


def _comparability(
    cases: Sequence[CaseSnapshot],
    parameters: _ParameterContext,
) -> tuple[ComparabilityState, tuple[ScientificGap, ...]]:
    unresolved = tuple(
        gap
        for gap in parameters.gaps
        if gap.code.startswith(
            (
                "parameter-binding-",
                "parameter-role-",
                "parameter-unit-",
            )
        )
    )
    if unresolved:
        return (
            "unknown",
            (
                _gap(
                    "case-comparability-unverified",
                    "Controlled-condition provenance is incomplete or contradictory.",
                ),
            ),
        )
    controlled = tuple(
        item.parameter_id for item in parameters.bindings if item.role == "controlled"
    )
    blockers: list[str] = []
    for reference, candidate in zip(cases, cases[1:], strict=False):
        reference_definition = _case_definition(reference, parameters)
        candidate_definition = _case_definition(candidate, parameters)
        result = check_case_comparability(
            CaseDefinition(
                reference_definition.case_id,
                {
                    name: reference_definition.conditions[name]
                    for name in controlled
                    if name in reference_definition.conditions
                },
                reference_definition.models,
            ),
            CaseDefinition(
                candidate_definition.case_id,
                {
                    name: candidate_definition.conditions[name]
                    for name in controlled
                    if name in candidate_definition.conditions
                },
                candidate_definition.models,
            ),
        )
        blockers.extend(result.blockers)
    if blockers:
        return (
            "blocked",
            (
                _gap(
                    "case-comparability-unverified",
                    "; ".join(sorted(set(blockers))),
                ),
            ),
        )
    return "verified", ()


def _controlling_maturity(
    base: MaturityAssessment,
    primary_evidence: tuple[EvidenceRecord, ...],
) -> MaturityAssessment:
    current = tuple(item for item in primary_evidence if not item.stale)
    evidence_level = min(
        (EvidenceMaturity(item.maturity) for item in current),
        key=_MATURITY_ORDER.__getitem__,
        default=EvidenceMaturity.RAW,
    )
    level = min((base.level, evidence_level), key=_MATURITY_ORDER.__getitem__)
    return replace(
        base,
        level=level,
        approved_by=base.approved_by if level == EvidenceMaturity.AUTHOR_APPROVED else None,
    )


def _linked_supported_claims(
    claims: tuple[ClaimRecord, ...],
    current_supporting_evidence_ids: tuple[str, ...],
) -> tuple[ClaimRecord, ...]:
    current_ids = set(current_supporting_evidence_ids)
    return tuple(
        sorted(
            (
                claim
                for claim in claims
                if claim.status == ClaimStatus.SUPPORTED
                and bool(claim.evidence_ids)
                and set(claim.evidence_ids).issubset(current_ids)
            ),
            key=lambda claim: claim.claim_id,
        )
    )


def _effective_ceiling(
    *,
    pattern: str,
    maturity: MaturityAssessment,
    supporting_claims: tuple[ClaimRecord, ...],
    independent_validation: bool,
    engineering_evidence: bool,
) -> ClaimCeiling:
    raw = assess_claim_ceiling(
        maturity=maturity,
        independent_validation=independent_validation,
        engineering_evidence=engineering_evidence,
    ).ceiling
    claim_cap = max(
        (ClaimCeiling(item.ceiling) for item in supporting_claims),
        key=lambda item: _CEILING_ORDER[item],
        default=ClaimCeiling.ASSOCIATION,
    )
    if pattern == "coupled-association":
        pattern_cap = ClaimCeiling.ASSOCIATION
    elif pattern in {"matched-comparison", "ordered-parameter-response"}:
        pattern_cap = (
            ClaimCeiling.MECHANISM
            if _CEILING_ORDER[claim_cap] >= _CEILING_ORDER[ClaimCeiling.MECHANISM]
            else ClaimCeiling.ASSOCIATION
        )
    else:
        pattern_cap = claim_cap
    return min((raw, claim_cap, pattern_cap), key=lambda item: _CEILING_ORDER[item])


def _maturity_for_opportunity(
    *,
    cases: Sequence[CaseSnapshot],
    case_science: Mapping[str, _CaseScience],
    qoi_science: Sequence[_QoIScience],
    comparable: bool,
    trend: TrendAssessment | None,
    primary_evidence: tuple[EvidenceSnapshot, ...],
) -> MaturityAssessment:
    qoi_check = QoICheck(
        valid=all(item.check.valid and item.basic_valid for item in qoi_science),
        missing=tuple(sorted({missing for item in qoi_science for missing in item.check.missing})),
    )
    assessments = []
    for case in cases:
        science = case_science[case.case_id]
        assessments.append(
            assess_evidence_maturity(
                has_provenance=bool(case.source_hash) and not case.stale,
                comparable=comparable,
                convergence=science.convergence,
                conservation=science.conservation,
                qoi=qoi_check,
                trend=trend,
            )
        )
    base_level = min(
        (item.level for item in assessments),
        key=_MATURITY_ORDER.__getitem__,
        default=EvidenceMaturity.RAW,
    )
    base = MaturityAssessment(
        level=base_level,
        blockers=tuple(sorted({blocker for item in assessments for blocker in item.blockers})),
        approval_rejected=any(item.approval_rejected for item in assessments),
        trend_contradiction=any(item.trend_contradiction for item in assessments),
        trend_claim_blocked=any(item.trend_claim_blocked for item in assessments),
    )
    return _controlling_maturity(base, tuple(primary_evidence))


def _evidence_for_qois(
    qoi_science: Sequence[_QoIScience],
) -> tuple[tuple[EvidenceSnapshot, ...], tuple[str, ...], tuple[ScientificGap, ...]]:
    current = {item.evidence_id: item for qoi in qoi_science for item in qoi.current_primary}
    constrained = {
        evidence_id for qoi in qoi_science for evidence_id in qoi.constrained_evidence_ids
    }
    gaps = {gap.code: gap for qoi in qoi_science for gap in qoi.gaps}
    return (
        tuple(current[key] for key in sorted(current)),
        tuple(sorted(constrained - set(current))),
        tuple(gaps[key] for key in sorted(gaps)),
    )


def _relation_for_ordered(trend: TrendAssessment) -> ScientificRelationFrame:
    polarity = {
        TrendKind.MONOTONIC_INCREASING: "increase",
        TrendKind.MONOTONIC_DECREASING: "decrease",
        TrendKind.INTERIOR_PEAK: "non-monotonic",
        TrendKind.INTERIOR_TROUGH: "non-monotonic",
        TrendKind.PLATEAU: "plateau",
        TrendKind.MIXED: "non-monotonic",
    }[trend.kind]
    return ScientificRelationFrame(
        relation_class="ordered-response",
        polarity=polarity,
        comparison_direction="parameter-ascending",
        quantifier="sampled-series-only",
    )


def _build_opportunity(
    *,
    snapshot: ScientificRecordSnapshot,
    pattern: OpportunityPattern,
    cases: Sequence[CaseSnapshot],
    qoi_science: Sequence[_QoIScience],
    primary_qoi_ids: tuple[str, ...],
    parameters: _ParameterContext,
    comparability: ComparabilityState,
    relation: ScientificRelationFrame,
    trend: TrendAssessment | None,
    case_science: Mapping[str, _CaseScience],
    extra_gaps: Iterable[ScientificGap] = (),
    validation_ids: tuple[str, ...] = (),
    sensitivity_ids: tuple[str, ...] = (),
    engineering_ids: tuple[str, ...] = (),
) -> ResearchOpportunity:
    current_primary, constrained, qoi_gaps = _evidence_for_qois(qoi_science)
    evidence_by_id = {item.evidence_id: item for item in snapshot.evidence}
    parameter_evidence_ids = {
        evidence_id
        for binding in parameters.bindings
        for evidence_id in binding.boundary_evidence_ids
    }
    assessment_evidence_ids = {
        evidence_id
        for case in cases
        for evidence_id in case_science[case.case_id].supporting_evidence_ids
    }
    assessment_gaps = [gap for case in cases for gap in case_science[case.case_id].evidence_gaps]
    current_primary_available = bool(current_primary)
    qoi_basic = all(item.basic_valid for item in qoi_science)
    linked_extra = tuple(
        evidence_by_id[item]
        for item in sorted(set((*validation_ids, *sensitivity_ids, *engineering_ids)))
        if item in evidence_by_id and not evidence_by_id[item].stale
    )
    all_support = {
        item.evidence_id: item
        for item in (*current_primary, *linked_extra)
        if item.evidence_id not in parameter_evidence_ids | assessment_evidence_ids
    }
    all_support.update(
        {
            evidence_id: evidence_by_id[evidence_id]
            for evidence_id in sorted(parameter_evidence_ids | assessment_evidence_ids)
            if evidence_id in evidence_by_id
        }
    )
    if not (current_primary_available and qoi_basic):
        all_support = {}
    primary = tuple(all_support[key] for key in sorted(all_support))
    supporting_ids = tuple(item.evidence_id for item in primary)
    maturity = _maturity_for_opportunity(
        cases=cases,
        case_science=case_science,
        qoi_science=qoi_science,
        comparable=comparability == "verified",
        trend=trend,
        primary_evidence=primary,
    )
    supporting_claims = _linked_supported_claims(snapshot.claims, supporting_ids)
    constrained_ids = set(constrained)
    independent_validation = bool(validation_ids) and all(
        item in all_support for item in validation_ids
    )
    engineering_evidence = bool(engineering_ids) and all(
        item in all_support for item in engineering_ids
    )
    ceiling = _effective_ceiling(
        pattern=pattern,
        maturity=maturity,
        supporting_claims=supporting_claims,
        independent_validation=independent_validation,
        engineering_evidence=engineering_evidence,
    )
    varied = tuple(item.parameter_id for item in parameters.bindings if item.role == "varied")
    controlled = tuple(
        item.parameter_id for item in parameters.bindings if item.role == "controlled"
    )
    gap_map = {
        gap.code: gap for gap in (*parameters.gaps, *qoi_gaps, *assessment_gaps, *extra_gaps)
    }
    linked_claim_ids = {claim.claim_id for claim in supporting_claims}
    for claim in snapshot.claims:
        if claim.claim_id in linked_claim_ids:
            continue
        if claim.status != ClaimStatus.SUPPORTED:
            code = f"claim-status-blocked:{claim.claim_id}:{claim.status.value}"
            gap_map[code] = _gap(code, "Only supported claims can raise the claim ceiling.")
        else:
            code = f"claim-evidence-not-fully-current:{claim.claim_id}"
            gap_map[code] = _gap(
                code,
                "The supported claim is not fully bound to current supporting evidence.",
            )
        for evidence_id in claim.evidence_ids:
            record = evidence_by_id.get(evidence_id)
            if record is None:
                code = f"claim-evidence-unresolved:{claim.claim_id}:{evidence_id}"
                gap_map[code] = _gap(code, "A claim evidence reference does not resolve.")
            elif evidence_id not in supporting_ids:
                constrained_ids.add(evidence_id)
    for blocker in maturity.blockers:
        code = "maturity-blocker:" + blocker.lower().replace(" ", "-")
        gap_map[code] = _gap(code, blocker)
    traceable_parameters = bool(varied) and not any(
        code.startswith("parameter-") or code == "comparison-factor-missing" for code in gap_map
    )
    candidate_eligible = traceable_parameters and current_primary_available and qoi_basic
    defensible = bool(
        candidate_eligible
        and comparability == "verified"
        and maturity.level in {EvidenceMaturity.VERIFIED, EvidenceMaturity.AUTHOR_APPROVED}
        and not assessment_gaps
    )
    output_scope: OutputScope
    if defensible:
        output_scope = "manuscript-topic"
    elif candidate_eligible:
        output_scope = "direction-only"
    else:
        output_scope = "missing-evidence"
    case_ids = tuple(sorted(case.case_id for case in cases))
    qoi_ids = tuple(sorted(item.qoi.qoi_id for item in qoi_science))
    contrast_ids = tuple(sorted(set((*validation_ids, *sensitivity_ids))))
    signature = OpportunitySemanticSignature(
        pattern=pattern,
        case_ids=case_ids,
        qoi_roles=tuple(
            [
                *(f"primary:{item}" for item in primary_qoi_ids),
                *(f"secondary:{item}" for item in qoi_ids if item not in primary_qoi_ids),
            ]
        ),
        parameter_bindings=parameters.bindings,
        trend_type=trend.kind.value if trend else None,
        relation=relation,
        validation_sensitivity_contrast_ids=contrast_ids,
    )
    opportunity_id = "opp-" + canonical_sha256(signature, domain=_OPPORTUNITY_DOMAIN)[:16]
    passed_gate_count = sum(
        (
            traceable_parameters,
            qoi_basic,
            current_primary_available,
            comparability == "verified",
            all(case_science[item.case_id].convergence.grade.value == "strong" for item in cases),
            all(case_science[item.case_id].conservation.passes for item in cases),
        )
    )
    unit_bindings = tuple(
        UnitBinding(
            record_id=item.qoi.qoi_id,
            record_kind="qoi",
            unit=item.qoi.unit or "unknown",
            compatible=item.basic_valid,
        )
        for item in qoi_science
    ) + tuple(
        UnitBinding(
            record_id=item.parameter_id,
            record_kind="parameter",
            unit=next(iter(parameters.values[item.parameter_id].values()))[1],
            compatible=True,
        )
        for item in parameters.bindings
    )
    rationale = (
        f"{pattern} over {len(case_ids)} discrete cases with structured QoI and parameter "
        f"provenance; claim strength is capped at {ceiling.value}."
    )
    return ResearchOpportunity(
        opportunity_id=opportunity_id,
        pattern=pattern,
        case_ids=case_ids,
        current_case_ids=tuple(sorted(case.case_id for case in cases if not case.stale)),
        qoi_ids=qoi_ids,
        primary_qoi_ids=primary_qoi_ids,
        supporting_evidence_ids=supporting_ids,
        constraint_provenance_evidence_ids=tuple(sorted(constrained_ids - set(supporting_ids))),
        unit_bindings=unit_bindings,
        comparability=comparability,
        trend_type=trend.kind.value if trend else None,
        relation=relation,
        evidence_maturity=maturity.level,
        claim_ceiling=ceiling,
        candidate_eligible=candidate_eligible,
        defensible=defensible,
        output_scope=output_scope,
        gaps=tuple(gap_map.values()),
        prohibited_inferences=_PROHIBITED_INFERENCES,
        rationale=rationale,
        required_evidence_kinds=("boundary", "case", "conservation", "convergence", "qoi"),
        parameter_ids=tuple(sorted((*varied, *controlled))),
        varied_parameter_ids=varied,
        controlled_parameter_ids=controlled,
        parameter_bindings=parameters.bindings,
        passed_gate_count=passed_gate_count,
        independent_validation_linked=independent_validation,
        literature_gap_maturity=EvidenceMaturity.RAW,
        semantic_signature=signature,
    )


def _qoi_groups(
    qoi_checks: Mapping[str, _QoIScience],
) -> dict[str, _QoISeries]:
    grouped: dict[str, list[_QoIScience]] = defaultdict(list)
    for science in qoi_checks.values():
        grouped[science.qoi.name.strip().casefold()].append(science)
    series: dict[str, _QoISeries] = {}
    for normalized_name in sorted(grouped):
        qois = tuple(sorted(grouped[normalized_name], key=lambda item: item.qoi.case_id))
        values_by_case: dict[str, float] | None = None
        gap: ScientificGap | None = None
        if all(isinstance(item.qoi.value, float) for item in qois):
            reference_unit = qois[0].qoi.unit
            if not all(units_compatible(reference_unit, item.qoi.unit) for item in qois):
                gap = _gap(
                    f"qoi-series-unit-incompatible:{normalized_name}",
                    "A cross-case QoI series contains dimensionally incompatible units.",
                )
            elif reference_unit is not None:
                values_by_case = {
                    item.qoi.case_id: convert_value(
                        float(item.qoi.value), str(item.qoi.unit), reference_unit
                    )
                    for item in qois
                }
        series[normalized_name] = _QoISeries(
            normalized_name=normalized_name,
            qois=qois,
            values_by_case=values_by_case,
            gap=gap,
        )
    return series


def _matched_comparisons(
    snapshot: ScientificRecordSnapshot,
    case_science: Mapping[str, _CaseScience],
    parameters: _ParameterContext,
    qoi_series: Mapping[str, _QoISeries],
) -> list[ResearchOpportunity]:
    cases = tuple(case for case in snapshot.cases if not case.stale)
    if len(cases) != _PATTERN_MIN_CASES["matched-comparison"]:
        return []
    comparability, comparison_gaps = _comparability(cases, parameters)
    opportunities = []
    for series in qoi_series.values():
        group = series.qois
        if {item.qoi.case_id for item in group} != {case.case_id for case in cases}:
            continue
        if series.values_by_case is None:
            continue
        values = tuple(series.values_by_case[case.case_id] for case in cases)
        polarity = "difference-only"
        if comparability == "verified":
            if values[1] > values[0]:
                polarity = "increase"
            elif values[1] < values[0]:
                polarity = "decrease"
        relation = ScientificRelationFrame(
            relation_class="difference",
            polarity=polarity,
            comparison_direction="variant-vs-reference",
            quantifier="pairwise",
        )
        opportunities.append(
            _build_opportunity(
                snapshot=snapshot,
                pattern="matched-comparison",
                cases=cases,
                qoi_science=group,
                primary_qoi_ids=tuple(sorted(item.qoi.qoi_id for item in group)),
                parameters=parameters,
                comparability=comparability,
                relation=relation,
                trend=None,
                case_science=case_science,
                extra_gaps=comparison_gaps,
            )
        )
    return opportunities


def _ordered_responses(
    snapshot: ScientificRecordSnapshot,
    case_science: Mapping[str, _CaseScience],
    parameters: _ParameterContext,
    qoi_series: Mapping[str, _QoISeries],
) -> list[ResearchOpportunity]:
    cases = tuple(case for case in snapshot.cases if not case.stale)
    varied = tuple(item for item in parameters.bindings if item.role == "varied")
    if len(cases) < _PATTERN_MIN_CASES["ordered-parameter-response"] or len(varied) != 1:
        return []
    comparability, comparison_gaps = _comparability(cases, parameters)
    parameter_id = varied[0].parameter_id
    by_case = parameters.values[parameter_id]
    reference_unit = by_case[cases[0].case_id][1]
    ordered_cases = tuple(
        sorted(
            cases,
            key=lambda case: convert_value(
                by_case[case.case_id][0], by_case[case.case_id][1], reference_unit
            ),
        )
    )
    x = tuple(
        convert_value(by_case[case.case_id][0], by_case[case.case_id][1], reference_unit)
        for case in ordered_cases
    )
    if len(set(x)) != len(x):
        comparison_gaps = (
            *comparison_gaps,
            _gap(
                f"varied-parameter-not-strictly-ordered:{parameter_id}",
                "The declared varied parameter is not strictly ordered.",
            ),
        )
        return []
    opportunities = []
    for series in qoi_series.values():
        group = series.qois
        by_qoi_case = {item.qoi.case_id: item for item in group}
        if set(by_qoi_case) != {case.case_id for case in cases}:
            continue
        if series.values_by_case is None:
            continue
        ordered_qois = tuple(by_qoi_case[case.case_id] for case in ordered_cases)
        trend = detect_trend(
            x,
            tuple(series.values_by_case[item.qoi.case_id] for item in ordered_qois),
        )
        opportunities.append(
            _build_opportunity(
                snapshot=snapshot,
                pattern="ordered-parameter-response",
                cases=ordered_cases,
                qoi_science=ordered_qois,
                primary_qoi_ids=tuple(sorted(item.qoi.qoi_id for item in ordered_qois)),
                parameters=parameters,
                comparability=comparability,
                relation=_relation_for_ordered(trend),
                trend=trend,
                case_science=case_science,
                extra_gaps=comparison_gaps,
            )
        )
    return opportunities


def _coupled_associations(
    snapshot: ScientificRecordSnapshot,
    case_science: Mapping[str, _CaseScience],
    parameters: _ParameterContext,
    qoi_series: Mapping[str, _QoISeries],
) -> list[ResearchOpportunity]:
    cases = tuple(case for case in snapshot.cases if not case.stale)
    if len(cases) < _PATTERN_MIN_CASES["coupled-association"]:
        return []
    groups = list(qoi_series.values())
    if len(groups) < 2:
        return []
    comparability, comparison_gaps = _comparability(cases, parameters)
    case_ids = tuple(case.case_id for case in cases)
    opportunities = []
    for left_index, left_series in enumerate(groups):
        for right_series in groups[left_index + 1 :]:
            left = left_series.qois
            right = right_series.qois
            left_by_case = {item.qoi.case_id: item for item in left}
            right_by_case = {item.qoi.case_id: item for item in right}
            if set(left_by_case) != set(case_ids) or set(right_by_case) != set(case_ids):
                continue
            if left_series.values_by_case is None or right_series.values_by_case is None:
                continue
            left_values = tuple(left_series.values_by_case[item] for item in case_ids)
            right_values = tuple(right_series.values_by_case[item] for item in case_ids)
            if len(set(left_values)) < 2 or len(set(right_values)) < 2:
                continue
            x = tuple(float(index) for index in range(len(case_ids)))
            left_trend = detect_trend(x, left_values)
            right_trend = detect_trend(x, right_values)
            signs = {
                TrendKind.MONOTONIC_INCREASING: 1,
                TrendKind.MONOTONIC_DECREASING: -1,
            }
            polarity = "not-applicable"
            if left_trend.kind in signs and right_trend.kind in signs:
                polarity = (
                    "positive" if signs[left_trend.kind] == signs[right_trend.kind] else "negative"
                )
            relation = ScientificRelationFrame(
                relation_class="coupled-association",
                polarity=polarity,
                comparison_direction="symmetric",
                quantifier="sampled-cases-only",
            )
            qois = (*left, *right)
            opportunities.append(
                _build_opportunity(
                    snapshot=snapshot,
                    pattern="coupled-association",
                    cases=cases,
                    qoi_science=qois,
                    primary_qoi_ids=tuple(sorted(item.qoi.qoi_id for item in qois)),
                    parameters=parameters,
                    comparability=comparability,
                    relation=relation,
                    trend=None,
                    case_science=case_science,
                    extra_gaps=comparison_gaps,
                )
            )
    return opportunities


def _validation_opportunities(
    snapshot: ScientificRecordSnapshot,
    case_science: Mapping[str, _CaseScience],
    parameters: _ParameterContext,
    qoi_series: Mapping[str, _QoISeries],
) -> list[ResearchOpportunity]:
    cases = tuple(case for case in snapshot.cases if not case.stale)
    if len(cases) < _PATTERN_MIN_CASES["validation-robustness"]:
        return []
    assessments = [case_science[case.case_id].assessment for case in cases]
    validation_ids = tuple(
        sorted(
            {
                evidence_id
                for item in assessments
                if item is not None
                for evidence_id in item.independent_validation_evidence_ids
            }
        )
    )
    sensitivity_ids = tuple(
        sorted(
            {
                evidence_id
                for item in assessments
                if item is not None
                for evidence_id in item.sensitivity_evidence_ids
            }
        )
    )
    engineering_ids = tuple(
        sorted(
            {
                evidence_id
                for item in assessments
                if item is not None
                for evidence_id in item.engineering_evidence_ids
            }
        )
    )
    if not validation_ids and not sensitivity_ids:
        return []
    comparability, comparison_gaps = _comparability(cases, parameters)
    opportunities = []
    for series in qoi_series.values():
        group = series.qois
        if series.values_by_case is None:
            continue
        if not all(item.basic_valid for item in group):
            continue
        if {item.qoi.case_id for item in group} != {case.case_id for case in cases}:
            continue
        opportunities.append(
            _build_opportunity(
                snapshot=snapshot,
                pattern="validation-robustness",
                cases=cases,
                qoi_science=group,
                primary_qoi_ids=tuple(sorted(item.qoi.qoi_id for item in group)),
                parameters=parameters,
                comparability=comparability,
                relation=ScientificRelationFrame(
                    relation_class="robustness",
                    polarity="not-applicable",
                    comparison_direction="not-applicable",
                    quantifier="validation-set-only",
                ),
                trend=None,
                case_science=case_science,
                extra_gaps=comparison_gaps,
                validation_ids=validation_ids,
                sensitivity_ids=sensitivity_ids,
                engineering_ids=engineering_ids,
            )
        )
    return opportunities


def _deduplicate_opportunity_ids(
    opportunities: Iterable[ResearchOpportunity],
) -> tuple[ResearchOpportunity, ...]:
    by_id: dict[str, tuple[bytes, ResearchOpportunity]] = {}
    for opportunity in opportunities:
        canonical = canonical_json_bytes(opportunity)
        existing = by_id.get(opportunity.opportunity_id)
        if existing is None:
            by_id[opportunity.opportunity_id] = (canonical, opportunity)
        elif existing[0] != canonical:
            raise ValueError(f"opportunity ID collision: {opportunity.opportunity_id}")
    return tuple(by_id[key][1] for key in sorted(by_id))


def discover_research_opportunities(
    snapshot: ScientificRecordSnapshot,
) -> OpportunityDiscoveryResult:
    """Discover deterministic opportunities without interpreting free-form scientific prose."""

    checked_snapshot = ScientificRecordSnapshot.model_validate(
        snapshot.model_dump(mode="python"), strict=True
    )
    qoi_checks = _qoi_checks(checked_snapshot)
    qoi_series = _qoi_groups(qoi_checks)
    scientific_qois = tuple(
        item
        for item in qoi_checks.values()
        if item.qoi.status in {"reported", "derived"}
        and isinstance(item.qoi.value, float)
        and math.isfinite(item.qoi.value)
    )
    if not scientific_qois:
        return OpportunityDiscoveryResult(opportunities=(), gaps=("scientific-qoi-required",))
    case_science = _case_science(checked_snapshot, qoi_checks)
    parameters = _parameter_context(checked_snapshot)
    opportunities = [
        *_matched_comparisons(checked_snapshot, case_science, parameters, qoi_series),
        *_ordered_responses(checked_snapshot, case_science, parameters, qoi_series),
        *_coupled_associations(checked_snapshot, case_science, parameters, qoi_series),
        *_validation_opportunities(checked_snapshot, case_science, parameters, qoi_series),
    ]
    canonical = _deduplicate_opportunity_ids(opportunities)
    gaps = tuple(
        sorted(
            {
                *(gap.code for gap in parameters.gaps),
                *(series.gap.code for series in qoi_series.values() if series.gap is not None),
                *(gap.code for item in canonical for gap in item.gaps),
            }
        )
    )
    if not canonical and not gaps:
        gaps = ("no-eligible-research-opportunity",)
    return OpportunityDiscoveryResult(opportunities=canonical, gaps=gaps)


__all__ = [
    "OpportunityDiscoveryResult",
    "OpportunitySemanticSignature",
    "ParameterBinding",
    "ResearchOpportunity",
    "ScientificGap",
    "UnitBinding",
    "discover_research_opportunities",
]
