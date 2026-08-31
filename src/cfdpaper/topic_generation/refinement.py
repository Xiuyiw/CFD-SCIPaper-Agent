"""Validate optional provider wording without changing locked topic science."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import Field, field_validator, model_validator

from cfdpaper.contracts import TaskContextPacket
from cfdpaper.providers import AIProvider
from cfdpaper.publication.topics import TopicCandidate
from cfdpaper.scientific.units import canonical_unit as registered_canonical_unit
from cfdpaper.topic_generation.candidates import CandidateSkeleton
from cfdpaper.topic_generation.canonical import canonical_json_bytes, canonical_sha256
from cfdpaper.topic_generation.models import (
    SHA256_PATTERN,
    GeneratedCandidateEnvelope,
    GenerationModel,
    ScientificReference,
    ScientificRelationFrame,
    SemanticFrame,
    SemanticParameterBinding,
)
from cfdpaper.topic_generation.opportunities import ResearchOpportunity

PROMPT_CONTRACT_VERSION = "topic-refinement-prompt-v1"
REFINEMENT_POLICY_VERSION = "semantic-refinement-policy-v2"
WRITABLE_FIELDS = ("title", "research_question", "rationale", "differentiation")
MIN_DIFFERENTIATION_MARGIN_GAIN = 0.15

HIGH_RISK_PHRASES_V2 = {
    "causal": (
        "cause",
        "causes",
        "caused",
        "causing",
        "drive",
        "drives",
        "drove",
        "driven",
        "driving",
        "lead to",
        "leads to",
        "led to",
        "leading to",
        "result in",
        "results in",
        "resulted in",
        "resulting in",
        "due to",
        "because of",
        "mechanism responsible for",
    ),
    "superiority": (
        "first",
        "novel",
        "novelty",
        "unprecedented",
        "better",
        "best",
        "superior",
        "improve",
        "improves",
        "improved",
        "improvement",
        "outperform",
        "outperforms",
        "outperformed",
        "outperforming",
        "optimal",
        "optimum",
    ),
    "continuous-region": (
        "optimal point",
        "optimum point",
        "optimal region",
        "optimum region",
        "continuous design space",
        "continuous operating region",
        "stable operating window",
        "safe operating window",
        "stability boundary",
    ),
    "validation": (
        "experimentally validated",
        "validated against experiment",
        "verified against experiment",
        "independently validated",
    ),
    "engineering-boundary": (
        "verified operating limit",
        "engineering boundary",
        "operating boundary",
        "validated operating window",
        "design limit",
        "safe operating limit",
    ),
}


class RefinementRejected(ValueError):
    """A deterministic reason for rejecting the entire provider batch."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class TopicSemanticFrame(GenerationModel):
    topic_id: str = Field(min_length=1)
    frame: SemanticFrame


