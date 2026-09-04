from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

import pytest

from cfdpaper.publication.figures import validate_figure_delivery
from cfdpaper.publication.render_figure import (
    FigureRenderError,
    build_figure_delivery,
    validate_rendered_figure,
)
from cfdpaper.qualification.claims import (
    assess_v03_claim_ceiling,
    build_candidate_figure_contract,
    lock_figure_contract,
)
from cfdpaper.qualification.models import (
    AuthorApproval,
    CaseDifference,
    DiscreteTrend,
    QoIAnalysis,
    QoIValue,
    QualificationReport,
    VNVStatus,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _vnv(label: str) -> VNVStatus:
    return VNVStatus(
        state="demonstrated",
        summary=f"{label} demonstrated for the intended numerical comparison",
        evidence_ids=(f"ev-{label}",),
        basis=f"located {label} evidence",
        source_locator=f"{label}.md#result",
        intended_use_supported=True,
    )


def _inputs(root: Path, coordinates: tuple[float, float, float] = (1.0, 2.0, 3.0)):
    observations = root / "observations.csv"
    observations.write_text(
        "case_id,flow_rate,pressure_drop\nC1,1,10\nC2,2,20\nC3,3,30\n",
        encoding="utf-8",
    )
    analysis = QoIAnalysis(
        qoi_contract_id="qoi-pressure-drop",
        qoi_name="Pressure drop",
        scientific_definition="inlet-to-outlet pressure drop",
        coordinate_name="Flow rate",
        qualification_input_fingerprint="a" * 64,
        scientific_input_fingerprint="b" * 64,
        values=tuple(
            QoIValue(
                result_id=f"result-{index}",
                case_id=f"C{index}",
                coordinate_value=coordinates[index - 1],
                coordinate_unit="kg/s",
                value=float(index * 10),
                unit="Pa",
                evidence_id=f"evidence-{index}",
                source_locator=f"observations.csv#row={index + 1}",
            )
            for index in range(1, 4)
        ),
        overall_change=20.0,
        trend=DiscreteTrend.MONOTONIC_INCREASING,
        restrictions=(),
        quantitative_reporting_allowed=True,
    )
    qualification = QualificationReport(
        status="eligible",
        differences=(
            CaseDifference(
                name="flow rate",
                reference="C1",
                candidate="C3",
                role="intended-study-factor",
            ),
        ),
        verification=_vnv("verification"),
        validation=_vnv("validation"),
        blockers=(),
        restrictions=(),
        minimum_corrections=(),
        input_fingerprint="a" * 64,
    )
    candidate = build_candidate_figure_contract(
        analysis=analysis,
        qualification=qualification,
        ceiling=assess_v03_claim_ceiling(qualification, analysis),
        figure_id="fig-pressure-drop",
        author="Author A",
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
        source_data_uri=(".cfdpaper/outputs/figure/fig-pressure-drop/source-data.csv"),
    )
    return observations, contract, candidate, analysis, approval


def _build(root: Path, coordinates: tuple[float, float, float] = (1.0, 2.0, 3.0)):
    observations, contract, candidate, analysis, approval = _inputs(root, coordinates)
    before = _sha256(observations)
    delivery = build_figure_delivery(
        root=root,
        contract=contract,
        candidate=candidate,
        analysis=analysis,
        approval=approval,
    )
    assert _sha256(observations) == before
    return delivery, contract, candidate, analysis


def test_small_decimal_coordinate_ticks_remain_inside_figure(tmp_path: Path) -> None:
    delivery, _, _, _ = _build(tmp_path, (0.05, 0.10, 0.15))

    visual = next(item for item in delivery.qa_results if item.dimension == "visual")
    bounds = next(item for item in visual.computed_checks if item.check_id == "artist-bounds")
    assert bounds.status == "pass"


def _png_dimensions(path: Path) -> tuple[int, int]:
    content = path.read_bytes()
    assert content.startswith(b"\x89PNG\r\n\x1a\n")
    return (
        int.from_bytes(content[16:20], "big"),
        int.from_bytes(content[20:24], "big"),
    )


def test_build_writes_only_the_bound_v03_figure_bundle(tmp_path: Path) -> None:
    delivery, _, _, analysis = _build(tmp_path)
    output = tmp_path / ".cfdpaper" / "outputs" / "figure" / "fig-pressure-drop"

    assert {path.name for path in output.iterdir()} == {
        "source-data.csv",
        "plot_fig-pressure-drop.py",
        "fig-pressure-drop.svg",
        "fig-pressure-drop.png",
        "caption.txt",
        "qa-data.json",
        "qa-narrative.json",
        "qa-visual.json",
        "delivery.json",
    }
    with (output / "source-data.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert [row["order"] for row in rows] == ["1", "2", "3"]
    assert [row["case_id"] for row in rows] == ["C1", "C2", "C3"]
    assert [float(row["coordinate_value"]) for row in rows] == [1.0, 2.0, 3.0]
    assert [row["coordinate_unit"] for row in rows] == ["kg/s"] * 3
    assert [float(row["qoi_value"]) for row in rows] == [10.0, 20.0, 30.0]
    assert [row["qoi_unit"] for row in rows] == ["Pa"] * 3
    assert [row["result_id"] for row in rows] == [item.result_id for item in analysis.values]
    assert [row["evidence_id"] for row in rows] == [item.evidence_id for item in analysis.values]
    assert [row["source_locator"] for row in rows] == [
        item.source_locator for item in analysis.values
    ]
    assert [row["trend"] for row in rows] == [analysis.trend.value] * 3
    caption = (output / "caption.txt").read_text(encoding="utf-8")
    assert caption == (
        "Pressure drop versus Flow rate for the observed discrete cases. "
        "Markers denote the reported values; the line is a visual guide only.\n"
    )
    assert "Identify" not in caption
    manifest = json.loads((output / "delivery.json").read_text(encoding="utf-8"))
    assert manifest["figure_id"] == "fig-pressure-drop"
    assert manifest["contract"] == delivery.contract.model_dump(mode="json")
    assert set(manifest["files"]) == {
        name
        for name in {
            "source-data.csv",
            "plot_fig-pressure-drop.py",
            "fig-pressure-drop.svg",
            "fig-pressure-drop.png",
            "caption.txt",
            "qa-data.json",
            "qa-narrative.json",
            "qa-visual.json",
        }
    }
    assert delivery.validation.valid is True
    assert validate_figure_delivery(
        delivery.contract,
        delivery.manifest,
        list(delivery.artifacts),
        list(delivery.qa_results),
    ).valid


def test_script_is_portable_runnable_and_does_not_recompute_qoi(tmp_path: Path) -> None:
    delivery, _, _, _ = _build(tmp_path)
    script = delivery.script_path
    content = script.read_text(encoding="utf-8")

    assert 'Path(__file__).with_name("source-data.csv")' in content
    assert str(tmp_path) not in content
    assert "MARKER_STYLE" in content
    assert "LINE_STYLE" in content
    assert "interpolate" not in content.casefold()
    assert "polyfit" not in content.casefold()

    delivery.svg_path.unlink()
    delivery.png_path.unlink()
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert delivery.svg_path.is_file()
    assert delivery.png_path.is_file()


def test_svg_png_and_three_qa_dimensions_are_reopened_and_valid(tmp_path: Path) -> None:
    delivery, _, _, _ = _build(tmp_path)

    svg_root = ElementTree.parse(delivery.svg_path).getroot()
    svg_text = " ".join(svg_root.itertext())
    assert svg_root.tag.rsplit("}", maxsplit=1)[-1] == "svg"
    for expected in ("Flow rate", "kg/s", "Pressure drop", "Pa", "C1", "C2", "C3"):
        assert expected in svg_text
    width, height = _png_dimensions(delivery.png_path)
    assert width >= 1500
    assert height >= 900
    assert {item.dimension for item in delivery.qa_results} == {
        "data",
        "narrative",
        "visual",
    }
    assert all(item.status == "pass" for item in delivery.qa_results)
    for result in delivery.qa_results:
        assert result.source_data_bindings[0].sha256 == _sha256(delivery.source_data_path)
        assert {binding.sha256 for binding in result.artifact_bindings} == {
            _sha256(delivery.svg_path),
            _sha256(delivery.png_path),
        }
    assert all(path.is_file() for path in delivery.qa_paths)
    for path in delivery.qa_paths:
        assert json.loads(path.read_text(encoding="utf-8"))["dimension"] in {
            "data",
            "narrative",
            "visual",
        }
    assert not list(delivery.output_dir.glob("*.pdf"))
    assert not list(delivery.output_dir.glob("*.tif*"))


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("case_id", "C9"),
        ("qoi_value", "999"),
        ("qoi_unit", "kPa"),
        ("source_locator", "other.csv#row=1"),
    ],
)
def test_data_qa_blocks_tampered_plotted_rows(tmp_path: Path, field: str, replacement: str) -> None:
    delivery, contract, candidate, analysis = _build(tmp_path)
    with delivery.source_data_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fieldnames = reader.fieldnames
    assert fieldnames is not None
    rows[0][field] = replacement
    with delivery.source_data_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    validation = validate_rendered_figure(
        root=tmp_path,
        contract=contract,
        candidate=candidate,
        analysis=analysis,
    )

    assert validation.valid is False
    data_qa = next(item for item in validation.qa_results if item.dimension == "data")
    assert data_qa.status == "fail"
    assert any(item.severity == "blocking" for item in data_qa.findings)


