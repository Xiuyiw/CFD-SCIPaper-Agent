"""TDD coverage for bounded, useful provider wording refinement."""

from __future__ import annotations

import json

import pytest

from cfdpaper.contracts import TaskContextPacket
from cfdpaper.topic_generation.candidates import build_generated_candidates
from cfdpaper.topic_generation.models import GeneratedCandidateEnvelope, ScientificRelationFrame
from cfdpaper.topic_generation.refinement import (  # noqa: F401
    PROMPT_CONTRACT_VERSION,  # noqa: F401
    REFINEMENT_POLICY_VERSION,
    AcceptedRefinement,
    TopicSemanticFrame,
    _canonical_unit,
    bounded_scientific_relation_preserved,
    build_semantic_frame,
    refine_candidate_wording,
    wording_fact_catalog_for,
)
from tests.topic_generation.test_candidates import opportunity_factory


class FakeProvider:
    name = "fake"
    model = "fake-science-v1"

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0
        self.prompts: list[str] = []

    @property
    def configured(self) -> bool:
        return True

    @property
    def available(self) -> bool:
        return True

    def generate(self, prompt: str) -> str:
        self.calls += 1
        self.prompts.append(prompt)
        assert REFINEMENT_POLICY_VERSION in prompt
        return self.response


def _context_packet() -> TaskContextPacket:
    return TaskContextPacket(task="topic-refinement", token_budget=512)


def _skeletons_and_frames() -> tuple[tuple[object, ...], tuple[TopicSemanticFrame, ...]]:
    opportunities = (
        opportunity_factory(
            pattern="matched-comparison",
            case_ids=("case-reference", "case-variant"),
            binding_case_ids=("case-reference", "case-variant"),
            qoi_ids=("qoi-pressure",),
            supporting_evidence_ids=("evidence-pressure",),
        ),
        opportunity_factory(
            pattern="ordered-parameter-response",
            case_ids=("case-high", "case-low", "case-mid"),
            binding_case_ids=("case-high", "case-low", "case-mid"),
            qoi_ids=("qoi-temperature",),
            supporting_evidence_ids=("evidence-temperature",),
        ),
    )
    built = build_generated_candidates(opportunities)
    by_opportunity = {item.opportunity_id: item for item in opportunities}
    frames = tuple(
        TopicSemanticFrame(
            topic_id=skeleton.candidate.topic_id,
            frame=build_semantic_frame(by_opportunity[skeleton.opportunity_id], skeleton.candidate),
        )
        for skeleton in built.skeletons
    )
    return built.skeletons, frames


def _valid_response(skeletons: tuple[object, ...], frames: tuple[TopicSemanticFrame, ...]) -> str:
    frame_by_topic = {item.topic_id: item.frame for item in frames}
    refinements = []
    for skeleton in skeletons:
        candidate = skeleton.candidate
        frame = frame_by_topic[candidate.topic_id]
        qois = [
            item.id.replace("_", " ").replace("-", " ")
            for item in frame.subject_references
            if item.kind == "qoi"
        ]
        cases = [
            item.id.replace("_", " ").replace("-", " ")
            for item in frame.contrast_references
            if item.kind == "case"
        ]
        varied = next(
            item.id.replace("_", " ").replace("-", " ")
            for item in frame.parameter_bindings
            if item.role == "varied"
        )
        primary, secondary = qois[0], (qois[1] if len(qois) > 1 else qois[0])
        contrast = ", ".join(cases)
        if frame.relation.relation_class == "difference":
            title = (
                f"Hydrodynamic comparison of {primary} in the reference and variant cases "
                f"for {varied}"
            )
            question = (
                f"Across two sampled cases, does the reference differ from the variant "
                f"in {primary} for {varied}?"
            )
            rationale = (
                f"Current structured evidence shows the reference differs from the variant "
                f"in {primary} for {varied} across two sampled cases."
            )
            differentiation = (
                f"The scientific question distinguishes how the reference differs from the "
                f"variant in {primary} from the other candidate."
            )
        elif frame.relation.relation_class == "ordered-response":
            title = f"Hydrodynamic response of {primary} to {varied} across {contrast}"
            question = (
                f"Across sampled cases, how does {primary} increase with {varied} for {contrast}?"
            )
            rationale = (
                f"Current structured evidence shows {primary} increases with {varied} "
                f"across sampled cases for {contrast}."
            )
            differentiation = (
                f"The scientific question distinguishes how {primary} increases with {varied} "
                "from the other candidate."
            )
        elif frame.relation.relation_class == "coupled-association":
            title = (
                f"Interdependent hydrodynamic response of {primary} and {secondary} "
                f"across {contrast}"
            )
            question = (
                f"Across sampled cases, how does {primary} co-vary with {secondary} for {contrast}?"
            )
            rationale = (
                f"Current structured evidence indicates that {primary} is positively associated "
                f"with {secondary} across sampled cases for {contrast} and {varied}."
            )
            differentiation = (
                f"The scientific question distinguishes current structured evidence that {primary} "
                f"is positively associated with {secondary} from the other candidate."
            )
        else:
            title = f"Hydrodynamic robustness of {primary} across the validation contrast"
            question = (
                f"Across the validation set, is {primary} robust across the validation contrast "
                f"for {varied}?"
            )
            rationale = (
                f"Current structured evidence shows {primary} is robust across the validation "
                f"contrast in the validation set for {varied}."
            )
            differentiation = (
                f"The scientific question distinguishes current structured evidence that {primary} "
                f"is robust across the validation contrast from the other candidate."
            )
        refinements.append(
            {
                "topic_id": candidate.topic_id,
                "semantic_frame": frame.model_dump(mode="json"),
                "title": title,
                "research_question": question,
                "rationale": rationale,
                "differentiation": differentiation,
            }
        )
    return json.dumps({"schema_version": 1, "refinements": refinements})


