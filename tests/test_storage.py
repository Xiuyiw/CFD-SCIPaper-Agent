import shutil
import sqlite3
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from pathlib import Path

import pytest

import cfdpaper.storage as storage
from cfdpaper.contracts import BoundaryRecord, CaseRecord, ClaimRecord, EvidenceRecord, StageResult
from cfdpaper.indexing import ProjectIndexer
from cfdpaper.state import initialize_project
from cfdpaper.storage import SCHEMA_VERSION, ProjectStore


def test_import_records_atomic_commits_a_complete_batch(tmp_path: Path) -> None:
    initialize_project(tmp_path, "demo")
    store = ProjectStore.open(tmp_path)

    store.import_records_atomic(
        sources=(
            {
                "uri": "results.csv",
                "locator": "results.csv",
                "sha256": "a" * 64,
                "mtime_ns": 1,
                "size_bytes": 12,
                "media_type": "text/csv",
            },
        ),
        cases=(CaseRecord(case_id="P1", source_uri="results.csv", locator="results.csv#case=P1"),),
        boundaries=(
            BoundaryRecord(
                boundary_id="b-P1",
                case_id="P1",
                boundary_type="velocity-inlet",
                values={"velocity": 0.25},
                units={"velocity": "m/s"},
                source_uri="results.csv",
                locator="results.csv#boundary=P1",
            ),
        ),
        evidence=(
            EvidenceRecord(
                evidence_id="conv-P1",
                source_uri="results.csv",
                locator="results.csv#convergence=P1",
                kind="convergence",
                summary="Monitor span satisfies the declared threshold.",
            ),
        ),
    )

    assert len(store.list_sources()) == 1
    assert len(store.list_cases()) == 1
    assert len(store.list_boundaries()) == 1
    assert len(store.list_evidence()) == 1


def test_import_records_atomic_rolls_back_on_mid_write_failure(tmp_path: Path) -> None:
    initialize_project(tmp_path, "demo")
    store = ProjectStore.open(tmp_path)
    with store.connect() as connection:
        connection.execute(
            "CREATE TRIGGER reject_atomic_evidence BEFORE INSERT ON evidence "
            "BEGIN SELECT RAISE(ABORT, 'reject atomic evidence'); END"
        )

    with pytest.raises(sqlite3.IntegrityError, match="reject atomic evidence"):
        store.import_records_atomic(
            sources=(
                {
                    "uri": "results.csv",
                    "locator": "results.csv",
                    "sha256": "a" * 64,
                    "mtime_ns": 1,
                    "size_bytes": 12,
                    "media_type": "text/csv",
                },
            ),
            cases=(
                CaseRecord(case_id="P1", source_uri="results.csv", locator="results.csv#case=P1"),
            ),
            boundaries=(),
            evidence=(
                EvidenceRecord(
                    evidence_id="conv-P1",
                    source_uri="results.csv",
                    locator="results.csv#convergence=P1",
                    kind="convergence",
                    summary="Monitor span satisfies the declared threshold.",
                ),
            ),
        )

    assert store.list_sources() == []
    assert store.list_cases() == []
    assert store.list_evidence() == []


class _SynchronizedStageCursor:
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        connection: sqlite3.Connection,
        barrier: threading.Barrier,
    ) -> None:
        self._cursor = cursor
        self._connection = connection
        self._barrier = barrier

    def fetchone(self) -> sqlite3.Row | None:
        row = self._cursor.fetchone()
        if row is None and not self._connection.in_transaction:
            self._barrier.wait(timeout=10)
        return row


class _SynchronizedStageConnection:
    def __init__(self, connection: sqlite3.Connection, barrier: threading.Barrier) -> None:
        self._connection = connection
        self._barrier = barrier

    def execute(
        self, sql: str, parameters: tuple[object, ...] = ()
    ) -> sqlite3.Cursor | _SynchronizedStageCursor:
        cursor = self._connection.execute(sql, parameters)
        if sql.startswith("SELECT status, outputs_json, approved_by FROM stages"):
            return _SynchronizedStageCursor(cursor, self._connection, self._barrier)
        return cursor


def _synchronize_first_stage_reads(
    monkeypatch: pytest.MonkeyPatch, barrier: threading.Barrier
) -> None:
    original_connect = ProjectStore.connect

    @contextmanager
    def synchronized_connect(self: ProjectStore) -> Iterator[_SynchronizedStageConnection]:
        with original_connect(self) as connection:
            yield _SynchronizedStageConnection(connection, barrier)

    monkeypatch.setattr(ProjectStore, "connect", synchronized_connect)


