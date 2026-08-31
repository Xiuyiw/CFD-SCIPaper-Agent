from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

import pytest

from cfdpaper.publication.topics import RankedTopic, TopicRankingResult
from cfdpaper.scientific import ClaimCeiling, EvidenceMaturity
from cfdpaper.topic_generation.candidates import (
    CandidateConstructionResult,
    CandidateSkeleton,
    apply_generation_constraints,
    build_generated_candidates,
)
from cfdpaper.topic_generation.canonical import canonical_json_bytes, canonical_sha256
from cfdpaper.topic_generation.models import ScientificRelationFrame
from cfdpaper.topic_generation.opportunities import (
    OpportunitySemanticSignature,
    ParameterBinding,
    ResearchOpportunity,
    ScientificGap,
    UnitBinding,
    discover_research_opportunities,
)
from tests.topic_generation.test_opportunities import synthetic_snapshot


@dataclass(frozen=True)
class FieldFactRoleCoverage:
    """Candidate-specific structured facts that one wording field must preserve."""

    field: Literal["title", "research_question", "rationale", "differentiation"]
    required_roles: tuple[str, ...]
    required_fact_ids: tuple[str, ...]


@dataclass(frozen=True)
class ExpectedCandidateScientificContract:
    """Fixture-specific oracle for one emitted topic, without freezing English prose."""

    topic_id: str
    opportunity_id: str
    rank_position: int
    pattern: str
    subject_references: tuple[tuple[str, str], ...]
    contrast_references: tuple[tuple[str, str], ...]
    case_ids: tuple[str, ...]
    qoi_roles: tuple[tuple[str, str], ...]
    varied_parameter_ids: tuple[str, ...]
    controlled_parameter_ids: tuple[str, ...]
    parameter_bindings: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...]
    trend_or_association: str
    relation: tuple[str, str, str, str]
    claim_ceiling: str
    evidence_backlinks: tuple[str, ...]
    semantic_signature: bytes
    ranking_reason_codes: tuple[str, ...]
    figure_evidence_roles: tuple[str, ...]
    paper_spine_evidence_roles: tuple[str, ...]
    text_fact_role_coverage: tuple[FieldFactRoleCoverage, ...]


class CandidateTextContractMismatch(AssertionError):
    """Raised when generated wording drops or mutates locked scientific semantics."""


def _relation_for(pattern: str) -> tuple[ScientificRelationFrame, str | None]:
    if pattern == "matched-comparison":
        return (
            ScientificRelationFrame(
                relation_class="difference",
                polarity="difference-only",
                comparison_direction="variant-vs-reference",
                quantifier="pairwise",
            ),
            None,
        )
    if pattern == "ordered-parameter-response":
        return (
            ScientificRelationFrame(
                relation_class="ordered-response",
                polarity="increase",
                comparison_direction="parameter-ascending",
                quantifier="sampled-series-only",
            ),
            "monotonic-increasing",
        )
    if pattern == "coupled-association":
        return (
            ScientificRelationFrame(
                relation_class="coupled-association",
                polarity="positive",
                comparison_direction="symmetric",
                quantifier="sampled-cases-only",
            ),
            None,
        )
    return (
        ScientificRelationFrame(
            relation_class="robustness",
            polarity="not-applicable",
            comparison_direction="not-applicable",
            quantifier="validation-set-only",
        ),
        None,
    )


def opportunity_factory(
    *,
    pattern: str = "matched-comparison",
    case_ids: tuple[str, ...] = ("case-a", "case-b"),
    binding_case_ids: tuple[str, ...] | None = None,
    qoi_ids: tuple[str, ...] = ("qoi-response-a",),
    candidate_eligible: bool = True,
    defensible: bool = True,
    output_scope: str | None = None,
    supporting_evidence_ids: tuple[str, ...] = ("evidence-response",),
    constraint_provenance_evidence_ids: tuple[str, ...] = (),
    passed_gate_count: int = 6,
    evidence_maturity: str = "verified",
    independent_validation_linked: bool = False,
    literature_gap_maturity: str = "raw",
    claim_ceiling: str = "observation",
    gaps: tuple[ScientificGap, ...] = (),
) -> ResearchOpportunity:
    relation, trend_type = _relation_for(pattern)
    binding_cases = binding_case_ids or case_ids
    bindings = (
        ParameterBinding(
            parameter_id="parameter-control",
            role="controlled",
            case_ids=binding_cases,
            boundary_evidence_ids=("evidence-boundary-control",),
        ),
        ParameterBinding(
            parameter_id="parameter-varied",
            role="varied",
            case_ids=binding_cases,
            boundary_evidence_ids=("evidence-boundary-varied",),
        ),
    )
    signature = OpportunitySemanticSignature(
        pattern=pattern,
        case_ids=case_ids,
        qoi_roles=tuple(f"primary:{item}" for item in qoi_ids),
        parameter_bindings=bindings,
        trend_type=trend_type,
        relation=relation,
        validation_sensitivity_contrast_ids=(),
    )
    calculated_id = "opp-" + canonical_sha256(signature, domain=b"cfdpaper-opportunity-v1")[:16]
    if output_scope is None:
        output_scope = "manuscript-topic" if defensible else "direction-only"
    return ResearchOpportunity(
        opportunity_id=calculated_id,
        pattern=pattern,
        case_ids=case_ids,
        current_case_ids=case_ids,
        qoi_ids=qoi_ids,
        primary_qoi_ids=qoi_ids,
        supporting_evidence_ids=supporting_evidence_ids,
        constraint_provenance_evidence_ids=constraint_provenance_evidence_ids,
        unit_bindings=tuple(
            [
                *(
                    UnitBinding(
                        record_id=item,
                        record_kind="qoi",
                        unit="Pa",
                        compatible=True,
                    )
                    for item in qoi_ids
                ),
                UnitBinding(
                    record_id="parameter-varied",
                    record_kind="parameter",
                    unit="kg/s",
                    compatible=True,
                ),
                UnitBinding(
                    record_id="parameter-control",
                    record_kind="parameter",
                    unit="m/s",
                    compatible=True,
                ),
            ]
        ),
        comparability="verified",
        trend_type=trend_type,
        relation=relation,
        evidence_maturity=EvidenceMaturity(evidence_maturity),
        claim_ceiling=ClaimCeiling(claim_ceiling),
        candidate_eligible=candidate_eligible,
        defensible=defensible,
        output_scope=output_scope,
        gaps=gaps,
        prohibited_inferences=(
            "causation",
            "continuous optimum",
            "engineering operating boundary",
            "stable operating window",
            "unsampled continuity",
        ),
        rationale="Structured evidence bounds the discrete scientific opportunity.",
        required_evidence_kinds=("boundary", "case", "qoi"),
        parameter_ids=("parameter-control", "parameter-varied"),
        varied_parameter_ids=("parameter-varied",),
        controlled_parameter_ids=("parameter-control",),
        parameter_bindings=bindings,
        passed_gate_count=passed_gate_count,
        independent_validation_linked=independent_validation_linked,
        literature_gap_maturity=EvidenceMaturity(literature_gap_maturity),
        semantic_signature=signature,
    )