class ProviderRefinement(GenerationModel):
    topic_id: str = Field(min_length=1)
    semantic_frame: SemanticFrame
    title: str = Field(min_length=1)
    research_question: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    differentiation: str = Field(min_length=1)

    @field_validator(*WRITABLE_FIELDS, mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("provider wording must be text")
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("provider wording must not be blank")
        return normalized


class ProviderRefinementEnvelope(GenerationModel):
    schema_version: Literal[1] = 1
    refinements: tuple[ProviderRefinement, ...]


class AcceptedRefinement(GenerationModel):
    topic_id: str = Field(min_length=1)
    semantic_frame: SemanticFrame
    title: str = Field(min_length=1)
    research_question: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    differentiation: str = Field(min_length=1)


class RefinementResult(GenerationModel):
    mode: Literal["provider-refined", "offline-fallback"]
    candidate_input: GeneratedCandidateEnvelope
    accepted_refinements: tuple[AcceptedRefinement, ...]
    accepted_refinement_hash: str = Field(pattern=SHA256_PATTERN)
    rejection_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_alignment(self) -> RefinementResult:
        candidates = self.candidate_input.candidates
        if tuple(item.topic_id for item in candidates) != tuple(
            item.topic_id for item in self.accepted_refinements
        ):
            raise ValueError("accepted refinements must align with candidates")
        expected = canonical_sha256(
            tuple(sorted(self.accepted_refinements, key=lambda item: item.topic_id)),
            domain=b"cfdpaper-accepted-refinement-v1",
        )
        if self.accepted_refinement_hash != expected:
            raise ValueError("accepted refinement hash does not match sanitized envelope")
        if self.rejection_reasons != tuple(sorted(set(self.rejection_reasons))):
            raise ValueError("rejection reasons must be sorted and unique")
        return self


@dataclass(frozen=True)
class WordingFactCatalog:
    """Recognizable science roles, never an allowlist for ordinary prose."""

    aliases: dict[str, tuple[str, ...]]
    core_by_field: dict[str, frozenset[str]]
    relation_aliases: tuple[str, ...]
    inverse_relation_aliases: tuple[str, ...]
    required_scope_aliases: tuple[str, ...]
    relation: ScientificRelationFrame


@dataclass(frozen=True)
class RelationTextPolicy:
    """Finite high-risk relation checks; surrounding scientific prose stays open."""

    required_roles: tuple[str, ...]
    scope_aliases: tuple[str, ...]
    operators: tuple[str, ...]
    forbidden_operators: tuple[str, ...]
    allowed_layouts: tuple[tuple[str, ...], ...]
    inverse_layouts: tuple[tuple[str, ...], ...]


COMPARISON_PREFIXES_V1 = ("compared with", "relative to")
PARAMETER_ASCENDING_V1 = ("increases", "rises", "is increased")
PAIRWISE_SCOPE_V1 = ("pairwise", "matched pair", "two sampled cases")
SAMPLED_SERIES_SCOPE_V1 = ("sampled series", "sampled cases", "discrete cases")
SAMPLED_CASES_SCOPE_V1 = ("sampled cases", "paired observations")
VALIDATION_SET_SCOPE_V1 = ("validation set", "sensitivity set", "tested cases")

SIGNED_MATCHED_OPERATORS_V1 = {
    "increase": ("higher than", "greater than", "exceeds"),
    "decrease": ("lower than", "less than", "falls below"),
}
MATCHED_NEGATIONS_V1 = {
    "increase": ("not higher than", "no higher than", "not greater than", "does not exceed"),
    "decrease": ("not lower than", "no lower than", "not less than", "does not fall below"),
    "difference-only": (
        "no difference",
        "does not differ from",
        "identical response",
        "equivalent response",
    ),
}
ORDERED_OPERATORS_V1 = {
    "increase": ("increases with", "rises with", "grows with", "increases"),
    "decrease": ("decreases with", "falls with", "declines with", "decreases"),
    "non-monotonic": (
        "is non-monotonic with",
        "changes direction with",
        "has an interior peak with",
        "has an interior trough with",
    ),
    "plateau": ("plateaus with", "levels off with", "is approximately unchanged with"),
}
ORDERED_NEGATIONS_V1 = {
    "increase": ("does not increase with", "does not rise with", "does not grow with"),
    "decrease": ("does not decrease with", "does not fall with", "does not decline with"),
    "non-monotonic": (
        "is not non-monotonic with",
        "does not change direction with",
        "has no interior peak with",
        "has no interior trough with",
    ),
    "plateau": (
        "does not plateau with",
        "does not level off with",
        "is not approximately unchanged with",
    ),
}
ASSOCIATION_OPERATORS_V1 = {
    "positive": (
        "is positively associated with",
        "co-varies positively with",
        "increases together with",
    ),
    "negative": (
        "is negatively associated with",
        "co-varies negatively with",
        "varies inversely with",
    ),
    "unsigned": (
        "is associated with",
        "co-varies with",
        "co-vary with",
        "shows an association with",
    ),
}
ASSOCIATION_NEGATIONS_V1 = {
    "positive": (
        "is not positively associated with",
        "does not co-vary positively with",
        "no positive association with",
    ),
    "negative": (
        "is not negatively associated with",
        "does not co-vary negatively with",
        "no negative association with",
    ),
    "unsigned": ("is not associated with", "does not co-vary with", "no association with"),
}
DIFFERENCE_OPERATORS_V1 = ("differs from", "difference between", "contrast between")
ROBUSTNESS_OPERATORS_V1 = (
    "is robust across",
    "is consistent across",
    "is sensitive to",
    "is assessed against",
)
ROBUSTNESS_NEGATIONS_V1 = (
    "is not robust across",
    "is not consistent across",
    "is not sensitive to",
    "is not assessed against",
)
CAUSAL_OR_CONTINUOUS_ESCALATIONS_V1 = ("causes", "drives", "optimal", "operating window")


def matched_policy(polarity: str) -> RelationTextPolicy:
    if polarity == "difference-only":
        return RelationTextPolicy(
            required_roles=("subject-case", "primary-qoi", "contrast-case"),
            scope_aliases=PAIRWISE_SCOPE_V1,
            operators=DIFFERENCE_OPERATORS_V1,
            forbidden_operators=MATCHED_NEGATIONS_V1["difference-only"]
            + tuple(phrase for group in SIGNED_MATCHED_OPERATORS_V1.values() for phrase in group),
            allowed_layouts=(
                ("subject-case", "operator", "contrast-case"),
                ("contrast-case", "operator", "subject-case"),
                ("operator", "subject-case", "contrast-case"),
                ("operator", "contrast-case", "subject-case"),
            ),
            inverse_layouts=(),
        )
    operators = SIGNED_MATCHED_OPERATORS_V1[polarity]
    inverse = SIGNED_MATCHED_OPERATORS_V1["decrease" if polarity == "increase" else "increase"]
    return RelationTextPolicy(
        required_roles=("subject-case", "primary-qoi", "contrast-case"),
        scope_aliases=PAIRWISE_SCOPE_V1,
        operators=operators,
        forbidden_operators=inverse + MATCHED_NEGATIONS_V1[polarity],
        allowed_layouts=(
            ("subject-case", "primary-qoi", "operator", "contrast-case"),
            ("comparison-prefix", "contrast-case", "subject-case", "primary-qoi", "operator"),
        ),
        inverse_layouts=(
            ("contrast-case", "primary-qoi", "operator", "subject-case"),
            ("comparison-prefix", "subject-case", "contrast-case", "primary-qoi", "operator"),
        ),
    )


def ordered_policy(polarity: str) -> RelationTextPolicy:
    inverse_polarities = {
        "increase": ("decrease",),
        "decrease": ("increase",),
        "non-monotonic": ("increase", "decrease", "plateau"),
        "plateau": ("increase", "decrease", "non-monotonic"),
    }[polarity]
    return RelationTextPolicy(
        required_roles=("primary-qoi", "varied-parameter"),
        scope_aliases=SAMPLED_SERIES_SCOPE_V1,
        operators=ORDERED_OPERATORS_V1[polarity],
        forbidden_operators=ORDERED_NEGATIONS_V1[polarity]
        + tuple(phrase for name in inverse_polarities for phrase in ORDERED_OPERATORS_V1[name]),
        allowed_layouts=(
            ("primary-qoi", "operator", "varied-parameter"),
            ("varied-parameter", "parameter-ascending", "primary-qoi", "operator"),
        ),
        inverse_layouts=(
            ("varied-parameter", "operator", "primary-qoi"),
            ("primary-qoi", "parameter-ascending", "varied-parameter", "operator"),
        ),
    )


def association_policy(polarity: str) -> RelationTextPolicy:
    inverse_names = {
        "positive": ("negative",),
        "negative": ("positive",),
        "unsigned": ("positive", "negative"),
    }[polarity]
    return RelationTextPolicy(
        required_roles=("primary-qoi", "secondary-qoi"),
        scope_aliases=SAMPLED_CASES_SCOPE_V1,
        operators=ASSOCIATION_OPERATORS_V1[polarity],
        forbidden_operators=ASSOCIATION_NEGATIONS_V1[polarity]
        + tuple(phrase for name in inverse_names for phrase in ASSOCIATION_OPERATORS_V1[name])
        + ROBUSTNESS_OPERATORS_V1
        + CAUSAL_OR_CONTINUOUS_ESCALATIONS_V1,
        allowed_layouts=(
            ("primary-qoi", "operator", "secondary-qoi"),
            ("secondary-qoi", "operator", "primary-qoi"),
        ),
        inverse_layouts=(),
    )


def robustness_policy() -> RelationTextPolicy:
    return RelationTextPolicy(
        required_roles=("primary-qoi", "validation-contrast"),
        scope_aliases=VALIDATION_SET_SCOPE_V1,
        operators=ROBUSTNESS_OPERATORS_V1,
        forbidden_operators=ROBUSTNESS_NEGATIONS_V1
        + tuple(phrase for group in ASSOCIATION_OPERATORS_V1.values() for phrase in group)
        + CAUSAL_OR_CONTINUOUS_ESCALATIONS_V1,
        allowed_layouts=(
            ("primary-qoi", "operator", "validation-contrast"),
            ("validation-contrast", "operator", "primary-qoi"),
        ),
        inverse_layouts=(),
    )


RELATION_TEXT_POLICIES_V1: dict[tuple[str, str, str, str], RelationTextPolicy] = {
    ("difference", "increase", "variant-vs-reference", "pairwise"): matched_policy("increase"),
    ("difference", "decrease", "variant-vs-reference", "pairwise"): matched_policy("decrease"),
    ("difference", "difference-only", "variant-vs-reference", "pairwise"): matched_policy(
        "difference-only"
    ),
    ("ordered-response", "increase", "parameter-ascending", "sampled-series-only"): ordered_policy(
        "increase"
    ),
    ("ordered-response", "decrease", "parameter-ascending", "sampled-series-only"): ordered_policy(
        "decrease"
    ),
    (
        "ordered-response",
        "non-monotonic",
        "parameter-ascending",
        "sampled-series-only",
    ): ordered_policy("non-monotonic"),
    ("ordered-response", "plateau", "parameter-ascending", "sampled-series-only"): ordered_policy(
        "plateau"
    ),
    ("coupled-association", "positive", "symmetric", "sampled-cases-only"): association_policy(
        "positive"
    ),
    ("coupled-association", "negative", "symmetric", "sampled-cases-only"): association_policy(
        "negative"
    ),
    (
        "coupled-association",
        "not-applicable",
        "symmetric",
        "sampled-cases-only",
    ): association_policy("unsigned"),
    ("robustness", "not-applicable", "not-applicable", "validation-set-only"): robustness_policy(),
}


def _humanize(identifier: str) -> str:
    return " ".join(identifier.replace("_", " ").replace("-", " ").split())


def _predicate(opportunity: ResearchOpportunity) -> str:
    if opportunity.pattern == "coupled-association":
        return "coupled-association"
    if opportunity.claim_ceiling.value == "engineering":
        return "engineering-boundary"
    if opportunity.claim_ceiling.value == "validation":
        return "validation"
    if opportunity.claim_ceiling.value == "mechanism":
        return "mechanism"
    if opportunity.pattern == "matched-comparison":
        return "matched-comparison"
    if opportunity.pattern == "ordered-parameter-response":
        return "ordered-response"
    return "observation"


def _parameter_bindings(opportunity: ResearchOpportunity) -> tuple[SemanticParameterBinding, ...]:
    expected_ids = tuple(sorted(opportunity.parameter_ids))
    bindings = tuple(
        SemanticParameterBinding(
            id=item.parameter_id,
            role=item.role,
            case_ids=item.case_ids,
            boundary_evidence_ids=item.boundary_evidence_ids,
        )
        for item in opportunity.parameter_bindings
    )
    if tuple(item.id for item in bindings) != expected_ids:
        raise ValueError("complete parameter binding is required")
    if {item.id for item in bindings if item.role == "varied"} != set(
        opportunity.varied_parameter_ids
    ):
        raise ValueError("varied parameter binding does not match opportunity")
    if {item.id for item in bindings if item.role == "controlled"} != set(
        opportunity.controlled_parameter_ids
    ):
        raise ValueError("controlled parameter binding does not match opportunity")
    return bindings


def build_semantic_frame(
    opportunity: ResearchOpportunity, candidate: TopicCandidate
) -> SemanticFrame:
    """Copy the complete Task 5/6 scientific envelope without inference."""

    if candidate.topic_id.strip() == "":
        raise ValueError("candidate topic ID must not be blank")
    expected_topic_id = (
        "auto-"
        + canonical_sha256(
            opportunity.semantic_signature,
            domain=b"cfdpaper-generated-topic-v1",
        )[:16]
    )
    if candidate.topic_id != expected_topic_id:
        raise ValueError("candidate topic ID does not match opportunity")
    return SemanticFrame(
        claim_class=opportunity.claim_ceiling.value,
        predicate_class=_predicate(opportunity),
        relation=opportunity.relation,
        subject_references=tuple(
            ScientificReference(kind="parameter", id=item)
            for item in opportunity.varied_parameter_ids
        )
        + tuple(ScientificReference(kind="qoi", id=item) for item in opportunity.primary_qoi_ids),
        contrast_references=tuple(
            ScientificReference(kind="case", id=item) for item in opportunity.current_case_ids
        ),
        parameter_bindings=_parameter_bindings(opportunity),
        evidence_references=tuple(
            ScientificReference(kind="evidence", id=item)
            for item in opportunity.supporting_evidence_ids
        ),
    )


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE).split())