def test_initialization_migrates_all_phase2_tables(tmp_path: Path) -> None:
    initialize_project(tmp_path, "demo")

    with closing(sqlite3.connect(tmp_path / ".cfdpaper" / "project.db")) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        schema_version = connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0]

    assert {
        "sources",
        "source_versions",
        "cases",
        "evidence",
        "claims",
        "claim_evidence",
        "stages",
        "chunks",
        "chunks_fts",
        "checkpoints",
        "scientific_records",
        "qoi_definition_assessments",
        "scientific_assessment_state",
    } <= tables
    assert schema_version == SCHEMA_VERSION == 6


def test_store_connection_context_explicitly_closes_for_windows_cleanup(tmp_path: Path) -> None:
    project = tmp_path / "closable"
    project.mkdir()
    initialize_project(project, "demo")
    store = ProjectStore.open(project)

    with store.connect() as connection:
        assert connection.execute("SELECT 1").fetchone()[0] == 1

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("SELECT 1")
    shutil.rmtree(project)
    assert not project.exists()


def test_store_migrates_an_existing_v1_database(tmp_path: Path) -> None:
    state_dir = tmp_path / ".cfdpaper"
    state_dir.mkdir()
    database = state_dir / "project.db"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "CREATE TABLE project_state "
            "(project_id TEXT PRIMARY KEY, stage TEXT NOT NULL, manifest_json TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO project_state VALUES ('legacy', 'initialized', '{}')")
        connection.commit()

    store = ProjectStore.open(tmp_path)

    assert store.schema_version >= 2
    assert store.status().project_id == "legacy"


def test_v010_schema3_project_migrates_to_v020_without_losing_state(tmp_path: Path) -> None:
    initialize_project(tmp_path, "legacy-v010")
    source = tmp_path / "results.csv"
    source.write_text("case,value\nreference,1.0\n", encoding="utf-8")
    store = ProjectStore.open(tmp_path)
    ProjectIndexer(store).inspect()
    store.set_stage("planned", {"source": "v0.1.0"})
    store.save_checkpoint("plan", {"source": "v0.1.0"})

    with store.connect() as connection:
        connection.execute("DROP TABLE scientific_assessment_state")
        connection.execute("DROP TABLE qoi_definition_assessments")
        connection.execute("DROP TABLE scientific_records")
        connection.execute("DELETE FROM schema_migrations WHERE version >= 4")

    migrated = ProjectStore.open(tmp_path)
    status = migrated.status()

    assert migrated.schema_version == SCHEMA_VERSION == 6
    assert status.project_id == "legacy-v010"
    assert status.stage == "planned"
    assert status.source_count == 1
    assert status.latest_checkpoint == "plan"


def test_structured_records_are_persisted_with_evidence_links(tmp_path: Path) -> None:
    initialize_project(tmp_path, "demo")
    source = tmp_path / "results.csv"
    source.write_text("case,dp\nA,12\n", encoding="utf-8")
    store = ProjectStore.open(tmp_path)

    ProjectIndexer(store).inspect()
    store.save_case(
        CaseRecord(
            case_id="case-a",
            source_uri="results.csv",
            locator="row:2",
            solver="Fluent",
        )
    )
    store.save_evidence(
        EvidenceRecord(
            evidence_id="ev-a",
            source_uri="results.csv",
            locator="row:2,column:dp",
            kind="qoi",
            summary="Pressure drop is 12 Pa.",
        )
    )
    store.save_claim(
        ClaimRecord(
            claim_id="claim-a",
            text="Case A pressure drop is 12 Pa.",
            status="supported",
            evidence_ids=["ev-a"],
        )
    )
    store.save_stage(StageResult(stage="inspect", status="complete", outputs={"sources": 1}))

    claims = store.list_claims(source_ids=[store.get_source("results.csv").source_id])
    with store.connect() as connection:
        case_count = connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        evidence_count = connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]

    assert case_count == 1
    assert evidence_count == 1
    assert claims == [
        ClaimRecord(
            claim_id="claim-a",
            text="Case A pressure drop is 12 Pa.",
            status="supported",
            evidence_ids=["ev-a"],
        )
    ]