def _opportunity_with_relation(
    *,
    pattern: str,
    trend_type: str | None,
    relation: ScientificRelationFrame,
) -> ResearchOpportunity:
    base = opportunity_factory(pattern=pattern)
    signature = base.semantic_signature.model_copy(
        update={"trend_type": trend_type, "relation": relation}
    )
    return ResearchOpportunity.model_validate(
        {
            **base.model_dump(mode="python"),
            "opportunity_id": "opp-"
            + canonical_sha256(signature, domain=b"cfdpaper-opportunity-v1")[:16],
            "trend_type": trend_type,
            "relation": relation,
            "semantic_signature": signature,
        }
    )


def _humanize(identifier: str) -> str:
    return " ".join(identifier.replace("_", " ").replace("-", " ").split())


def _relation_text(
    pattern: str,
    trend_or_association: str,
    relation: tuple[str, str, str, str],
) -> str:
    _, polarity, _, _ = relation
    if pattern == "matched-comparison":
        if polarity == "difference-only":
            return "matched difference between the reference and variant cases"
        return f"matched {_humanize(polarity)} for the variant relative to the reference"
    if pattern == "ordered-parameter-response":
        trend = {
            "monotonic-increasing": "sampled monotonic increase",
            "monotonic-decreasing": "sampled monotonic decrease",
            "interior-peak": "sampled non-monotonic response with an interior peak",
            "interior-trough": "sampled non-monotonic response with an interior trough",
            "plateau": "sampled plateau response",
            "mixed": "mixed sampled response",
        }[trend_or_association]
        return f"{trend} across the discrete varied-parameter series"
    if pattern == "coupled-association":
        if polarity == "not-applicable":
            return "sampled association without an assigned sign"
        return f"{_humanize(polarity)} association across sampled cases"
    return "robustness across the validation or sensitivity contrast"


def _relation_semantic_aliases(
    pattern: str,
    trend_or_association: str,
    relation: tuple[str, str, str, str],
) -> tuple[str, ...]:
    _, polarity, _, _ = relation
    if pattern == "matched-comparison":
        if polarity == "difference-only":
            return ("matched difference", "reference", "variant")
        return (f"matched {_humanize(polarity)}", "variant relative to the reference")
    if pattern == "ordered-parameter-response":
        return (
            _relation_text(pattern, trend_or_association, relation).split(" across ")[0],
            "discrete varied-parameter series",
        )
    if pattern == "coupled-association":
        if polarity == "not-applicable":
            return ("sampled association", "without an assigned sign")
        return (f"{_humanize(polarity)} association", "across sampled cases")
    return ("robustness", "validation or sensitivity contrast")


def _inverse_relation_aliases(
    pattern: str,
    trend_or_association: str,
    relation: tuple[str, str, str, str],
) -> tuple[str, ...]:
    _, polarity, _, _ = relation
    if pattern == "matched-comparison":
        return {
            "increase": ("matched decrease",),
            "decrease": ("matched increase",),
            "difference-only": ("matched increase", "matched decrease"),
        }[polarity]
    if pattern == "ordered-parameter-response":
        return tuple(
            phrase
            for trend, phrase in {
                "monotonic-increasing": "sampled monotonic increase",
                "monotonic-decreasing": "sampled monotonic decrease",
                "interior-peak": "sampled non-monotonic response with an interior peak",
                "interior-trough": "sampled non-monotonic response with an interior trough",
                "plateau": "sampled plateau response",
                "mixed": "mixed sampled response",
            }.items()
            if trend != trend_or_association
        )
    if pattern == "coupled-association":
        return tuple(
            phrase
            for candidate, phrase in {
                "positive": "positive association",
                "negative": "negative association",
                "not-applicable": "sampled association without an assigned sign",
            }.items()
            if candidate != polarity
        )
    return ()


def _coverage_for(
    *,
    pattern: str,
    qoi_ids: tuple[str, ...],
    varied_parameter_ids: tuple[str, ...],
    case_ids: tuple[str, ...],
    evidence_ids: tuple[str, ...],
    trend_or_association: str,
    relation: tuple[str, str, str, str],
    claim_ceiling: str,
) -> tuple[FieldFactRoleCoverage, ...]:
    subject = varied_parameter_ids[0]
    contrast = "-vs-".join(case_ids)
    qoi_fact_ids = tuple(f"qoi:{qoi_id}" for qoi_id in qoi_ids)
    relation_id = f"relation:{pattern}:{trend_or_association}"
    return (
        FieldFactRoleCoverage(
            field="title",
            required_roles=(
                "scientific-relation",
                "subject",
                "contrast-or-intervention",
                "qoi-or-outcome",
            ),
            required_fact_ids=(
                relation_id,
                f"subject:{subject}",
                f"contrast:{contrast}",
                *qoi_fact_ids,
            ),
        ),
        FieldFactRoleCoverage(
            field="research_question",
            required_roles=(
                "scientific-relation",
                "subject",
                "contrast-or-intervention",
                "qoi-or-outcome",
            ),
            required_fact_ids=(
                relation_id,
                f"subject:{subject}",
                f"contrast:{contrast}",
                *qoi_fact_ids,
            ),
        ),
        FieldFactRoleCoverage(
            field="rationale",
            required_roles=(
                "scientific-relation",
                "qoi-or-outcome",
                "evidence-basis",
                "evidence-ceiling",
            ),
            required_fact_ids=(
                relation_id,
                *qoi_fact_ids,
                f"evidence:{evidence_ids[0]}",
                f"ceiling:{claim_ceiling}",
            ),
        ),
        FieldFactRoleCoverage(
            field="differentiation",
            required_roles=(
                "candidate-differentiation",
                "scientific-relation",
                "subject",
                "contrast-or-intervention",
                "qoi-or-outcome",
                "candidate-semantic-signature",
            ),
            required_fact_ids=(
                relation_id,
                f"subject:{subject}",
                f"contrast:{contrast}",
                *qoi_fact_ids,
                f"signature:{pattern}:{trend_or_association}",
            ),
        ),
    )


