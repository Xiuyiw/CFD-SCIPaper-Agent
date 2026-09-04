from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from cfdpaper.indexing import ProjectIndexer
from cfdpaper.planning import run_plan
from cfdpaper.qualification import artifacts
from cfdpaper.qualification.service import (
    StaleArtifactError,
    approve_and_render_figure,
    approve_final_artifact,
    approve_qoi_contract,
    run_analyze,
    run_qualify,
    run_write,
)
from cfdpaper.state import initialize_project
from cfdpaper.storage import ProjectStore

FIXTURE = Path(__file__).parents[1] / "examples" / "steady_laminar_pipe"


def _locked_project(root: Path) -> tuple[Path, Path, Path]:
    shutil.copytree(FIXTURE, root, dirs_exist_ok=True)
    initialize_project(root, "stale-pipe")
    ProjectIndexer(ProjectStore.open(root)).inspect()
    inputs = root / ".cfdpaper" / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / "topic-candidates.json", inputs / "topic_candidates.json")
    records = root / "project-records.json"
    observations = root / "observations.csv"
    question = root / "question.json"
    qualified = run_qualify(
        root,
        records_path=records,
        observations_path=observations,
        question_path=question,
    )
    run_plan(root, approve_topic="steady-pipe-pressure-drop", author="Author")
    approve_qoi_contract(
        root,
        contract_id=qualified.candidate.qoi_contract_id,
        author="Author",
    )
    analysis = run_analyze(root)
    approve_and_render_figure(
        root,
        contract_id=analysis.candidate_figure.figure_id,
        author="Author",
    )
    run_write(root, artifact="results-paragraph")
    return records, observations, question


def _assert_stale(root: Path, expected_dependency: str) -> None:
    status = json.loads(
        (root / ".cfdpaper" / "outputs" / "qualify" / "qoi-results.json").read_text(
            encoding="utf-8"
        )
    )
    assert status["artifact_status"] == "stale"
    assert status["stale_dependency"] == expected_dependency
    assert status["rerun_command"].startswith("cfdpaper qualify")


def test_changed_observation_marks_outputs_stale_and_restores_deterministically(
    tmp_path: Path,
) -> None:
    _, observations, _ = _locked_project(tmp_path)
    original = observations.read_bytes()
    observations.write_text(
        observations.read_text(encoding="utf-8").replace(",48,", ",49,"),
        encoding="utf-8",
    )

    with pytest.raises(StaleArtifactError, match="observations"):
        run_analyze(tmp_path)
    _assert_stale(tmp_path, "observations")

    observations.write_bytes(original)
    store = ProjectStore.open(tmp_path)
    with store.connect() as connection:
        before = connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]
    run_analyze(tmp_path)
    with store.connect() as connection:
        after = connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]
    assert after == before


def test_changed_expected_membership_marks_outputs_stale(tmp_path: Path) -> None:
    _, _, question = _locked_project(tmp_path)
    payload = json.loads(question.read_text(encoding="utf-8"))
    payload["proposal"]["expected_members"][1]["coordinate_value"] = 0.11
    question.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(StaleArtifactError, match="expected membership"):
        run_analyze(tmp_path)
    _assert_stale(tmp_path, "expected membership")


def test_tampered_locked_contract_requires_contract_reapproval(tmp_path: Path) -> None:
    _locked_project(tmp_path)
    locked = tmp_path / ".cfdpaper" / "outputs" / "qualify" / "locked-qoi-contract.json"
    payload = json.loads(locked.read_text(encoding="utf-8"))
    payload["qoi_name"] = "Altered pressure drop"
    locked.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(StaleArtifactError, match="locked QoI contract") as raised:
        run_analyze(tmp_path)
    assert "--approve-qoi-contract" in raised.value.rerun_command


def test_changed_unit_registry_version_marks_outputs_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _locked_project(tmp_path)
    monkeypatch.setattr(artifacts.unit_definitions, "UNIT_REGISTRY_VERSION", "changed-test")

    with pytest.raises(StaleArtifactError, match="unit definitions"):
        run_analyze(tmp_path)
    _assert_stale(tmp_path, "unit definitions")


def test_declared_source_cannot_overwrite_newer_inspected_content(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    initialize_project(tmp_path, "source-binding")
    store = ProjectStore.open(tmp_path)
    ProjectIndexer(store).inspect()
    reference = tmp_path / "analytic-reference.md"
    reference.write_text(reference.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
    ProjectIndexer(store).inspect()
    actual_hash = hashlib.sha256(reference.read_bytes()).hexdigest()

    with pytest.raises(StaleArtifactError, match="source files"):
        run_qualify(
            tmp_path,
            records_path=tmp_path / "project-records.json",
            observations_path=tmp_path / "observations.csv",
            question_path=tmp_path / "question.json",
        )

    assert store.get_source("analytic-reference.md").sha256 == actual_hash


def test_uninspected_source_change_blocks_analysis(tmp_path: Path) -> None:
    _locked_project(tmp_path)
    reference = tmp_path / "analytic-reference.md"
    reference.write_text(reference.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")

    with pytest.raises(StaleArtifactError, match="source files"):
        run_analyze(tmp_path)


def test_final_approval_rechecks_current_inputs_without_rewriting_outputs(tmp_path: Path) -> None:
    _, observations, _ = _locked_project(tmp_path)
    write_dir = tmp_path / ".cfdpaper" / "outputs" / "write"
    before = {path.name: path.read_bytes() for path in write_dir.iterdir() if path.is_file()}
    observations.write_text(
        observations.read_text(encoding="utf-8").replace(",48.0,", ",49.0,"),
        encoding="utf-8",
    )

    with pytest.raises(StaleArtifactError, match="observations"):
        approve_final_artifact(tmp_path, artifact="results-paragraph", author="Author")

    assert {
        path.name: path.read_bytes() for path in write_dir.iterdir() if path.is_file()
    } == before