def _offline_response(skeletons: tuple[object, ...], frames: tuple[TopicSemanticFrame, ...]) -> str:
    frame_by_topic = {item.topic_id: item.frame for item in frames}
    return json.dumps(
        {
            "schema_version": 1,
            "refinements": [
                {
                    "topic_id": skeleton.candidate.topic_id,
                    "semantic_frame": frame_by_topic[skeleton.candidate.topic_id].model_dump(
                        mode="json"
                    ),
                    "title": skeleton.candidate.title,
                    "research_question": skeleton.candidate.research_question,
                    "rationale": skeleton.rationale,
                    "differentiation": skeleton.differentiation,
                }
                for skeleton in skeletons
            ],
        }
    )


def test_build_semantic_frame_copies_every_locked_scientific_binding() -> None:
    opportunity = opportunity_factory(
        pattern="ordered-parameter-response",
        case_ids=("case-a", "case-b", "case-c"),
        binding_case_ids=("case-a", "case-b", "case-c"),
        qoi_ids=("qoi-response-a",),
        supporting_evidence_ids=("evidence-a", "evidence-b"),
    )
    candidate = build_generated_candidates((opportunity,)).candidate_input.candidates[0]

    frame = build_semantic_frame(opportunity, candidate)

    assert PROMPT_CONTRACT_VERSION == "topic-refinement-prompt-v1"
    assert REFINEMENT_POLICY_VERSION == "semantic-refinement-policy-v2"
    assert frame.relation == opportunity.relation
    assert {item.id for item in frame.parameter_bindings} == set(opportunity.parameter_ids)
    assert {item.role for item in frame.parameter_bindings} == {"varied", "controlled"}
    assert (
        tuple(item.id for item in frame.evidence_references) == opportunity.supporting_evidence_ids
    )


def test_professional_specialist_wording_with_bounded_material_gain_is_accepted() -> None:
    skeletons, frames = _skeletons_and_frames()
    provider = FakeProvider(_valid_response(skeletons, frames))

    result = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=provider,
    )

    assert provider.calls == 1
    assert result.mode == "provider-refined"
    assert result.rejection_reasons == ()
    assert "hydrodynamic" in result.accepted_refinements[0].title.casefold()
    for skeleton, candidate, accepted in zip(
        tuple(sorted(skeletons, key=lambda item: item.candidate.topic_id)),
        result.candidate_input.candidates,
        result.accepted_refinements,
        strict=True,
    ):
        before = (
            GeneratedCandidateEnvelope(candidates=(skeleton.candidate,))
            .candidates[0]
            .model_dump(mode="json")
        )
        after = candidate.model_dump(mode="json")
        for field in before:
            if field not in {"title", "research_question"}:
                assert after[field] == before[field]
        assert accepted.semantic_frame == next(
            item.frame for item in frames if item.topic_id == candidate.topic_id
        )
    assert not hasattr(result, "raw_response")