def _expected_contract(
    *,
    topic_id: str,
    opportunity_id: str,
    rank_position: int,
    pattern: str,
    case_ids: tuple[str, ...],
    qoi_ids: tuple[str, ...],
    supporting_evidence_ids: tuple[str, ...],
    trend_or_association: str,
    relation: tuple[str, str, str, str],
    claim_ceiling: str,
) -> ExpectedCandidateScientificContract:
    bindings = (
        (
            "parameter-control",
            "controlled",
            case_ids,
            tuple(f"evidence-boundary-control-{case_id[-1]}" for case_id in case_ids),
        ),
        (
            "parameter-varied",
            "varied",
            case_ids,
            tuple(f"evidence-boundary-factor-{case_id[-1]}" for case_id in case_ids),
        ),
    )
    assessment_evidence_ids = tuple(
        f"evidence-{kind}-{case_id[-1]}"
        for kind in ("case", "convergence", "conservation")
        for case_id in case_ids
    )
    all_supporting_evidence_ids = tuple(
        sorted(
            {
                *supporting_evidence_ids,
                *assessment_evidence_ids,
                *(item for _, _, _, evidence_ids in bindings for item in evidence_ids),
            }
        )
    )
    relation_frame = ScientificRelationFrame(
        relation_class=relation[0],
        polarity=relation[1],
        comparison_direction=relation[2],
        quantifier=relation[3],
    )
    signature = OpportunitySemanticSignature(
        pattern=pattern,
        case_ids=case_ids,
        qoi_roles=tuple(f"primary:{item}" for item in qoi_ids),
        parameter_bindings=tuple(
            ParameterBinding(
                parameter_id=parameter_id,
                role=role,
                case_ids=binding_cases,
                boundary_evidence_ids=boundary_evidence_ids,
            )
            for parameter_id, role, binding_cases, boundary_evidence_ids in bindings
        ),
        trend_type=None if trend_or_association == "not-applicable" else trend_or_association,
        relation=relation_frame,
        validation_sensitivity_contrast_ids=(),
    )
    figure_evidence_roles = tuple(
        sorted(
            {
                "case-qoi-comparison",
                "parameter:parameter-control",
                "parameter:parameter-varied",
                *(f"qoi:{item}" for item in qoi_ids),
                *(f"support:{item}" for item in all_supporting_evidence_ids),
            }
        )
    )
    paper_spine_evidence_roles = {
        "matched-comparison": ("results-comparison",),
        "ordered-parameter-response": ("results-response",),
        "coupled-association": ("results-association",),
        "validation-robustness": ("methods-validation",),
    }[pattern]
    return ExpectedCandidateScientificContract(
        topic_id=topic_id,
        opportunity_id=opportunity_id,
        rank_position=rank_position,
        pattern=pattern,
        subject_references=(("parameter", "parameter-varied"),),
        contrast_references=tuple(("case", item) for item in case_ids),
        case_ids=case_ids,
        qoi_roles=tuple((item, "primary") for item in qoi_ids),
        varied_parameter_ids=("parameter-varied",),
        controlled_parameter_ids=("parameter-control",),
        parameter_bindings=bindings,
        trend_or_association=trend_or_association,
        relation=relation,
        claim_ceiling=claim_ceiling,
        evidence_backlinks=all_supporting_evidence_ids,
        semantic_signature=canonical_json_bytes(signature),
        ranking_reason_codes=(
            "current-primary-evidence",
            "verified-comparability",
            "complete-parameter-binding",
            f"bounded-claim-ceiling:{claim_ceiling}",
        ),
        figure_evidence_roles=figure_evidence_roles,
        paper_spine_evidence_roles=paper_spine_evidence_roles,
        text_fact_role_coverage=_coverage_for(
            pattern=pattern,
            qoi_ids=qoi_ids,
            varied_parameter_ids=("parameter-varied",),
            case_ids=case_ids,
            evidence_ids=supporting_evidence_ids,
            trend_or_association=trend_or_association,
            relation=relation,
            claim_ceiling=claim_ceiling,
        ),
    )


def _mature_candidate_contracts() -> dict[str, ExpectedCandidateScientificContract]:
    cases = ("case-a", "case-b", "case-c")
    association = ("coupled-association", "positive", "symmetric", "sampled-cases-only")
    increasing = (
        "ordered-response",
        "increase",
        "parameter-ascending",
        "sampled-series-only",
    )
    contracts = (
        _expected_contract(
            topic_id="auto-b874c483c1c24472",
            opportunity_id="opp-0c443e4b06598c95",
            rank_position=0,
            pattern="coupled-association",
            case_ids=cases,
            qoi_ids=(
                "qoi-response-a",
                "qoi-response-b",
                "qoi-response-c",
                "qoi-secondary-a",
                "qoi-secondary-b",
                "qoi-secondary-c",
            ),
            supporting_evidence_ids=(
                "evidence-qoi-a",
                "evidence-qoi-b",
                "evidence-qoi-c",
                "evidence-secondary-a",
                "evidence-secondary-b",
                "evidence-secondary-c",
            ),
            trend_or_association="not-applicable",
            relation=association,
            claim_ceiling="association",
        ),
        _expected_contract(
            topic_id="auto-4745330999758d1a",
            opportunity_id="opp-4448fe4060791514",
            rank_position=1,
            pattern="ordered-parameter-response",
            case_ids=cases,
            qoi_ids=("qoi-secondary-a", "qoi-secondary-b", "qoi-secondary-c"),
            supporting_evidence_ids=(
                "evidence-secondary-a",
                "evidence-secondary-b",
                "evidence-secondary-c",
            ),
            trend_or_association="monotonic-increasing",
            relation=increasing,
            claim_ceiling="association",
        ),
        _expected_contract(
            topic_id="auto-392970a67f2d0bfd",
            opportunity_id="opp-748a9d0d4113f92c",
            rank_position=2,
            pattern="ordered-parameter-response",
            case_ids=cases,
            qoi_ids=("qoi-response-a", "qoi-response-b", "qoi-response-c"),
            supporting_evidence_ids=("evidence-qoi-a", "evidence-qoi-b", "evidence-qoi-c"),
            trend_or_association="monotonic-increasing",
            relation=increasing,
            claim_ceiling="association",
        ),
    )
    return {item.topic_id: item for item in contracts}


def _matched_primary_contract() -> dict[str, ExpectedCandidateScientificContract]:
    contract = _expected_contract(
        topic_id="auto-e6ce151e0198f137",
        opportunity_id="opp-6a9a80df930f4d30",
        rank_position=0,
        pattern="matched-comparison",
        case_ids=("case-a", "case-b"),
        qoi_ids=("qoi-response-a", "qoi-response-b"),
        supporting_evidence_ids=("evidence-qoi-a", "evidence-qoi-b"),
        trend_or_association="not-applicable",
        relation=("difference", "increase", "variant-vs-reference", "pairwise"),
        claim_ceiling="association",
    )
    return {contract.topic_id: contract}


def _ranking_reason_codes(opportunity: ResearchOpportunity) -> tuple[str, ...]:
    codes = ["current-primary-evidence"]
    if opportunity.comparability == "verified":
        codes.append("verified-comparability")
    if opportunity.parameter_bindings:
        codes.append("complete-parameter-binding")
    codes.append(f"bounded-claim-ceiling:{opportunity.claim_ceiling.value}")
    return tuple(codes)


def _paper_spine_evidence_roles(
    opportunity: ResearchOpportunity,
    skeleton: CandidateSkeleton,
) -> tuple[str, ...]:
    if "case-qoi-comparison" not in skeleton.figure_evidence_structure:
        raise CandidateTextContractMismatch("candidate lacks executable case-QoI figure evidence")
    return {
        "matched-comparison": ("results-comparison",),
        "ordered-parameter-response": ("results-response",),
        "coupled-association": ("results-association",),
        "validation-robustness": ("methods-validation",),
    }[opportunity.pattern]


def _fact_aliases(contract: ExpectedCandidateScientificContract, fact_id: str) -> tuple[str, ...]:
    if fact_id.startswith("subject:"):
        return (_humanize(fact_id.removeprefix("subject:")),)
    if fact_id.startswith("contrast:"):
        return (", ".join(_humanize(item) for item in contract.case_ids),)
    if fact_id.startswith("qoi:"):
        return (_humanize(fact_id.removeprefix("qoi:")),)
    if fact_id.startswith("relation:") or fact_id.startswith("signature:"):
        return _relation_semantic_aliases(
            contract.pattern,
            contract.trend_or_association,
            contract.relation,
        )
    if fact_id.startswith("evidence:"):
        return (
            "current structured evidence",
            *(_humanize(qoi_id) for qoi_id, _ in contract.qoi_roles),
            ", ".join(_humanize(case_id) for case_id in contract.case_ids),
        )
    if fact_id.startswith("ceiling:"):
        return (f"{fact_id.removeprefix('ceiling:')} claim ceiling",)
    raise AssertionError(f"unknown fact ID: {fact_id}")


