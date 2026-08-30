import base64
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from cfdpaper.contracts import ClaimRecord, FigureContract
from cfdpaper.publication.claims import (
    ClaimEvidenceMapping,
    EvidenceCeiling,
    EvidenceLink,
    check_claim_ceiling,
)
from cfdpaper.publication.figures import (
    FigureArtifact,
    FigureComputedCheck,
    QAAssetBinding,
    QAFinding,
    QAResult,
    SourceDataEntry,
    SourceDataManifest,
    source_data_manifest_hash,
    validate_figure_delivery,
)


def write_nonempty(path: Path, content: str = "content") -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_minimal_png(path: Path) -> Path:
    path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
    )
    return path


def write_minimal_jpeg(path: Path) -> Path:
    path.write_bytes(
        b"\xff\xd8"
        b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
        b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00"
        b"\x00\xff\xd9"
    )
    return path


def write_minimal_gif(path: Path) -> Path:
    path.write_bytes(base64.b64decode("R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="))
    return path


def traced_qa_results(
    tmp_path: Path,
    manifest: SourceDataManifest,
    *,
    narrative_blocking: bool = False,
    visual_check_status: str = "pass",
) -> list[QAResult]:
    source = tmp_path / "qa-trace.txt"
    source.write_text("Computed QA trace for synthetic figure delivery.", encoding="utf-8")
    source_hash = file_sha256(source)
    source_data_bindings = [
        QAAssetBinding(uri=entry.path, sha256=file_sha256(entry.path))
        for entry in manifest.entries
        if entry.path.is_file() and entry.path.stat().st_size > 0
    ]
    media_suffixes = {".svg", ".pdf", ".eps", ".png", ".jpg", ".jpeg", ".gif"}
    artifact_bindings = [
        QAAssetBinding(uri=path, sha256=file_sha256(path))
        for path in tmp_path.iterdir()
        if path.is_file() and path.stat().st_size > 0 and path.suffix.lower() in media_suffixes
    ]
    timestamp = datetime(2026, 8, 29, tzinfo=timezone.utc)
    results: list[QAResult] = []
    for dimension in ("data", "narrative", "visual"):
        findings = (
            [
                QAFinding(
                    finding_id="narrative-overreach",
                    severity="blocking",
                    detail="Title exceeds the evidence.",
                )
            ]
            if dimension == "narrative" and narrative_blocking
            else []
        )
        check_status = visual_check_status if dimension == "visual" else "pass"
        results.append(
            QAResult(
                dimension=dimension,
                computed_checks=[
                    FigureComputedCheck(
                        check_id=f"{dimension}-check",
                        status=check_status,
                        detail=f"{dimension} computed check",
                    )
                ],
                findings=findings,
                executor="publication-test",
                tool="synthetic-qa",
                timestamp=timestamp,
                source=source,
                source_hash=source_hash,
                source_data_bindings=source_data_bindings,
                artifact_bindings=artifact_bindings,
                manifest_hash=source_data_manifest_hash(manifest),
            )
        )
    return results


def figure_contract(source_data: Path) -> FigureContract:
    return FigureContract(
        figure_id="fig-1",
        primary_claim_id="claim-1",
        evidence_ids=["ev-qoi", "ev-field"],
        panels=["response", "distribution"],
        source_data_uri=str(source_data),
        prohibited_inferences=["continuous behavior between sampled cases"],
    )


def test_figure_delivery_requires_real_nonempty_editable_output(tmp_path: Path) -> None:
    source = write_nonempty(tmp_path / "figure-data.csv", "case,value\nA,1.0\n")
    preview = write_minimal_png(tmp_path / "figure.png")
    editable = tmp_path / "figure.svg"
    manifest = SourceDataManifest(
        figure_id="fig-1",
        entries=[
            SourceDataEntry(
                data_id="table-1",
                path=source,
                evidence_ids=["ev-qoi", "ev-field"],
                row_count=1,
                sha256=file_sha256(source),
            )
        ],
    )

    result = validate_figure_delivery(
        figure_contract(source),
        manifest,
        artifacts=[
            FigureArtifact(path=preview, role="preview"),
            FigureArtifact(path=editable, role="editable"),
        ],
        qa=traced_qa_results(tmp_path, manifest),
    )

    assert result.valid is False
    assert result.issues == [f"output file is missing or empty:{editable}"]


