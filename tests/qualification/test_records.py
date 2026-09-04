from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from cfdpaper.qualification.records import (
    GuidedRecords,
    load_guided_records,
    persist_guided_records,
)
from cfdpaper.state import initialize_project
from cfdpaper.storage import ProjectStore


def _payload() -> dict[str, object]:
    source = {
        "source_uri": "results.csv",
        "locator": "results.csv",
        "sha256": "a" * 64,
        "mtime_ns": 1,
        "size_bytes": 12,
        "media_type": "text/csv",
    }
    return {
        "cases": [
            {
                "case_id": "P1",
                "source_uri": "results.csv",
                "locator": "results.csv#case=P1",
                "solver": "STAR-CCM+",
                "solver_version": "18",
                "state": "extracted",
            }
        ],
        "boundaries": [
            {
                "boundary_id": "boundary-P1",
                "case_id": "P1",
                "source_uri": "results.csv",
                "locator": "results.csv#boundary=P1",
                "boundary_type": "velocity-inlet",
                "values": {"mean_velocity": 0.25},
                "units": {"mean_velocity": "m/s"},
                "comparison_role": "intended-study-factor",
            }
        ],
        "models": [
            {
                "model_id": "model-P1",
                "case_id": "P1",
                "source_uri": "results.csv",
                "locator": "results.csv#model=P1",
                "description": "steady laminar flow",
                "comparison_role": "demonstrated-equivalent-or-immaterial",
                "basis": "same model in all cases",
                "verification_status": "demonstrated",
                "verification_basis": "analytic pressure-drop comparison",
                "verification_locator": "results.csv#verification=P1",
                "validation_status": "not-demonstrated",
                "validation_basis": "no external experiment is supplied",
                "validation_locator": "results.csv#validation=P1",
            }
        ],
        "convergence": [
            {
                "evidence_id": "conv-P1",
                "case_id": "P1",
                "source_uri": "results.csv",
                "locator": "results.csv#convergence=P1",
                "metric": "pressure-drop monitor span",
                "observed_value": 0.001,
                "unit": "1",
                "threshold_value": 0.005,
                "operator": "<=",
                "consequence": "restricting",
                "basis": "project convergence criterion",
            }
        ],
        "conservation": [
            {
                "evidence_id": "cons-P1",
                "case_id": "P1",
                "source_uri": "results.csv",
                "locator": "results.csv#conservation=P1",
                "metric": "mass imbalance",
                "observed_value": 0.0001,
                "unit": "1",
                "threshold_value": 0.001,
                "operator": "<=",
                "consequence": "blocking",
                "basis": "project conservation criterion",
            }
        ],
        "sources": [source],
    }


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize("missing", list(_payload()))
def test_records_reject_missing_top_level_key_before_writes(tmp_path: Path, missing: str) -> None:
    path = tmp_path / "project-records.json"
    payload = _payload()
    del payload[missing]
    _write(path, payload)

    with pytest.raises(ValidationError, match=missing):
        load_guided_records(path)


def test_records_reject_unknown_top_level_key(tmp_path: Path) -> None:
    path = tmp_path / "project-records.json"
    payload = _payload()
    payload["approval"] = "not a scientific record"
    _write(path, payload)

    with pytest.raises(ValidationError, match="approval"):
        load_guided_records(path)


def test_records_require_nonblank_identifiers_and_complete_vnv(tmp_path: Path) -> None:
    path = tmp_path / "project-records.json"
    payload = _payload()
    payload["cases"][0]["case_id"] = "   "  # type: ignore[index]
    _write(path, payload)
    with pytest.raises(ValidationError, match="case_id"):
        load_guided_records(path)

    payload = _payload()
    del payload["models"][0]["validation_status"]  # type: ignore[index]
    _write(path, payload)
    with pytest.raises(ValidationError, match="validation_status"):
        load_guided_records(path)


def test_boundary_mappings_are_defensively_copied_frozen_and_json_serializable() -> None:
    payload = _payload()
    values = payload["boundaries"][0]["values"]  # type: ignore[index]
    units = payload["boundaries"][0]["units"]  # type: ignore[index]
    records = GuidedRecords.model_validate(payload)
    boundary = records.boundaries[0]

    values["mean_velocity"] = 99.0
    units["mean_velocity"] = "km/s"

    assert boundary.values == {"mean_velocity": 0.25}
    assert boundary.units == {"mean_velocity": "m/s"}
    with pytest.raises(TypeError):
        boundary.values["mean_velocity"] = 1.0
    with pytest.raises(TypeError):
        boundary.units["mean_velocity"] = "cm/s"
    assert json.loads(boundary.model_dump_json())["values"] == {"mean_velocity": 0.25}