def test_evidence_and_cases_keep_their_source_version_provenance(tmp_path: Path) -> None:
    initialize_project(tmp_path, "demo")
    source = tmp_path / "results.csv"
    source.write_text("case,dp\nA,12\n", encoding="utf-8")
    store = ProjectStore.open(tmp_path)
    ProjectIndexer(store).inspect()
    version_1 = store.get_source("results.csv")
    store.save_case(CaseRecord(case_id="case-a", source_uri="results.csv", locator="row:2"))
    store.save_evidence(
        EvidenceRecord(
            evidence_id="ev-a",
            source_uri="results.csv",
            locator="row:2,column:dp",
            kind="qoi",
            summary="Pressure drop is 12 Pa.",
        )
    )
    source.write_text("case,dp\nA,10\n", encoding="utf-8")
    ProjectIndexer(store, strict_hash=True).inspect()
    version_2 = store.get_source("results.csv")

    evidence = store.list_evidence()[0]
    case = store.list_cases()[0]

    assert version_1.sha256 != version_2.sha256
    assert evidence.source_hash == version_1.sha256
    assert evidence.stale is True
    assert case.source_hash == version_1.sha256
    assert case.stale is True


def test_migrations_are_atomic_under_sixteen_concurrent_openers(tmp_path: Path) -> None:
    state_dir = tmp_path / ".cfdpaper"
    state_dir.mkdir()
    database = state_dir / "project.db"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "CREATE TABLE project_state "
            "(project_id TEXT PRIMARY KEY, stage TEXT NOT NULL, manifest_json TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO project_state VALUES ('demo', 'initialized', '{}')")
        connection.execute(
            "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO schema_migrations VALUES (1, 'earlier')")
        connection.commit()
    barrier = threading.Barrier(16)

    def migrate_in_thread() -> int:
        barrier.wait()
        return ProjectStore.open(tmp_path).schema_version

    with ThreadPoolExecutor(max_workers=16) as executor:
        versions = list(executor.map(lambda _: migrate_in_thread(), range(16)))

    with closing(sqlite3.connect(database)) as connection:
        migration_rows = connection.execute(
            "SELECT version, COUNT(*) FROM schema_migrations GROUP BY version ORDER BY version"
        ).fetchall()
    assert versions == [6] * 16
    assert migration_rows == [(1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1)]


def test_v2_to_v3_marks_unrecoverable_record_versions_unknown_and_stale(
    tmp_path: Path,
) -> None:
    initialize_project(tmp_path, "demo")
    source = tmp_path / "results.csv"
    source.write_text("case,dp\nA,12\n", encoding="utf-8")
    store = ProjectStore.open(tmp_path)
    ProjectIndexer(store).inspect()
    store.save_case(CaseRecord(case_id="case-a", source_uri="results.csv", locator="row:2"))
    store.save_evidence(
        EvidenceRecord(
            evidence_id="ev-a",
            source_uri="results.csv",
            locator="row:2,column:dp",
            kind="qoi",
            summary="Historical pressure drop.",
        )
    )
    source.write_text("case,dp\nA,10\n", encoding="utf-8")
    ProjectIndexer(store, strict_hash=True).inspect()
    assert store.source_version_count(store.get_source("results.csv").source_id) == 2

    with store.connect() as connection:
        connection.execute("DROP INDEX idx_cases_source_version")
        connection.execute("DROP INDEX idx_evidence_source_version")
        connection.execute("ALTER TABLE cases DROP COLUMN source_version_hash")
        connection.execute("ALTER TABLE evidence DROP COLUMN source_version_hash")
        connection.execute("DELETE FROM schema_migrations WHERE version=3")

    migrated = ProjectStore.open(tmp_path)
    case = migrated.list_cases()[0]
    evidence = migrated.list_evidence()[0]

    assert case.source_hash == "UNKNOWN"
    assert case.stale is True
    assert evidence.source_hash == "UNKNOWN"
    assert evidence.stale is True


def test_repeated_init_rejects_a_different_project_identity(tmp_path: Path) -> None:
    initialize_project(tmp_path, "first")

    with pytest.raises(ValueError, match="already initialized.*first"):
        initialize_project(tmp_path, "second")

    assert ProjectStore.open(tmp_path).status().project_id == "first"


def test_set_stage_refuses_ambiguous_project_rows(tmp_path: Path) -> None:
    initialize_project(tmp_path, "first")
    store = ProjectStore.open(tmp_path)
    with store.connect() as connection:
        connection.execute("INSERT INTO project_state VALUES ('rogue', 'initialized', '{}')")

    with pytest.raises(RuntimeError, match="exactly one project"):
        store.set_stage("inspect")

    with store.connect() as connection:
        stages = dict(connection.execute("SELECT project_id, stage FROM project_state"))
    assert stages == {"first": "initialized", "rogue": "initialized"}


