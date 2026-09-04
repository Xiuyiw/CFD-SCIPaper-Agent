from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cfdpaper.publication.render_figure import FigureDelivery, build_figure_delivery
from cfdpaper.publication.results_paragraph import (
    ParagraphRenderError,
    _materialize_numeric_tokens,
    render_results_paragraph,
)
from cfdpaper.qualification.claims import (
    assess_v03_claim_ceiling,
    build_candidate_figure_contract,
    lock_figure_contract,
)
from cfdpaper.qualification.models import (
    AuthorApproval,
    CandidateFigureContract,
    CaseDifference,
    ClaimCeilingDecision,
    DiscreteTrend,
    NumericBacklink,
    NumericFormattingRule,
    ParagraphDuty,
    QoIAnalysis,
    QoIValue,
    QualificationReport,
    V03ClaimCeiling,
    VNVStatus,
)
from cfdpaper.topic_generation.canonical import canonical_sha256


def _vnv(label: str, state: str = "demonstrated") -> VNVStatus:
    located = state in {"demonstrated", "partial"}
    return VNVStatus(
        state=state,
        summary=f"{label} status",
        evidence_ids=(f"ev-{label}",) if located else (),
        basis=f"located {label} evidence" if located else None,
        source_locator=f"{label}.md#result" if located else None,
        intended_use_supported=state == "demonstrated",
    )


def _analysis(count: int = 3) -> QoIAnalysis:
    values = tuple(
        QoIValue(
            result_id=f"result-{index}",
            case_id=f"C{index}",
            coordinate_value=float(index),
            coordinate_unit="kg/s",
            value=float(index * 10),
            unit="Pa",
            evidence_id=f"evidence-{index}",
            source_locator=f"observations.csv#row={index + 1}",
        )
        for index in range(1, count + 1)
    )
    return QoIAnalysis(
        qoi_contract_id="qoi-pressure-drop",
        qoi_name="Pressure drop",
        scientific_definition="inlet-to-outlet pressure drop",
        coordinate_name="Flow rate",
        qualification_input_fingerprint="a" * 64,
        scientific_input_fingerprint="b" * 64,
        values=values,
        overall_change=values[-1].value - values[0].value,
        trend=(DiscreteTrend.MONOTONIC_INCREASING if count >= 3 else DiscreteTrend.OVERALL_CHANGE),
        restrictions=(),
        quantitative_reporting_allowed=True,
    )


def _qualification(*, supported: bool = True) -> QualificationReport:
    return QualificationReport(
        status="eligible",
        differences=(
            CaseDifference(
                name="mass flow rate",
                reference="C1",
                candidate="C3",
                role="intended-study-factor",
            ),
        ),
        verification=_vnv("verification", "demonstrated" if supported else "partial"),
        validation=_vnv("validation"),
        blockers=(),
        restrictions=(),
        minimum_corrections=(),
        input_fingerprint="a" * 64,
    )


def _delivery(
    root: Path,
    *,
    count: int = 3,
    supported: bool = True,
    formatting_rule: NumericFormattingRule | None = None,
    approved_interpretation: str | None = None,
) -> tuple[
    ParagraphDuty,
    QoIAnalysis,
    ClaimCeilingDecision,
    CandidateFigureContract,
    FigureDelivery,
]:
    analysis = _analysis(count)
    qualification = _qualification(supported=supported)
    ceiling = assess_v03_claim_ceiling(qualification, analysis)
    candidate = build_candidate_figure_contract(
        analysis=analysis,
        qualification=qualification,
        ceiling=ceiling,
        figure_id="fig-7",
        author="Author A",
    )
    if formatting_rule is not None or approved_interpretation is not None:
        paragraph_duty = candidate.paragraph_duty.model_copy(
            update={
                "formatting_rule": formatting_rule or candidate.paragraph_duty.formatting_rule,
                "approved_interpretation": approved_interpretation,
            }
        )
        body = candidate.model_dump(mode="python", exclude={"fingerprint"})
        body["paragraph_duty"] = paragraph_duty
        candidate = CandidateFigureContract(
            **body,
            fingerprint=canonical_sha256(body, domain=b"cfdpaper-v03-candidate-figure-contract"),
        )
    approval = AuthorApproval(
        author="Author A",
        object_id=candidate.figure_id,
        object_fingerprint=candidate.fingerprint,
        approved_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
    )
    contract = lock_figure_contract(
        candidate,
        approval=approval,
        current_qualification=qualification,
        current_analysis=analysis,
        current_input_fingerprint=analysis.scientific_input_fingerprint,
        source_data_uri=".cfdpaper/outputs/figure/fig-7/source-data.csv",
    )
    delivery = build_figure_delivery(
        root=root,
        contract=contract,
        candidate=candidate,
        analysis=analysis,
        approval=approval,
    )
    return candidate.paragraph_duty, analysis, ceiling, candidate, delivery