def test_figure_delivery_accepts_complete_manifest_artifacts_and_qa(tmp_path: Path) -> None:
    source = write_nonempty(tmp_path / "figure-data.csv", "case,value\nA,1.0\n")
    preview = write_minimal_png(tmp_path / "figure.png")
    editable = write_nonempty(tmp_path / "figure.svg", "<svg><text>A</text></svg>")
    manifest = SourceDataManifest(
        figure_id="fig-1",
        entries=[
            SourceDataEntry(
                data_id="table-1",
                path=source,
                evidence_ids=["ev-qoi", "ev-field"],
                row_count=1,
                sha256=file_sha256(source),
            )
        ],
    )

    result = validate_figure_delivery(
        figure_contract(source),
        manifest,
        artifacts=[
            FigureArtifact(path=preview, role="preview"),
            FigureArtifact(path=editable, role="editable"),
        ],
        qa=traced_qa_results(tmp_path, manifest),
    )

    assert result.valid is True
    assert result.issues == []
    assert result.computed_checks
    assert all(check.status == "pass" for check in result.computed_checks)
    assert any(check.check_id == "editable-format" for check in result.computed_checks)


def test_figure_delivery_rejects_unmapped_evidence_and_failed_qa(tmp_path: Path) -> None:
    source = write_nonempty(tmp_path / "figure-data.csv")
    editable = tmp_path / "figure.pdf"
    editable.write_bytes(b"%PDF-1.4\n%%EOF")
    manifest = SourceDataManifest(
        figure_id="fig-1",
        entries=[
            SourceDataEntry(
                data_id="table-1",
                path=source,
                evidence_ids=["ev-qoi"],
                row_count=0,
                sha256=file_sha256(source),
            )
        ],
    )

    result = validate_figure_delivery(
        figure_contract(source),
        manifest,
        artifacts=[FigureArtifact(path=editable, role="editable")],
        qa=traced_qa_results(
            tmp_path,
            manifest,
            narrative_blocking=True,
            visual_check_status="fail",
        ),
    )

    assert result.valid is False
    assert result.issues == [
        "figure evidence is absent from source-data manifest:ev-field",
        "narrative QA did not pass",
        "visual QA did not pass",
    ]


def test_figure_delivery_verifies_declared_source_data_hash(tmp_path: Path) -> None:
    source = write_nonempty(tmp_path / "figure-data.csv", "case,value\nA,1.0\n")
    editable = write_nonempty(tmp_path / "figure.svg", "<svg/>")
    manifest = SourceDataManifest(
        figure_id="fig-1",
        entries=[
            SourceDataEntry(
                data_id="table-1",
                path=source,
                evidence_ids=["ev-qoi", "ev-field"],
                row_count=1,
                sha256="0" * 64,
            )
        ],
    )

    result = validate_figure_delivery(
        figure_contract(source),
        manifest,
        artifacts=[FigureArtifact(path=editable, role="editable")],
        qa=traced_qa_results(tmp_path, manifest),
    )

    assert result.valid is False
    assert result.issues == [f"source-data hash mismatch:{source}"]


def test_source_data_manifest_requires_sha256(tmp_path: Path) -> None:
    source = write_nonempty(tmp_path / "figure-data.csv", "case,value\nA,1.0\n")

    with pytest.raises(ValidationError, match="sha256"):
        SourceDataEntry(
            data_id="table-1",
            path=source,
            evidence_ids=["ev-qoi"],
            row_count=1,
        )


def test_figure_delivery_detects_false_csv_row_count(tmp_path: Path) -> None:
    source = write_nonempty(tmp_path / "figure-data.csv", "case,value\nA,1.0\n")
    editable = write_nonempty(tmp_path / "figure.svg", "<svg/>")
    manifest = SourceDataManifest(
        figure_id="fig-1",
        entries=[
            SourceDataEntry(
                data_id="table-1",
                path=source,
                evidence_ids=["ev-qoi", "ev-field"],
                row_count=7,
                sha256=file_sha256(source),
            )
        ],
    )

    result = validate_figure_delivery(
        figure_contract(source),
        manifest,
        artifacts=[FigureArtifact(path=editable, role="editable")],
        qa=traced_qa_results(tmp_path, manifest),
    )

    assert result.valid is False
    assert result.issues == [f"source-data row count mismatch:{source}:7!=1"]


def test_figure_delivery_rejects_fake_svg_despite_reported_visual_qa(
    tmp_path: Path,
) -> None:
    source = write_nonempty(tmp_path / "figure-data.csv", "case,value\nA,1.0\n")
    editable = write_nonempty(tmp_path / "figure.svg", "not svg markup")
    manifest = SourceDataManifest(
        figure_id="fig-1",
        entries=[
            SourceDataEntry(
                data_id="table-1",
                path=source,
                evidence_ids=["ev-qoi", "ev-field"],
                row_count=1,
                sha256=file_sha256(source),
            )
        ],
    )

    result = validate_figure_delivery(
        figure_contract(source),
        manifest,
        artifacts=[FigureArtifact(path=editable, role="editable")],
        qa=traced_qa_results(tmp_path, manifest),
    )

    assert result.valid is False
    assert result.issues == [f"editable SVG structure is invalid:{editable}"]
    assert any(check.check_id == "artifact-svg:figure.svg" for check in result.computed_checks)