def test_records_reject_duplicate_source_identity(tmp_path: Path) -> None:
    path = tmp_path / "project-records.json"
    payload = _payload()
    payload["sources"].append(dict(payload["sources"][0]))  # type: ignore[union-attr,index]
    _write(path, payload)

    with pytest.raises(ValidationError, match="source_uri"):
        load_guided_records(path)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["boundaries"].append(dict(payload["boundaries"][0])),
        lambda payload: payload["models"].append(dict(payload["models"][0])),
        lambda payload: payload["conservation"][0].update(
            {"evidence_id": payload["convergence"][0]["evidence_id"]}
        ),
        lambda payload: payload["models"][0].update(
            {"model_id": payload["boundaries"][0]["boundary_id"]}
        ),
        lambda payload: payload["convergence"][0].update(
            {"evidence_id": payload["boundaries"][0]["boundary_id"]}
        ),
        lambda payload: payload["conservation"][0].update(
            {"evidence_id": payload["models"][0]["model_id"]}
        ),
        lambda payload: payload["convergence"][0].update(
            {"evidence_id": f"model-{payload['models'][0]['model_id']}"}
        ),
        lambda payload: payload["convergence"][0].update(
            {"evidence_id": f"verification-{payload['models'][0]['model_id']}"}
        ),
        lambda payload: payload["convergence"][0].update(
            {"evidence_id": f"validation-{payload['models'][0]['model_id']}"}
        ),
    ],
    ids=[
        "duplicate-boundary-id",
        "duplicate-model-id",
        "cross-assessment-id",
        "boundary-model-original-id",
        "boundary-evidence-original-id",
        "model-evidence-original-id",
        "mapped-model-id",
        "mapped-verification-id",
        "mapped-validation-id",
    ],
)
def test_record_identity_conflicts_fail_before_any_database_write(
    tmp_path: Path, mutate: Callable[[dict[str, object]], None]
) -> None:
    initialize_project(tmp_path, "demo")
    store = ProjectStore.open(tmp_path)
    payload = _payload()
    mutate(payload)
    path = tmp_path / "project-records.json"
    _write(path, payload)

    with pytest.raises(ValidationError, match="identifier|persistent evidence"):
        records = load_guided_records(path)
        persist_guided_records(store, records)

    assert store.list_sources() == []
    assert store.list_cases() == []
    assert store.list_boundaries() == []
    assert store.list_evidence() == []


def test_complete_envelope_becomes_visible_after_one_atomic_commit(tmp_path: Path) -> None:
    initialize_project(tmp_path, "demo")
    path = tmp_path / "project-records.json"
    _write(path, _payload())
    records = load_guided_records(path)
    store = ProjectStore.open(tmp_path)

    persist_guided_records(store, records)

    assert [record.case_id for record in store.list_cases()] == ["P1"]
    assert [record.boundary_id for record in store.list_boundaries()] == ["boundary-P1"]
    assert {record.evidence_id for record in store.list_evidence()} == {
        "model-model-P1",
        "verification-model-P1",
        "validation-model-P1",
        "conv-P1",
        "cons-P1",
    }
    assert store.get_source("results.csv").sha256 == "a" * 64


def test_validation_failure_writes_no_members_and_preserves_existing_records(
    tmp_path: Path,
) -> None:
    initialize_project(tmp_path, "demo")
    store = ProjectStore.open(tmp_path)
    valid = GuidedRecords.model_validate(_payload())
    persist_guided_records(store, valid)
    invalid_payload = _payload()
    invalid_payload["sources"] = []
    invalid_payload["cases"][0]["case_id"] = "P2"  # type: ignore[index]
    invalid = GuidedRecords.model_validate(invalid_payload)

    with pytest.raises(ValueError, match="declared source"):
        persist_guided_records(store, invalid)

    assert [record.case_id for record in store.list_cases()] == ["P1"]
    assert len(store.list_boundaries()) == 1
    assert len(store.list_evidence()) == 5


def test_mid_write_failure_rolls_back_every_member(tmp_path: Path) -> None:
    initialize_project(tmp_path, "demo")
    store = ProjectStore.open(tmp_path)
    with store.connect() as connection:
        connection.execute(
            "CREATE TRIGGER reject_guided_evidence BEFORE INSERT ON evidence "
            "BEGIN SELECT RAISE(ABORT, 'reject guided evidence'); END"
        )

    with pytest.raises(sqlite3.IntegrityError, match="reject guided evidence"):
        persist_guided_records(store, GuidedRecords.model_validate(_payload()))

    assert store.list_sources() == []
    assert store.list_cases() == []
    assert store.list_boundaries() == []
    assert store.list_evidence() == []


def test_mid_write_failure_preserves_preexisting_rows_byte_for_byte(tmp_path: Path) -> None:
    initialize_project(tmp_path, "demo")
    store = ProjectStore.open(tmp_path)
    persist_guided_records(store, GuidedRecords.model_validate(_payload()))
    with store.connect() as connection:
        connection.execute(
            "CREATE TRIGGER reject_reimported_evidence BEFORE INSERT ON evidence "
            "BEGIN SELECT RAISE(ABORT, 'reject reimported evidence'); END"
        )

    tables = ("sources", "source_versions", "cases", "scientific_records", "evidence")

    def raw_rows() -> dict[str, tuple[tuple[object, ...], ...]]:
        with store.connect() as connection:
            return {
                table: tuple(
                    tuple(row)
                    for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")
                )
                for table in tables
            }

    before = raw_rows()
    replacement = _payload()
    replacement["sources"][0].update(  # type: ignore[index]
        {"sha256": "b" * 64, "mtime_ns": 2, "size_bytes": 24}
    )
    replacement["cases"][0]["solver_version"] = "19"  # type: ignore[index]
    replacement["boundaries"][0]["values"]["mean_velocity"] = 0.75  # type: ignore[index]

    with pytest.raises(sqlite3.IntegrityError, match="reject reimported evidence"):
        persist_guided_records(store, GuidedRecords.model_validate(replacement))

    assert raw_rows() == before