def test_save_workflow_transition_persists_stage_project_and_checkpoint(
    tmp_path: Path,
) -> None:
    initialize_project(tmp_path, "demo")
    store = ProjectStore.open(tmp_path)
    checkpoint_id = store.save_workflow_transition(
        StageResult(stage="plan", status="complete", outputs={"outcome": "analysis-note"}),
        project_stage="planned",
        checkpoint_id="plan-checkpoint-1",
        checkpoint_stage="plan",
        checkpoint_payload={"outcome": "analysis-note"},
    )

    checkpoint = store.resume_checkpoint(checkpoint_id)
    with store.connect() as connection:
        stage = connection.execute(
            "SELECT status, outputs_json FROM stages WHERE stage = 'plan'"
        ).fetchone()

    assert checkpoint_id == "plan-checkpoint-1"
    assert store.status().stage == "planned"
    assert checkpoint.stage == "plan"
    assert checkpoint.payload == {"outcome": "analysis-note"}
    assert stage is not None
    assert stage["status"] == "complete"
    assert stage["outputs_json"] == '{"outcome": "analysis-note"}'


def test_save_workflow_transition_reuses_an_identical_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize_project(tmp_path, "demo")
    store = ProjectStore.open(tmp_path)
    record = StageResult(stage="plan", status="complete", outputs={"outcome": "analysis-note"})
    arguments = {
        "project_stage": "planned",
        "checkpoint_id": "plan-checkpoint-1",
        "checkpoint_stage": "plan",
        "checkpoint_payload": {"outcome": "analysis-note"},
    }
    timestamps = iter(["2026-08-29T00:00:01+00:00", "2026-08-29T00:00:02+00:00"])
    monkeypatch.setattr(storage, "_utc_now", lambda: next(timestamps))

    store.save_workflow_transition(record, **arguments)
    with store.connect() as connection:
        first_timestamps = connection.execute(
            "SELECT s.updated_at, c.created_at FROM stages s CROSS JOIN checkpoints c "
            "WHERE s.stage = 'plan' AND c.checkpoint_id = 'plan-checkpoint-1'"
        ).fetchone()
    store.save_workflow_transition(record, **arguments)
    with store.connect() as connection:
        second_timestamps = connection.execute(
            "SELECT s.updated_at, c.created_at FROM stages s CROSS JOIN checkpoints c "
            "WHERE s.stage = 'plan' AND c.checkpoint_id = 'plan-checkpoint-1'"
        ).fetchone()
        checkpoint_count = connection.execute(
            "SELECT COUNT(*) FROM checkpoints WHERE checkpoint_id = ?",
            ("plan-checkpoint-1",),
        ).fetchone()[0]

    assert tuple(first_timestamps) == (
        "2026-08-29T00:00:01+00:00",
        "2026-08-29T00:00:01+00:00",
    )
    assert tuple(second_timestamps) == tuple(first_timestamps)
    assert checkpoint_count == 1


def test_save_workflow_transition_serializes_identical_first_writers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize_project(tmp_path, "demo")
    store = ProjectStore.open(tmp_path)
    writer_count = 16
    barrier = threading.Barrier(writer_count)
    _synchronize_first_stage_reads(monkeypatch, barrier)
    record = StageResult(stage="plan", status="complete", outputs={"outcome": "analysis-note"})
    arguments = {
        "project_stage": "planned",
        "checkpoint_id": "plan-checkpoint-1",
        "checkpoint_stage": "plan",
        "checkpoint_payload": {"outcome": "analysis-note"},
    }

    with ThreadPoolExecutor(max_workers=writer_count) as executor:
        checkpoint_ids = list(
            executor.map(
                lambda _: store.save_workflow_transition(record, **arguments),
                range(writer_count),
            )
        )

    with store.connect() as connection:
        first_state = connection.execute(
            "SELECT s.updated_at, c.created_at, "
            "(SELECT COUNT(*) FROM stages WHERE stage = 'plan'), "
            "(SELECT COUNT(*) FROM checkpoints WHERE checkpoint_id = 'plan-checkpoint-1') "
            "FROM stages s CROSS JOIN checkpoints c "
            "WHERE s.stage = 'plan' AND c.checkpoint_id = 'plan-checkpoint-1'"
        ).fetchone()
    store.save_workflow_transition(record, **arguments)
    with store.connect() as connection:
        final_timestamps = connection.execute(
            "SELECT s.updated_at, c.created_at FROM stages s CROSS JOIN checkpoints c "
            "WHERE s.stage = 'plan' AND c.checkpoint_id = 'plan-checkpoint-1'"
        ).fetchone()

    assert checkpoint_ids == ["plan-checkpoint-1"] * writer_count
    assert tuple(first_state[2:]) == (1, 1)
    assert tuple(final_timestamps) == tuple(first_state[:2])