def test_coupled_association_accepts_open_professional_hydrodynamic_wording() -> None:
    opportunity = opportunity_factory(
        pattern="coupled-association",
        case_ids=("case-reference", "case-variant"),
        binding_case_ids=("case-reference", "case-variant"),
        qoi_ids=("qoi-primary", "qoi-secondary"),
        supporting_evidence_ids=("evidence-primary", "evidence-secondary"),
    )
    skeleton = build_generated_candidates((opportunity,)).skeletons[0]
    frame = TopicSemanticFrame(
        topic_id=skeleton.candidate.topic_id,
        frame=build_semantic_frame(opportunity, skeleton.candidate),
    )
    response = _valid_response((skeleton,), (frame,))

    result = refine_candidate_wording(
        skeletons=(skeleton,),
        frames=(frame,),
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(response),
    )

    assert result.mode == "provider-refined"
    assert "hydrodynamic" in result.candidate_input.candidates[0].title
    assert "associated" in result.accepted_refinements[0].rationale
    assert result.accepted_refinements[0].semantic_frame == frame.frame
    assert bounded_scientific_relation_preserved(
        proposed=result.accepted_refinements[0],
        relation=frame.frame.relation,
        catalog=wording_fact_catalog_for(skeleton.candidate.topic_id, frame.frame),
    )
    assert result.candidate_input.candidates[0].supporting_evidence_ids == tuple(
        skeleton.candidate.supporting_evidence_ids
    )
    assert result.accepted_refinements[0].semantic_frame.claim_class == frame.frame.claim_class


@pytest.mark.parametrize(
    ("attack", "reason"),
    (
        ("invented-number", "numeric-invention"),
        ("invented-unit", "unit-invention"),
        ("invented-id", "reference-out-of-bounds"),
        ("changed-frame", "semantic-frame-mismatch"),
        ("causal-language", "claim-escalation"),
        ("superiority-language", "prohibited-phrase"),
        ("continuous-window", "prohibited-phrase"),
        ("validation-upgrade", "claim-escalation"),
        ("engineering-boundary", "claim-escalation"),
        ("malformed-json", "malformed-json"),
        ("missing-topic", "topic-id-mismatch"),
        ("unknown-topic", "topic-id-mismatch"),
        ("reordered-topics", "topic-id-mismatch"),
        ("wrong-reference-kind", "semantic-frame-mismatch"),
        ("duplicate-topic", "topic-id-mismatch"),
        ("no-material-gain", "no-material-gain"),
    ),
)
def test_any_refinement_boundary_violation_falls_back_as_one_batch(
    attack: str, reason: str
) -> None:
    skeletons, frames = _skeletons_and_frames()
    response = _valid_response(skeletons, frames)
    if attack == "malformed-json":
        response = "{not json"
    elif attack == "no-material-gain":
        response = json.dumps(
            {
                "schema_version": 1,
                "refinements": [
                    {
                        "topic_id": skeleton.candidate.topic_id,
                        "semantic_frame": next(
                            item.frame
                            for item in frames
                            if item.topic_id == skeleton.candidate.topic_id
                        ).model_dump(mode="json"),
                        "title": skeleton.candidate.title,
                        "research_question": skeleton.candidate.research_question,
                        "rationale": skeleton.rationale,
                        "differentiation": skeleton.differentiation,
                    }
                    for skeleton in skeletons
                ],
            }
        )
    else:
        parsed = json.loads(response)
        first = parsed["refinements"][0]
        if attack == "invented-number":
            first["title"] += " at 999"
        elif attack == "invented-unit":
            first["title"] += " at 5 kPa"
        elif attack == "invented-id":
            first["rationale"] += " evidence-uninvented"
        elif attack == "changed-frame":
            first["semantic_frame"]["relation"]["polarity"] = "decrease"
        elif attack == "causal-language":
            first["rationale"] += " This causes the response."
        elif attack == "superiority-language":
            first["title"] += " with superior performance"
        elif attack == "continuous-window":
            first["title"] += " in a stable operating window"
        elif attack == "validation-upgrade":
            first["rationale"] += " This is experimentally validated."
        elif attack == "engineering-boundary":
            first["rationale"] += " This defines an engineering boundary."
        elif attack == "missing-topic":
            parsed["refinements"].pop()
        elif attack == "unknown-topic":
            first["topic_id"] = "auto-unknown"
        elif attack == "reordered-topics":
            parsed["refinements"].reverse()
        elif attack == "wrong-reference-kind":
            first["semantic_frame"]["subject_references"][0]["kind"] = "case"
        elif attack == "duplicate-topic":
            parsed["refinements"][1]["topic_id"] = first["topic_id"]
        response = json.dumps(parsed)
    provider = FakeProvider(response)

    result = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=provider,
    )

    assert provider.calls == 1
    assert result.mode == "offline-fallback"
    assert result.rejection_reasons == (reason,)
    expected = GeneratedCandidateEnvelope(
        candidates=tuple(
            item.candidate for item in sorted(skeletons, key=lambda item: item.candidate.topic_id)
        )
    )
    assert result.candidate_input == expected


