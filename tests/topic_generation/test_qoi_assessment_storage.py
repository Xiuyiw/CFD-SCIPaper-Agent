from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from pydantic import ValidationError

from cfdpaper.contracts import EvidenceRecord, QoIRecord
from cfdpaper.indexing import ProjectIndexer
from cfdpaper.state import initialize_project
from cfdpaper.storage import ProjectStore
from cfdpaper.topic_generation.models import (
    QoIDefinitionAssessmentRecord,
    make_qoi_definition_assessment,
)

SOURCE_URI = "definitions.json"
SOURCE_LOCATOR = "$.qois[0]"


def _assessment(
    source_hash: str,
    *,
    qoi_id: str = "qoi-pressure-drop",
    evidence_ids: tuple[str, ...] = ("evidence-pressure-drop",),
    name: str = "Total pressure loss",
    unit: str = "Pa",
    formula: str = "p_total,in - p_total,out",
    source_uri: str = SOURCE_URI,
    source_locator: str = SOURCE_LOCATOR,
) -> QoIDefinitionAssessmentRecord:
    return make_qoi_definition_assessment(
        qoi_id=qoi_id,
        provenance_kind="structured-import",
        source_uri=source_uri,
        source_hash=source_hash,
        source_locator=source_locator,
        evidence_ids=evidence_ids,
        name=name,
        unit=unit,
        formula=formula,
        spatial_scope="inlet and outlet planes",
        reduction="area-weighted mean difference",
        temporal_scope="steady state",
        producer_version="definitions-importer 1.0",
    )


def _save_qoi_and_evidence(
    store: ProjectStore,
    source_hash: str,
    *,
    qoi_id: str = "qoi-pressure-drop",
    evidence_id: str = "evidence-pressure-drop",
    name: str = "Total pressure loss",
    unit: str | None = "Pa",
    locator: str = SOURCE_LOCATOR,
    evidence_kind: str = "qoi",
    evidence_stale: bool = False,
) -> None:
    store.save_qoi(
        QoIRecord(
            qoi_id=qoi_id,
            case_id="case-a",
            name=name,
            value=12.0,
            unit=unit,
            definition=(
                "formula=p_total,in-p_total,out; scope=inlet/outlet; "
                "reduction=area mean; time=steady"
            ),
            status="derived",
            source_uri=SOURCE_URI,
            locator=locator,
        )
    )
    store.save_evidence(
        EvidenceRecord(
            evidence_id=evidence_id,
            source_uri=SOURCE_URI,
            locator=locator,
            kind=evidence_kind,
            summary=f"Structured evidence for {qoi_id}.",
            stale=evidence_stale,
        )
    )


def prepared_qoi_store(
    tmp_path: Path,
    *,
    qoi_unit: str | None = "Pa",
    assessment_unit: str = "Pa",
) -> tuple[ProjectStore, QoIDefinitionAssessmentRecord, Path]:
    source = tmp_path / SOURCE_URI
    source.write_text('{"qois": [{"pressure_drop_pa": 12.0}]}\n', encoding="utf-8")
    initialize_project(tmp_path, "qoi-assessments")
    store = ProjectStore.open(tmp_path)
    ProjectIndexer(store).inspect()
    source_hash = store.get_source(SOURCE_URI).sha256
    _save_qoi_and_evidence(store, source_hash, unit=qoi_unit)
    return store, _assessment(source_hash, unit=assessment_unit), source


