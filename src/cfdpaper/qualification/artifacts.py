"""Deterministic V0.3 qualification artifacts and scientific fingerprints."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, TypeVar
from uuid import uuid4

from pydantic import BaseModel

from cfdpaper.scientific import units as unit_definitions
from cfdpaper.topic_generation.canonical import canonical_json_bytes, canonical_sha256

from .models import ExpectedMember, ObservationTable


class ArtifactInputMismatch(ValueError):
    """Raised when a persisted artifact does not match its declared scientific input."""


ModelT = TypeVar("ModelT", bound=BaseModel)
_OUTPUT_PARTS = (".cfdpaper", "outputs", "qualify")
_FIGURE_OUTPUT_PARTS = (".cfdpaper", "outputs", "figure")
_WRITE_OUTPUT_PARTS = (".cfdpaper", "outputs", "write")
_WRITE_ARTIFACT_NAMES = frozenset(
    {"results-paragraph.txt", "numeric-backlinks.json", "delivery.json"}
)


def qualify_output_dir(project_root: Path) -> Path:
    return Path(project_root).resolve().joinpath(*_OUTPUT_PARTS)


def figure_output_dir(project_root: Path, figure_id: str, *, create: bool = False) -> Path:
    """Return the one permitted output directory for a rendered V0.3 figure."""

    root = Path(project_root).resolve()
    figure = figure_id.strip()
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", figure) is None:
        raise ValueError("figure_id must be one safe path segment")
    expected = root.joinpath(*_FIGURE_OUTPUT_PARTS, figure)
    if create:
        expected.mkdir(parents=True, exist_ok=True)
    resolved = expected.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("path escapes the figure output directory") from error
    if resolved != expected:
        raise ValueError("path escapes the figure output directory")
    return resolved


def write_output_dir(project_root: Path, *, create: bool = False) -> Path:
    """Return the deterministic V0.3 results-paragraph output directory."""

    root = Path(project_root).resolve()
    expected = root.joinpath(*_WRITE_OUTPUT_PARTS)
    if create:
        expected.mkdir(parents=True, exist_ok=True)
    resolved = expected.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("path escapes the write output directory") from error
    if resolved != expected:
        raise ValueError("path escapes the write output directory")
    return resolved


def write_output_artifact_atomic(
    project_root: Path,
    artifact_name: str,
    content: bytes,
) -> Path:
    """Atomically replace one of the three V0.3 paragraph-delivery artifacts."""

    name = artifact_name.strip()
    if name not in _WRITE_ARTIFACT_NAMES:
        raise ValueError("unsupported write artifact name")
    destination = write_output_dir(project_root, create=True) / name
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(content)
            stream.flush()
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _write_staged_artifact(path: Path, content: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()


def write_output_bundle_atomic(
    project_root: Path,
    artifacts: dict[str, bytes],
) -> Path:
    """Publish the complete paragraph delivery with one directory swap."""

    if set(artifacts) != _WRITE_ARTIFACT_NAMES:
        raise ValueError("write bundle must contain exactly the three delivery artifacts")
    destination = write_output_dir(project_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    staging = destination.with_name(f".{destination.name}.{token}.stage")
    backup = destination.with_name(f".{destination.name}.{token}.backup")
    staging.mkdir()
    try:
        for name in sorted(_WRITE_ARTIFACT_NAMES):
            _write_staged_artifact(staging / name, artifacts[name])
        had_previous = destination.exists()
        if had_previous:
            destination.replace(backup)
        try:
            staging.replace(destination)
        except BaseException:
            if had_previous and backup.exists():
                backup.replace(destination)
            raise
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return destination


def _validated_output_dir(project_root: Path, *, create: bool) -> Path:
    root = Path(project_root).resolve()
    expected = root.joinpath(*_OUTPUT_PARTS)
    if create:
        expected.mkdir(parents=True, exist_ok=True)
    resolved = expected.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("path escapes the qualification output directory") from error
    if resolved != expected:
        raise ValueError("path escapes the qualification output directory")
    return resolved


def qualify_artifact_path(project_root: Path, artifact_name: str) -> Path:
    name = artifact_name.strip()
    candidate = Path(name)
    if not name or candidate.is_absolute() or candidate.name != name or candidate.suffix != ".json":
        raise ValueError("qualification artifact must be one JSON filename")
    return qualify_output_dir(project_root) / name


def qualification_report_path(project_root: Path) -> Path:
    return qualify_artifact_path(project_root, "qualification-report.json")


def candidate_qoi_contract_path(project_root: Path) -> Path:
    return qualify_artifact_path(project_root, "candidate-qoi-contract.json")


def locked_qoi_contract_path(project_root: Path) -> Path:
    return qualify_artifact_path(project_root, "locked-qoi-contract.json")


def qoi_results_path(project_root: Path) -> Path:
    return qualify_artifact_path(project_root, "qoi-results.json")


def claim_ceiling_path(project_root: Path) -> Path:
    return qualify_artifact_path(project_root, "claim-ceiling.json")


def candidate_figure_contract_path(project_root: Path) -> Path:
    return qualify_artifact_path(project_root, "candidate-figure-contract.json")


def paragraph_duty_path(project_root: Path) -> Path:
    return qualify_artifact_path(project_root, "paragraph-duty.json")


def canonical_bytes(value: Any) -> bytes:
    """Return the repository's canonical compact JSON representation."""

    return canonical_json_bytes(value)


def write_json_atomic(
    project_root: Path,
    artifact_name: str,
    value: Any,
    *,
    _fail_before_replace: bool = False,
) -> Path:
    """Write one validated qualification artifact without exposing partial bytes."""

    name = qualify_artifact_path(project_root, artifact_name).name
    content = canonical_bytes(value)
    destination = _validated_output_dir(project_root, create=True) / name
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(content)
            stream.flush()
        if _fail_before_replace:
            raise RuntimeError("injected failure before artifact replacement")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def load_json_model(
    project_root: Path,
    artifact_name: str,
    model_type: type[ModelT],
    *,
    expected_source_sha256: str | None = None,
) -> ModelT:
    """Strictly reload a qualification artifact and optionally bind its source hash."""

    name = qualify_artifact_path(project_root, artifact_name).name
    path = _validated_output_dir(project_root, create=False) / name
    loaded = model_type.model_validate_json(path.read_bytes())
    if expected_source_sha256 is not None:
        actual = getattr(loaded, "source_sha256", None)
        if actual != expected_source_sha256:
            raise ArtifactInputMismatch("artifact source hash does not match current source hash")
    return loaded


def scientific_input_fingerprint(
    *,
    observation_table: ObservationTable,
    expected_members: tuple[ExpectedMember, ...] = (),
    qoi_contract: BaseModel | None = None,
    qualification: BaseModel | None = None,
    topic_fingerprint: str | None = None,
    components: Any | None = None,
    unit_registry_version: str | None = None,
    unit_registry_digest: str | None = None,
) -> str:
    """Bind scientific records and the exact unit-registry identity in one digest."""

    version = unit_registry_version or unit_definitions.UNIT_REGISTRY_VERSION
    digest = unit_registry_digest or unit_definitions.UNIT_REGISTRY_SHA256
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ValueError("unit registry digest must be a lowercase SHA-256 value")
    payload = {
        "observation_table": observation_table,
        "expected_members": expected_members,
        "qoi_contract": qoi_contract,
        "qualification": qualification,
        "topic_fingerprint": topic_fingerprint,
        "components": components,
        "unit_registry": {"version": version, "sha256": digest},
    }
    return canonical_sha256(payload, domain=b"cfdpaper-v03-scientific-input")
