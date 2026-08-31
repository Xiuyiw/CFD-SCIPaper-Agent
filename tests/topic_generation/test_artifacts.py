"""TDD coverage for atomic, content-addressed topic-generation artifacts."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cfdpaper.cache import ContentAddressedCache
from cfdpaper.topic_generation.artifacts import (
    GENERATOR_VERSION,
    GenerationArtifactConflict,
    GenerationMaterial,
    GenerationReport,
    InjectedGenerationCrash,
    build_generation_report,
    generated_candidates_path,
    generation_fingerprint,
    generation_report_path,
    load_committed_generation_bundle,
    next_generation_revision,
    opportunity_envelope_sha256,
    publish_generation_bundle,
    recover_generation_bundle,
    semantic_reuse_key,
)
from cfdpaper.topic_generation.candidates import build_generated_candidates
from cfdpaper.topic_generation.canonical import canonical_json_bytes, canonical_sha256
from cfdpaper.topic_generation.models import GeneratedCandidateEnvelope, GenerationRequest
from cfdpaper.topic_generation.opportunities import (
    OpportunityDiscoveryResult,
    discover_research_opportunities,
)
from cfdpaper.topic_generation.refinement import (
    PROMPT_CONTRACT_VERSION,
    REFINEMENT_POLICY_VERSION,
    TopicSemanticFrame,
    build_semantic_frame,
    offline_refinement_result,
)
from cfdpaper.topic_generation.snapshot import (
    build_scientific_snapshot,
    load_scientific_snapshot,
)
from tests.topic_generation.factories import populated_scientific_store
from tests.topic_generation.test_candidates import opportunity_factory
from tests.topic_generation.test_opportunities import synthetic_snapshot


def _prepared_bundle(
    tmp_path: Path,
    *,
    revision: int,
    author_brief: str | None = None,
    generated_at: datetime | None = None,
    qoi_id: str = "qoi-response-a",
):
    store = populated_scientific_store(tmp_path)
    snapshot = load_scientific_snapshot(store)
    opportunity = opportunity_factory(
        case_ids=("case-a", "case-b"),
        binding_case_ids=("case-a", "case-b"),
        qoi_ids=(qoi_id,),
        supporting_evidence_ids=("evidence-qoi-a" if qoi_id.endswith("-a") else "evidence-qoi-b",),
    )
    opportunities = OpportunityDiscoveryResult(opportunities=(opportunity,), gaps=())
    construction = build_generated_candidates(opportunities.opportunities)
    frames = tuple(
        TopicSemanticFrame(
            topic_id=skeleton.candidate.topic_id,
            frame=build_semantic_frame(opportunity, skeleton.candidate),
        )
        for skeleton in construction.skeletons
    )
    refinement = offline_refinement_result(construction.skeletons, frames)
    request = GenerationRequest(author_brief=author_brief)
    report = build_generation_report(
        request=request,
        snapshot=snapshot,
        opportunities=opportunities,
        construction=construction,
        refinement=refinement,
        generation_revision=revision,
        generated_at=generated_at or datetime(2026, 8, 30, tzinfo=timezone.utc),
    )
    return (
        ContentAddressedCache(tmp_path),
        canonical_json_bytes(opportunities),
        canonical_json_bytes(refinement.candidate_input),
        report,
    )


def _publish_fixture_bundle(
    tmp_path: Path,
    *,
    revision: int,
    author_brief: str | None = None,
    failpoint: str | None = None,
    qoi_id: str = "qoi-response-a",
):
    cache, opportunities_bytes, candidates_bytes, report = _prepared_bundle(
        tmp_path, revision=revision, author_brief=author_brief, qoi_id=qoi_id
    )
    return publish_generation_bundle(
        project_root=tmp_path,
        cache=cache,
        opportunities_bytes=opportunities_bytes,
        candidates_bytes=candidates_bytes,
        report=report,
        assert_plan_lock_held=lambda: True,
        failpoint=failpoint,
    )


@pytest.mark.parametrize(
    "failpoint",
    [
        "after-cache-opportunities",
        "after-cache-candidates",
        "after-replace-opportunities",
        "after-replace-candidates",
        "after-replace-generation-report",
    ],
)
def test_retry_recovers_one_consistent_revision_after_each_generation_failpoint(
    tmp_path: Path, failpoint: str
) -> None:
    _publish_fixture_bundle(tmp_path, revision=1)
    with pytest.raises(InjectedGenerationCrash):
        _publish_fixture_bundle(
            tmp_path,
            revision=2,
            author_brief="revision B",
            qoi_id="qoi-response-b",
            failpoint=failpoint,
        )

    recovered = recover_generation_bundle(
        project_root=tmp_path, expected_project_id="snapshot-project"
    )

    assert recovered is not None
    assert recovered.report.generation_revision == (2 if failpoint.endswith("report") else 1)
    assert recovered.candidate_sha256 == recovered.report.candidate_sha256
    assert recovered.opportunity_sha256 == recovered.report.opportunity_sha256


def test_report_is_last_commit_marker_and_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    _publish_fixture_bundle(tmp_path, revision=1)
    generated_candidates_path(tmp_path).write_bytes(b"corrupt")

    with pytest.raises(GenerationArtifactConflict, match="candidate artifact hash mismatch"):
        load_committed_generation_bundle(tmp_path, expected_project_id="snapshot-project")


def test_recovery_restores_predecessor_after_cross_key_crash(tmp_path: Path) -> None:
    first = _publish_fixture_bundle(tmp_path, revision=1)
    with pytest.raises(InjectedGenerationCrash):
        _publish_fixture_bundle(
            tmp_path,
            revision=2,
            author_brief="B",
            qoi_id="qoi-response-b",
            failpoint="after-replace-candidates",
        )

    recovered = recover_generation_bundle(
        project_root=tmp_path, expected_project_id="snapshot-project"
    )

    assert recovered is not None
    assert recovered.report.generation_fingerprint == first.report.generation_fingerprint
    assert recovered.report.generation_revision == 1
    assert (
        next_generation_revision(recovered.report, semantic_reuse_key="b" * 64, regenerate=False)
        == 2
    )
    retried = _publish_fixture_bundle(
        tmp_path, revision=2, author_brief="B", qoi_id="qoi-response-b"
    )
    assert retried.report.generation_revision == recovered.report.generation_revision + 1
    assert retried.candidate_sha256 == retried.report.candidate_sha256
    assert retried.opportunity_sha256 == retried.report.opportunity_sha256
    assert retried.candidate_sha256 != first.candidate_sha256
    assert retried.opportunity_sha256 != first.opportunity_sha256


def test_report_rejects_unrecognized_generator_metadata(tmp_path: Path) -> None:
    _, _, _, report = _prepared_bundle(tmp_path, revision=1)
    raw = report.model_dump(mode="json")
    raw["generator_version"] = "unrecognized-generator"

    with pytest.raises(ValueError, match="generation version metadata"):
        GenerationReport.model_validate(raw)


def test_load_rejects_tampered_candidate_provenance(tmp_path: Path) -> None:
    published = _publish_fixture_bundle(tmp_path, revision=1)
    raw = published.report.model_dump(mode="json")
    raw["candidate_provenance"][0]["claim_ceiling"] = "engineering"
    generation_report_path(tmp_path).write_bytes(
        canonical_json_bytes(GenerationReport.model_validate(raw))
    )

    with pytest.raises(GenerationArtifactConflict, match="candidate provenance"):
        load_committed_generation_bundle(tmp_path, expected_project_id="snapshot-project")


def test_generation_material_excludes_timestamp_and_provider_randomness() -> None:
    common = dict(
        semantic_reuse_key="a" * 64,
        generation_revision=1,
        requested_provider_mode="auto",
        requested_provider_model="model",
        resolved_provider_name="provider",
        resolved_provider_model="model",
        context_packet_sha256=None,
        opportunity_sha256="b" * 64,
        candidate_sha256="c" * 64,
        accepted_refinement_hash="d" * 64,
    )
    first = GenerationMaterial(**common)
    second = GenerationMaterial(**common)

    assert generation_fingerprint(first) == generation_fingerprint(second)
    assert GENERATOR_VERSION == "hybrid-topic-generator-v1"


@pytest.mark.parametrize(
    "mutation",
    ("varied-parameter", "controlled-parameter", "boundary-evidence"),
)
def test_scientific_parameter_provenance_changes_post_discovery_reuse_material(
    mutation: str,
) -> None:
    baseline = synthetic_snapshot()
    baseline_opportunities = discover_research_opportunities(baseline)
    if mutation == "varied-parameter":
        changed_boundaries = tuple(
            boundary.model_copy(update={"values": {"parameter-varied": 9.0}})
            if boundary.boundary_id == "boundary-factor-a"
            else boundary
            for boundary in baseline.boundaries
        )
        changed_evidence = baseline.evidence
    elif mutation == "controlled-parameter":
        changed_boundaries = tuple(
            boundary.model_copy(update={"values": {"parameter-control": 2.0}})
            if boundary.boundary_id == "boundary-control-a"
            else boundary
            for boundary in baseline.boundaries
        )
        changed_evidence = baseline.evidence
    else:
        changed_boundaries = baseline.boundaries
        changed_evidence = tuple(
            evidence.model_copy(update={"locator": "$.unbound[0]"})
            if evidence.evidence_id == "evidence-boundary-factor-a"
            else evidence
            for evidence in baseline.evidence
        )
    changed = build_scientific_snapshot(
        project_id=baseline.project_id,
        cases=baseline.cases,
        boundaries=changed_boundaries,
        meshes=baseline.meshes,
        fields=baseline.fields,
        qois=baseline.qois,
        qoi_definition_assessments=baseline.qoi_definition_assessments,
        evidence=changed_evidence,
        claims=baseline.claims,
        assessments=baseline.assessments,
    )
    changed_opportunities = discover_research_opportunities(changed)
    request = GenerationRequest(provider_mode="offline")
    baseline_digest = opportunity_envelope_sha256(baseline_opportunities)
    changed_digest = opportunity_envelope_sha256(changed_opportunities)
    baseline_key = semantic_reuse_key(request, baseline, baseline_opportunities)
    changed_key = semantic_reuse_key(request, changed, changed_opportunities)
    common = dict(
        generation_revision=1,
        requested_provider_mode="offline",
        requested_provider_model=None,
        resolved_provider_name="offline",
        resolved_provider_model=None,
        context_packet_sha256=None,
        candidate_sha256="a" * 64,
        accepted_refinement_hash="b" * 64,
    )

    assert baseline.aggregate_sha256 != changed.aggregate_sha256
    assert baseline_digest != changed_digest
    assert canonical_json_bytes(baseline_opportunities) != canonical_json_bytes(
        changed_opportunities
    )
    assert baseline_key == canonical_sha256(
        {
            "request": {
                "provider_mode": "offline",
                "provider_model": None,
                "author_brief_sha256": None,
            },
            "snapshot": baseline.component_hashes,
            "aggregate_sha256": baseline.aggregate_sha256,
            "opportunity_sha256": baseline_digest,
            "generator_version": GENERATOR_VERSION,
            "prompt_version": PROMPT_CONTRACT_VERSION,
            "policy_version": REFINEMENT_POLICY_VERSION,
        },
        domain=b"cfdpaper-topic-semantic-reuse-v1",
    )
    assert baseline_key != changed_key
    assert generation_fingerprint(
        GenerationMaterial(
            semantic_reuse_key=baseline_key,
            opportunity_sha256=baseline_digest,
            **common,
        )
    ) != generation_fingerprint(
        GenerationMaterial(
            semantic_reuse_key=changed_key,
            opportunity_sha256=changed_digest,
            **common,
        )
    )


def test_report_and_reuse_key_share_the_artifact_opportunity_digest(tmp_path: Path) -> None:
    _, opportunity_bytes, _, report = _prepared_bundle(tmp_path, revision=1)

    assert report.opportunity_sha256 == hashlib.sha256(opportunity_bytes).hexdigest()


def test_explicit_offline_request_is_not_reported_as_provider_fallback(tmp_path: Path) -> None:
    _, _, _, report = _prepared_bundle(tmp_path, revision=1)

    assert report.generation_mode == "offline"
    assert report.resolved_provider_name == "offline"
    assert report.resolved_provider_model is None
    assert report.fallback_reasons == ()


def test_provider_refinement_binds_resolved_provider_and_context_material(tmp_path: Path) -> None:
    store = populated_scientific_store(tmp_path)
    snapshot = load_scientific_snapshot(store)
    opportunity = opportunity_factory()
    opportunities = OpportunityDiscoveryResult(opportunities=(opportunity,), gaps=())
    construction = build_generated_candidates(opportunities.opportunities)
    frames = tuple(
        TopicSemanticFrame(
            topic_id=skeleton.candidate.topic_id,
            frame=build_semantic_frame(opportunity, skeleton.candidate),
        )
        for skeleton in construction.skeletons
    )
    refinement = offline_refinement_result(construction.skeletons, frames).model_copy(
        update={"mode": "provider-refined"}
    )
    request = GenerationRequest(provider_mode="auto", provider_model="requested-model")
    kwargs = dict(
        request=request,
        snapshot=snapshot,
        opportunities=opportunities,
        construction=construction,
        refinement=refinement,
        generation_revision=1,
        generated_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
    )

    with pytest.raises(GenerationArtifactConflict, match="resolved provider metadata"):
        build_generation_report(
            **kwargs,
            resolved_provider_name="fake-provider",
            resolved_provider_model="resolved-model",
        )

    report = build_generation_report(
        **kwargs,
        resolved_provider_name="fake-provider",
        resolved_provider_model="resolved-model",
        context_packet_sha256="f" * 64,
    )

    assert report.generation_mode == "provider-refined"
    assert report.resolved_provider_name == "fake-provider"
    assert report.resolved_provider_model == "resolved-model"
    assert report.context_packet_sha256 == "f" * 64


def test_offline_fallback_distinguishes_unattempted_and_rejected_provider(tmp_path: Path) -> None:
    store = populated_scientific_store(tmp_path)
    snapshot = load_scientific_snapshot(store)
    opportunity = opportunity_factory()
    opportunities = OpportunityDiscoveryResult(opportunities=(opportunity,), gaps=())
    construction = build_generated_candidates(opportunities.opportunities)
    frames = tuple(
        TopicSemanticFrame(
            topic_id=skeleton.candidate.topic_id,
            frame=build_semantic_frame(opportunity, skeleton.candidate),
        )
        for skeleton in construction.skeletons
    )
    fallback = offline_refinement_result(construction.skeletons, frames).model_copy(
        update={"rejection_reasons": ("malformed-json",)}
    )
    kwargs = dict(
        request=GenerationRequest(provider_mode="auto", provider_model="requested-model"),
        snapshot=snapshot,
        opportunities=opportunities,
        construction=construction,
        refinement=fallback,
        generation_revision=1,
        generated_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
    )

    unattempted = build_generation_report(**kwargs)
    assert (unattempted.resolved_provider_name, unattempted.resolved_provider_model) == (
        "offline",
        None,
    )
    assert unattempted.context_packet_sha256 is None

    rejected = build_generation_report(
        **kwargs,
        resolved_provider_name="fake-provider",
        resolved_provider_model="resolved-model",
        context_packet_sha256="e" * 64,
    )
    assert (rejected.resolved_provider_name, rejected.resolved_provider_model) == (
        "fake-provider",
        "resolved-model",
    )
    assert rejected.context_packet_sha256 == "e" * 64


def test_report_construction_rejects_candidate_text_or_locked_field_mismatch(
    tmp_path: Path,
) -> None:
    store = populated_scientific_store(tmp_path)
    snapshot = load_scientific_snapshot(store)
    opportunity = opportunity_factory()
    opportunities = OpportunityDiscoveryResult(opportunities=(opportunity,), gaps=())
    construction = build_generated_candidates(opportunities.opportunities)
    frames = tuple(
        TopicSemanticFrame(
            topic_id=skeleton.candidate.topic_id,
            frame=build_semantic_frame(opportunity, skeleton.candidate),
        )
        for skeleton in construction.skeletons
    )
    refinement = offline_refinement_result(construction.skeletons, frames)
    altered = refinement.model_copy(
        update={
            "candidate_input": GeneratedCandidateEnvelope(
                candidates=(
                    refinement.candidate_input.candidates[0].model_copy(
                        update={"title": "Unbound title"}
                    ),
                )
            )
        }
    )

    with pytest.raises(GenerationArtifactConflict, match="candidate refinement fields"):
        build_generation_report(
            request=GenerationRequest(),
            snapshot=snapshot,
            opportunities=opportunities,
            construction=construction,
            refinement=altered,
            generation_revision=1,
            generated_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
        )


def test_report_rejects_duplicate_or_misaligned_topic_mapping(tmp_path: Path) -> None:
    _, _, _, report = _prepared_bundle(tmp_path, revision=1)
    raw = report.model_dump(mode="json")
    raw["topic_to_opportunity"] = [
        [report.topic_to_opportunity[0][0], report.topic_to_opportunity[0][1]],
        [report.topic_to_opportunity[0][0], "opp-0000000000000000"],
    ]

    with pytest.raises(ValueError, match="topic-to-opportunity"):
        GenerationReport.model_validate(raw)


def test_noncanonical_candidate_bytes_fail_closed_even_with_matching_report_hash(
    tmp_path: Path,
) -> None:
    published = _publish_fixture_bundle(tmp_path, revision=1)
    noncanonical = b" " + generated_candidates_path(tmp_path).read_bytes()
    candidate_sha256 = hashlib.sha256(noncanonical).hexdigest()
    material = GenerationMaterial(
        semantic_reuse_key=published.report.semantic_reuse_key,
        generation_revision=published.report.generation_revision,
        requested_provider_mode=published.report.requested_provider_mode,
        requested_provider_model=published.report.requested_provider_model,
        resolved_provider_name=published.report.resolved_provider_name,
        resolved_provider_model=published.report.resolved_provider_model,
        context_packet_sha256=published.report.context_packet_sha256,
        opportunity_sha256=published.report.opportunity_sha256,
        candidate_sha256=candidate_sha256,
        accepted_refinement_hash=published.report.accepted_refinement_hash,
    )
    raw = published.report.model_dump(mode="json")
    raw["candidate_sha256"] = candidate_sha256
    raw["generation_fingerprint"] = generation_fingerprint(material)
    altered_report = GenerationReport.model_validate(raw)
    published.cache.put_bytes(noncanonical)
    generated_candidates_path(tmp_path).write_bytes(noncanonical)
    generation_report_path(tmp_path).write_bytes(canonical_json_bytes(altered_report))

    with pytest.raises(
        GenerationArtifactConflict, match="candidate artifact bytes are not canonical"
    ):
        load_committed_generation_bundle(tmp_path, expected_project_id="snapshot-project")


def test_invalid_b_publish_preserves_a_marker_and_recovers_a(tmp_path: Path) -> None:
    first = _publish_fixture_bundle(tmp_path, revision=1)
    marker_a = generation_report_path(tmp_path).read_bytes()
    cache, opportunity_bytes, candidate_bytes, report_b = _prepared_bundle(
        tmp_path, revision=2, qoi_id="qoi-response-b"
    )
    noncanonical_b = b" " + candidate_bytes
    noncanonical_digest = hashlib.sha256(noncanonical_b).hexdigest()
    material_b = GenerationMaterial(
        semantic_reuse_key=report_b.semantic_reuse_key,
        generation_revision=report_b.generation_revision,
        requested_provider_mode=report_b.requested_provider_mode,
        requested_provider_model=report_b.requested_provider_model,
        resolved_provider_name=report_b.resolved_provider_name,
        resolved_provider_model=report_b.resolved_provider_model,
        context_packet_sha256=report_b.context_packet_sha256,
        opportunity_sha256=report_b.opportunity_sha256,
        candidate_sha256=noncanonical_digest,
        accepted_refinement_hash=report_b.accepted_refinement_hash,
    )
    raw_report_b = report_b.model_dump(mode="json")
    raw_report_b["candidate_sha256"] = noncanonical_digest
    raw_report_b["generation_fingerprint"] = generation_fingerprint(material_b)
    invalid_report_b = GenerationReport.model_validate(raw_report_b)

    with pytest.raises(
        GenerationArtifactConflict, match="candidate artifact bytes are not canonical"
    ):
        publish_generation_bundle(
            project_root=tmp_path,
            cache=cache,
            opportunities_bytes=opportunity_bytes,
            candidates_bytes=noncanonical_b,
            report=invalid_report_b,
            assert_plan_lock_held=lambda: True,
        )

    assert generation_report_path(tmp_path).read_bytes() == marker_a
    recovered = recover_generation_bundle(
        project_root=tmp_path, expected_project_id="snapshot-project"
    )
    assert recovered is not None
    assert recovered.report.generation_revision == 1
    assert recovered.candidate_sha256 == first.candidate_sha256


def test_noncanonical_report_marker_fails_closed(tmp_path: Path) -> None:
    _publish_fixture_bundle(tmp_path, revision=1)
    generation_report_path(tmp_path).write_bytes(
        b" " + generation_report_path(tmp_path).read_bytes()
    )

    with pytest.raises(GenerationArtifactConflict, match="report bytes are not canonical"):
        load_committed_generation_bundle(tmp_path, expected_project_id="snapshot-project")


def test_recovery_does_not_mutate_fixed_artifacts_for_noncanonical_report(tmp_path: Path) -> None:
    _publish_fixture_bundle(tmp_path, revision=1)
    before_opportunities = (
        tmp_path / ".cfdpaper/outputs/plan/research-opportunities.json"
    ).read_bytes()
    before_candidates = generated_candidates_path(tmp_path).read_bytes()
    generation_report_path(tmp_path).write_bytes(
        b" " + generation_report_path(tmp_path).read_bytes()
    )

    with pytest.raises(GenerationArtifactConflict, match="report bytes are not canonical"):
        recover_generation_bundle(project_root=tmp_path, expected_project_id="snapshot-project")

    assert (
        tmp_path / ".cfdpaper/outputs/plan/research-opportunities.json"
    ).read_bytes() == before_opportunities
    assert generated_candidates_path(tmp_path).read_bytes() == before_candidates


def test_load_rejects_candidate_locked_field_mutation(tmp_path: Path) -> None:
    published = _publish_fixture_bundle(tmp_path, revision=1)
    raw_candidates = generated_candidates_path(tmp_path).read_bytes()
    raw = GeneratedCandidateEnvelope.model_validate_json(raw_candidates).model_dump(mode="json")
    raw["candidates"][0]["supporting_evidence_ids"] = ["evidence-qoi-b"]
    altered_candidates = canonical_json_bytes(GeneratedCandidateEnvelope.model_validate(raw))
    altered_digest = hashlib.sha256(altered_candidates).hexdigest()
    material = GenerationMaterial(
        semantic_reuse_key=published.report.semantic_reuse_key,
        generation_revision=published.report.generation_revision,
        requested_provider_mode=published.report.requested_provider_mode,
        requested_provider_model=published.report.requested_provider_model,
        resolved_provider_name=published.report.resolved_provider_name,
        resolved_provider_model=published.report.resolved_provider_model,
        context_packet_sha256=published.report.context_packet_sha256,
        opportunity_sha256=published.report.opportunity_sha256,
        candidate_sha256=altered_digest,
        accepted_refinement_hash=published.report.accepted_refinement_hash,
    )
    report_raw = published.report.model_dump(mode="json")
    report_raw["candidate_sha256"] = altered_digest
    report_raw["generation_fingerprint"] = generation_fingerprint(material)
    report = GenerationReport.model_validate(report_raw)
    published.cache.put_bytes(altered_candidates)
    generated_candidates_path(tmp_path).write_bytes(altered_candidates)
    generation_report_path(tmp_path).write_bytes(canonical_json_bytes(report))

    with pytest.raises(GenerationArtifactConflict, match="candidate provenance"):
        load_committed_generation_bundle(tmp_path, expected_project_id="snapshot-project")


@pytest.mark.parametrize("field", ("provider_mode", "provider_model", "author_brief"))
def test_semantic_reuse_key_binds_requested_generation_inputs(tmp_path: Path, field: str) -> None:
    _, _, _, report = _prepared_bundle(tmp_path, revision=1)
    other = tmp_path / "other"
    other.mkdir()
    store = populated_scientific_store(other)
    snapshot = load_scientific_snapshot(store)
    opportunity = opportunity_factory()
    opportunities = OpportunityDiscoveryResult(opportunities=(opportunity,), gaps=())
    request = GenerationRequest()
    changed = request.model_copy(update={field: "local" if field == "provider_mode" else "changed"})

    assert semantic_reuse_key(request, snapshot, opportunities) != semantic_reuse_key(
        changed, snapshot, opportunities
    )
    assert report.generation_fingerprint


def test_report_binding_rejects_cross_project_and_missing_or_corrupt_cache(tmp_path: Path) -> None:
    published = _publish_fixture_bundle(tmp_path, revision=1)

    with pytest.raises(GenerationArtifactConflict, match="generation project mismatch"):
        load_committed_generation_bundle(tmp_path, expected_project_id="other-project")
    published.cache.path_for(published.report.candidate_sha256).unlink()
    with pytest.raises(GenerationArtifactConflict, match="candidate cache"):
        load_committed_generation_bundle(tmp_path, expected_project_id="snapshot-project")
    with pytest.raises(GenerationArtifactConflict, match="candidate cache"):
        recover_generation_bundle(project_root=tmp_path, expected_project_id="snapshot-project")
    published.cache.put_bytes(generated_candidates_path(tmp_path).read_bytes())
    published.cache.path_for(published.report.candidate_sha256).write_bytes(b"corrupt")
    with pytest.raises(GenerationArtifactConflict, match="candidate cache"):
        load_committed_generation_bundle(tmp_path, expected_project_id="snapshot-project")


def test_temp_files_are_ignored_and_plan_lock_precedes_cache_write(tmp_path: Path) -> None:
    cache, opportunities_bytes, candidates_bytes, report = _prepared_bundle(tmp_path, revision=1)
    order: list[str] = []
    original = cache.put_bytes

    def put_bytes(content: bytes) -> Path:
        order.append("cache")
        return original(content)

    cache.put_bytes = put_bytes  # type: ignore[method-assign]
    (tmp_path / ".cfdpaper" / "outputs" / "plan").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".cfdpaper" / "outputs" / "plan" / ".leftover.tmp").write_bytes(b"ignored")
    publish_generation_bundle(
        project_root=tmp_path,
        cache=cache,
        opportunities_bytes=opportunities_bytes,
        candidates_bytes=candidates_bytes,
        report=report,
        assert_plan_lock_held=lambda: order.append("plan-lock") or True,
    )

    assert order[:2] == ["plan-lock", "cache"]
    assert (
        load_committed_generation_bundle(tmp_path, expected_project_id="snapshot-project")
        is not None
    )
    assert generation_report_path(tmp_path).is_file()


def test_revision_rules_reuse_unchanged_and_increment_for_change_or_regeneration(
    tmp_path: Path,
) -> None:
    published = _publish_fixture_bundle(tmp_path, revision=1)

    assert (
        next_generation_revision(
            published.report,
            semantic_reuse_key=published.report.semantic_reuse_key,
            regenerate=False,
        )
        == 1
    )
    assert (
        next_generation_revision(published.report, semantic_reuse_key="e" * 64, regenerate=False)
        == 2
    )
    assert (
        next_generation_revision(
            published.report,
            semantic_reuse_key=published.report.semantic_reuse_key,
            regenerate=True,
        )
        == 2
    )