def _assert_field_fact_coverage(
    text: str,
    coverage: FieldFactRoleCoverage,
    contract: ExpectedCandidateScientificContract,
) -> None:
    normalized = " ".join(text.casefold().split())
    if len(normalized.split()) < 8:
        raise CandidateTextContractMismatch(
            f"{coverage.field} is too generic to express scientific facts"
        )
    forbidden = (" causes ", " optimal ", " operating boundary ", "stable operating window")
    if any(token in normalized for token in forbidden):
        raise CandidateTextContractMismatch(
            f"{coverage.field} exceeds the locked scientific ceiling"
        )
    for fact_id in coverage.required_fact_ids:
        aliases = _fact_aliases(contract, fact_id)
        for phrase in aliases:
            if phrase not in normalized:
                raise CandidateTextContractMismatch(
                    f"{coverage.field} omits candidate-specific fact {fact_id}"
                )
            if f"not {phrase}" in normalized or f"no {phrase}" in normalized:
                raise CandidateTextContractMismatch(
                    f"{coverage.field} negates candidate-specific fact {fact_id}"
                )
        if fact_id.startswith("relation:") or fact_id.startswith("signature:"):
            if any(
                inverse in normalized
                for inverse in _inverse_relation_aliases(
                    contract.pattern,
                    contract.trend_or_association,
                    contract.relation,
                )
            ):
                raise CandidateTextContractMismatch(
                    f"{coverage.field} reverses candidate-specific relation {fact_id}"
                )
    if coverage.field == "rationale" and normalized.split() == list(
        " ".join(contract.evidence_backlinks).casefold().split()
    ):
        raise CandidateTextContractMismatch("rationale is evidence-ID-only text")
    if coverage.field == "differentiation" and normalized in {
        "this candidate is distinct.",
        "distinct scientific question.",
    }:
        raise CandidateTextContractMismatch("differentiation is vacuous")


def _candidate_scientific_contract(
    candidate_id: str,
    opportunity: ResearchOpportunity,
    skeleton: CandidateSkeleton,
) -> dict[str, object]:
    relation = opportunity.relation
    return {
        "topic_id": candidate_id,
        "opportunity_id": opportunity.opportunity_id,
        "pattern": opportunity.pattern,
        "subject_references": (("parameter", opportunity.varied_parameter_ids[0]),),
        "contrast_references": tuple(("case", item) for item in opportunity.case_ids),
        "case_ids": opportunity.case_ids,
        "qoi_roles": tuple((item, "primary") for item in opportunity.primary_qoi_ids),
        "varied_parameter_ids": opportunity.varied_parameter_ids,
        "controlled_parameter_ids": opportunity.controlled_parameter_ids,
        "parameter_bindings": tuple(
            (
                item.parameter_id,
                item.role,
                item.case_ids,
                item.boundary_evidence_ids,
            )
            for item in opportunity.parameter_bindings
        ),
        "trend_or_association": opportunity.trend_type or "not-applicable",
        "relation": (
            relation.relation_class,
            relation.polarity,
            relation.comparison_direction,
            relation.quantifier,
        ),
        "claim_ceiling": opportunity.claim_ceiling.value,
        "evidence_backlinks": tuple(
            sorted(
                {
                    *opportunity.supporting_evidence_ids,
                    *(
                        evidence_id
                        for binding in opportunity.parameter_bindings
                        for evidence_id in binding.boundary_evidence_ids
                    ),
                }
            )
        ),
        "semantic_signature": canonical_json_bytes(opportunity.semantic_signature),
        "ranking_reason_codes": _ranking_reason_codes(opportunity),
        "figure_evidence_roles": skeleton.figure_evidence_structure,
        "paper_spine_evidence_roles": _paper_spine_evidence_roles(opportunity, skeleton),
    }


def _assert_candidate_contracts(
    snapshot: object,
    constructed: CandidateConstructionResult,
    expected: dict[str, ExpectedCandidateScientificContract],
) -> None:
    discovered = discover_research_opportunities(snapshot)  # type: ignore[arg-type]
    opportunities = {item.opportunity_id: item for item in discovered.opportunities}
    candidates = {item.topic_id: item for item in constructed.candidate_input.candidates}
    skeletons = {item.candidate.topic_id: item for item in constructed.skeletons}
    mapping = dict(constructed.topic_to_opportunity)
    expected_ids = set(expected)
    if (
        set(candidates) != expected_ids
        or set(skeletons) != expected_ids
        or set(mapping) != expected_ids
    ):
        raise CandidateTextContractMismatch("emitted candidates do not match the per-topic oracle")
    if tuple(item.topic_id for item in constructed.candidate_input.candidates) != tuple(
        item.topic_id for item in sorted(expected.values(), key=lambda item: item.rank_position)
    ):
        raise CandidateTextContractMismatch(
            "candidate rank order differs from the scientific oracle"
        )
    for topic_id, contract in expected.items():
        if mapping[topic_id] != contract.opportunity_id:
            raise CandidateTextContractMismatch(f"{topic_id} maps to the wrong opportunity")
        opportunity = opportunities.get(contract.opportunity_id)
        if opportunity is None:
            raise CandidateTextContractMismatch(f"{topic_id} opportunity is absent from discovery")
        skeleton = skeletons[topic_id]
        actual = _candidate_scientific_contract(topic_id, opportunity, skeleton)
        for field in (
            "topic_id",
            "opportunity_id",
            "pattern",
            "subject_references",
            "contrast_references",
            "case_ids",
            "qoi_roles",
            "varied_parameter_ids",
            "controlled_parameter_ids",
            "parameter_bindings",
            "trend_or_association",
            "relation",
            "claim_ceiling",
            "evidence_backlinks",
            "semantic_signature",
            "ranking_reason_codes",
            "figure_evidence_roles",
            "paper_spine_evidence_roles",
        ):
            if actual[field] != getattr(contract, field):
                raise CandidateTextContractMismatch(f"{topic_id} mismatches {field}")
        texts = {
            "title": candidates[topic_id].title,
            "research_question": candidates[topic_id].research_question,
            "rationale": skeleton.rationale,
            "differentiation": skeleton.differentiation,
        }
        for coverage in contract.text_fact_role_coverage:
            _assert_field_fact_coverage(texts[coverage.field], coverage, contract)


def _rewrite_candidate_text(
    constructed: CandidateConstructionResult,
    topic_id: str,
    **updates: str,
) -> CandidateConstructionResult:
    updated_skeletons: list[CandidateSkeleton] = []
    for skeleton in constructed.skeletons:
        if skeleton.candidate.topic_id != topic_id:
            updated_skeletons.append(skeleton)
            continue
        candidate_updates = {
            key: value for key, value in updates.items() if key in {"title", "research_question"}
        }
        skeleton_updates = {
            key: value for key, value in updates.items() if key in {"rationale", "differentiation"}
        }
        candidate = skeleton.candidate.model_copy(update=candidate_updates)
        updated_skeletons.append(
            skeleton.model_copy(update={"candidate": candidate, **skeleton_updates})
        )
    candidates = tuple(item.candidate for item in updated_skeletons)
    return constructed.model_copy(
        update={
            "candidate_input": constructed.candidate_input.model_copy(
                update={"candidates": candidates}
            ),
            "skeletons": tuple(updated_skeletons),
        }
    )


