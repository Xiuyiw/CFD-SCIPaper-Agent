from cfdpaper.contracts import EvidenceRecord
from cfdpaper.publication.spine import (
    PaperSpine,
    SectionContract,
    validate_spine,
)
from cfdpaper.publication.topics import TopicCandidate, rank_topics


def evidence(
    evidence_id: str,
    kind: str,
    maturity: str = "verified",
    *,
    stale: bool = False,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        source_uri="synthetic/results.csv",
        locator=f"row:{evidence_id}",
        kind=kind,
        summary=f"Synthetic {kind} evidence",
        maturity=maturity,
        stale=stale,
    )


def test_topic_ranking_prefers_defensible_complete_candidate() -> None:
    candidates = [
        TopicCandidate(
            topic_id="mixing",
            title="Flow mixing across operating settings",
            research_question="How does inlet setting alter mixing uniformity?",
            supporting_evidence_ids=["field-1"],
            required_evidence_kinds={"field", "boundary"},
            minimum_verified_evidence=2,
            significance=0.9,
            novelty=0.8,
        ),
        TopicCandidate(
            topic_id="loss",
            title="Pressure loss across operating settings",
            research_question="How does inlet setting alter pressure loss?",
            supporting_evidence_ids=["qoi-1", "boundary-1"],
            required_evidence_kinds={"qoi", "boundary"},
            minimum_verified_evidence=2,
            significance=0.7,
            novelty=0.6,
        ),
    ]

    result = rank_topics(
        candidates,
        [
            evidence("field-1", "field", maturity="screened"),
            evidence("qoi-1", "qoi"),
            evidence("boundary-1", "boundary"),
        ],
    )

    assert result.outcome == "manuscript"
    assert result.ranked_topics[0].candidate.topic_id == "loss"
    assert result.ranked_topics[0].defensible is True


def test_topic_ranking_returns_analysis_note_when_some_evidence_is_incomplete() -> None:
    candidate = TopicCandidate(
        topic_id="wake",
        title="Wake recovery across operating settings",
        research_question="How quickly does the wake recover?",
        supporting_evidence_ids=["field-1"],
        required_evidence_kinds={"field", "mesh"},
        minimum_verified_evidence=2,
    )

    result = rank_topics([candidate], [evidence("field-1", "field")])

    assert result.outcome == "analysis-note"
    assert result.missing_evidence == ["kind:mesh", "verified-evidence:1"]
    assert "manuscript" not in result.reason.lower()


def test_topic_requires_each_required_kind_to_reach_required_maturity() -> None:
    candidate = TopicCandidate(
        topic_id="recovery",
        title="Response recovery across sampled settings",
        research_question="How does the sampled response recover?",
        supporting_evidence_ids=["field-1", "boundary-1", "qoi-1"],
        required_evidence_kinds={"field", "boundary"},
        minimum_verified_evidence=2,
    )

    result = rank_topics(
        [candidate],
        [
            evidence("field-1", "field", maturity="screened"),
            evidence("boundary-1", "boundary", maturity="verified"),
            evidence("qoi-1", "qoi", maturity="verified"),
        ],
    )

    assert result.outcome == "analysis-note"
    assert result.ranked_topics[0].defensible is False
    assert result.missing_evidence == ["maturity:field:verified"]


def test_topic_deduplicates_supporting_evidence_ids_before_counting() -> None:
    candidate = TopicCandidate(
        topic_id="response",
        title="Response across sampled settings",
        research_question="How does the response vary?",
        supporting_evidence_ids=["qoi-1", "qoi-1"],
        required_evidence_kinds={"qoi"},
        minimum_verified_evidence=2,
    )

    result = rank_topics([candidate], [evidence("qoi-1", "qoi")])

    assert result.outcome == "analysis-note"
    assert result.ranked_topics[0].verified_evidence_count == 1
    assert result.missing_evidence == ["verified-evidence:1"]


