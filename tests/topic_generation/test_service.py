"""TDD coverage for hybrid topic-generation orchestration."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from cfdpaper.cache import ContentAddressedCache
from cfdpaper.contracts import TaskContextPacket
from cfdpaper.state import initialize_project
from cfdpaper.storage import ProjectStore
from cfdpaper.topic_generation.artifacts import generated_candidates_path
from cfdpaper.topic_generation.canonical import canonical_json_bytes
from cfdpaper.topic_generation.models import GenerationRequest
from cfdpaper.topic_generation.opportunities import discover_research_opportunities
from cfdpaper.topic_generation.refinement import TopicSemanticFrame, build_semantic_frame
from cfdpaper.topic_generation.service import (
    TOPIC_REFINEMENT_TOKEN_BUDGET,
    ProviderExecutionError,
    ProviderUnavailableError,
    RegenerateRequiredError,
    TopicGenerationDependencies,
    TopicGenerationService,
    _build_refinement_context,
)
from tests.topic_generation.test_opportunities import synthetic_snapshot


@dataclass
class Counters:
    snapshot_loads: int = 0
    context_builds: int = 0
    provider_calls: int = 0
    provider_availability_checks: int = 0


class SnapshotLoader:
    def __init__(self, snapshot: object, counters: Counters) -> None:
        self.snapshot = snapshot
        self.counters = counters

    def __call__(self, _: ProjectStore) -> object:
        self.counters.snapshot_loads += 1
        return self.snapshot


class RecordingContextBuilder:
    def __init__(self, counters: Counters) -> None:
        self.counters = counters
        self.calls: list[dict[str, object]] = []
        self.extra_constraints: tuple[str, ...] = ()

    def build(self, **kwargs: object) -> TaskContextPacket:
        self.counters.context_builds += 1
        constraints = [*kwargs["constraints"], *self.extra_constraints]
        self.calls.append({**kwargs, "constraints": constraints})
        return TaskContextPacket(
            task=str(kwargs["task"]),
            token_budget=int(kwargs["token_budget"]),
            constraints=constraints,
            exclusions=list(kwargs["exclusions"]),
        )


class FakeProvider:
    name = "fake"
    model = "fake-model-v1"

    def __init__(self, response: str, counters: Counters, *, available: bool = True) -> None:
        self.response = response
        self.counters = counters
        self._available = available

    @property
    def configured(self) -> bool:
        return self._available

    @property
    def available(self) -> bool:
        self.counters.provider_availability_checks += 1
        return self._available

    def generate(self, _: str) -> str:
        self.counters.provider_calls += 1
        return self.response


class ExplodingProvider(FakeProvider):
    def generate(self, _: str) -> str:
        self.counters.provider_calls += 1
        raise RuntimeError("transport must not escape")


class UnavailableAtCallProvider(FakeProvider):
    def generate(self, _: str) -> str:
        self.counters.provider_calls += 1
        from cfdpaper.providers import ProviderUnavailable

        raise ProviderUnavailable("configured provider became unavailable")


def _valid_provider_response(snapshot: object) -> str:
    opportunities = discover_research_opportunities(snapshot)
    from cfdpaper.topic_generation.candidates import build_generated_candidates

    construction = build_generated_candidates(opportunities.opportunities)
    by_id = {item.opportunity_id: item for item in opportunities.opportunities}
    frames = tuple(
        TopicSemanticFrame(
            topic_id=skeleton.candidate.topic_id,
            frame=build_semantic_frame(by_id[skeleton.opportunity_id], skeleton.candidate),
        )
        for skeleton in construction.skeletons
    )
    skeletons = tuple(sorted(construction.skeletons, key=lambda item: item.candidate.topic_id))
    ordered_frames = tuple(sorted(frames, key=lambda item: item.topic_id))
    assert len(skeletons) == len(ordered_frames) == 1
    frame = ordered_frames[0].frame
    qois = " and ".join(
        reference.id.replace("-", " ")
        for reference in frame.subject_references
        if reference.kind == "qoi"
    )
    cases = ", ".join(
        reference.id.replace("-", " ")
        for reference in frame.contrast_references
        if reference.kind == "case"
    )
    varied = next(
        binding.id.replace("-", " ")
        for binding in frame.parameter_bindings
        if binding.role == "varied"
    )
    refinement = {
        "topic_id": skeletons[0].candidate.topic_id,
        "semantic_frame": frame.model_dump(mode="json"),
        "title": f"Hydrodynamic response of {qois} to {varied} across {cases}",
        "research_question": (
            f"Across sampled cases, how does {qois} increase with {varied} for {cases}?"
        ),
        "rationale": (
            f"Current structured evidence shows {qois} increases with {varied} "
            "across sampled cases "
            f"for {cases}."
        ),
        "differentiation": (
            f"The scientific question distinguishes how {qois} increases with {varied} "
            "from other candidate questions."
        ),
    }
    return json.dumps({"schema_version": 1, "refinements": [refinement]})


def _prepared_service(
    root: Path,
    *,
    snapshot: object | None = None,
    provider_factory: Callable[[Counters, object], FakeProvider | None] | None = None,
) -> tuple[TopicGenerationService, Counters, RecordingContextBuilder]:
    root.mkdir(parents=True, exist_ok=True)
    scientific_snapshot = snapshot or synthetic_snapshot(values=(1.0, 2.0, 3.0))
    initialize_project(root, scientific_snapshot.project_id)
    store = ProjectStore.open(root)
    counters = Counters()
    context_builder = RecordingContextBuilder(counters)
    provider = (
        provider_factory(counters, scientific_snapshot) if provider_factory is not None else None
    )
    dependencies = TopicGenerationDependencies(
        store=store,
        cache=ContentAddressedCache(root),
        context_builder=context_builder,
        provider=provider,
        provider_name=None if provider is None else provider.name,
        provider_model=None if provider is None else provider.model,
        snapshot_loader=SnapshotLoader(scientific_snapshot, counters),
    )
    return TopicGenerationService(root, dependencies), counters, context_builder


def test_matching_committed_generation_recovers_partial_output_and_reuses_before_resolution(
    tmp_path: Path,
) -> None:
    service, _, _ = _prepared_service(
        tmp_path,
        provider_factory=lambda counted, snapshot: FakeProvider(
            _valid_provider_response(snapshot), counted
        ),
    )
    generated = service.generate(GenerationRequest(provider_mode="auto"))
    generated_candidates_path(tmp_path).write_bytes(b"partial-output")
    reused, counters, context_builder = _prepared_service(
        tmp_path,
        provider_factory=lambda counted, snapshot: FakeProvider("provider-randomness", counted),
    )

    result = reused.generate(GenerationRequest(provider_mode="auto"))

    assert result.reused is True
    assert result.candidate_input == generated.candidate_input
    assert generated_candidates_path(tmp_path).read_bytes() != b"partial-output"
    assert counters.context_builds == 0
    assert counters.provider_calls == 0
    assert counters.provider_availability_checks == 0
    assert context_builder.calls == []


def test_offline_mode_does_not_evaluate_provider_or_context(tmp_path: Path) -> None:
    service, counters, context_builder = _prepared_service(
        tmp_path,
        provider_factory=lambda counted, snapshot: ExplodingProvider("", counted),
    )

    result = service.generate(GenerationRequest(provider_mode="offline"))

    assert result.mode == "offline"
    assert counters.context_builds == 0
    assert counters.provider_calls == 0
    assert counters.provider_availability_checks == 0
    assert context_builder.calls == []


def test_auto_unavailable_falls_back_but_explicit_unavailable_commits_nothing(
    tmp_path: Path,
) -> None:
    auto, _, _ = _prepared_service(
        tmp_path / "auto",
        provider_factory=lambda counted, snapshot: FakeProvider("", counted, available=False),
    )
    result = auto.generate(GenerationRequest(provider_mode="auto"))
    explicit, _, _ = _prepared_service(
        tmp_path / "explicit",
        provider_factory=lambda counted, snapshot: FakeProvider("", counted, available=False),
    )

    assert result.mode == "offline-fallback"
    assert result.report.fallback_reasons == ("provider-unavailable-auto",)
    with pytest.raises(ProviderUnavailableError, match="explicit-provider-unavailable"):
        explicit.generate(GenerationRequest(provider_mode="openai"))
    assert not (
        tmp_path / "explicit/.cfdpaper/outputs/plan/candidate-generation-report.json"
    ).exists()


def test_invalid_provider_content_commits_auditable_offline_fallback(tmp_path: Path) -> None:
    service, counters, context_builder = _prepared_service(
        tmp_path,
        provider_factory=lambda counted, snapshot: FakeProvider("not json", counted),
    )

    result = service.generate(GenerationRequest(provider_mode="auto"))

    assert result.mode == "offline-fallback"
    assert result.report.rejection_reasons
    assert counters.context_builds == counters.provider_calls == 1
    assert context_builder.calls[0]["token_budget"] == TOPIC_REFINEMENT_TOKEN_BUDGET


def test_context_only_packet_fact_does_not_expand_service_topic_whitelist(
    tmp_path: Path,
) -> None:
    def provider_with_context_only_fact(counters: Counters, snapshot: object) -> FakeProvider:
        response = json.loads(_valid_provider_response(snapshot))
        response["refinements"][0]["title"] += " auto-context-only"
        return FakeProvider(json.dumps(response), counters)

    service, counters, context_builder = _prepared_service(
        tmp_path, provider_factory=provider_with_context_only_fact
    )
    context_builder.extra_constraints = ("auto-context-only",)

    result = service.generate(GenerationRequest(provider_mode="auto"))

    assert result.mode == "offline-fallback"
    assert result.report.rejection_reasons == ("reference-out-of-bounds",)
    assert counters.context_builds == counters.provider_calls == 1
    assert "auto-context-only" in context_builder.calls[0]["constraints"]


@pytest.mark.parametrize(
    ("provider_factory", "reason"),
    (
        (
            lambda counted, snapshot: UnavailableAtCallProvider("", counted),
            "provider-unavailable-auto",
        ),
        (
            lambda counted, snapshot: ExplodingProvider("", counted),
            "provider-exception-auto",
        ),
    ),
)
def test_attempted_auto_provider_failures_retain_auditable_resolution_metadata(
    tmp_path: Path,
    provider_factory: Callable[[Counters, object], FakeProvider],
    reason: str,
) -> None:
    service, counters, context_builder = _prepared_service(
        tmp_path, provider_factory=provider_factory
    )

    result = service.generate(GenerationRequest(provider_mode="auto"))

    assert result.mode == "offline-fallback"
    assert result.report.fallback_reasons == (reason,)
    assert result.report.resolved_provider_name == "fake"
    assert result.report.resolved_provider_model == "fake-model-v1"
    assert result.report.context_packet_sha256 is not None
    assert counters.context_builds == counters.provider_calls == 1
    assert len(context_builder.calls) == 1


def test_explicit_fake_provider_refines_once_with_complete_bounded_context(tmp_path: Path) -> None:
    scientific_snapshot = synthetic_snapshot(values=(1.0, 2.0, 3.0))
    service, counters, context_builder = _prepared_service(
        tmp_path,
        snapshot=scientific_snapshot,
        provider_factory=lambda counted, snapshot: FakeProvider(
            _valid_provider_response(snapshot), counted
        ),
    )

    result = service.generate(
        GenerationRequest(provider_mode="openai", provider_model="fake-model-v1")
    )

    discovered = discover_research_opportunities(scientific_snapshot)
    canonical_opportunities = tuple(
        sorted(discovered.opportunities, key=lambda item: item.opportunity_id)
    )
    expected_query = "\n".join(item.rationale for item in canonical_opportunities)
    expected_constraint_set: set[str] = set()
    for item in canonical_opportunities:
        expected_constraint_set.update(
            {
                f"{item.opportunity_id}:pattern={item.pattern}",
                f"{item.opportunity_id}:trend={item.trend_type}",
                f"{item.opportunity_id}:claim-ceiling={item.claim_ceiling.value}",
                *(
                    f"{item.opportunity_id}:reference={reference_id}"
                    for reference_id in (
                        *item.case_ids,
                        *item.qoi_ids,
                        *item.parameter_ids,
                        *item.supporting_evidence_ids,
                    )
                ),
                *(
                    f"{item.opportunity_id}:unit-binding="
                    f"{canonical_json_bytes(binding).decode('utf-8')}"
                    for binding in item.unit_bindings
                ),
                *(
                    f"{item.opportunity_id}:parameter-binding="
                    f"{canonical_json_bytes(binding).decode('utf-8')}"
                    for binding in item.parameter_bindings
                ),
            }
        )
    expected_constraints = sorted(expected_constraint_set)
    expected_exclusions = sorted(
        {inference for item in canonical_opportunities for inference in item.prohibited_inferences}
    )
    call = context_builder.calls[0]
    repeat_builder = RecordingContextBuilder(Counters())
    first_packet, first_hash = _build_refinement_context(repeat_builder, canonical_opportunities)
    second_packet, second_hash = _build_refinement_context(repeat_builder, canonical_opportunities)

    assert result.mode == "provider-refined"
    assert counters.context_builds == counters.provider_calls == 1
    assert call["task"] == "topic-candidate-deepening"
    assert call["query"] == expected_query
    assert TOPIC_REFINEMENT_TOKEN_BUDGET == 4096
    assert call["token_budget"] == 4096
    assert call["constraints"] == expected_constraints
    assert call["exclusions"] == expected_exclusions
    assert first_packet == second_packet
    assert first_hash == second_hash == result.report.context_packet_sha256


def test_mode_model_and_author_brief_changes_require_regenerate_before_provider_resolution(
    tmp_path: Path,
) -> None:
    service, _, _ = _prepared_service(tmp_path)
    service.generate(GenerationRequest(provider_mode="offline"))
    changed, counters, context_builder = _prepared_service(
        tmp_path,
        provider_factory=lambda counted, snapshot: FakeProvider("not json", counted),
    )

    with pytest.raises(RegenerateRequiredError, match="requires-regenerate"):
        changed.generate(GenerationRequest(provider_mode="auto"))
    with pytest.raises(RegenerateRequiredError, match="requires-regenerate"):
        changed.generate(GenerationRequest(provider_mode="offline", author_brief="focus response"))
    assert counters.context_builds == counters.provider_calls == 0
    assert context_builder.calls == []


def test_provider_model_only_change_requires_regenerate_before_provider_resolution(
    tmp_path: Path,
) -> None:
    first, _, _ = _prepared_service(
        tmp_path,
        provider_factory=lambda counted, snapshot: FakeProvider(
            _valid_provider_response(snapshot), counted
        ),
    )
    first.generate(GenerationRequest(provider_mode="auto", provider_model="model-a"))
    changed, counters, context_builder = _prepared_service(
        tmp_path,
        provider_factory=lambda counted, snapshot: FakeProvider("not json", counted),
    )

    with pytest.raises(
        RegenerateRequiredError, match="generation-input-change-requires-regenerate"
    ):
        changed.generate(GenerationRequest(provider_mode="auto", provider_model="model-b"))

    assert counters.provider_availability_checks == 0
    assert counters.context_builds == counters.provider_calls == 0
    assert context_builder.calls == []


def test_scientific_change_and_explicit_regenerate_create_one_new_revision(tmp_path: Path) -> None:
    service, _, _ = _prepared_service(tmp_path)
    first = service.generate(GenerationRequest(provider_mode="offline"))
    changed_snapshot = synthetic_snapshot(values=(2.0, 3.0, 4.0), second_qoi_values=(5.0, 6.0, 7.0))
    changed, _, _ = _prepared_service(tmp_path, snapshot=changed_snapshot)
    second = changed.generate(GenerationRequest(provider_mode="offline"))
    third = changed.generate(GenerationRequest(provider_mode="offline", regenerate=True))
    reused = changed.generate(GenerationRequest(provider_mode="offline"))

    assert second.report.generation_revision == first.report.generation_revision + 1
    assert third.report.generation_revision == second.report.generation_revision + 1
    assert reused.reused is True
    assert reused.report.generation_revision == third.report.generation_revision


def test_provider_exception_and_missing_science_fail_closed_without_padding(tmp_path: Path) -> None:
    explicit, _, _ = _prepared_service(
        tmp_path / "explicit",
        provider_factory=lambda counted, snapshot: ExplodingProvider("", counted),
    )
    missing, _, _ = _prepared_service(
        tmp_path / "missing", snapshot=synthetic_snapshot(include_primary=False)
    )

    with pytest.raises(ProviderExecutionError, match="explicit-provider-failed"):
        explicit.generate(GenerationRequest(provider_mode="openai"))
    result = missing.generate(GenerationRequest(provider_mode="offline"))

    assert not (
        tmp_path / "explicit/.cfdpaper/outputs/plan/candidate-generation-report.json"
    ).exists()
    assert result.outcome == "missing-evidence"
    assert len(result.candidate_input.candidates) < 2
    assert result.minimum_missing_data == tuple(sorted(set(result.minimum_missing_data)))
