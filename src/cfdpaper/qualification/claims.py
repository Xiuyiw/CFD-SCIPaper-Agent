"""Bound V0.3 claims and propose one discrete evidence-linked figure."""

from __future__ import annotations

import math
import re

from cfdpaper.contracts import FigureContract
from cfdpaper.topic_generation.canonical import canonical_sha256

from .models import (
    AuthorApproval,
    BoundedClaim,
    CandidateFigureContract,
    CandidateFigurePanel,
    ClaimCeilingDecision,
    ParagraphDuty,
    QoIAnalysis,
    QualificationReport,
    V03ClaimCeiling,
)

_PROHIBITED_INFERENCES = (
    "interpolation",
    "continuous optimum",
    "stability boundary",
    "unsampled prediction",
)


def _complete_quantitative_bindings(analysis: QoIAnalysis) -> bool:
    if len(analysis.values) < 2:
        return False
    case_ids = tuple(item.case_id.strip() for item in analysis.values)
    evidence_ids = tuple(item.evidence_id.strip() for item in analysis.values)
    result_ids = tuple(item.result_id.strip() for item in analysis.values)
    return (
        all(case_ids)
        and len(set(case_ids)) == len(case_ids)
        and all(evidence_ids)
        and len(set(evidence_ids)) == len(evidence_ids)
        and all(result_ids)
        and len(set(result_ids)) == len(result_ids)
        and all(item.unit.strip() for item in analysis.values)
        and all(item.coordinate_unit.strip() for item in analysis.values)
        and all(item.source_locator.strip() for item in analysis.values)
        and all(math.isfinite(item.value) for item in analysis.values)
        and all(math.isfinite(item.coordinate_value) for item in analysis.values)
    )


def _intended_use_is_supported(qualification: QualificationReport) -> bool:
    return all(
        status.state == "demonstrated"
        and status.intended_use_supported
        and bool(status.evidence_ids)
        and bool(status.basis)
        and bool(status.source_locator)
        for status in (qualification.verification, qualification.validation)
    )


def _qualification_fingerprint(qualification: QualificationReport) -> str:
    return canonical_sha256(qualification, domain=b"cfdpaper-v03-qualification-report")


def _analysis_fingerprint(analysis: QoIAnalysis) -> str:
    return canonical_sha256(analysis, domain=b"cfdpaper-v03-qoi-analysis")


def assess_v03_claim_ceiling(
    qualification: QualificationReport,
    analysis: QoIAnalysis,
) -> ClaimCeilingDecision:
    """Compute the closed ceiling only from located scientific inputs."""

    if qualification.input_fingerprint != analysis.qualification_input_fingerprint:
        raise ValueError("qualification input fingerprint does not match the QoI analysis")
    qualification_fingerprint = _qualification_fingerprint(qualification)
    analysis_fingerprint = _analysis_fingerprint(analysis)
    complete = _complete_quantitative_bindings(analysis)
    quantitative = analysis.quantitative_reporting_allowed and complete
    nuisance = any(item.role == "unresolved-nuisance" for item in qualification.differences)
    blocking = bool(qualification.blockers) or any(
        item.role == "blocking" for item in qualification.differences
    )

    if qualification.status == "insufficient" or blocking or not analysis.values:
        ceiling = V03ClaimCeiling.NO_NUMERICAL_CLAIM
        reasons = ("comparison or executable QoI evidence is insufficient",)
        duties = ("state the evidence gap without reporting a numerical result",)
    elif len(analysis.values) < 3 or not quantitative:
        ceiling = V03ClaimCeiling.DIRECTIONAL_COMPARISON
        reasons = ("only a located directional comparison is supported",)
        duties = ("report direction across the observed discrete cases",)
    elif qualification.status == "restricted":
        ceiling = V03ClaimCeiling.QUALIFIED_NUMERICAL_OBSERVATION
        reasons = ("located numerical observations remain subject to stated restrictions",)
        duties = ("report located values together with the applicable restriction",)
    elif (
        qualification.status == "eligible"
        and not qualification.blockers
        and not qualification.restrictions
        and not qualification.minimum_corrections
        and not analysis.restrictions
        and analysis.trend is not None
        and analysis.overall_change is not None
        and _intended_use_is_supported(qualification)
        and not nuisance
    ):
        ceiling = V03ClaimCeiling.SUPPORTED_PHYSICAL_INTERPRETATION
        reasons = ("the eligible comparison has located intended-use verification and validation",)
        duties = (
            "report located values",
            "interpret the response only within the demonstrated intended use",
        )
    else:
        ceiling = V03ClaimCeiling.QUALIFIED_NUMERICAL_OBSERVATION
        reasons = ("located values are complete but physical interpretation lacks full support",)
        duties = ("report the located numerical observation without a physical causal claim",)

    decision_body = {
        "ceiling": ceiling,
        "reasons": reasons,
        "allowed_sentence_duties": duties,
        "quantitative_reporting_allowed": ceiling
        in {
            V03ClaimCeiling.QUALIFIED_NUMERICAL_OBSERVATION,
            V03ClaimCeiling.SUPPORTED_PHYSICAL_INTERPRETATION,
        },
        "qualification_fingerprint": qualification_fingerprint,
        "analysis_fingerprint": analysis_fingerprint,
        "scientific_input_fingerprint": analysis.scientific_input_fingerprint,
    }
    fingerprint = canonical_sha256(decision_body, domain=b"cfdpaper-v03-claim-ceiling-decision")
    return ClaimCeilingDecision(
        **decision_body,
        fingerprint=fingerprint,
    )