def test_figure_delivery_rejects_truncated_pdf(tmp_path: Path) -> None:
    source = write_nonempty(tmp_path / "figure-data.csv", "case,value\nA,1.0\n")
    editable = tmp_path / "figure.pdf"
    editable.write_bytes(b"%PDF-1.4\nmissing terminator")
    manifest = SourceDataManifest(
        figure_id="fig-1",
        entries=[
            SourceDataEntry(
                data_id="table-1",
                path=source,
                evidence_ids=["ev-qoi", "ev-field"],
                row_count=1,
                sha256=file_sha256(source),
            )
        ],
    )

    result = validate_figure_delivery(
        figure_contract(source),
        manifest,
        artifacts=[FigureArtifact(path=editable, role="editable")],
        qa=traced_qa_results(tmp_path, manifest),
    )

    assert result.valid is False
    assert result.issues == [f"output PDF structure is invalid:{editable}"]


def test_figure_delivery_validates_pdf_structure_for_preview_role(
    tmp_path: Path,
) -> None:
    source = write_nonempty(tmp_path / "figure-data.csv", "case,value\nA,1.0\n")
    editable = write_nonempty(tmp_path / "figure.svg", "<svg/>")
    preview = tmp_path / "preview.pdf"
    preview.write_bytes(b"not a PDF")
    manifest = SourceDataManifest(
        figure_id="fig-1",
        entries=[
            SourceDataEntry(
                data_id="table-1",
                path=source,
                evidence_ids=["ev-qoi", "ev-field"],
                row_count=1,
                sha256=file_sha256(source),
            )
        ],
    )

    result = validate_figure_delivery(
        figure_contract(source),
        manifest,
        artifacts=[
            FigureArtifact(path=editable, role="editable"),
            FigureArtifact(path=preview, role="preview"),
        ],
        qa=traced_qa_results(tmp_path, manifest),
    )

    assert result.valid is False
    assert result.issues == [f"output PDF structure is invalid:{preview}"]


def test_figure_delivery_rejects_empty_checks_and_self_reported_pass(
    tmp_path: Path,
) -> None:
    source = write_nonempty(tmp_path / "figure-data.csv", "case,value\nA,1.0\n")
    editable = write_nonempty(tmp_path / "figure.svg", "<svg/>")
    qa_source = write_nonempty(tmp_path / "qa-trace.txt", "Trace exists.")
    manifest = SourceDataManifest(
        figure_id="fig-1",
        entries=[
            SourceDataEntry(
                data_id="table-1",
                path=source,
                evidence_ids=["ev-qoi", "ev-field"],
                row_count=1,
                sha256=file_sha256(source),
            )
        ],
    )
    valid_qa = traced_qa_results(tmp_path, manifest)
    empty_visual_payload = valid_qa[-1].model_dump()
    empty_visual_payload["computed_checks"] = []
    empty_visual_payload["source"] = qa_source
    empty_visual_payload["source_hash"] = file_sha256(qa_source)
    empty_visual_payload["status"] = "pass"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        QAResult.model_validate(empty_visual_payload)

    empty_visual_payload.pop("status")
    qa = [item for item in valid_qa if item.dimension != "visual"]
    qa.append(QAResult.model_validate(empty_visual_payload))
    result = validate_figure_delivery(
        figure_contract(source),
        manifest,
        artifacts=[FigureArtifact(path=editable, role="editable")],
        qa=qa,
    )

    assert result.valid is False
    assert result.issues == ["visual QA has no computed checks"]


def test_figure_delivery_rejects_unrelated_qa_asset_bindings(tmp_path: Path) -> None:
    source = write_nonempty(tmp_path / "figure-data.csv", "case,value\nA,1.0\n")
    editable = write_nonempty(tmp_path / "figure.svg", "<svg/>")
    unrelated = write_nonempty(tmp_path / "unrelated.svg", "<svg/>")
    manifest = SourceDataManifest(
        figure_id="fig-1",
        entries=[
            SourceDataEntry(
                data_id="table-1",
                path=source,
                evidence_ids=["ev-qoi", "ev-field"],
                row_count=1,
                sha256=file_sha256(source),
            )
        ],
    )
    qa = traced_qa_results(tmp_path, manifest)
    visual = next(item for item in qa if item.dimension == "visual")
    visual.artifact_bindings = [QAAssetBinding(uri=unrelated, sha256=file_sha256(unrelated))]

    result = validate_figure_delivery(
        figure_contract(source),
        manifest,
        artifacts=[FigureArtifact(path=editable, role="editable")],
        qa=qa,
    )

    assert result.valid is False
    assert "visual QA artifact bindings do not match delivery" in result.issues