def _text_contract_for_skeleton(
    opportunity: ResearchOpportunity,
    skeleton: CandidateSkeleton,
) -> ExpectedCandidateScientificContract:
    """Build a field-level oracle without replacing the discovery vertical slice."""

    relation = opportunity.relation
    return _expected_contract(
        topic_id=skeleton.candidate.topic_id,
        opportunity_id=opportunity.opportunity_id,
        rank_position=0,
        pattern=opportunity.pattern,
        case_ids=opportunity.current_case_ids,
        qoi_ids=opportunity.primary_qoi_ids,
        supporting_evidence_ids=opportunity.supporting_evidence_ids,
        trend_or_association=opportunity.trend_type or "not-applicable",
        relation=(
            relation.relation_class,
            relation.polarity,
            relation.comparison_direction,
            relation.quantifier,
        ),
        claim_ceiling=opportunity.claim_ceiling.value,
    )


def _mutate_candidate_wording(
    constructed: CandidateConstructionResult,
    mutation: str,
) -> CandidateConstructionResult:
    target, alternate = constructed.skeletons[:2]
    if mutation in {
        "swap-title-only-same-pattern-distinct-qoi",
        "swap-question-only-same-pattern-distinct-qoi",
        "swap-rationale-only-same-pattern-distinct-qoi",
        "swap-differentiation-only-same-pattern-distinct-qoi",
        "ordered-same-polarity-distinct-qoi-swap",
    }:
        target, alternate = constructed.skeletons[1:3]
    topic_id = target.candidate.topic_id
    if mutation == "generic-topic-a":
        return _rewrite_candidate_text(constructed, topic_id, title="Generic Topic A")
    if mutation == "unrelated-text":
        return _rewrite_candidate_text(
            constructed,
            topic_id,
            title="Unrelated topic about an unrelated outcome",
            research_question="What happens in an unrelated setting?",
            rationale="An unrelated observation is discussed here.",
            differentiation="This is unrelated to the scientific record.",
        )
    if mutation == "swap-whole-candidate-text":
        return _rewrite_candidate_text(
            constructed,
            topic_id,
            title=alternate.candidate.title,
            research_question=alternate.candidate.research_question,
            rationale=alternate.rationale,
            differentiation=alternate.differentiation,
        )
    if mutation == "swap-title-only-same-pattern-distinct-qoi":
        return _rewrite_candidate_text(constructed, topic_id, title=alternate.candidate.title)
    if mutation == "swap-question-only-same-pattern-distinct-qoi":
        return _rewrite_candidate_text(
            constructed,
            topic_id,
            research_question=alternate.candidate.research_question,
        )
    if mutation == "swap-rationale-only-same-pattern-distinct-qoi":
        return _rewrite_candidate_text(constructed, topic_id, rationale=alternate.rationale)
    if mutation == "swap-differentiation-only-same-pattern-distinct-qoi":
        return _rewrite_candidate_text(
            constructed,
            topic_id,
            differentiation=alternate.differentiation,
        )
    if mutation == "remove-subject":
        return _rewrite_candidate_text(
            constructed,
            topic_id,
            title=target.candidate.title.replace("parameter varied", "parameter"),
        )
    if mutation == "remove-contrast":
        return _rewrite_candidate_text(
            constructed,
            topic_id,
            research_question=target.candidate.research_question.replace(
                "case a, case b, case c", "the comparison"
            ),
        )
    if mutation == "remove-qoi":
        return _rewrite_candidate_text(
            constructed,
            topic_id,
            differentiation=target.differentiation.replace("qoi response a", "the outcome"),
        )
    if mutation == "remove-nonfirst-qoi":
        return _rewrite_candidate_text(
            constructed,
            topic_id,
            differentiation=target.differentiation.replace("qoi response b", "the second outcome"),
        )
    if mutation == "generic-rationale":
        return _rewrite_candidate_text(
            constructed,
            topic_id,
            rationale="The available data motivate further investigation of this topic.",
        )
    if mutation == "generic-differentiation":
        return _rewrite_candidate_text(
            constructed,
            topic_id,
            differentiation="This candidate is distinct.",
        )
    if mutation == "token-soup":
        return _rewrite_candidate_text(
            constructed,
            topic_id,
            title=(
                "parameter varied qoi response a case a case b case c positive association "
                "symmetric sampled evidence ceiling"
            ),
        )
    if mutation.startswith("negated-"):
        return _rewrite_candidate_text(
            constructed,
            topic_id,
            title=f"Not {target.candidate.title}",
        )
    if mutation == "reverse-relation":
        return _rewrite_candidate_text(
            constructed,
            topic_id,
            title=target.candidate.title.replace("Positive association", "Negative association"),
        )
    if mutation == "cross-candidate-title-swap":
        return _rewrite_candidate_text(constructed, topic_id, title=alternate.candidate.title)
    if mutation == "ordered-same-polarity-distinct-qoi-swap":
        return _rewrite_candidate_text(constructed, topic_id, title=alternate.candidate.title)
    if mutation == "association-robustness-family-swap":
        return _rewrite_candidate_text(
            constructed,
            topic_id,
            title=target.candidate.title.replace("Positive association", "Robustness"),
        )
    if mutation == "evidence-ids-only-rationale":
        return _rewrite_candidate_text(
            constructed,
            topic_id,
            rationale="evidence-qoi-a evidence-qoi-b evidence-qoi-c",
        )
    if mutation == "vacuous-differentiation":
        return _rewrite_candidate_text(
            constructed,
            topic_id,
            differentiation="Distinct scientific question.",
        )
    raise AssertionError(f"unknown mutation: {mutation}")


def test_candidate_heuristics_match_exact_conservative_formulas() -> None:
    opportunity = opportunity_factory(
        case_ids=("case-a", "case-b", "case-c", "case-d", "case-e"),
        passed_gate_count=6,
        evidence_maturity="verified",
        independent_validation_linked=True,
        literature_gap_maturity="verified",
    )

    result = build_generated_candidates((opportunity,))
    candidate = result.candidate_input.candidates[0]

    assert candidate.significance == 0.7
    assert candidate.novelty == 0.5
    assert candidate.minimum_verified_evidence == max(1, len(candidate.required_evidence_kinds))
    assert result.gaps == ("insufficient-distinct-opportunities",)


@pytest.mark.parametrize("count", [2, 3, 4, 5, 6])
def test_candidate_selection_returns_at_most_four_distinct_questions(count: int) -> None:
    patterns = (
        "matched-comparison",
        "ordered-parameter-response",
        "coupled-association",
        "validation-robustness",
    )
    opportunities = tuple(
        opportunity_factory(
            pattern=patterns[index % len(patterns)],
            qoi_ids=(f"qoi-{index}",),
            case_ids=(f"case-{index}", f"case-{index + 1}", f"case-{index + 2}"),
        )
        for index in range(count)
    )

    result = build_generated_candidates(opportunities)

    assert len(result.candidate_input.candidates) == min(count, 4)
    assert len({item.research_question for item in result.candidate_input.candidates}) == len(
        result.candidate_input.candidates
    )


def test_exact_and_near_duplicate_opportunities_collapse_at_point_eight_overlap() -> None:
    first = opportunity_factory(
        case_ids=("a", "b", "c", "d"),
        binding_case_ids=("a", "b", "c", "d"),
    )
    exact = ResearchOpportunity.model_validate(first.model_dump(mode="python"))
    near = opportunity_factory(
        case_ids=("a", "b", "c", "d", "f"),
        binding_case_ids=("a", "b", "c", "d"),
    )

    result = build_generated_candidates((first, exact, near))

    assert len(result.candidate_input.candidates) == 1
    assert result.gaps == ("insufficient-distinct-opportunities",)


