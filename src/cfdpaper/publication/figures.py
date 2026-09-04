"""Figure contracts, source-data manifests, artifacts, and QA gates."""

from __future__ import annotations

import csv
import hashlib
import json
import zlib
from datetime import datetime
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from cfdpaper.contracts import FigureContract

EDITABLE_FIGURE_SUFFIXES = frozenset({".svg", ".pdf", ".eps"})


class PublicationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class SourceDataEntry(PublicationModel):
    data_id: str = Field(min_length=1)
    path: Path
    evidence_ids: list[str] = Field(min_length=1)
    row_count: int | None = Field(default=None, ge=0)
    sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
    )


class SourceDataManifest(PublicationModel):
    figure_id: str = Field(min_length=1)
    entries: list[SourceDataEntry] = Field(min_length=1)


class FigureArtifact(PublicationModel):
    path: Path
    role: Literal["editable", "preview", "other"]


class QAFinding(PublicationModel):
    finding_id: str = Field(min_length=1)
    severity: Literal["info", "warning", "blocking"]
    detail: str = Field(min_length=1)


class FigureComputedCheck(PublicationModel):
    check_id: str = Field(min_length=1)
    status: Literal["pass", "fail"]
    detail: str = Field(min_length=1)


class QAAssetBinding(PublicationModel):
    uri: Path
    sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
    )


class QAResult(PublicationModel):
    dimension: Literal["data", "narrative", "visual"]
    computed_checks: list[FigureComputedCheck] = Field(default_factory=list)
    findings: list[QAFinding] = Field(default_factory=list)
    executor: str = Field(min_length=1)
    tool: str = Field(min_length=1)
    timestamp: datetime
    source: Path
    source_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
    )
    source_data_bindings: list[QAAssetBinding] = Field(min_length=1)
    artifact_bindings: list[QAAssetBinding] = Field(min_length=1)
    manifest_hash: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
    )

    @model_validator(mode="after")
    def trace_is_real(self) -> QAResult:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("QA timestamp must be timezone-aware")
        if not _is_nonempty_file(self.source):
            raise ValueError("QA source is missing or empty")
        if _sha256(self.source) != self.source_hash.lower():
            raise ValueError("QA source hash does not match")
        return self

    @property
    def status(self) -> Literal["pass", "fail"]:
        checks_pass = bool(self.computed_checks) and all(
            check.status == "pass" for check in self.computed_checks
        )
        has_blocker = any(finding.severity == "blocking" for finding in self.findings)
        return "pass" if checks_pass and not has_blocker else "fail"


class FigureDeliveryValidation(PublicationModel):
    valid: bool
    issues: list[str] = Field(default_factory=list)
    computed_checks: list[FigureComputedCheck] = Field(default_factory=list)
    qa_results: list[QAResult] = Field(default_factory=list)