def test_word_boundaries_allow_causal_but_reject_cause() -> None:
    skeletons, frames = _skeletons_and_frames()
    parsed = json.loads(_valid_response(skeletons, frames))
    parsed["refinements"][0]["title"] += " for causal drivetrain diagnostics"

    accepted = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(json.dumps(parsed)),
    )

    assert accepted.mode == "provider-refined"


def test_nfkc_unit_spellings_share_the_registered_canonical_unit() -> None:
    assert _canonical_unit("W/m²") == "w/m2"
    assert _canonical_unit("W/m^2") == "w/m2"
    assert _canonical_unit("Ｗ/ｍ²") == "w/m2"


@pytest.mark.parametrize(
    "attack",
    (
        "copied-offline-wording",
        "one-field-decoration",
        "generic-synonyms-no-supported-fact",
        "repeated-supported-alias-stuffing",
        "token-soup",
        "arbitrary-safe-vocabulary-margin",
        "delete-supported-fact",
        "relocate-core-fact",
        "one-new-fact-plus-loss",
    ),
)
def test_refinement_without_candidate_level_material_gain_falls_back(attack: str) -> None:
    skeletons, frames = _skeletons_and_frames()
    parsed = json.loads(_offline_response(skeletons, frames))
    first = parsed["refinements"][0]
    if attack == "copied-offline-wording":
        for response, skeleton in zip(parsed["refinements"], skeletons, strict=True):
            response.update(
                title=skeleton.candidate.title,
                research_question=skeleton.candidate.research_question,
                rationale=skeleton.rationale,
                differentiation=skeleton.differentiation,
            )
    elif attack == "one-field-decoration":
        first["title"] += " with hydrodynamic diagnostics"
        for response, skeleton in zip(parsed["refinements"][1:], skeletons[1:], strict=True):
            response.update(
                title=skeleton.candidate.title,
                research_question=skeleton.candidate.research_question,
                rationale=skeleton.rationale,
                differentiation=skeleton.differentiation,
            )
    elif attack == "generic-synonyms-no-supported-fact":
        first["title"] += " with detailed scientific characterization"
        first["research_question"] += " What nuanced behavior is apparent?"
    elif attack == "repeated-supported-alias-stuffing":
        first["title"] += " boundary evidence boundary evidence"
        first["research_question"] += " parameter control parameter control"
    elif attack == "token-soup":
        first["title"] = "qoi temperature parameter varied boundary evidence sampled cases"
    elif attack == "arbitrary-safe-vocabulary-margin":
        first["title"] += " interdisciplinary hydrodynamic characterization"
    elif attack == "delete-supported-fact":
        first["title"] = first["title"].replace("qoi temperature", "the outcome")
    elif attack == "relocate-core-fact":
        first["title"] = first["title"].replace("qoi temperature", "the outcome")
        first["rationale"] += " qoi temperature remains the outcome."
    elif attack == "one-new-fact-plus-loss":
        first["title"] = first["title"].replace("qoi temperature", "the outcome")
        first["rationale"] += " Boundary evidence is retained."

    result = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(json.dumps(parsed)),
    )

    assert result.mode == "offline-fallback"
    assert result.rejection_reasons == ("no-material-gain",)


@pytest.mark.parametrize(
    ("attack", "field", "replacement"),
    (
        (
            "evidence-id-only-rationale",
            "rationale",
            "evidence-temperature evidence-boundary-varied",
        ),
        ("vacuous-differentiation", "differentiation", "This candidate is different."),
        (
            "one-new-fact-plus-relation-semantic-loss",
            "rationale",
            "Current structured evidence for qoi temperature across sampled cases "
            "and parameter varied.",
        ),
    ),
)
def test_semantic_loss_attacks_do_not_masquerade_as_material_gain(
    attack: str, field: str, replacement: str
) -> None:
    skeletons, frames = _skeletons_and_frames()
    parsed = json.loads(_valid_response(skeletons, frames))
    parsed["refinements"][0][field] = replacement

    result = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(json.dumps(parsed)),
    )

    assert attack
    assert result.mode == "offline-fallback"
    assert result.rejection_reasons == ("semantic-frame-mismatch",)


def test_frame_binding_or_response_order_change_falls_back_before_wording_acceptance() -> None:
    skeletons, frames = _skeletons_and_frames()
    parsed = json.loads(_valid_response(skeletons, frames))
    parsed["refinements"][0]["semantic_frame"]["parameter_bindings"] = []
    binding_result = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(json.dumps(parsed)),
    )
    parsed = json.loads(_valid_response(skeletons, frames))
    parsed["refinements"].reverse()
    order_result = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(json.dumps(parsed)),
    )

    assert binding_result.rejection_reasons == ("semantic-frame-mismatch",)
    assert order_result.rejection_reasons == ("topic-id-mismatch",)