def test_candidate_support_is_current_and_reverse_traceable() -> None:
    opportunity = opportunity_factory(
        supporting_evidence_ids=("evidence-current",),
        constraint_provenance_evidence_ids=("evidence-stale",),
    )

    result = build_generated_candidates((opportunity,))
    candidate = result.candidate_input.candidates[0]

    assert candidate.supporting_evidence_ids == ("evidence-current",)
    assert "evidence-stale" not in candidate.supporting_evidence_ids
    assert result.topic_to_opportunity == ((candidate.topic_id, opportunity.opportunity_id),)


def test_ineligible_is_filtered_and_direction_only_never_becomes_manuscript() -> None:
    blocked = opportunity_factory(
        candidate_eligible=False,
        defensible=False,
        output_scope="missing-evidence",
    )
    direction = opportunity_factory(
        pattern="ordered-parameter-response",
        candidate_eligible=True,
        defensible=False,
        output_scope="direction-only",
    )
    result = build_generated_candidates((blocked, direction))
    raw = TopicRankingResult(
        outcome="manuscript",
        ranked_topics=[
            RankedTopic(
                candidate=result.candidate_input.candidates[0],
                score=0.8,
                evidence_coverage=1.0,
                verified_evidence_count=3,
                defensible=True,
            )
        ],
        reason="Raw ranking accepted the candidate.",
    )

    projected = apply_generation_constraints(
        raw,
        opportunities_by_topic_id={result.skeletons[0].candidate.topic_id: direction},
    )

    assert [item.opportunity_id for item in result.skeletons] == [direction.opportunity_id]
    assert projected.outcome == "analysis-note"
    assert all(not item.defensible for item in projected.ranked_topics)


def test_mature_snapshot_vertical_slice_uses_task4_snapshot_and_task5_discovery() -> None:
    snapshot = synthetic_snapshot(second_qoi_values=(300.0, 320.0, 340.0))
    discovered = discover_research_opportunities(snapshot)

    constructed = build_generated_candidates(discovered.opportunities)

    assert 2 <= len(constructed.candidate_input.candidates) <= 4
    assert len(constructed.skeletons) == len(constructed.candidate_input.candidates)
    assert len(constructed.topic_to_opportunity) == len(constructed.candidate_input.candidates)
    topic_to_opportunity = dict(constructed.topic_to_opportunity)
    assert all(
        skeleton.opportunity_id == topic_to_opportunity[skeleton.candidate.topic_id]
        for skeleton in constructed.skeletons
    )


def test_mature_vertical_slice_matches_every_candidate_scientific_contract() -> None:
    snapshot = synthetic_snapshot(second_qoi_values=(300.0, 320.0, 340.0))
    discovered = discover_research_opportunities(snapshot)
    constructed = build_generated_candidates(discovered.opportunities)

    _assert_candidate_contracts(snapshot, constructed, _mature_candidate_contracts())


def test_matched_primary_candidate_preserves_the_full_relation_frame() -> None:
    snapshot = synthetic_snapshot(values=(1.0, 2.0))
    discovered = discover_research_opportunities(snapshot)
    constructed = build_generated_candidates(discovered.opportunities)

    _assert_candidate_contracts(snapshot, constructed, _matched_primary_contract())


@pytest.mark.parametrize(
    "pattern, relation_phrase",
    (
        ("matched-comparison", "matched difference"),
        ("ordered-parameter-response", "sampled"),
        ("coupled-association", "association"),
        ("validation-robustness", "robustness"),
    ),
)
def test_candidate_wording_covers_subject_contrast_qoi_and_bounded_relation(
    pattern: str, relation_phrase: str
) -> None:
    opportunity = opportunity_factory(pattern=pattern)

    skeleton = build_generated_candidates((opportunity,)).skeletons[0]
    text = " ".join(
        (
            skeleton.candidate.title,
            skeleton.candidate.research_question,
            skeleton.rationale,
            skeleton.differentiation,
        )
    ).casefold()

    assert "parameter varied" in text
    assert "qoi response a" in text
    assert relation_phrase in text
    assert "evidence-response" not in text
    assert not any(
        phrase in text
        for phrase in (
            "causes",
            "optimal",
            "operating boundary",
            "stable operating window",
        )
    )


def test_each_candidate_text_field_preserves_its_bounded_fact_roles() -> None:
    skeleton = build_generated_candidates((opportunity_factory(),)).skeletons[0]

    for text in (skeleton.candidate.title, skeleton.candidate.research_question):
        lowered = text.casefold()
        assert "parameter varied" in lowered
        assert "qoi response a" in lowered
        assert "case a" in lowered
    rationale = skeleton.rationale.casefold()
    assert "matched difference" in rationale
    assert "qoi response a" in rationale
    assert "observation" in rationale
    differentiation = skeleton.differentiation.casefold()
    assert "matched difference" in differentiation
    assert "parameter varied" in differentiation
    assert "qoi response a" in differentiation
    assert "case a" in differentiation


def test_generation_constraints_can_only_lower_defensibility_and_merge_offline_gaps() -> None:
    opportunity = opportunity_factory(
        defensible=False,
        gaps=(ScientificGap(code="weak-convergence", message="Convergence is weak."),),
    )
    constructed = build_generated_candidates((opportunity,))
    candidate = constructed.candidate_input.candidates[0]
    raw = TopicRankingResult(
        outcome="manuscript",
        ranked_topics=[
            RankedTopic(
                candidate=candidate,
                score=0.8,
                evidence_coverage=1.0,
                verified_evidence_count=3,
                defensible=True,
                missing_evidence=["existing-gap"],
            )
        ],
        reason="Raw ranking accepted the candidate.",
    )
    projected = apply_generation_constraints(
        raw,
        opportunities_by_topic_id={candidate.topic_id: opportunity},
    )

    assert projected.outcome == "analysis-note"
    assert projected.ranked_topics[0].defensible is False
    assert projected.ranked_topics[0].missing_evidence == [
        "existing-gap",
        "offline:weak-convergence",
    ]
    with pytest.raises(ValueError, match="mapping"):
        apply_generation_constraints(raw, opportunities_by_topic_id={})


def test_generation_constraints_accepts_a_valid_title_and_question_refinement() -> None:
    opportunity = opportunity_factory()
    offline = build_generated_candidates((opportunity,)).candidate_input.candidates[0]
    refined = offline.model_copy(
        update={
            "title": "Matched difference in response for the variant relative to the reference",
            "research_question": (
                "How does the response differ between the reference and variant cases?"
            ),
        }
    )
    assert refined.topic_id == offline.topic_id
    assert refined.model_dump(exclude={"title", "research_question"}) == offline.model_dump(
        exclude={"title", "research_question"}
    )
    ranking = TopicRankingResult(
        outcome="manuscript",
        ranked_topics=[
            RankedTopic(
                candidate=refined,
                score=0.8,
                evidence_coverage=1.0,
                verified_evidence_count=3,
                defensible=True,
            )
        ],
        reason="A validated refinement retains the offline scientific identity.",
    )

    projected = apply_generation_constraints(
        ranking,
        opportunities_by_topic_id={offline.topic_id: opportunity},
    )

    assert projected.ranked_topics[0].candidate.title == refined.title
    assert projected.ranked_topics[0].candidate.research_question == refined.research_question