def _forced_ceiling(
    analysis: QoIAnalysis,
    level: V03ClaimCeiling,
) -> ClaimCeilingDecision:
    body = {
        "ceiling": level,
        "reasons": ("forced test ceiling",),
        "allowed_sentence_duties": ("test duty",),
        "quantitative_reporting_allowed": level
        in {
            V03ClaimCeiling.QUALIFIED_NUMERICAL_OBSERVATION,
            V03ClaimCeiling.SUPPORTED_PHYSICAL_INTERPRETATION,
        },
        "qualification_fingerprint": "c" * 64,
        "analysis_fingerprint": canonical_sha256(analysis, domain=b"cfdpaper-v03-qoi-analysis"),
        "scientific_input_fingerprint": analysis.scientific_input_fingerprint,
    }
    return ClaimCeilingDecision(
        **body,
        fingerprint=canonical_sha256(body, domain=b"cfdpaper-v03-claim-ceiling-decision"),
    )


def test_no_numerical_ceiling_refuses_delivery_before_writing(tmp_path: Path) -> None:
    duty, analysis, _, candidate, figure = _delivery(tmp_path)

    with pytest.raises(ParagraphRenderError, match="no-numerical-claim"):
        render_results_paragraph(
            duty=duty,
            analysis=analysis,
            ceiling=_forced_ceiling(analysis, V03ClaimCeiling.NO_NUMERICAL_CLAIM),
            candidate=candidate,
            figure_delivery=figure,
        )

    assert not (tmp_path / ".cfdpaper" / "outputs" / "write").exists()


def test_directional_paragraph_names_cases_coordinate_and_figure_without_mechanism(
    tmp_path: Path,
) -> None:
    duty, analysis, ceiling, candidate, figure = _delivery(tmp_path, count=2)

    delivery = render_results_paragraph(
        duty=duty,
        analysis=analysis,
        ceiling=ceiling,
        candidate=candidate,
        figure_delivery=figure,
    )

    assert ceiling.ceiling == V03ClaimCeiling.DIRECTIONAL_COMPARISON
    assert "C1 and C2" in delivery.paragraph
    assert "Flow rate" in delivery.paragraph
    assert "Fig. 7" in delivery.paragraph
    assert "increased" in delivery.paragraph
    assert delivery.backlinks == ()
    assert not {"because", "caused", "mechanism", "therefore"} & set(
        delivery.paragraph.casefold().replace(".", "").split()
    )


def test_qualified_paragraph_reports_all_values_units_and_discrete_trend(
    tmp_path: Path,
) -> None:
    duty, analysis, ceiling, candidate, figure = _delivery(tmp_path, supported=False)

    delivery = render_results_paragraph(
        duty=duty,
        analysis=analysis,
        ceiling=ceiling,
        candidate=candidate,
        figure_delivery=figure,
    )

    assert ceiling.ceiling == V03ClaimCeiling.QUALIFIED_NUMERICAL_OBSERVATION
    assert "Across the observed discrete cases, Pressure drop increased monotonically" in (
        delivery.paragraph
    )
    assert "10, 20, and 30 Pa" in delivery.paragraph
    assert "C1, C2, and C3, respectively" in delivery.paragraph
    assert tuple(item.qoi_result_id for item in delivery.backlinks) == tuple(
        item.result_id for item in analysis.values
    )
    assert all(item.unit == "Pa" for item in delivery.backlinks)
    assert all(item.formatting_rule.mode == "significant-figures" for item in delivery.backlinks)


def test_supported_paragraph_uses_only_the_approved_interpretation(tmp_path: Path) -> None:
    approved = "The pressure response reflects the approved flow-resistance interpretation."
    duty, analysis, ceiling, candidate, figure = _delivery(
        tmp_path, approved_interpretation=approved
    )
    assert duty.approved_interpretation == approved

    delivery = render_results_paragraph(
        duty=duty,
        analysis=analysis,
        ceiling=ceiling,
        candidate=candidate,
        figure_delivery=figure,
    )

    assert ceiling.ceiling == V03ClaimCeiling.SUPPORTED_PHYSICAL_INTERPRETATION
    assert delivery.paragraph.endswith(approved)
    assert delivery.paragraph.count(approved) == 1
    assert "test duty" not in delivery.paragraph