def test_narrative_qa_blocks_prohibited_inference_wording(tmp_path: Path) -> None:
    _, contract, candidate, analysis = _build(tmp_path)
    overreaching = candidate.model_copy(
        update={"caption_duty": "This identifies a continuous optimum."}
    )

    validation = validate_rendered_figure(
        root=tmp_path,
        contract=contract,
        candidate=overreaching,
        analysis=analysis,
    )

    assert validation.valid is False
    narrative = next(item for item in validation.qa_results if item.dimension == "narrative")
    assert narrative.status == "fail"
    assert any(item.severity == "blocking" for item in narrative.findings)


@pytest.mark.parametrize(
    "wording",
    [
        "This identifies an optimal response over a continuous range.",
        "This defines a safe operating boundary.",
    ],
)
def test_narrative_qa_blocks_synonymous_boundary_claims(tmp_path: Path, wording: str) -> None:
    _, contract, candidate, analysis = _build(tmp_path)
    overreaching = candidate.model_copy(update={"caption_duty": wording})

    validation = validate_rendered_figure(
        root=tmp_path,
        contract=contract,
        candidate=overreaching,
        analysis=analysis,
    )

    assert validation.valid is False
    narrative = next(item for item in validation.qa_results if item.dimension == "narrative")
    assert narrative.status == "fail"