def test_input_permutation_keeps_accepted_envelope_bytes_deterministic() -> None:
    skeletons, frames = _skeletons_and_frames()
    original = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(
            _valid_response(
                tuple(sorted(skeletons, key=lambda item: item.candidate.topic_id)),
                tuple(sorted(frames, key=lambda item: item.topic_id)),
            )
        ),
    )
    reversed_skeletons = tuple(reversed(skeletons))
    reversed_frames = tuple(reversed(frames))
    permuted = refine_candidate_wording(
        skeletons=reversed_skeletons,
        frames=reversed_frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(
            _valid_response(
                tuple(sorted(skeletons, key=lambda item: item.candidate.topic_id)),
                tuple(sorted(frames, key=lambda item: item.topic_id)),
            )
        ),
    )

    assert original.model_dump_json() == permuted.model_dump_json()


def test_mechanism_frame_allows_bounded_causal_wording_but_association_does_not() -> None:
    mechanism = opportunity_factory(claim_ceiling="mechanism")
    mechanism_skeletons = build_generated_candidates((mechanism,)).skeletons
    mechanism_frames = tuple(
        TopicSemanticFrame(
            topic_id=item.candidate.topic_id,
            frame=build_semantic_frame(mechanism, item.candidate),
        )
        for item in mechanism_skeletons
    )
    mechanism_response = json.loads(_valid_response(mechanism_skeletons, mechanism_frames))
    mechanism_response["refinements"][0]["rationale"] += (
        " Current structured evidence for qoi response a across the reference and variant cases "
        "shows that qoi response a causes the observed response for sampled parameter varied "
        "across the reference and variant cases."
    )
    mechanism_result = refine_candidate_wording(
        skeletons=mechanism_skeletons,
        frames=mechanism_frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(json.dumps(mechanism_response)),
    )
    association = opportunity_factory(pattern="coupled-association", qoi_ids=("qoi-a", "qoi-b"))
    association_skeletons = build_generated_candidates((association,)).skeletons
    association_frames = tuple(
        TopicSemanticFrame(
            topic_id=item.candidate.topic_id,
            frame=build_semantic_frame(association, item.candidate),
        )
        for item in association_skeletons
    )
    association_response = json.loads(_valid_response(association_skeletons, association_frames))
    association_response["refinements"][0]["rationale"] += " The mechanism causes the response."
    association_result = refine_candidate_wording(
        skeletons=association_skeletons,
        frames=association_frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(json.dumps(association_response)),
    )

    assert mechanism_result.mode == "provider-refined"
    assert association_result.rejection_reasons == ("claim-escalation",)


def test_clause_level_relation_validation_rejects_missing_primary_qoi_role() -> None:
    association = opportunity_factory(
        pattern="coupled-association", qoi_ids=("qoi-first", "qoi-second")
    )
    skeletons = build_generated_candidates((association,)).skeletons
    frames = tuple(
        TopicSemanticFrame(
            topic_id=item.candidate.topic_id,
            frame=build_semantic_frame(association, item.candidate),
        )
        for item in skeletons
    )
    parsed = json.loads(_valid_response(skeletons, frames))
    parsed["refinements"][0]["research_question"] = parsed["refinements"][0][
        "research_question"
    ].replace("qoi second", "the second outcome")
    parsed["refinements"][0]["rationale"] = parsed["refinements"][0]["rationale"].replace(
        "qoi second", "the second outcome"
    )

    result = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(json.dumps(parsed)),
    )

    assert result.mode == "offline-fallback"
    assert result.rejection_reasons == ("semantic-frame-mismatch",)


def test_unknown_fields_and_near_duplicate_wording_are_rejected_without_false_positive() -> None:
    skeletons, frames = _skeletons_and_frames()
    unknown = json.loads(_valid_response(skeletons, frames))
    unknown["refinements"][0]["untrusted_explanation"] = "must not be retained"
    unknown_result = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(json.dumps(unknown)),
    )
    duplicate = json.loads(_valid_response(skeletons, frames))
    duplicate["refinements"][1]["title"] = duplicate["refinements"][0]["title"] + " diagnostic"
    duplicate["refinements"][1]["research_question"] = (
        duplicate["refinements"][0]["research_question"] + " diagnostic"
    )
    first_words = set(
        (
            duplicate["refinements"][0]["title"]
            + " "
            + duplicate["refinements"][0]["research_question"]
        )
        .casefold()
        .split()
    )
    second_words = set(
        (
            duplicate["refinements"][1]["title"]
            + " "
            + duplicate["refinements"][1]["research_question"]
        )
        .casefold()
        .split()
    )
    assert duplicate["refinements"][0]["title"] != duplicate["refinements"][1]["title"]
    assert len(first_words & second_words) / len(first_words | second_words) >= 0.85
    duplicate_result = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(json.dumps(duplicate)),
    )
    distinct_result = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(_valid_response(skeletons, frames)),
    )

    assert unknown_result.rejection_reasons == ("malformed-json",)
    assert duplicate_result.rejection_reasons == ("duplicate-refinement",)
    assert distinct_result.mode == "provider-refined"
    assert distinct_result.rejection_reasons == ()


