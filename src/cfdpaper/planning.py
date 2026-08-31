"""Thin orchestration for evidence-bounded topic planning."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from inspect import signature
from pathlib import Path
from typing import Any, Literal, cast, get_args
from uuid import NAMESPACE_URL, uuid4, uuid5

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaMode

from cfdpaper.cache import ContentAddressedCache
from cfdpaper.contracts import EvidenceRecord, StageResult
from cfdpaper.indexing import ConcurrentModificationError, ProjectIndexer
from cfdpaper.locking import (
    ProcessFileLockReleaseError,
    ProcessFileLockTimeoutError,
    process_file_lock,
)
from cfdpaper.publication.topics import (
    RankedTopic,
    TopicCandidate,
    TopicRankingResult,
    rank_topics,
)
from cfdpaper.retrieval import HybridRetriever, TaskContextBuilder
from cfdpaper.storage import ProjectStore
from cfdpaper.topic_generation.artifacts import generated_candidates_path, recover_generation_bundle
from cfdpaper.topic_generation.candidates import apply_generation_constraints
from cfdpaper.topic_generation.canonical import canonical_sha256
from cfdpaper.topic_generation.models import GenerationRequest
from cfdpaper.topic_generation.service import (
    GenerationExecution,
    TopicGenerationDependencies,
    TopicGenerationService,
)

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_PUBLIC_SCHEMA_NAMES = {
    "_TopicCandidateSnapshot": "TopicCandidate",
    "_RankedTopicSnapshot": "RankedTopic",
    "_TopicRankingResultSnapshot": "TopicRankingResult",
}


def _public_schema_names(value: object) -> object:
    if isinstance(value, str):
        for private_name, public_name in _PUBLIC_SCHEMA_NAMES.items():
            value = value.replace(private_name, public_name)
        return value
    if isinstance(value, list):
        return [_public_schema_names(item) for item in value]
    if isinstance(value, dict):
        return {
            _public_schema_names(key): _public_schema_names(item) for key, item in value.items()
        }
    return value


class PlanningError(RuntimeError):
    """Base class for stable user-facing planning failures."""


class PlanningInputError(PlanningError):
    """Raised when candidate input or approval input is invalid."""


class PlanningWriteError(PlanningError):
    """Raised when a report or workflow transition cannot be persisted."""


@dataclass(frozen=True)
class CandidateSource:
    """The only three candidate origins accepted by the planning boundary."""

    kind: Literal["author-explicit", "author-default", "generated"]
    path: Path | None


class PlanningModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @classmethod
    def model_json_schema(
        cls,
        by_alias: bool = True,
        ref_template: str = "#/$defs/{model}",
        schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
        mode: JsonSchemaMode = "validation",
        *,
        union_format: Literal["any_of", "primitive_type_array"] = "any_of",
    ) -> dict[str, Any]:
        parent_model_json_schema = super().model_json_schema
        schema_kwargs: dict[str, Any] = {
            "by_alias": by_alias,
            "ref_template": ref_template,
            "schema_generator": schema_generator,
            "mode": mode,
        }
        if "union_format" in signature(parent_model_json_schema).parameters:
            schema_kwargs["union_format"] = union_format
        schema = parent_model_json_schema(**schema_kwargs)
        return cast(dict[str, Any], _public_schema_names(schema))

    def model_copy(
        self,
        *,
        update: dict[str, object] | None = None,
        deep: bool = False,
    ) -> PlanningModel:
        if update:
            raise TypeError(
                "planning record updates require explicit model_validate of a complete payload"
            )
        return super().model_copy(deep=deep)


class _TopicCandidateSnapshot(TopicCandidate):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=False,
        validate_default=True,
    )

    supporting_evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    required_evidence_kinds: frozenset[str] = Field(default_factory=frozenset)

    @field_serializer("required_evidence_kinds")
    def serialize_required_evidence_kinds(self, value: frozenset[str]) -> list[str]:
        return sorted(value)


class _RankedTopicSnapshot(RankedTopic):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=False,
        validate_default=True,
    )

    candidate: _TopicCandidateSnapshot
    missing_evidence: tuple[str, ...] = Field(default_factory=tuple)


class _TopicRankingResultSnapshot(TopicRankingResult):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=False,
        validate_default=True,
    )

    ranked_topics: tuple[_RankedTopicSnapshot, ...]
    missing_evidence: tuple[str, ...] = Field(default_factory=tuple)


def _copy_candidate(snapshot: _TopicCandidateSnapshot) -> TopicCandidate:
    return TopicCandidate.model_validate(snapshot.model_dump(mode="python"))


def _copy_ranking(snapshot: _TopicRankingResultSnapshot) -> TopicRankingResult:
    return TopicRankingResult.model_validate(snapshot.model_dump(mode="python"))


def _raw_model_field(model: BaseModel, name: str) -> object:
    return BaseModel.__getattribute__(model, name)


def _legal_evidence_kinds() -> set[str]:
    kinds = get_args(EvidenceRecord.model_fields["kind"].annotation)
    if not kinds or any(not isinstance(kind, str) for kind in kinds):
        raise RuntimeError("EvidenceRecord.kind must be a non-empty Literal of str")
    return set(kinds)


class CandidateInput(PlanningModel):
    schema_version: Literal[1]
    candidates: tuple[_TopicCandidateSnapshot, ...] = Field(default_factory=tuple)

    def __getattribute__(self, name: str) -> object:
        if name == "candidates":
            snapshots = cast(
                tuple[_TopicCandidateSnapshot, ...],
                _raw_model_field(self, name),
            )
            return tuple(_copy_candidate(candidate) for candidate in snapshots)
        return BaseModel.__getattribute__(self, name)

    @field_serializer("candidates", mode="wrap")
    def serialize_candidates(
        self,
        _value: tuple[_TopicCandidateSnapshot, ...],
        handler: SerializerFunctionWrapHandler,
    ) -> object:
        snapshots = cast(
            tuple[_TopicCandidateSnapshot, ...],
            _raw_model_field(self, "candidates"),
        )
        return handler(snapshots)

    @model_validator(mode="before")
    @classmethod
    def author_values_are_strict(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        if "schema_version" in value:
            schema_version = value["schema_version"]
            if type(schema_version) is not int or schema_version != 1:
                raise ValueError("schema_version must be JSON integer 1")
        candidates = value.get("candidates")
        if not isinstance(candidates, (list, tuple)):
            return value
        normalized_candidates = []
        for index, candidate in enumerate(candidates):
            if isinstance(candidate, TopicCandidate):
                candidate_data = candidate.model_dump(mode="python")
            elif isinstance(candidate, dict):
                candidate_data = dict(candidate)
            else:
                normalized_candidates.append(candidate)
                continue
            for field in ("topic_id", "title", "research_question"):
                if field not in candidate_data:
                    continue
                raw = candidate_data[field]
                if not isinstance(raw, str) or not raw.strip():
                    raise ValueError(f"candidates.{index}.{field} must be a non-blank string")
            if "topic_id" in candidate_data:
                candidate_data["topic_id"] = candidate_data["topic_id"].strip()
            field = "minimum_verified_evidence"
            if field in candidate_data and type(candidate_data[field]) is not int:
                raise ValueError(f"candidates.{index}.{field} must be an integer")
            for field in ("significance", "novelty"):
                if field not in candidate_data:
                    continue
                raw = candidate_data[field]
                if type(raw) not in (int, float) or (type(raw) is float and not math.isfinite(raw)):
                    raise ValueError(f"candidates.{index}.{field} must be a finite number")
            normalized_candidates.append(candidate_data)
        normalized_value = dict(value)
        normalized_value["candidates"] = normalized_candidates
        return normalized_value

    @model_validator(mode="after")
    def topic_ids_are_unique(self) -> CandidateInput:
        snapshots = cast(
            tuple[_TopicCandidateSnapshot, ...],
            _raw_model_field(self, "candidates"),
        )
        seen: set[str] = set()
        for candidate in snapshots:
            if candidate.topic_id in seen:
                topic_id = candidate.topic_id
                raise ValueError(f"duplicate topic ID: {topic_id}")
            seen.add(candidate.topic_id)
        legal = _legal_evidence_kinds()
        for candidate in snapshots:
            for kind in sorted(candidate.required_evidence_kinds - legal):
                raise ValueError(f"unknown evidence kind: {kind}")
        return self


class InspectionSummary(PlanningModel):
    mode: Literal["fast"] = "fast"
    discovered: int = Field(ge=0)
    added: int = Field(ge=0)
    updated: int = Field(ge=0)
    unchanged: int = Field(ge=0)
    stale: int = Field(ge=0)


class PlanApproval(PlanningModel):
    topic_id: str = Field(min_length=1)
    author: str = Field(min_length=1)
    scope: Literal["manuscript-topic", "direction-only"]
    plan_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_at: datetime

    @field_validator("author", mode="before")
    @classmethod
    def normalize_author(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("author must not be blank")
        return normalized

    @field_validator("approved_at")
    @classmethod
    def approved_at_is_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("approved_at must be timezone-aware")
        return value


class PlanReport(PlanningModel):
    schema_version: Literal[1]
    project_id: str = Field(min_length=1)
    candidate_source_uri: str = Field(min_length=1)
    candidate_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generation_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    plan_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime
    inspection: InspectionSummary
    ranking: _TopicRankingResultSnapshot
    leading_topic_id: str | None = None
    approval: PlanApproval | None = None

    def __getattribute__(self, name: str) -> object:
        if name == "ranking":
            snapshot = cast(
                _TopicRankingResultSnapshot,
                _raw_model_field(self, name),
            )
            return _copy_ranking(snapshot)
        return BaseModel.__getattribute__(self, name)

    @field_serializer("ranking", mode="wrap")
    def serialize_ranking(
        self,
        _value: _TopicRankingResultSnapshot,
        handler: SerializerFunctionWrapHandler,
    ) -> object:
        snapshot = cast(
            _TopicRankingResultSnapshot,
            _raw_model_field(self, "ranking"),
        )
        return handler(snapshot)

    @model_validator(mode="before")
    @classmethod
    def schema_version_is_exact(cls, value: object) -> object:
        if not isinstance(value, dict) or "schema_version" not in value:
            return value
        schema_version = value["schema_version"]
        if type(schema_version) is not int or schema_version != 1:
            raise ValueError("schema_version must be JSON integer 1")
        normalized = dict(value)
        ranking = normalized.get("ranking")
        if isinstance(ranking, TopicRankingResult):
            normalized["ranking"] = ranking.model_dump(
                mode="python",
                serialize_as_any=True,
            )
        return normalized

    @field_validator("generated_at")
    @classmethod
    def generated_at_is_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def report_bindings_are_consistent(self) -> PlanReport:
        expected_fingerprint = (
            plan_fingerprint(self.candidate_source_sha256, self.evidence_snapshot_sha256)
            if self.generation_fingerprint is None
            else generated_plan_fingerprint(
                self.candidate_source_sha256,
                self.evidence_snapshot_sha256,
                self.generation_fingerprint,
            )
        )
        if self.plan_fingerprint != expected_fingerprint:
            raise ValueError("plan fingerprint does not match source hashes")

        ranking = cast(
            _TopicRankingResultSnapshot,
            _raw_model_field(self, "ranking"),
        )
        expected_leading = (
            ranking.ranked_topics[0].candidate.topic_id if ranking.ranked_topics else None
        )
        if self.leading_topic_id != expected_leading:
            raise ValueError("leading topic must match first ranked topic")

        approval = self.approval
        if approval is None:
            return self
        if approval.plan_fingerprint != self.plan_fingerprint:
            raise ValueError("approval fingerprint does not match plan fingerprint")
        selected = next(
            (
                item
                for item in ranking.ranked_topics
                if item.candidate.topic_id == approval.topic_id
            ),
            None,
        )
        if selected is None:
            raise ValueError(f"approval topic is not ranked: {approval.topic_id}")
        expected_scope = "manuscript-topic" if selected.defensible else "direction-only"
        if approval.scope != expected_scope:
            raise ValueError(
                f"approval scope does not match topic defensibility: expected {expected_scope}"
            )
        return self


class PlanExecution(PlanningModel):
    report_path: Path
    report: PlanReport
    checkpoint_id: str
    current_inspection: InspectionSummary
    approval_invalidated: bool = False
    candidate_source_kind: Literal["author-explicit", "author-default", "generated"]
    generation: GenerationExecution | None = None


def _validation_summary(error: ValidationError) -> str:
    details = []
    for item in error.errors(include_input=False, include_url=False):
        location = ".".join(str(part) for part in item["loc"]) or "<root>"
        details.append((location, item["type"], item["msg"]))
    return "; ".join(
        f"{location} [{error_type}]: {message}" for location, error_type, message in sorted(details)
    )


def load_candidate_input(path: Path) -> tuple[CandidateInput, bytes, str]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        envelope = CandidateInput.model_validate(payload)
    except ValidationError as error:
        summary = _validation_summary(error)
        raise PlanningInputError(f"invalid candidate input {path}: {summary}") from error
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        raise PlanningInputError(f"invalid candidate input {path}: {error}") from error
    return envelope, raw, hashlib.sha256(raw).hexdigest()


def resolve_candidate_source(root: Path, explicit_path: Path | None) -> CandidateSource:
    if explicit_path is not None:
        return CandidateSource("author-explicit", explicit_path.expanduser().resolve())
    default_path = root / ".cfdpaper" / "inputs" / "topic_candidates.json"
    if default_path.exists():
        return CandidateSource("author-default", default_path.resolve())
    return CandidateSource("generated", None)


def _default_generation_dependencies(store: ProjectStore) -> TopicGenerationDependencies:
    return TopicGenerationDependencies(
        store=store,
        cache=ContentAddressedCache(store.root),
        context_builder=TaskContextBuilder(HybridRetriever(store)),
        assert_plan_lock_held=lambda: True,
    )


def evidence_snapshot_sha256(evidence: list[EvidenceRecord]) -> str:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in evidence:
        if item.evidence_id in seen:
            duplicates.add(item.evidence_id)
        seen.add(item.evidence_id)
    if duplicates:
        raise PlanningInputError(f"duplicate evidence ID: {min(duplicates)}")
    canonical = json.dumps(
        [
            item.model_dump(mode="json")
            for item in sorted(evidence, key=lambda item: item.evidence_id)
        ],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def plan_fingerprint(candidate_sha256: str, evidence_sha256: str) -> str:
    for source, value in (
        ("candidate", candidate_sha256),
        ("evidence", evidence_sha256),
    ):
        if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
            raise PlanningInputError(
                f"invalid {source} SHA-256: expected 64 lowercase hexadecimal characters"
            )
    payload = (
        b"cfdpaper-plan-v1\0"
        + candidate_sha256.encode("ascii")
        + b"\0"
        + evidence_sha256.encode("ascii")
    )
    return hashlib.sha256(payload).hexdigest()


def generated_plan_fingerprint(
    candidate_sha256: str,
    evidence_sha256: str,
    generation_fingerprint: str,
) -> str:
    for source, value in (
        ("candidate", candidate_sha256),
        ("evidence", evidence_sha256),
        ("generation", generation_fingerprint),
    ):
        if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
            raise PlanningInputError(
                f"invalid {source} SHA-256: expected 64 lowercase hexadecimal characters"
            )
    return canonical_sha256(
        {
            "candidate_sha256": candidate_sha256,
            "evidence_sha256": evidence_sha256,
            "generation_fingerprint": generation_fingerprint,
        },
        domain=b"cfdpaper-generated-plan-v1",
    )


def plan_report_bytes(report: PlanReport) -> bytes:
    """Keep historical author reports byte-identical while binding generated reports."""

    exclude = {"generation_fingerprint"} if report.generation_fingerprint is None else set()
    return (report.model_dump_json(indent=2, exclude=exclude) + "\n").encode("utf-8")


def _fsync_parent_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write_report(path: Path, report: PlanReport) -> None:
    temporary = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with temporary.open("xb") as stream:
            stream.write(plan_report_bytes(report))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_parent_directory(path.parent)
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise PlanningWriteError(f"could not write planning report {path}: {error}") from error
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    try:
        temporary.unlink(missing_ok=True)
    except OSError as error:
        raise PlanningWriteError(
            f"could not clean up planning report temporary file {temporary}: {error}"
        ) from error


def _checkpoint_id(
    checkpoint_stage: str,
    fingerprint: str,
    approval: PlanApproval | None,
) -> str:
    approval_identity = (
        None if approval is None else [approval.scope, approval.topic_id, approval.author.strip()]
    )
    identity_key = json.dumps(
        {
            "checkpoint_kind": checkpoint_stage,
            "plan_fingerprint": fingerprint,
            "approval": approval_identity,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return str(uuid5(NAMESPACE_URL, f"cfdpaper-checkpoint-v1\0{identity_key}"))


def _transition_for(
    report: PlanReport,
    report_path: Path,
) -> tuple[StageResult, str, str, dict[str, Any]]:
    approval = report.approval
    if approval is not None and approval.scope == "manuscript-topic":
        status = "approved"
        project_stage = "topic-approved"
        checkpoint_stage = "plan-approval"
        approved_by = approval.author
    elif approval is not None:
        status = "complete"
        project_stage = "planned"
        checkpoint_stage = "plan-direction-approval"
        approved_by = None
    else:
        status = "complete"
        project_stage = "planned"
        checkpoint_stage = "plan"
        approved_by = None
    payload = {
        "report_path": str(report_path),
        "plan_fingerprint": report.plan_fingerprint,
        "outcome": report.ranking.outcome,
        "leading_topic_id": report.leading_topic_id,
        "missing_evidence": report.ranking.missing_evidence,
        "inspection": report.inspection.model_dump(mode="json"),
        "approval": approval.model_dump(mode="json") if approval is not None else None,
    }
    record = StageResult(
        stage="plan",
        status=status,
        outputs=payload,
        approved_by=approved_by,
        completed_at=report.generated_at,
    )
    return record, project_stage, checkpoint_stage, payload


def _load_existing_report(
    path: Path,
    *,
    explicit_approval: bool,
) -> PlanReport | None:
    if not path.exists():
        return None
    try:
        return PlanReport.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValidationError, ValueError) as error:
        if explicit_approval:
            return None
        raise PlanningInputError(f"existing planning report cannot be validated: {path}") from error


def _normalize_approval_inputs(
    approve_topic: str | None,
    author: str | None,
) -> tuple[str | None, str | None]:
    if (approve_topic is None) != (author is None):
        raise PlanningInputError("--approve-topic and --author must be supplied together")
    if approve_topic is None:
        return None, None
    if not isinstance(approve_topic, str) or not approve_topic.strip():
        raise PlanningInputError("--approve-topic must contain non-whitespace characters")
    if not isinstance(author, str) or not author.strip():
        raise PlanningInputError("--author must contain non-whitespace characters")
    return approve_topic.strip(), author.strip()


def _approval_for(
    ranking: TopicRankingResult,
    selected_topic: str,
    author: str,
    fingerprint: str,
) -> PlanApproval:
    selected = next(
        (item for item in ranking.ranked_topics if item.candidate.topic_id == selected_topic),
        None,
    )
    if selected is None:
        raise PlanningInputError(f"approval topic is not ranked: {selected_topic}")
    return PlanApproval(
        topic_id=selected_topic,
        author=author,
        scope="manuscript-topic" if selected.defensible else "direction-only",
        plan_fingerprint=fingerprint,
        approved_at=datetime.now(timezone.utc),
    )


def _same_ranking(
    existing: PlanReport,
    ranking: TopicRankingResult,
    leading_topic_id: str | None,
) -> bool:
    return existing.leading_topic_id == leading_topic_id and existing.ranking.model_dump(
        mode="python"
    ) == ranking.model_dump(mode="python")


def _approval_is_bound(
    existing: PlanReport,
    project_id: str,
    fingerprint: str,
    ranking: TopicRankingResult,
) -> bool:
    approval = existing.approval
    if approval is None:
        return False
    leading = ranking.ranked_topics[0].candidate.topic_id if ranking.ranked_topics else None
    if (
        existing.project_id != project_id
        or existing.plan_fingerprint != fingerprint
        or approval.plan_fingerprint != fingerprint
        or not _same_ranking(existing, ranking, leading)
    ):
        return False
    selected = next(
        (item for item in ranking.ranked_topics if item.candidate.topic_id == approval.topic_id),
        None,
    )
    if selected is None:
        return False
    expected_scope = "manuscript-topic" if selected.defensible else "direction-only"
    return approval.scope == expected_scope


def _same_approval_identity(first: PlanApproval, second: PlanApproval) -> bool:
    return (
        first.topic_id == second.topic_id
        and first.author == second.author
        and first.scope == second.scope
        and first.plan_fingerprint == second.plan_fingerprint
    )


_CHECKPOINT_CORE_FIELDS = (
    "report_path",
    "plan_fingerprint",
    "outcome",
    "leading_topic_id",
    "missing_evidence",
    "approval",
)
_TRANSITION_PAYLOAD_FIELDS = frozenset((*_CHECKPOINT_CORE_FIELDS, "inspection"))


def _approval_checkpoint_stage(approval: PlanApproval) -> str:
    return "plan-approval" if approval.scope == "manuscript-topic" else "plan-direction-approval"


def _strict_stored_approval(payload: dict[str, Any]) -> PlanApproval:
    if "approval" not in payload or payload["approval"] is None:
        raise RuntimeError("deterministic checkpoint ID collision")
    try:
        return PlanApproval.model_validate_json(
            json.dumps(payload["approval"], ensure_ascii=False),
            strict=True,
        )
    except (TypeError, ValueError, ValidationError) as error:
        raise RuntimeError("deterministic checkpoint ID collision") from error


def _strict_stored_inspection(payload: dict[str, Any]) -> InspectionSummary:
    if "inspection" not in payload or payload["inspection"] is None:
        raise RuntimeError("deterministic checkpoint ID collision")
    try:
        return InspectionSummary.model_validate(payload["inspection"], strict=True)
    except (TypeError, ValueError, ValidationError) as error:
        raise RuntimeError("deterministic checkpoint ID collision") from error


def _approval_payload_semantics_match(
    payload: dict[str, Any],
    report_path: Path,
    fingerprint: str,
    ranking: TopicRankingResult,
) -> bool:
    leading = ranking.ranked_topics[0].candidate.topic_id if ranking.ranked_topics else None
    expected_semantics = {
        "report_path": str(report_path),
        "plan_fingerprint": fingerprint,
        "outcome": ranking.outcome,
        "leading_topic_id": leading,
        "missing_evidence": ranking.missing_evidence,
    }
    return all(
        field in payload and payload[field] == value for field, value in expected_semantics.items()
    )


def _plan_stage_snapshot(
    store: ProjectStore,
) -> tuple[str, dict[str, Any], str | None] | None:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT status, outputs_json, approved_by FROM stages WHERE stage = 'plan'"
        ).fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(str(row["outputs_json"]))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("deterministic checkpoint ID collision") from error
    if not isinstance(payload, dict):
        raise RuntimeError("deterministic checkpoint ID collision")
    _strict_stored_inspection(payload)
    return str(row["status"]), payload, row["approved_by"]


def _generation_report_is_integrated(store: ProjectStore, report: PlanReport) -> bool:
    """Return whether the durable plan transition agrees with a generated report.

    A generated artifact report is committed before the ranking report and SQLite
    transition.  A regenerate retry must therefore reuse that artifact revision
    when the later transition was interrupted, rather than silently producing a
    new revision.
    """

    stage_snapshot = _plan_stage_snapshot(store)
    if stage_snapshot is None:
        return False
    _status, payload, _approved_by = stage_snapshot
    expected_approval = report.approval.model_dump(mode="json") if report.approval else None
    return (
        payload.get("plan_fingerprint") == report.plan_fingerprint
        and payload.get("approval") == expected_approval
    )


def _approval_from_checkpoint(
    store: ProjectStore,
    checkpoint_id: str,
    checkpoint_stage: str,
    report_path: Path,
    fingerprint: str,
    ranking: TopicRankingResult,
    desired_approval: PlanApproval,
) -> tuple[PlanApproval, dict[str, Any]] | None:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT stage, payload_json FROM checkpoints WHERE checkpoint_id = ?",
            (checkpoint_id,),
        ).fetchone()
    if row is None:
        return None
    if row["stage"] != checkpoint_stage:
        raise RuntimeError("deterministic checkpoint ID collision")
    try:
        checkpoint_payload = json.loads(str(row["payload_json"]))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("deterministic checkpoint ID collision") from error
    if not isinstance(checkpoint_payload, dict) or not _approval_payload_semantics_match(
        checkpoint_payload,
        report_path,
        fingerprint,
        ranking,
    ):
        raise RuntimeError("deterministic checkpoint ID collision")
    _strict_stored_inspection(checkpoint_payload)
    checkpoint_approval = _strict_stored_approval(checkpoint_payload)
    selected = next(
        (
            item
            for item in ranking.ranked_topics
            if item.candidate.topic_id == checkpoint_approval.topic_id
        ),
        None,
    )
    expected_scope = (
        None
        if selected is None
        else "manuscript-topic"
        if selected.defensible
        else "direction-only"
    )
    if (
        not _same_approval_identity(checkpoint_approval, desired_approval)
        or checkpoint_approval.scope != expected_scope
    ):
        raise RuntimeError("deterministic checkpoint ID collision")
    return checkpoint_approval, checkpoint_payload


def _validated_current_approval(
    store: ProjectStore,
    stage_snapshot: tuple[str, dict[str, Any], str | None] | None,
    report_path: Path,
    fingerprint: str,
    ranking: TopicRankingResult,
    current_approval: PlanApproval,
    report_approval: PlanApproval | None,
) -> PlanApproval:
    if stage_snapshot is None:
        raise RuntimeError("deterministic checkpoint ID collision")
    plan_status, plan_outputs, plan_approved_by = stage_snapshot
    checkpoint_stage = _approval_checkpoint_stage(current_approval)
    checkpoint_id = _checkpoint_id(checkpoint_stage, fingerprint, current_approval)
    stored = _approval_from_checkpoint(
        store,
        checkpoint_id,
        checkpoint_stage,
        report_path,
        fingerprint,
        ranking,
        current_approval,
    )
    if stored is None:
        raise RuntimeError("deterministic checkpoint ID collision")
    checkpoint_approval, checkpoint_payload = stored
    plan_approval = _strict_stored_approval(plan_outputs)
    expected_status = "approved" if checkpoint_approval.scope == "manuscript-topic" else "complete"
    expected_approved_by = (
        checkpoint_approval.author if checkpoint_approval.scope == "manuscript-topic" else None
    )
    if (
        checkpoint_payload != plan_outputs
        or checkpoint_approval != plan_approval
        or (report_approval is not None and report_approval != checkpoint_approval)
        or plan_status != expected_status
        or plan_approved_by != expected_approved_by
    ):
        raise RuntimeError("deterministic checkpoint ID collision")
    return checkpoint_approval


def _can_replay_report_transition(
    store: ProjectStore,
    stage_snapshot: tuple[str, dict[str, Any], str | None] | None,
    report: PlanReport,
    report_path: Path,
    candidate_path: Path,
    project_id: str,
    fingerprint: str,
    ranking: TopicRankingResult,
    desired_approval: PlanApproval | None,
) -> bool:
    target_approval = report.approval
    if (
        target_approval is None
        or desired_approval is None
        or report.project_id != project_id
        or report.candidate_source_uri != str(candidate_path)
        or report.plan_fingerprint != fingerprint
        or not _approval_is_bound(report, project_id, fingerprint, ranking)
        or (
            desired_approval is not None
            and not _same_approval_identity(target_approval, desired_approval)
        )
    ):
        return False

    project_stage = store.status().stage
    if stage_snapshot is None:
        with store.connect() as connection:
            plan_checkpoint_count = connection.execute(
                "SELECT COUNT(*) FROM checkpoints WHERE stage IN "
                "('plan', 'plan-approval', 'plan-direction-approval')"
            ).fetchone()[0]
        return project_stage in {"initialized", "inspected"} and plan_checkpoint_count == 0

    plan_status, plan_outputs, plan_approved_by = stage_snapshot
    if set(plan_outputs) != _TRANSITION_PAYLOAD_FIELDS or not _approval_payload_semantics_match(
        plan_outputs,
        report_path,
        fingerprint,
        ranking,
    ):
        raise RuntimeError("deterministic checkpoint ID collision")
    _strict_stored_inspection(plan_outputs)

    if plan_outputs["approval"] is None:
        predecessor_approval = None
        expected_status = "complete"
        expected_approved_by = None
        expected_project_stage = "planned"
        checkpoint_stage = "plan"
    else:
        predecessor_approval = _strict_stored_approval(plan_outputs)
        if _same_approval_identity(predecessor_approval, target_approval):
            return False
        expected_status = (
            "approved" if predecessor_approval.scope == "manuscript-topic" else "complete"
        )
        expected_approved_by = (
            predecessor_approval.author
            if predecessor_approval.scope == "manuscript-topic"
            else None
        )
        expected_project_stage = (
            "topic-approved" if predecessor_approval.scope == "manuscript-topic" else "planned"
        )
        checkpoint_stage = _approval_checkpoint_stage(predecessor_approval)

    checkpoint_id = _checkpoint_id(checkpoint_stage, fingerprint, predecessor_approval)
    with store.connect() as connection:
        checkpoint = connection.execute(
            "SELECT stage, payload_json FROM checkpoints WHERE checkpoint_id = ?",
            (checkpoint_id,),
        ).fetchone()
    if checkpoint is None:
        raise RuntimeError("deterministic checkpoint ID collision")
    try:
        checkpoint_payload = json.loads(str(checkpoint["payload_json"]))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("deterministic checkpoint ID collision") from error
    if (
        plan_status != expected_status
        or plan_approved_by != expected_approved_by
        or project_stage != expected_project_stage
        or checkpoint["stage"] != checkpoint_stage
        or checkpoint_payload != plan_outputs
    ):
        raise RuntimeError("deterministic checkpoint ID collision")
    if predecessor_approval is not None:
        stored = _approval_from_checkpoint(
            store,
            checkpoint_id,
            checkpoint_stage,
            report_path,
            fingerprint,
            ranking,
            predecessor_approval,
        )
        if stored is None or stored[0] != predecessor_approval or stored[1] != plan_outputs:
            raise RuntimeError("deterministic checkpoint ID collision")
    return True


def _stable_transition_payload(
    store: ProjectStore,
    checkpoint_id: str,
    checkpoint_stage: str,
    desired_payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        checkpoint = store.resume_checkpoint(checkpoint_id)
    except LookupError:
        return desired_payload
    existing_payload = checkpoint.payload
    if not isinstance(existing_payload, dict):
        raise RuntimeError("deterministic checkpoint ID collision")
    _strict_stored_inspection(existing_payload)
    core_matches = isinstance(existing_payload, dict) and all(
        field in existing_payload
        and field in desired_payload
        and existing_payload[field] == desired_payload[field]
        for field in _CHECKPOINT_CORE_FIELDS
    )
    if checkpoint.stage != checkpoint_stage or not core_matches:
        raise RuntimeError("deterministic checkpoint ID collision")
    return existing_payload


def _run_plan(
    root: Path,
    *,
    candidates_path: Path | None = None,
    approve_topic: str | None = None,
    author: str | None = None,
    provider_mode: str = "offline",
    regenerate: bool = False,
    generation_dependencies: TopicGenerationDependencies | None = None,
    lock_timeout_seconds: float = 30.0,
) -> PlanExecution:
    approve_topic, author = _normalize_approval_inputs(approve_topic, author)
    store = ProjectStore.open(root)
    report_path = store.root / ".cfdpaper" / "outputs" / "plan" / "topic-ranking.json"
    lock_path = store.root / ".cfdpaper" / "locks" / "plan.lock"
    with process_file_lock(lock_path, timeout_seconds=lock_timeout_seconds):
        source = resolve_candidate_source(store.root, candidates_path)
        if source.kind != "generated" and regenerate:
            raise PlanningInputError("--regenerate requires generated candidates")
        inspected = ProjectIndexer(store, strict_hash=False).inspect()
        inspection = InspectionSummary(mode="fast", **asdict(inspected))
        evidence = store.list_evidence()
        evidence_sha = evidence_snapshot_sha256(evidence)
        generation: GenerationExecution | None = None
        generation_fingerprint: str | None = None
        if source.kind == "generated":
            service_regenerate = regenerate
            if regenerate:
                committed_generation = recover_generation_bundle(
                    project_root=store.root,
                    expected_project_id=store.status().project_id,
                )
                integrated = _load_existing_report(report_path, explicit_approval=False)
                if committed_generation is not None and (
                    integrated is None
                    or integrated.generation_fingerprint
                    != committed_generation.report.generation_fingerprint
                    or not _generation_report_is_integrated(store, integrated)
                ):
                    service_regenerate = False
            try:
                request = GenerationRequest(
                    provider_mode=provider_mode, regenerate=service_regenerate
                )
            except ValidationError as error:
                raise PlanningInputError(f"invalid provider mode: {error}") from error
            dependencies = generation_dependencies or _default_generation_dependencies(store)
            generation = TopicGenerationService(store.root, dependencies).generate(request)
            candidate_path = generated_candidates_path(store.root)
            try:
                raw = candidate_path.read_bytes()
                envelope = CandidateInput.model_validate_json(raw)
            except (OSError, ValidationError, ValueError) as error:
                raise PlanningInputError(f"invalid generated candidate input: {error}") from error
            candidate_sha = hashlib.sha256(raw).hexdigest()
            if candidate_sha != generation.report.candidate_sha256:
                raise PlanningInputError("generated candidate bytes do not match generation report")
            by_opportunity = {
                item.opportunity_id: item for item in generation.opportunities.opportunities
            }
            mapping = dict(generation.report.topic_to_opportunity)
            if len(mapping) != len(generation.report.topic_to_opportunity):
                raise PlanningInputError("generated topic mapping contains duplicate topic IDs")
            try:
                opportunities_by_topic_id = {
                    topic_id: by_opportunity[opportunity_id]
                    for topic_id, opportunity_id in mapping.items()
                }
            except KeyError as error:
                raise PlanningInputError(
                    "generated topic mapping references an unknown opportunity"
                ) from error
            ranking = apply_generation_constraints(
                rank_topics(envelope.candidates, evidence),
                opportunities_by_topic_id=opportunities_by_topic_id,
            )
            generation_fingerprint = generation.report.generation_fingerprint
            fingerprint = generated_plan_fingerprint(
                candidate_sha,
                evidence_sha,
                generation_fingerprint,
            )
        else:
            assert source.path is not None
            candidate_path = source.path
            envelope, _raw, candidate_sha = load_candidate_input(candidate_path)
            fingerprint = plan_fingerprint(candidate_sha, evidence_sha)
            ranking = rank_topics(envelope.candidates, evidence)
        leading = ranking.ranked_topics[0].candidate.topic_id if ranking.ranked_topics else None
        project_id = store.status().project_id
        existing = _load_existing_report(
            report_path,
            explicit_approval=approve_topic is not None,
        )
        existing_bound = existing is not None and _approval_is_bound(
            existing, project_id, fingerprint, ranking
        )
        approval_invalidated = (
            existing is not None and existing.approval is not None and not existing_bound
        )
        desired_approval = (
            _approval_for(ranking, approve_topic, cast(str, author), fingerprint)
            if approve_topic is not None
            else None
        )
        stage_snapshot = _plan_stage_snapshot(store)
        stage_approval = None
        if stage_snapshot is not None and stage_snapshot[1].get("approval") is not None:
            stage_approval = _strict_stored_approval(stage_snapshot[1])
        report_current_approval = None
        if (
            desired_approval is not None
            and existing is not None
            and existing.approval is not None
            and existing.project_id == project_id
            and existing.plan_fingerprint == fingerprint
            and existing.approval.plan_fingerprint == fingerprint
        ):
            if not _same_ranking(existing, ranking, leading):
                raise RuntimeError("deterministic checkpoint ID collision")
            report_current_approval = existing.approval
        elif existing_bound and existing is not None:
            report_current_approval = existing.approval

        current_approval = report_current_approval
        if (
            current_approval is None
            and desired_approval is not None
            and stage_approval is not None
            and stage_approval.plan_fingerprint == fingerprint
        ):
            current_approval = stage_approval
        replaying_report_transition = (
            existing is not None
            and report_current_approval is not None
            and _can_replay_report_transition(
                store,
                stage_snapshot,
                existing,
                report_path,
                candidate_path,
                project_id,
                fingerprint,
                ranking,
                desired_approval,
            )
        )
        if current_approval is not None and not replaying_report_transition:
            current_approval = _validated_current_approval(
                store,
                stage_snapshot,
                report_path,
                fingerprint,
                ranking,
                current_approval,
                report_current_approval,
            )

        if desired_approval is None:
            approval = current_approval
        elif current_approval is not None and _same_approval_identity(
            current_approval,
            desired_approval,
        ):
            approval = current_approval
        else:
            approval_checkpoint_stage = _approval_checkpoint_stage(desired_approval)
            approval_checkpoint_id = _checkpoint_id(
                approval_checkpoint_stage,
                fingerprint,
                desired_approval,
            )
            stored_target = _approval_from_checkpoint(
                store,
                approval_checkpoint_id,
                approval_checkpoint_stage,
                report_path,
                fingerprint,
                ranking,
                desired_approval,
            )
            if stored_target is None:
                approval = desired_approval
            else:
                if existing is None and current_approval is None:
                    raise RuntimeError("deterministic checkpoint ID collision")
                approval = stored_target[0]
        report_is_reused = (
            existing is not None
            and existing.project_id == project_id
            and existing.plan_fingerprint == fingerprint
            and existing.candidate_source_uri == str(candidate_path)
            and _same_ranking(existing, ranking, leading)
            and existing.approval == approval
        )
        if report_is_reused:
            assert existing is not None
            report = existing
        else:
            report = PlanReport(
                schema_version=1,
                project_id=project_id,
                candidate_source_uri=str(candidate_path),
                candidate_source_sha256=candidate_sha,
                evidence_snapshot_sha256=evidence_sha,
                generation_fingerprint=generation_fingerprint,
                plan_fingerprint=fingerprint,
                generated_at=datetime.now(timezone.utc),
                inspection=inspection,
                ranking=ranking,
                leading_topic_id=leading,
                approval=approval,
            )
        record, project_stage, checkpoint_stage, payload = _transition_for(report, report_path)
        checkpoint_id = _checkpoint_id(
            checkpoint_stage,
            fingerprint,
            report.approval,
        )
        payload = _stable_transition_payload(
            store,
            checkpoint_id,
            checkpoint_stage,
            payload,
        )
        record = StageResult(
            stage=record.stage,
            status=record.status,
            outputs=payload,
            approved_by=record.approved_by,
            completed_at=record.completed_at,
        )
        if not report_is_reused:
            _atomic_write_report(report_path, report)
        store.save_workflow_transition(
            record,
            project_stage=project_stage,
            checkpoint_id=checkpoint_id,
            checkpoint_stage=checkpoint_stage,
            checkpoint_payload=payload,
        )
        return PlanExecution(
            report_path=report_path,
            report=report,
            checkpoint_id=checkpoint_id,
            current_inspection=inspection,
            approval_invalidated=approval_invalidated,
            candidate_source_kind=source.kind,
            generation=generation,
        )


def run_plan(
    root: Path,
    *,
    candidates_path: Path | None = None,
    approve_topic: str | None = None,
    author: str | None = None,
    provider_mode: str = "offline",
    regenerate: bool = False,
    generation_dependencies: TopicGenerationDependencies | None = None,
    lock_timeout_seconds: float = 30.0,
) -> PlanExecution:
    try:
        return _run_plan(
            root,
            candidates_path=candidates_path,
            approve_topic=approve_topic,
            author=author,
            provider_mode=provider_mode,
            regenerate=regenerate,
            generation_dependencies=generation_dependencies,
            lock_timeout_seconds=lock_timeout_seconds,
        )
    except PlanningError:
        raise
    except (
        ProcessFileLockTimeoutError,
        ProcessFileLockReleaseError,
        ConcurrentModificationError,
        sqlite3.Error,
        OSError,
        RuntimeError,
    ) as error:
        raise PlanningWriteError(f"planning transition failed: {error}") from error