def test_topic_stale_evidence_does_not_contribute_maturity() -> None:
    candidate = TopicCandidate(
        topic_id="response",
        title="Response across sampled settings",
        research_question="How does the response vary?",
        supporting_evidence_ids=["qoi-1"],
        required_evidence_kinds={"qoi"},
        minimum_verified_evidence=1,
    )

    result = rank_topics(
        [candidate],
        [evidence("qoi-1", "qoi", maturity="author-approved", stale=True)],
    )

    assert result.outcome == "analysis-note"
    assert result.ranked_topics[0].verified_evidence_count == 0
    assert result.ranked_topics[0].defensible is False
    assert "stale-evidence:qoi-1" in result.missing_evidence
    assert "maturity:qoi:verified" in result.missing_evidence


def test_topic_ranking_returns_missing_evidence_without_candidate_support() -> None:
    candidate = TopicCandidate(
        topic_id="thermal",
        title="Thermal response across operating settings",
        research_question="How does the temperature field respond?",
        supporting_evidence_ids=["field-absent"],
        required_evidence_kinds={"field"},
    )

    result = rank_topics([candidate], [])

    assert result.outcome == "missing-evidence"
    assert result.ranked_topics[0].score == 0.0
    assert result.missing_evidence == ["evidence-id:field-absent", "kind:field"]


def test_spine_contract_reports_unresolved_claim_and_figure_references() -> None:
    spine = PaperSpine(
        topic_id="loss",
        central_claim_id="claim-main",
        sections=[
            SectionContract(
                section_id="results",
                role="results",
                title="Pressure-loss response",
                purpose="Quantify the response without causal overreach.",
                required_claim_ids=["claim-main", "claim-trend"],
                required_figure_ids=["fig-loss"],
            )
        ],
    )

    result = validate_spine(
        spine,
        available_claim_ids={"claim-main"},
        available_figure_ids=set(),
    )

    assert result.valid is False
    assert result.issues == [
        "section:results missing claim:claim-trend",
        "section:results missing figure:fig-loss",
    ]


def test_spine_contract_accepts_fully_resolved_structure() -> None:
    spine = PaperSpine(
        topic_id="loss",
        central_claim_id="claim-main",
        sections=[
            SectionContract(
                section_id="results",
                role="results",
                title="Pressure-loss response",
                purpose="Report the supported trend.",
                required_claim_ids=["claim-main"],
                required_figure_ids=["fig-loss"],
            ),
            SectionContract(
                section_id="discussion",
                role="discussion",
                title="Scope and limitations",
                purpose="Bound interpretation to the sampled cases.",
                required_claim_ids=["claim-main"],
            ),
        ],
    )

    result = validate_spine(
        spine,
        available_claim_ids={"claim-main"},
        available_figure_ids={"fig-loss"},
    )

    assert result.valid is True
    assert result.issues == []


def test_spine_requires_central_claim_to_be_used_by_a_section() -> None:
    spine = PaperSpine(
        topic_id="loss",
        central_claim_id="claim-main",
        sections=[
            SectionContract(
                section_id="results",
                role="results",
                title="Sampled response",
                purpose="Report a secondary observation.",
                required_claim_ids=["claim-secondary"],
            )
        ],
    )

    result = validate_spine(
        spine,
        available_claim_ids={"claim-main", "claim-secondary"},
        available_figure_ids=set(),
    )

    assert result.valid is False
    assert result.issues == ["spine central claim is not used by any section:claim-main"]


def test_spine_detects_prohibited_content_case_insensitively() -> None:
    spine = PaperSpine(
        topic_id="loss",
        central_claim_id="claim-main",
        sections=[
            SectionContract(
                section_id="results",
                role="results",
                title="Sampled response",
                purpose="Report only discrete evidence.",
                required_claim_ids=["claim-main"],
                prohibited_content=["optimal operating point"],
            )
        ],
    )

    result = validate_spine(
        spine,
        available_claim_ids={"claim-main"},
        available_figure_ids=set(),
        section_content={"results": "The Optimal Operating Point occurs between sampled cases."},
    )

    assert result.valid is False
    assert result.issues == ["section:results contains prohibited content:optimal operating point"]
