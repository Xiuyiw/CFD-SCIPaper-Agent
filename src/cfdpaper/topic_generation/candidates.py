"""Construct conservative, evidence-traceable topic candidates offline."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import Field, model_validator

from cfdpaper.publication.topics import RankedTopic, TopicCandidate, TopicRankingResult
from cfdpaper.topic_generation.canonical import canonical_sha256
from cfdpaper.topic_generation.models import GeneratedCandidateEnvelope, GenerationModel
from cfdpaper.topic_generation.opportunities import ResearchOpportunity

_CEILING_ORDER = {
    "observation": 0,
    "association": 1,
    "mechanism": 2,
    "validation": 3,
    "engineering": 4,
}


class CandidateSkeleton(GenerationModel):
    """Offline wording and traceability retained beside an existing public candidate."""

    opportunity_id: str = Field(min_length=1)
    candidate: TopicCandidate
    rationale: str = Field(min_length=1)
    differentiation: str = Field(min_length=1)
    prohibited_inferences: tuple[str, ...]
    output_scope: Literal["manuscript-candidate", "direction-only", "analysis-note"]
    parameter_ids: tuple[str, ...]
    figure_evidence_structure: tuple[str, ...]

    @model_validator(mode="after")
    def validate_traceability_ordering(self) -> CandidateSkeleton:
        if (
            self.parameter_ids != tuple(sorted(set(self.parameter_ids)))
            or not self.parameter_ids
            or any(not item for item in self.parameter_ids)
        ):
            raise ValueError("parameter IDs must be sorted, unique, and nonempty")
        figure_roles = tuple(sorted(set(self.figure_evidence_structure)))
        if (
            self.figure_evidence_structure != figure_roles
            or not figure_roles
            or any(not item for item in figure_roles)
        ):
            raise ValueError("figure evidence roles must be sorted, unique, and nonempty")
        return self


class CandidateConstructionResult(GenerationModel):
    """Candidate rank order plus a deterministic lookup back to scientific opportunities."""

    candidate_input: GeneratedCandidateEnvelope
    skeletons: tuple[CandidateSkeleton, ...]
    topic_to_opportunity: tuple[tuple[str, str], ...]
    gaps: tuple[str, ...]

    @model_validator(mode="after")
    def validate_alignment(self) -> CandidateConstructionResult:
        candidate_ids = tuple(item.topic_id for item in self.candidate_input.candidates)
        skeleton_ids = tuple(item.candidate.topic_id for item in self.skeletons)
        if candidate_ids != skeleton_ids:
            raise ValueError("candidate input and skeleton order must align")
        if len({item.opportunity_id for item in self.skeletons}) != len(self.skeletons):
            raise ValueError("topic-to-opportunity mapping cannot reuse a skeleton opportunity")
        mappings = tuple(sorted(self.topic_to_opportunity))
        if self.topic_to_opportunity != mappings:
            raise ValueError("topic-to-opportunity mapping must be topic-ID sorted")
        mapping_ids = tuple(item[0] for item in mappings)
        if mapping_ids != tuple(sorted(candidate_ids)) or len(set(mapping_ids)) != len(mapping_ids):
            raise ValueError("topic-to-opportunity mapping cardinality does not match candidates")
        if any(not topic_id or not opportunity_id for topic_id, opportunity_id in mappings):
            raise ValueError("topic-to-opportunity mapping IDs must be nonblank")
        expected_mappings = tuple(
            sorted((item.candidate.topic_id, item.opportunity_id) for item in self.skeletons)
        )
        if mappings != expected_mappings:
            raise ValueError("topic-to-opportunity mapping must match every skeleton identity")
        if self.gaps != tuple(sorted(set(self.gaps))):
            raise ValueError("construction gaps must be sorted and unique")
        return self


def _humanize(identifier: str) -> str:
    return " ".join(identifier.replace("_", " ").replace("-", " ").split())


def _labels(opportunity: ResearchOpportunity) -> tuple[str, str, str]:
    subject = _humanize(opportunity.varied_parameter_ids[0])
    outcome = " and ".join(_humanize(item) for item in opportunity.primary_qoi_ids)
    contrast = ", ".join(_humanize(case_id) for case_id in opportunity.case_ids)
    return subject, outcome, contrast


def _relation_phrase(opportunity: ResearchOpportunity) -> str:
    polarity = opportunity.relation.polarity
    if opportunity.pattern == "matched-comparison":
        if polarity == "difference-only":
            return "matched difference between the reference and variant cases"
        return f"matched {_humanize(polarity)} for the variant relative to the reference"
    if opportunity.pattern == "ordered-parameter-response":
        trend = {
            "monotonic-increasing": "sampled monotonic increase",
            "monotonic-decreasing": "sampled monotonic decrease",
            "interior-peak": "sampled non-monotonic response with an interior peak",
            "interior-trough": "sampled non-monotonic response with an interior trough",
            "plateau": "sampled plateau response",
            "mixed": "mixed sampled response",
        }[opportunity.trend_type or "mixed"]
        return f"{trend} across the discrete varied-parameter series"
    if opportunity.pattern == "coupled-association":
        if polarity == "not-applicable":
            return "sampled association without an assigned sign"
        return f"{_humanize(polarity)} association across sampled cases"
    return "robustness across the validation or sensitivity contrast"


def _wording(opportunity: ResearchOpportunity) -> tuple[str, str, str, str]:
    subject, outcome, contrast = _labels(opportunity)
    relation = _relation_phrase(opportunity)
    ceiling = opportunity.claim_ceiling.value
    if opportunity.pattern == "coupled-association":
        association = relation.removesuffix(" across sampled cases")
        connector = "between" if len(opportunity.primary_qoi_ids) == 2 else "among"
        title = (
            f"{association.capitalize()} {connector} {outcome} across sampled cases for sampled "
            f"{subject} across {contrast}"
        )
        question = (
            f"How is the {association} {connector} {outcome} observed across sampled cases for "
            f"sampled {subject} across {contrast}?"
        )
        rationale = (
            f"Current structured evidence supports the {association} {connector} {outcome} across "
            f"sampled cases for sampled {subject} across {contrast}; "
            f"interpretation remains bounded by the {ceiling} claim ceiling."
        )
        differentiation = (
            f"This candidate distinguishes the {association} {connector} {outcome} across sampled "
            f"cases for {subject} across {contrast} from other evidence-bounded "
            "scientific questions."
        )
    else:
        title = f"{relation.capitalize()} in {outcome} for sampled {subject} across {contrast}"
        question = (
            f"How does {outcome} exhibit the {relation} for sampled {subject} across {contrast}?"
        )
        rationale = (
            f"Current structured evidence supports the {relation} for {outcome} across {contrast}; "
            f"interpretation remains bounded by the {ceiling} claim ceiling."
        )
        differentiation = (
            f"This candidate distinguishes the {relation} in {outcome} for {subject} across "
            f"{contrast} from other evidence-bounded scientific questions."
        )
    return title, question, rationale, differentiation


def _significance(opportunity: ResearchOpportunity) -> float:
    case_breadth = min(len(opportunity.current_case_ids), 4) / 4
    gate_fraction = opportunity.passed_gate_count / 6
    maturity_bonus = (
        0.10 if opportunity.evidence_maturity.value in {"verified", "author-approved"} else 0.0
    )
    validation_bonus = 0.10 if opportunity.independent_validation_linked else 0.0
    return round(
        min(
            0.70,
            0.20 + 0.25 * gate_fraction + 0.10 * case_breadth + maturity_bonus + validation_bonus,
        ),
        6,
    )


def _novelty(opportunity: ResearchOpportunity) -> float:
    if opportunity.literature_gap_maturity.value in {"verified", "author-approved"}:
        return 0.50
    if opportunity.literature_gap_maturity.value == "screened":
        return 0.35
    return 0.20


def _near_duplicate(first: ResearchOpportunity, second: ResearchOpportunity) -> bool:
    if (
        first.pattern != second.pattern
        or first.primary_qoi_ids != second.primary_qoi_ids
        or first.parameter_bindings != second.parameter_bindings
    ):
        return False
    union = set(first.case_ids) | set(second.case_ids)
    overlap = set(first.case_ids) & set(second.case_ids)
    return bool(union) and len(overlap) / len(union) >= 0.80


def _topic_id(opportunity: ResearchOpportunity) -> str:
    digest = canonical_sha256(
        opportunity.semantic_signature,
        domain=b"cfdpaper-generated-topic-v1",
    )
    return f"auto-{digest[:16]}"


def _required_maturity(opportunity: ResearchOpportunity) -> str:
    return "author-approved" if opportunity.claim_ceiling.value == "engineering" else "verified"


def _candidate_sort_key(opportunity: ResearchOpportunity) -> tuple[Any, ...]:
    return (
        -int(opportunity.defensible),
        -_CEILING_ORDER[opportunity.claim_ceiling.value],
        -_significance(opportunity),
        -_novelty(opportunity),
        opportunity.opportunity_id,
    )


def _make_skeleton(opportunity: ResearchOpportunity) -> CandidateSkeleton:
    title, question, rationale, differentiation = _wording(opportunity)
    candidate = TopicCandidate(
        topic_id=_topic_id(opportunity),
        title=title,
        research_question=question,
        supporting_evidence_ids=list(opportunity.supporting_evidence_ids),
        required_evidence_kinds=set(opportunity.required_evidence_kinds),
        required_maturity=_required_maturity(opportunity),
        minimum_verified_evidence=max(1, len(opportunity.required_evidence_kinds)),
        significance=_significance(opportunity),
        novelty=_novelty(opportunity),
    )
    figure_evidence_structure = tuple(
        sorted(
            {
                "case-qoi-comparison",
                *(f"parameter:{item}" for item in opportunity.parameter_ids),
                *(f"qoi:{item}" for item in opportunity.primary_qoi_ids),
                *(f"support:{item}" for item in opportunity.supporting_evidence_ids),
            }
        )
    )
    return CandidateSkeleton(
        opportunity_id=opportunity.opportunity_id,
        candidate=candidate,
        rationale=rationale,
        differentiation=differentiation,
        prohibited_inferences=opportunity.prohibited_inferences,
        output_scope="manuscript-candidate" if opportunity.defensible else opportunity.output_scope,
        parameter_ids=opportunity.parameter_ids,
        figure_evidence_structure=figure_evidence_structure,
    )


def build_generated_candidates(
    opportunities: Sequence[ResearchOpportunity],
) -> CandidateConstructionResult:
    """Build at most four semantically distinct offline candidates without padding."""

    ranked = sorted(
        (item for item in opportunities if item.candidate_eligible),
        key=_candidate_sort_key,
    )
    selected: list[ResearchOpportunity] = []
    seen_ids: set[str] = set()
    for opportunity in ranked:
        if opportunity.opportunity_id in seen_ids or any(
            _near_duplicate(opportunity, existing) for existing in selected
        ):
            continue
        selected.append(opportunity)
        seen_ids.add(opportunity.opportunity_id)
        if len(selected) == 4:
            break
    skeletons = tuple(_make_skeleton(opportunity) for opportunity in selected)
    candidates = tuple(item.candidate for item in skeletons)
    mappings = tuple(sorted((item.candidate.topic_id, item.opportunity_id) for item in skeletons))
    gaps = ("insufficient-distinct-opportunities",) if len(skeletons) <= 1 else ()
    return CandidateConstructionResult(
        candidate_input=GeneratedCandidateEnvelope(candidates=candidates),
        skeletons=skeletons,
        topic_to_opportunity=mappings,
        gaps=gaps,
    )


def _projected_outcome(
    ranked_topics: list[RankedTopic],
) -> tuple[Literal["manuscript", "analysis-note", "missing-evidence"], str]:
    if not ranked_topics:
        return "missing-evidence", "No topic candidates were supplied."
    leading = ranked_topics[0]
    if leading.defensible:
        return "manuscript", "The leading topic meets its declared evidence requirements."
    if leading.score > 0:
        return "analysis-note", "Evidence supports only an analysis note."
    return "missing-evidence", "No supplied evidence supports a candidate topic."


def apply_generation_constraints(
    ranking: TopicRankingResult,
    *,
    opportunities_by_topic_id: Mapping[str, ResearchOpportunity],
) -> TopicRankingResult:
    """Project immutable opportunity ceilings onto a public ranking without raising them."""

    topic_ids = tuple(item.candidate.topic_id for item in ranking.ranked_topics)
    if len(set(topic_ids)) != len(topic_ids) or set(topic_ids) != set(opportunities_by_topic_id):
        raise ValueError("topic-to-opportunity mapping cardinality does not match ranking")
    projected: list[RankedTopic] = []
    for raw in ranking.ranked_topics:
        opportunity = opportunities_by_topic_id[raw.candidate.topic_id]
        if raw.candidate.topic_id != _topic_id(opportunity):
            raise ValueError("ranking candidate and opportunity generation identity do not match")
        offline_gaps = [f"offline:{gap.code}" for gap in opportunity.gaps]
        payload = raw.model_dump(mode="python", warnings=False)
        payload["candidate"] = TopicCandidate.model_validate(payload["candidate"])
        payload["defensible"] = bool(raw.defensible and opportunity.defensible)
        payload["missing_evidence"] = sorted(set((*raw.missing_evidence, *offline_gaps)))
        projected.append(RankedTopic.model_validate(payload))
    projected.sort(key=lambda item: (-int(item.defensible), -item.score, item.candidate.topic_id))
    outcome, reason = _projected_outcome(projected)
    return TopicRankingResult(
        outcome=outcome,
        ranked_topics=projected,
        missing_evidence=projected[0].missing_evidence if projected else [],
        reason=reason,
    )


__all__ = [
    "CandidateConstructionResult",
    "CandidateSkeleton",
    "apply_generation_constraints",
    "build_generated_candidates",
]