def test_semantic_frame_reference_order_is_locked_before_provider_normalization() -> None:
    skeletons, frames = _skeletons_and_frames()
    parsed = json.loads(_valid_response(skeletons, frames))
    first_frame = parsed["refinements"][0]["semantic_frame"]
    first_frame["subject_references"].reverse()

    result = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(json.dumps(parsed)),
    )

    assert result.mode == "offline-fallback"
    assert result.rejection_reasons == ("semantic-frame-mismatch",)


def test_relation_roles_must_remain_in_one_ordered_scientific_clause() -> None:
    """A bag of correct aliases must not stand in for the matched relationship."""

    opportunity = opportunity_factory(
        pattern="matched-comparison",
        case_ids=("case-reference", "case-variant"),
        binding_case_ids=("case-reference", "case-variant"),
        qoi_ids=("qoi-pressure",),
        supporting_evidence_ids=("evidence-pressure",),
    )
    skeletons = build_generated_candidates((opportunity,)).skeletons
    frames = tuple(
        TopicSemanticFrame(
            topic_id=item.candidate.topic_id,
            frame=build_semantic_frame(opportunity, item.candidate),
        )
        for item in skeletons
    )
    parsed = json.loads(_valid_response(skeletons, frames))
    item = parsed["refinements"][0]
    item["research_question"] = (
        "How does the matched difference between the reference and variant cases "
        "exhibit qoi pressure for sampled parameter varied across case reference, "
        "case variant?"
    )
    item["rationale"] = (
        "Current structured evidence for qoi pressure across case reference, case variant "
        "documents the matched difference for sampled parameter varied across case reference, "
        "case variant."
    )

    result = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(json.dumps(parsed)),
    )

    assert result.mode == "offline-fallback"
    assert result.rejection_reasons == ("semantic-frame-mismatch",)


def test_frame_rejects_candidate_belonging_to_a_different_opportunity() -> None:
    first = opportunity_factory(pattern="matched-comparison")
    second = opportunity_factory(pattern="ordered-parameter-response")
    candidates = build_generated_candidates((first, second)).candidate_input.candidates
    candidate_for_second = next(
        item
        for item in candidates
        if item.topic_id
        != build_generated_candidates((first,)).candidate_input.candidates[0].topic_id
    )

    with pytest.raises(ValueError, match="does not match opportunity"):
        build_semantic_frame(first, candidate_for_second)


def test_matched_roles_do_not_guess_reference_and_variant_from_case_id_sorting() -> None:
    opportunity = opportunity_factory(
        pattern="matched-comparison",
        # In the real source order case-z is the reference and case-a is the variant.
        # Neither public case ID encodes that role, so a catalog must not infer it.
        case_ids=("case-a", "case-z"),
        binding_case_ids=("case-a", "case-z"),
    )
    candidate = build_generated_candidates((opportunity,)).candidate_input.candidates[0]
    frame = build_semantic_frame(opportunity, candidate).model_copy(
        update={
            "relation": ScientificRelationFrame(
                relation_class="difference",
                polarity="increase",
                comparison_direction="variant-vs-reference",
                quantifier="pairwise",
            )
        }
    )
    catalog = wording_fact_catalog_for(candidate.topic_id, frame)

    assert catalog.aliases["subject-case"] == ("variant", "variant case")
    assert catalog.aliases["contrast-case"] == ("reference", "reference case")
    assert "case a" not in catalog.aliases["subject-case"]
    assert "case z" not in catalog.aliases["contrast-case"]

    generic = AcceptedRefinement(
        topic_id=candidate.topic_id,
        semantic_frame=frame,
        title="Hydrodynamic comparison",
        research_question=(
            "Does variant qoi response a higher than reference across two sampled cases?"
        ),
        rationale=(
            "Current structured evidence shows variant qoi response a higher than reference "
            "across two sampled cases."
        ),
        differentiation="The scientific question distinguishes the candidate.",
    )
    actual_case_words = generic.model_copy(
        update={
            "research_question": (
                "Does case a qoi response a higher than case z across two sampled cases?"
            ),
            "rationale": "Case a qoi response a higher than case z across two sampled cases.",
        }
    )
    swapped_generic = generic.model_copy(
        update={
            "research_question": (
                "Does reference qoi response a higher than variant across two sampled cases?"
            ),
            "rationale": "Reference qoi response a higher than variant across two sampled cases.",
        }
    )
    assert bounded_scientific_relation_preserved(
        proposed=generic, relation=frame.relation, catalog=catalog
    )
    assert not bounded_scientific_relation_preserved(
        proposed=actual_case_words, relation=frame.relation, catalog=catalog
    )
    assert not bounded_scientific_relation_preserved(
        proposed=swapped_generic, relation=frame.relation, catalog=catalog
    )


