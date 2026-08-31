"""SQLite persistence and migrations for the project knowledge layer."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid4, uuid5

from pydantic import BaseModel

from cfdpaper.contracts import (
    BoundaryRecord,
    CaseRecord,
    ClaimRecord,
    EvidenceRecord,
    FieldRecord,
    MeshRecord,
    QoIRecord,
    StageResult,
)
from cfdpaper.scientific.units import canonical_unit
from cfdpaper.topic_generation.canonical import canonical_json_bytes
from cfdpaper.topic_generation.models import QoIDefinitionAssessmentRecord
from cfdpaper.topic_generation.snapshot import ScientificAssessmentSet

SCHEMA_VERSION = 6
UNKNOWN_SOURCE_VERSION_HASH = "UNKNOWN"

_SCIENTIFIC_RECORD_SPECS = {
    "boundary": (BoundaryRecord, "boundary_id"),
    "mesh": (MeshRecord, "mesh_id"),
    "field": (FieldRecord, "field_id"),
    "qoi": (QoIRecord, "qoi_id"),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _migration_1(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS project_state ("
        "project_id TEXT PRIMARY KEY, stage TEXT NOT NULL, manifest_json TEXT NOT NULL)"
    )


def _migration_2(connection: sqlite3.Connection) -> None:
    _execute_sql_batch(
        connection,
        """
        CREATE TABLE IF NOT EXISTS sources (
            source_id TEXT PRIMARY KEY,
            uri TEXT NOT NULL UNIQUE,
            locator TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            mtime_ns INTEGER NOT NULL,
            size_bytes INTEGER NOT NULL,
            version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
            stale INTEGER NOT NULL DEFAULT 0 CHECK(stale IN (0, 1)),
            authority REAL NOT NULL DEFAULT 0.5 CHECK(authority BETWEEN 0.0 AND 1.0),
            media_type TEXT,
            indexed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS source_versions (
            source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
            version INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            mtime_ns INTEGER NOT NULL,
            size_bytes INTEGER NOT NULL,
            indexed_at TEXT NOT NULL,
            PRIMARY KEY (source_id, version)
        );
        CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL REFERENCES sources(source_id),
            solver TEXT,
            solver_version TEXT,
            state TEXT NOT NULL DEFAULT 'discovered',
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS evidence (
            evidence_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL REFERENCES sources(source_id),
            locator TEXT NOT NULL,
            kind TEXT NOT NULL,
            summary TEXT NOT NULL,
            maturity TEXT NOT NULL DEFAULT 'raw',
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS claims (
            claim_id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            ceiling TEXT NOT NULL DEFAULT 'observation',
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS claim_evidence (
            claim_id TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
            evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id) ON DELETE CASCADE,
            PRIMARY KEY (claim_id, evidence_id)
        );
        CREATE TABLE IF NOT EXISTS stages (
            stage TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            outputs_json TEXT NOT NULL DEFAULT '{}',
            approved_by TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
            ordinal INTEGER NOT NULL,
            content TEXT NOT NULL,
            locator TEXT NOT NULL,
            token_count INTEGER NOT NULL,
            UNIQUE (source_id, ordinal)
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            chunk_id UNINDEXED,
            source_id UNINDEXED,
            content,
            locator UNINDEXED,
            tokenize='unicode61'
        );
        CREATE TABLE IF NOT EXISTS checkpoints (
            checkpoint_id TEXT PRIMARY KEY,
            stage TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sources_stale ON sources(stale);
        CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_id);
        CREATE INDEX IF NOT EXISTS idx_evidence_source ON evidence(source_id);
        CREATE INDEX IF NOT EXISTS idx_cases_source ON cases(source_id);
        """,
    )


def _migration_3(connection: sqlite3.Connection) -> None:
    case_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(cases)")}
    if "source_version_hash" not in case_columns:
        connection.execute("ALTER TABLE cases ADD COLUMN source_version_hash TEXT")
    evidence_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(evidence)")}
    if "source_version_hash" not in evidence_columns:
        connection.execute("ALTER TABLE evidence ADD COLUMN source_version_hash TEXT")
    connection.execute(
        "UPDATE cases SET source_version_hash=? WHERE source_version_hash IS NULL",
        (UNKNOWN_SOURCE_VERSION_HASH,),
    )
    connection.execute(
        "UPDATE evidence SET source_version_hash=? WHERE source_version_hash IS NULL",
        (UNKNOWN_SOURCE_VERSION_HASH,),
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_cases_source_version "
        "ON cases(source_id, source_version_hash)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_evidence_source_version "
        "ON evidence(source_id, source_version_hash)"
    )


def _migration_4(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS scientific_records ("
        "record_type TEXT NOT NULL, "
        "record_id TEXT NOT NULL, "
        "source_id TEXT NOT NULL REFERENCES sources(source_id), "
        "source_version_hash TEXT NOT NULL, "
        "record_json TEXT NOT NULL, "
        "PRIMARY KEY(record_type, record_id))"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_scientific_records_source "
        "ON scientific_records(source_id, source_version_hash)"
    )


def _migration_5(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS qoi_definition_assessments ("
        "qoi_id TEXT PRIMARY KEY, "
        "definition_id TEXT NOT NULL UNIQUE, "
        "record_json TEXT NOT NULL)"
    )


def _migration_6(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS scientific_assessment_state ("
        "scope TEXT PRIMARY KEY CHECK(scope='current'), "
        "record_json TEXT NOT NULL)"
    )


def _execute_sql_batch(connection: sqlite3.Connection, script: str) -> None:
    """Execute complete SQL statements without ``executescript`` implicit commits."""

    pending = ""
    for line in script.splitlines():
        pending += line + "\n"
        if sqlite3.complete_statement(pending):
            statement = pending.strip()
            pending = ""
            if statement:
                connection.execute(statement)
    if pending.strip():
        raise RuntimeError("incomplete migration SQL statement")


MIGRATIONS = {
    1: _migration_1,
    2: _migration_2,
    3: _migration_3,
    4: _migration_4,
    5: _migration_5,
    6: _migration_6,
}


def migrate_schema(connection: sqlite3.Connection) -> int:
    """Apply all forward-only, idempotent database migrations."""

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        applied = {
            int(row[0]) for row in connection.execute("SELECT version FROM schema_migrations")
        }
        for version, migration in MIGRATIONS.items():
            if version not in applied:
                migration(connection)
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, _utc_now()),
                )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    return SCHEMA_VERSION


@dataclass(frozen=True)
class StoredSource:
    source_id: str
    uri: str
    locator: str
    sha256: str
    mtime_ns: int
    size_bytes: int
    version: int
    stale: bool
    authority: float
    indexed_at: str


@dataclass(frozen=True)
class StoreStatus:
    project_id: str
    stage: str
    schema_version: int
    source_count: int
    stale_count: int
    chunk_count: int
    latest_checkpoint: str | None


@dataclass(frozen=True)
class Checkpoint:
    checkpoint_id: str
    stage: str
    payload: dict[str, Any]
    created_at: str


class ProjectStore:
    """Short-lived-connection SQLite store safe to reopen in another process."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.database = self.root / ".cfdpaper" / "project.db"

    @classmethod
    def open(cls, root: Path) -> ProjectStore:
        store = cls(root)
        if not store.database.is_file():
            raise FileNotFoundError(f"CFD-Paper-Agent project state not found: {store.database}")
        with store.connect() as connection:
            migrate_schema(connection)
        return store

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            connection.close()

    @property
    def schema_version(self) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0])

    def status(self) -> StoreStatus:
        with self.connect() as connection:
            project = self._require_unique_project(connection)
            counts = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(stale), 0) FROM sources"
            ).fetchone()
            chunks = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            checkpoint = connection.execute(
                "SELECT stage FROM checkpoints ORDER BY created_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
        return StoreStatus(
            project_id=str(project[0]),
            stage=str(project[1]),
            schema_version=self.schema_version,
            source_count=int(counts[0]),
            stale_count=int(counts[1]),
            chunk_count=int(chunks),
            latest_checkpoint=str(checkpoint[0]) if checkpoint else None,
        )

    def set_stage(self, stage: str, outputs: dict[str, Any] | None = None) -> None:
        now = _utc_now()
        payload = json.dumps(outputs or {}, sort_keys=True)
        with self.connect() as connection:
            project = self._require_unique_project(connection)
            connection.execute(
                "UPDATE project_state SET stage = ? WHERE project_id = ?",
                (stage, project["project_id"]),
            )
            connection.execute(
                "INSERT INTO stages(stage, status, outputs_json, updated_at) "
                "VALUES (?, 'complete', ?, ?) "
                "ON CONFLICT(stage) DO UPDATE SET status='complete', "
                "outputs_json=excluded.outputs_json, updated_at=excluded.updated_at",
                (stage, payload, now),
            )

    @staticmethod
    def _require_unique_project(connection: sqlite3.Connection) -> sqlite3.Row:
        projects = connection.execute("SELECT project_id, stage FROM project_state").fetchall()
        if len(projects) != 1:
            raise RuntimeError("project state must contain exactly one project")
        return projects[0]

    def get_source(self, uri: str) -> StoredSource:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM sources WHERE uri = ?", (uri,)).fetchone()
        if row is None:
            raise KeyError(uri)
        return self._source_from_row(row)

    def list_sources(self, *, include_stale: bool = True) -> list[StoredSource]:
        sql = "SELECT * FROM sources"
        if not include_stale:
            sql += " WHERE stale = 0"
        sql += " ORDER BY uri"
        with self.connect() as connection:
            rows = connection.execute(sql).fetchall()
        return [self._source_from_row(row) for row in rows]

    @staticmethod
    def _source_from_row(row: sqlite3.Row) -> StoredSource:
        return StoredSource(
            source_id=str(row["source_id"]),
            uri=str(row["uri"]),
            locator=str(row["locator"]),
            sha256=str(row["sha256"]),
            mtime_ns=int(row["mtime_ns"]),
            size_bytes=int(row["size_bytes"]),
            version=int(row["version"]),
            stale=bool(row["stale"]),
            authority=float(row["authority"]),
            indexed_at=str(row["indexed_at"]),
        )

    def index_source(
        self,
        *,
        uri: str,
        locator: str,
        sha256: str,
        mtime_ns: int,
        size_bytes: int,
        media_type: str | None,
        chunks: Iterable[tuple[str, str, int]],
    ) -> str:
        """Upsert a current source version and atomically replace its text chunks."""

        now = _utc_now()
        source_id = str(uuid5(NAMESPACE_URL, f"cfdpaper:{uri}"))
        chunk_rows = list(chunks)
        with self.connect() as connection:
            old = connection.execute(
                "SELECT source_id, sha256, version FROM sources WHERE uri = ?", (uri,)
            ).fetchone()
            if old is not None and str(old["sha256"]) == sha256:
                connection.execute(
                    "UPDATE sources SET locator=?, mtime_ns=?, size_bytes=?, stale=0, "
                    "media_type=?, indexed_at=? WHERE source_id=?",
                    (locator, mtime_ns, size_bytes, media_type, now, old["source_id"]),
                )
                return "unchanged"

            version = 1 if old is None else int(old["version"]) + 1
            if old is None:
                connection.execute(
                    "INSERT INTO sources(source_id, uri, locator, sha256, mtime_ns, "
                    "size_bytes, version, stale, media_type, indexed_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)",
                    (
                        source_id,
                        uri,
                        locator,
                        sha256,
                        mtime_ns,
                        size_bytes,
                        version,
                        media_type,
                        now,
                    ),
                )
                result = "added"
            else:
                source_id = str(old["source_id"])
                connection.execute(
                    "UPDATE sources SET locator=?, sha256=?, mtime_ns=?, size_bytes=?, "
                    "version=?, stale=0, media_type=?, indexed_at=? WHERE source_id=?",
                    (
                        locator,
                        sha256,
                        mtime_ns,
                        size_bytes,
                        version,
                        media_type,
                        now,
                        source_id,
                    ),
                )
                result = "updated"
            connection.execute(
                "INSERT INTO source_versions VALUES (?, ?, ?, ?, ?, ?)",
                (source_id, version, sha256, mtime_ns, size_bytes, now),
            )
            connection.execute("DELETE FROM chunks_fts WHERE source_id = ?", (source_id,))
            connection.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
            for ordinal, (content, chunk_locator, token_count) in enumerate(chunk_rows):
                chunk_id = str(uuid5(NAMESPACE_URL, f"{source_id}:{version}:{ordinal}"))
                connection.execute(
                    "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
                    (chunk_id, source_id, ordinal, content, chunk_locator, token_count),
                )
                connection.execute(
                    "INSERT INTO chunks_fts(chunk_id, source_id, content, locator) "
                    "VALUES (?, ?, ?, ?)",
                    (chunk_id, source_id, content, chunk_locator),
                )
        return result

    def mark_stale_except(self, seen_uris: set[str]) -> int:
        with self.connect() as connection:
            current = {
                str(row[0]) for row in connection.execute("SELECT uri FROM sources WHERE stale = 0")
            }
            missing = current - seen_uris
            if missing:
                placeholders = ",".join("?" for _ in missing)
                connection.execute(
                    f"UPDATE sources SET stale = 1 WHERE uri IN ({placeholders})",  # noqa: S608
                    tuple(sorted(missing)),
                )
        return len(missing)

    def source_version_count(self, source_id: str) -> int:
        with self.connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM source_versions WHERE source_id = ?", (source_id,)
            ).fetchone()[0]
        return int(count)

    def chunk_count(self, uri: str | None = None) -> int:
        with self.connect() as connection:
            if uri is None:
                count = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            else:
                count = connection.execute(
                    "SELECT COUNT(*) FROM chunks c JOIN sources s USING(source_id) WHERE s.uri = ?",
                    (uri,),
                ).fetchone()[0]
        return int(count)

    def set_source_authority(self, uri: str, authority: float) -> None:
        if not 0.0 <= authority <= 1.0:
            raise ValueError("authority must be between 0 and 1")
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE sources SET authority = ? WHERE uri = ?", (authority, uri)
            )
            if cursor.rowcount == 0:
                raise KeyError(uri)

    def _source_snapshot_for_record(
        self, source_uri: str, source_hash: str | None
    ) -> tuple[str, str]:
        source = self.get_source(source_uri)
        snapshot_hash = source_hash or source.sha256
        with self.connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM source_versions WHERE source_id=? AND sha256=?",
                (source.source_id, snapshot_hash),
            ).fetchone()
        if exists is None:
            raise ValueError(f"source hash is not an indexed version: {source_uri}")
        return source.source_id, snapshot_hash

    def _save_scientific_record(self, record_type: str, record: BaseModel) -> None:
        model, id_field = _SCIENTIFIC_RECORD_SPECS[record_type]
        validated = model.model_validate(record.model_dump(mode="python"))
        source_id, source_version_hash = self._source_snapshot_for_record(
            validated.source_uri, validated.source_hash
        )
        validated = validated.model_copy(update={"source_hash": source_version_hash})
        record_id = str(getattr(validated, id_field))
        record_json = canonical_json_bytes(validated).decode("utf-8")
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO scientific_records(record_type, record_id, source_id, "
                "source_version_hash, record_json) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(record_type, record_id) DO UPDATE SET "
                "source_id=excluded.source_id, "
                "source_version_hash=excluded.source_version_hash, "
                "record_json=excluded.record_json",
                (record_type, record_id, source_id, source_version_hash, record_json),
            )

    def _list_scientific_records(self, record_type: str) -> list[BaseModel]:
        model, _ = _SCIENTIFIC_RECORD_SPECS[record_type]
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT r.record_json, r.source_version_hash, s.sha256, s.stale "
                "FROM scientific_records r JOIN sources s USING(source_id) "
                "WHERE r.record_type=? ORDER BY r.record_id",
                (record_type,),
            ).fetchall()
        records: list[BaseModel] = []
        for row in rows:
            record = model.model_validate(json.loads(str(row["record_json"])))
            saved_hash = str(row["source_version_hash"])
            stale = record.stale or bool(row["stale"]) or saved_hash != str(row["sha256"])
            records.append(record.model_copy(update={"source_hash": saved_hash, "stale": stale}))
        return records

    def save_boundary(self, record: BoundaryRecord) -> None:
        self._save_scientific_record("boundary", record)

    def list_boundaries(self) -> list[BoundaryRecord]:
        return cast(list[BoundaryRecord], self._list_scientific_records("boundary"))

    def save_mesh(self, record: MeshRecord) -> None:
        self._save_scientific_record("mesh", record)

    def list_meshes(self) -> list[MeshRecord]:
        return cast(list[MeshRecord], self._list_scientific_records("mesh"))

    def save_field(self, record: FieldRecord) -> None:
        self._save_scientific_record("field", record)

    def list_fields(self) -> list[FieldRecord]:
        return cast(list[FieldRecord], self._list_scientific_records("field"))

    def save_qoi(self, record: QoIRecord) -> None:
        self._save_scientific_record("qoi", record)

    def list_qois(self) -> list[QoIRecord]:
        return cast(list[QoIRecord], self._list_scientific_records("qoi"))

    @staticmethod
    def _validate_qoi_definition_assessment(
        connection: sqlite3.Connection,
        record: QoIDefinitionAssessmentRecord,
    ) -> None:
        qoi_row = connection.execute(
            "SELECT record_json FROM scientific_records "
            "WHERE record_type = 'qoi' AND record_id = ?",
            (record.qoi_id,),
        ).fetchone()
        if qoi_row is None:
            raise RuntimeError(f"unknown qoi: {record.qoi_id}")
        qoi = QoIRecord.model_validate_json(str(qoi_row["record_json"]))
        if qoi.name.strip().casefold() != record.name.strip().casefold():
            raise RuntimeError("QoI definition name mismatch")
        try:
            units_match = canonical_unit(qoi.unit) == canonical_unit(record.unit)
        except ValueError as error:
            raise RuntimeError("QoI definition unit mismatch") from error
        if not units_match:
            raise RuntimeError("QoI definition unit mismatch")

        placeholders = ",".join("?" for _ in record.evidence_ids)
        evidence_rows = connection.execute(
            "SELECT e.evidence_id, e.locator, e.kind, e.metadata_json, "
            "e.source_version_hash, s.uri, s.sha256, s.stale "
            "FROM evidence e JOIN sources s USING(source_id) "
            f"WHERE e.evidence_id IN ({placeholders})",
            record.evidence_ids,
        ).fetchall()
        if len(evidence_rows) != len(record.evidence_ids):
            raise RuntimeError("QoI definition evidence missing")

        exact_qoi_locator = False
        for evidence in evidence_rows:
            metadata = json.loads(str(evidence["metadata_json"]))
            saved_hash = str(evidence["source_version_hash"])
            current_hash = str(evidence["sha256"])
            if (
                bool(evidence["stale"])
                or bool(metadata.get("stale", False))
                or saved_hash != current_hash
            ):
                raise RuntimeError("QoI definition evidence stale or version mismatch")
            if str(evidence["uri"]) != record.source_uri:
                raise RuntimeError("QoI definition source URI mismatch")
            if saved_hash != record.source_hash:
                raise RuntimeError("QoI definition source hash mismatch")
            if str(evidence["kind"]) == "qoi" and str(evidence["locator"]) == record.source_locator:
                exact_qoi_locator = True
        if not exact_qoi_locator:
            raise RuntimeError("QoI definition evidence binding lacks exact qoi locator")

    def save_qoi_definition_assessment(self, record: QoIDefinitionAssessmentRecord) -> None:
        validated = QoIDefinitionAssessmentRecord.model_validate(record.model_dump(mode="python"))
        payload = canonical_json_bytes(validated).decode("utf-8")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._validate_qoi_definition_assessment(connection, validated)
            existing = connection.execute(
                "SELECT definition_id, record_json FROM qoi_definition_assessments "
                "WHERE qoi_id = ?",
                (validated.qoi_id,),
            ).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO qoi_definition_assessments"
                    "(qoi_id, definition_id, record_json) VALUES (?, ?, ?)",
                    (validated.qoi_id, validated.definition_id, payload),
                )
                return
            if (
                str(existing["definition_id"]) == validated.definition_id
                and str(existing["record_json"]) == payload
            ):
                return
            raise RuntimeError("unequal QoI definition overwrite is forbidden")

    def _replace_qoi_definition_row(
        self,
        connection: sqlite3.Connection,
        record: QoIDefinitionAssessmentRecord,
        payload: str,
    ) -> None:
        connection.execute(
            "UPDATE qoi_definition_assessments "
            "SET definition_id = ?, record_json = ? WHERE qoi_id = ?",
            (record.definition_id, payload, record.qoi_id),
        )

    def replace_qoi_definition_assessment(
        self,
        record: QoIDefinitionAssessmentRecord,
        *,
        expected_definition_id: str,
    ) -> None:
        validated = QoIDefinitionAssessmentRecord.model_validate(record.model_dump(mode="python"))
        payload = canonical_json_bytes(validated).decode("utf-8")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT definition_id FROM qoi_definition_assessments WHERE qoi_id = ?",
                (validated.qoi_id,),
            ).fetchone()
            if existing is None or str(existing["definition_id"]) != expected_definition_id:
                raise RuntimeError("stale QoI definition identity")
            self._validate_qoi_definition_assessment(connection, validated)
            self._replace_qoi_definition_row(connection, validated, payload)

    def list_qoi_definition_assessments(
        self,
    ) -> tuple[QoIDefinitionAssessmentRecord, ...]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT record_json FROM qoi_definition_assessments ORDER BY qoi_id, definition_id"
            ).fetchall()
        return tuple(
            QoIDefinitionAssessmentRecord.model_validate_json(str(row["record_json"]))
            for row in rows
        )

    @staticmethod
    def _validate_scientific_assessment_set(
        connection: sqlite3.Connection,
        record: ScientificAssessmentSet,
    ) -> None:
        case_ids = tuple(case.case_id for case in record.cases)
        if case_ids:
            placeholders = ",".join("?" for _ in case_ids)
            rows = connection.execute(
                "SELECT c.case_id, c.metadata_json, c.source_version_hash, "
                "s.uri, s.sha256, s.stale FROM cases c JOIN sources s USING(source_id) "
                f"WHERE c.case_id IN ({placeholders})",
                case_ids,
            ).fetchall()
            if len(rows) != len(case_ids):
                raise RuntimeError("scientific assessment case missing")
            for row in rows:
                metadata = json.loads(str(row["metadata_json"]))
                if (
                    bool(row["stale"])
                    or bool(metadata.get("stale", False))
                    or str(row["source_version_hash"]) != str(row["sha256"])
                ):
                    raise RuntimeError("scientific assessment case stale or version mismatch")
            case_sources = {
                str(row["case_id"]): (str(row["uri"]), str(row["sha256"])) for row in rows
            }
        else:
            case_sources = {}

        strict_binding_sets: dict[str, set[tuple[str, str]]] = {}
        for case in record.cases:
            for kind, bound_ids in (
                ("case", case.case_evidence_ids),
                ("convergence", case.convergence_evidence_ids),
                ("conservation", case.conservation_evidence_ids),
            ):
                for evidence_id in bound_ids:
                    strict_binding_sets.setdefault(evidence_id, set()).add((case.case_id, kind))
        if any(len(bindings) != 1 for bindings in strict_binding_sets.values()):
            raise RuntimeError("scientific assessment evidence kind or source mismatch")
        strict_bindings = {
            evidence_id: next(iter(bindings))
            for evidence_id, bindings in strict_binding_sets.items()
        }

        evidence_ids = tuple(
            sorted(
                {
                    evidence_id
                    for case in record.cases
                    for evidence_id in (
                        *case.independent_validation_evidence_ids,
                        *case.engineering_evidence_ids,
                        *case.sensitivity_evidence_ids,
                        *case.case_evidence_ids,
                        *case.convergence_evidence_ids,
                        *case.conservation_evidence_ids,
                    )
                }
            )
        )
        if not evidence_ids:
            return
        placeholders = ",".join("?" for _ in evidence_ids)
        rows = connection.execute(
            "SELECT e.evidence_id, e.kind, e.metadata_json, e.source_version_hash, "
            "s.uri, s.sha256, s.stale FROM evidence e JOIN sources s USING(source_id) "
            f"WHERE e.evidence_id IN ({placeholders})",
            evidence_ids,
        ).fetchall()
        if len(rows) != len(evidence_ids):
            raise RuntimeError("scientific assessment evidence missing")
        for row in rows:
            metadata = json.loads(str(row["metadata_json"]))
            if (
                bool(row["stale"])
                or bool(metadata.get("stale", False))
                or str(row["source_version_hash"]) != str(row["sha256"])
            ):
                raise RuntimeError("scientific assessment evidence stale or version mismatch")
            binding = strict_bindings.get(str(row["evidence_id"]))
            if binding is not None:
                case_id, expected_kind = binding
                case_source = case_sources[case_id]
                if (
                    str(row["kind"]) != expected_kind
                    or str(row["uri"]) != case_source[0]
                    or str(row["source_version_hash"]) != case_source[1]
                ):
                    raise RuntimeError("scientific assessment evidence kind or source mismatch")

    def save_scientific_assessment_set(self, record: ScientificAssessmentSet) -> None:
        validated = ScientificAssessmentSet.model_validate(
            record.model_dump(mode="python"), strict=True
        )
        payload = canonical_json_bytes(validated).decode("utf-8")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._validate_scientific_assessment_set(connection, validated)
            connection.execute(
                "INSERT INTO scientific_assessment_state(scope, record_json) "
                "VALUES ('current', ?) ON CONFLICT(scope) DO UPDATE SET "
                "record_json=excluded.record_json",
                (payload,),
            )

    def load_scientific_assessment_set(self) -> ScientificAssessmentSet:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT record_json FROM scientific_assessment_state WHERE scope = 'current'"
            ).fetchone()
        if row is None:
            return ScientificAssessmentSet()
        return ScientificAssessmentSet.model_validate_json(str(row["record_json"]), strict=True)

    def save_case(self, record: CaseRecord) -> None:
        source_id, source_version_hash = self._source_snapshot_for_record(
            record.source_uri, record.source_hash
        )
        metadata = {"locator": record.locator, "stale": record.stale}
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO cases(case_id, source_id, solver, solver_version, state, "
                "metadata_json, source_version_hash) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(case_id) DO UPDATE SET source_id=excluded.source_id, "
                "solver=excluded.solver, solver_version=excluded.solver_version, "
                "state=excluded.state, metadata_json=excluded.metadata_json, "
                "source_version_hash=excluded.source_version_hash",
                (
                    record.case_id,
                    source_id,
                    record.solver,
                    record.solver_version,
                    record.state,
                    json.dumps(metadata, sort_keys=True),
                    source_version_hash,
                ),
            )

    def list_cases(self, *, source_ids: list[str] | None = None) -> list[CaseRecord]:
        parameters: list[str] = []
        where = ""
        if source_ids:
            where = " WHERE c.source_id IN (" + ",".join("?" for _ in source_ids) + ")"
            parameters.extend(source_ids)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT c.*, s.uri, s.sha256 AS current_hash, s.stale AS source_stale "
                "FROM cases c JOIN sources s USING(source_id)" + where + " ORDER BY c.case_id",
                parameters,
            ).fetchall()
        records = []
        for row in rows:
            metadata = json.loads(str(row["metadata_json"]))
            snapshot_hash = str(row["source_version_hash"])
            records.append(
                CaseRecord(
                    case_id=str(row["case_id"]),
                    source_uri=str(row["uri"]),
                    locator=str(metadata.get("locator", row["uri"])),
                    source_hash=snapshot_hash,
                    stale=(
                        bool(row["source_stale"])
                        or bool(metadata.get("stale", False))
                        or snapshot_hash != str(row["current_hash"])
                    ),
                    solver=row["solver"],
                    solver_version=row["solver_version"],
                    state=str(row["state"]),
                )
            )
        return records

    def save_evidence(self, record: EvidenceRecord) -> None:
        source_id, source_version_hash = self._source_snapshot_for_record(
            record.source_uri, record.source_hash
        )
        metadata = {"stale": record.stale}
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO evidence(evidence_id, source_id, locator, kind, summary, "
                "maturity, metadata_json, source_version_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(evidence_id) DO UPDATE SET source_id=excluded.source_id, "
                "locator=excluded.locator, kind=excluded.kind, summary=excluded.summary, "
                "maturity=excluded.maturity, metadata_json=excluded.metadata_json, "
                "source_version_hash=excluded.source_version_hash",
                (
                    record.evidence_id,
                    source_id,
                    record.locator,
                    record.kind,
                    record.summary,
                    record.maturity,
                    json.dumps(metadata, sort_keys=True),
                    source_version_hash,
                ),
            )

    def list_evidence(self, *, source_ids: list[str] | None = None) -> list[EvidenceRecord]:
        parameters: list[str] = []
        where = ""
        if source_ids:
            where = " WHERE e.source_id IN (" + ",".join("?" for _ in source_ids) + ")"
            parameters.extend(source_ids)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT e.*, s.uri, s.sha256 AS current_hash, s.stale AS source_stale "
                "FROM evidence e JOIN sources s USING(source_id)"
                + where
                + " ORDER BY e.evidence_id",
                parameters,
            ).fetchall()
        records = []
        for row in rows:
            metadata = json.loads(str(row["metadata_json"]))
            snapshot_hash = str(row["source_version_hash"])
            records.append(
                EvidenceRecord(
                    evidence_id=str(row["evidence_id"]),
                    source_uri=str(row["uri"]),
                    locator=str(row["locator"]),
                    source_hash=snapshot_hash,
                    stale=(
                        bool(row["source_stale"])
                        or bool(metadata.get("stale", False))
                        or snapshot_hash != str(row["current_hash"])
                    ),
                    kind=str(row["kind"]),
                    summary=str(row["summary"]),
                    maturity=str(row["maturity"]),
                )
            )
        return records

    def save_claim(self, record: ClaimRecord) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO claims(claim_id, text, status, ceiling) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(claim_id) DO UPDATE SET text=excluded.text, "
                "status=excluded.status, ceiling=excluded.ceiling",
                (record.claim_id, record.text, record.status.value, record.ceiling),
            )
            connection.execute("DELETE FROM claim_evidence WHERE claim_id = ?", (record.claim_id,))
            connection.executemany(
                "INSERT INTO claim_evidence(claim_id, evidence_id) VALUES (?, ?)",
                [(record.claim_id, evidence_id) for evidence_id in record.evidence_ids],
            )

    def list_claims(self, *, source_ids: list[str] | None = None) -> list[ClaimRecord]:
        parameters: list[str] = []
        where = ""
        if source_ids:
            where = (
                " WHERE EXISTS (SELECT 1 FROM claim_evidence ce "
                "JOIN evidence e ON e.evidence_id=ce.evidence_id "
                "WHERE ce.claim_id=c.claim_id AND e.source_id IN ("
                + ",".join("?" for _ in source_ids)
                + "))"
            )
            parameters.extend(source_ids)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT c.* FROM claims c" + where + " ORDER BY c.claim_id", parameters
            ).fetchall()
            records = []
            for row in rows:
                evidence_ids = [
                    str(link[0])
                    for link in connection.execute(
                        "SELECT evidence_id FROM claim_evidence WHERE claim_id=? "
                        "ORDER BY evidence_id",
                        (row["claim_id"],),
                    )
                ]
                records.append(
                    ClaimRecord(
                        claim_id=str(row["claim_id"]),
                        text=str(row["text"]),
                        status=str(row["status"]),
                        evidence_ids=evidence_ids,
                        ceiling=str(row["ceiling"]),
                    )
                )
        return records

    def save_stage(self, record: StageResult) -> None:
        updated_at = (
            record.completed_at.isoformat() if record.completed_at is not None else _utc_now()
        )
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO stages(stage, status, outputs_json, approved_by, updated_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(stage) DO UPDATE SET "
                "status=excluded.status, outputs_json=excluded.outputs_json, "
                "approved_by=excluded.approved_by, updated_at=excluded.updated_at",
                (
                    record.stage,
                    record.status,
                    json.dumps(record.outputs, sort_keys=True),
                    record.approved_by,
                    updated_at,
                ),
            )

    def save_workflow_transition(
        self,
        record: StageResult,
        *,
        project_stage: str,
        checkpoint_id: str,
        checkpoint_stage: str,
        checkpoint_payload: dict[str, Any],
    ) -> str:
        outputs_json = json.dumps(record.outputs, sort_keys=True)
        checkpoint_payload_json = json.dumps(checkpoint_payload, sort_keys=True)
        now = record.completed_at.isoformat() if record.completed_at is not None else _utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            project = self._require_unique_project(connection)
            existing_stage = connection.execute(
                "SELECT status, outputs_json, approved_by FROM stages WHERE stage = ?",
                (record.stage,),
            ).fetchone()
            stage_values = (record.status, outputs_json, record.approved_by)
            if existing_stage is None:
                connection.execute(
                    "INSERT INTO stages(stage, status, outputs_json, approved_by, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (record.stage, *stage_values, now),
                )
            elif (
                existing_stage["status"],
                existing_stage["outputs_json"],
                existing_stage["approved_by"],
            ) != stage_values:
                connection.execute(
                    "UPDATE stages SET status = ?, outputs_json = ?, approved_by = ?, "
                    "updated_at = ? WHERE stage = ?",
                    (*stage_values, now, record.stage),
                )

            connection.execute(
                "UPDATE project_state SET stage = ? WHERE project_id = ?",
                (project_stage, project["project_id"]),
            )
            checkpoint = connection.execute(
                "SELECT stage, payload_json FROM checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,),
            ).fetchone()
            checkpoint_values = (checkpoint_stage, checkpoint_payload_json)
            if checkpoint is None:
                connection.execute(
                    "INSERT INTO checkpoints(checkpoint_id, stage, payload_json, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (checkpoint_id, *checkpoint_values, now),
                )
            elif (checkpoint["stage"], checkpoint["payload_json"]) != checkpoint_values:
                raise RuntimeError("deterministic checkpoint ID collision")
        return checkpoint_id

    def save_checkpoint(self, stage: str, payload: dict[str, Any]) -> str:
        checkpoint_id = str(uuid4())
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO checkpoints VALUES (?, ?, ?, ?)",
                (checkpoint_id, stage, json.dumps(payload, sort_keys=True), _utc_now()),
            )
        return checkpoint_id

    def resume_checkpoint(self, checkpoint_id: str | None = None) -> Checkpoint:
        with self.connect() as connection:
            if checkpoint_id is None:
                row = connection.execute(
                    "SELECT * FROM checkpoints ORDER BY created_at DESC, rowid DESC LIMIT 1"
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT * FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,)
                ).fetchone()
        if row is None:
            raise LookupError("no matching checkpoint")
        return Checkpoint(
            checkpoint_id=str(row["checkpoint_id"]),
            stage=str(row["stage"]),
            payload=json.loads(str(row["payload_json"])),
            created_at=str(row["created_at"]),
        )