def _has_phrase(text: str, phrase: str) -> bool:
    normalized_text = _normalize_text(text)
    normalized_phrase = _normalize_text(phrase)
    if not normalized_phrase:
        return False
    return (
        re.search(
            rf"(?<!\w){re.escape(normalized_phrase)}(?!\w)", normalized_text, flags=re.UNICODE
        )
        is not None
    )


def _relation_aliases(
    frame: SemanticFrame,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    key = _relation_key(frame.relation)
    try:
        policy = RELATION_TEXT_POLICIES_V1[key]
    except KeyError as error:
        raise RefinementRejected("semantic-frame-mismatch") from error
    return policy.operators, policy.forbidden_operators, policy.scope_aliases


def _relation_key(relation: ScientificRelationFrame) -> tuple[str, str, str, str]:
    return (
        relation.relation_class,
        relation.polarity,
        relation.comparison_direction,
        relation.quantifier,
    )


def wording_fact_catalog_for(topic_id: str, frame: SemanticFrame) -> WordingFactCatalog:
    """Build checkable topic-local facts without restricting surrounding prose."""

    allowed, inverse, scopes = _relation_aliases(frame)
    qois = tuple(item.id for item in frame.subject_references if item.kind == "qoi")
    varied = tuple(item.id for item in frame.parameter_bindings if item.role == "varied")
    controlled = tuple(item.id for item in frame.parameter_bindings if item.role == "controlled")
    primary_qoi = qois[:1]
    secondary_qoi = qois[1:]
    validation_contrast = (
        ("validation contrast", "sensitivity contrast", "validation or sensitivity contrast")
        if frame.relation.relation_class == "robustness"
        else ()
    )
    aliases: dict[str, tuple[str, ...]] = {
        **{f"qoi:{item}": (_humanize(item),) for item in qois},
        **{f"varied:{item}": (_humanize(item),) for item in varied},
        **{f"controlled:{item}": (_humanize(item),) for item in controlled},
        # ScientificRecordSnapshot does not expose case-ID roles.  Keep the direction locked by
        # the relation's variant-vs-reference semantic labels, never by case-ID sort order.
        "subject-case": ("variant", "variant case"),
        "contrast-case": ("reference", "reference case"),
        "primary-qoi": tuple(_humanize(item) for item in primary_qoi),
        "secondary-qoi": tuple(_humanize(item) for item in secondary_qoi),
        "varied-parameter": tuple(_humanize(item) for item in varied),
        "validation-contrast": validation_contrast,
        "relation": allowed,
        "scope": scopes,
        "evidence": ("current structured evidence", "structured evidence"),
        "boundary-evidence": ("boundary evidence",),
        "signature": ("scientific question", "candidate distinguishes"),
    }
    policy = RELATION_TEXT_POLICIES_V1[_relation_key(frame.relation)]
    title_core = frozenset(policy.required_roles)
    return WordingFactCatalog(
        aliases=aliases,
        core_by_field={"title": title_core, "research_question": title_core},
        relation_aliases=allowed,
        inverse_relation_aliases=inverse,
        required_scope_aliases=scopes,
        relation=frame.relation,
    )


def _fact_ids(text: str, catalog: WordingFactCatalog) -> frozenset[str]:
    return frozenset(
        fact_id
        for fact_id, aliases in catalog.aliases.items()
        if any(_has_phrase(text, alias) for alias in aliases)
    )


def _risk_clause_has_bound_topic_roles(clause: str, catalog: WordingFactCatalog) -> bool:
    required = {
        "primary-qoi",
        "varied-parameter",
        "evidence",
    }
    if catalog.aliases["subject-case"]:
        required.add("subject-case")
    if catalog.aliases["contrast-case"]:
        required.add("contrast-case")
    return required <= _fact_ids(clause, catalog)


def _risk_code(text: str, frame: SemanticFrame, catalog: WordingFactCatalog) -> str | None:
    risk_text = text
    for fact_id, aliases in catalog.aliases.items():
        if fact_id.startswith(("qoi:", "varied:", "controlled:")) or fact_id == "contrast":
            for alias in aliases:
                risk_text = re.sub(
                    rf"(?<!\w){re.escape(alias)}(?!\w)",
                    " structured-role ",
                    risk_text,
                    flags=re.IGNORECASE | re.UNICODE,
                )
    for group in ("superiority", "continuous-region"):
        if any(_has_phrase(risk_text, phrase) for phrase in HIGH_RISK_PHRASES_V2[group]):
            return "prohibited-phrase"
    clauses = tuple(clause for clause in re.split(r"[.!?;\n]+", text) if clause.strip())
    if any(_has_phrase(text, phrase) for phrase in HIGH_RISK_PHRASES_V2["causal"]):
        if not (frame.claim_class == "mechanism" and frame.predicate_class == "mechanism"):
            return "claim-escalation"
        if not any(
            any(_has_phrase(clause, phrase) for phrase in HIGH_RISK_PHRASES_V2["causal"])
            and _risk_clause_has_bound_topic_roles(clause, catalog)
            for clause in clauses
        ):
            return "claim-escalation"
    if any(_has_phrase(text, phrase) for phrase in HIGH_RISK_PHRASES_V2["validation"]):
        if not (frame.claim_class == "validation" and frame.predicate_class == "validation"):
            return "claim-escalation"
        if not any(
            any(_has_phrase(clause, phrase) for phrase in HIGH_RISK_PHRASES_V2["validation"])
            and _risk_clause_has_bound_topic_roles(clause, catalog)
            for clause in clauses
        ):
            return "claim-escalation"
    if any(_has_phrase(text, phrase) for phrase in HIGH_RISK_PHRASES_V2["engineering-boundary"]):
        if not (
            frame.claim_class == "engineering" and frame.predicate_class == "engineering-boundary"
        ):
            return "claim-escalation"
        if not any(
            any(
                _has_phrase(clause, phrase)
                for phrase in HIGH_RISK_PHRASES_V2["engineering-boundary"]
            )
            and _risk_clause_has_bound_topic_roles(clause, catalog)
            for clause in clauses
        ):
            return "claim-escalation"
    return None


_NUMBER_RE = re.compile(
    r"(?<![\w.])[-+]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:e[-+]?\d+)?(?![\w.])",
    re.IGNORECASE | re.UNICODE,
)
_ID_RE = re.compile(
    r"\b(?:case|qoi|evidence|parameter|auto|opp|ev)-[A-Za-z0-9][A-Za-z0-9_-]*\b",
    re.IGNORECASE | re.UNICODE,
)
_UNIT_RE = re.compile(
    r"(?:(?<![\w/])(?:w/m\^?(?:2|3)|kg/m\^?3|kg/s|m/s|degc|°c|kpa|mpa|bar|ppm|mm|cm|kw|mw|kj|pa|w|j|k|s)(?!\w)|(?<=\d)%)",
    re.IGNORECASE | re.UNICODE,
)


def _source_text(value: str) -> str:
    """Preserve decimal, exponent, slash, and unit syntax for bounded extraction."""

    return unicodedata.normalize("NFKC", value)


def _canonical_unit(value: str) -> str:
    return registered_canonical_unit(_source_text(value))


def _validate_no_invention(
    text: str,
    frame: SemanticFrame,
    offline: AcceptedRefinement,
    *,
    topic_id: str,
    opportunity_id: str,
) -> None:
    offline_text = " ".join(getattr(offline, field) for field in WRITABLE_FIELDS)
    known_numbers = {item.casefold() for item in _NUMBER_RE.findall(_source_text(offline_text))}
    known_units = {_canonical_unit(item) for item in _UNIT_RE.findall(_source_text(offline_text))}
    known_ids = {
        item.id.casefold()
        for item in (
            *frame.subject_references,
            *frame.contrast_references,
            *frame.evidence_references,
        )
    } | {item.id.casefold() for item in frame.parameter_bindings}
    known_ids |= {topic_id.casefold(), opportunity_id.casefold()}
    known_ids |= {
        identifier.casefold()
        for binding in frame.parameter_bindings
        for identifier in (*binding.case_ids, *binding.boundary_evidence_ids)
    }
    known_ids |= {item.casefold() for item in _ID_RE.findall(_source_text(offline_text))}
    source_text = _source_text(text)
    if any(_canonical_unit(item) not in known_units for item in _UNIT_RE.findall(source_text)):
        raise RefinementRejected("unit-invention")
    if any(item.casefold() not in known_numbers for item in _NUMBER_RE.findall(source_text)):
        raise RefinementRejected("numeric-invention")
    if any(item.casefold() not in known_ids for item in _ID_RE.findall(source_text)):
        raise RefinementRejected("reference-out-of-bounds")


def _role_aliases(
    catalog: WordingFactCatalog, role: str, policy: RelationTextPolicy
) -> tuple[str, ...]:
    if role in {
        "subject-case",
        "contrast-case",
        "primary-qoi",
        "secondary-qoi",
        "varied-parameter",
        "validation-contrast",
    }:
        return catalog.aliases[role]
    if role == "operator":
        return policy.operators
    if role == "comparison-prefix":
        return COMPARISON_PREFIXES_V1
    if role == "parameter-ascending":
        return PARAMETER_ASCENDING_V1
    raise ValueError(f"unknown relation role: {role}")


def _spans_for_aliases(clause: str, aliases: Sequence[str]) -> tuple[tuple[int, int], ...]:
    normalized = _normalize_text(clause)
    spans = {
        (match.start(), match.end())
        for alias in aliases
        if (normalized_alias := _normalize_text(alias))
        for match in re.finditer(
            rf"(?<!\w){re.escape(normalized_alias)}(?!\w)", normalized, flags=re.UNICODE
        )
    }
    return tuple(sorted(spans))


def matches_ordered_layout(
    clause: str,
    layout: tuple[str, ...],
    catalog: WordingFactCatalog,
    policy: RelationTextPolicy,
) -> bool:
    """Require non-overlapping scientific roles in the declared relation order."""

    role_spans = tuple(
        _spans_for_aliases(clause, _role_aliases(catalog, role, policy)) for role in layout
    )
    if any(not spans for spans in role_spans):
        return False

    def find(position: int, after: int) -> bool:
        if position == len(role_spans):
            return True
        return any(
            start >= after and find(position + 1, end) for start, end in role_spans[position]
        )

    return find(0, 0)


def _relation_preserved(proposed: AcceptedRefinement, catalog: WordingFactCatalog) -> bool:
    if proposed.semantic_frame.relation != catalog.relation:
        return False
    try:
        policy = RELATION_TEXT_POLICIES_V1[_relation_key(catalog.relation)]
    except KeyError:
        return False
    required = frozenset({"relation", "scope", *policy.required_roles})
    clauses = tuple(
        clause
        for clause in re.split(r"[.!?;\n]+", proposed.research_question + ";" + proposed.rationale)
        if clause.strip()
    )
    for clause in clauses:
        if any(_has_phrase(clause, phrase) for phrase in policy.forbidden_operators):
            return False
        if any(
            matches_ordered_layout(clause, layout, catalog, policy)
            for layout in policy.inverse_layouts
        ):
            return False
        facts = _fact_ids(clause, catalog)
        if required <= facts and any(
            matches_ordered_layout(clause, layout, catalog, policy)
            for layout in policy.allowed_layouts
        ):
            return True
    return False


def _has_relation_contradiction(proposed: AcceptedRefinement, catalog: WordingFactCatalog) -> bool:
    policy = RELATION_TEXT_POLICIES_V1.get(_relation_key(catalog.relation))
    if policy is None:
        return True
    for clause in re.split(r"[.!?;\n]+", proposed.research_question + ";" + proposed.rationale):
        if any(_has_phrase(clause, phrase) for phrase in policy.forbidden_operators):
            return True
        if any(
            matches_ordered_layout(clause, layout, catalog, policy)
            for layout in policy.inverse_layouts
        ):
            return True
    return False


def _uses_trusted_offline_relation_text(
    proposed: AcceptedRefinement, offline: AcceptedRefinement
) -> bool:
    """Keep an echoed Task 6 relation baseline available for no-gain detection."""

    return all(
        _normalize_text(getattr(offline, field)) in _normalize_text(getattr(proposed, field))
        for field in ("research_question", "rationale")
    )


def _differentiation_preserved(proposed: AcceptedRefinement, catalog: WordingFactCatalog) -> bool:
    facts = _fact_ids(proposed.differentiation, catalog)
    required = {"signature", "relation", "primary-qoi"}
    if catalog.aliases["secondary-qoi"]:
        required.add("secondary-qoi")
    return required <= facts


def bounded_scientific_relation_preserved(
    *,
    proposed: AcceptedRefinement,
    relation: ScientificRelationFrame,
    catalog: WordingFactCatalog,
) -> bool:
    """Public test hook for bounded relation preservation, not publication judgement."""

    return relation == catalog.relation and _relation_preserved(proposed, catalog)


def _duplicate_text(first: AcceptedRefinement, second: AcceptedRefinement) -> bool:
    first_tokens = set(_normalize_text(first.title + " " + first.research_question).split())
    second_tokens = set(_normalize_text(second.title + " " + second.research_question).split())
    union = first_tokens | second_tokens
    return bool(union) and len(first_tokens & second_tokens) / len(union) >= 0.85


def _differentiation_margin(
    item: AcceptedRefinement, batch: Sequence[AcceptedRefinement], catalog: WordingFactCatalog
) -> float:
    own = {
        (field, fact)
        for field in ("title", "research_question")
        for fact in _fact_ids(getattr(item, field), catalog)
    }
    similarities: list[float] = []
    for other in batch:
        if other.topic_id == item.topic_id:
            continue
        other_catalog = (
            catalog
            if other.semantic_frame == item.semantic_frame
            else wording_fact_catalog_for(other.topic_id, other.semantic_frame)
        )
        theirs = {
            (field, fact)
            for field in ("title", "research_question")
            for fact in _fact_ids(getattr(other, field), other_catalog)
        }
        union = own | theirs
        similarities.append(len(own & theirs) / len(union) if union else 1.0)
    return 1.0 - max(similarities, default=0.0)


def _has_material_gain(
    offline: AcceptedRefinement,
    proposed: AcceptedRefinement,
    catalog: WordingFactCatalog,
    offline_batch: Sequence[AcceptedRefinement],
    proposed_batch: Sequence[AcceptedRefinement],
) -> bool:
    if proposed.semantic_frame != offline.semantic_frame or not (
        _relation_preserved(proposed, catalog)
        or _uses_trusted_offline_relation_text(proposed, offline)
    ):
        return False
    before = {field: _fact_ids(getattr(offline, field), catalog) for field in WRITABLE_FIELDS}
    after = {field: _fact_ids(getattr(proposed, field), catalog) for field in WRITABLE_FIELDS}
    if not frozenset().union(*before.values()) <= frozenset().union(*after.values()):
        return False
    if any(not required <= after[field] for field, required in catalog.core_by_field.items()):
        return False
    changed = tuple(
        field
        for field in WRITABLE_FIELDS
        if _normalize_text(getattr(offline, field)) != _normalize_text(getattr(proposed, field))
    )
    gains = {field: after[field] - before[field] for field in changed}
    gained_ids = frozenset().union(*gains.values()) if gains else frozenset()
    margin = _differentiation_margin(proposed, proposed_batch, catalog) - _differentiation_margin(
        offline, offline_batch, catalog
    )
    return len(changed) >= 2 and (
        (sum(bool(value) for value in gains.values()) >= 2 and len(gained_ids) >= 2)
        or (len(gained_ids) >= 1 and margin >= MIN_DIFFERENTIATION_MARGIN_GAIN)
    )


def _offline_refinement(
    skeletons: Sequence[CandidateSkeleton],
    frames: Sequence[TopicSemanticFrame],
    reason: str | None = None,
) -> RefinementResult:
    frame_by_topic = {item.topic_id: item.frame for item in frames}
    accepted = tuple(
        AcceptedRefinement(
            topic_id=item.candidate.topic_id,
            semantic_frame=frame_by_topic[item.candidate.topic_id],
            title=item.candidate.title,
            research_question=item.candidate.research_question,
            rationale=item.rationale,
            differentiation=item.differentiation,
        )
        for item in skeletons
    )
    return _result(
        "offline-fallback",
        tuple(item.candidate for item in skeletons),
        accepted,
        (() if reason is None else (reason,)),
    )


def offline_refinement_result(
    skeletons: Sequence[CandidateSkeleton], frames: Sequence[TopicSemanticFrame]
) -> RefinementResult:
    return _offline_refinement(skeletons, frames)


def _result(
    mode: Literal["provider-refined", "offline-fallback"],
    candidates: tuple[TopicCandidate, ...],
    accepted: tuple[AcceptedRefinement, ...],
    reasons: tuple[str, ...] = (),
) -> RefinementResult:
    return RefinementResult(
        mode=mode,
        candidate_input=GeneratedCandidateEnvelope(candidates=candidates),
        accepted_refinements=accepted,
        accepted_refinement_hash=canonical_sha256(
            tuple(sorted(accepted, key=lambda item: item.topic_id)),
            domain=b"cfdpaper-accepted-refinement-v1",
        ),
        rejection_reasons=tuple(sorted(set(reasons))),
    )


def _validate_inputs(
    skeletons: Sequence[CandidateSkeleton], frames: Sequence[TopicSemanticFrame]
) -> None:
    ids = tuple(item.candidate.topic_id for item in skeletons)
    frame_ids = tuple(item.topic_id for item in frames)
    if (
        len(set(ids)) != len(ids)
        or len(set(frame_ids)) != len(frame_ids)
        or set(ids) != set(frame_ids)
    ):
        raise RefinementRejected("topic-id-mismatch")


def _canonical_inputs(
    skeletons: Sequence[CandidateSkeleton], frames: Sequence[TopicSemanticFrame]
) -> tuple[tuple[CandidateSkeleton, ...], tuple[TopicSemanticFrame, ...]]:
    _validate_inputs(skeletons, frames)
    return (
        tuple(sorted(skeletons, key=lambda item: item.candidate.topic_id)),
        tuple(sorted(frames, key=lambda item: item.topic_id)),
    )


def _build_prompt(
    skeletons: Sequence[CandidateSkeleton],
    frames: Sequence[TopicSemanticFrame],
    semantic_reuse_key: str,
    context_packet: TaskContextPacket,
) -> str:
    payload = {
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
        "refinement_policy_version": REFINEMENT_POLICY_VERSION,
        "semantic_reuse_key": semantic_reuse_key,
        "context_packet": context_packet.model_dump(mode="json"),
        "topics": [
            {"topic_id": item.topic_id, "semantic_frame": item.frame.model_dump(mode="json")}
            for item in frames
        ],
        "offline": [
            {
                "topic_id": item.candidate.topic_id,
                "title": item.candidate.title,
                "research_question": item.candidate.research_question,
                "rationale": item.rationale,
                "differentiation": item.differentiation,
            }
            for item in skeletons
        ],
    }
    return canonical_json_bytes(payload).decode("utf-8")


def _parse_batch(
    raw: str, skeletons: Sequence[CandidateSkeleton], frames: Sequence[TopicSemanticFrame]
) -> tuple[AcceptedRefinement, ...]:
    try:
        raw_envelope = json.loads(raw)
        envelope = ProviderRefinementEnvelope.model_validate_json(raw)
        raw_refinements = raw_envelope["refinements"]
        if not isinstance(raw_refinements, list):
            raise ValueError("refinements must be a list")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RefinementRejected("malformed-json") from error
    expected_ids = tuple(item.candidate.topic_id for item in skeletons)
    proposed_ids = tuple(item.topic_id for item in envelope.refinements)
    if proposed_ids != expected_ids or len(set(proposed_ids)) != len(proposed_ids):
        raise RefinementRejected("topic-id-mismatch")
    frame_by_topic = {item.topic_id: item.frame for item in frames}
    raw_candidates = tuple(
        AcceptedRefinement.model_validate(item.model_dump()) for item in envelope.refinements
    )
    if any(
        _duplicate_text(first, second)
        for index, first in enumerate(raw_candidates)
        for second in raw_candidates[index + 1 :]
    ):
        raise RefinementRejected("duplicate-refinement")
    accepted: list[AcceptedRefinement] = []
    offline = _offline_refinement(skeletons, frames)
    offline_by_topic = {item.topic_id: item for item in offline.accepted_refinements}
    skeleton_by_topic = {item.candidate.topic_id: item for item in skeletons}
    for item, raw_item in zip(envelope.refinements, raw_refinements, strict=True):
        expected_frame = frame_by_topic[item.topic_id]
        if not isinstance(raw_item, dict) or canonical_json_bytes(
            raw_item.get("semantic_frame")
        ) != canonical_json_bytes(expected_frame):
            raise RefinementRejected("semantic-frame-mismatch")
        proposed = AcceptedRefinement.model_validate(item.model_dump())
        catalog = wording_fact_catalog_for(item.topic_id, expected_frame)
        for field in WRITABLE_FIELDS:
            text = getattr(proposed, field)
            risk = _risk_code(text, expected_frame, catalog)
            if risk is not None:
                raise RefinementRejected(risk)
            _validate_no_invention(
                text,
                expected_frame,
                offline_by_topic[item.topic_id],
                topic_id=item.topic_id,
                opportunity_id=skeleton_by_topic[item.topic_id].opportunity_id,
            )
        if not _relation_preserved(proposed, catalog) and (
            _has_relation_contradiction(proposed, catalog)
            or not _uses_trusted_offline_relation_text(proposed, offline_by_topic[item.topic_id])
        ):
            raise RefinementRejected("semantic-frame-mismatch")
        if not _differentiation_preserved(proposed, catalog) and _normalize_text(
            proposed.differentiation
        ) != _normalize_text(offline_by_topic[item.topic_id].differentiation):
            raise RefinementRejected("semantic-frame-mismatch")
        accepted.append(proposed)
    return tuple(accepted)


def refine_candidate_wording(
    *,
    skeletons: Sequence[CandidateSkeleton],
    frames: Sequence[TopicSemanticFrame],
    semantic_reuse_key: str,
    context_packet: TaskContextPacket,
    provider: AIProvider,
) -> RefinementResult:
    """Accept one complete bounded batch, otherwise preserve Task 6 offline wording."""

    try:
        skeletons, frames = _canonical_inputs(skeletons, frames)
        if not re.fullmatch(SHA256_PATTERN, semantic_reuse_key):
            raise RefinementRejected("semantic-reuse-key-invalid")
        raw = provider.generate(
            _build_prompt(skeletons, frames, semantic_reuse_key, context_packet)
        )
        accepted = _parse_batch(raw, skeletons, frames)
        offline = _offline_refinement(skeletons, frames)
        offline_by_topic = {item.topic_id: item for item in offline.accepted_refinements}
        catalogs = {
            item.topic_id: wording_fact_catalog_for(item.topic_id, item.frame) for item in frames
        }
        if not all(
            _has_material_gain(
                offline_by_topic[item.topic_id],
                item,
                catalogs[item.topic_id],
                offline.accepted_refinements,
                accepted,
            )
            for item in accepted
        ):
            raise RefinementRejected("no-material-gain")
    except RefinementRejected as error:
        return _offline_refinement(skeletons, frames, error.code)
    candidate_by_topic = {item.candidate.topic_id: item.candidate for item in skeletons}
    candidates = tuple(
        candidate_by_topic[item.topic_id].model_copy(
            update={
                "title": item.title,
                "research_question": item.research_question,
            }
        )
        for item in accepted
    )
    return _result("provider-refined", candidates, accepted)