def _single_pattern_inputs(
    pattern: str,
) -> tuple[tuple[object, ...], tuple[TopicSemanticFrame, ...]]:
    qoi_ids = (
        ("qoi-primary", "qoi-secondary") if pattern == "coupled-association" else ("qoi-primary",)
    )
    opportunity = opportunity_factory(
        pattern=pattern,
        case_ids=("case-reference", "case-variant"),
        binding_case_ids=("case-reference", "case-variant"),
        qoi_ids=qoi_ids,
        supporting_evidence_ids=("evidence-primary", "evidence-secondary"),
    )
    skeletons = build_generated_candidates((opportunity,)).skeletons
    return skeletons, tuple(
        TopicSemanticFrame(
            topic_id=item.candidate.topic_id,
            frame=build_semantic_frame(opportunity, item.candidate),
        )
        for item in skeletons
    )


def _result_for_single_attack(pattern: str, mutate: object):
    skeletons, frames = _single_pattern_inputs(pattern)
    payload = json.loads(_valid_response(skeletons, frames))
    mutate(payload["refinements"][0])
    return refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(json.dumps(payload)),
    )


@pytest.mark.parametrize(
    ("label", "pattern", "mutate"),
    (
        (
            "matched-explicit-negation",
            "matched-comparison",
            lambda item: item.__setitem__(
                "rationale", item["rationale"].replace("differs from", "does not differ from")
            ),
        ),
        (
            "ordered-explicit-negation",
            "ordered-parameter-response",
            lambda item: item.__setitem__(
                "rationale", item["rationale"].replace("increases with", "does not increase with")
            ),
        ),
        (
            "ordered-inverse-polarity",
            "ordered-parameter-response",
            lambda item: item.update(
                research_question=item["research_question"].replace(
                    "increase with", "decrease with"
                ),
                rationale=item["rationale"].replace("increases with", "decreases with"),
            ),
        ),
        (
            "ordered-qoi-parameter-swap",
            "ordered-parameter-response",
            lambda item: item.__setitem__(
                "rationale",
                item["rationale"].replace(
                    "qoi primary increases with parameter varied",
                    "parameter varied increases with qoi primary",
                ),
            ),
        ),
        (
            "association-explicit-negation",
            "coupled-association",
            lambda item: item.__setitem__(
                "rationale",
                item["rationale"].replace(
                    "is positively associated with", "is not positively associated with"
                ),
            ),
        ),
        (
            "association-inverse-polarity",
            "coupled-association",
            lambda item: item.__setitem__(
                "rationale", item["rationale"].replace("positively", "negatively")
            ),
        ),
        (
            "association-family-swap",
            "coupled-association",
            lambda item: item.__setitem__(
                "rationale",
                item["rationale"].replace("is positively associated with", "is robust across"),
            ),
        ),
        (
            "robustness-explicit-negation",
            "validation-robustness",
            lambda item: item.__setitem__(
                "rationale", item["rationale"].replace("is robust across", "is not robust across")
            ),
        ),
        (
            "robustness-family-swap",
            "validation-robustness",
            lambda item: item.__setitem__(
                "rationale",
                item["rationale"].replace("is robust across", "is positively associated with"),
            ),
        ),
        (
            "broadened-scope",
            "ordered-parameter-response",
            lambda item: item.update(
                research_question=item["research_question"].replace(
                    "sampled cases", "all operating conditions"
                ),
                rationale=item["rationale"].replace("sampled cases", "all operating conditions"),
            ),
        ),
    ),
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_relation_text_attacks_reject_actual_provider_wording(
    label: str, pattern: str, mutate: object
) -> None:
    result = _result_for_single_attack(pattern, mutate)

    assert label
    assert result.mode == "offline-fallback"
    assert result.rejection_reasons == ("semantic-frame-mismatch",)


def test_signed_matched_inverse_and_subject_contrast_swap_reject() -> None:
    skeletons, frames = _single_pattern_inputs("matched-comparison")
    signed_relation = ScientificRelationFrame(
        relation_class="difference",
        polarity="increase",
        comparison_direction="variant-vs-reference",
        quantifier="pairwise",
    )
    signed_frame = TopicSemanticFrame(
        topic_id=frames[0].topic_id,
        frame=frames[0].frame.model_copy(update={"relation": signed_relation}),
    )
    base = json.loads(_valid_response(skeletons, frames))["refinements"][0]
    base["semantic_frame"] = signed_frame.frame.model_dump(mode="json")
    base["research_question"] = (
        "Across two sampled cases, is the variant qoi primary higher than the reference?"
    )
    base["rationale"] = (
        "Current structured evidence shows the variant qoi primary higher than the reference "
        "across two sampled cases."
    )
    inversions = []
    for source, replacement in (
        ("higher than", "lower than"),
        (
            "variant qoi primary higher than the reference",
            "reference qoi primary higher than the variant",
        ),
    ):
        mutated = dict(base)
        mutated["rationale"] = mutated["rationale"].replace(source, replacement)
        inversions.append(mutated)
    for item in inversions:
        response = json.dumps({"schema_version": 1, "refinements": [item]})
        result = refine_candidate_wording(
            skeletons=skeletons,
            frames=(signed_frame,),
            semantic_reuse_key="a" * 64,
            context_packet=_context_packet(),
            provider=FakeProvider(response),
        )
        assert result.rejection_reasons == ("semantic-frame-mismatch",)


def test_context_packet_is_visible_to_provider_but_does_not_extend_topic_whitelist() -> None:
    skeletons, frames = _skeletons_and_frames()
    parsed = json.loads(_valid_response(skeletons, frames))
    parsed["refinements"][0]["title"] += " for auto-context-only"
    provider = FakeProvider(json.dumps(parsed))
    context = TaskContextPacket(
        task="topic-refinement",
        token_budget=512,
        constraints=["context-only phrase", "auto-context-only"],
    )

    result = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=context,
        provider=provider,
    )

    assert "context-only phrase" in provider.prompts[0]
    assert result.rejection_reasons == ("reference-out-of-bounds",)