def _bounded_claim(analysis: QoIAnalysis, ceiling: ClaimCeilingDecision) -> BoundedClaim:
    first = analysis.values[0]
    last = analysis.values[-1]
    if ceiling.ceiling == V03ClaimCeiling.NO_NUMERICAL_CLAIM:
        text = "The available evidence does not support a numerical comparison."
    elif ceiling.ceiling == V03ClaimCeiling.DIRECTIONAL_COMPARISON:
        direction = "increased" if last.value > first.value else "decreased"
        if last.value == first.value:
            direction = "did not change"
        text = f"The locked QoI {direction} across the observed discrete cases."
    elif ceiling.ceiling == V03ClaimCeiling.QUALIFIED_NUMERICAL_OBSERVATION:
        text = (
            f"Across the observed discrete cases, the locked QoI changed from "
            f"{first.value:g} to {last.value:g} {first.unit}."
        )
    else:
        text = (
            f"Across the demonstrated intended-use comparison, the locked QoI changed from "
            f"{first.value:g} to {last.value:g} {first.unit}."
        )
    evidence_ids = tuple(dict.fromkeys(item.evidence_id for item in analysis.values))
    numeric_backlink_ids = tuple(item.result_id for item in analysis.values)
    identity = canonical_sha256(
        {
            "analysis": analysis,
            "ceiling": ceiling.ceiling,
            "text": text,
        },
        domain=b"cfdpaper-v03-bounded-claim",
    )
    return BoundedClaim(
        claim_id=f"claim-{identity[:16]}",
        text=text,
        ceiling=ceiling.ceiling,
        evidence_ids=evidence_ids,
        numeric_backlink_ids=numeric_backlink_ids,
    )


def _candidate_payload(candidate: CandidateFigureContract) -> dict[str, object]:
    return candidate.model_dump(mode="python", exclude={"fingerprint"})


def _candidate_fingerprint(candidate: CandidateFigureContract) -> str:
    return canonical_sha256(
        _candidate_payload(candidate), domain=b"cfdpaper-v03-candidate-figure-contract"
    )