def _is_nonempty_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_data_manifest_hash(manifest: SourceDataManifest) -> str:
    payload = json.dumps(
        manifest.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _binding_signature(bindings: list[QAAssetBinding]) -> list[tuple[str, str]]:
    return sorted(
        (str(binding.uri.expanduser().resolve()), binding.sha256.lower()) for binding in bindings
    )


def _tabular_row_count(path: Path) -> int:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        rows = [
            row
            for row in csv.reader(source, delimiter=delimiter)
            if any(cell.strip() for cell in row)
        ]
    return max(len(rows) - 1, 0)


def _valid_svg(path: Path) -> bool:
    try:
        root = ElementTree.parse(path).getroot()
    except (ElementTree.ParseError, OSError):
        return False
    return root.tag.rsplit("}", maxsplit=1)[-1].casefold() == "svg"


def _valid_pdf(path: Path) -> bool:
    try:
        content = path.read_bytes()
    except OSError:
        return False
    return content.startswith(b"%PDF-") and content.rstrip().endswith(b"%%EOF")


def _valid_eps(path: Path) -> bool:
    try:
        return path.read_bytes().startswith(b"%!PS-Adobe")
    except OSError:
        return False


def _valid_png(path: Path) -> bool:
    try:
        content = path.read_bytes()
    except OSError:
        return False
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    offset = 8
    seen_ihdr = False
    seen_idat = False
    while offset + 12 <= len(content):
        chunk_length = int.from_bytes(content[offset : offset + 4], "big")
        chunk_type = content[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + chunk_length
        crc_end = data_end + 4
        if crc_end > len(content):
            return False
        chunk_data = content[data_start:data_end]
        expected_crc = int.from_bytes(content[data_end:crc_end], "big")
        if zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF != expected_crc:
            return False
        if not seen_ihdr:
            if chunk_type != b"IHDR" or chunk_length != 13:
                return False
            width = int.from_bytes(chunk_data[:4], "big")
            height = int.from_bytes(chunk_data[4:8], "big")
            if width == 0 or height == 0:
                return False
            seen_ihdr = True
        elif chunk_type == b"IDAT":
            seen_idat = True
        elif chunk_type == b"IEND":
            return chunk_length == 0 and seen_idat and crc_end == len(content)
        offset = crc_end
    return False


def _valid_jpeg(path: Path) -> bool:
    try:
        content = path.read_bytes()
    except OSError:
        return False
    if not content.startswith(b"\xff\xd8") or not content.endswith(b"\xff\xd9"):
        return False
    offset = 2
    seen_frame = False
    frame_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    while offset < len(content) - 2:
        if content[offset] != 0xFF:
            return False
        while offset < len(content) and content[offset] == 0xFF:
            offset += 1
        if offset >= len(content):
            return False
        marker = content[offset]
        offset += 1
        if marker in {*range(0xD0, 0xD8), 0x01}:
            continue
        if offset + 2 > len(content):
            return False
        segment_length = int.from_bytes(content[offset : offset + 2], "big")
        if segment_length < 2 or offset + segment_length > len(content):
            return False
        if marker in frame_markers:
            frame_data = content[offset + 2 : offset + segment_length]
            if len(frame_data) < 6:
                return False
            height = int.from_bytes(frame_data[1:3], "big")
            width = int.from_bytes(frame_data[3:5], "big")
            if width == 0 or height == 0:
                return False
            seen_frame = True
        offset += segment_length
        if marker == 0xDA:
            return seen_frame
    return False


def _valid_gif(path: Path) -> bool:
    try:
        content = path.read_bytes()
    except OSError:
        return False
    if len(content) < 14 or content[:6] not in {b"GIF87a", b"GIF89a"}:
        return False
    width = int.from_bytes(content[6:8], "little")
    height = int.from_bytes(content[8:10], "little")
    if width == 0 or height == 0:
        return False
    packed = content[10]
    offset = 13
    if packed & 0x80:
        offset += 3 * (2 ** ((packed & 0x07) + 1))
    if offset > len(content):
        return False

    def consume_subblocks(start: int) -> int | None:
        while start < len(content):
            block_length = content[start]
            start += 1
            if block_length == 0:
                return start
            start += block_length
            if start > len(content):
                return None
        return None

    seen_image = False
    while offset < len(content):
        block_type = content[offset]
        offset += 1
        if block_type == 0x3B:
            return seen_image and offset == len(content)
        if block_type == 0x21:
            if offset >= len(content):
                return False
            offset = consume_subblocks(offset + 1) or -1
        elif block_type == 0x2C:
            if offset + 9 > len(content):
                return False
            image_width = int.from_bytes(content[offset + 4 : offset + 6], "little")
            image_height = int.from_bytes(content[offset + 6 : offset + 8], "little")
            image_packed = content[offset + 8]
            if image_width == 0 or image_height == 0:
                return False
            offset += 9
            if image_packed & 0x80:
                offset += 3 * (2 ** ((image_packed & 0x07) + 1))
            if offset >= len(content):
                return False
            offset = consume_subblocks(offset + 1) or -1
            seen_image = True
        else:
            return False
        if offset < 0:
            return False
    return False


def validate_figure_delivery(
    contract: FigureContract,
    manifest: SourceDataManifest,
    artifacts: list[FigureArtifact],
    qa: list[QAResult],
) -> FigureDeliveryValidation:
    """Validate that a figure is evidenced, materialized, editable, and reviewed."""

    issues: list[str] = []
    computed_checks: list[FigureComputedCheck] = []

    def check(check_id: str, passed: bool, failure: str, success: str) -> None:
        computed_checks.append(
            FigureComputedCheck(
                check_id=check_id,
                status="pass" if passed else "fail",
                detail=success if passed else failure,
            )
        )
        if not passed:
            issues.append(failure)

    check(
        "manifest-figure-id",
        manifest.figure_id == contract.figure_id,
        f"source-data manifest figure mismatch:{manifest.figure_id}!={contract.figure_id}",
        "source-data manifest matches figure contract",
    )

    manifest_evidence = {
        evidence_id for entry in manifest.entries for evidence_id in entry.evidence_ids
    }
    for evidence_id in contract.evidence_ids:
        check(
            f"manifest-evidence:{evidence_id}",
            evidence_id in manifest_evidence,
            f"figure evidence is absent from source-data manifest:{evidence_id}",
            f"figure evidence is mapped:{evidence_id}",
        )

    manifest_paths = {entry.path.expanduser().resolve() for entry in manifest.entries}
    contract_source = Path(contract.source_data_uri).expanduser()
    if contract_source.is_absolute():
        source_is_mapped = contract_source.resolve() in manifest_paths
    else:
        source_parts = contract_source.parts
        source_is_mapped = any(
            path.parts[-len(source_parts) :] == source_parts for path in manifest_paths
        )
    check(
        "manifest-source-uri",
        source_is_mapped,
        f"contract source data is absent from manifest:{contract.source_data_uri}",
        "contract source data is present in manifest",
    )

    for entry in manifest.entries:
        source_exists = _is_nonempty_file(entry.path)
        check(
            f"source-file:{entry.data_id}",
            source_exists,
            f"source-data file is missing or empty:{entry.path}",
            f"source-data file is nonempty:{entry.path}",
        )
        if source_exists:
            check(
                f"source-hash:{entry.data_id}",
                _sha256(entry.path) == entry.sha256.lower(),
                f"source-data hash mismatch:{entry.path}",
                f"source-data hash matches:{entry.path}",
            )
            if entry.path.suffix.lower() in {".csv", ".tsv"}:
                if entry.row_count is None:
                    check(
                        f"source-row-count:{entry.data_id}",
                        False,
                        f"source-data row count is required:{entry.path}",
                        "unreachable",
                    )
                else:
                    try:
                        actual_row_count = _tabular_row_count(entry.path)
                    except (OSError, UnicodeError, csv.Error):
                        check(
                            f"source-row-count:{entry.data_id}",
                            False,
                            f"source-data table cannot be parsed:{entry.path}",
                            "unreachable",
                        )
                    else:
                        check(
                            f"source-row-count:{entry.data_id}",
                            actual_row_count == entry.row_count,
                            (
                                f"source-data row count mismatch:{entry.path}:"
                                f"{entry.row_count}!={actual_row_count}"
                            ),
                            f"source-data row count matches:{entry.path}",
                        )

    for artifact in artifacts:
        artifact_exists = _is_nonempty_file(artifact.path)
        check(
            f"artifact-file:{artifact.path.name}",
            artifact_exists,
            f"output file is missing or empty:{artifact.path}",
            f"output file is nonempty:{artifact.path}",
        )
        if artifact_exists:
            suffix = artifact.path.suffix.lower()
            if suffix == ".svg":
                check(
                    f"artifact-svg:{artifact.path.name}",
                    _valid_svg(artifact.path),
                    f"editable SVG structure is invalid:{artifact.path}",
                    f"editable SVG structure is valid:{artifact.path}",
                )
            elif suffix == ".pdf":
                check(
                    f"artifact-pdf:{artifact.path.name}",
                    _valid_pdf(artifact.path),
                    f"output PDF structure is invalid:{artifact.path}",
                    f"output PDF structure is valid:{artifact.path}",
                )
            elif suffix == ".eps":
                check(
                    f"artifact-eps:{artifact.path.name}",
                    _valid_eps(artifact.path),
                    f"editable EPS structure is invalid:{artifact.path}",
                    f"editable EPS structure is valid:{artifact.path}",
                )
            elif suffix == ".png":
                check(
                    f"artifact-png:{artifact.path.name}",
                    _valid_png(artifact.path),
                    f"output PNG structure is invalid:{artifact.path}",
                    f"output PNG structure is valid:{artifact.path}",
                )
            elif suffix in {".jpg", ".jpeg"}:
                check(
                    f"artifact-jpeg:{artifact.path.name}",
                    _valid_jpeg(artifact.path),
                    f"output JPEG structure is invalid:{artifact.path}",
                    f"output JPEG structure is valid:{artifact.path}",
                )
            elif suffix == ".gif":
                check(
                    f"artifact-gif:{artifact.path.name}",
                    _valid_gif(artifact.path),
                    f"output GIF structure is invalid:{artifact.path}",
                    f"output GIF structure is valid:{artifact.path}",
                )

    editable_artifacts = [artifact for artifact in artifacts if artifact.role == "editable"]
    if not editable_artifacts:
        check(
            "editable-output",
            False,
            "editable output is required",
            "unreachable",
        )
    else:
        check(
            "editable-format",
            any(
                artifact.path.suffix.lower() in EDITABLE_FIGURE_SUFFIXES
                for artifact in editable_artifacts
            ),
            "editable output must use SVG, PDF, or EPS format",
            "editable output uses SVG, PDF, or EPS format",
        )

    revalidated_qa: list[QAResult] = []
    for result in qa:
        try:
            revalidated_qa.append(QAResult.model_validate(result.model_dump()))
        except ValidationError:
            issues.append(f"{result.dimension} QA trace failed revalidation")

    expected_source_bindings = [
        QAAssetBinding(uri=entry.path, sha256=_sha256(entry.path))
        for entry in manifest.entries
        if _is_nonempty_file(entry.path)
    ]
    expected_artifact_bindings = [
        QAAssetBinding(uri=artifact.path, sha256=_sha256(artifact.path))
        for artifact in artifacts
        if _is_nonempty_file(artifact.path)
    ]
    expected_manifest_hash = source_data_manifest_hash(manifest)

    for dimension in ("data", "narrative", "visual"):
        dimension_results = [result for result in revalidated_qa if result.dimension == dimension]
        if not dimension_results:
            issues.append(f"{dimension} QA result is missing")
            continue
        if len(dimension_results) > 1:
            issues.append(f"{dimension} QA result is duplicated")
            continue
        result = dimension_results[0]
        if result.manifest_hash.lower() != expected_manifest_hash:
            issues.append(f"{dimension} QA manifest hash does not match delivery")
        if _binding_signature(result.source_data_bindings) != _binding_signature(
            expected_source_bindings
        ):
            issues.append(f"{dimension} QA source-data bindings do not match delivery")
        if _binding_signature(result.artifact_bindings) != _binding_signature(
            expected_artifact_bindings
        ):
            issues.append(f"{dimension} QA artifact bindings do not match delivery")
        if not result.computed_checks:
            issues.append(f"{dimension} QA has no computed checks")
        elif result.status != "pass":
            issues.append(f"{dimension} QA did not pass")

    return FigureDeliveryValidation(
        valid=not issues,
        issues=issues,
        computed_checks=computed_checks,
        qa_results=revalidated_qa,
    )
