"""Strict internal records for topic-generation inputs and scientific semantics."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    field_serializer,
    field_validator,
    model_validator,
)

from cfdpaper.publication.topics import TopicCandidate

from .canonical import canonical_sha256

SHA256_PATTERN = r"^[0-9a-f]{64}$"

ReferenceKind = Literal["case", "qoi", "parameter", "evidence"]
ClaimClass = Literal["observation", "association", "mechanism", "validation", "engineering"]
PredicateClass = Literal[
    "observation",
    "matched-comparison",
    "ordered-response",
    "coupled-association",
    "mechanism",
    "validation",
    "engineering-boundary",
]
RelationClass = Literal["difference", "ordered-response", "coupled-association", "robustness"]
RelationPolarity = Literal[
    "increase",
    "decrease",
    "non-monotonic",
    "plateau",
    "positive",
    "negative",
    "difference-only",
    "not-applicable",
]
ComparisonDirection = Literal[
    "variant-vs-reference",
    "parameter-ascending",
    "symmetric",
    "not-applicable",
]
RelationQuantifier = Literal[
    "pairwise",
    "sampled-series-only",
    "sampled-cases-only",
    "validation-set-only",
]
ProviderMode = Literal["offline", "auto", "openai", "deepseek", "gemini", "claude", "local"]


class GenerationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GenerationRequest(GenerationModel):
    provider_mode: ProviderMode = "offline"
    provider_model: str | None = None
    regenerate: bool = False
    author_brief: str | None = None

    @field_validator("provider_model", "author_brief")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("optional generation text must not be blank")
        return normalized


class _FrozenTopicCandidate(TopicCandidate):
    model_config = ConfigDict(extra="forbid", frozen=True)

    supporting_evidence_ids: tuple[str, ...] = ()
    required_evidence_kinds: frozenset[str] = frozenset()

    @field_serializer("required_evidence_kinds")
    def serialize_required_evidence_kinds(self, value: frozenset[str]) -> list[str]:
        return sorted(value)


class GeneratedCandidateEnvelope(GenerationModel):
    schema_version: Literal[1] = 1
    candidates: tuple[TopicCandidate, ...]

    @field_validator("candidates", mode="before")
    @classmethod
    def snapshot_candidates(cls, value: Any) -> Any:
        if not isinstance(value, (list, tuple)):
            return value
        return tuple(
            _FrozenTopicCandidate.model_validate(
                candidate.model_dump(mode="python")
                if isinstance(candidate, BaseModel)
                else candidate
            )
            for candidate in value
        )

    @field_serializer("candidates")
    def serialize_candidates(
        self,
        value: tuple[TopicCandidate, ...],
        info: SerializationInfo,
    ) -> tuple[dict[str, Any], ...]:
        return tuple(candidate.model_dump(mode=info.mode, warnings="error") for candidate in value)


class ScientificReference(GenerationModel):
    kind: ReferenceKind
    id: str = Field(min_length=1)

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("scientific reference ID must be a string")
        normalized = value.strip()
        if not normalized:
            raise ValueError("scientific reference ID must not be blank")
        return normalized


class SemanticParameterBinding(GenerationModel):
    kind: Literal["parameter"] = "parameter"
    id: str = Field(min_length=1)
    role: Literal["varied", "controlled"]
    case_ids: tuple[str, ...] = Field(min_length=1)
    boundary_evidence_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("parameter binding ID must be a string")
        normalized = value.strip()
        if not normalized:
            raise ValueError("parameter binding ID must not be blank")
        return normalized

    @field_validator("case_ids", "boundary_evidence_ids", mode="before")
    @classmethod
    def normalize_binding_ids(cls, value: Any) -> tuple[str, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("parameter binding IDs must be nonblank and unique")
        if any(not isinstance(item, str) for item in value):
            raise ValueError("parameter binding IDs must be nonblank and unique")
        normalized = tuple(sorted(item.strip() for item in value))
        if any(not item for item in normalized) or len(set(normalized)) != len(normalized):
            raise ValueError("parameter binding IDs must be nonblank and unique")
        return normalized


class ScientificRelationFrame(GenerationModel):
    relation_class: RelationClass
    polarity: RelationPolarity
    comparison_direction: ComparisonDirection
    quantifier: RelationQuantifier


class SemanticFrame(GenerationModel):
    claim_class: ClaimClass
    predicate_class: PredicateClass
    relation: ScientificRelationFrame
    subject_references: tuple[ScientificReference, ...]
    contrast_references: tuple[ScientificReference, ...]
    parameter_bindings: tuple[SemanticParameterBinding, ...]
    evidence_references: tuple[ScientificReference, ...]

    @field_validator(
        "subject_references",
        "contrast_references",
        "evidence_references",
        mode="before",
    )
    @classmethod
    def normalize_references(cls, value: Any) -> tuple[ScientificReference, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("scientific references must be a list or tuple")
        references = tuple(ScientificReference.model_validate(item) for item in value)
        keys = [(reference.kind, reference.id) for reference in references]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate scientific reference")
        return tuple(sorted(references, key=lambda reference: (reference.kind, reference.id)))

    @field_validator("parameter_bindings", mode="before")
    @classmethod
    def normalize_parameter_bindings(cls, value: Any) -> tuple[SemanticParameterBinding, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("parameter bindings must be a list or tuple")
        bindings = tuple(SemanticParameterBinding.model_validate(item) for item in value)
        ids = [binding.id for binding in bindings]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate parameter binding")
        return tuple(sorted(bindings, key=lambda binding: binding.id))


class QoIDefinitionAssessmentPayload(GenerationModel):
    schema_version: Literal[1] = 1
    qoi_id: str = Field(min_length=1)
    provenance_kind: Literal["adapter", "structured-import", "author-structured-input"]
    source_uri: str = Field(min_length=1)
    source_hash: str = Field(pattern=SHA256_PATTERN)
    source_locator: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    name: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    formula: str = Field(min_length=1)
    spatial_scope: str = Field(min_length=1)
    reduction: str = Field(min_length=1)
    temporal_scope: str = Field(min_length=1)
    producer_version: str = Field(min_length=1)

    @field_validator(
        "qoi_id",
        "source_uri",
        "source_locator",
        "name",
        "unit",
        "formula",
        "spatial_scope",
        "reduction",
        "temporal_scope",
        "producer_version",
        mode="before",
    )
    @classmethod
    def normalize_text_fields(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("QoI definition text fields must not be blank")
        return normalized

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def normalize_evidence_ids(cls, value: Any) -> tuple[str, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("evidence_ids must be non-empty strings")
        if any(not isinstance(item, str) for item in value):
            raise ValueError("evidence_ids must be non-empty strings")
        normalized = tuple(item.strip() for item in value)
        if not normalized or any(not item for item in normalized):
            raise ValueError("evidence_ids must be non-empty strings")
        if len(set(normalized)) != len(normalized):
            raise ValueError("evidence_ids must be unique")
        return tuple(sorted(normalized))


class QoIDefinitionAssessmentRecord(QoIDefinitionAssessmentPayload):
    definition_id: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_definition_id(self) -> QoIDefinitionAssessmentRecord:
        content = self.model_dump(mode="json", exclude={"definition_id"})
        expected = canonical_sha256(content, domain=b"cfdpaper-qoi-definition-v1")
        if self.definition_id != expected:
            raise ValueError("definition_id does not match canonical content")
        return self


def make_qoi_definition_assessment(**fields: Any) -> QoIDefinitionAssessmentRecord:
    payload = QoIDefinitionAssessmentPayload.model_validate({"schema_version": 1, **fields})
    content = payload.model_dump(mode="json")
    definition_id = canonical_sha256(content, domain=b"cfdpaper-qoi-definition-v1")
    return QoIDefinitionAssessmentRecord.model_validate({**content, "definition_id": definition_id})