def build_candidate_figure_contract(
    *,
    analysis: QoIAnalysis,
    qualification: QualificationReport,
    ceiling: ClaimCeilingDecision,
    figure_id: str,
    author: str,
) -> CandidateFigureContract:
    """Build one candidate panel from exact locked discrete members."""

    figure = figure_id.strip()
    normalized_author = author.strip()
    if not figure or not normalized_author:
        raise ValueError("figure_id and author must be nonblank")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", figure) is None:
        raise ValueError("figure_id must be one safe path segment")
    qualification_fingerprint = _qualification_fingerprint(qualification)
    analysis_fingerprint = _analysis_fingerprint(analysis)
    if ceiling.analysis_fingerprint != analysis_fingerprint:
        raise ValueError("claim-ceiling analysis fingerprint does not match the current analysis")
    if ceiling.qualification_fingerprint != qualification_fingerprint:
        raise ValueError(
            "claim-ceiling qualification fingerprint does not match the current qualification"
        )
    if ceiling.scientific_input_fingerprint != analysis.scientific_input_fingerprint:
        raise ValueError("claim-ceiling scientific input is stale")
    if ceiling != assess_v03_claim_ceiling(qualification, analysis):
        raise ValueError("claim-ceiling decision is not the current canonical decision")
    if ceiling.ceiling == V03ClaimCeiling.NO_NUMERICAL_CLAIM:
        raise ValueError("no-numerical-claim cannot generate a figure candidate")
    if len(analysis.values) < 2:
        raise ValueError("candidate figure requires at least two observed members")
    if not _complete_quantitative_bindings(analysis):
        raise ValueError("candidate figure requires complete located QoI values")
    x_units = {item.coordinate_unit for item in analysis.values}
    y_units = {item.unit for item in analysis.values}
    if len(x_units) != 1 or len(y_units) != 1:
        raise ValueError("candidate figure requires one x unit and one y unit")

    claim = _bounded_claim(analysis, ceiling)
    panel = CandidateFigurePanel(
        panel_id=f"{figure}-panel-a",
        x_variable=analysis.coordinate_name,
        x_unit=analysis.values[0].coordinate_unit,
        x_values=tuple(item.coordinate_value for item in analysis.values),
        y_variable=analysis.qoi_name,
        y_definition=analysis.scientific_definition,
        y_unit=analysis.values[0].unit,
        case_order=tuple(item.case_id for item in analysis.values),
    )
    paragraph = ParagraphDuty(
        claim_id=claim.claim_id,
        duty="; ".join(ceiling.allowed_sentence_duties),
        evidence_ids=claim.evidence_ids,
        numeric_backlink_ids=claim.numeric_backlink_ids,
        prohibited_inferences=_PROHIBITED_INFERENCES,
    )
    body = {
        "figure_id": figure,
        "qualification_fingerprint": qualification_fingerprint,
        "analysis_fingerprint": analysis_fingerprint,
        "scientific_input_fingerprint": analysis.scientific_input_fingerprint,
        "claim_ceiling_fingerprint": ceiling.fingerprint,
        "author": normalized_author,
        "primary_claim": claim,
        "evidence_ids": claim.evidence_ids,
        "numeric_backlink_ids": claim.numeric_backlink_ids,
        "panels": (panel,),
        "paragraph_duty": paragraph,
        "caption_duty": (
            "Identify all cases as discrete observations and state that connecting lines guide "
            "the eye only."
        ),
        "prohibited_inferences": _PROHIBITED_INFERENCES,
        "status": "candidate",
    }
    fingerprint = canonical_sha256(body, domain=b"cfdpaper-v03-candidate-figure-contract")
    return CandidateFigureContract(**body, fingerprint=fingerprint)


def lock_figure_contract(
    candidate: CandidateFigureContract,
    *,
    approval: AuthorApproval,
    current_qualification: QualificationReport,
    current_analysis: QoIAnalysis,
    current_input_fingerprint: str,
    source_data_uri: str,
) -> FigureContract:
    """Convert an unchanged, author-approved candidate to the public contract."""

    expected_source_uri = f".cfdpaper/outputs/figure/{candidate.figure_id}/source-data.csv"
    if source_data_uri != expected_source_uri:
        raise ValueError("source_data_uri must equal the deterministic figure output path")
    if _candidate_fingerprint(candidate) != candidate.fingerprint:
        raise ValueError("candidate fingerprint does not match candidate content")
    if approval.author != candidate.author:
        raise ValueError("approval author does not match the candidate author")
    if (
        approval.object_id != candidate.figure_id
        or approval.object_fingerprint != candidate.fingerprint
    ):
        raise ValueError("approval is not bound to this candidate")
    if current_input_fingerprint != current_analysis.scientific_input_fingerprint:
        raise ValueError("current scientific input does not match the QoI analysis")
    if _qualification_fingerprint(current_qualification) != candidate.qualification_fingerprint:
        raise ValueError("current qualification does not match the figure candidate")
    if _analysis_fingerprint(current_analysis) != candidate.analysis_fingerprint:
        raise ValueError("current QoI analysis does not match the figure candidate")
    if current_analysis.scientific_input_fingerprint != candidate.scientific_input_fingerprint:
        raise ValueError("scientific analysis is stale")
    current_ceiling = assess_v03_claim_ceiling(current_qualification, current_analysis)
    if current_ceiling.fingerprint != candidate.claim_ceiling_fingerprint:
        raise ValueError("current claim ceiling does not match the figure candidate")
    if current_ceiling.ceiling != candidate.primary_claim.ceiling:
        raise ValueError("current claim ceiling level does not match the primary claim")

    return FigureContract(
        figure_id=candidate.figure_id,
        primary_claim_id=candidate.primary_claim.claim_id,
        evidence_ids=list(candidate.evidence_ids),
        panels=[candidate.panels[0].panel_id],
        source_data_uri=source_data_uri,
        prohibited_inferences=list(candidate.prohibited_inferences),
    )