def test_qoi_assessment_save_is_idempotent_and_reopens_in_order(tmp_path: Path) -> None:
    store, _, _ = prepared_qoi_store(tmp_path)
    source_hash = store.get_source(SOURCE_URI).sha256
    record_z = _assessment(
        source_hash,
        qoi_id="qoi-z",
        evidence_ids=("evidence-z",),
    )
    _save_qoi_and_evidence(
        store,
        source_hash,
        qoi_id="qoi-z",
        evidence_id="evidence-z",
    )
    record_a = _assessment(
        source_hash,
        qoi_id="qoi-a",
        evidence_ids=("evidence-a",),
        source_locator="$.qois[1]",
    )
    _save_qoi_and_evidence(
        store,
        source_hash,
        qoi_id="qoi-a",
        evidence_id="evidence-a",
        locator="$.qois[1]",
    )

    store.save_qoi_definition_assessment(record_z)
    with store.connect() as connection:
        before = tuple(
            connection.execute(
                "SELECT rowid, qoi_id, definition_id, record_json "
                "FROM qoi_definition_assessments ORDER BY qoi_id, definition_id"
            ).fetchall()
        )
    store.save_qoi_definition_assessment(record_z)
    store.save_qoi_definition_assessment(record_a)
    with store.connect() as connection:
        after = tuple(
            connection.execute(
                "SELECT rowid, qoi_id, definition_id, record_json "
                "FROM qoi_definition_assessments WHERE qoi_id = 'qoi-z'"
            ).fetchall()
        )

    reopened = ProjectStore.open(tmp_path).list_qoi_definition_assessments()

    assert before == after
    assert isinstance(reopened, tuple)
    assert reopened == tuple(sorted(reopened, key=lambda item: (item.qoi_id, item.definition_id)))
    assert reopened == (record_a, record_z)


def test_unequal_save_for_same_qoi_fails_without_overwrite(tmp_path: Path) -> None:
    store, original, _ = prepared_qoi_store(tmp_path)
    replacement = _assessment(original.source_hash, formula="p_static,in - p_static,out")
    store.save_qoi_definition_assessment(original)

    with pytest.raises(RuntimeError, match="unequal QoI definition overwrite"):
        store.save_qoi_definition_assessment(replacement)

    assert store.list_qoi_definition_assessments() == (original,)


def test_qoi_assessment_cas_replaces_only_expected_definition(tmp_path: Path) -> None:
    store, original, _ = prepared_qoi_store(tmp_path)
    replacement = _assessment(original.source_hash, formula="p_total,in - p_static,out")
    stale_writer = _assessment(original.source_hash, formula="p_static,in - p_total,out")
    store.save_qoi_definition_assessment(original)

    store.replace_qoi_definition_assessment(
        replacement, expected_definition_id=original.definition_id
    )
    with pytest.raises(RuntimeError, match="stale QoI definition identity"):
        store.replace_qoi_definition_assessment(
            stale_writer, expected_definition_id=original.definition_id
        )

    assert store.list_qoi_definition_assessments() == (replacement,)


def test_qoi_assessment_rejects_free_text_substitute_and_bad_binding(tmp_path: Path) -> None:
    store, record, _ = prepared_qoi_store(tmp_path)

    assert store.list_qoi_definition_assessments() == ()
    wrong_binding = _assessment(record.source_hash, source_locator="$.qois[999]")
    with pytest.raises(RuntimeError, match="definition evidence binding"):
        store.save_qoi_definition_assessment(wrong_binding)
    assert store.list_qoi_definition_assessments() == ()


def test_qoi_assessment_cas_transaction_failure_preserves_old_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, original, _ = prepared_qoi_store(tmp_path)
    replacement = _assessment(original.source_hash, formula="p_total,in - p_static,out")
    store.save_qoi_definition_assessment(original)

    def fail_replace(
        connection: sqlite3.Connection,
        record: QoIDefinitionAssessmentRecord,
        payload: str,
    ) -> None:
        raise sqlite3.OperationalError("injected replacement failure")

    monkeypatch.setattr(store, "_replace_qoi_definition_row", fail_replace)
    with pytest.raises(sqlite3.OperationalError, match="injected replacement failure"):
        store.replace_qoi_definition_assessment(
            replacement, expected_definition_id=original.definition_id
        )

    assert store.list_qoi_definition_assessments() == (original,)