def test_save_workflow_transition_serializes_conflicting_checkpoint_payloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize_project(tmp_path, "demo")
    store = ProjectStore.open(tmp_path)
    versions = [1, 2] * 8
    _synchronize_first_stage_reads(monkeypatch, threading.Barrier(len(versions)))

    def attempt_transition(version: int) -> tuple[str, int]:
        try:
            store.save_workflow_transition(
                StageResult(stage="plan", status="complete", outputs={"version": version}),
                project_stage=f"planned-{version}",
                checkpoint_id="plan-checkpoint-1",
                checkpoint_stage="plan",
                checkpoint_payload={"version": version},
            )
        except RuntimeError as error:
            assert str(error) == "deterministic checkpoint ID collision"
            return "collision", version
        return "saved", version

    with ThreadPoolExecutor(max_workers=len(versions)) as executor:
        outcomes = list(executor.map(attempt_transition, versions))

    saved_versions = {version for outcome, version in outcomes if outcome == "saved"}
    assert len(saved_versions) == 1
    winning_version = saved_versions.pop()
    assert outcomes.count(("saved", winning_version)) == 8
    assert outcomes.count(("collision", 3 - winning_version)) == 8
    with store.connect() as connection:
        stage = connection.execute(
            "SELECT outputs_json FROM stages WHERE stage = 'plan'"
        ).fetchone()
        row_counts = connection.execute(
            "SELECT (SELECT COUNT(*) FROM stages WHERE stage = 'plan'), "
            "(SELECT COUNT(*) FROM checkpoints WHERE checkpoint_id = 'plan-checkpoint-1')"
        ).fetchone()
    assert store.status().stage == f"planned-{winning_version}"
    assert stage["outputs_json"] == f'{{"version": {winning_version}}}'
    assert store.resume_checkpoint("plan-checkpoint-1").payload == {"version": winning_version}
    assert tuple(row_counts) == (1, 1)


def test_save_workflow_transition_collision_rolls_back_stage_and_project(
    tmp_path: Path,
) -> None:
    initialize_project(tmp_path, "demo")
    store = ProjectStore.open(tmp_path)
    store.save_workflow_transition(
        StageResult(stage="plan", status="complete", outputs={"version": 1}),
        project_stage="planned",
        checkpoint_id="plan-checkpoint-1",
        checkpoint_stage="plan",
        checkpoint_payload={"version": 1},
    )
    with store.connect() as connection:
        original_stage = connection.execute(
            "SELECT status, outputs_json, approved_by, updated_at FROM stages WHERE stage = 'plan'"
        ).fetchone()

    with pytest.raises(RuntimeError, match="^deterministic checkpoint ID collision$"):
        store.save_workflow_transition(
            StageResult(stage="plan", status="blocked", outputs={"version": 2}),
            project_stage="must-roll-back",
            checkpoint_id="plan-checkpoint-1",
            checkpoint_stage="plan",
            checkpoint_payload={"version": 2},
        )

    with store.connect() as connection:
        final_stage = connection.execute(
            "SELECT status, outputs_json, approved_by, updated_at FROM stages WHERE stage = 'plan'"
        ).fetchone()
        checkpoint_count = connection.execute(
            "SELECT COUNT(*) FROM checkpoints WHERE checkpoint_id = 'plan-checkpoint-1'"
        ).fetchone()[0]
    assert tuple(final_stage) == tuple(original_stage)
    assert store.status().stage == "planned"
    assert store.resume_checkpoint("plan-checkpoint-1").payload == {"version": 1}
    assert checkpoint_count == 1


def test_save_workflow_transition_rolls_back_all_changes_on_checkpoint_failure(
    tmp_path: Path,
) -> None:
    initialize_project(tmp_path, "demo")
    store = ProjectStore.open(tmp_path)
    with store.connect() as connection:
        connection.execute(
            "CREATE TRIGGER reject_plan_checkpoint "
            "BEFORE INSERT ON checkpoints WHEN NEW.stage = 'plan' "
            "BEGIN SELECT RAISE(ABORT, 'reject plan'); END"
        )

    with pytest.raises(sqlite3.IntegrityError, match="reject plan"):
        store.save_workflow_transition(
            StageResult(stage="plan", status="complete", outputs={"outcome": "analysis-note"}),
            project_stage="planned",
            checkpoint_id="plan-checkpoint-1",
            checkpoint_stage="plan",
            checkpoint_payload={"outcome": "analysis-note"},
        )

    with store.connect() as connection:
        plan_stage_count = connection.execute(
            "SELECT COUNT(*) FROM stages WHERE stage = 'plan'"
        ).fetchone()[0]
    assert store.status().stage == "initialized"
    assert plan_stage_count == 0
