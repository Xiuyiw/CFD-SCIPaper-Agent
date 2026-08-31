"""Durable, content-addressed publication of generated topic artifacts."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import Field, field_validator, model_validator

from cfdpaper.cache import CacheIntegrityError, ContentAddressedCache
from cfdpaper.scientific import ClaimCeiling, EvidenceMaturity
from cfdpaper.topic_generation.candidates import (
    CandidateConstructionResult,
    build_generated_candidates,
)
from cfdpaper.topic_generation.canonical import canonical_json_bytes, canonical_sha256
from cfdpaper.topic_generation.models import (
    SHA256_PATTERN,
    GeneratedCandidateEnvelope,
    GenerationModel,
    GenerationRequest,
    ScientificRelationFrame,
    SemanticParameterBinding,
)
from cfdpaper.topic_generation.opportunities import (
    OpportunityDiscoveryResult,
    OpportunitySemanticSignature,
    ParameterBinding,
    ResearchOpportunity,
    ScientificGap,
    UnitBinding,
)
from cfdpaper.topic_generation.refinement import (
    PROMPT_CONTRACT_VERSION,
    REFINEMENT_POLICY_VERSION,
    AcceptedRefinement,
    RefinementResult,
)
from cfdpaper.topic_generation.snapshot import ComponentHash, ScientificRecordSnapshot

GENERATOR_VERSION = "hybrid-topic-generator-v1"
_OUTPUT_RELATIVE = Path(".cfdpaper") / "outputs" / "plan"


class GenerationArtifactConflict(RuntimeError):
    """A generated artifact cannot be tied to its recorded scientific state."""


class InjectedGenerationCrash(RuntimeError):
    """Test-only deterministic crash at a filesystem publication boundary."""


class GenerationArtifactHashes(GenerationModel):
    opportunity_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_sha256: str = Field(pattern=SHA256_PATTERN)


class GenerationMaterial(GenerationModel):
    """Semantic identity; deliberately excludes operational timestamps and raw provider text."""

    semantic_reuse_key: str = Field(pattern=SHA256_PATTERN)
    generation_revision: int = Field(ge=1)
    requested_provider_mode: str
    requested_provider_model: str | None
    resolved_provider_name: str
    resolved_provider_model: str | None
    context_packet_sha256: str | None
    opportunity_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_sha256: str = Field(pattern=SHA256_PATTERN)
    accepted_refinement_hash: str = Field(pattern=SHA256_PATTERN)


class CandidateProvenance(GenerationModel):
    topic_id: str = Field(min_length=1)
    opportunity_id: str = Field(min_length=1)
    pattern: str = Field(min_length=1)
    case_ids: tuple[str, ...]
    qoi_ids: tuple[str, ...]
    parameter_bindings: tuple[SemanticParameterBinding, ...]
    trend_type: str | None
    relation: ScientificRelationFrame
    claim_ceiling: str = Field(min_length=1)
    supporting_evidence_ids: tuple[str, ...]
    semantic_signature_sha256: str = Field(pattern=SHA256_PATTERN)
    ranking_reason_codes: tuple[str, ...]
    figure_evidence_structure: tuple[str, ...]
    paper_spine_evidence_structure: tuple[str, ...]
    locked_candidate_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator(
        "case_ids",
        "qoi_ids",
        "supporting_evidence_ids",
        "ranking_reason_codes",
        "figure_evidence_structure",
        "paper_spine_evidence_structure",
        mode="before",
    )
    @classmethod
    def normalize_ids(cls, value: object) -> tuple[str, ...]:
        if not isinstance(value, (tuple, list)) or any(not isinstance(item, str) for item in value):
            raise ValueError("candidate provenance values must be string sequences")
        normalized = tuple(sorted(item.strip() for item in value))
        if any(not item for item in normalized) or len(set(normalized)) != len(normalized):
            raise ValueError("candidate provenance values must be nonblank and unique")
        return normalized


class TopicHeuristicRecord(GenerationModel):
    topic_id: str = Field(min_length=1)
    significance: float = Field(ge=0, le=1)
    novelty: float = Field(ge=0, le=1)
    maturity: str = Field(min_length=1)
    claim_ceiling: str = Field(min_length=1)
    defensible: bool


class SourceRecordProvenance(GenerationModel):
    record_kind: str = Field(min_length=1)
    record_id: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    source_hash: str = Field(pattern=SHA256_PATTERN)
    source_locator: str = Field(min_length=1)
    stale: bool


class GenerationReport(GenerationModel):
    schema_version: Literal[1] = 1
    project_id: str = Field(min_length=1)
    scientific_snapshot_sha256: str = Field(pattern=SHA256_PATTERN)
    scientific_component_hashes: tuple[ComponentHash, ...]
    semantic_reuse_key: str = Field(pattern=SHA256_PATTERN)
    generation_fingerprint: str = Field(pattern=SHA256_PATTERN)
    generation_revision: int = Field(ge=1)
    generation_mode: Literal["offline", "provider-refined", "offline-fallback"]
    generator_version: str
    prompt_contract_version: str
    refinement_policy_version: str
    requested_provider_mode: str
    requested_provider_model: str | None
    resolved_provider_name: str
    resolved_provider_model: str | None
    context_packet_sha256: str | None
    author_brief_sha256: str | None
    generated_at: datetime
    opportunity_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_sha256: str = Field(pattern=SHA256_PATTERN)
    accepted_refinement_envelope: tuple[AcceptedRefinement, ...]
    accepted_refinement_hash: str = Field(pattern=SHA256_PATTERN)
    topic_to_opportunity: tuple[tuple[str, str], ...]
    candidate_provenance: tuple[CandidateProvenance, ...]
    offline_heuristics: tuple[TopicHeuristicRecord, ...]
    fallback_reasons: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    minimum_missing_data: tuple[str, ...] = ()
    prohibited_inferences: tuple[str, ...] = ()
    source_record_provenance: tuple[SourceRecordProvenance, ...]

    @model_validator(mode="after")
    def validate_report_identity(self) -> GenerationReport:
        if (
            self.generator_version != GENERATOR_VERSION
            or self.prompt_contract_version != PROMPT_CONTRACT_VERSION
            or self.refinement_policy_version != REFINEMENT_POLICY_VERSION
        ):
            raise ValueError("generation version metadata does not match this generator")
        material = GenerationMaterial(
            semantic_reuse_key=self.semantic_reuse_key,
            generation_revision=self.generation_revision,
            requested_provider_mode=self.requested_provider_mode,
            requested_provider_model=self.requested_provider_model,
            resolved_provider_name=self.resolved_provider_name,
            resolved_provider_model=self.resolved_provider_model,
            context_packet_sha256=self.context_packet_sha256,
            opportunity_sha256=self.opportunity_sha256,
            candidate_sha256=self.candidate_sha256,
            accepted_refinement_hash=self.accepted_refinement_hash,
        )
        if self.generation_fingerprint != generation_fingerprint(material):
            raise ValueError("generation fingerprint does not match semantic material")
        accepted = tuple(sorted(self.accepted_refinement_envelope, key=lambda item: item.topic_id))
        expected_accepted = canonical_sha256(accepted, domain=b"cfdpaper-accepted-refinement-v1")
        if (
            self.accepted_refinement_envelope != accepted
            or self.accepted_refinement_hash != expected_accepted
        ):
            raise ValueError("accepted refinement envelope does not match its hash")
        mappings = tuple(sorted(self.topic_to_opportunity))
        accepted_ids = tuple(item.topic_id for item in accepted)
        mapping_ids = tuple(item[0] for item in mappings)
        mapping_opportunity_ids = tuple(item[1] for item in mappings)
        provenance_ids = tuple(item.topic_id for item in self.candidate_provenance)
        heuristic_ids = tuple(item.topic_id for item in self.offline_heuristics)
        if (
            self.topic_to_opportunity != mappings
            or any(not all(item) for item in mappings)
            or len(set(mapping_ids)) != len(mapping_ids)
            or len(set(mapping_opportunity_ids)) != len(mapping_opportunity_ids)
            or mapping_ids != accepted_ids
            or provenance_ids != accepted_ids
            or heuristic_ids != accepted_ids
        ):
            raise ValueError("topic-to-opportunity mappings must be sorted and nonblank")
        mapping_by_topic = dict(mappings)
        if any(
            mapping_by_topic[item.topic_id] != item.opportunity_id
            for item in self.candidate_provenance
        ):
            raise ValueError("candidate provenance does not match topic mapping")
        source_provenance = tuple(
            sorted(
                self.source_record_provenance,
                key=lambda item: (item.record_kind, item.record_id),
            )
        )
        if self.source_record_provenance != source_provenance:
            raise ValueError("source record provenance must be sorted")
        return self


class CommittedGenerationBundle(GenerationModel):
    report: GenerationReport
    opportunity_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_sha256: str = Field(pattern=SHA256_PATTERN)
    opportunities: OpportunityDiscoveryResult
    candidates: GeneratedCandidateEnvelope
    cache: ContentAddressedCache

    model_config = {"arbitrary_types_allowed": True, "extra": "forbid", "frozen": True}


def _outputs_dir(project_root: Path) -> Path:
    return project_root.expanduser().resolve() / _OUTPUT_RELATIVE


def opportunities_path(project_root: Path) -> Path:
    return _outputs_dir(project_root) / "research-opportunities.json"


def generated_candidates_path(project_root: Path) -> Path:
    return _outputs_dir(project_root) / "generated-topic-candidates.json"


def generation_report_path(project_root: Path) -> Path:
    return _outputs_dir(project_root) / "candidate-generation-report.json"


def opportunity_envelope_sha256(opportunities: OpportunityDiscoveryResult) -> str:
    """Return the raw digest of the canonical opportunity artifact bytes."""

    return hashlib.sha256(canonical_json_bytes(opportunities)).hexdigest()


def semantic_reuse_key(
    request: GenerationRequest,
    snapshot: ScientificRecordSnapshot,
    opportunities: OpportunityDiscoveryResult,
) -> str:
    request_material = request.model_dump(mode="json", exclude={"author_brief", "regenerate"})
    request_material["author_brief_sha256"] = (
        canonical_sha256(request.author_brief, domain=b"cfdpaper-topic-author-brief-v1")
        if request.author_brief is not None
        else None
    )
    return canonical_sha256(
        {
            "request": request_material,
            "snapshot": snapshot.component_hashes,
            "aggregate_sha256": snapshot.aggregate_sha256,
            "opportunity_sha256": opportunity_envelope_sha256(opportunities),
            "generator_version": GENERATOR_VERSION,
            "prompt_version": PROMPT_CONTRACT_VERSION,
            "policy_version": REFINEMENT_POLICY_VERSION,
        },
        domain=b"cfdpaper-topic-semantic-reuse-v1",
    )


def generation_fingerprint(material: GenerationMaterial) -> str:
    return canonical_sha256(material, domain=b"cfdpaper-topic-generation-v1")


def next_generation_revision(
    previous: GenerationReport | None, *, semantic_reuse_key: str, regenerate: bool
) -> int:
    if previous is None:
        return 1
    if not regenerate and previous.semantic_reuse_key == semantic_reuse_key:
        return previous.generation_revision
    return previous.generation_revision + 1


def _source_provenance(snapshot: ScientificRecordSnapshot) -> tuple[SourceRecordProvenance, ...]:
    records = (
        *(("case", item.case_id, item) for item in snapshot.cases),
        *(("boundary", item.boundary_id, item) for item in snapshot.boundaries),
        *(("mesh", item.mesh_id, item) for item in snapshot.meshes),
        *(("field", item.field_id, item) for item in snapshot.fields),
        *(("qoi", item.qoi_id, item) for item in snapshot.qois),
        *(("evidence", item.evidence_id, item) for item in snapshot.evidence),
    )
    return tuple(
        sorted(
            (
                SourceRecordProvenance(
                    record_kind=kind,
                    record_id=record_id,
                    source_uri=item.source_uri,
                    source_hash=item.source_hash,
                    source_locator=item.locator,
                    stale=item.stale,
                )
                for kind, record_id, item in records
            ),
            key=lambda item: (item.record_kind, item.record_id),
        )
    )


def build_generation_report(
    *,
    request: GenerationRequest,
    snapshot: ScientificRecordSnapshot,
    opportunities: OpportunityDiscoveryResult,
    construction: CandidateConstructionResult,
    refinement: RefinementResult,
    generation_revision: int,
    generated_at: datetime,
    resolved_provider_name: str | None = None,
    resolved_provider_model: str | None = None,
    context_packet_sha256: str | None = None,
) -> GenerationReport:
    """Create a report whose semantic fields are completely derived from locked inputs."""

    _validate_refinement_against_construction(construction, refinement)
    opportunity_bytes = canonical_json_bytes(opportunities)
    candidate_bytes = canonical_json_bytes(refinement.candidate_input)
    opportunity_sha256 = opportunity_envelope_sha256(opportunities)
    if opportunity_sha256 != hashlib.sha256(opportunity_bytes).hexdigest():
        raise GenerationArtifactConflict(
            "canonical opportunity digest does not match artifact bytes"
        )
    candidate_sha256 = hashlib.sha256(candidate_bytes).hexdigest()
    reuse_key = semantic_reuse_key(request, snapshot, opportunities)
    opportunity_by_id = {item.opportunity_id: item for item in opportunities.opportunities}
    frame_by_topic = {
        item.topic_id: item.semantic_frame for item in refinement.accepted_refinements
    }
    skeleton_by_topic = {item.candidate.topic_id: item for item in construction.skeletons}
    provenance: list[CandidateProvenance] = []
    heuristics: list[TopicHeuristicRecord] = []
    for topic_id, opportunity_id in construction.topic_to_opportunity:
        opportunity = opportunity_by_id.get(opportunity_id)
        skeleton = skeleton_by_topic.get(topic_id)
        frame = frame_by_topic.get(topic_id)
        if opportunity is None or skeleton is None or frame is None:
            raise GenerationArtifactConflict("candidate construction is not reportable")
        provenance.append(
            CandidateProvenance(
                topic_id=topic_id,
                opportunity_id=opportunity_id,
                pattern=opportunity.pattern,
                case_ids=opportunity.case_ids,
                qoi_ids=opportunity.primary_qoi_ids,
                parameter_bindings=frame.parameter_bindings,
                trend_type=opportunity.trend_type,
                relation=opportunity.relation,
                claim_ceiling=opportunity.claim_ceiling.value,
                supporting_evidence_ids=opportunity.supporting_evidence_ids,
                semantic_signature_sha256=canonical_sha256(
                    opportunity.semantic_signature, domain=b"cfdpaper-opportunity-v1"
                ),
                ranking_reason_codes=(
                    f"pattern:{opportunity.pattern}",
                    f"ceiling:{opportunity.claim_ceiling.value}",
                    f"maturity:{opportunity.evidence_maturity.value}",
                ),
                figure_evidence_structure=skeleton.figure_evidence_structure,
                paper_spine_evidence_structure=tuple(
                    sorted(
                        {
                            "research-question",
                            *(f"support:{item}" for item in opportunity.supporting_evidence_ids),
                        }
                    )
                ),
                locked_candidate_sha256=hashlib.sha256(
                    _candidate_locked_fields(skeleton.candidate)
                ).hexdigest(),
            )
        )
        candidate = skeleton.candidate
        heuristics.append(
            TopicHeuristicRecord(
                topic_id=topic_id,
                significance=candidate.significance,
                novelty=candidate.novelty,
                maturity=opportunity.evidence_maturity.value,
                claim_ceiling=opportunity.claim_ceiling.value,
                defensible=opportunity.defensible,
            )
        )
    accepted = tuple(sorted(refinement.accepted_refinements, key=lambda item: item.topic_id))
    generation_mode: Literal["offline", "provider-refined", "offline-fallback"] = (
        "offline" if request.provider_mode == "offline" else refinement.mode
    )
    attempted_provider = any(
        value is not None
        for value in (resolved_provider_name, resolved_provider_model, context_packet_sha256)
    )
    if generation_mode == "provider-refined" or (
        generation_mode == "offline-fallback" and attempted_provider
    ):
        if (
            not resolved_provider_name
            or not resolved_provider_model
            or context_packet_sha256 is None
        ):
            raise GenerationArtifactConflict(
                "provider refinement must bind resolved provider metadata"
            )
    else:
        resolved_provider_name = "offline"
        resolved_provider_model = None
        context_packet_sha256 = None
    material = GenerationMaterial(
        semantic_reuse_key=reuse_key,
        generation_revision=generation_revision,
        requested_provider_mode=request.provider_mode,
        requested_provider_model=request.provider_model,
        resolved_provider_name=resolved_provider_name,
        resolved_provider_model=resolved_provider_model,
        context_packet_sha256=context_packet_sha256,
        opportunity_sha256=opportunity_sha256,
        candidate_sha256=candidate_sha256,
        accepted_refinement_hash=refinement.accepted_refinement_hash,
    )
    return GenerationReport(
        project_id=snapshot.project_id,
        scientific_snapshot_sha256=snapshot.aggregate_sha256,
        scientific_component_hashes=snapshot.component_hashes,
        semantic_reuse_key=reuse_key,
        generation_fingerprint=generation_fingerprint(material),
        generation_revision=generation_revision,
        generation_mode=generation_mode,
        generator_version=GENERATOR_VERSION,
        prompt_contract_version=PROMPT_CONTRACT_VERSION,
        refinement_policy_version=REFINEMENT_POLICY_VERSION,
        requested_provider_mode=request.provider_mode,
        requested_provider_model=request.provider_model,
        resolved_provider_name=material.resolved_provider_name,
        resolved_provider_model=material.resolved_provider_model,
        context_packet_sha256=context_packet_sha256,
        author_brief_sha256=(
            canonical_sha256(request.author_brief, domain=b"cfdpaper-topic-author-brief-v1")
            if request.author_brief is not None
            else None
        ),
        generated_at=generated_at,
        opportunity_sha256=opportunity_sha256,
        candidate_sha256=candidate_sha256,
        accepted_refinement_envelope=accepted,
        accepted_refinement_hash=refinement.accepted_refinement_hash,
        topic_to_opportunity=construction.topic_to_opportunity,
        candidate_provenance=tuple(sorted(provenance, key=lambda item: item.topic_id)),
        offline_heuristics=tuple(sorted(heuristics, key=lambda item: item.topic_id)),
        fallback_reasons=(
            refinement.rejection_reasons if generation_mode == "offline-fallback" else ()
        ),
        rejection_reasons=refinement.rejection_reasons,
        minimum_missing_data=construction.gaps,
        prohibited_inferences=tuple(
            sorted(
                {
                    item
                    for opportunity in opportunities.opportunities
                    for item in opportunity.prohibited_inferences
                }
            )
        ),
        source_record_provenance=_source_provenance(snapshot),
    )


def _candidate_locked_fields(candidate: object) -> bytes:
    payload = candidate.model_dump(mode="python")  # type: ignore[attr-defined]
    payload.pop("title", None)
    payload.pop("research_question", None)
    payload["supporting_evidence_ids"] = sorted(payload["supporting_evidence_ids"])
    payload["required_evidence_kinds"] = sorted(payload["required_evidence_kinds"])
    return canonical_json_bytes(payload)


def _validate_refinement_against_construction(
    construction: CandidateConstructionResult, refinement: RefinementResult
) -> None:
    refined = tuple(refinement.candidate_input.candidates)
    accepted = tuple(refinement.accepted_refinements)
    skeletons = tuple(construction.skeletons)
    if tuple(item.topic_id for item in refined) != tuple(
        item.topic_id for item in accepted
    ) or tuple(item.topic_id for item in refined) != tuple(
        item.candidate.topic_id for item in skeletons
    ):
        raise GenerationArtifactConflict("candidate refinement alignment mismatch")
    for candidate, accepted_item, skeleton in zip(refined, accepted, skeletons, strict=True):
        if (
            candidate.title != accepted_item.title
            or candidate.research_question != accepted_item.research_question
            or _candidate_locked_fields(candidate) != _candidate_locked_fields(skeleton.candidate)
        ):
            raise GenerationArtifactConflict(
                "candidate refinement fields do not match locked envelope"
            )


def _atomic_replace_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as stream:
            stream.write(content)
            stream.flush()
            try:
                os.fsync(stream.fileno())
            except OSError:
                pass
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _maybe_fail(failpoint: str | None, expected: str) -> None:
    if failpoint == expected:
        raise InjectedGenerationCrash(expected)


def _assert_report_digests(
    report: GenerationReport, opportunity_digest: str, candidate_digest: str
) -> None:
    if report.opportunity_sha256 != opportunity_digest:
        raise GenerationArtifactConflict("opportunity report hash mismatch")
    if report.candidate_sha256 != candidate_digest:
        raise GenerationArtifactConflict("candidate report hash mismatch")


def publish_generation_bundle(
    *,
    project_root: Path,
    cache: ContentAddressedCache,
    opportunities_bytes: bytes,
    candidates_bytes: bytes,
    report: GenerationReport,
    assert_plan_lock_held: Callable[[], bool],
    failpoint: str | None = None,
) -> CommittedGenerationBundle:
    """Publish cache-first and report-last; the caller owns the existing plan lock."""

    if not assert_plan_lock_held():
        raise GenerationArtifactConflict("plan lock must be held before artifact publication")
    opportunity_digest = hashlib.sha256(opportunities_bytes).hexdigest()
    candidate_digest = hashlib.sha256(candidates_bytes).hexdigest()
    _assert_report_digests(report, opportunity_digest, candidate_digest)
    _validate_publication_inputs(report, opportunities_bytes, candidates_bytes)
    if cache.put_bytes(opportunities_bytes) != cache.path_for(opportunity_digest):
        raise GenerationArtifactConflict("unexpected opportunity cache path")
    _maybe_fail(failpoint, "after-cache-opportunities")
    if cache.put_bytes(candidates_bytes) != cache.path_for(candidate_digest):
        raise GenerationArtifactConflict("unexpected candidate cache path")
    _maybe_fail(failpoint, "after-cache-candidates")
    _atomic_replace_bytes(opportunities_path(project_root), opportunities_bytes)
    _maybe_fail(failpoint, "after-replace-opportunities")
    _atomic_replace_bytes(generated_candidates_path(project_root), candidates_bytes)
    _maybe_fail(failpoint, "after-replace-candidates")
    _atomic_replace_bytes(generation_report_path(project_root), canonical_json_bytes(report))
    _maybe_fail(failpoint, "after-replace-generation-report")
    loaded = load_committed_generation_bundle(project_root, expected_project_id=report.project_id)
    if loaded is None:
        raise GenerationArtifactConflict("generation report marker disappeared during publication")
    return loaded


def _read_cached(cache: ContentAddressedCache, digest: str, *, kind: str) -> bytes:
    try:
        return cache.read_bytes(digest)
    except (CacheIntegrityError, FileNotFoundError, OSError) as error:
        raise GenerationArtifactConflict(f"{kind} cache is missing or corrupt") from error


def _validate_publication_inputs(
    report: GenerationReport, opportunities_bytes: bytes, candidates_bytes: bytes
) -> None:
    """Reject invalid bundle content before cache or fixed-output mutation."""

    try:
        opportunities = _parse_canonical_opportunities(opportunities_bytes)
        candidates = GeneratedCandidateEnvelope.model_validate_json(candidates_bytes)
    except ValueError as error:
        raise GenerationArtifactConflict("generation artifact is invalid") from error
    if canonical_json_bytes(candidates) != candidates_bytes:
        raise GenerationArtifactConflict("candidate artifact bytes are not canonical")
    _validate_scientific_alignment(report, opportunities, candidates)


def _validate_scientific_alignment(
    report: GenerationReport,
    opportunities: OpportunityDiscoveryResult,
    candidates: GeneratedCandidateEnvelope,
) -> None:
    if (
        canonical_sha256(
            tuple(sorted(report.accepted_refinement_envelope, key=lambda item: item.topic_id)),
            domain=b"cfdpaper-accepted-refinement-v1",
        )
        != report.accepted_refinement_hash
    ):
        raise GenerationArtifactConflict("accepted refinement hash mismatch")
    candidate_ids = tuple(item.topic_id for item in candidates.candidates)
    accepted_by_topic = {item.topic_id: item for item in report.accepted_refinement_envelope}
    if candidate_ids != tuple(accepted_by_topic):
        raise GenerationArtifactConflict("candidate and accepted refinement alignment mismatch")
    opportunity_by_id = {item.opportunity_id: item for item in opportunities.opportunities}
    mapping_by_topic = dict(report.topic_to_opportunity)
    heuristic_by_topic = {item.topic_id: item for item in report.offline_heuristics}
    for candidate in candidates.candidates:
        accepted = accepted_by_topic[candidate.topic_id]
        provenance = next(
            item for item in report.candidate_provenance if item.topic_id == candidate.topic_id
        )
        opportunity = opportunity_by_id.get(mapping_by_topic[candidate.topic_id])
        expected = build_generated_candidates((opportunity,)) if opportunity is not None else None
        if expected is None or len(expected.skeletons) != 1:
            raise GenerationArtifactConflict("candidate provenance cannot be reconstructed")
        expected_skeleton = expected.skeletons[0]
        expected_paper_spine = tuple(
            sorted(
                {
                    "research-question",
                    *(f"support:{item}" for item in opportunity.supporting_evidence_ids),
                }
            )
        )
        expected_ranking_reasons = tuple(
            sorted(
                (
                    f"pattern:{opportunity.pattern}",
                    f"ceiling:{opportunity.claim_ceiling.value}",
                    f"maturity:{opportunity.evidence_maturity.value}",
                )
            )
        )
        heuristic = heuristic_by_topic[candidate.topic_id]
        if opportunity is None or (
            candidate.title != accepted.title
            or candidate.research_question != accepted.research_question
            or provenance.opportunity_id != opportunity.opportunity_id
            or provenance.pattern != opportunity.pattern
            or provenance.case_ids != opportunity.case_ids
            or provenance.qoi_ids != opportunity.primary_qoi_ids
            or provenance.parameter_bindings != accepted.semantic_frame.parameter_bindings
            or provenance.trend_type != opportunity.trend_type
            or provenance.relation != opportunity.relation
            or provenance.claim_ceiling != opportunity.claim_ceiling.value
            or provenance.supporting_evidence_ids != opportunity.supporting_evidence_ids
            or provenance.semantic_signature_sha256
            != canonical_sha256(opportunity.semantic_signature, domain=b"cfdpaper-opportunity-v1")
            or provenance.locked_candidate_sha256
            != hashlib.sha256(_candidate_locked_fields(candidate)).hexdigest()
            or _candidate_locked_fields(candidate)
            != _candidate_locked_fields(expected_skeleton.candidate)
            or provenance.ranking_reason_codes != expected_ranking_reasons
            or provenance.figure_evidence_structure != expected_skeleton.figure_evidence_structure
            or provenance.paper_spine_evidence_structure != expected_paper_spine
            or heuristic.significance != expected_skeleton.candidate.significance
            or heuristic.novelty != expected_skeleton.candidate.novelty
            or heuristic.maturity != opportunity.evidence_maturity.value
            or heuristic.claim_ceiling != opportunity.claim_ceiling.value
            or heuristic.defensible != opportunity.defensible
        ):
            raise GenerationArtifactConflict(
                "candidate provenance does not match committed science"
            )


def _validate_report_and_artifacts(
    project_root: Path, report: GenerationReport, cache: ContentAddressedCache
) -> CommittedGenerationBundle:
    opportunity_path = opportunities_path(project_root)
    candidate_path = generated_candidates_path(project_root)
    if not opportunity_path.is_file() or not candidate_path.is_file():
        raise GenerationArtifactConflict("committed generation artifact is missing")
    opportunity_bytes = opportunity_path.read_bytes()
    candidate_bytes = candidate_path.read_bytes()
    opportunity_digest = hashlib.sha256(opportunity_bytes).hexdigest()
    candidate_digest = hashlib.sha256(candidate_bytes).hexdigest()
    if opportunity_digest != report.opportunity_sha256:
        raise GenerationArtifactConflict("opportunity artifact hash mismatch")
    if candidate_digest != report.candidate_sha256:
        raise GenerationArtifactConflict("candidate artifact hash mismatch")
    try:
        opportunities = _parse_canonical_opportunities(opportunity_bytes)
        candidates = GeneratedCandidateEnvelope.model_validate_json(candidate_bytes)
    except ValueError as error:
        raise GenerationArtifactConflict("committed generation artifact is invalid") from error
    if canonical_json_bytes(candidates) != candidate_bytes:
        raise GenerationArtifactConflict("candidate artifact bytes are not canonical")
    _validate_scientific_alignment(report, opportunities, candidates)
    cached_opportunities = _read_cached(cache, report.opportunity_sha256, kind="opportunity")
    cached_candidates = _read_cached(cache, report.candidate_sha256, kind="candidate")
    if cached_opportunities != opportunity_bytes or cached_candidates != candidate_bytes:
        raise GenerationArtifactConflict("committed artifacts do not match content-addressed cache")
    return CommittedGenerationBundle(
        report=report,
        opportunity_sha256=opportunity_digest,
        candidate_sha256=candidate_digest,
        opportunities=opportunities,
        candidates=candidates,
        cache=cache,
    )


def _parse_canonical_opportunities(content: bytes) -> OpportunityDiscoveryResult:
    """Rehydrate the strict opportunity models from their canonical JSON encoding."""

    try:
        raw = json.loads(content)
        raw_opportunities = raw["opportunities"]
        if not isinstance(raw_opportunities, list) or not isinstance(raw.get("gaps"), list):
            raise ValueError("invalid opportunity envelope")
        opportunities = tuple(_parse_opportunity(item) for item in raw_opportunities)
        result = OpportunityDiscoveryResult(opportunities=opportunities, gaps=tuple(raw["gaps"]))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("invalid canonical opportunity envelope") from error
    if canonical_json_bytes(result) != content:
        raise ValueError("opportunity artifact bytes are not canonical")
    return result


def _parse_opportunity(raw: object) -> ResearchOpportunity:
    if not isinstance(raw, dict):
        raise ValueError("invalid opportunity")
    signature_raw = raw["semantic_signature"]
    if not isinstance(signature_raw, dict):
        raise ValueError("invalid opportunity signature")
    relation = ScientificRelationFrame(**raw["relation"])
    signature = OpportunitySemanticSignature(
        pattern=signature_raw["pattern"],
        case_ids=tuple(signature_raw["case_ids"]),
        qoi_roles=tuple(signature_raw["qoi_roles"]),
        parameter_bindings=tuple(
            ParameterBinding(**item) for item in signature_raw["parameter_bindings"]
        ),
        trend_type=signature_raw["trend_type"],
        relation=ScientificRelationFrame(**signature_raw["relation"]),
        validation_sensitivity_contrast_ids=tuple(
            signature_raw["validation_sensitivity_contrast_ids"]
        ),
    )
    return ResearchOpportunity(
        opportunity_id=raw["opportunity_id"],
        pattern=raw["pattern"],
        case_ids=tuple(raw["case_ids"]),
        current_case_ids=tuple(raw["current_case_ids"]),
        qoi_ids=tuple(raw["qoi_ids"]),
        primary_qoi_ids=tuple(raw["primary_qoi_ids"]),
        supporting_evidence_ids=tuple(raw["supporting_evidence_ids"]),
        constraint_provenance_evidence_ids=tuple(raw["constraint_provenance_evidence_ids"]),
        unit_bindings=tuple(UnitBinding(**item) for item in raw["unit_bindings"]),
        comparability=raw["comparability"],
        trend_type=raw["trend_type"],
        relation=relation,
        evidence_maturity=EvidenceMaturity(raw["evidence_maturity"]),
        claim_ceiling=ClaimCeiling(raw["claim_ceiling"]),
        candidate_eligible=raw["candidate_eligible"],
        defensible=raw["defensible"],
        output_scope=raw["output_scope"],
        gaps=tuple(ScientificGap(**item) for item in raw["gaps"]),
        prohibited_inferences=tuple(raw["prohibited_inferences"]),
        rationale=raw["rationale"],
        required_evidence_kinds=tuple(raw["required_evidence_kinds"]),
        parameter_ids=tuple(raw["parameter_ids"]),
        varied_parameter_ids=tuple(raw["varied_parameter_ids"]),
        controlled_parameter_ids=tuple(raw["controlled_parameter_ids"]),
        parameter_bindings=tuple(ParameterBinding(**item) for item in raw["parameter_bindings"]),
        passed_gate_count=raw["passed_gate_count"],
        independent_validation_linked=raw["independent_validation_linked"],
        literature_gap_maturity=EvidenceMaturity(raw["literature_gap_maturity"]),
        semantic_signature=signature,
    )


def _load_generation_report_marker(project_root: Path) -> GenerationReport | None:
    report_path = generation_report_path(project_root)
    if not report_path.is_file():
        return None
    try:
        report_bytes = report_path.read_bytes()
        report = GenerationReport.model_validate_json(report_bytes)
    except ValueError as error:
        raise GenerationArtifactConflict("generation report is invalid") from error
    if canonical_json_bytes(report) != report_bytes:
        raise GenerationArtifactConflict("generation report bytes are not canonical")
    return report


def load_committed_generation_bundle(
    project_root: Path, *, expected_project_id: str
) -> CommittedGenerationBundle | None:
    report = _load_generation_report_marker(project_root)
    if report is None:
        return None
    if report.project_id != expected_project_id:
        raise GenerationArtifactConflict("generation project mismatch")
    return _validate_report_and_artifacts(project_root, report, ContentAddressedCache(project_root))


def recover_generation_bundle(
    *,
    project_root: Path,
    expected_project_id: str,
) -> CommittedGenerationBundle | None:
    report = _load_generation_report_marker(project_root)
    if report is None:
        for path in (opportunities_path(project_root), generated_candidates_path(project_root)):
            path.unlink(missing_ok=True)
        return None
    if report.project_id != expected_project_id:
        raise GenerationArtifactConflict("generation project mismatch")
    cache = ContentAddressedCache(project_root)
    opportunity_bytes = _read_cached(cache, report.opportunity_sha256, kind="opportunity")
    _atomic_replace_bytes(opportunities_path(project_root), opportunity_bytes)
    candidate_bytes = _read_cached(cache, report.candidate_sha256, kind="candidate")
    _atomic_replace_bytes(generated_candidates_path(project_root), candidate_bytes)
    return load_committed_generation_bundle(project_root, expected_project_id=expected_project_id)


__all__ = [
    "GENERATOR_VERSION",
    "CandidateProvenance",
    "CommittedGenerationBundle",
    "GenerationArtifactConflict",
    "GenerationArtifactHashes",
    "GenerationMaterial",
    "GenerationReport",
    "InjectedGenerationCrash",
    "SourceRecordProvenance",
    "TopicHeuristicRecord",
    "build_generation_report",
    "generated_candidates_path",
    "generation_fingerprint",
    "generation_report_path",
    "load_committed_generation_bundle",
    "next_generation_revision",
    "opportunity_envelope_sha256",
    "opportunities_path",
    "publish_generation_bundle",
    "recover_generation_bundle",
    "semantic_reuse_key",
]
