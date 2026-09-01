"""Strict project-record intake and atomic persistence."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from cfdpaper.contracts import BoundaryRecord, CaseRecord, EvidenceRecord
from cfdpaper.scientific.units import canonical_unit
from cfdpaper.storage import ProjectStore

from .models import QualificationModel

ComparisonRole = Literal[
    "intended-study-factor",
    "demonstrated-equivalent-or-immaterial",
    "unresolved-nuisance",
    "blocking",
]
VNVState = Literal["demonstrated", "partial", "not-demonstrated", "not-applicable"]


class DeclaredSource(QualificationModel):
    source_uri: str
    locator: str
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    mtime_ns: int = Field(ge=0)
    size_bytes: int = Field(ge=0)
    media_type: str | None = None

    @field_validator("source_uri", "locator")
    @classmethod
    def required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must be nonblank")
        return stripped

    @field_validator("sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return value.lower()


class DeclaredCase(QualificationModel):
    case_id: str
    source_uri: str
    locator: str
    solver: str | None = None
    solver_version: str | None = None
    state: Literal["discovered", "extracted", "validated", "insufficient"] = "extracted"

    @field_validator("case_id", "source_uri", "locator")
    @classmethod
    def required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must be nonblank")
        return stripped


class DeclaredBoundary(QualificationModel):
    boundary_id: str
    case_id: str
    source_uri: str
    locator: str
    boundary_type: str
    values: Mapping[str, float | str | None]
    units: Mapping[str, str]
    comparison_role: ComparisonRole
    basis: str | None = None

    @field_validator("boundary_id", "case_id", "source_uri", "locator", "boundary_type")
    @classmethod
    def required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must be nonblank")
        return stripped

    @field_validator("values", "units", mode="after")
    @classmethod
    def mappings_are_defensively_frozen(cls, value: Mapping[str, object]) -> Mapping[str, object]:
        return MappingProxyType(dict(value))

    @field_serializer("values", "units")
    def serialize_mapping(self, value: Mapping[str, object]) -> dict[str, object]:
        return dict(value)

    @model_validator(mode="after")
    def demonstrated_role_has_basis(self) -> DeclaredBoundary:
        if self.comparison_role == "demonstrated-equivalent-or-immaterial" and not (
            self.basis and self.basis.strip()
        ):
            raise ValueError("demonstrated equivalence requires a basis")
        return self


class DeclaredModel(QualificationModel):
    model_id: str
    case_id: str
    source_uri: str
    locator: str
    description: str
    comparison_role: ComparisonRole
    basis: str | None = None
    verification_status: VNVState
    verification_basis: str
    verification_locator: str
    validation_status: VNVState
    validation_basis: str
    validation_locator: str

    @field_validator(
        "model_id",
        "case_id",
        "source_uri",
        "locator",
        "description",
        "verification_basis",
        "verification_locator",
        "validation_basis",
        "validation_locator",
    )
    @classmethod
    def required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must be nonblank")
        return stripped

    @model_validator(mode="after")
    def role_and_vnv_fields_are_complete(self) -> DeclaredModel:
        if self.comparison_role == "demonstrated-equivalent-or-immaterial" and not (
            self.basis and self.basis.strip()
        ):
            raise ValueError("demonstrated equivalence requires a basis")
        for label, state, basis, locator in (
            (
                "verification",
                self.verification_status,
                self.verification_basis,
                self.verification_locator,
            ),
            ("validation", self.validation_status, self.validation_basis, self.validation_locator),
        ):
            if not (state and basis.strip() and locator.strip()):
                raise ValueError(f"{label} status requires basis and locator")
        return self


class DeclaredAssessment(QualificationModel):
    evidence_id: str
    case_id: str
    source_uri: str
    locator: str
    metric: str
    observed_value: float
    unit: str
    threshold_value: float
    operator: Literal["<=", "<", ">=", ">"]
    consequence: Literal["blocking", "restricting"]
    basis: str

    @field_validator("evidence_id", "case_id", "source_uri", "locator", "metric", "basis")
    @classmethod
    def required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must be nonblank")
        return stripped

    @field_validator("observed_value", "threshold_value")
    @classmethod
    def values_are_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("assessment value must be finite")
        return value

    @field_validator("unit")
    @classmethod
    def unit_is_explicit(cls, value: str) -> str:
        canonical_unit(value)
        return value.strip()


class GuidedRecords(QualificationModel):
    cases: tuple[DeclaredCase, ...]
    boundaries: tuple[DeclaredBoundary, ...]
    models: tuple[DeclaredModel, ...]
    convergence: tuple[DeclaredAssessment, ...]
    conservation: tuple[DeclaredAssessment, ...]
    sources: tuple[DeclaredSource, ...]

    @model_validator(mode="after")
    def identities_are_unique(self) -> GuidedRecords:
        source_uris = [source.source_uri for source in self.sources]
        if len(source_uris) != len(set(source_uris)):
            raise ValueError("source_uri values must be unique")
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("case_id values must be unique")

        identifier_groups = {
            "boundary_id": [record.boundary_id for record in self.boundaries],
            "model_id": [record.model_id for record in self.models],
            "evidence_id": [
                record.evidence_id for record in (*self.convergence, *self.conservation)
            ],
        }
        for label, identifiers in identifier_groups.items():
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"{label} identifiers must be unique")

        raw_identifiers = [
            identifier for identifiers in identifier_groups.values() for identifier in identifiers
        ]
        if len(raw_identifiers) != len(set(raw_identifiers)):
            raise ValueError("identifiers must not conflict across record collections")

        persistent_evidence_ids = [
            record.evidence_id for record in (*self.convergence, *self.conservation)
        ] + [
            evidence_id
            for record in self.models
            for evidence_id in (
                f"model-{record.model_id}",
                f"verification-{record.model_id}",
                f"validation-{record.model_id}",
            )
        ]
        if len(persistent_evidence_ids) != len(set(persistent_evidence_ids)):
            raise ValueError("persistent evidence identifiers must be unique")
        return self


def load_guided_records(path: Path) -> GuidedRecords:
    """Load the exact records envelope before any project write occurs."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return GuidedRecords.model_validate(payload)


