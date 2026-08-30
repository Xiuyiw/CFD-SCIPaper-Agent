"""Local project-state creation and loading."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from cfdpaper.contracts import ProjectManifest
from cfdpaper.storage import SCHEMA_VERSION, ProjectStore, migrate_schema

STATE_DIR = ".cfdpaper"


def initialize_project(root: Path, project_id: str) -> ProjectManifest:
    manifest = ProjectManifest(project_id=project_id, root=root)
    state_dir = manifest.root / STATE_DIR
    state_dir.mkdir(exist_ok=True)
    (state_dir / "cache").mkdir(exist_ok=True)
    (state_dir / "checkpoints").mkdir(exist_ok=True)

    database = state_dir / "project.db"
    with closing(sqlite3.connect(database)) as connection:
        migrate_schema(connection)
        projects = connection.execute("SELECT project_id FROM project_state").fetchall()
        if len(projects) > 1:
            raise RuntimeError("project state must contain exactly one project")
        if projects and str(projects[0][0]) != project_id:
            raise ValueError(
                f"project root already initialized as {projects[0][0]}; "
                f"cannot replace with {project_id}"
            )
        if not projects:
            connection.execute(
                "INSERT INTO project_state(project_id, stage, manifest_json) VALUES (?, ?, ?)",
                (project_id, "initialized", manifest.model_dump_json()),
            )
        connection.commit()

    index_manifest = {
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id,
        "files": {},
    }
    index_path = state_dir / "index_manifest.json"
    if not index_path.exists():
        index_path.write_text(json.dumps(index_manifest, indent=2), encoding="utf-8")
    return manifest


def read_status(root: Path) -> tuple[str, str]:
    status = ProjectStore.open(root).status()
    return status.project_id, status.stage