def test_figure_delivery_rejects_old_qa_after_artifact_changes(tmp_path: Path) -> None:
    source = write_nonempty(tmp_path / "figure-data.csv", "case,value\nA,1.0\n")
    editable = write_nonempty(tmp_path / "figure.svg", "<svg/>")
    manifest = SourceDataManifest(
        figure_id="fig-1",
        entries=[
            SourceDataEntry(
                data_id="table-1",
                path=source,
                evidence_ids=["ev-qoi", "ev-field"],
                row_count=1,
                sha256=file_sha256(source),
            )
        ],
    )
    old_qa = traced_qa_results(tmp_path, manifest)
    editable.write_text("<svg><text>changed</text></svg>", encoding="utf-8")
    fresh_qa = traced_qa_results(tmp_path, manifest)
    old_visual = next(item for item in old_qa if item.dimension == "visual")
    qa = [item for item in fresh_qa if item.dimension != "visual"] + [old_visual]

    result = validate_figure_delivery(
        figure_contract(source),
        manifest,
        artifacts=[FigureArtifact(path=editable, role="editable")],
        qa=qa,
    )

    assert result.valid is False
    assert "visual QA artifact bindings do not match delivery" in result.issues


@pytest.mark.parametrize(
    ("suffix", "content", "format_name"),
    [
        (".png", b"not png", "PNG"),
        (".jpg", b"not jpeg", "JPEG"),
        (".gif", b"not gif", "GIF"),
    ],
)
def test_figure_delivery_rejects_fake_raster_artifact(
    tmp_path: Path,
    suffix: str,
    content: bytes,
    format_name: str,
) -> None:
    source = write_nonempty(tmp_path / "figure-data.csv", "case,value\nA,1.0\n")
    editable = write_nonempty(tmp_path / "figure.svg", "<svg/>")
    preview = tmp_path / f"preview{suffix}"
    preview.write_bytes(content)
    manifest = SourceDataManifest(
        figure_id="fig-1",
        entries=[
            SourceDataEntry(
                data_id="table-1",
                path=source,
                evidence_ids=["ev-qoi", "ev-field"],
                row_count=1,
                sha256=file_sha256(source),
            )
        ],
    )
    qa = traced_qa_results(tmp_path, manifest)

    result = validate_figure_delivery(
        figure_contract(source),
        manifest,
        artifacts=[
            FigureArtifact(path=editable, role="editable"),
            FigureArtifact(path=preview, role="preview"),
        ],
        qa=qa,
    )

    assert result.valid is False
    assert f"output {format_name} structure is invalid:{preview}" in result.issues


@pytest.mark.parametrize(
    ("suffix", "content", "format_name"),
    [
        (
            ".png",
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR"
            + b"\x00" * 13
            + b"\x00\x00\x00\x00"
            + b"\x00\x00\x00\x00IEND\x00\x00\x00\x00",
            "PNG",
        ),
        (".jpg", b"\xff\xd8not-a-jpeg\xff\xd9", "JPEG"),
        (".gif", b"GIF89a;", "GIF"),
    ],
)
def test_figure_delivery_rejects_magic_only_raster_artifact(
    tmp_path: Path,
    suffix: str,
    content: bytes,
    format_name: str,
) -> None:
    source = write_nonempty(tmp_path / "figure-data.csv", "case,value\nA,1.0\n")
    editable = write_nonempty(tmp_path / "figure.svg", "<svg/>")
    preview = tmp_path / f"preview{suffix}"
    preview.write_bytes(content)
    manifest = SourceDataManifest(
        figure_id="fig-1",
        entries=[
            SourceDataEntry(
                data_id="table-1",
                path=source,
                evidence_ids=["ev-qoi", "ev-field"],
                row_count=1,
                sha256=file_sha256(source),
            )
        ],
    )

    result = validate_figure_delivery(
        figure_contract(source),
        manifest,
        artifacts=[
            FigureArtifact(path=editable, role="editable"),
            FigureArtifact(path=preview, role="preview"),
        ],
        qa=traced_qa_results(tmp_path, manifest),
    )

    assert result.valid is False
    assert f"output {format_name} structure is invalid:{preview}" in result.issues