def test_narrative_qa_uses_actual_endpoints_for_direction(tmp_path: Path) -> None:
    _, contract, candidate, analysis = _build(tmp_path)
    wrong_claim = candidate.primary_claim.model_copy(
        update={"text": "Pressure drop fell from 10 to 30 Pa."}
    )
    contradictory = candidate.model_copy(update={"primary_claim": wrong_claim})

    validation = validate_rendered_figure(
        root=tmp_path,
        contract=contract,
        candidate=contradictory,
        analysis=analysis,
    )

    assert validation.valid is False
    narrative = next(item for item in validation.qa_results if item.dimension == "narrative")
    assert narrative.status == "fail"


def test_delivery_manifest_blocks_script_and_redrawn_artifact_drift(tmp_path: Path) -> None:
    delivery, contract, candidate, analysis = _build(tmp_path)
    script = delivery.script_path
    script.write_text(
        script.read_text(encoding="utf-8").replace(
            'y_values = [float(row["qoi_value"]) for row in rows]',
            'y_values = [float(row["qoi_value"]) * 2.0 for row in rows]',
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=delivery.output_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr

    validation = validate_rendered_figure(
        root=tmp_path,
        contract=contract,
        candidate=candidate,
        analysis=analysis,
    )

    assert validation.valid is False
    assert any("hash mismatch" in issue for issue in validation.issues)


@pytest.mark.parametrize(
    "filename",
    [
        "source-data.csv",
        "plot_fig-pressure-drop.py",
        "fig-pressure-drop.svg",
        "fig-pressure-drop.png",
        "caption.txt",
        "qa-data.json",
        "qa-narrative.json",
        "qa-visual.json",
        "delivery.json",
    ],
)
def test_missing_delivery_file_returns_invalid_instead_of_raising(
    tmp_path: Path, filename: str
) -> None:
    delivery, contract, candidate, analysis = _build(tmp_path)
    (delivery.output_dir / filename).unlink()

    validation = validate_rendered_figure(
        root=tmp_path,
        contract=contract,
        candidate=candidate,
        analysis=analysis,
    )

    assert validation.valid is False
    assert any(filename in issue and "missing" in issue for issue in validation.issues)


def test_visual_qa_blocks_missing_case_text(tmp_path: Path) -> None:
    delivery, contract, candidate, analysis = _build(tmp_path)
    svg = delivery.svg_path.read_text(encoding="utf-8")
    delivery.svg_path.write_text(svg.replace("C2", "missing-case"), encoding="utf-8")

    validation = validate_rendered_figure(
        root=tmp_path,
        contract=contract,
        candidate=candidate,
        analysis=analysis,
    )

    assert validation.valid is False
    visual = next(item for item in validation.qa_results if item.dimension == "visual")
    assert visual.status == "fail"
    assert any(item.severity == "blocking" for item in visual.findings)


def test_visual_qa_blocks_a_clipped_annotation(tmp_path: Path) -> None:
    delivery, contract, candidate, analysis = _build(tmp_path)
    script = delivery.script_path
    script.write_text(
        script.read_text(encoding="utf-8").replace(
            "CASE_LABEL_OFFSET = 8", "CASE_LABEL_OFFSET = 800"
        ),
        encoding="utf-8",
    )

    validation = validate_rendered_figure(
        root=tmp_path,
        contract=contract,
        candidate=candidate,
        analysis=analysis,
    )

    assert validation.valid is False
    visual = next(item for item in validation.qa_results if item.dimension == "visual")
    assert visual.status == "fail"
    assert any("clipped" in item.detail.casefold() for item in visual.findings)


def test_build_rejects_an_unbound_approval_before_writing(tmp_path: Path) -> None:
    _, contract, candidate, analysis, approval = _inputs(tmp_path)
    wrong = approval.model_copy(update={"object_fingerprint": "f" * 64})

    with pytest.raises(FigureRenderError, match="approval"):
        build_figure_delivery(
            root=tmp_path,
            contract=contract,
            candidate=candidate,
            analysis=analysis,
            approval=wrong,
        )

    assert not (tmp_path / ".cfdpaper" / "outputs" / "figure").exists()
