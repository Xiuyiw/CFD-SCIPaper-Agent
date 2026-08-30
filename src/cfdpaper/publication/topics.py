"""Topic screening that refuses to turn incomplete evidence into a paper claim."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cfdpaper.contracts import EvidenceRecord


class PublicationModel(BaseModel):
    """Strict base model for publication workstream records."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class TopicCandidate(PublicationModel):
    """A possible paper topic and the evidence needed to defend it."""

    topic_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    research_question: str = Field(min_length=1)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    required_evidence_kinds: set[str] = Field(default_factory=set)
    required_maturity: Literal["raw", "screened", "verified", "author-approved"] = "verified"
    minimum_verified_evidence: int = Field(default=1, ge=1)
    significance: float = Field(default=0.5, ge=0.0, le=1.0)
    novelty: float = Field(default=0.5, ge=0.0, le=1.0)


class RankedTopic(PublicationModel):
    candidate: TopicCandidate
    score: float = Field(ge=0.0, le=1.0)
    evidence_coverage: float = Field(ge=0.0, le=1.0)
    verified_evidence_count: int = Field(ge=0)
    defensible: bool
    missing_evidence: list[str] = Field(default_factory=list)


class TopicRankingResult(PublicationModel):
    outcome: Literal["manuscript", "analysis-note", "missing-evidence"]
    ranked_topics: list[RankedTopic]
    missing_evidence: list[str] = Field(default_factory=list)
    reason: str


def _rank_candidate(
    candidate: TopicCandidate,
    evidence_by_id: dict[str, EvidenceRecord],
) -> RankedTopic:
    supporting_evidence_ids = list(dict.fromkeys(candidate.supporting_evidence_ids))
    matched = [
        evidence_by_id[evidence_id]
        for evidence_id in supporting_evidence_ids
        if evidence_id in evidence_by_id
    ]
    fresh_matched = [item for item in matched if not item.stale]
    matched_kinds = {item.kind for item in matched}
    maturity_order = {
        "raw": 0,
        "screened": 1,
        "verified": 2,
        "author-approved": 3,
    }
    missing_ids = sorted(set(supporting_evidence_ids) - evidence_by_id.keys())
    stale_ids = sorted(item.evidence_id for item in matched if item.stale)
    missing_kinds = sorted(candidate.required_evidence_kinds - matched_kinds)
    immature_kinds = sorted(
        kind
        for kind in candidate.required_evidence_kinds & matched_kinds
        if not any(item.kind == kind for item in fresh_matched)
        or max(maturity_order[item.maturity] for item in fresh_matched if item.kind == kind)
        < maturity_order[candidate.required_maturity]
    )
    verified_count = sum(item.maturity in {"verified", "author-approved"} for item in fresh_matched)

    required_count = len(candidate.required_evidence_kinds)
    mature_kinds = candidate.required_evidence_kinds & matched_kinds - set(immature_kinds)
    kind_coverage = len(mature_kinds) / required_count if required_count else 1.0
    verification_coverage = min(
        verified_count / candidate.minimum_verified_evidence,
        1.0,
    )
    has_candidate_support = bool(matched)
    score = (
        0.55 * kind_coverage
        + 0.25 * verification_coverage
        + 0.10 * candidate.significance
        + 0.10 * candidate.novelty
        if has_candidate_support
        else 0.0
    )
    missing = [*(f"evidence-id:{item}" for item in missing_ids)]
    missing.extend(f"stale-evidence:{item}" for item in stale_ids)
    missing.extend(f"kind:{item}" for item in missing_kinds)
    missing.extend(f"maturity:{item}:{candidate.required_maturity}" for item in immature_kinds)
    if matched and verified_count < candidate.minimum_verified_evidence:
        missing.append(f"verified-evidence:{candidate.minimum_verified_evidence - verified_count}")

    return RankedTopic(
        candidate=candidate,
        score=round(score, 6),
        evidence_coverage=kind_coverage,
        verified_evidence_count=verified_count,
        defensible=(
            has_candidate_support
            and kind_coverage == 1.0
            and verified_count >= candidate.minimum_verified_evidence
        ),
        missing_evidence=missing,
    )


def rank_topics(
    candidates: list[TopicCandidate],
    evidence: list[EvidenceRecord],
) -> TopicRankingResult:
    """Rank topics and select the most defensible allowed output type."""

    evidence_by_id = {item.evidence_id: item for item in evidence}
    ranked = sorted(
        (_rank_candidate(candidate, evidence_by_id) for candidate in candidates),
        key=lambda item: (-int(item.defensible), -item.score, item.candidate.topic_id),
    )

    if not ranked:
        return TopicRankingResult(
            outcome="missing-evidence",
            ranked_topics=[],
            reason="No topic candidates were supplied.",
        )

    selected = ranked[0]
    if selected.defensible:
        outcome: Literal["manuscript", "analysis-note", "missing-evidence"] = "manuscript"
        reason = "The leading topic meets its declared evidence requirements."
    elif selected.score > 0:
        outcome = "analysis-note"
        reason = "Evidence supports only an analysis note."
    else:
        outcome = "missing-evidence"
        reason = "No supplied evidence supports a candidate topic."

    return TopicRankingResult(
        outcome=outcome,
        ranked_topics=ranked,
        missing_evidence=selected.missing_evidence,
        reason=reason,
    )