@pytest.mark.parametrize(
    ("suffix", "writer"),
    [
        (".png", write_minimal_png),
        (".jpg", write_minimal_jpeg),
        (".gif", write_minimal_gif),
    ],
)
def test_figure_delivery_accepts_structured_raster_artifact(
    tmp_path: Path,
    suffix: str,
    writer,
) -> None:
    source = write_nonempty(tmp_path / "figure-data.csv", "case,value\nA,1.0\n")
    editable = write_nonempty(tmp_path / "figure.svg", "<svg/>")
    preview = writer(tmp_path / f"preview{suffix}")
    manifest = SourceDataManifest(
        figure_id="fig-1",
        entries=[
            SourceDataEntry(
                data_id="table-1",
                path=source,
                evidence_ids=["ev-qoi", "ev-field"],
                row_count=1,
                sha256=file_sha256(source),
            )
        ],
    )

    result = validate_figure_delivery(
        figure_contract(source),
        manifest,
        artifacts=[
            FigureArtifact(path=editable, role="editable"),
            FigureArtifact(path=preview, role="preview"),
        ],
        qa=traced_qa_results(tmp_path, manifest),
    )

    assert result.valid is True


def test_claim_ceiling_blocks_mechanism_claim_supported_only_by_association() -> None:
    claim = ClaimRecord(
        claim_id="claim-1",
        text="The inlet setting causes the observed wake recovery.",
        status="supported",
        evidence_ids=["ev-field", "ev-qoi"],
        ceiling="mechanism",
    )
    mapping = ClaimEvidenceMapping(
        claim_id="claim-1",
        links=[
            EvidenceLink(evidence_id="ev-field", role="supports"),
            EvidenceLink(evidence_id="ev-qoi", role="context"),
        ],
    )

    result = check_claim_ceiling(
        claim,
        mapping,
        [
            EvidenceCeiling(evidence_id="ev-field", ceiling="association"),
            EvidenceCeiling(evidence_id="ev-qoi", ceiling="observation"),
        ],
    )

    assert result.allowed is False
    assert result.effective_ceiling == "association"
    assert result.issues == [
        "claim ceiling mechanism exceeds supporting evidence ceiling association"
    ]


def test_claim_ceiling_uses_supporting_links_not_context_links() -> None:
    claim = ClaimRecord(
        claim_id="claim-1",
        text="The response is associated with inlet setting.",
        status="supported",
        evidence_ids=["ev-field", "ev-context"],
        ceiling="association",
    )
    mapping = ClaimEvidenceMapping(
        claim_id="claim-1",
        links=[
            EvidenceLink(evidence_id="ev-field", role="supports"),
            EvidenceLink(evidence_id="ev-context", role="context"),
        ],
    )

    result = check_claim_ceiling(
        claim,
        mapping,
        [
            EvidenceCeiling(evidence_id="ev-field", ceiling="association"),
            EvidenceCeiling(evidence_id="ev-context", ceiling="observation"),
        ],
    )

    assert result.allowed is True
    assert result.issues == []


def test_claim_ceiling_rejects_missing_evidence_assessment() -> None:
    claim = ClaimRecord(
        claim_id="claim-1",
        text="A sampled response was observed.",
        evidence_ids=["ev-field"],
        ceiling="observation",
    )
    mapping = ClaimEvidenceMapping(
        claim_id="claim-1",
        links=[EvidenceLink(evidence_id="ev-field", role="supports")],
    )

    result = check_claim_ceiling(claim, mapping, [])

    assert result.allowed is False
    assert result.effective_ceiling is None
    assert result.issues == ["missing evidence ceiling:ev-field"]


def test_claim_ceiling_rejects_support_link_absent_from_claim_record() -> None:
    claim = ClaimRecord(
        claim_id="claim-1",
        text="A sampled response was observed.",
        evidence_ids=["ev-field"],
        ceiling="observation",
    )
    mapping = ClaimEvidenceMapping(
        claim_id="claim-1",
        links=[
            EvidenceLink(evidence_id="ev-field", role="supports"),
            EvidenceLink(evidence_id="ev-unregistered", role="supports"),
        ],
    )

    result = check_claim_ceiling(
        claim,
        mapping,
        [
            EvidenceCeiling(evidence_id="ev-field", ceiling="observation"),
            EvidenceCeiling(evidence_id="ev-unregistered", ceiling="engineering"),
        ],
    )

    assert result.allowed is False
    assert result.issues == ["supporting evidence is absent from claim record:ev-unregistered"]