def test_supported_paragraph_without_approved_interpretation_stays_observational(
    tmp_path: Path,
) -> None:
    duty, analysis, ceiling, candidate, figure = _delivery(tmp_path)

    delivery = render_results_paragraph(
        duty=duty,
        analysis=analysis,
        ceiling=ceiling,
        candidate=candidate,
        figure_delivery=figure,
    )

    assert ceiling.ceiling == V03ClaimCeiling.SUPPORTED_PHYSICAL_INTERPRETATION
    assert delivery.paragraph.endswith("respectively.")
    assert "interpreted only" not in delivery.paragraph


def _backlink(backlink_id: str, raw: float, rendered: str) -> NumericBacklink:
    return NumericBacklink(
        backlink_id=backlink_id,
        case_id="C10",
        raw_value=raw,
        rendered_value=rendered,
        unit="Pa",
        qoi_result_id=f"result-{backlink_id}",
        evidence_id=f"evidence-{backlink_id}",
        source_locator="observations.csv#row=2",
        formatting_rule=NumericFormattingRule(mode="significant-figures", digits=3),
    )


@pytest.mark.parametrize(
    ("template", "backlinks", "message"),
    [
        ("Value {{NB:nb-0001}}.", (), "unexpected"),
        ("Value.", (_backlink("nb-0001", 9.876, "9.88"),), "unused"),
        (
            "{{NB:nb-0001}} then {{NB:nb-0001}}.",
            (_backlink("nb-0001", 9.876, "9.88"),),
            "duplicated",
        ),
        (
            "{{NB:nb-9999}}.",
            (_backlink("nb-0001", 9.876, "9.88"),),
            "unexpected",
        ),
    ],
)
def test_numeric_tokens_reject_missing_duplicate_injected_or_unused(
    template: str,
    backlinks: tuple[NumericBacklink, ...],
    message: str,
) -> None:
    with pytest.raises(ParagraphRenderError, match=message):
        _materialize_numeric_tokens(template, backlinks)


def test_numeric_tokens_reject_rounding_drift_and_ignore_other_digits() -> None:
    changed = _backlink("nb-0001", 9.876, "9.87")
    with pytest.raises(ParagraphRenderError, match="formatted value"):
        _materialize_numeric_tokens("Value {{NB:nb-0001}}.", (changed,))

    assert (
        _materialize_numeric_tokens(
            "Section 3, Fig. 7, C10 and citation [12] contain no value token.", ()
        )
        == "Section 3, Fig. 7, C10 and citation [12] contain no value token."
    )


def test_renderer_rejects_missing_unit_stale_input_and_failed_figure_qa(
    tmp_path: Path,
) -> None:
    duty, analysis, ceiling, candidate, figure = _delivery(tmp_path, supported=False)
    bad_value = analysis.values[0].model_copy(update={"unit": ""})
    missing_unit = analysis.model_copy(update={"values": (bad_value, *analysis.values[1:])})
    with pytest.raises(ParagraphRenderError, match="unit"):
        render_results_paragraph(
            duty=duty,
            analysis=missing_unit,
            ceiling=ceiling,
            candidate=candidate,
            figure_delivery=figure,
        )

    stale = analysis.model_copy(update={"scientific_input_fingerprint": "d" * 64})
    with pytest.raises(ParagraphRenderError, match="stale"):
        render_results_paragraph(
            duty=duty,
            analysis=stale,
            ceiling=ceiling,
            candidate=candidate,
            figure_delivery=figure,
        )

    failed = figure.model_copy(
        update={
            "validation": figure.validation.model_copy(
                update={"valid": False, "issues": ["visual QA failed"]}
            )
        }
    )
    with pytest.raises(ParagraphRenderError, match="figure QA"):
        render_results_paragraph(
            duty=duty,
            analysis=analysis,
            ceiling=ceiling,
            candidate=candidate,
            figure_delivery=failed,
        )


def test_renderer_rejects_duplicate_qoi_binding_and_injected_placeholder(
    tmp_path: Path,
) -> None:
    duty, analysis, ceiling, candidate, figure = _delivery(tmp_path, supported=False)
    duplicate = analysis.model_copy(update={"values": (*analysis.values, analysis.values[-1])})
    with pytest.raises(ParagraphRenderError, match="duplicate"):
        render_results_paragraph(
            duty=duty,
            analysis=duplicate,
            ceiling=ceiling,
            candidate=candidate,
            figure_delivery=figure,
        )

    (
        supported_duty,
        supported_analysis,
        supported,
        supported_candidate,
        supported_figure,
    ) = _delivery(
        tmp_path / "supported",
        approved_interpretation="Unexpected {{NB:nb-injected}} token.",
    )
    with pytest.raises(ParagraphRenderError, match="unexpected"):
        render_results_paragraph(
            duty=supported_duty,
            analysis=supported_analysis,
            ceiling=supported,
            candidate=supported_candidate,
            figure_delivery=supported_figure,
        )


