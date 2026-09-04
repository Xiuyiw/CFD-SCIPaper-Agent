"""Render one evidence-bound results paragraph from locked V0.3 inputs."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from cfdpaper.qualification.artifacts import (
    canonical_bytes,
    write_output_bundle_atomic,
)
from cfdpaper.qualification.models import (
    CandidateFigureContract,
    ClaimCeilingDecision,
    NumericBacklink,
    NumericFormattingRule,
    ParagraphDelivery,
    ParagraphDuty,
    QoIAnalysis,
    V03ClaimCeiling,
)
from cfdpaper.topic_generation.canonical import canonical_sha256

from .render_figure import FigureDelivery


class ParagraphRenderError(RuntimeError):
    """Raised when locked evidence cannot support a paragraph delivery."""


_TOKEN = re.compile(r"\{\{NB:([A-Za-z0-9._-]+)\}\}")
_PROCESS_TERMS = re.compile(
    r"\b(?:audit|workflow|pipeline|checkpoint|traceability|pass/fail|rechecked)\b",
    flags=re.IGNORECASE,
)


def _format_numeric(value: float, rule: NumericFormattingRule) -> str:
    if rule.mode == "decimal-places":
        return f"{value:.{rule.digits}f}"
    return format(value, f".{rule.digits}g")


def _natural_join(items: tuple[str, ...]) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _figure_label(figure_id: str) -> str:
    match = re.fullmatch(r"fig(?:ure)?[-_. ]?(.*)", figure_id, flags=re.IGNORECASE)
    if match and match.group(1):
        return f"Fig. {match.group(1)}"
    return f"Fig. {figure_id}"


def _trend_text(analysis: QoIAnalysis) -> str:
    if analysis.trend is None:
        return "showed the reported overall change"
    return {
        "monotonic-increasing": "increased monotonically",
        "monotonic-decreasing": "decreased monotonically",
        "interior-peak": "reached an interior peak",
        "plateau": "approached a plateau",
        "overall-change": (
            "increased"
            if analysis.values[-1].value > analysis.values[0].value
            else "decreased"
            if analysis.values[-1].value < analysis.values[0].value
            else "showed no overall change"
        ),
    }[analysis.trend.value]


def _backlinks(duty: ParagraphDuty, analysis: QoIAnalysis) -> tuple[NumericBacklink, ...]:
    result_ids = tuple(item.result_id for item in analysis.values)
    if len(set(result_ids)) != len(result_ids):
        raise ParagraphRenderError("duplicate QoI result binding")
    if tuple(duty.numeric_backlink_ids) != result_ids:
        raise ParagraphRenderError("paragraph duty and QoI result bindings do not match")
    backlinks = []
    for index, value in enumerate(analysis.values, start=1):
        if not value.unit.strip():
            raise ParagraphRenderError("numeric backlink unit is missing")
        rendered = _format_numeric(value.value, duty.formatting_rule)
        backlinks.append(
            NumericBacklink(
                backlink_id=f"nb-{index:04d}",
                case_id=value.case_id,
                raw_value=value.value,
                rendered_value=rendered,
                unit=value.unit,
                qoi_result_id=value.result_id,
                evidence_id=value.evidence_id,
                source_locator=value.source_locator,
                formatting_rule=duty.formatting_rule,
            )
        )
    return tuple(backlinks)


def _materialize_numeric_tokens(
    template: str,
    backlinks: tuple[NumericBacklink, ...],
) -> str:
    identifiers = tuple(item.backlink_id for item in backlinks)
    if len(set(identifiers)) != len(identifiers):
        raise ParagraphRenderError("numeric backlink ID is duplicated")
    tokens = _TOKEN.findall(template)
    if len(tokens) != len(set(tokens)):
        raise ParagraphRenderError("numeric placeholder is duplicated")
    unexpected = set(tokens) - set(identifiers)
    if unexpected:
        raise ParagraphRenderError("unexpected numeric placeholder")
    unused = set(identifiers) - set(tokens)
    if unused:
        raise ParagraphRenderError("numeric backlink is unused")
    rendered = template
    for backlink in backlinks:
        expected = _format_numeric(backlink.raw_value, backlink.formatting_rule)
        if backlink.rendered_value != expected:
            raise ParagraphRenderError("formatted value does not match the locked rounding rule")
        rendered = rendered.replace(
            f"{{{{NB:{backlink.backlink_id}}}}}", backlink.rendered_value, 1
        )
    if _TOKEN.search(rendered):
        raise ParagraphRenderError("numeric placeholder remains after rendering")
    return rendered


def _project_root(figure_delivery: FigureDelivery) -> Path:
    output = figure_delivery.output_dir.resolve()
    expected_tail = (".cfdpaper", "outputs", "figure", figure_delivery.contract.figure_id)
    if tuple(output.parts[-4:]) != expected_tail:
        raise ParagraphRenderError("figure delivery is outside the expected project output")
    return output.parents[3]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_inputs(
    *,
    duty: ParagraphDuty,
    analysis: QoIAnalysis,
    ceiling: ClaimCeilingDecision,
    candidate: CandidateFigureContract,
    figure_delivery: FigureDelivery,
) -> None:
    if ceiling.ceiling == V03ClaimCeiling.NO_NUMERICAL_CLAIM:
        raise ParagraphRenderError("no-numerical-claim cannot produce a results paragraph")
    result_ids = tuple(item.result_id for item in analysis.values)
    if len(set(result_ids)) != len(result_ids):
        raise ParagraphRenderError("duplicate QoI result binding")
    if any(not item.unit.strip() for item in analysis.values):
        raise ParagraphRenderError("numeric backlink unit is missing")
    expected_analysis = canonical_sha256(analysis, domain=b"cfdpaper-v03-qoi-analysis")
    candidate_body = candidate.model_dump(mode="python", exclude={"fingerprint"})
    expected_candidate = canonical_sha256(
        candidate_body, domain=b"cfdpaper-v03-candidate-figure-contract"
    )
    if (
        candidate.fingerprint != expected_candidate
        or candidate.fingerprint != figure_delivery.delivery_manifest.candidate_fingerprint
    ):
        raise ParagraphRenderError("paragraph inputs do not match the approved figure candidate")
    if duty != candidate.paragraph_duty:
        raise ParagraphRenderError("paragraph duty does not match the approved paragraph duty")
    if (
        ceiling.fingerprint != candidate.claim_ceiling_fingerprint
        or ceiling.ceiling != candidate.primary_claim.ceiling
    ):
        raise ParagraphRenderError("claim ceiling does not match the approved claim ceiling")
    if (
        ceiling.analysis_fingerprint != expected_analysis
        or ceiling.scientific_input_fingerprint != analysis.scientific_input_fingerprint
        or figure_delivery.delivery_manifest.analysis_fingerprint != expected_analysis
        or figure_delivery.delivery_manifest.scientific_input_fingerprint
        != analysis.scientific_input_fingerprint
        or candidate.analysis_fingerprint != expected_analysis
        or candidate.scientific_input_fingerprint != analysis.scientific_input_fingerprint
    ):
        raise ParagraphRenderError("stale scientific input")
    if not figure_delivery.validation.valid or any(
        result.status != "pass" for result in figure_delivery.qa_results
    ):
        raise ParagraphRenderError("figure QA must pass before paragraph delivery")
    for name, expected_hash in figure_delivery.delivery_manifest.files.items():
        path = figure_delivery.output_dir / name
        if not path.is_file() or _sha256(path) != expected_hash:
            raise ParagraphRenderError("figure QA delivery has changed")
    if duty.claim_id != figure_delivery.contract.primary_claim_id:
        raise ParagraphRenderError("paragraph duty does not match the approved figure claim")
    if tuple(duty.evidence_ids) != tuple(figure_delivery.contract.evidence_ids):
        raise ParagraphRenderError("paragraph evidence does not match the approved figure")


def _paragraph_template(
    *,
    duty: ParagraphDuty,
    analysis: QoIAnalysis,
    ceiling: ClaimCeilingDecision,
    figure_delivery: FigureDelivery,
    backlinks: tuple[NumericBacklink, ...],
) -> str:
    cases = tuple(item.case_id for item in analysis.values)
    if not cases:
        raise ParagraphRenderError("paragraph requires observed cases")
    introduction = (
        f"{_figure_label(figure_delivery.contract.figure_id)} compares "
        f"{_natural_join(cases)} along the prescribed {analysis.coordinate_name}."
    )
    trend = _trend_text(analysis)
    if ceiling.ceiling == V03ClaimCeiling.DIRECTIONAL_COMPARISON:
        return f"{introduction} {analysis.qoi_name} {trend} across the observed discrete cases."

    values = _natural_join(tuple(f"{{{{NB:{item.backlink_id}}}}}" for item in backlinks))
    units = {item.unit for item in backlinks}
    if len(units) != 1:
        raise ParagraphRenderError("numeric backlinks require one common unit")
    observation = (
        f"Across the observed discrete cases, {analysis.qoi_name} {trend}; values were "
        f"{values} {next(iter(units))} for {_natural_join(cases)}, respectively."
    )
    if ceiling.ceiling == V03ClaimCeiling.SUPPORTED_PHYSICAL_INTERPRETATION:
        if duty.approved_interpretation is not None:
            return f"{introduction} {observation} {duty.approved_interpretation}"
    return f"{introduction} {observation}"


def render_results_paragraph(
    *,
    duty: ParagraphDuty,
    analysis: QoIAnalysis,
    ceiling: ClaimCeilingDecision,
    candidate: CandidateFigureContract,
    figure_delivery: FigureDelivery,
) -> ParagraphDelivery:
    """Render and atomically persist one ceiling-bounded results paragraph."""

    _validate_inputs(
        duty=duty,
        analysis=analysis,
        ceiling=ceiling,
        candidate=candidate,
        figure_delivery=figure_delivery,
    )
    backlinks = (
        ()
        if ceiling.ceiling == V03ClaimCeiling.DIRECTIONAL_COMPARISON
        else _backlinks(duty, analysis)
    )
    template = _paragraph_template(
        duty=duty,
        analysis=analysis,
        ceiling=ceiling,
        figure_delivery=figure_delivery,
        backlinks=backlinks,
    )
    paragraph = _materialize_numeric_tokens(template, backlinks)
    if _PROCESS_TERMS.search(paragraph):
        raise ParagraphRenderError("results paragraph contains process language")
    delivery = ParagraphDelivery(
        paragraph=paragraph,
        figure_id=figure_delivery.contract.figure_id,
        ceiling=ceiling.ceiling,
        scientific_input_fingerprint=analysis.scientific_input_fingerprint,
        backlinks=backlinks,
    )
    root = _project_root(figure_delivery)
    write_output_bundle_atomic(
        root,
        {
            "results-paragraph.txt": f"{paragraph}\n".encode(),
            "numeric-backlinks.json": canonical_bytes(backlinks),
            "delivery.json": canonical_bytes(delivery),
        },
    )
    return delivery