@pytest.mark.parametrize(
    ("claim_ceiling", "expected_maturity"),
    (
        ("observation", "verified"),
        ("validation", "verified"),
        ("engineering", "author-approved"),
    ),
)
def test_required_maturity_is_author_approved_only_for_engineering_ceiling(
    claim_ceiling: str, expected_maturity: str
) -> None:
    candidate = build_generated_candidates(
        (opportunity_factory(claim_ceiling=claim_ceiling),)
    ).candidate_input.candidates[0]

    assert candidate.required_maturity == expected_maturity


def test_construction_result_rejects_topic_mapping_cardinality_mismatch() -> None:
    opportunity = opportunity_factory()
    result = build_generated_candidates((opportunity,))

    with pytest.raises(ValueError, match="mapping"):
        CandidateConstructionResult.model_validate(
            {
                **result.model_dump(mode="python"),
                "topic_to_opportunity": (),
            }
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "generic-topic-a",
        "unrelated-text",
        "swap-whole-candidate-text",
        "swap-title-only-same-pattern-distinct-qoi",
        "swap-question-only-same-pattern-distinct-qoi",
        "swap-rationale-only-same-pattern-distinct-qoi",
        "swap-differentiation-only-same-pattern-distinct-qoi",
        "remove-subject",
        "remove-contrast",
        "remove-qoi",
        "remove-nonfirst-qoi",
        "generic-rationale",
        "generic-differentiation",
        "token-soup",
        "negated-matched-relation",
        "negated-ordered-relation",
        "negated-association-relation",
        "negated-robustness-relation",
        "reverse-relation",
        "cross-candidate-title-swap",
        "ordered-same-polarity-distinct-qoi-swap",
        "association-robustness-family-swap",
        "evidence-ids-only-rationale",
        "vacuous-differentiation",
    ),
)
def test_candidate_text_contract_rejects_semantic_mutations(mutation: str) -> None:
    snapshot = synthetic_snapshot(second_qoi_values=(300.0, 320.0, 340.0))
    discovered = discover_research_opportunities(snapshot)
    constructed = build_generated_candidates(discovered.opportunities)

    with pytest.raises(CandidateTextContractMismatch):
        _assert_candidate_contracts(
            snapshot,
            _mutate_candidate_wording(constructed, mutation),
            _mature_candidate_contracts(),
        )


@pytest.mark.parametrize(
    "field",
    ("title", "research_question", "rationale", "differentiation"),
)
def test_single_field_swaps_fail_for_shared_envelope_with_distinct_candidate_provenance(
    field: Literal["title", "research_question", "rationale", "differentiation"],
) -> None:
    """A shared scientific envelope must not hide candidate-specific provenance loss."""

    left = opportunity_factory(
        case_ids=("case-left-reference", "case-left-variant"),
        binding_case_ids=("case-left-reference", "case-left-variant"),
        qoi_ids=("qoi-shared-response",),
        supporting_evidence_ids=("evidence-left-response",),
    )
    right = opportunity_factory(
        case_ids=("case-right-reference", "case-right-variant"),
        binding_case_ids=("case-right-reference", "case-right-variant"),
        qoi_ids=("qoi-shared-response",),
        supporting_evidence_ids=("evidence-right-response",),
    )
    assert left.pattern == right.pattern
    assert left.primary_qoi_ids == right.primary_qoi_ids
    assert left.claim_ceiling == right.claim_ceiling
    assert left.relation == right.relation
    assert left.current_case_ids != right.current_case_ids
    assert left.semantic_signature != right.semantic_signature
    assert left.supporting_evidence_ids != right.supporting_evidence_ids

    constructed = build_generated_candidates((left, right))
    mapping = dict(constructed.topic_to_opportunity)
    skeletons = {mapping[item.candidate.topic_id]: item for item in constructed.skeletons}
    left_skeleton = skeletons[left.opportunity_id]
    right_skeleton = skeletons[right.opportunity_id]
    replacement = {
        "title": right_skeleton.candidate.title,
        "research_question": right_skeleton.candidate.research_question,
        "rationale": right_skeleton.rationale,
        "differentiation": right_skeleton.differentiation,
    }[field]
    mutated = _rewrite_candidate_text(
        constructed,
        left_skeleton.candidate.topic_id,
        **{field: replacement},
    )
    mutated_left = next(
        item
        for item in mutated.skeletons
        if item.candidate.topic_id == left_skeleton.candidate.topic_id
    )
    contract = _text_contract_for_skeleton(left, left_skeleton)
    coverage = next(item for item in contract.text_fact_role_coverage if item.field == field)
    texts = {
        "title": mutated_left.candidate.title,
        "research_question": mutated_left.candidate.research_question,
        "rationale": mutated_left.rationale,
        "differentiation": mutated_left.differentiation,
    }

    with pytest.raises(CandidateTextContractMismatch):
        _assert_field_fact_coverage(texts[field], coverage, contract)


@pytest.mark.parametrize(
    "pattern",
    (
        "matched-comparison",
        "ordered-parameter-response",
        "coupled-association",
        "validation-robustness",
    ),
)
def test_each_relation_family_rejects_a_negated_locked_relation(pattern: str) -> None:
    opportunity = opportunity_factory(pattern=pattern)
    skeleton = build_generated_candidates((opportunity,)).skeletons[0]
    relation = opportunity.relation
    base = next(iter(_matched_primary_contract().values()))
    trend_or_association = opportunity.trend_type or "not-applicable"
    contract = replace(
        base,
        pattern=pattern,
        trend_or_association=trend_or_association,
        relation=(
            relation.relation_class,
            relation.polarity,
            relation.comparison_direction,
            relation.quantifier,
        ),
        text_fact_role_coverage=_coverage_for(
            pattern=pattern,
            qoi_ids=opportunity.primary_qoi_ids,
            varied_parameter_ids=opportunity.varied_parameter_ids,
            case_ids=opportunity.case_ids,
            evidence_ids=opportunity.supporting_evidence_ids,
            trend_or_association=trend_or_association,
            relation=(
                relation.relation_class,
                relation.polarity,
                relation.comparison_direction,
                relation.quantifier,
            ),
            claim_ceiling=opportunity.claim_ceiling.value,
        ),
    )

    with pytest.raises(CandidateTextContractMismatch):
        _assert_field_fact_coverage(
            f"Not {skeleton.candidate.title}",
            contract.text_fact_role_coverage[0],
            contract,
        )