def test_renderer_writes_the_three_deterministic_delivery_files(tmp_path: Path) -> None:
    duty, analysis, ceiling, candidate, figure = _delivery(tmp_path, supported=False)

    first = render_results_paragraph(
        duty=duty,
        analysis=analysis,
        ceiling=ceiling,
        candidate=candidate,
        figure_delivery=figure,
    )
    output = tmp_path / ".cfdpaper" / "outputs" / "write"
    before = {path.name: path.read_bytes() for path in output.iterdir()}
    second = render_results_paragraph(
        duty=duty,
        analysis=analysis,
        ceiling=ceiling,
        candidate=candidate,
        figure_delivery=figure,
    )

    assert {path.name for path in output.iterdir()} == {
        "results-paragraph.txt",
        "numeric-backlinks.json",
        "delivery.json",
    }
    assert (output / "results-paragraph.txt").read_text(encoding="utf-8") == (
        first.paragraph + "\n"
    )
    backlinks = json.loads((output / "numeric-backlinks.json").read_text(encoding="utf-8"))
    assert backlinks == [item.model_dump(mode="json") for item in first.backlinks]
    persisted = json.loads((output / "delivery.json").read_text(encoding="utf-8"))
    assert persisted == first.model_dump(mode="json")
    assert second == first
    assert {path.name: path.read_bytes() for path in output.iterdir()} == before


def test_decimal_places_format_is_central_and_preserved_in_backlinks(tmp_path: Path) -> None:
    decimal_rule = NumericFormattingRule(mode="decimal-places", digits=2)
    duty, analysis, ceiling, candidate, figure = _delivery(
        tmp_path,
        supported=False,
        formatting_rule=decimal_rule,
    )

    delivery = render_results_paragraph(
        duty=duty,
        analysis=analysis,
        ceiling=ceiling,
        candidate=candidate,
        figure_delivery=figure,
    )

    assert "10.00, 20.00, and 30.00 Pa" in delivery.paragraph
    assert [item.rendered_value for item in delivery.backlinks] == [
        "10.00",
        "20.00",
        "30.00",
    ]


@pytest.mark.parametrize(
    "duty_update",
    [
        {"duty": "A different sentence duty."},
        {"approved_interpretation": "An unapproved causal mechanism."},
        {"formatting_rule": NumericFormattingRule(mode="decimal-places", digits=1)},
        {"prohibited_inferences": ("interpolation",)},
    ],
)
def test_renderer_rejects_any_duty_change_after_candidate_approval(
    tmp_path: Path,
    duty_update: dict[str, object],
) -> None:
    duty, analysis, ceiling, candidate, figure = _delivery(tmp_path)

    with pytest.raises(ParagraphRenderError, match="approved paragraph duty"):
        render_results_paragraph(
            duty=duty.model_copy(update=duty_update),
            analysis=analysis,
            ceiling=ceiling,
            candidate=candidate,
            figure_delivery=figure,
        )


def test_renderer_rejects_forced_higher_ceiling(tmp_path: Path) -> None:
    duty, analysis, ceiling, candidate, figure = _delivery(tmp_path, supported=False)
    assert ceiling.ceiling == V03ClaimCeiling.QUALIFIED_NUMERICAL_OBSERVATION

    with pytest.raises(ParagraphRenderError, match="approved claim ceiling"):
        render_results_paragraph(
            duty=duty,
            analysis=analysis,
            ceiling=_forced_ceiling(analysis, V03ClaimCeiling.SUPPORTED_PHYSICAL_INTERPRETATION),
            candidate=candidate,
            figure_delivery=figure,
        )


@pytest.mark.parametrize("failed_write", [2, 3])
def test_bundle_publish_preserves_previous_delivery_if_staging_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failed_write: int,
) -> None:
    duty, analysis, ceiling, candidate, figure = _delivery(tmp_path, supported=False)
    render_results_paragraph(
        duty=duty,
        analysis=analysis,
        ceiling=ceiling,
        candidate=candidate,
        figure_delivery=figure,
    )
    output = tmp_path / ".cfdpaper" / "outputs" / "write"
    previous = {path.name: path.read_bytes() for path in output.iterdir()}
    import cfdpaper.qualification.artifacts as artifacts

    original = artifacts._write_staged_artifact
    calls = 0

    def fail_during_staging(path: Path, content: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == failed_write:
            raise OSError("simulated staging failure")
        original(path, content)

    monkeypatch.setattr(artifacts, "_write_staged_artifact", fail_during_staging)

    with pytest.raises(OSError, match="simulated staging failure"):
        render_results_paragraph(
            duty=duty,
            analysis=analysis,
            ceiling=ceiling,
            candidate=candidate,
            figure_delivery=figure,
        )

    assert {path.name: path.read_bytes() for path in output.iterdir()} == previous