def test_qoi_assessment_cas_has_exactly_one_winner_under_sixteen_writers(
    tmp_path: Path,
) -> None:
    store, original, _ = prepared_qoi_store(tmp_path)
    store.save_qoi_definition_assessment(original)
    writer_count = 16
    barrier = threading.Barrier(writer_count)
    candidates = tuple(
        _assessment(original.source_hash, formula=f"p_total,in - p_total,out + {index} Pa")
        for index in range(writer_count)
    )

    def attempt(candidate: QoIDefinitionAssessmentRecord) -> tuple[str, str]:
        barrier.wait()
        try:
            store.replace_qoi_definition_assessment(
                candidate, expected_definition_id=original.definition_id
            )
        except RuntimeError as error:
            assert str(error) == "stale QoI definition identity"
            return "stale", candidate.definition_id
        return "saved", candidate.definition_id

    with ThreadPoolExecutor(max_workers=writer_count) as executor:
        outcomes = tuple(executor.map(attempt, candidates))

    winners = [definition_id for outcome, definition_id in outcomes if outcome == "saved"]
    assert len(winners) == 1
    [stored] = store.list_qoi_definition_assessments()
    assert stored.definition_id == winners[0]
    assert sum(outcome == "stale" for outcome, _ in outcomes) == writer_count - 1


def test_qoi_assessment_rejects_unknown_qoi_without_partial_row(tmp_path: Path) -> None:
    store, record, _ = prepared_qoi_store(tmp_path)
    unknown = _assessment(record.source_hash, qoi_id="qoi-unknown")

    with pytest.raises(RuntimeError, match="unknown qoi"):
        store.save_qoi_definition_assessment(unknown)

    assert store.list_qoi_definition_assessments() == ()


def test_qoi_assessment_rejects_name_mismatch_without_partial_row(tmp_path: Path) -> None:
    store, record, _ = prepared_qoi_store(tmp_path)
    mismatch = _assessment(record.source_hash, name="Static pressure loss")

    with pytest.raises(RuntimeError, match="QoI definition name mismatch"):
        store.save_qoi_definition_assessment(mismatch)

    assert store.list_qoi_definition_assessments() == ()


@pytest.mark.parametrize(
    ("qoi_unit", "assessment_unit"),
    [("W/m^2", "W/m2"), ("W/m³", "W/m3"), ("kg/m^3", "kg/m3"), ("°C", "degC")],
)
def test_qoi_assessment_accepts_explicit_canonical_unit_aliases(
    tmp_path: Path, qoi_unit: str, assessment_unit: str
) -> None:
    store, record, _ = prepared_qoi_store(
        tmp_path, qoi_unit=qoi_unit, assessment_unit=assessment_unit
    )

    store.save_qoi_definition_assessment(record)

    assert store.list_qoi_definition_assessments() == (record,)


@pytest.mark.parametrize(
    ("qoi_unit", "assessment_unit"),
    [("kPa", "Pa"), (None, "Pa"), ("rpm", "rpm"), ("Pa", "rpm")],
)
def test_qoi_assessment_rejects_mismatched_missing_or_unknown_units(
    tmp_path: Path, qoi_unit: str | None, assessment_unit: str
) -> None:
    store, record, _ = prepared_qoi_store(
        tmp_path, qoi_unit=qoi_unit, assessment_unit=assessment_unit
    )

    with pytest.raises(RuntimeError, match="QoI definition unit mismatch"):
        store.save_qoi_definition_assessment(record)

    assert store.list_qoi_definition_assessments() == ()


def test_qoi_assessment_rejects_missing_evidence_without_partial_row(tmp_path: Path) -> None:
    store, record, _ = prepared_qoi_store(tmp_path)
    missing = _assessment(
        record.source_hash,
        evidence_ids=("evidence-pressure-drop", "evidence-missing"),
    )

    with pytest.raises(RuntimeError, match="QoI definition evidence missing"):
        store.save_qoi_definition_assessment(missing)

    assert store.list_qoi_definition_assessments() == ()


def test_qoi_assessment_validates_every_evidence_record_is_current(tmp_path: Path) -> None:
    store, record, _ = prepared_qoi_store(tmp_path)
    store.save_evidence(
        EvidenceRecord(
            evidence_id="evidence-stale-auxiliary",
            source_uri=SOURCE_URI,
            locator="$.notes[0]",
            kind="other",
            summary="Auxiliary but stale evidence.",
            stale=True,
        )
    )
    record = _assessment(
        record.source_hash,
        evidence_ids=("evidence-pressure-drop", "evidence-stale-auxiliary"),
    )

    with pytest.raises(RuntimeError, match="QoI definition evidence stale or version mismatch"):
        store.save_qoi_definition_assessment(record)

    assert store.list_qoi_definition_assessments() == ()