def write_guided_records(path: Path, records: GuidedRecords) -> None:
    """Write a fully validated guided envelope atomically."""

    validated = GuidedRecords.model_validate(records.model_dump(mode="python"))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(validated.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _assessment_summary(record: DeclaredAssessment) -> str:
    return (
        f"{record.metric}: observed {record.observed_value:g} {record.unit}; "
        f"declared threshold {record.operator} {record.threshold_value:g} {record.unit} "
        f"({record.consequence}); basis: {record.basis}."
    )


def persist_guided_records(store: ProjectStore, records: GuidedRecords) -> None:
    """Map one strict envelope to existing records and commit it once."""

    validated = GuidedRecords.model_validate(records.model_dump(mode="python"))
    source_uris = {source.source_uri for source in validated.sources}
    case_ids = {case.case_id for case in validated.cases}
    referenced_sources = {
        record.source_uri
        for collection in (
            validated.cases,
            validated.boundaries,
            validated.models,
            validated.convergence,
            validated.conservation,
        )
        for record in collection
    }
    if not referenced_sources <= source_uris:
        raise ValueError("Every imported record must refer to a declared source.")
    referenced_cases = {
        record.case_id
        for collection in (
            validated.boundaries,
            validated.models,
            validated.convergence,
            validated.conservation,
        )
        for record in collection
    }
    if not referenced_cases <= case_ids:
        raise ValueError("Every imported scientific record must refer to a declared case.")

    sources = tuple(
        {
            "uri": source.source_uri,
            "locator": source.locator,
            "sha256": source.sha256,
            "mtime_ns": source.mtime_ns,
            "size_bytes": source.size_bytes,
            "media_type": source.media_type,
        }
        for source in validated.sources
    )
    cases = tuple(
        CaseRecord(
            case_id=record.case_id,
            source_uri=record.source_uri,
            locator=record.locator,
            solver=record.solver,
            solver_version=record.solver_version,
            state=record.state,
        )
        for record in validated.cases
    )
    boundaries = tuple(
        BoundaryRecord(
            boundary_id=record.boundary_id,
            case_id=record.case_id,
            boundary_type=record.boundary_type,
            values={
                **record.values,
                "comparison_role": record.comparison_role,
                "comparison_basis": record.basis,
            },
            units=record.units,
            source_uri=record.source_uri,
            locator=record.locator,
        )
        for record in validated.boundaries
    )
    evidence = tuple(
        [
            EvidenceRecord(
                evidence_id=f"model-{record.model_id}",
                source_uri=record.source_uri,
                locator=record.locator,
                kind="other",
                summary=(
                    f"Case {record.case_id} model: {record.description}; role: "
                    f"{record.comparison_role}; basis: {record.basis or 'not supplied'}."
                ),
            )
            for record in validated.models
        ]
        + [
            EvidenceRecord(
                evidence_id=f"verification-{record.model_id}",
                source_uri=record.source_uri,
                locator=record.verification_locator,
                kind="other",
                summary=(
                    f"Case {record.case_id} numerical verification: "
                    f"{record.verification_status}; basis: {record.verification_basis}."
                ),
            )
            for record in validated.models
        ]
        + [
            EvidenceRecord(
                evidence_id=f"validation-{record.model_id}",
                source_uri=record.source_uri,
                locator=record.validation_locator,
                kind="other",
                summary=(
                    f"Case {record.case_id} external validation: {record.validation_status}; "
                    f"basis: {record.validation_basis}."
                ),
            )
            for record in validated.models
        ]
        + [
            EvidenceRecord(
                evidence_id=record.evidence_id,
                source_uri=record.source_uri,
                locator=record.locator,
                kind="convergence",
                summary=_assessment_summary(record),
            )
            for record in validated.convergence
        ]
        + [
            EvidenceRecord(
                evidence_id=record.evidence_id,
                source_uri=record.source_uri,
                locator=record.locator,
                kind="conservation",
                summary=_assessment_summary(record),
            )
            for record in validated.conservation
        ]
    )
    store.import_records_atomic(
        sources=sources,
        cases=cases,
        boundaries=boundaries,
        evidence=evidence,
    )