@pytest.mark.parametrize(
    ("pattern", "trend_type", "frame"),
    (
        (
            "matched-comparison",
            None,
            ScientificRelationFrame(
                relation_class="difference",
                polarity="increase",
                comparison_direction="variant-vs-reference",
                quantifier="pairwise",
            ),
        ),
        (
            "matched-comparison",
            None,
            ScientificRelationFrame(
                relation_class="difference",
                polarity="decrease",
                comparison_direction="variant-vs-reference",
                quantifier="pairwise",
            ),
        ),
        (
            "matched-comparison",
            None,
            ScientificRelationFrame(
                relation_class="difference",
                polarity="difference-only",
                comparison_direction="variant-vs-reference",
                quantifier="pairwise",
            ),
        ),
        (
            "ordered-parameter-response",
            "monotonic-increasing",
            ScientificRelationFrame(
                relation_class="ordered-response",
                polarity="increase",
                comparison_direction="parameter-ascending",
                quantifier="sampled-series-only",
            ),
        ),
        (
            "ordered-parameter-response",
            "monotonic-decreasing",
            ScientificRelationFrame(
                relation_class="ordered-response",
                polarity="decrease",
                comparison_direction="parameter-ascending",
                quantifier="sampled-series-only",
            ),
        ),
        (
            "ordered-parameter-response",
            "interior-peak",
            ScientificRelationFrame(
                relation_class="ordered-response",
                polarity="non-monotonic",
                comparison_direction="parameter-ascending",
                quantifier="sampled-series-only",
            ),
        ),
        (
            "ordered-parameter-response",
            "plateau",
            ScientificRelationFrame(
                relation_class="ordered-response",
                polarity="plateau",
                comparison_direction="parameter-ascending",
                quantifier="sampled-series-only",
            ),
        ),
        (
            "coupled-association",
            None,
            ScientificRelationFrame(
                relation_class="coupled-association",
                polarity="negative",
                comparison_direction="symmetric",
                quantifier="sampled-cases-only",
            ),
        ),
        (
            "coupled-association",
            None,
            ScientificRelationFrame(
                relation_class="coupled-association",
                polarity="not-applicable",
                comparison_direction="symmetric",
                quantifier="sampled-cases-only",
            ),
        ),
        (
            "validation-robustness",
            None,
            ScientificRelationFrame(
                relation_class="robustness",
                polarity="not-applicable",
                comparison_direction="not-applicable",
                quantifier="validation-set-only",
            ),
        ),
    ),
)
def test_offline_wording_preserves_relation_semantics_without_internal_audit_jargon(
    pattern: str,
    trend_type: str | None,
    frame: ScientificRelationFrame,
) -> None:
    opportunity = _opportunity_with_relation(
        pattern=pattern,
        trend_type=trend_type,
        relation=frame,
    )
    skeleton = build_generated_candidates((opportunity,)).skeletons[0]
    relation = (
        frame.relation_class,
        frame.polarity,
        frame.comparison_direction,
        frame.quantifier,
    )
    aliases = _relation_semantic_aliases(
        pattern,
        trend_type or "not-applicable",
        relation,
    )

    for text in (
        skeleton.candidate.title,
        skeleton.candidate.research_question,
        skeleton.rationale,
        skeleton.differentiation,
    ):
        normalized = text.casefold()
        assert all(alias in normalized for alias in aliases)
        assert not any(token in normalized for token in (" polarity", " direction", " quantifier"))


def test_coupled_wording_uses_between_for_a_two_qoi_association() -> None:
    opportunity = opportunity_factory(
        pattern="coupled-association",
        qoi_ids=("qoi-left", "qoi-right"),
    )

    skeleton = build_generated_candidates((opportunity,)).skeletons[0]

    assert "positive association between qoi left and qoi right across sampled cases" in (
        skeleton.candidate.title.casefold()
    )


def test_candidate_construction_is_byte_identical_for_permuted_opportunities() -> None:
    snapshot = synthetic_snapshot(second_qoi_values=(300.0, 320.0, 340.0))
    opportunities = discover_research_opportunities(snapshot).opportunities

    original = build_generated_candidates(opportunities)
    permuted = build_generated_candidates(tuple(reversed(opportunities)))

    assert canonical_json_bytes(original) == canonical_json_bytes(permuted)
    assert original.candidate_input.candidates == permuted.candidate_input.candidates
    assert original.topic_to_opportunity == permuted.topic_to_opportunity


def test_zero_and_one_opportunity_results_report_the_honest_distinctness_gap() -> None:
    one = opportunity_factory()

    assert build_generated_candidates(()).gaps == ("insufficient-distinct-opportunities",)
    assert build_generated_candidates((one,)).gaps == ("insufficient-distinct-opportunities",)


def test_construction_rejects_wrong_mapping_value_and_duplicate_skeleton_identity() -> None:
    result = build_generated_candidates((opportunity_factory(),))
    payload = result.model_dump(mode="python")
    payload["topic_to_opportunity"] = (
        (result.skeletons[0].candidate.topic_id, "opp-0000000000000000"),
    )

    with pytest.raises(ValueError, match="mapping"):
        CandidateConstructionResult.model_validate(payload)

    duplicate_payload = result.model_dump(mode="python")
    duplicate_payload["candidate_input"]["candidates"] *= 2
    duplicate_payload["skeletons"] *= 2
    duplicate_payload["topic_to_opportunity"] *= 2
    with pytest.raises(ValueError, match="mapping|align"):
        CandidateConstructionResult.model_validate(duplicate_payload)

    reused_opportunity_payload = result.model_dump(mode="python")
    cloned_skeleton = dict(reused_opportunity_payload["skeletons"][0])
    cloned_candidate = dict(cloned_skeleton["candidate"])
    cloned_candidate["topic_id"] = "auto-ffffffffffffffff"
    cloned_skeleton["candidate"] = cloned_candidate
    reused_opportunity_payload["candidate_input"]["candidates"] += (cloned_candidate,)
    reused_opportunity_payload["skeletons"] += (cloned_skeleton,)
    reused_opportunity_payload["topic_to_opportunity"] += (
        ("auto-ffffffffffffffff", result.skeletons[0].opportunity_id),
    )
    with pytest.raises(ValueError, match="reuse"):
        CandidateConstructionResult.model_validate(reused_opportunity_payload)


def test_skeleton_rejects_unsorted_or_duplicate_parameter_and_figure_roles() -> None:
    skeleton = build_generated_candidates((opportunity_factory(),)).skeletons[0]
    payload = skeleton.model_dump(mode="python")
    payload["parameter_ids"] = tuple(reversed(payload["parameter_ids"]))

    with pytest.raises(ValueError, match="parameter IDs"):
        CandidateSkeleton.model_validate(payload)

    payload = skeleton.model_dump(mode="python")
    payload["parameter_ids"] = ("",)
    with pytest.raises(ValueError, match="parameter IDs"):
        CandidateSkeleton.model_validate(payload)

    payload = skeleton.model_dump(mode="python")
    payload["figure_evidence_structure"] = (
        payload["figure_evidence_structure"][0],
        payload["figure_evidence_structure"][0],
    )
    with pytest.raises(ValueError, match="figure evidence"):
        CandidateSkeleton.model_validate(payload)

    payload = skeleton.model_dump(mode="python")
    payload["figure_evidence_structure"] = ("",)
    with pytest.raises(ValueError, match="figure evidence"):
        CandidateSkeleton.model_validate(payload)


def test_generation_constraints_rejects_swapped_or_forged_topic_identity() -> None:
    first = opportunity_factory(qoi_ids=("qoi-first",))
    second = opportunity_factory(pattern="ordered-parameter-response", qoi_ids=("qoi-second",))
    constructed = build_generated_candidates((first, second))
    ranking = TopicRankingResult(
        outcome="manuscript",
        ranked_topics=[
            RankedTopic(
                candidate=item,
                score=0.8,
                evidence_coverage=1.0,
                verified_evidence_count=3,
                defensible=True,
            )
            for item in constructed.candidate_input.candidates
        ],
        reason="Raw ranking accepted candidates.",
    )
    first_topic, second_topic = (item.topic_id for item in constructed.candidate_input.candidates)

    with pytest.raises(ValueError, match="identity"):
        apply_generation_constraints(
            ranking,
            opportunities_by_topic_id={first_topic: second, second_topic: first},
        )
    with pytest.raises(ValueError, match="identity"):
        apply_generation_constraints(
            ranking,
            opportunities_by_topic_id={
                first_topic: opportunity_factory(qoi_ids=("forged",)),
                second_topic: second,
            },
        )
    with pytest.raises(ValueError, match="mapping"):
        apply_generation_constraints(
            ranking,
            opportunities_by_topic_id={first_topic: first},
        )