def test_qoi_assessment_rejects_evidence_version_mismatch(tmp_path: Path) -> None:
    store, record, _ = prepared_qoi_store(tmp_path)
    with store.connect() as connection:
        connection.execute(
            "UPDATE evidence SET source_version_hash = ? WHERE evidence_id = ?",
            ("0" * 64, "evidence-pressure-drop"),
        )

    with pytest.raises(RuntimeError, match="QoI definition evidence stale or version mismatch"):
        store.save_qoi_definition_assessment(record)

    assert store.list_qoi_definition_assessments() == ()


def test_qoi_assessment_rejects_evidence_from_stale_source(tmp_path: Path) -> None:
    store, record, _ = prepared_qoi_store(tmp_path)
    with store.connect() as connection:
        connection.execute("UPDATE sources SET stale = 1 WHERE uri = ?", (SOURCE_URI,))

    with pytest.raises(RuntimeError, match="QoI definition evidence stale or version mismatch"):
        store.save_qoi_definition_assessment(record)

    assert store.list_qoi_definition_assessments() == ()


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"source_uri": "other.json"}, "QoI definition source URI mismatch"),
        ({"source_hash": "0" * 64}, "QoI definition source hash mismatch"),
    ],
)
def test_qoi_assessment_rejects_source_identity_mismatch(
    tmp_path: Path, changes: dict[str, str], message: str
) -> None:
    store, record, _ = prepared_qoi_store(tmp_path)
    mismatched = make_qoi_definition_assessment(
        **{
            **record.model_dump(mode="python", exclude={"definition_id", "schema_version"}),
            **changes,
        }
    )

    with pytest.raises(RuntimeError, match=message):
        store.save_qoi_definition_assessment(mismatched)

    assert store.list_qoi_definition_assessments() == ()


def test_qoi_assessment_accepts_exact_qoi_binding_with_current_auxiliary_evidence(
    tmp_path: Path,
) -> None:
    store, record, _ = prepared_qoi_store(tmp_path)
    store.save_evidence(
        EvidenceRecord(
            evidence_id="evidence-auxiliary",
            source_uri=SOURCE_URI,
            locator="$.notes[0]",
            kind="other",
            summary="Current auxiliary evidence.",
        )
    )
    record = _assessment(
        record.source_hash,
        evidence_ids=("evidence-pressure-drop", "evidence-auxiliary"),
    )

    store.save_qoi_definition_assessment(record)

    assert store.list_qoi_definition_assessments() == (record,)


@pytest.mark.parametrize("field", ["definition_id", "schema_version"])
def test_qoi_assessment_strictly_revalidates_identity_and_schema(
    tmp_path: Path, field: str
) -> None:
    store, record, _ = prepared_qoi_store(tmp_path)
    invalid_value: object = "0" * 64 if field == "definition_id" else 2
    invalid = record.model_copy(update={field: invalid_value})

    with pytest.raises(ValidationError):
        store.save_qoi_definition_assessment(invalid)

    assert store.list_qoi_definition_assessments() == ()


def test_qoi_assessment_cas_rejects_missing_row(tmp_path: Path) -> None:
    store, record, _ = prepared_qoi_store(tmp_path)

    with pytest.raises(RuntimeError, match="stale QoI definition identity"):
        store.replace_qoi_definition_assessment(record, expected_definition_id="f" * 64)

    assert store.list_qoi_definition_assessments() == ()


def test_qoi_assessment_migration_has_required_constraints(tmp_path: Path) -> None:
    store, _, _ = prepared_qoi_store(tmp_path)

    with store.connect() as connection:
        columns = tuple(
            (row[1], row[2], row[3], row[5])
            for row in connection.execute("PRAGMA table_info(qoi_definition_assessments)")
        )
        unique_indexes = tuple(
            row[1]
            for row in connection.execute("PRAGMA index_list(qoi_definition_assessments)")
            if row[2]
        )

    assert columns == (
        ("qoi_id", "TEXT", 0, 1),
        ("definition_id", "TEXT", 1, 0),
        ("record_json", "TEXT", 1, 0),
    )
    assert unique_indexes
