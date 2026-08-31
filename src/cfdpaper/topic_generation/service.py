"""Dependency-injected orchestration for hybrid topic generation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from cfdpaper.cache import ContentAddressedCache
from cfdpaper.contracts import TaskContextPacket
from cfdpaper.providers import AIProvider, ProviderUnavailable
from cfdpaper.retrieval import TaskContextBuilder
from cfdpaper.storage import ProjectStore
from cfdpaper.topic_generation.artifacts import (
    CommittedGenerationBundle,
    GenerationReport,
    build_generation_report,
    next_generation_revision,
    publish_generation_bundle,
    recover_generation_bundle,
    semantic_reuse_key,
)
from cfdpaper.topic_generation.candidates import (
    CandidateConstructionResult,
    CandidateSkeleton,
    build_generated_candidates,
)
from cfdpaper.topic_generation.canonical import canonical_json_bytes, canonical_sha256
from cfdpaper.topic_generation.models import (
    GeneratedCandidateEnvelope,
    GenerationModel,
    GenerationRequest,
)
from cfdpaper.topic_generation.opportunities import (
    OpportunityDiscoveryResult,
    ResearchOpportunity,
    discover_research_opportunities,
)
from cfdpaper.topic_generation.refinement import (
    RefinementResult,
    TopicSemanticFrame,
    build_semantic_frame,
    offline_refinement_result,
    refine_candidate_wording,
)
from cfdpaper.topic_generation.snapshot import ScientificRecordSnapshot, load_scientific_snapshot

TOPIC_REFINEMENT_TOKEN_BUDGET = 4096


class RegenerateRequiredError(RuntimeError):
    """A non-scientific generation input changed without explicit regeneration."""


class ProviderUnavailableError(RuntimeError):
    """The specifically requested provider cannot be used without a fallback."""


class ProviderExecutionError(RuntimeError):
    """A specifically requested provider failed before publication."""


@dataclass(frozen=True)
class TopicGenerationDependencies:
    store: ProjectStore
    cache: ContentAddressedCache
    context_builder: TaskContextBuilder
    provider: AIProvider | None = None
    provider_name: str | None = None
    provider_model: str | None = None
    snapshot_loader: Callable[[ProjectStore], ScientificRecordSnapshot] = load_scientific_snapshot
    assert_plan_lock_held: Callable[[], bool] = field(default=lambda: True)


class GenerationExecution(GenerationModel):
    candidate_input: GeneratedCandidateEnvelope
    opportunities: OpportunityDiscoveryResult
    report: GenerationReport
    reused: bool
    mode: str
    outcome: Literal["generated", "missing-evidence"]
    minimum_missing_data: tuple[str, ...]

    @classmethod
    def from_reused(cls, bundle: CommittedGenerationBundle) -> GenerationExecution:
        return cls(
            candidate_input=bundle.candidates,
            opportunities=bundle.opportunities,
            report=bundle.report,
            reused=True,
            mode=bundle.report.generation_mode,
            outcome=("generated" if bundle.candidates.candidates else "missing-evidence"),
            minimum_missing_data=tuple(sorted(set(bundle.report.minimum_missing_data))),
        )


class TopicGenerationService:
    """Run deterministic topic generation before optional bounded wording refinement."""

    def __init__(self, root: Path, dependencies: TopicGenerationDependencies) -> None:
        self.root = root.expanduser().resolve()
        self.dependencies = dependencies

    def generate(self, request: GenerationRequest) -> GenerationExecution:
        snapshot = self.dependencies.snapshot_loader(self.dependencies.store)
        opportunities = discover_research_opportunities(snapshot)
        reuse_key = semantic_reuse_key(request, snapshot, opportunities)
        committed = recover_generation_bundle(
            project_root=self.root,
            expected_project_id=snapshot.project_id,
        )
        if (
            committed is not None
            and committed.report.semantic_reuse_key == reuse_key
            and not request.regenerate
        ):
            return GenerationExecution.from_reused(committed)
        if self._requires_regenerate(request, snapshot, committed):
            raise RegenerateRequiredError("generation-input-change-requires-regenerate")
        return self._generate_new(request, snapshot, opportunities, reuse_key, committed)

    def _requires_regenerate(
        self,
        request: GenerationRequest,
        snapshot: ScientificRecordSnapshot,
        committed: CommittedGenerationBundle | None,
    ) -> bool:
        if committed is None or request.regenerate:
            return False
        report = committed.report
        if report.scientific_component_hashes != snapshot.component_hashes:
            return False
        requested_author_brief_hash = (
            canonical_sha256(request.author_brief, domain=b"cfdpaper-topic-author-brief-v1")
            if request.author_brief is not None
            else None
        )
        return (
            report.requested_provider_mode != request.provider_mode
            or report.requested_provider_model != request.provider_model
            or report.author_brief_sha256 != requested_author_brief_hash
        )

    def _generate_new(
        self,
        request: GenerationRequest,
        snapshot: ScientificRecordSnapshot,
        opportunities: OpportunityDiscoveryResult,
        reuse_key: str,
        committed: CommittedGenerationBundle | None,
    ) -> GenerationExecution:
        construction = _canonical_construction(
            build_generated_candidates(opportunities.opportunities)
        )
        frames = _semantic_frames(construction.skeletons, opportunities.opportunities)
        refinement, provider_metadata = self._refine(
            request, construction.skeletons, frames, opportunities.opportunities, reuse_key
        )
        revision = next_generation_revision(
            None if committed is None else committed.report,
            semantic_reuse_key=reuse_key,
            regenerate=request.regenerate,
        )
        report = build_generation_report(
            request=request,
            snapshot=snapshot,
            opportunities=opportunities,
            construction=construction,
            refinement=refinement,
            generation_revision=revision,
            generated_at=datetime.now(timezone.utc),
            **provider_metadata,
        )
        bundle = publish_generation_bundle(
            project_root=self.root,
            cache=self.dependencies.cache,
            opportunities_bytes=canonical_json_bytes(opportunities),
            candidates_bytes=canonical_json_bytes(refinement.candidate_input),
            report=report,
            assert_plan_lock_held=self.dependencies.assert_plan_lock_held,
        )
        return GenerationExecution(
            candidate_input=bundle.candidates,
            opportunities=bundle.opportunities,
            report=bundle.report,
            reused=False,
            mode=bundle.report.generation_mode,
            outcome=("generated" if bundle.candidates.candidates else "missing-evidence"),
            minimum_missing_data=tuple(sorted(set(bundle.report.minimum_missing_data))),
        )

    def _refine(
        self,
        request: GenerationRequest,
        skeletons: tuple[CandidateSkeleton, ...],
        frames: tuple[TopicSemanticFrame, ...],
        opportunities: tuple[ResearchOpportunity, ...],
        reuse_key: str,
    ) -> tuple[RefinementResult, dict[str, str | None]]:
        offline = offline_refinement_result(skeletons, frames)
        if request.provider_mode == "offline":
            return offline, {}
        provider = self.dependencies.provider
        if provider is None or not provider.available:
            if request.provider_mode == "auto":
                return _offline_with_reason(offline, "provider-unavailable-auto"), {}
            raise ProviderUnavailableError("explicit-provider-unavailable")
        provider_name = self.dependencies.provider_name or provider.name
        provider_model = self.dependencies.provider_model or getattr(provider, "model", None)
        if not provider_name or not provider_model:
            if request.provider_mode == "auto":
                return _offline_with_reason(offline, "provider-unavailable-auto"), {}
            raise ProviderUnavailableError("explicit-provider-unavailable")
        packet, packet_sha256 = _build_refinement_context(
            self.dependencies.context_builder,
            opportunities,
        )
        try:
            refined = refine_candidate_wording(
                skeletons=skeletons,
                frames=frames,
                semantic_reuse_key=reuse_key,
                context_packet=packet,
                provider=provider,
            )
        except ProviderUnavailable as error:
            if request.provider_mode == "auto":
                return _offline_with_reason(offline, "provider-unavailable-auto"), {
                    "resolved_provider_name": provider_name,
                    "resolved_provider_model": provider_model,
                    "context_packet_sha256": packet_sha256,
                }
            raise ProviderUnavailableError("explicit-provider-unavailable") from error
        except Exception as error:
            if request.provider_mode == "auto":
                return _offline_with_reason(offline, "provider-exception-auto"), {
                    "resolved_provider_name": provider_name,
                    "resolved_provider_model": provider_model,
                    "context_packet_sha256": packet_sha256,
                }
            raise ProviderExecutionError("explicit-provider-failed") from error
        return refined, {
            "resolved_provider_name": provider_name,
            "resolved_provider_model": provider_model,
            "context_packet_sha256": packet_sha256,
        }


def _semantic_frames(
    skeletons: tuple[CandidateSkeleton, ...], opportunities: tuple[ResearchOpportunity, ...]
) -> tuple[TopicSemanticFrame, ...]:
    by_id = {item.opportunity_id: item for item in opportunities}
    frames: list[TopicSemanticFrame] = []
    for skeleton in skeletons:
        opportunity = by_id.get(skeleton.opportunity_id)
        if opportunity is None:
            raise ValueError("candidate skeleton does not map to a discovered opportunity")
        frames.append(
            TopicSemanticFrame(
                topic_id=skeleton.candidate.topic_id,
                frame=build_semantic_frame(opportunity, skeleton.candidate),
            )
        )
    return tuple(frames)


def _canonical_construction(raw: CandidateConstructionResult) -> CandidateConstructionResult:
    skeletons = tuple(sorted(raw.skeletons, key=lambda item: item.candidate.topic_id))
    return CandidateConstructionResult(
        candidate_input=GeneratedCandidateEnvelope(
            candidates=tuple(item.candidate for item in skeletons)
        ),
        skeletons=skeletons,
        topic_to_opportunity=raw.topic_to_opportunity,
        gaps=raw.gaps,
    )


def _offline_with_reason(offline: RefinementResult, reason: str) -> RefinementResult:
    return RefinementResult.model_validate(
        offline.model_dump(mode="python") | {"rejection_reasons": (reason,)}, strict=True
    )


def _build_refinement_context(
    builder: TaskContextBuilder,
    opportunities: tuple[ResearchOpportunity, ...],
) -> tuple[TaskContextPacket, str]:
    synopsis = "\n".join(item.rationale for item in opportunities)
    constraints_set: set[str] = set()
    for opportunity in opportunities:
        constraints_set.update(
            {
                f"{opportunity.opportunity_id}:pattern={opportunity.pattern}",
                f"{opportunity.opportunity_id}:trend={opportunity.trend_type}",
                f"{opportunity.opportunity_id}:claim-ceiling={opportunity.claim_ceiling.value}",
                *(
                    f"{opportunity.opportunity_id}:reference={reference_id}"
                    for reference_id in (
                        *opportunity.case_ids,
                        *opportunity.qoi_ids,
                        *opportunity.parameter_ids,
                        *opportunity.supporting_evidence_ids,
                    )
                ),
                *(
                    f"{opportunity.opportunity_id}:unit-binding="
                    f"{canonical_json_bytes(binding).decode('utf-8')}"
                    for binding in opportunity.unit_bindings
                ),
                *(
                    f"{opportunity.opportunity_id}:parameter-binding="
                    f"{canonical_json_bytes(binding).decode('utf-8')}"
                    for binding in opportunity.parameter_bindings
                ),
            }
        )
    exclusions = sorted(
        {
            inference
            for opportunity in opportunities
            for inference in opportunity.prohibited_inferences
        }
    )
    packet = builder.build(
        task="topic-candidate-deepening",
        query=synopsis,
        token_budget=TOPIC_REFINEMENT_TOKEN_BUDGET,
        constraints=sorted(constraints_set),
        exclusions=exclusions,
    )
    return packet, canonical_sha256(packet, domain=b"cfdpaper-topic-context-packet-v1")


__all__ = [
    "GenerationExecution",
    "ProviderExecutionError",
    "ProviderUnavailableError",
    "RegenerateRequiredError",
    "TOPIC_REFINEMENT_TOKEN_BUDGET",
    "TopicGenerationDependencies",
    "TopicGenerationService",
]
