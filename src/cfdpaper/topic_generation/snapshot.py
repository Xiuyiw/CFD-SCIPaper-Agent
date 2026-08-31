"""Deterministic, immutable snapshots of persisted scientific records."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, TypeVar

from pydantic import ConfigDict, Field, field_serializer, field_validator, model_validator

from cfdpaper.contracts import (
    BoundaryRecord,
    CaseRecord,
    ClaimRecord,
    EvidenceRecord,
    FieldRecord,
    MeshRecord,
    QoIRecord,
)
from cfdpaper.scientific.units import canonical_unit
from cfdpaper.topic_generation.canonical import canonical_json_bytes, canonical_sha256
from cfdpaper.topic_generation.models import (
    SHA256_PATTERN,
    GenerationModel,
    QoIDefinitionAssessmentRecord,
)

if TYPE_CHECKING:
    from cfdpaper.storage import ProjectStore

COMPONENT_NAMES = (
    "cases",
    "boundaries",
    "meshes",
    "fields",
    "qois",
    "qoi-definitions",
    "evidence",
    "claims",
    "assessments",
)
_COMPONENT_DOMAIN = b"cfdpaper-scientific-component-v1"
_SNAPSHOT_DOMAIN = b"cfdpaper-scientific-snapshot-v1"
_RECORD_SNAPSHOT_CONFIG = ConfigDict(
    extra="forbid",
    frozen=True,
    validate_default=True,
    strict=True,
    revalidate_instances="always",
)

NonfiniteValueTag = Literal[
    "nonfinite:nan",
    "nonfinite:positive-infinity",
    "nonfinite:negative-infinity",
]


def _nonblank(value: Any, *, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} must not be blank")
    return normalized


class _ScientificModel(GenerationModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
        allow_inf_nan=False,
        revalidate_instances="always",
        strict=True,
    )


class NamedScalar(GenerationModel):
    model_config = _ScientificModel.model_config

    name: str = Field(min_length=1)
    value: float

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: Any) -> str:
        return _nonblank(value, label="scalar name")


def _normalize_named_scalars(value: Any) -> tuple[NamedScalar, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("NamedScalar arrays must be a list or tuple")
    items = tuple(NamedScalar.model_validate(item, strict=True) for item in value)
    names = [item.name for item in items]
    if len(set(names)) != len(names):
        raise ValueError("duplicate NamedScalar name")
    return tuple(sorted(items, key=lambda item: item.name))


def _normalize_ids(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("evidence IDs must be a list or tuple")
    if any(not isinstance(item, str) for item in value):
        raise ValueError("evidence IDs must be strings")
    normalized = tuple(item.strip() for item in value)
    if any(not item for item in normalized):
        raise ValueError("evidence IDs must not be blank")
    if len(set(normalized)) != len(normalized):
        raise ValueError("evidence IDs must be unique")
    return tuple(sorted(normalized))


class CaseNumericalAssessmentInput(GenerationModel):
    model_config = _ScientificModel.model_config

    case_id: str = Field(min_length=1)
    residuals: tuple[NamedScalar, ...]
    residual_targets: tuple[NamedScalar, ...]
    qoi_relative_span: float | None
    conservation_inflow: float
    conservation_outflow: float
    conservation_tolerance: float = Field(ge=0)
    case_evidence_ids: tuple[str, ...] = ()
    convergence_evidence_ids: tuple[str, ...] = ()
    conservation_evidence_ids: tuple[str, ...] = ()
    independent_validation_evidence_ids: tuple[str, ...]
    engineering_evidence_ids: tuple[str, ...]
    sensitivity_evidence_ids: tuple[str, ...]

    @field_validator("case_id", mode="before")
    @classmethod
    def normalize_case_id(cls, value: Any) -> str:
        return _nonblank(value, label="case ID")

    @field_validator("residuals", "residual_targets", mode="before")
    @classmethod
    def normalize_scalar_arrays(cls, value: Any) -> tuple[NamedScalar, ...]:
        return _normalize_named_scalars(value)

    @field_validator(
        "case_evidence_ids",
        "convergence_evidence_ids",
        "conservation_evidence_ids",
        "independent_validation_evidence_ids",
        "engineering_evidence_ids",
        "sensitivity_evidence_ids",
        mode="before",
    )
    @classmethod
    def normalize_evidence_ids(cls, value: Any) -> tuple[str, ...]:
        return _normalize_ids(value)


class ScientificAssessmentSet(GenerationModel):
    model_config = _ScientificModel.model_config

    schema_version: Literal[1] = 1
    cases: tuple[CaseNumericalAssessmentInput, ...] = ()

    @field_validator("cases", mode="before")
    @classmethod
    def normalize_cases(cls, value: Any) -> tuple[CaseNumericalAssessmentInput, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("assessment cases must be a list or tuple")
        cases = tuple(
            CaseNumericalAssessmentInput.model_validate(item, strict=True) for item in value
        )
        ids = [case.case_id for case in cases]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate assessment case ID")
        return tuple(sorted(cases, key=lambda item: item.case_id))


class CaseSnapshot(CaseRecord):
    model_config = _RECORD_SNAPSHOT_CONFIG


def _copy_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("snapshot mapping fields require a mapping")
    return dict(value)


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


class BoundarySnapshot(BoundaryRecord):
    model_config = _RECORD_SNAPSHOT_CONFIG

    values: Mapping[str, float | str | None] = Field(default_factory=dict)
    units: Mapping[str, str] = Field(default_factory=dict)

    @field_validator("values", "units", mode="before")
    @classmethod
    def copy_mappings(cls, value: Any) -> dict[str, Any]:
        return _copy_mapping(value)

    @field_validator("values", "units")
    @classmethod
    def freeze_mappings(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return _freeze_mapping(value)

    @field_serializer("values", "units")
    def serialize_mappings(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return dict(value)


class MeshSnapshot(MeshRecord):
    model_config = _RECORD_SNAPSHOT_CONFIG

    quality: Mapping[str, float | None] = Field(default_factory=dict)

    @field_validator("quality", mode="before")
    @classmethod
    def copy_quality(cls, value: Any) -> dict[str, Any]:
        return _copy_mapping(value)

    @field_validator("quality")
    @classmethod
    def freeze_quality(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return _freeze_mapping(value)

    @field_serializer("quality")
    def serialize_quality(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return dict(value)


class FieldSnapshot(FieldRecord):
    model_config = _RECORD_SNAPSHOT_CONFIG


class QoISnapshot(QoIRecord):
    model_config = _RECORD_SNAPSHOT_CONFIG

    value: float | None | NonfiniteValueTag = None

    @field_validator("value", mode="before")
    @classmethod
    def encode_nonfinite_value(cls, value: Any) -> Any:
        if not isinstance(value, float) or math.isfinite(value):
            return value
        if math.isnan(value):
            return "nonfinite:nan"
        if value > 0:
            return "nonfinite:positive-infinity"
        return "nonfinite:negative-infinity"


class EvidenceSnapshot(EvidenceRecord):
    model_config = _RECORD_SNAPSHOT_CONFIG


class ClaimSnapshot(ClaimRecord):
    model_config = _RECORD_SNAPSHOT_CONFIG

    evidence_ids: tuple[str, ...] = ()

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def normalize_claim_evidence_ids(cls, value: Any) -> tuple[str, ...]:
        return _normalize_ids(value)


class ComponentHash(GenerationModel):
    model_config = _ScientificModel.model_config

    name: str
    sha256: str = Field(pattern=SHA256_PATTERN)


class ScientificRecordSnapshot(GenerationModel):
    model_config = _ScientificModel.model_config

    schema_version: Literal[1] = 1
    project_id: str = Field(min_length=1)
    cases: tuple[CaseSnapshot, ...]
    boundaries: tuple[BoundarySnapshot, ...]
    meshes: tuple[MeshSnapshot, ...]
    fields: tuple[FieldSnapshot, ...]
    qois: tuple[QoISnapshot, ...]
    qoi_definition_assessments: tuple[QoIDefinitionAssessmentRecord, ...]
    evidence: tuple[EvidenceSnapshot, ...]
    claims: tuple[ClaimSnapshot, ...]
    assessments: ScientificAssessmentSet
    component_hashes: tuple[ComponentHash, ...]
    aggregate_sha256: str = Field(pattern=SHA256_PATTERN)
    gaps: tuple[str, ...]

    @field_validator("project_id", mode="before")
    @classmethod
    def normalize_project_id(cls, value: Any) -> str:
        return _nonblank(value, label="project ID")

    @model_validator(mode="after")
    def validate_content_hashes(self) -> ScientificRecordSnapshot:
        canonical_groups = (
            ("cases", _canonical_records(self.cases, CaseSnapshot, "case_id", "case")),
            (
                "boundaries",
                _canonical_records(self.boundaries, BoundarySnapshot, "boundary_id", "boundary"),
            ),
            ("meshes", _canonical_records(self.meshes, MeshSnapshot, "mesh_id", "mesh")),
            ("fields", _canonical_records(self.fields, FieldSnapshot, "field_id", "field")),
            ("qois", _canonical_records(self.qois, QoISnapshot, "qoi_id", "qoi")),
            (
                "qoi_definition_assessments",
                _canonical_records(
                    self.qoi_definition_assessments,
                    QoIDefinitionAssessmentRecord,
                    "qoi_id",
                    "qoi definition",
                ),
            ),
            (
                "evidence",
                _canonical_records(self.evidence, EvidenceSnapshot, "evidence_id", "evidence"),
            ),
            ("claims", _canonical_records(self.claims, ClaimSnapshot, "claim_id", "claim")),
        )
        for field_name, canonical in canonical_groups:
            if getattr(self, field_name) != canonical:
                raise ValueError(f"scientific {field_name} are not in canonical form")
        canonical_assessments = ScientificAssessmentSet.model_validate(
            self.assessments.model_dump(mode="python"), strict=True
        )
        if self.assessments != canonical_assessments:
            raise ValueError("scientific assessments are not in canonical form")

        names = tuple(component.name for component in self.component_hashes)
        if names != COMPONENT_NAMES:
            raise ValueError("scientific component names or order do not match")
        component_values = (
            self.cases,
            self.boundaries,
            self.meshes,
            self.fields,
            self.qois,
            self.qoi_definition_assessments,
            self.evidence,
            self.claims,
            self.assessments,
        )
        expected_components = tuple(
            ComponentHash(name=name, sha256=canonical_sha256(value, domain=_COMPONENT_DOMAIN))
            for name, value in zip(COMPONENT_NAMES, component_values, strict=True)
        )
        if self.component_hashes != expected_components:
            raise ValueError("scientific component hash does not match content")
        expected_aggregate = canonical_sha256(
            {"project_id": self.project_id, "component_hashes": self.component_hashes},
            domain=_SNAPSHOT_DOMAIN,
        )
        if self.aggregate_sha256 != expected_aggregate:
            raise ValueError("scientific aggregate hash does not match content")
        expected_gaps = _derive_gaps(
            cases=self.cases,
            boundaries=self.boundaries,
            meshes=self.meshes,
            fields=self.fields,
            qois=self.qois,
            qoi_definition_assessments=self.qoi_definition_assessments,
            evidence=self.evidence,
            assessments=self.assessments,
        )
        if self.gaps != expected_gaps:
            raise ValueError("scientific gaps do not match snapshot content")
        return self

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> ScientificRecordSnapshot:
        if update is None:
            if deep:
                return type(self).model_validate(self.model_dump(mode="python"), strict=True)
            return super().model_copy()
        data = self.model_dump(mode="python")
        data.update(update)
        return type(self).model_validate(data, strict=True)

    def component_sha256(self, name: str) -> str:
        for component in self.component_hashes:
            if component.name == name:
                return component.sha256
        raise KeyError(name)


SnapshotT = TypeVar("SnapshotT", bound=GenerationModel)


def _canonical_records(
    records: Iterable[Any],
    model: type[SnapshotT],
    id_field: str,
    label: str,
) -> tuple[SnapshotT, ...]:
    """Create private frozen copies, deduplicate exact records, and sort by stable ID."""

    by_id: dict[str, tuple[bytes, SnapshotT]] = {}
    for record in records:
        data = record.model_dump(mode="python") if hasattr(record, "model_dump") else record
        snapshot = model.model_validate(data, strict=True)
        record_id = _nonblank(getattr(snapshot, id_field), label=f"{label} ID")
        canonical = canonical_json_bytes(snapshot)
        existing = by_id.get(record_id)
        if existing is None:
            by_id[record_id] = (canonical, snapshot)
        elif existing[0] != canonical:
            raise ValueError(f"duplicate {label} ID: {record_id}")
    return tuple(by_id[record_id][1] for record_id in sorted(by_id))


def _record_gaps(label: str, records: Iterable[Any], id_field: str) -> list[str]:
    return [
        f"source-record-stale:{label}:{getattr(record, id_field)}"
        for record in records
        if record.stale
    ]


def _known_unit(unit: str | None) -> bool:
    try:
        canonical_unit(unit)
    except ValueError:
        return False
    return True


def _derive_gaps(
    *,
    cases: tuple[CaseSnapshot, ...],
    boundaries: tuple[BoundarySnapshot, ...],
    meshes: tuple[MeshSnapshot, ...],
    fields: tuple[FieldSnapshot, ...],
    qois: tuple[QoISnapshot, ...],
    qoi_definition_assessments: tuple[QoIDefinitionAssessmentRecord, ...],
    evidence: tuple[EvidenceSnapshot, ...],
    assessments: ScientificAssessmentSet,
) -> tuple[str, ...]:
    gaps: list[str] = []
    for label, records, id_field in (
        ("case", cases, "case_id"),
        ("boundary", boundaries, "boundary_id"),
        ("mesh", meshes, "mesh_id"),
        ("field", fields, "field_id"),
        ("qoi", qois, "qoi_id"),
        ("evidence", evidence, "evidence_id"),
    ):
        gaps.extend(_record_gaps(label, records, id_field))
    assessed_case_ids = {assessment.case_id for assessment in assessments.cases}
    for case in cases:
        if not case.stale and case.case_id not in assessed_case_ids:
            gaps.append(f"case-numerical-assessment-missing:{case.case_id}")
    definition_qoi_ids = {record.qoi_id for record in qoi_definition_assessments}
    for qoi in qois:
        if qoi.status in {"missing", "invalid"}:
            gaps.append(f"qoi-status-{qoi.status}:{qoi.qoi_id}")
        if qoi.value is None:
            gaps.append(f"qoi-value-missing:{qoi.qoi_id}")
        elif isinstance(qoi.value, str):
            gaps.append(f"qoi-value-nonfinite:{qoi.qoi_id}")
        if qoi.unit is None or not qoi.unit.strip():
            gaps.append(f"qoi-unit-missing:{qoi.qoi_id}")
        elif not _known_unit(qoi.unit):
            gaps.append(f"qoi-unit-unknown:{qoi.qoi_id}")
        eligible = (
            not qoi.stale
            and qoi.status in {"reported", "derived"}
            and isinstance(qoi.value, float)
            and math.isfinite(qoi.value)
            and _known_unit(qoi.unit)
        )
        if eligible and qoi.qoi_id not in definition_qoi_ids:
            gaps.append(f"qoi-structured-definition-missing:{qoi.qoi_id}")
    return tuple(sorted(set(gaps)))


def build_scientific_snapshot(
    *,
    project_id: str,
    cases: Sequence[CaseRecord],
    boundaries: Sequence[BoundaryRecord],
    meshes: Sequence[MeshRecord],
    fields: Sequence[FieldRecord],
    qois: Sequence[QoIRecord],
    qoi_definition_assessments: Sequence[QoIDefinitionAssessmentRecord],
    evidence: Sequence[EvidenceRecord],
    claims: Sequence[ClaimRecord],
    assessments: ScientificAssessmentSet,
) -> ScientificRecordSnapshot:
    """Assemble one order-independent, content-addressed scientific snapshot."""

    normalized_project_id = _nonblank(project_id, label="project ID")
    case_records = _canonical_records(cases, CaseSnapshot, "case_id", "case")
    boundary_records = _canonical_records(boundaries, BoundarySnapshot, "boundary_id", "boundary")
    mesh_records = _canonical_records(meshes, MeshSnapshot, "mesh_id", "mesh")
    field_records = _canonical_records(fields, FieldSnapshot, "field_id", "field")
    qoi_records = _canonical_records(qois, QoISnapshot, "qoi_id", "qoi")
    definition_records = _canonical_records(
        qoi_definition_assessments,
        QoIDefinitionAssessmentRecord,
        "qoi_id",
        "qoi definition",
    )
    evidence_records = _canonical_records(evidence, EvidenceSnapshot, "evidence_id", "evidence")
    claim_records = _canonical_records(claims, ClaimSnapshot, "claim_id", "claim")
    assessment_records = ScientificAssessmentSet.model_validate(
        assessments.model_dump(mode="python")
        if isinstance(assessments, ScientificAssessmentSet)
        else assessments,
        strict=True,
    )

    component_values = (
        case_records,
        boundary_records,
        mesh_records,
        field_records,
        qoi_records,
        definition_records,
        evidence_records,
        claim_records,
        assessment_records,
    )
    component_hashes = tuple(
        ComponentHash(name=name, sha256=canonical_sha256(value, domain=_COMPONENT_DOMAIN))
        for name, value in zip(COMPONENT_NAMES, component_values, strict=True)
    )
    aggregate_sha256 = canonical_sha256(
        {"project_id": normalized_project_id, "component_hashes": component_hashes},
        domain=_SNAPSHOT_DOMAIN,
    )

    gaps = _derive_gaps(
        cases=case_records,
        boundaries=boundary_records,
        meshes=mesh_records,
        fields=field_records,
        qois=qoi_records,
        qoi_definition_assessments=definition_records,
        evidence=evidence_records,
        assessments=assessment_records,
    )

    return ScientificRecordSnapshot(
        project_id=normalized_project_id,
        cases=case_records,
        boundaries=boundary_records,
        meshes=mesh_records,
        fields=field_records,
        qois=qoi_records,
        qoi_definition_assessments=definition_records,
        evidence=evidence_records,
        claims=claim_records,
        assessments=assessment_records,
        component_hashes=component_hashes,
        aggregate_sha256=aggregate_sha256,
        gaps=gaps,
    )


def load_scientific_snapshot(store: ProjectStore) -> ScientificRecordSnapshot:
    """Load a snapshot exclusively through persistent store accessors."""

    return build_scientific_snapshot(
        project_id=store.status().project_id,
        cases=store.list_cases(),
        boundaries=store.list_boundaries(),
        meshes=store.list_meshes(),
        fields=store.list_fields(),
        qois=store.list_qois(),
        qoi_definition_assessments=store.list_qoi_definition_assessments(),
        evidence=store.list_evidence(),
        claims=store.list_claims(),
        assessments=store.load_scientific_assessment_set(),
    )