@pytest.mark.parametrize(
    ("context_fact", "provider_fact", "reason"),
    (
        ("4.2", " at 4.2", "numeric-invention"),
        ("W/m^2", " at 4.2 W/m^2", "unit-invention"),
        ("evidence-context-only", " evidence-context-only", "reference-out-of-bounds"),
    ),
)
def test_context_only_facts_never_expand_the_provider_whitelist(
    context_fact: str, provider_fact: str, reason: str
) -> None:
    skeletons, frames = _skeletons_and_frames()
    parsed = json.loads(_valid_response(skeletons, frames))
    parsed["refinements"][0]["rationale"] += provider_fact
    context = TaskContextPacket(
        task="topic-refinement",
        token_budget=512,
        constraints=[context_fact],
    )

    result = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=context,
        provider=FakeProvider(json.dumps(parsed)),
    )

    assert result.rejection_reasons == (reason,)


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    (
        ("title", " at 1e3 W/m²", "unit-invention"),
        ("title", " at 1e3 W/m^2", "unit-invention"),
        ("title", " at 1e3 W/m³", "unit-invention"),
        ("title", " at 1e3 kg/m^3", "unit-invention"),
        ("rationale", " with 2.5e-3 kg/m³", "unit-invention"),
        ("differentiation", " opp-untrusted", "reference-out-of-bounds"),
        ("research_question", " ev-untrusted", "reference-out-of-bounds"),
    ),
)
def test_original_scientific_tokens_are_extracted_before_normalization(
    field: str, value: str, reason: str
) -> None:
    skeletons, frames = _skeletons_and_frames()
    parsed = json.loads(_valid_response(skeletons, frames))
    parsed["refinements"][0][field] += value

    result = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(json.dumps(parsed)),
    )

    assert result.rejection_reasons == (reason,)


@pytest.mark.parametrize(
    ("frame_field", "replacement"),
    (
        ("relation_class", "difference"),
        ("polarity", "decrease"),
        ("comparison_direction", "symmetric"),
        ("quantifier", "pairwise"),
    ),
)
def test_every_locked_relation_slot_rejects_provider_mutation(
    frame_field: str, replacement: str
) -> None:
    skeletons, frames = _skeletons_and_frames()
    parsed = json.loads(_valid_response(skeletons, frames))
    parsed["refinements"][0]["semantic_frame"]["relation"][frame_field] = replacement

    result = refine_candidate_wording(
        skeletons=skeletons,
        frames=frames,
        semantic_reuse_key="a" * 64,
        context_packet=_context_packet(),
        provider=FakeProvider(json.dumps(parsed)),
    )

    assert result.rejection_reasons == ("semantic-frame-mismatch",)
