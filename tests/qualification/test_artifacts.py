from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from cfdpaper.qualification.artifacts import (
    ArtifactInputMismatch,
    candidate_qoi_contract_path,
    canonical_bytes,
    load_json_model,
    qualification_report_path,
    qualify_artifact_path,
    scientific_input_fingerprint,
    write_json_atomic,
)
from cfdpaper.qualification.models import ObservationRow, ObservationTable, ValueRole


def _table(source_hash: str = "a" * 64) -> ObservationTable:
    return ObservationTable(
        source_uri="observations.csv",
        source_sha256=source_hash,
        rows=(
            ObservationRow(
                case_id="P1",
                coordinate_name="mean_velocity",
                coordinate_value=0.25,
                coordinate_unit="m/s",
                variable="pressure_drop",
                value=1.0,
                value_role=ValueRole.PRECOMPUTED_QOI,
                unit="Pa",
                scope="inlet-to-outlet pressure difference",
                source_locator="observations.csv#row=2",
            ),
        ),
    )


def test_qualify_artifact_paths_are_deterministic_and_confined(tmp_path: Path) -> None:
    expected = tmp_path / ".cfdpaper" / "outputs" / "qualify"
    assert qualification_report_path(tmp_path) == expected / "qualification-report.json"
    assert candidate_qoi_contract_path(tmp_path) == expected / "candidate-qoi-contract.json"
    assert qualify_artifact_path(tmp_path, "custom.json") == expected / "custom.json"

    for name in ("../escape.json", "nested/escape.json", "not-json.txt", ""):
        with pytest.raises(ValueError):
            qualify_artifact_path(tmp_path, name)


def test_atomic_write_rejects_symlink_escape_from_qualify_directory(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / ".cfdpaper" / "outputs" / "qualify"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlinks are unavailable on this platform: {error}")

    with pytest.raises(ValueError, match="escapes the qualification output directory"):
        write_json_atomic(tmp_path, "qualification-report.json", {"status": "candidate"})

    assert list(outside.iterdir()) == []


def test_canonical_bytes_and_atomic_write_are_deterministic(tmp_path: Path) -> None:
    payload = {"z": 1, "a": [2, 3]}
    expected = b'{"a":[2,3],"z":1}'

    assert canonical_bytes(payload) == expected
    path = write_json_atomic(tmp_path, "qualification-report.json", payload)
    assert path == qualification_report_path(tmp_path)
    assert path.read_bytes() == expected
    assert list(path.parent.glob("*.tmp")) == []
    assert [item for item in tmp_path.rglob("*") if item.is_file()] == [path]


def test_atomic_failure_preserves_previous_artifact_and_removes_temporary(
    tmp_path: Path,
) -> None:
    path = write_json_atomic(tmp_path, "qualification-report.json", {"version": 1})
    original = path.read_bytes()

    with pytest.raises(RuntimeError, match="injected"):
        write_json_atomic(
            tmp_path,
            "qualification-report.json",
            {"version": 2},
            _fail_before_replace=True,
        )

    assert path.read_bytes() == original
    assert list(path.parent.glob("*.tmp")) == []


def test_load_json_model_is_strict_and_rejects_source_hash_mismatch(tmp_path: Path) -> None:
    write_json_atomic(tmp_path, "observation-table.json", _table())
    loaded = load_json_model(
        tmp_path,
        "observation-table.json",
        ObservationTable,
        expected_source_sha256="a" * 64,
    )
    assert loaded == _table()

    with pytest.raises(ArtifactInputMismatch, match="source hash"):
        load_json_model(
            tmp_path,
            "observation-table.json",
            ObservationTable,
            expected_source_sha256="b" * 64,
        )

    payload = json.loads(qualify_artifact_path(tmp_path, "observation-table.json").read_text())
    payload["unexpected"] = True
    qualify_artifact_path(tmp_path, "observation-table.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    with pytest.raises(ValidationError):
        load_json_model(tmp_path, "observation-table.json", ObservationTable)


def test_scientific_fingerprint_is_deterministic_and_binds_unit_registry_identity() -> None:
    first = scientific_input_fingerprint(observation_table=_table())
    second = scientific_input_fingerprint(observation_table=_table())
    changed_version = scientific_input_fingerprint(
        observation_table=_table(), unit_registry_version="different-version"
    )
    changed_digest = scientific_input_fingerprint(
        observation_table=_table(), unit_registry_digest="f" * 64
    )

    assert first == second
    assert len(first) == 64
    assert changed_version != first
    assert changed_digest != first
