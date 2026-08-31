import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
import warnings
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from inspect import signature
from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel, ValidationError

import cfdpaper.planning as planning_module
from cfdpaper.cache import ContentAddressedCache
from cfdpaper.contracts import EvidenceRecord
from cfdpaper.indexing import ProjectIndexer
from cfdpaper.planning import (
    CandidateInput,
    InspectionSummary,
    PlanApproval,
    PlanExecution,
    PlanningInputError,
    PlanningWriteError,
    PlanReport,
    evidence_snapshot_sha256,
    load_candidate_input,
    plan_fingerprint,
    plan_report_bytes,
    run_plan,
)
from cfdpaper.publication.topics import (
    RankedTopic,
    TopicCandidate,
    TopicRankingResult,
    rank_topics,
)
from cfdpaper.retrieval import HybridRetriever, TaskContextBuilder
from cfdpaper.state import initialize_project
from cfdpaper.storage import ProjectStore
from cfdpaper.topic_generation.canonical import canonical_sha256
from cfdpaper.topic_generation.service import TopicGenerationDependencies
from cfdpaper.topic_generation.snapshot import ScientificRecordSnapshot, load_scientific_snapshot
from tests.fixtures.planning.author_plan_report_golden import AUTHOR_PLAN_REPORT_GOLDEN_HEX
from tests.topic_generation.factories import (
    SOURCE_URI,
    mature_ordered_scientific_store,
    populated_scientific_store,
)
from tests.topic_generation.test_opportunities import synthetic_snapshot


def candidate_payload(*, required_kinds: list[str] | None = None) -> dict:
    return {
        "schema_version": 1,
        "candidates": [
            {
                "topic_id": "topic-01",
                "title": "Pressure-loss comparison",
                "research_question": "How does configuration affect pressure loss?",
                "supporting_evidence_ids": ["ev-01"],
                "required_evidence_kinds": required_kinds or ["qoi"],
                "required_maturity": "verified",
                "minimum_verified_evidence": 1,
                "significance": 0.8,
                "novelty": 0.7,
            }
        ],
    }


def two_candidate_payload() -> dict:
    payload = candidate_payload()
    payload["candidates"].append(
        {
            "topic_id": "topic-gap",
            "title": "Unsupported direction",
            "research_question": "Which evidence would support this direction?",
            "supporting_evidence_ids": ["ev-missing"],
            "required_evidence_kinds": ["qoi"],
            "required_maturity": "verified",
            "minimum_verified_evidence": 1,
            "significance": 0.6,
            "novelty": 0.9,
        }
    )
    return payload


def write_candidates(path: Path, payload: dict | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload or candidate_payload()), encoding="utf-8")
    return path


def prepared_project(
    tmp_path: Path,
    *,
    project_id: str = "demo",
) -> tuple[ProjectStore, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    initialize_project(tmp_path, project_id)
    source = tmp_path / "results.csv"
    source.write_bytes(b"case,dp\nA,12\n")
    store = ProjectStore.open(tmp_path)
    ProjectIndexer(store).inspect()
    stored = store.get_source("results.csv")
    store.save_evidence(
        EvidenceRecord(
            evidence_id="ev-01",
            source_uri="results.csv",
            locator="row:2",
            source_hash=stored.sha256,
            kind="qoi",
            summary="pressure loss",
            maturity="verified",
        )
    )
    candidates = write_candidates(tmp_path / ".cfdpaper" / "inputs" / "topic_candidates.json")
    return store, candidates


def prepared_generated_project(tmp_path: Path) -> ProjectStore:
    return populated_scientific_store(tmp_path)


def generated_dependencies(store: ProjectStore, snapshot: object) -> TopicGenerationDependencies:
    raw = snapshot.model_dump(mode="python")
    raw["project_id"] = store.status().project_id
    raw["aggregate_sha256"] = canonical_sha256(
        {"project_id": raw["project_id"], "component_hashes": raw["component_hashes"]},
        domain=b"cfdpaper-scientific-snapshot-v1",
    )
    project_snapshot = ScientificRecordSnapshot.model_validate(raw)
    return TopicGenerationDependencies(
        store=store,
        cache=ContentAddressedCache(store.root),
        context_builder=TaskContextBuilder(HybridRetriever(store)),
        snapshot_loader=lambda _store: project_snapshot,
        assert_plan_lock_held=lambda: True,
    )


def test_generated_candidates_are_used_only_when_no_author_input_exists(tmp_path: Path) -> None:
    store = prepared_generated_project(tmp_path)

    execution = run_plan(tmp_path, provider_mode="offline")

    assert execution.candidate_source_kind == "generated"
    assert execution.generation is not None
    assert (
        execution.report.generation_fingerprint
        == execution.generation.report.generation_fingerprint
    )
    assert store.status().stage == "planned"


def test_generated_direction_only_topic_requires_real_author_but_stays_non_manuscript(
    tmp_path: Path,
) -> None:
    store = prepared_generated_project(tmp_path)
    dependencies = generated_dependencies(store, synthetic_snapshot(values=(1.0, 2.0, 3.0)))
    proposal = run_plan(
        tmp_path,
        provider_mode="offline",
        generation_dependencies=dependencies,
    )
    topic_id = proposal.report.ranking.ranked_topics[0].candidate.topic_id

    approved = run_plan(
        tmp_path,
        provider_mode="offline",
        approve_topic=topic_id,
        author="Author",
        generation_dependencies=dependencies,
    )

    assert proposal.report.approval is None
    assert approved.report.approval is not None
    assert approved.report.approval.scope == "direction-only"
    assert store.status().stage == "planned"
    assert store.resume_checkpoint(approved.checkpoint_id).stage == "plan-direction-approval"


def test_generated_candidate_declares_evidence_for_every_required_manuscript_kind(
    tmp_path: Path,
) -> None:
    store = mature_ordered_scientific_store(tmp_path)
    dependencies = generated_dependencies(store, load_scientific_snapshot(store))

    proposal = run_plan(
        tmp_path,
        provider_mode="offline",
        generation_dependencies=dependencies,
    )
    candidate = proposal.generation.candidate_input.candidates[0]
    evidence_by_id = {item.evidence_id: item for item in store.list_evidence()}
    declared_kinds = {
        evidence_by_id[evidence_id].kind
        for evidence_id in candidate.supporting_evidence_ids
        if evidence_id in evidence_by_id
    }

    assert candidate.required_evidence_kinds <= declared_kinds
    assert proposal.report.ranking.outcome == "manuscript"
    assert proposal.report.approval is None

    approved = run_plan(
        tmp_path,
        provider_mode="offline",
        approve_topic=candidate.topic_id,
        author="Author",
        generation_dependencies=dependencies,
    )

    assert approved.report.approval is not None
    assert approved.report.approval.scope == "manuscript-topic"
    assert approved.report.approval.plan_fingerprint == approved.report.plan_fingerprint
    assert store.status().stage == "topic-approved"


def test_generated_approval_is_invalidated_by_regeneration_and_evidence_change(
    tmp_path: Path,
) -> None:
    store = prepared_generated_project(tmp_path)
    dependencies = generated_dependencies(store, synthetic_snapshot(values=(1.0, 2.0, 3.0)))
    proposal = run_plan(
        tmp_path,
        provider_mode="offline",
        generation_dependencies=dependencies,
    )
    topic_id = proposal.report.ranking.ranked_topics[0].candidate.topic_id
    approved = run_plan(
        tmp_path,
        provider_mode="offline",
        approve_topic=topic_id,
        author="Author",
        generation_dependencies=dependencies,
    )
    assert approved.report.approval is not None
    assert approved.report.approval.plan_fingerprint == approved.report.plan_fingerprint

    regenerated = run_plan(
        tmp_path,
        provider_mode="offline",
        regenerate=True,
        generation_dependencies=dependencies,
    )

    assert regenerated.report.candidate_source_sha256 == approved.report.candidate_source_sha256
    assert regenerated.report.generation_fingerprint != approved.report.generation_fingerprint
    assert regenerated.approval_invalidated is True
    assert regenerated.report.approval is None
    assert store.status().stage == "planned"

    reapproved = run_plan(
        tmp_path,
        provider_mode="offline",
        approve_topic=topic_id,
        author="Author",
        generation_dependencies=dependencies,
    )
    assert reapproved.report.approval is not None
    (tmp_path / SOURCE_URI).write_text(
        '{"parameter": [4.0], "response": [14.0]}\n',
        encoding="utf-8",
    )

    after_evidence_change = run_plan(
        tmp_path,
        provider_mode="offline",
        generation_dependencies=dependencies,
    )

    assert (
        after_evidence_change.report.candidate_source_sha256
        == reapproved.report.candidate_source_sha256
    )
    assert after_evidence_change.report.plan_fingerprint != reapproved.report.plan_fingerprint
    assert after_evidence_change.approval_invalidated is True
    assert after_evidence_change.report.approval is None
    assert store.status().stage == "planned"


@pytest.mark.parametrize(
    "field",
    ("candidate_source_sha256", "evidence_snapshot_sha256", "generation_fingerprint"),
)
def test_generated_plan_report_rejects_each_tampered_fingerprint_input(
    tmp_path: Path, field: str
) -> None:
    store = prepared_generated_project(tmp_path)
    execution = run_plan(
        tmp_path,
        provider_mode="offline",
        generation_dependencies=generated_dependencies(
            store, synthetic_snapshot(values=(1.0, 2.0, 3.0))
        ),
    )
    payload = execution.report.model_dump(mode="json")
    payload[field] = "f" * 64

    with pytest.raises(ValidationError, match="plan fingerprint does not match source hashes"):
        PlanReport.model_validate(payload)


def test_author_source_precedence_blocks_generation_and_regenerate(tmp_path: Path) -> None:
    _store, explicit = prepared_project(tmp_path)

    execution = run_plan(tmp_path, candidates_path=explicit)

    assert execution.candidate_source_kind == "author-explicit"
    assert execution.generation is None
    with pytest.raises(PlanningInputError, match="--regenerate requires generated candidates"):
        run_plan(tmp_path, candidates_path=explicit, regenerate=True)


def test_invalid_default_author_candidate_file_does_not_fall_back_to_generation(
    tmp_path: Path,
) -> None:
    _store, default = prepared_project(tmp_path)
    default.write_text("{not valid JSON", encoding="utf-8")

    with pytest.raises(PlanningInputError):
        run_plan(tmp_path)

    assert not (
        tmp_path / ".cfdpaper" / "outputs" / "plan" / "candidate-generation-report.json"
    ).exists()


def test_default_author_source_is_resolved_after_acquiring_plan_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _store, default = prepared_project(tmp_path)
    default.unlink()

    @contextmanager
    def create_default_source_while_locking(*_args: object, **_kwargs: object):
        write_candidates(default)
        yield

    monkeypatch.setattr(planning_module, "process_file_lock", create_default_source_while_locking)

    execution = run_plan(tmp_path)

    assert execution.candidate_source_kind == "author-default"
    assert execution.generation is None


def test_author_mode_plan_report_matches_pre_slice_golden_bytes(tmp_path: Path) -> None:
    _store, _candidates = prepared_project(tmp_path)
    report = run_plan(tmp_path).report
    payload = report.model_dump(mode="json")
    payload["candidate_source_uri"] = "fixture://author-input"
    payload["generated_at"] = "2026-08-30T00:00:00Z"
    fixed = PlanReport.model_validate(payload)

    actual = plan_report_bytes(fixed)

    assert actual == bytes.fromhex(AUTHOR_PLAN_REPORT_GOLDEN_HEX)
    assert actual.endswith(b"\n")
    assert b'"generation_fingerprint"' not in actual


def corrupt_inspection(payload: dict, corruption: str) -> None:
    if corruption == "missing":
        del payload["inspection"]
    elif corruption == "null":
        payload["inspection"] = None
    elif corruption == "wrong-mode":
        payload["inspection"]["mode"] = "strict"
    elif corruption == "negative":
        payload["inspection"]["discovered"] = -1
    elif corruption == "extra":
        payload["inspection"]["unexpected"] = 1
    else:
        payload["inspection"]["discovered"] = "1"


def test_run_plan_uses_default_input_fast_inspection_and_persists_manuscript(
    tmp_path: Path,
) -> None:
    store, candidates = prepared_project(tmp_path)

    execution = run_plan(tmp_path)

    assert isinstance(execution, PlanExecution)
    assert execution.report_path == (
        tmp_path / ".cfdpaper" / "outputs" / "plan" / "topic-ranking.json"
    )
    report = PlanReport.model_validate_json(execution.report_path.read_text(encoding="utf-8"))
    assert report.candidate_source_uri == str(candidates.resolve())
    assert execution.candidate_source_kind == "author-default"
    assert execution.generation is None
    assert report.inspection.mode == "fast"
    assert report.ranking.outcome == "manuscript"
    assert report.leading_topic_id == "topic-01"
    assert report.approval is None
    assert store.status().stage == "planned"
    checkpoint = store.resume_checkpoint(execution.checkpoint_id)
    assert checkpoint.stage == "plan"
    assert checkpoint.payload["inspection"] == report.inspection.model_dump(mode="json")


def test_run_plan_explicit_candidate_path_overrides_default(tmp_path: Path) -> None:
    _store, _default = prepared_project(tmp_path)
    override = write_candidates(tmp_path / "author-input.json")

    execution = run_plan(tmp_path, candidates_path=override)
    report = execution.report

    assert report.candidate_source_uri == str(override.resolve())
    assert execution.candidate_source_kind == "author-explicit"
    assert execution.generation is None


def test_run_plan_default_candidate_provenance_resolves_symlink_target(
    tmp_path: Path,
) -> None:
    _store, default = prepared_project(tmp_path)
    target = write_candidates(tmp_path / "author-candidates.json")
    default.unlink()
    try:
        default.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable: {error}")

    report = run_plan(tmp_path).report

    assert report.candidate_source_uri == str(target.resolve())


@pytest.mark.parametrize(
    ("approve_topic", "author"),
    [("topic-01", None), (None, "Author")],
)
def test_run_plan_requires_paired_approval_inputs_before_project_access(
    tmp_path: Path,
    approve_topic: str | None,
    author: str | None,
) -> None:
    with pytest.raises(
        PlanningInputError,
        match="--approve-topic and --author must be supplied together",
    ):
        run_plan(tmp_path, approve_topic=approve_topic, author=author)


@pytest.mark.parametrize(
    ("approve_topic", "author", "message"),
    [
        ("topic-01", " \t ", "--author must contain non-whitespace characters"),
        (" \n ", "Author", "--approve-topic must contain non-whitespace characters"),
    ],
)
def test_run_plan_rejects_blank_approval_inputs_before_project_access(
    tmp_path: Path,
    approve_topic: str,
    author: str,
    message: str,
) -> None:
    with pytest.raises(PlanningInputError, match=message):
        run_plan(tmp_path, approve_topic=approve_topic, author=author)


def test_run_plan_rejects_unknown_ranked_topic_without_writing(tmp_path: Path) -> None:
    store, _candidates = prepared_project(tmp_path)
    report_path = tmp_path / ".cfdpaper" / "outputs" / "plan" / "topic-ranking.json"

    with pytest.raises(PlanningInputError, match="approval topic is not ranked: unknown"):
        run_plan(tmp_path, approve_topic=" unknown ", author="Author")

    assert store.status().stage == "initialized"
    assert not report_path.exists()


def test_run_plan_approves_defensible_topic_with_normalized_identity(tmp_path: Path) -> None:
    store, _candidates = prepared_project(tmp_path)

    execution = run_plan(tmp_path, approve_topic=" topic-01 ", author=" Dr. Author ")
    approval = execution.report.approval

    assert approval is not None
    assert approval.topic_id == "topic-01"
    assert approval.author == "Dr. Author"
    assert approval.scope == "manuscript-topic"
    assert approval.approved_at.utcoffset() is not None
    assert store.status().stage == "topic-approved"
    checkpoint = store.resume_checkpoint(execution.checkpoint_id)
    assert checkpoint.stage == "plan-approval"
    with store.connect() as connection:
        stage = connection.execute(
            "SELECT status, approved_by FROM stages WHERE stage = 'plan'"
        ).fetchone()
    assert tuple(stage) == ("approved", "Dr. Author")


def test_run_plan_selects_nonleading_nondefensible_topic_as_direction_only(
    tmp_path: Path,
) -> None:
    store, candidates = prepared_project(tmp_path)
    write_candidates(candidates, two_candidate_payload())

    execution = run_plan(tmp_path, approve_topic="topic-gap", author="Author")
    approval = execution.report.approval

    assert execution.report.ranking.outcome == "manuscript"
    assert execution.report.leading_topic_id == "topic-01"
    assert approval is not None
    assert approval.topic_id == "topic-gap"
    assert approval.scope == "direction-only"
    assert store.status().stage == "planned"
    assert store.resume_checkpoint(execution.checkpoint_id).stage == ("plan-direction-approval")
    with store.connect() as connection:
        stage = connection.execute(
            "SELECT status, approved_by FROM stages WHERE stage = 'plan'"
        ).fetchone()
    assert tuple(stage) == ("complete", None)


def test_run_plan_degrades_deleted_source_approval_to_direction_only(tmp_path: Path) -> None:
    store, _candidates = prepared_project(tmp_path)
    (tmp_path / "results.csv").unlink()

    execution = run_plan(tmp_path, approve_topic="topic-01", author="Author")
    approval = execution.report.approval

    assert execution.report.ranking.outcome == "analysis-note"
    assert approval is not None
    assert approval.scope == "direction-only"
    assert store.status().stage == "planned"
    assert store.resume_checkpoint(execution.checkpoint_id).stage == ("plan-direction-approval")
    with store.connect() as connection:
        stage = connection.execute(
            "SELECT status, approved_by FROM stages WHERE stage = 'plan'"
        ).fetchone()
    assert tuple(stage) == ("complete", None)


def test_run_plan_missing_evidence_selection_is_never_manuscript_approved(
    tmp_path: Path,
) -> None:
    store, candidates = prepared_project(tmp_path)
    payload = two_candidate_payload()
    payload["candidates"] = [payload["candidates"][1]]
    write_candidates(candidates, payload)

    execution = run_plan(tmp_path, approve_topic="topic-gap", author="Author")

    assert execution.report.ranking.outcome == "missing-evidence"
    assert execution.report.approval is not None
    assert execution.report.approval.scope == "direction-only"
    assert store.status().stage == "planned"


def test_run_plan_marks_evidence_stale_after_ordinary_source_change(tmp_path: Path) -> None:
    store, _candidates = prepared_project(tmp_path)
    source = tmp_path / "results.csv"
    original = store.get_source("results.csv")
    source.write_text("case,dp\nA,10\n", encoding="utf-8")
    stat = source.stat()
    os.utime(source, ns=(stat.st_atime_ns, original.mtime_ns + 2_000_000_000))
    assert source.stat().st_mtime_ns != original.mtime_ns

    execution = run_plan(tmp_path)
    report = execution.report

    assert report.inspection.updated == 1
    assert report.ranking.outcome == "analysis-note"
    assert "stale-evidence:ev-01" in report.ranking.missing_evidence
    assert store.status().stage == "planned"
    assert store.resume_checkpoint(execution.checkpoint_id).stage == "plan"


def test_run_plan_records_deleted_source_as_stale(tmp_path: Path) -> None:
    store, _candidates = prepared_project(tmp_path)
    (tmp_path / "results.csv").unlink()

    execution = run_plan(tmp_path)
    report = execution.report

    assert report.inspection.stale == 1
    assert report.ranking.outcome == "analysis-note"
    assert store.status().stage == "planned"
    assert store.resume_checkpoint(execution.checkpoint_id).stage == "plan"


def test_run_plan_persists_missing_evidence_for_empty_candidates(tmp_path: Path) -> None:
    store, candidates = prepared_project(tmp_path)
    write_candidates(candidates, {"schema_version": 1, "candidates": []})

    execution = run_plan(tmp_path)
    report = execution.report

    assert report.ranking.outcome == "missing-evidence"
    assert report.leading_topic_id is None
    assert store.status().stage == "planned"
    assert store.resume_checkpoint(execution.checkpoint_id).stage == "plan"


def test_fast_plan_does_not_claim_same_size_same_mtime_detection(tmp_path: Path) -> None:
    store, _candidates = prepared_project(tmp_path)
    source = tmp_path / "results.csv"
    original = store.get_source("results.csv")
    source.write_bytes(b"case,dp\nA,10\n")
    stat = source.stat()
    os.utime(source, ns=(stat.st_atime_ns, original.mtime_ns))

    execution = run_plan(tmp_path)

    assert execution.current_inspection.unchanged == 1
    assert execution.report.inspection.mode == "fast"


def test_identical_unapproved_plan_reuses_report_and_checkpoint(tmp_path: Path) -> None:
    prepared_project(tmp_path)
    first = run_plan(tmp_path)
    first_bytes = first.report_path.read_bytes()

    second = run_plan(tmp_path)

    assert second.report_path.read_bytes() == first_bytes
    assert second.report.generated_at == first.report.generated_at
    assert second.checkpoint_id == first.checkpoint_id


def test_unchanged_approved_plan_without_flags_preserves_approval_and_checkpoint(
    tmp_path: Path,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    first = run_plan(tmp_path, approve_topic="topic-01", author="Author")
    first_bytes = first.report_path.read_bytes()
    first_approval = first.report.approval
    first_checkpoint = store.resume_checkpoint(first.checkpoint_id)

    second = run_plan(tmp_path)

    assert first_approval is not None
    assert second.report.approval == first_approval
    assert second.report_path.read_bytes() == first_bytes
    assert second.report.generated_at == first.report.generated_at
    assert second.checkpoint_id == first.checkpoint_id
    assert second.report.approval is not None
    assert second.report.approval.approved_at == first_approval.approved_at
    assert store.resume_checkpoint(second.checkpoint_id).payload == first_checkpoint.payload
    assert second.approval_invalidated is False
    assert store.status().stage == "topic-approved"


def test_unchanged_direction_approval_without_flags_preserves_checkpoint(
    tmp_path: Path,
) -> None:
    store, candidates = prepared_project(tmp_path)
    write_candidates(candidates, two_candidate_payload())
    first = run_plan(tmp_path, approve_topic="topic-gap", author="Author")
    first_bytes = first.report_path.read_bytes()
    first_checkpoint = store.resume_checkpoint(first.checkpoint_id)
    assert first.report.approval is not None

    second = run_plan(tmp_path)

    assert second.report_path.read_bytes() == first_bytes
    assert second.report.approval == first.report.approval
    assert second.report.approval is not None
    assert second.report.approval.approved_at == first.report.approval.approved_at
    assert second.checkpoint_id == first.checkpoint_id
    assert store.resume_checkpoint(second.checkpoint_id).payload == first_checkpoint.payload
    assert second.approval_invalidated is False
    assert store.status().stage == "planned"


def test_identical_explicit_approval_reuses_report_timestamp_and_checkpoint(
    tmp_path: Path,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    first = run_plan(tmp_path, approve_topic="topic-01", author="Author")
    first_bytes = first.report_path.read_bytes()
    first_checkpoint = store.resume_checkpoint(first.checkpoint_id)
    assert first.report.approval is not None

    second = run_plan(
        tmp_path,
        approve_topic=" topic-01 ",
        author="  Author  ",
    )

    assert second.report_path.read_bytes() == first_bytes
    assert second.report.generated_at == first.report.generated_at
    assert second.report.approval is not None
    assert second.report.approval.approved_at == first.report.approval.approved_at
    assert second.checkpoint_id == first.checkpoint_id
    assert store.resume_checkpoint(second.checkpoint_id).payload == first_checkpoint.payload
    assert second.approval_invalidated is False


def test_explicit_approval_can_return_to_a_historical_author_identity(
    tmp_path: Path,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    first_a = run_plan(tmp_path, approve_topic="topic-01", author="Author A")
    first_a_checkpoint = store.resume_checkpoint(first_a.checkpoint_id)
    first_a_approval = first_a.report.approval
    assert first_a_approval is not None
    approval_b = run_plan(tmp_path, approve_topic="topic-01", author="Author B")
    returned_a = run_plan(tmp_path, approve_topic="topic-01", author=" Author A ")

    assert returned_a.checkpoint_id == first_a.checkpoint_id
    assert returned_a.report.approval == first_a_approval
    assert returned_a.report.approval is not None
    assert returned_a.report.approval.approved_at == first_a_approval.approved_at
    assert returned_a.checkpoint_id != approval_b.checkpoint_id
    assert store.resume_checkpoint(returned_a.checkpoint_id).payload == first_a_checkpoint.payload
    with store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 2
        stage = connection.execute(
            "SELECT status, outputs_json, approved_by FROM stages WHERE stage = 'plan'"
        ).fetchone()
    assert tuple(stage)[::2] == ("approved", "Author A")
    assert json.loads(stage["outputs_json"])["approval"] == first_a_approval.model_dump(mode="json")


@pytest.mark.parametrize(
    "corruption",
    ["missing", "null", "wrong-mode", "negative", "extra", "non-int"],
)
def test_explicit_historical_switch_rejects_invalid_target_inspection(
    tmp_path: Path,
    corruption: str,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    approval_a = run_plan(tmp_path, approve_topic="topic-01", author="Author A")
    approval_b = run_plan(tmp_path, approve_topic="topic-01", author="Author B")
    with store.connect() as connection:
        target_payload = json.loads(
            connection.execute(
                "SELECT payload_json FROM checkpoints WHERE checkpoint_id = ?",
                (approval_a.checkpoint_id,),
            ).fetchone()[0]
        )
        corrupt_inspection(target_payload, corruption)
        connection.execute(
            "UPDATE checkpoints SET payload_json = ? WHERE checkpoint_id = ?",
            (json.dumps(target_payload, sort_keys=True), approval_a.checkpoint_id),
        )
        stage_before = tuple(
            connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone()
        )
        checkpoints_before = [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM checkpoints ORDER BY checkpoint_id"
            ).fetchall()
        ]
    report_before = approval_b.report_path.read_bytes()

    with pytest.raises(PlanningWriteError, match="deterministic checkpoint ID collision"):
        run_plan(tmp_path, approve_topic="topic-01", author="Author A")

    assert approval_b.report_path.read_bytes() == report_before
    with store.connect() as connection:
        assert (
            tuple(connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone())
            == stage_before
        )
        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM checkpoints ORDER BY checkpoint_id"
            ).fetchall()
        ] == checkpoints_before


def test_explicit_approval_can_return_across_historical_scopes(tmp_path: Path) -> None:
    store, candidates = prepared_project(tmp_path)
    write_candidates(candidates, two_candidate_payload())
    manuscript = run_plan(tmp_path, approve_topic="topic-01", author="Author")
    manuscript_approval = manuscript.report.approval
    assert manuscript_approval is not None

    direction = run_plan(tmp_path, approve_topic="topic-gap", author="Author")
    assert direction.report.approval is not None
    assert direction.report.approval.scope == "direction-only"
    with store.connect() as connection:
        direction_stage = connection.execute(
            "SELECT status, approved_by FROM stages WHERE stage = 'plan'"
        ).fetchone()
    assert tuple(direction_stage) == ("complete", None)

    returned = run_plan(tmp_path, approve_topic="topic-01", author="Author")

    assert returned.checkpoint_id == manuscript.checkpoint_id
    assert returned.report.approval == manuscript_approval
    assert returned.report.approval is not None
    assert returned.report.approval.scope == "manuscript-topic"
    with store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 2
        returned_stage = connection.execute(
            "SELECT status, approved_by FROM stages WHERE stage = 'plan'"
        ).fetchone()
    assert tuple(returned_stage) == ("approved", "Author")


@pytest.mark.parametrize("corruption", ["report", "stage", "checkpoint"])
def test_explicit_historical_switch_rejects_current_identity_tamper(
    tmp_path: Path,
    corruption: str,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    approval_a = run_plan(tmp_path, approve_topic="topic-01", author="Author A")
    approval_b = run_plan(tmp_path, approve_topic="topic-01", author="Author B")
    if corruption == "report":
        report_payload = json.loads(approval_b.report_path.read_text(encoding="utf-8"))
        report_payload["approval"]["approved_at"] = "2035-01-02T03:04:05Z"
        approval_b.report_path.write_text(json.dumps(report_payload), encoding="utf-8")
    else:
        with store.connect() as connection:
            table = "stages" if corruption == "stage" else "checkpoints"
            json_column = "outputs_json" if corruption == "stage" else "payload_json"
            where = "stage = 'plan'" if corruption == "stage" else "checkpoint_id = ?"
            parameters = () if corruption == "stage" else (approval_b.checkpoint_id,)
            payload = json.loads(
                connection.execute(
                    f"SELECT {json_column} FROM {table} WHERE {where}",  # noqa: S608
                    parameters,
                ).fetchone()[0]
            )
            payload["approval"]["approved_at"] = "2035-01-02T03:04:05Z"
            connection.execute(
                f"UPDATE {table} SET {json_column} = ? WHERE {where}",  # noqa: S608
                (json.dumps(payload, sort_keys=True), *parameters),
            )
    report_before = approval_b.report_path.read_bytes()
    with store.connect() as connection:
        stage_before = tuple(
            connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone()
        )
        checkpoints_before = [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM checkpoints ORDER BY checkpoint_id"
            ).fetchall()
        ]

    with pytest.raises(PlanningWriteError, match="deterministic checkpoint ID collision"):
        run_plan(tmp_path, approve_topic="topic-01", author="Author A")

    assert approval_b.report_path.read_bytes() == report_before
    with store.connect() as connection:
        assert (
            tuple(connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone())
            == stage_before
        )
        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM checkpoints ORDER BY checkpoint_id"
            ).fetchall()
        ] == checkpoints_before
    assert store.status().stage == "topic-approved"
    assert approval_a.checkpoint_id != approval_b.checkpoint_id


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("outcome", "analysis-note"),
        ("author", "Mallory"),
        ("scope", "direction-only"),
        ("approved_at", "2035-01-02T03:04:05"),
    ],
)
def test_explicit_historical_switch_rejects_invalid_target_checkpoint(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    approval_a = run_plan(tmp_path, approve_topic="topic-01", author="Author A")
    approval_b = run_plan(tmp_path, approve_topic="topic-01", author="Author B")
    with store.connect() as connection:
        payload = json.loads(
            connection.execute(
                "SELECT payload_json FROM checkpoints WHERE checkpoint_id = ?",
                (approval_a.checkpoint_id,),
            ).fetchone()[0]
        )
        if field == "outcome":
            payload[field] = value
        else:
            payload["approval"][field] = value
        connection.execute(
            "UPDATE checkpoints SET payload_json = ? WHERE checkpoint_id = ?",
            (json.dumps(payload, sort_keys=True), approval_a.checkpoint_id),
        )
        stage_before = tuple(
            connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone()
        )
        checkpoints_before = [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM checkpoints ORDER BY checkpoint_id"
            ).fetchall()
        ]
    report_before = approval_b.report_path.read_bytes()

    with pytest.raises(PlanningWriteError, match="deterministic checkpoint ID collision"):
        run_plan(tmp_path, approve_topic="topic-01", author="Author A")

    assert approval_b.report_path.read_bytes() == report_before
    with store.connect() as connection:
        assert (
            tuple(connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone())
            == stage_before
        )
        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM checkpoints ORDER BY checkpoint_id"
            ).fetchall()
        ] == checkpoints_before


@pytest.mark.parametrize("report_state", ["deleted", "invalid"])
@pytest.mark.parametrize(
    ("selected_topic", "scope"),
    [
        ("topic-01", "manuscript-topic"),
        ("topic-gap", "direction-only"),
    ],
)
def test_explicit_approval_recovers_report_from_semantic_checkpoint(
    tmp_path: Path,
    report_state: str,
    selected_topic: str,
    scope: str,
) -> None:
    store, candidates = prepared_project(tmp_path)
    if selected_topic == "topic-gap":
        write_candidates(candidates, two_candidate_payload())
    first = run_plan(tmp_path, approve_topic=selected_topic, author="Author")
    first_checkpoint = store.resume_checkpoint(first.checkpoint_id)
    first_approval = first.report.approval
    assert first_approval is not None
    if report_state == "deleted":
        first.report_path.unlink()
    else:
        first.report_path.write_bytes(b"invalid-private-report\xff")

    recovered = run_plan(
        tmp_path,
        approve_topic=f" {selected_topic} ",
        author="  Author  ",
    )

    assert recovered.report.approval == first_approval
    assert recovered.report.approval is not None
    assert recovered.report.approval.scope == scope
    assert recovered.report.approval.approved_at == first_approval.approved_at
    assert recovered.report.approval.model_dump(mode="json") == first_checkpoint.payload["approval"]
    assert recovered.checkpoint_id == first.checkpoint_id
    assert store.resume_checkpoint(recovered.checkpoint_id).payload == first_checkpoint.payload
    PlanReport.model_validate_json(recovered.report_path.read_text(encoding="utf-8"))
    with store.connect() as connection:
        checkpoint_count = connection.execute(
            "SELECT COUNT(*) FROM checkpoints WHERE checkpoint_id = ?",
            (first.checkpoint_id,),
        ).fetchone()[0]
        stage_payload = json.loads(
            connection.execute("SELECT outputs_json FROM stages WHERE stage = 'plan'").fetchone()[0]
        )
    assert checkpoint_count == 1
    assert stage_payload == first_checkpoint.payload


def test_ordinary_evidence_change_invalidates_old_approval_and_downgrades_stage(
    tmp_path: Path,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    first = run_plan(tmp_path, approve_topic="topic-01", author="Author")
    source = tmp_path / "results.csv"
    original = store.get_source("results.csv")
    source.write_text("case,dp\nA,10\n", encoding="utf-8")
    stat = source.stat()
    os.utime(source, ns=(stat.st_atime_ns, original.mtime_ns + 2_000_000_000))

    second = run_plan(tmp_path)

    assert second.report.plan_fingerprint != first.report.plan_fingerprint
    assert second.approval_invalidated is True
    assert second.report.approval is None
    assert second.report.ranking.outcome == "analysis-note"
    assert store.status().stage == "planned"
    assert store.resume_checkpoint(second.checkpoint_id).stage == "plan"
    with store.connect() as connection:
        stage = connection.execute(
            "SELECT status, approved_by FROM stages WHERE stage = 'plan'"
        ).fetchone()
    assert tuple(stage) == ("complete", None)


def test_approved_report_copied_to_another_project_is_invalidated(tmp_path: Path) -> None:
    _store_a, _candidates_a = prepared_project(tmp_path / "project-a", project_id="project-a")
    approved = run_plan(
        tmp_path / "project-a",
        approve_topic="topic-01",
        author="Author",
    )
    store_b, _candidates_b = prepared_project(tmp_path / "project-b", project_id="project-b")
    report_b = tmp_path / "project-b" / ".cfdpaper" / "outputs" / "plan" / "topic-ranking.json"
    report_b.parent.mkdir(parents=True, exist_ok=True)
    report_b.write_bytes(approved.report_path.read_bytes())

    execution = run_plan(tmp_path / "project-b")

    assert execution.report.project_id == "project-b"
    assert execution.approval_invalidated is True
    assert execution.report.approval is None
    assert store_b.status().stage == "planned"


def test_same_candidate_bytes_at_new_uri_refreshes_provenance_but_preserves_approval(
    tmp_path: Path,
) -> None:
    store, candidates = prepared_project(tmp_path)
    first = run_plan(tmp_path, approve_topic="topic-01", author="Author")
    first_bytes = first.report_path.read_bytes()
    alternate = tmp_path / ".cfdpaper" / "inputs" / "alternate-topic-candidates.json"
    alternate.parent.mkdir(parents=True, exist_ok=True)
    alternate.write_bytes(candidates.read_bytes())

    second = run_plan(tmp_path, candidates_path=alternate)

    assert second.report.plan_fingerprint == first.report.plan_fingerprint
    assert second.report.candidate_source_uri == str(alternate.resolve())
    assert second.report.approval == first.report.approval
    assert second.approval_invalidated is False
    assert second.report_path.read_bytes() != first_bytes
    assert second.checkpoint_id == first.checkpoint_id
    assert store.status().stage == "topic-approved"


def test_candidate_uri_and_inspection_change_reuses_semantic_checkpoint_payload(
    tmp_path: Path,
) -> None:
    store, candidates = prepared_project(tmp_path)
    first = run_plan(tmp_path, approve_topic="topic-01", author="Author")
    first_checkpoint = store.resume_checkpoint(first.checkpoint_id)
    alternate = tmp_path / "alternate-topic-candidates.json"
    alternate.write_bytes(candidates.read_bytes())

    second = run_plan(tmp_path, candidates_path=alternate)

    assert second.current_inspection.added == 1
    assert second.report.inspection.added == 1
    assert second.report.candidate_source_uri == str(alternate.resolve())
    assert second.report.approval == first.report.approval
    assert second.approval_invalidated is False
    assert second.checkpoint_id == first.checkpoint_id
    assert store.resume_checkpoint(second.checkpoint_id).payload == first_checkpoint.payload
    with store.connect() as connection:
        checkpoint_count = connection.execute(
            "SELECT COUNT(*) FROM checkpoints WHERE checkpoint_id = ?",
            (first.checkpoint_id,),
        ).fetchone()[0]
        stage_payload = json.loads(
            connection.execute("SELECT outputs_json FROM stages WHERE stage = 'plan'").fetchone()[0]
        )
    assert checkpoint_count == 1
    assert stage_payload == first_checkpoint.payload
    assert stage_payload["inspection"] != second.current_inspection.model_dump(mode="json")


@pytest.mark.parametrize("tampered_field", ["outcome", "approval"])
def test_tampered_checkpoint_core_fails_closed_before_report_replace(
    tmp_path: Path,
    tampered_field: str,
) -> None:
    store, candidates = prepared_project(tmp_path)
    first = run_plan(tmp_path, approve_topic="topic-01", author="Author")
    report_bytes = first.report_path.read_bytes()
    checkpoint = store.resume_checkpoint(first.checkpoint_id)
    tampered_payload = dict(checkpoint.payload)
    if tampered_field == "outcome":
        tampered_payload["outcome"] = "analysis-note"
    else:
        tampered_approval = dict(tampered_payload["approval"])
        tampered_approval["author"] = "Mallory"
        tampered_payload["approval"] = tampered_approval
    with store.connect() as connection:
        connection.execute(
            "UPDATE checkpoints SET payload_json = ? WHERE checkpoint_id = ?",
            (json.dumps(tampered_payload, sort_keys=True), first.checkpoint_id),
        )
        stage_before = tuple(
            connection.execute(
                "SELECT status, outputs_json, approved_by, updated_at "
                "FROM stages WHERE stage = 'plan'"
            ).fetchone()
        )
    alternate = tmp_path / ".cfdpaper" / "inputs" / "alternate-topic-candidates.json"
    alternate.write_bytes(candidates.read_bytes())

    with pytest.raises(PlanningWriteError, match="deterministic checkpoint ID collision"):
        run_plan(tmp_path, candidates_path=alternate)

    with store.connect() as connection:
        stage_after = tuple(
            connection.execute(
                "SELECT status, outputs_json, approved_by, updated_at "
                "FROM stages WHERE stage = 'plan'"
            ).fetchone()
        )
    assert first.report_path.read_bytes() == report_bytes
    assert stage_after == stage_before
    assert store.status().stage == "topic-approved"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("approved_at", "2026-08-29T00:00:00"),
        ("author", "Mallory"),
        ("scope", "direction-only"),
    ],
)
def test_invalid_stored_approval_cannot_recover_damaged_report(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    first = run_plan(tmp_path, approve_topic="topic-01", author="Author")
    checkpoint = store.resume_checkpoint(first.checkpoint_id)
    tampered_payload = dict(checkpoint.payload)
    tampered_approval = dict(tampered_payload["approval"])
    tampered_approval[field] = value
    tampered_payload["approval"] = tampered_approval
    with store.connect() as connection:
        connection.execute(
            "UPDATE checkpoints SET payload_json = ? WHERE checkpoint_id = ?",
            (json.dumps(tampered_payload, sort_keys=True), first.checkpoint_id),
        )
        stage_before = tuple(
            connection.execute(
                "SELECT status, outputs_json, approved_by, updated_at "
                "FROM stages WHERE stage = 'plan'"
            ).fetchone()
        )
    damaged_report = b"invalid-private-report\xff"
    first.report_path.write_bytes(damaged_report)

    with pytest.raises(PlanningWriteError, match="deterministic checkpoint ID collision"):
        run_plan(tmp_path, approve_topic="topic-01", author=" Author ")

    with store.connect() as connection:
        stage_after = tuple(
            connection.execute(
                "SELECT status, outputs_json, approved_by, updated_at "
                "FROM stages WHERE stage = 'plan'"
            ).fetchone()
        )
    assert first.report_path.read_bytes() == damaged_report
    assert stage_after == stage_before
    assert store.status().stage == "topic-approved"


@pytest.mark.parametrize("report_state", ["valid", "invalid", "deleted"])
def test_checkpoint_aware_timestamp_tamper_cannot_replace_report(
    tmp_path: Path,
    report_state: str,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    first = run_plan(tmp_path, approve_topic="topic-01", author="Author")
    checkpoint = store.resume_checkpoint(first.checkpoint_id)
    tampered_payload = dict(checkpoint.payload)
    tampered_approval = dict(tampered_payload["approval"])
    tampered_approval["approved_at"] = "2031-09-01T12:30:00Z"
    tampered_payload["approval"] = tampered_approval
    with store.connect() as connection:
        connection.execute(
            "UPDATE checkpoints SET payload_json = ? WHERE checkpoint_id = ?",
            (json.dumps(tampered_payload, sort_keys=True), first.checkpoint_id),
        )
        stage_before = tuple(
            connection.execute(
                "SELECT status, outputs_json, approved_by, updated_at "
                "FROM stages WHERE stage = 'plan'"
            ).fetchone()
        )
    if report_state == "invalid":
        first.report_path.write_bytes(b"invalid-private-report\xff")
    elif report_state == "deleted":
        first.report_path.unlink()
    report_before = first.report_path.read_bytes() if first.report_path.exists() else None

    with pytest.raises(PlanningWriteError, match="deterministic checkpoint ID collision"):
        run_plan(tmp_path, approve_topic=" topic-01 ", author=" Author ")

    report_after = first.report_path.read_bytes() if first.report_path.exists() else None
    with store.connect() as connection:
        stage_after = tuple(
            connection.execute(
                "SELECT status, outputs_json, approved_by, updated_at "
                "FROM stages WHERE stage = 'plan'"
            ).fetchone()
        )
    assert report_after == report_before
    assert stage_after == stage_before
    assert store.status().stage == "topic-approved"


@pytest.mark.parametrize(
    "corruption",
    [
        "stage-approved-at",
        "stage-approval-missing",
        "stage-json-invalid",
        "stage-row-missing",
        "stage-status",
        "stage-approved-by",
        "checkpoint-row-missing",
    ],
)
def test_missing_or_inconsistent_transition_replica_fails_closed(
    tmp_path: Path,
    corruption: str,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    first = run_plan(tmp_path, approve_topic="topic-01", author="Author")
    report_before = first.report_path.read_bytes()
    with store.connect() as connection:
        if corruption in {"stage-approved-at", "stage-approval-missing"}:
            stage_payload = json.loads(
                connection.execute(
                    "SELECT outputs_json FROM stages WHERE stage = 'plan'"
                ).fetchone()[0]
            )
            if corruption == "stage-approved-at":
                stage_payload["approval"]["approved_at"] = "2032-01-02T03:04:05Z"
            else:
                stage_payload["approval"] = None
            connection.execute(
                "UPDATE stages SET outputs_json = ? WHERE stage = 'plan'",
                (json.dumps(stage_payload, sort_keys=True),),
            )
        elif corruption == "stage-json-invalid":
            connection.execute("UPDATE stages SET outputs_json = '{' WHERE stage = 'plan'")
        elif corruption == "stage-row-missing":
            connection.execute("DELETE FROM stages WHERE stage = 'plan'")
        elif corruption == "stage-status":
            connection.execute("UPDATE stages SET status = 'complete' WHERE stage = 'plan'")
        elif corruption == "stage-approved-by":
            connection.execute("UPDATE stages SET approved_by = 'Mallory' WHERE stage = 'plan'")
        else:
            connection.execute(
                "DELETE FROM checkpoints WHERE checkpoint_id = ?",
                (first.checkpoint_id,),
            )
        stage_before = connection.execute(
            "SELECT status, outputs_json, approved_by, updated_at FROM stages WHERE stage = 'plan'"
        ).fetchone()
        checkpoint_before = connection.execute(
            "SELECT stage, payload_json, created_at FROM checkpoints WHERE checkpoint_id = ?",
            (first.checkpoint_id,),
        ).fetchone()
        stage_before = tuple(stage_before) if stage_before is not None else None
        checkpoint_before = tuple(checkpoint_before) if checkpoint_before is not None else None

    with pytest.raises(PlanningWriteError, match="deterministic checkpoint ID collision"):
        run_plan(tmp_path, approve_topic="topic-01", author="Author")

    with store.connect() as connection:
        stage_after = connection.execute(
            "SELECT status, outputs_json, approved_by, updated_at FROM stages WHERE stage = 'plan'"
        ).fetchone()
        checkpoint_after = connection.execute(
            "SELECT stage, payload_json, created_at FROM checkpoints WHERE checkpoint_id = ?",
            (first.checkpoint_id,),
        ).fetchone()
        stage_after = tuple(stage_after) if stage_after is not None else None
        checkpoint_after = tuple(checkpoint_after) if checkpoint_after is not None else None
    assert first.report_path.read_bytes() == report_before
    assert stage_after == stage_before
    assert checkpoint_after == checkpoint_before
    assert store.status().stage == "topic-approved"


@pytest.mark.parametrize(
    ("selected_topic", "project_stage"),
    [("topic-01", "topic-approved"), ("topic-gap", "planned")],
)
@pytest.mark.parametrize(
    "corruption",
    [
        "stage-approved-at",
        "stage-status",
        "stage-approved-by",
        "stage-approval-missing",
        "stage-approval-invalid",
        "checkpoint-approved-at",
        "checkpoint-approval-missing",
        "checkpoint-approval-invalid",
    ],
)
def test_no_flags_preserved_approval_rejects_transition_replica_tamper(
    tmp_path: Path,
    selected_topic: str,
    project_stage: str,
    corruption: str,
) -> None:
    store, candidates = prepared_project(tmp_path)
    if selected_topic == "topic-gap":
        write_candidates(candidates, two_candidate_payload())
    first = run_plan(tmp_path, approve_topic=selected_topic, author="Author")
    report_before = first.report_path.read_bytes()
    with store.connect() as connection:
        if corruption.startswith("stage-"):
            if corruption == "stage-status":
                tampered_status = "approved" if project_stage == "planned" else "complete"
                connection.execute(
                    "UPDATE stages SET status = ? WHERE stage = 'plan'",
                    (tampered_status,),
                )
            elif corruption == "stage-approved-by":
                connection.execute("UPDATE stages SET approved_by = 'Mallory' WHERE stage = 'plan'")
            else:
                stage_payload = json.loads(
                    connection.execute(
                        "SELECT outputs_json FROM stages WHERE stage = 'plan'"
                    ).fetchone()[0]
                )
                if corruption == "stage-approved-at":
                    stage_payload["approval"]["approved_at"] = "2033-02-03T04:05:06Z"
                elif corruption == "stage-approval-missing":
                    stage_payload["approval"] = None
                else:
                    stage_payload["approval"]["approved_at"] = "2033-02-03T04:05:06"
                connection.execute(
                    "UPDATE stages SET outputs_json = ? WHERE stage = 'plan'",
                    (json.dumps(stage_payload, sort_keys=True),),
                )
        else:
            checkpoint_payload = json.loads(
                connection.execute(
                    "SELECT payload_json FROM checkpoints WHERE checkpoint_id = ?",
                    (first.checkpoint_id,),
                ).fetchone()[0]
            )
            if corruption == "checkpoint-approved-at":
                checkpoint_payload["approval"]["approved_at"] = "2034-03-04T05:06:07Z"
            elif corruption == "checkpoint-approval-missing":
                checkpoint_payload["approval"] = None
            else:
                checkpoint_payload["approval"]["approved_at"] = "2034-03-04T05:06:07"
            connection.execute(
                "UPDATE checkpoints SET payload_json = ? WHERE checkpoint_id = ?",
                (json.dumps(checkpoint_payload, sort_keys=True), first.checkpoint_id),
            )
        stage_before = connection.execute(
            "SELECT status, outputs_json, approved_by, updated_at FROM stages WHERE stage = 'plan'"
        ).fetchone()
        checkpoint_before = connection.execute(
            "SELECT stage, payload_json, created_at FROM checkpoints WHERE checkpoint_id = ?",
            (first.checkpoint_id,),
        ).fetchone()
        stage_before = tuple(stage_before)
        checkpoint_before = tuple(checkpoint_before)

    with pytest.raises(PlanningWriteError, match="deterministic checkpoint ID collision"):
        run_plan(tmp_path)

    with store.connect() as connection:
        stage_after = tuple(
            connection.execute(
                "SELECT status, outputs_json, approved_by, updated_at "
                "FROM stages WHERE stage = 'plan'"
            ).fetchone()
        )
        checkpoint_after = tuple(
            connection.execute(
                "SELECT stage, payload_json, created_at FROM checkpoints WHERE checkpoint_id = ?",
                (first.checkpoint_id,),
            ).fetchone()
        )
    assert first.report_path.read_bytes() == report_before
    assert stage_after == stage_before
    assert checkpoint_after == checkpoint_before
    assert store.status().stage == project_stage


@pytest.mark.parametrize(
    "corruption",
    ["missing", "null", "wrong-mode", "negative", "extra", "non-int"],
)
def test_no_flags_rejects_matching_invalid_current_inspections(
    tmp_path: Path,
    corruption: str,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    first = run_plan(tmp_path, approve_topic="topic-01", author="Author")
    report_before = first.report_path.read_bytes()
    with store.connect() as connection:
        stage_payload = json.loads(
            connection.execute("SELECT outputs_json FROM stages WHERE stage = 'plan'").fetchone()[0]
        )
        corrupt_inspection(stage_payload, corruption)
        raw_payload = json.dumps(stage_payload, sort_keys=True)
        connection.execute(
            "UPDATE stages SET outputs_json = ? WHERE stage = 'plan'",
            (raw_payload,),
        )
        connection.execute(
            "UPDATE checkpoints SET payload_json = ? WHERE checkpoint_id = ?",
            (raw_payload, first.checkpoint_id),
        )
        stage_before = tuple(
            connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone()
        )
        checkpoint_before = tuple(
            connection.execute(
                "SELECT * FROM checkpoints WHERE checkpoint_id = ?",
                (first.checkpoint_id,),
            ).fetchone()
        )

    with pytest.raises(PlanningWriteError, match="deterministic checkpoint ID collision"):
        run_plan(tmp_path)

    assert first.report_path.read_bytes() == report_before
    with store.connect() as connection:
        assert (
            tuple(connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone())
            == stage_before
        )
        assert (
            tuple(
                connection.execute(
                    "SELECT * FROM checkpoints WHERE checkpoint_id = ?",
                    (first.checkpoint_id,),
                ).fetchone()
            )
            == checkpoint_before
        )


@pytest.mark.parametrize("replica", ["stage", "checkpoint"])
def test_no_flags_rejects_one_sided_current_inspection_change(
    tmp_path: Path,
    replica: str,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    first = run_plan(tmp_path, approve_topic="topic-01", author="Author")
    report_before = first.report_path.read_bytes()
    with store.connect() as connection:
        table = "stages" if replica == "stage" else "checkpoints"
        column = "outputs_json" if replica == "stage" else "payload_json"
        where = "stage = 'plan'" if replica == "stage" else "checkpoint_id = ?"
        parameters = () if replica == "stage" else (first.checkpoint_id,)
        payload = json.loads(
            connection.execute(
                f"SELECT {column} FROM {table} WHERE {where}",  # noqa: S608
                parameters,
            ).fetchone()[0]
        )
        payload["inspection"]["discovered"] += 1
        connection.execute(
            f"UPDATE {table} SET {column} = ? WHERE {where}",  # noqa: S608
            (json.dumps(payload, sort_keys=True), *parameters),
        )
        stage_before = tuple(
            connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone()
        )
        checkpoint_before = tuple(
            connection.execute(
                "SELECT * FROM checkpoints WHERE checkpoint_id = ?",
                (first.checkpoint_id,),
            ).fetchone()
        )

    with pytest.raises(PlanningWriteError, match="deterministic checkpoint ID collision"):
        run_plan(tmp_path)

    assert first.report_path.read_bytes() == report_before
    with store.connect() as connection:
        assert (
            tuple(connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone())
            == stage_before
        )
        assert (
            tuple(
                connection.execute(
                    "SELECT * FROM checkpoints WHERE checkpoint_id = ?",
                    (first.checkpoint_id,),
                ).fetchone()
            )
            == checkpoint_before
        )


def test_semantically_tampered_approved_report_cannot_preserve_approval(
    tmp_path: Path,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    approved = run_plan(tmp_path, approve_topic="topic-01", author="Author")
    payload = json.loads(approved.report_path.read_text(encoding="utf-8"))
    payload["ranking"]["outcome"] = "analysis-note"
    payload["ranking"]["reason"] = "Tampered but schema-valid ranking."
    payload["ranking"]["ranked_topics"][0]["defensible"] = False
    payload["ranking"]["ranked_topics"][0]["score"] = 0.1
    payload["approval"]["scope"] = "direction-only"
    tampered = PlanReport.model_validate(payload)
    approved.report_path.write_text(tampered.model_dump_json(indent=2) + "\n", encoding="utf-8")

    execution = run_plan(tmp_path)

    assert execution.approval_invalidated is True
    assert execution.report.ranking.outcome == "manuscript"
    assert execution.report.ranking.ranked_topics[0].defensible is True
    assert execution.report.approval is None
    assert store.status().stage == "planned"


@pytest.mark.parametrize(
    ("approve_topic", "author", "scope"),
    [
        ("topic-01", "Second Author", "manuscript-topic"),
        ("topic-gap", "First Author", "direction-only"),
    ],
)
def test_different_explicit_approval_gets_new_checkpoint_and_timestamp(
    tmp_path: Path,
    approve_topic: str,
    author: str,
    scope: str,
) -> None:
    store, candidates = prepared_project(tmp_path)
    write_candidates(candidates, two_candidate_payload())
    first = run_plan(tmp_path, approve_topic="topic-01", author="First Author")
    first_bytes = first.report_path.read_bytes()
    assert first.report.approval is not None

    second = run_plan(tmp_path, approve_topic=approve_topic, author=author)

    assert second.report_path.read_bytes() != first_bytes
    assert second.report.approval is not None
    assert second.report.approval.topic_id == approve_topic
    assert second.report.approval.author == author
    assert second.report.approval.scope == scope
    assert second.report.approval.approved_at != first.report.approval.approved_at
    assert second.checkpoint_id != first.checkpoint_id
    assert second.approval_invalidated is False
    with store.connect() as connection:
        checkpoint_count = connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]
    assert checkpoint_count == 2


def test_run_plan_replaces_semantically_tampered_valid_existing_report(
    tmp_path: Path,
) -> None:
    prepared_project(tmp_path)
    first = run_plan(tmp_path)
    payload = json.loads(first.report_path.read_text(encoding="utf-8"))
    payload["ranking"]["outcome"] = "analysis-note"
    payload["ranking"]["reason"] = "Tampered but schema-valid ranking."
    payload["ranking"]["ranked_topics"][0]["defensible"] = False
    payload["ranking"]["ranked_topics"][0]["score"] = 0.1
    tampered = PlanReport.model_validate(payload)
    tampered_bytes = (tampered.model_dump_json(indent=2) + "\n").encode("utf-8")
    first.report_path.write_bytes(tampered_bytes)
    with ProjectStore.open(tmp_path).connect() as connection:
        connection.execute("DELETE FROM checkpoints")
        connection.execute("DELETE FROM stages WHERE stage = 'plan'")
        connection.execute("UPDATE project_state SET stage = 'initialized'")

    execution = run_plan(tmp_path)

    assert execution.report.ranking.outcome == "manuscript"
    assert execution.report.ranking.ranked_topics[0].defensible is True
    assert execution.report_path.read_bytes() != tampered_bytes


def test_invalid_existing_report_error_does_not_echo_secret_input(
    tmp_path: Path,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    report_path = tmp_path / ".cfdpaper" / "outputs" / "plan" / "topic-ranking.json"
    payload = PlanReport.model_validate(
        report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    ).model_dump(mode="json")
    payload["secret_token"] = "swordfish-secret"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PlanningInputError) as captured:
        run_plan(tmp_path)

    message = str(captured.value)
    assert "existing planning report cannot be validated" in message
    assert "swordfish-secret" not in message
    assert "errors.pydantic.dev" not in message
    assert store.status().stage == "initialized"


def test_existing_report_custom_validation_error_is_generic(
    tmp_path: Path,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    report_path = tmp_path / ".cfdpaper" / "outputs" / "plan" / "topic-ranking.json"
    payload = PlanReport.model_validate(
        report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    ).model_dump(mode="json")
    payload["approval"] = {
        "topic_id": "swordfish-secret",
        "author": "Author",
        "scope": "manuscript-topic",
        "plan_fingerprint": payload["plan_fingerprint"],
        "approved_at": datetime(2026, 8, 29, tzinfo=timezone.utc).isoformat(),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PlanningInputError) as captured:
        run_plan(tmp_path)

    message = str(captured.value)
    assert message == f"existing planning report cannot be validated: {report_path}"
    assert "swordfish-secret" not in message
    assert "input" not in message
    assert "errors.pydantic.dev" not in message
    assert store.status().stage == "initialized"


def test_unreadable_existing_report_without_new_approval_fails_closed_and_is_unchanged(
    tmp_path: Path,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    report_path = tmp_path / ".cfdpaper" / "outputs" / "plan" / "topic-ranking.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    original = b"private-invalid-report\xff"
    report_path.write_bytes(original)

    with pytest.raises(PlanningInputError, match="existing planning report cannot be validated"):
        run_plan(tmp_path)

    assert report_path.read_bytes() == original
    assert store.status().stage == "initialized"


def test_valid_explicit_approval_can_replace_invalid_existing_report(tmp_path: Path) -> None:
    store, _candidates = prepared_project(tmp_path)
    report_path = tmp_path / ".cfdpaper" / "outputs" / "plan" / "topic-ranking.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    original = b"private-invalid-report\xff"
    report_path.write_bytes(original)

    execution = run_plan(tmp_path, approve_topic="topic-01", author="Author")

    assert execution.report_path.read_bytes() != original
    assert execution.report.approval is not None
    assert execution.report.approval.scope == "manuscript-topic"
    assert store.status().stage == "topic-approved"


@pytest.mark.parametrize(
    ("approve_topic", "author", "message"),
    [
        ("unknown", "Author", "approval topic is not ranked: unknown"),
        ("topic-01", "   ", "--author must contain non-whitespace characters"),
    ],
)
def test_invalid_explicit_approval_does_not_replace_invalid_existing_report(
    tmp_path: Path,
    approve_topic: str,
    author: str,
    message: str,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    report_path = tmp_path / ".cfdpaper" / "outputs" / "plan" / "topic-ranking.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    original = b"private-invalid-report\xff"
    report_path.write_bytes(original)

    with pytest.raises(PlanningInputError, match=message):
        run_plan(tmp_path, approve_topic=approve_topic, author=author)

    assert report_path.read_bytes() == original
    assert store.status().stage == "initialized"


def test_existing_report_decode_error_is_generic_and_explicit_approval_can_replace(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "topic-ranking.json"
    report_path.write_bytes(b"swordfish-secret\xff")

    with pytest.raises(PlanningInputError) as captured:
        planning_module._load_existing_report(report_path, explicit_approval=False)

    assert str(captured.value) == (f"existing planning report cannot be validated: {report_path}")
    assert "swordfish-secret" not in str(captured.value)
    assert planning_module._load_existing_report(report_path, explicit_approval=True) is None


def test_existing_report_os_error_does_not_echo_cause(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = tmp_path / "topic-ranking.json"
    report_path.write_text("{}", encoding="utf-8")

    def deny_read(_path: Path, encoding: str | None = None) -> str:
        del encoding
        raise OSError("swordfish-secret")

    monkeypatch.setattr(Path, "read_text", deny_read)

    with pytest.raises(PlanningInputError) as captured:
        planning_module._load_existing_report(report_path, explicit_approval=False)

    assert str(captured.value) == (f"existing planning report cannot be validated: {report_path}")
    assert "swordfish-secret" not in str(captured.value)
    assert planning_module._load_existing_report(report_path, explicit_approval=True) is None


def test_report_replace_failure_does_not_advance_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared_project(tmp_path)

    def deny_replace(_source: Path, _destination: Path) -> None:
        raise PermissionError("replace denied")

    monkeypatch.setattr(planning_module.os, "replace", deny_replace)

    with pytest.raises(PlanningWriteError, match="could not write"):
        run_plan(tmp_path)

    assert ProjectStore.open(tmp_path).status().stage == "initialized"


def test_atomic_report_parent_creation_error_is_stable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = PlanReport.model_validate(
        report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    )

    def deny_mkdir(
        _path: Path,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        del mode, parents, exist_ok
        raise PermissionError("mkdir denied")

    monkeypatch.setattr(Path, "mkdir", deny_mkdir)

    with pytest.raises(PlanningWriteError, match="could not write planning report"):
        planning_module._atomic_write_report(tmp_path / "reports" / "plan.json", report)


def test_atomic_report_cleanup_error_does_not_mask_replace_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = PlanReport.model_validate(
        report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    )

    def deny_replace(_source: Path, _destination: Path) -> None:
        raise PermissionError("replace denied")

    def deny_unlink(_path: Path, missing_ok: bool = False) -> None:
        del missing_ok
        raise PermissionError("unlink denied")

    monkeypatch.setattr(planning_module.os, "replace", deny_replace)
    monkeypatch.setattr(Path, "unlink", deny_unlink)

    with pytest.raises(PlanningWriteError, match="could not write planning report") as captured:
        planning_module._atomic_write_report(tmp_path / "plan.json", report)

    assert isinstance(captured.value.__cause__, PermissionError)
    assert "replace denied" in str(captured.value.__cause__)


def test_atomic_report_cleanup_only_error_is_stable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = PlanReport.model_validate(
        report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    )

    def deny_unlink(_path: Path, missing_ok: bool = False) -> None:
        del missing_ok
        raise PermissionError("unlink denied")

    monkeypatch.setattr(Path, "unlink", deny_unlink)

    with pytest.raises(PlanningWriteError, match="temporary file") as captured:
        planning_module._atomic_write_report(tmp_path / "plan.json", report)

    assert isinstance(captured.value.__cause__, PermissionError)
    assert "unlink denied" in str(captured.value.__cause__)


def test_posix_parent_directory_fsync_closes_descriptor_on_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed: list[int] = []

    class FakeOS:
        name = "posix"
        O_RDONLY = 0

        @staticmethod
        def open(_path: Path, _flags: int) -> int:
            return 41

        @staticmethod
        def fsync(_descriptor: int) -> None:
            raise OSError("directory fsync denied")

        @staticmethod
        def close(descriptor: int) -> None:
            closed.append(descriptor)

    monkeypatch.setattr(planning_module, "os", FakeOS())

    with pytest.raises(OSError, match="directory fsync denied"):
        planning_module._fsync_parent_directory(tmp_path)

    assert closed == [41]


def test_parent_directory_fsync_failure_does_not_advance_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared_project(tmp_path)

    def deny_directory_fsync(_directory: Path) -> None:
        raise OSError("directory fsync denied")

    monkeypatch.setattr(
        planning_module,
        "_fsync_parent_directory",
        deny_directory_fsync,
        raising=False,
    )

    with pytest.raises(PlanningWriteError, match="could not write") as captured:
        run_plan(tmp_path)

    assert "directory fsync denied" in str(captured.value.__cause__)
    assert ProjectStore.open(tmp_path).status().stage == "initialized"


def evidence_record(**updates: object) -> EvidenceRecord:
    values = {
        "evidence_id": "ev-01",
        "source_uri": "source.csv",
        "locator": "row:2",
        "source_hash": "a" * 64,
        "stale": False,
        "kind": "qoi",
        "summary": "pressure loss",
        "maturity": "verified",
    }
    values.update(updates)
    return EvidenceRecord.model_validate(values)


def ranked_topic(topic_id: str, *, defensible: bool) -> RankedTopic:
    return RankedTopic(
        candidate=TopicCandidate(
            topic_id=topic_id,
            title=f"Topic {topic_id}",
            research_question=f"What supports {topic_id}?",
            supporting_evidence_ids=["ev-01"],
            required_evidence_kinds={"qoi"},
        ),
        score=0.8 if defensible else 0.4,
        evidence_coverage=1.0 if defensible else 0.5,
        verified_evidence_count=1 if defensible else 0,
        defensible=defensible,
    )


def ranking_result(*topics: RankedTopic) -> TopicRankingResult:
    return TopicRankingResult(
        outcome="manuscript" if topics and topics[0].defensible else "analysis-note",
        ranked_topics=list(topics),
        reason="Synthetic ranking for planning contract tests.",
    )


def report_payload(ranking: TopicRankingResult) -> dict:
    candidate_sha = "a" * 64
    evidence_sha = "b" * 64
    return {
        "schema_version": 1,
        "project_id": "demo",
        "candidate_source_uri": "candidates.json",
        "candidate_source_sha256": candidate_sha,
        "evidence_snapshot_sha256": evidence_sha,
        "plan_fingerprint": plan_fingerprint(candidate_sha, evidence_sha),
        "generated_at": datetime(2026, 8, 29, tzinfo=timezone.utc),
        "inspection": InspectionSummary(
            discovered=1,
            added=0,
            updated=0,
            unchanged=1,
            stale=0,
        ),
        "ranking": ranking,
        "leading_topic_id": (
            ranking.ranked_topics[0].candidate.topic_id if ranking.ranked_topics else None
        ),
    }


def test_candidate_input_is_strict_and_rejects_unknown_evidence_kind(tmp_path: Path) -> None:
    path = write_candidates(
        tmp_path / "candidates.json", candidate_payload(required_kinds=["trend"])
    )

    with pytest.raises(PlanningInputError, match="unknown evidence kind: trend"):
        load_candidate_input(path)


def test_candidate_input_rejects_duplicate_topic_ids(tmp_path: Path) -> None:
    payload = candidate_payload()
    payload["candidates"].append(dict(payload["candidates"][0]))
    path = write_candidates(tmp_path / "candidates.json", payload)

    with pytest.raises(PlanningInputError, match="duplicate topic ID: topic-01"):
        load_candidate_input(path)


@pytest.mark.parametrize("raw", [b"{", b"\xff"])
def test_candidate_input_rejects_invalid_json_or_utf8(tmp_path: Path, raw: bytes) -> None:
    path = tmp_path / "candidates.json"
    path.write_bytes(raw)

    with pytest.raises(PlanningInputError, match="invalid candidate input"):
        load_candidate_input(path)


def test_candidate_input_forbids_unknown_envelope_fields(tmp_path: Path) -> None:
    payload = candidate_payload()
    payload["unexpected"] = True
    path = write_candidates(tmp_path / "candidates.json", payload)

    with pytest.raises(PlanningInputError, match="unexpected"):
        load_candidate_input(path)


def test_plan_fingerprint_is_order_stable_and_domain_separated() -> None:
    first = EvidenceRecord(
        evidence_id="ev-01",
        source_uri="source.csv",
        locator="row:2",
        source_hash="a" * 64,
        kind="qoi",
        summary="pressure loss",
        maturity="verified",
    )
    second = first.model_copy(update={"evidence_id": "ev-02", "locator": "row:3"})
    evidence_hash = evidence_snapshot_sha256([second, first])

    assert evidence_hash == evidence_snapshot_sha256([first, second])
    assert plan_fingerprint("b" * 64, evidence_hash) == plan_fingerprint("b" * 64, evidence_hash)
    assert plan_fingerprint("c" * 64, evidence_hash) != plan_fingerprint("b" * 64, evidence_hash)


def test_plan_report_rejects_fingerprint_not_derived_from_its_sources() -> None:
    payload = report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    payload["plan_fingerprint"] = "c" * 64

    with pytest.raises(ValidationError, match="plan fingerprint does not match source hashes"):
        PlanReport.model_validate(payload)


@pytest.mark.parametrize(
    ("topics", "leading_topic_id"),
    [
        ((ranked_topic("topic-01", defensible=True),), "topic-02"),
        ((), "topic-01"),
    ],
)
def test_plan_report_leading_topic_must_match_first_ranked_topic(
    topics: tuple[RankedTopic, ...],
    leading_topic_id: str,
) -> None:
    payload = report_payload(ranking_result(*topics))
    payload["leading_topic_id"] = leading_topic_id

    with pytest.raises(ValidationError, match="leading topic must match first ranked topic"):
        PlanReport.model_validate(payload)


@pytest.mark.parametrize(
    "approval",
    [
        {
            "topic_id": "topic-01",
            "author": "Author",
            "scope": "manuscript-topic",
            "plan_fingerprint": "c" * 64,
            "approved_at": datetime(2026, 8, 29, tzinfo=timezone.utc),
        },
        {
            "topic_id": "missing",
            "author": "Author",
            "scope": "direction-only",
            "plan_fingerprint": plan_fingerprint("a" * 64, "b" * 64),
            "approved_at": datetime(2026, 8, 29, tzinfo=timezone.utc),
        },
        {
            "topic_id": "topic-01",
            "author": "Author",
            "scope": "direction-only",
            "plan_fingerprint": plan_fingerprint("a" * 64, "b" * 64),
            "approved_at": datetime(2026, 8, 29, tzinfo=timezone.utc),
        },
    ],
)
def test_plan_report_rejects_unbound_or_incorrectly_scoped_approval(approval: dict) -> None:
    payload = report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    payload["approval"] = approval

    with pytest.raises(ValidationError, match="approval"):
        PlanReport.model_validate(payload)


def test_plan_report_allows_direction_approval_for_nondefensible_nonleading_topic() -> None:
    ranking = ranking_result(
        ranked_topic("leading", defensible=True),
        ranked_topic("direction", defensible=False),
    )
    payload = report_payload(ranking)
    payload["approval"] = PlanApproval(
        topic_id="direction",
        author="Author",
        scope="direction-only",
        plan_fingerprint=payload["plan_fingerprint"],
        approved_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
    )

    report = PlanReport.model_validate(payload)

    assert report.ranking.outcome == "manuscript"
    assert report.leading_topic_id == "leading"
    assert report.approval is not None
    assert report.approval.topic_id == "direction"
    assert report.approval.scope == "direction-only"


@pytest.mark.parametrize(
    ("candidate_sha", "evidence_sha", "source"),
    [
        ("a" * 63, "b" * 64, "candidate"),
        ("A" * 64, "b" * 64, "candidate"),
        ("g" * 64, "b" * 64, "candidate"),
        ("a" * 63 + "\0", "b" * 64, "candidate"),
        ("a" * 64, "b" * 63, "evidence"),
        ("a" * 64, "B" * 64, "evidence"),
        ("a" * 64, "z" * 64, "evidence"),
        ("a" * 64, "b" * 63 + "\0", "evidence"),
    ],
)
def test_plan_fingerprint_rejects_noncanonical_hash_inputs(
    candidate_sha: str,
    evidence_sha: str,
    source: str,
) -> None:
    with pytest.raises(PlanningInputError, match=f"invalid {source} SHA-256"):
        plan_fingerprint(candidate_sha, evidence_sha)


def test_plan_fingerprint_has_an_exact_domain_separated_vector() -> None:
    fingerprint = plan_fingerprint("a" * 64, "b" * 64)

    assert fingerprint == "41fee39383f45ebb619cf1aa6f502e506d0e537e239c5449036d61965ef5891b"
    assert fingerprint != hashlib.sha256(("a" * 64 + "b" * 64).encode("ascii")).hexdigest()


def test_evidence_snapshot_rejects_duplicate_ids_independent_of_input_order() -> None:
    first = evidence_record(locator="row:2")
    duplicate = evidence_record(locator="row:3")

    for records in ([first, duplicate], [duplicate, first]):
        with pytest.raises(PlanningInputError, match="duplicate evidence ID: ev-01"):
            evidence_snapshot_sha256(records)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("topic_id", "  "),
        ("topic_id", 1),
        ("title", "\t"),
        ("title", []),
        ("research_question", "\n"),
        ("research_question", {}),
        ("minimum_verified_evidence", "1"),
        ("minimum_verified_evidence", True),
        ("significance", "0.8"),
        ("significance", True),
        ("significance", float("inf")),
        ("novelty", "0.7"),
        ("novelty", False),
        ("novelty", float("nan")),
    ],
)
def test_candidate_input_rejects_coerced_or_nonfinite_author_values(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    payload = candidate_payload()
    payload["candidates"][0][field] = value
    path = write_candidates(tmp_path / "candidates.json", payload)

    with pytest.raises(PlanningInputError, match=field):
        load_candidate_input(path)


def test_candidate_input_allows_an_empty_candidate_list(tmp_path: Path) -> None:
    path = write_candidates(
        tmp_path / "candidates.json",
        {"schema_version": 1, "candidates": []},
    )

    envelope, _raw, _source_hash = load_candidate_input(path)

    assert envelope.candidates == ()


def test_validation_summary_is_stable_and_does_not_echo_inputs(tmp_path: Path) -> None:
    invalid = dict(candidate_payload()["candidates"][0])
    invalid["required_maturity"] = "future"
    invalid["minimum_verified_evidence"] = 0
    invalid["unexpected"] = "secret-author-value"
    path = tmp_path / "candidates.json"
    messages = []
    for candidate in (invalid, dict(reversed(list(invalid.items())))):
        path.write_text(
            json.dumps({"schema_version": 1, "candidates": [candidate]}),
            encoding="utf-8",
        )
        with pytest.raises(PlanningInputError) as captured:
            load_candidate_input(path)
        messages.append(str(captured.value))

    assert messages[0] == messages[1]
    assert "secret-author-value" not in messages[0]
    assert "input_value" not in messages[0]
    assert "pydantic.dev" not in messages[0]


def test_invalid_evidence_kind_contract_fails_as_internal_configuration_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = write_candidates(tmp_path / "candidates.json")
    monkeypatch.setattr(EvidenceRecord.model_fields["kind"], "annotation", Literal[1])

    with pytest.raises(
        RuntimeError, match="EvidenceRecord.kind must be a non-empty Literal of str"
    ):
        load_candidate_input(path)


def test_evidence_snapshot_matches_exact_unicode_canonical_vector() -> None:
    record = evidence_record(
        evidence_id="ev-α",
        source_uri="数据/结果.csv",
        summary="压降 Δp",
        maturity="author-approved",
        stale=True,
    )

    assert evidence_snapshot_sha256([record]) == (
        "93fbb7080257aa6946993c1e1338b4f05d257d57e49a8475a38568db35021a56"
    )


def test_evidence_snapshot_is_sensitive_to_every_reachable_record_field() -> None:
    base = evidence_record()
    base_hash = evidence_snapshot_sha256([base])
    variants = {
        "evidence_id": "ev-02",
        "source_uri": "other.csv",
        "locator": "row:3",
        "source_hash": "b" * 64,
        "stale": True,
        "kind": "field",
        "summary": "temperature field",
        "maturity": "author-approved",
    }

    for field, value in variants.items():
        changed = base.model_copy(update={field: value})
        assert evidence_snapshot_sha256([changed]) != base_hash, field


def test_plan_approval_rejects_blank_author() -> None:
    with pytest.raises(ValidationError, match="author must not be blank"):
        PlanApproval(
            topic_id="topic-01",
            author="   ",
            scope="manuscript-topic",
            plan_fingerprint="a" * 64,
            approved_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
        )


def test_plan_approval_trims_author_and_report_roundtrip_preserves_it() -> None:
    payload = report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    payload["approval"] = {
        "topic_id": "topic-01",
        "author": " Author ",
        "scope": "manuscript-topic",
        "plan_fingerprint": payload["plan_fingerprint"],
        "approved_at": datetime(2026, 8, 29, tzinfo=timezone.utc),
    }

    report = PlanReport.model_validate(payload)
    restored = PlanReport.model_validate_json(report.model_dump_json())

    assert report.approval is not None
    assert report.approval.author == "Author"
    assert restored.approval is not None
    assert restored.approval.author == "Author"


@pytest.mark.parametrize("schema_version", [True, 1.0, "1", 0, 2])
def test_candidate_schema_version_requires_exact_json_integer_one(
    tmp_path: Path,
    schema_version: object,
) -> None:
    payload = candidate_payload()
    payload["schema_version"] = schema_version
    path = write_candidates(tmp_path / "candidates.json", payload)

    with pytest.raises(PlanningInputError, match="schema_version must be JSON integer 1"):
        load_candidate_input(path)


@pytest.mark.parametrize("schema_version", [True, 1.0, "1", 0, 2])
def test_report_schema_version_requires_exact_json_integer_one(schema_version: object) -> None:
    payload = report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    payload["schema_version"] = schema_version

    with pytest.raises(ValidationError, match="schema_version must be JSON integer 1"):
        PlanReport.model_validate(payload)


def test_schema_version_accepts_exact_integer_one(tmp_path: Path) -> None:
    candidate_path = write_candidates(tmp_path / "candidates.json", candidate_payload())
    candidate, _raw, _source_hash = load_candidate_input(candidate_path)
    report = PlanReport.model_validate(
        report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    )

    assert type(candidate.schema_version) is int
    assert candidate.schema_version == 1
    assert type(report.schema_version) is int
    assert report.schema_version == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("significance", 10**1000),
        ("significance", -(10**1000)),
        ("novelty", 10**1000),
        ("novelty", -(10**1000)),
    ],
)
def test_candidate_huge_json_integer_is_a_stable_input_error(
    tmp_path: Path,
    field: str,
    value: int,
) -> None:
    payload = candidate_payload()
    payload["candidates"][0][field] = value
    path = write_candidates(tmp_path / "candidates.json", payload)

    with pytest.raises(PlanningInputError, match=field):
        load_candidate_input(path)


def test_planning_models_are_frozen_and_failed_assignment_does_not_pollute() -> None:
    topic = ranked_topic("topic-01", defensible=True).candidate
    candidate_input = CandidateInput(schema_version=1, candidates=[topic])
    report = PlanReport.model_validate(
        report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    )
    candidate_before = candidate_input.model_dump_json()
    report_before = report.model_dump_json()

    with pytest.raises(ValidationError, match="frozen"):
        candidate_input.candidates = [topic, topic]
    with pytest.raises(ValidationError, match="frozen"):
        report.leading_topic_id = "other"

    assert candidate_input.model_dump_json() == candidate_before
    assert report.model_dump_json() == report_before


def test_planning_model_copy_updates_require_explicit_revalidation() -> None:
    report = PlanReport.model_validate(
        report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    )

    with pytest.raises(TypeError, match="explicit model_validate"):
        report.model_copy(update={"leading_topic_id": "other"})

    payload = report.model_dump(mode="python")
    payload["generated_at"] = datetime(2026, 8, 30, tzinfo=timezone.utc)
    rebuilt = PlanReport.model_validate(payload)
    assert rebuilt.generated_at == payload["generated_at"]


def test_candidate_topic_id_is_trimmed_for_json_and_model_inputs(tmp_path: Path) -> None:
    payload = candidate_payload()
    payload["candidates"][0]["topic_id"] = " topic-01 "
    path = write_candidates(tmp_path / "candidates.json", payload)
    from_json, _raw, _source_hash = load_candidate_input(path)
    topic = TopicCandidate.model_validate(payload["candidates"][0])
    from_model = CandidateInput(schema_version=1, candidates=[topic])

    assert from_json.candidates[0].topic_id == "topic-01"
    assert from_model.candidates[0].topic_id == "topic-01"
    assert topic.topic_id == " topic-01 "


def test_candidate_duplicate_topic_ids_are_checked_after_trimming(tmp_path: Path) -> None:
    payload = candidate_payload()
    duplicate = dict(payload["candidates"][0])
    duplicate["topic_id"] = " topic-01 "
    payload["candidates"].append(duplicate)
    path = write_candidates(tmp_path / "candidates.json", payload)

    with pytest.raises(PlanningInputError, match="duplicate topic ID: topic-01"):
        load_candidate_input(path)


def test_plan_report_requires_schema_version() -> None:
    payload = report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    payload.pop("schema_version")

    with pytest.raises(ValidationError, match="schema_version"):
        PlanReport.model_validate(payload)


def test_planning_timestamps_reject_naive_datetimes() -> None:
    naive = datetime(2026, 8, 29)
    with pytest.raises(ValidationError, match="approved_at must be timezone-aware"):
        PlanApproval(
            topic_id="topic-01",
            author="Author",
            scope="manuscript-topic",
            plan_fingerprint="a" * 64,
            approved_at=naive,
        )

    payload = report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    payload["generated_at"] = naive
    with pytest.raises(ValidationError, match="generated_at must be timezone-aware"):
        PlanReport.model_validate(payload)


def test_planning_timestamp_roundtrip_preserves_aware_offsets() -> None:
    generated_offset = timezone(timedelta(hours=-4))
    approved_offset = timezone(timedelta(hours=5, minutes=30))
    payload = report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    payload["generated_at"] = datetime(2026, 8, 29, 10, tzinfo=generated_offset)
    payload["approval"] = {
        "topic_id": "topic-01",
        "author": "Author",
        "scope": "manuscript-topic",
        "plan_fingerprint": payload["plan_fingerprint"],
        "approved_at": datetime(2026, 8, 29, 20, tzinfo=approved_offset),
    }

    restored = PlanReport.model_validate_json(PlanReport.model_validate(payload).model_dump_json())

    assert restored.generated_at.utcoffset() == timedelta(hours=-4)
    assert restored.approval is not None
    assert restored.approval.approved_at.utcoffset() == timedelta(hours=5, minutes=30)


def test_checkpoint_id_is_canonical_semantic_identity_only() -> None:
    fingerprint = "a" * 64
    approved_at = datetime(2026, 8, 29, tzinfo=timezone.utc)
    assert list(signature(planning_module._checkpoint_id).parameters) == [
        "checkpoint_stage",
        "fingerprint",
        "approval",
    ]
    approval_with_colon_in_topic = PlanApproval(
        topic_id="a:b",
        author="c",
        scope="manuscript-topic",
        plan_fingerprint=fingerprint,
        approved_at=approved_at,
    )
    approval_with_colon_in_author = PlanApproval(
        topic_id="a",
        author="b:c",
        scope="manuscript-topic",
        plan_fingerprint=fingerprint,
        approved_at=approved_at,
    )
    same_normalized_approval = PlanApproval(
        topic_id="a:b",
        author=" c ",
        scope="manuscript-topic",
        plan_fingerprint=fingerprint,
        approved_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
    )
    different_scope = PlanApproval(
        topic_id="a:b",
        author="c",
        scope="direction-only",
        plan_fingerprint=fingerprint,
        approved_at=approved_at,
    )
    different_topic = PlanApproval(
        topic_id="other",
        author="c",
        scope="manuscript-topic",
        plan_fingerprint=fingerprint,
        approved_at=approved_at,
    )
    different_author = PlanApproval(
        topic_id="a:b",
        author="other",
        scope="manuscript-topic",
        plan_fingerprint=fingerprint,
        approved_at=approved_at,
    )
    other_fingerprint = "b" * 64
    different_fingerprint = PlanApproval(
        topic_id="a:b",
        author="c",
        scope="manuscript-topic",
        plan_fingerprint=other_fingerprint,
        approved_at=approved_at,
    )

    first = planning_module._checkpoint_id(
        "plan-approval", fingerprint, approval_with_colon_in_topic
    )
    second = planning_module._checkpoint_id(
        "plan-approval", fingerprint, approval_with_colon_in_author
    )
    without_approval = planning_module._checkpoint_id("plan-approval", fingerprint, None)

    assert first != second
    assert first != without_approval
    assert first == planning_module._checkpoint_id(
        "plan-approval", fingerprint, same_normalized_approval
    )
    variants = {
        planning_module._checkpoint_id(
            "plan-direction-approval", fingerprint, approval_with_colon_in_topic
        ),
        planning_module._checkpoint_id("plan-approval", fingerprint, different_scope),
        planning_module._checkpoint_id("plan-approval", fingerprint, different_topic),
        planning_module._checkpoint_id("plan-approval", fingerprint, different_author),
        planning_module._checkpoint_id("plan-approval", other_fingerprint, different_fingerprint),
    }
    assert first not in variants
    assert len(variants) == 5


def test_candidate_input_is_deeply_immutable_and_roundtrips_unchanged() -> None:
    topic = ranked_topic("topic-01", defensible=True).candidate
    envelope = CandidateInput(schema_version=1, candidates=[topic])
    before = envelope.model_dump_json()
    stored = envelope.candidates[0]

    with pytest.raises(AttributeError):
        envelope.candidates.append(topic)
    with pytest.raises(AttributeError):
        envelope.candidates.reverse()
    stored.title = "Changed"
    stored.supporting_evidence_ids.append("ev-02")
    stored.supporting_evidence_ids.reverse()
    stored.supporting_evidence_ids[0] = "ev-03"
    stored.required_evidence_kinds.add("field")
    stored.required_evidence_kinds.update({"mesh"})
    stored.required_evidence_kinds |= {"boundary"}

    assert isinstance(stored, TopicCandidate)
    assert envelope.candidates[0].title != "Changed"
    assert envelope.candidates[0].supporting_evidence_ids == ["ev-01"]
    assert envelope.candidates[0].required_evidence_kinds == {"qoi"}
    assert envelope.model_dump_json() == before
    assert CandidateInput.model_validate_json(before).model_dump_json() == before


def test_plan_report_ranking_is_deeply_immutable_and_roundtrips_unchanged() -> None:
    ordinary_ranking = ranking_result(ranked_topic("topic-01", defensible=True))
    report = PlanReport.model_validate(report_payload(ordinary_ranking))
    before = report.model_dump_json()
    stored_ranking = report.ranking
    stored_ranked = stored_ranking.ranked_topics[0]

    stored_ranking.ranked_topics.reverse()
    stored_ranking.ranked_topics.append(stored_ranked)
    stored_ranking.ranked_topics[0] = stored_ranked
    stored_ranked.score = 0.1
    stored_ranked.candidate.title = "Changed"
    stored_ranked.missing_evidence.append("kind:field")
    stored_ranking.missing_evidence.append("kind:field")
    stored_ranked.candidate.supporting_evidence_ids.append("ev-02")
    stored_ranked.candidate.required_evidence_kinds.add("field")

    assert isinstance(stored_ranking, TopicRankingResult)
    assert isinstance(stored_ranked, RankedTopic)
    assert isinstance(stored_ranked.candidate, TopicCandidate)
    assert len(report.ranking.ranked_topics) == 1
    assert report.ranking.ranked_topics[0].score == 0.8
    assert report.ranking.ranked_topics[0].candidate.title == "Topic topic-01"
    assert report.ranking.missing_evidence == []
    assert report.model_dump_json() == before
    restored = PlanReport.model_validate_json(before)
    assert restored.model_dump_json() == before
    assert restored.plan_fingerprint == plan_fingerprint(
        restored.candidate_source_sha256,
        restored.evidence_snapshot_sha256,
    )
    assert restored.leading_topic_id == restored.ranking.ranked_topics[0].candidate.topic_id


def test_task4_style_plain_ranking_input_and_json_shape_remain_supported() -> None:
    candidate = ranked_topic("topic-01", defensible=True).candidate
    envelope = CandidateInput(schema_version=1, candidates=[candidate])
    ranking = rank_topics(envelope.candidates, [evidence_record()])

    report = PlanReport.model_validate(report_payload(ranking))
    serialized = json.loads(report.model_dump_json())
    restored = PlanReport.model_validate_json(report.model_dump_json())

    assert ranking.outcome == "manuscript"
    assert isinstance(report.ranking, TopicRankingResult)
    assert isinstance(serialized["ranking"]["ranked_topics"], list)
    assert isinstance(
        serialized["ranking"]["ranked_topics"][0]["candidate"]["supporting_evidence_ids"],
        list,
    )
    assert isinstance(
        serialized["ranking"]["ranked_topics"][0]["candidate"]["required_evidence_kinds"],
        list,
    )
    assert restored.model_dump(mode="json") == report.model_dump(mode="json")


def test_builtin_mutable_descriptors_only_change_public_copies() -> None:
    envelope = CandidateInput(
        schema_version=1,
        candidates=[ranked_topic("topic-01", defensible=True).candidate],
    )
    report = PlanReport.model_validate(
        report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    )
    envelope_before = envelope.model_dump_json()
    report_before = report.model_dump_json()
    candidate_copy = envelope.candidates[0]
    ranking_copy = report.ranking

    list.append(candidate_copy.supporting_evidence_ids, "ev-bypass")
    set.add(candidate_copy.required_evidence_kinds, "field")
    list.append(ranking_copy.ranked_topics, ranking_copy.ranked_topics[0])
    list.append(ranking_copy.missing_evidence, "kind:field")

    assert envelope.model_dump_json() == envelope_before
    assert report.model_dump_json() == report_before
    assert envelope.candidates[0].supporting_evidence_ids == ["ev-01"]
    assert len(report.ranking.ranked_topics) == 1


def test_snapshot_storage_names_do_not_leak_from_external_schema_or_dumps() -> None:
    envelope = CandidateInput(
        schema_version=1,
        candidates=[ranked_topic("topic-01", defensible=True).candidate],
    )
    report = PlanReport.model_validate(
        report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    )
    expected_report_fields = {
        "schema_version",
        "project_id",
        "candidate_source_uri",
        "candidate_source_sha256",
        "evidence_snapshot_sha256",
        "generation_fingerprint",
        "plan_fingerprint",
        "generated_at",
        "inspection",
        "ranking",
        "leading_topic_id",
        "approval",
    }
    candidate_schema = CandidateInput.model_json_schema()
    candidate_schema_by_name = CandidateInput.model_json_schema(by_alias=False)
    report_schema = PlanReport.model_json_schema()
    report_schema_by_name = PlanReport.model_json_schema(by_alias=False)
    candidate_dump = envelope.model_dump()
    candidate_dump_by_name = envelope.model_dump(by_alias=False)
    report_dump = report.model_dump()
    report_dump_by_name = report.model_dump(by_alias=False)

    assert set(CandidateInput.model_fields) == {"schema_version", "candidates"}
    assert set(PlanReport.model_fields) == expected_report_fields
    assert set(candidate_schema["properties"]) == {"schema_version", "candidates"}
    assert candidate_schema_by_name["properties"] == candidate_schema["properties"]
    assert set(report_schema["properties"]) == expected_report_fields
    assert report_schema_by_name["properties"] == report_schema["properties"]
    assert candidate_dump_by_name == candidate_dump
    assert report_dump_by_name == report_dump
    assert (
        CandidateInput.model_validate(candidate_dump).model_dump_json()
        == envelope.model_dump_json()
    )
    assert PlanReport.model_validate(report_dump).model_dump_json() == report.model_dump_json()
    assert "candidates" in signature(CandidateInput).parameters
    assert "ranking" in signature(PlanReport).parameters


@pytest.mark.parametrize("by_alias", [True, False])
def test_planning_json_schemas_do_not_expose_private_snapshot_types(
    by_alias: bool,
) -> None:
    private_names = (
        "_TopicCandidateSnapshot",
        "_RankedTopicSnapshot",
        "_TopicRankingResultSnapshot",
    )

    for model in (CandidateInput, PlanReport):
        encoded = json.dumps(model.model_json_schema(by_alias=by_alias), sort_keys=True)

        assert not any(name in encoded for name in private_names)


def test_planning_json_schema_supports_legacy_parent_without_union_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def legacy_model_json_schema(
        cls: type[BaseModel],
        by_alias: bool = True,
        ref_template: str = "#/$defs/{model}",
        schema_generator: object = None,
        mode: object = "validation",
    ) -> dict[str, object]:
        calls.append(
            {
                "cls": cls,
                "by_alias": by_alias,
                "ref_template": ref_template,
                "schema_generator": schema_generator,
                "mode": mode,
            }
        )
        return {
            "$defs": {"_TopicCandidateSnapshot": {"title": "_TopicCandidateSnapshot"}},
            "properties": {"candidates": {"items": {"$ref": "#/$defs/_TopicCandidateSnapshot"}}},
        }

    monkeypatch.setattr(
        BaseModel,
        "model_json_schema",
        classmethod(legacy_model_json_schema),
    )

    default_schema = CandidateInput.model_json_schema()
    by_name_schema = CandidateInput.model_json_schema(by_alias=False)

    assert [call["by_alias"] for call in calls] == [True, False]
    assert "_TopicCandidateSnapshot" not in json.dumps(default_schema, sort_keys=True)
    assert "_TopicCandidateSnapshot" not in json.dumps(by_name_schema, sort_keys=True)
    assert default_schema["properties"]["candidates"]["items"]["$ref"] == ("#/$defs/TopicCandidate")


def test_planning_json_schema_respects_supported_union_format() -> None:
    schema = PlanReport.model_json_schema(union_format="primitive_type_array")

    assert schema["properties"]["leading_topic_id"]["type"] == ["string", "null"]


def test_snapshot_serializers_preserve_nested_include_and_exclude() -> None:
    candidate = ranked_topic("topic-01", defensible=True).candidate
    candidate.required_evidence_kinds = {"qoi", "field"}
    envelope = CandidateInput(
        schema_version=1,
        candidates=[candidate],
    )
    report = PlanReport.model_validate(
        report_payload(ranking_result(ranked_topic("topic-01", defensible=True)))
    )

    candidate_include = {"candidates": {0: {"topic_id", "required_evidence_kinds"}}}
    candidate_exclude = {"candidates": {0: {"title"}}}
    ranking_exclude = {"ranking": {"reason"}}
    ranking_include = {"ranking": {"ranked_topics": {0: {"candidate": {"topic_id"}}}}}

    included_candidate = envelope.model_dump(include=candidate_include)
    excluded_candidate = envelope.model_dump(exclude=candidate_exclude)
    excluded_report = report.model_dump(exclude=ranking_exclude)
    included_report = report.model_dump(include=ranking_include)
    included_candidate_json = json.loads(envelope.model_dump_json(include=candidate_include))
    excluded_report_json = json.loads(report.model_dump_json(exclude=ranking_exclude))

    assert included_candidate == {
        "candidates": (
            {
                "topic_id": "topic-01",
                "required_evidence_kinds": ["field", "qoi"],
            },
        )
    }
    assert included_candidate_json == {
        "candidates": [
            {
                "topic_id": "topic-01",
                "required_evidence_kinds": ["field", "qoi"],
            }
        ]
    }
    assert "title" not in excluded_candidate["candidates"][0]
    assert "reason" not in excluded_report["ranking"]
    assert "reason" not in excluded_report_json["ranking"]
    assert included_report == {
        "ranking": {"ranked_topics": ({"candidate": {"topic_id": "topic-01"}},)}
    }


@pytest.mark.parametrize("container_type", [list, tuple])
@pytest.mark.parametrize("use_model", [False, True])
def test_candidate_normalization_accepts_list_or_tuple_of_dict_or_model(
    container_type: type,
    use_model: bool,
) -> None:
    candidate = candidate_payload()["candidates"][0]
    candidate["topic_id"] = " topic-01 "
    item = TopicCandidate.model_validate(candidate) if use_model else candidate

    envelope = CandidateInput.model_validate(
        {"schema_version": 1, "candidates": container_type([item])}
    )

    assert envelope.candidates[0].topic_id == "topic-01"
    assert isinstance(envelope.candidates[0], TopicCandidate)


def test_raw_ranking_serialization_is_warning_free_and_keeps_json_arrays() -> None:
    envelope = CandidateInput(
        schema_version=1,
        candidates=[ranked_topic("topic-01", defensible=True).candidate],
    )
    ranking = rank_topics(envelope.candidates, [evidence_record()])

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        dumped = ranking.model_dump()
        dumped_json = json.loads(ranking.model_dump_json())

    assert isinstance(dumped["ranked_topics"], list)
    assert isinstance(dumped_json["ranked_topics"], list)
    assert isinstance(
        dumped_json["ranked_topics"][0]["candidate"]["required_evidence_kinds"],
        list,
    )


_HASH_SEED_SCRIPT = r"""
import sys
from pathlib import Path

import cfdpaper
from cfdpaper.planning import CandidateInput

root = Path(sys.argv[1]).resolve()
Path(cfdpaper.__file__).resolve().relative_to(root)
envelope = CandidateInput.model_validate(
    {
        "schema_version": 1,
        "candidates": [
            {
                "topic_id": "topic-01",
                "title": "Pressure-loss comparison",
                "research_question": "How does configuration affect pressure loss?",
                "supporting_evidence_ids": ["ev-01"],
                "required_evidence_kinds": ["qoi", "mesh", "boundary", "field"],
                "required_maturity": "verified",
                "minimum_verified_evidence": 1,
                "significance": 0.8,
                "novelty": 0.7,
            }
        ],
    }
)
print(envelope.model_dump_json())
"""


def test_required_evidence_kind_json_is_stable_across_python_hash_seeds() -> None:
    root = Path.cwd().resolve()
    outputs = []
    for seed in range(1, 9):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = str(seed)
        environment["PYTHONPATH"] = str(root / "src")
        completed = subprocess.run(
            [sys.executable, "-c", _HASH_SEED_SCRIPT, str(root)],
            cwd=root,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        outputs.append(completed.stdout.strip())

    assert len(set(outputs)) == 1
    serialized = json.loads(outputs[0])
    assert serialized["candidates"][0]["required_evidence_kinds"] == [
        "boundary",
        "field",
        "mesh",
        "qoi",
    ]


_CONCURRENT_PLAN_SCRIPT = r"""
import os
import sys
import time
from pathlib import Path

import cfdpaper
from cfdpaper.planning import run_plan

source_root = (Path(sys.argv[1]).resolve() / "src").resolve()
Path(cfdpaper.__file__).resolve().relative_to(source_root)
project = Path(sys.argv[2])
ready = Path(sys.argv[3])
start = Path(sys.argv[4])
ready.mkdir(parents=True, exist_ok=True)
(ready / str(os.getpid())).touch()
deadline = time.monotonic() + 30.0
while not start.exists():
    if time.monotonic() >= deadline:
        raise TimeoutError("parent did not release the planning barrier")
    time.sleep(0.01)
print(run_plan(project).checkpoint_id, flush=True)
"""


_ABNORMAL_LOCK_HOLDER_SCRIPT = r"""
import os
import sys
from pathlib import Path

import cfdpaper
from cfdpaper.locking import process_file_lock

source_root = (Path(sys.argv[1]).resolve() / "src").resolve()
Path(cfdpaper.__file__).resolve().relative_to(source_root)
lock_path = Path(sys.argv[2])
ready = Path(sys.argv[3])
with process_file_lock(lock_path):
    ready.touch()
    os._exit(0)
"""


def _subprocess_diagnostics(
    processes: list[subprocess.Popen[str]],
    stdout_paths: list[Path],
    stderr_paths: list[Path],
) -> str:
    details = []
    for process, stdout_path, stderr_path in zip(
        processes, stdout_paths, stderr_paths, strict=True
    ):
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
        details.append(
            f"pid={process.pid} returncode={process.poll()} stdout={stdout!r} stderr={stderr!r}"
        )
    return "\n".join(details)


def _terminate_and_wait(processes: list[subprocess.Popen[str]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.kill()
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_run_plan_serializes_sixteen_processes_into_one_semantic_transition(
    tmp_path: Path,
) -> None:
    prepared_project(tmp_path)
    worktree = Path.cwd().resolve()
    script = tmp_path / "concurrent_plan.py"
    script.write_text(_CONCURRENT_PLAN_SCRIPT, encoding="utf-8")
    ready = tmp_path / "ready"
    start = tmp_path / "start"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(worktree / "src")
    processes: list[subprocess.Popen[str]] = []
    stdout_paths: list[Path] = []
    stderr_paths: list[Path] = []
    failure: str | None = None

    try:
        for index in range(16):
            stdout_path = tmp_path / f"worker-{index}.stdout"
            stderr_path = tmp_path / f"worker-{index}.stderr"
            with (
                stdout_path.open("w", encoding="utf-8") as stdout_file,
                stderr_path.open("w", encoding="utf-8") as stderr_file,
            ):
                process = subprocess.Popen(
                    [
                        sys.executable,
                        str(script),
                        str(worktree),
                        str(tmp_path),
                        str(ready),
                        str(start),
                    ],
                    cwd=worktree,
                    env=environment,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    text=True,
                    encoding="utf-8",
                )
            processes.append(process)
            stdout_paths.append(stdout_path)
            stderr_paths.append(stderr_path)

        ready_deadline = time.monotonic() + 20.0
        while time.monotonic() < ready_deadline:
            if ready.exists() and len(list(ready.iterdir())) == 16:
                break
            if any(process.poll() is not None for process in processes):
                break
            time.sleep(0.02)
        ready_pids = {path.name for path in ready.iterdir()} if ready.exists() else set()
        if len(ready_pids) != 16 or not all(pid.isdigit() for pid in ready_pids):
            failure = (
                "planning ready barrier must contain 16 unique numeric child PIDs: "
                f"actual={sorted(ready_pids)}"
            )
        else:
            start.touch()
            completion_deadline = time.monotonic() + 30.0
            while time.monotonic() < completion_deadline:
                if all(process.poll() is not None for process in processes):
                    break
                time.sleep(0.02)
            unfinished = [process.pid for process in processes if process.poll() is None]
            if unfinished:
                failure = f"planning workers exceeded completion deadline: {unfinished}"
    finally:
        _terminate_and_wait(processes)

    diagnostics = _subprocess_diagnostics(processes, stdout_paths, stderr_paths)
    assert failure is None, f"{failure}\n{diagnostics}"
    assert all(process.returncode == 0 for process in processes), diagnostics
    stdout_lines = [path.read_text(encoding="utf-8").splitlines() for path in stdout_paths]
    assert all(len(lines) == 1 and lines[0] for lines in stdout_lines), diagnostics
    checkpoint_ids = [lines[0] for lines in stdout_lines]
    assert len(set(checkpoint_ids)) == 1, diagnostics

    store = ProjectStore.open(tmp_path)
    with store.connect() as connection:
        stage_count = connection.execute(
            "SELECT COUNT(*) FROM stages WHERE stage = 'plan'"
        ).fetchone()[0]
        stage_row = connection.execute(
            "SELECT status, outputs_json, approved_by FROM stages WHERE stage = 'plan'"
        ).fetchone()
        checkpoint_count = connection.execute(
            "SELECT COUNT(*) FROM checkpoints WHERE stage = 'plan'"
        ).fetchone()[0]
        checkpoint_row = connection.execute(
            "SELECT stage, payload_json FROM checkpoints WHERE stage = 'plan'"
        ).fetchone()
    report_path = tmp_path / ".cfdpaper" / "outputs" / "plan" / "topic-ranking.json"
    # Canonical JSON receives the complete PlanReport semantic validation. Pydantic's
    # runtime strict=True is intentionally unsuitable for JSON datetime/array forms.
    report = PlanReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    expected_payload = {
        "report_path": str(report_path),
        "plan_fingerprint": report.plan_fingerprint,
        "outcome": report.ranking.outcome,
        "leading_topic_id": report.leading_topic_id,
        "missing_evidence": report.ranking.missing_evidence,
        "inspection": report.inspection.model_dump(mode="json"),
        "approval": None,
    }
    assert stage_count == 1
    assert checkpoint_count == 1
    assert tuple(stage_row)[::2] == ("complete", None)
    assert checkpoint_row["stage"] == "plan"
    assert json.loads(stage_row["outputs_json"]) == expected_payload
    assert json.loads(checkpoint_row["payload_json"]) == expected_payload
    assert report.ranking.outcome == "manuscript"
    assert store.status().stage == "planned"


def test_run_plan_recovers_after_abnormal_lock_holder_exit(tmp_path: Path) -> None:
    prepared_project(tmp_path)
    worktree = Path.cwd().resolve()
    script = tmp_path / "abnormal_lock_holder.py"
    script.write_text(_ABNORMAL_LOCK_HOLDER_SCRIPT, encoding="utf-8")
    lock_path = tmp_path / ".cfdpaper" / "locks" / "plan.lock"
    ready = tmp_path / "lock-holder-ready"
    stdout_path = tmp_path / "lock-holder.stdout"
    stderr_path = tmp_path / "lock-holder.stderr"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(worktree / "src")

    with (
        stdout_path.open("w", encoding="utf-8") as stdout_file,
        stderr_path.open("w", encoding="utf-8") as stderr_file,
    ):
        process = subprocess.Popen(
            [sys.executable, str(script), str(worktree), str(lock_path), str(ready)],
            cwd=worktree,
            env=environment,
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
            encoding="utf-8",
        )
    failure: str | None = None
    try:
        ready_deadline = time.monotonic() + 20.0
        while not ready.exists() and time.monotonic() < ready_deadline:
            if process.poll() is not None:
                break
            time.sleep(0.02)
        if not ready.exists():
            failure = "abnormal lock holder did not signal lock acquisition"
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            failure = "abnormal lock holder did not exit within 20 seconds"
    finally:
        _terminate_and_wait([process])

    diagnostics = _subprocess_diagnostics([process], [stdout_path], [stderr_path])
    assert failure is None, f"{failure}\n{diagnostics}"
    assert process.returncode == 0, diagnostics
    execution = run_plan(tmp_path, lock_timeout_seconds=0.5)
    assert execution.report.ranking.outcome == "manuscript"
    assert ProjectStore.open(tmp_path).status().stage == "planned"


@pytest.mark.parametrize(
    ("approval", "expected_project_stage", "expected_checkpoint_stage"),
    [
        ({}, "planned", "plan"),
        (
            {"approve_topic": "topic-01", "author": "Author"},
            "topic-approved",
            "plan-approval",
        ),
    ],
)
def test_run_plan_repairs_report_after_one_database_transition_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    approval: dict[str, str],
    expected_project_stage: str,
    expected_checkpoint_stage: str,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    original_transition = ProjectStore.save_workflow_transition
    calls = 0

    def fail_once(self: ProjectStore, *args: object, **kwargs: object) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise sqlite3.OperationalError("injected transition failure")
        return original_transition(self, *args, **kwargs)

    monkeypatch.setattr(ProjectStore, "save_workflow_transition", fail_once)

    with pytest.raises(PlanningWriteError, match="injected transition failure"):
        run_plan(tmp_path, **approval)

    report_path = tmp_path / ".cfdpaper" / "outputs" / "plan" / "topic-ranking.json"
    first_report_bytes = report_path.read_bytes()
    first_report = PlanReport.model_validate_json(first_report_bytes)
    assert store.status().stage == "initialized"
    with store.connect() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM stages WHERE stage = 'plan'").fetchone()[0]
            == 0
        )
        assert connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 0

    repaired = run_plan(tmp_path, **approval)

    assert calls == 2
    assert repaired.report_path.read_bytes() == first_report_bytes
    assert repaired.report.plan_fingerprint == first_report.plan_fingerprint
    assert store.status().stage == expected_project_stage
    with store.connect() as connection:
        checkpoint_rows = connection.execute(
            "SELECT checkpoint_id, stage FROM checkpoints"
        ).fetchall()
        stage_count = connection.execute(
            "SELECT COUNT(*) FROM stages WHERE stage = 'plan'"
        ).fetchone()[0]
    assert [(row["checkpoint_id"], row["stage"]) for row in checkpoint_rows] == [
        (repaired.checkpoint_id, expected_checkpoint_stage)
    ]
    assert stage_count == 1


def test_explicit_approval_repairs_report_first_transition_from_inspected_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    store.set_stage("inspected")
    original_transition = ProjectStore.save_workflow_transition
    calls = 0

    def fail_once(self: ProjectStore, *args: object, **kwargs: object) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise sqlite3.OperationalError("injected inspected transition failure")
        return original_transition(self, *args, **kwargs)

    monkeypatch.setattr(ProjectStore, "save_workflow_transition", fail_once)
    approval = {"approve_topic": "topic-01", "author": "Author"}

    with pytest.raises(PlanningWriteError, match="inspected transition failure"):
        run_plan(tmp_path, **approval)

    report_path = tmp_path / ".cfdpaper" / "outputs" / "plan" / "topic-ranking.json"
    report_bytes = report_path.read_bytes()
    failed_report = PlanReport.model_validate_json(report_bytes)
    assert failed_report.approval is not None
    assert failed_report.approval.author == "Author"
    assert store.status().stage == "inspected"
    with store.connect() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM stages WHERE stage = 'plan'").fetchone()[0]
            == 0
        )
        assert connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 0

    repaired = run_plan(tmp_path, **approval)

    assert calls == 2
    assert repaired.report_path.read_bytes() == report_bytes
    assert repaired.report.approval == failed_report.approval
    assert store.status().stage == "topic-approved"
    with store.connect() as connection:
        checkpoint_count, distinct_checkpoint_count = connection.execute(
            "SELECT COUNT(*), COUNT(DISTINCT checkpoint_id) FROM checkpoints"
        ).fetchone()
        plan_stage_count = connection.execute(
            "SELECT COUNT(*) FROM stages WHERE stage = 'plan'"
        ).fetchone()[0]
    assert checkpoint_count == distinct_checkpoint_count == 1
    assert plan_stage_count == 1


@pytest.mark.parametrize(
    ("mode", "expected_project_stage", "expected_checkpoint_stages"),
    [
        ("unapproved", "planned", {"plan"}),
        ("explicit-initial", "topic-approved", {"plan-approval"}),
        ("explicit-predecessor", "topic-approved", {"plan", "plan-approval"}),
    ],
)
def test_report_first_repair_preserves_report_inspection_across_index_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    expected_project_stage: str,
    expected_checkpoint_stages: set[str],
) -> None:
    store, _candidates = prepared_project(tmp_path)
    predecessor = run_plan(tmp_path) if mode == "explicit-predecessor" else None
    (tmp_path / "new-unindexed-source.csv").write_text("case,dp\nB,14\n", encoding="utf-8")
    original_transition = ProjectStore.save_workflow_transition
    failed = False

    def fail_once(self: ProjectStore, *args: object, **kwargs: object) -> str:
        nonlocal failed
        if not failed:
            failed = True
            raise sqlite3.OperationalError("injected transition failure after inspection")
        return original_transition(self, *args, **kwargs)

    approval = {"approve_topic": "topic-01", "author": "Author"} if mode != "unapproved" else {}
    monkeypatch.setattr(ProjectStore, "save_workflow_transition", fail_once)
    with pytest.raises(PlanningWriteError, match="failure after inspection"):
        run_plan(tmp_path, **approval)

    report_path = tmp_path / ".cfdpaper" / "outputs" / "plan" / "topic-ranking.json"
    first_report_bytes = report_path.read_bytes()
    first_report = PlanReport.model_validate_json(first_report_bytes)
    assert first_report.inspection.added == 1
    assert first_report.inspection.updated == 0
    if mode == "unapproved":
        assert first_report.approval is None
    else:
        assert first_report.approval is not None
    if predecessor is None:
        assert store.status().stage == "initialized"
    else:
        assert store.status().stage == "planned"
        assert store.resume_checkpoint(predecessor.checkpoint_id).stage == "plan"

    repaired = run_plan(tmp_path, **approval)

    assert repaired.report_path.read_bytes() == first_report_bytes
    assert repaired.report.inspection == first_report.inspection
    assert repaired.report.plan_fingerprint == first_report.plan_fingerprint
    assert repaired.current_inspection.added == 0
    assert repaired.current_inspection.updated == 0
    assert repaired.current_inspection.unchanged > first_report.inspection.unchanged
    assert store.status().stage == expected_project_stage
    with store.connect() as connection:
        stage_payload = json.loads(
            connection.execute("SELECT outputs_json FROM stages WHERE stage = 'plan'").fetchone()[0]
        )
        checkpoint_rows = connection.execute("SELECT stage FROM checkpoints").fetchall()
    assert stage_payload["inspection"] == first_report.inspection.model_dump(mode="json")
    assert {row["stage"] for row in checkpoint_rows} == expected_checkpoint_stages


@pytest.mark.parametrize("retry_with_flags", [True, False])
def test_run_plan_requires_explicit_flags_to_replay_approval_over_unapproved_predecessor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    retry_with_flags: bool,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    predecessor = run_plan(tmp_path)
    with store.connect() as connection:
        predecessor_stage = tuple(
            connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone()
        )
        predecessor_checkpoints = [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM checkpoints ORDER BY checkpoint_id"
            ).fetchall()
        ]
    original_transition = ProjectStore.save_workflow_transition
    failed = False

    def fail_once(self: ProjectStore, *args: object, **kwargs: object) -> str:
        nonlocal failed
        if not failed:
            failed = True
            raise sqlite3.OperationalError("injected approval transition failure")
        return original_transition(self, *args, **kwargs)

    monkeypatch.setattr(ProjectStore, "save_workflow_transition", fail_once)
    with pytest.raises(PlanningWriteError, match="injected approval transition failure"):
        run_plan(tmp_path, approve_topic="topic-01", author="Author")

    approved_report_bytes = predecessor.report_path.read_bytes()
    approved_report = PlanReport.model_validate_json(approved_report_bytes)
    assert approved_report.approval is not None
    assert approved_report.approval.author == "Author"
    assert store.status().stage == "planned"
    with store.connect() as connection:
        stage_after_failure = tuple(
            connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone()
        )
        checkpoints_after_failure = [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM checkpoints ORDER BY checkpoint_id"
            ).fetchall()
        ]
    assert stage_after_failure == predecessor_stage
    assert checkpoints_after_failure == predecessor_checkpoints
    assert store.resume_checkpoint(predecessor.checkpoint_id).stage == "plan"

    if not retry_with_flags:
        with pytest.raises(PlanningWriteError, match="deterministic checkpoint ID collision"):
            run_plan(tmp_path)
        assert predecessor.report_path.read_bytes() == approved_report_bytes
        with store.connect() as connection:
            assert (
                tuple(connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone())
                == predecessor_stage
            )
            assert [
                tuple(row)
                for row in connection.execute(
                    "SELECT * FROM checkpoints ORDER BY checkpoint_id"
                ).fetchall()
            ] == predecessor_checkpoints

    repaired = run_plan(tmp_path, approve_topic="topic-01", author="Author")

    assert repaired.report_path.read_bytes() == approved_report_bytes
    assert repaired.report.approval == approved_report.approval
    assert repaired.checkpoint_id != predecessor.checkpoint_id
    assert store.status().stage == "topic-approved"
    with store.connect() as connection:
        stage_after = connection.execute(
            "SELECT status, outputs_json, approved_by FROM stages WHERE stage = 'plan'"
        ).fetchone()
        checkpoint_rows = connection.execute(
            "SELECT checkpoint_id, stage, payload_json FROM checkpoints ORDER BY checkpoint_id"
        ).fetchall()
    assert tuple(stage_after)[::2] == ("approved", "Author")
    assert json.loads(stage_after["outputs_json"])["approval"] == (
        approved_report.approval.model_dump(mode="json")
    )
    assert {(row["checkpoint_id"], row["stage"]) for row in checkpoint_rows} == {
        (predecessor.checkpoint_id, "plan"),
        (repaired.checkpoint_id, "plan-approval"),
    }


def test_run_plan_requires_explicit_flags_to_replay_failed_historical_approval_switch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    approval_a = run_plan(tmp_path, approve_topic="topic-01", author="Author A")
    approval_b = run_plan(tmp_path, approve_topic="topic-01", author="Author B")
    original_transition = ProjectStore.save_workflow_transition
    failed = False

    def fail_once(self: ProjectStore, *args: object, **kwargs: object) -> str:
        nonlocal failed
        if not failed:
            failed = True
            raise sqlite3.OperationalError("injected historical switch failure")
        return original_transition(self, *args, **kwargs)

    monkeypatch.setattr(ProjectStore, "save_workflow_transition", fail_once)
    with pytest.raises(PlanningWriteError, match="injected historical switch failure"):
        run_plan(tmp_path, approve_topic="topic-01", author="Author A")

    switched_report_bytes = approval_b.report_path.read_bytes()
    switched_report = PlanReport.model_validate_json(switched_report_bytes)
    assert switched_report.approval == approval_a.report.approval
    assert store.status().stage == "topic-approved"
    with store.connect() as connection:
        predecessor_stage = connection.execute(
            "SELECT status, outputs_json, approved_by FROM stages WHERE stage = 'plan'"
        ).fetchone()
    assert tuple(predecessor_stage)[::2] == ("approved", "Author B")
    assert json.loads(predecessor_stage["outputs_json"])["approval"] == (
        approval_b.report.approval.model_dump(mode="json")
    )
    with store.connect() as connection:
        stage_before = tuple(
            connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone()
        )
        checkpoints_before = [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM checkpoints ORDER BY checkpoint_id"
            ).fetchall()
        ]

    with pytest.raises(PlanningWriteError, match="deterministic checkpoint ID collision"):
        run_plan(tmp_path)

    assert approval_b.report_path.read_bytes() == switched_report_bytes
    with store.connect() as connection:
        assert (
            tuple(connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone())
            == stage_before
        )
        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM checkpoints ORDER BY checkpoint_id"
            ).fetchall()
        ] == checkpoints_before

    repaired = run_plan(tmp_path, approve_topic="topic-01", author="Author A")

    assert repaired.report_path.read_bytes() == switched_report_bytes
    assert repaired.report.approval == approval_a.report.approval
    assert repaired.checkpoint_id == approval_a.checkpoint_id
    with store.connect() as connection:
        stage = connection.execute(
            "SELECT status, outputs_json, approved_by FROM stages WHERE stage = 'plan'"
        ).fetchone()
        checkpoint_count = connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]
    assert tuple(stage)[::2] == ("approved", "Author A")
    assert json.loads(stage["outputs_json"])["approval"] == (
        approval_a.report.approval.model_dump(mode="json")
    )
    assert checkpoint_count == 2


def test_no_flags_rejects_schema_valid_unrequested_approval_report(
    tmp_path: Path,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    current = run_plan(tmp_path, approve_topic="topic-01", author="Author B")
    report_payload = json.loads(current.report_path.read_text(encoding="utf-8"))
    report_payload["approval"]["author"] = "Mallory"
    current.report_path.write_text(json.dumps(report_payload), encoding="utf-8")
    mallory_report_bytes = current.report_path.read_bytes()
    mallory_report = PlanReport.model_validate_json(mallory_report_bytes)
    assert mallory_report.approval is not None
    assert mallory_report.approval.author == "Mallory"
    with store.connect() as connection:
        stage_before = tuple(
            connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone()
        )
        checkpoints_before = [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM checkpoints ORDER BY checkpoint_id"
            ).fetchall()
        ]

    with pytest.raises(PlanningWriteError, match="deterministic checkpoint ID collision"):
        run_plan(tmp_path)

    assert current.report_path.read_bytes() == mallory_report_bytes
    with store.connect() as connection:
        assert (
            tuple(connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone())
            == stage_before
        )
        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM checkpoints ORDER BY checkpoint_id"
            ).fetchall()
        ] == checkpoints_before

    repaired = run_plan(tmp_path, approve_topic="topic-01", author="Mallory")

    assert repaired.report.approval == mallory_report.approval
    with store.connect() as connection:
        stage = connection.execute(
            "SELECT approved_by, outputs_json FROM stages WHERE stage = 'plan'"
        ).fetchone()
        checkpoint_count = connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]
    assert stage["approved_by"] == "Mallory"
    assert json.loads(stage["outputs_json"])["approval"] == (
        mallory_report.approval.model_dump(mode="json")
    )
    assert checkpoint_count == 2


def test_no_flags_rejects_historical_approval_report_replacement(tmp_path: Path) -> None:
    store, _candidates = prepared_project(tmp_path)
    approval_a = run_plan(tmp_path, approve_topic="topic-01", author="Author A")
    approval_a_bytes = approval_a.report_path.read_bytes()
    approval_b = run_plan(tmp_path, approve_topic="topic-01", author="Author B")
    approval_b.report_path.write_bytes(approval_a_bytes)
    with store.connect() as connection:
        stage_before = tuple(
            connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone()
        )
        checkpoints_before = [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM checkpoints ORDER BY checkpoint_id"
            ).fetchall()
        ]

    with pytest.raises(PlanningWriteError, match="deterministic checkpoint ID collision"):
        run_plan(tmp_path)

    assert approval_b.report_path.read_bytes() == approval_a_bytes
    with store.connect() as connection:
        assert (
            tuple(connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone())
            == stage_before
        )
        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM checkpoints ORDER BY checkpoint_id"
            ).fetchall()
        ] == checkpoints_before

    repaired = run_plan(tmp_path, approve_topic="topic-01", author="Author A")

    assert repaired.report.approval == approval_a.report.approval
    assert repaired.checkpoint_id == approval_a.checkpoint_id
    with store.connect() as connection:
        stage = connection.execute(
            "SELECT approved_by, outputs_json FROM stages WHERE stage = 'plan'"
        ).fetchone()
        checkpoint_count = connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]
    assert stage["approved_by"] == "Author A"
    assert json.loads(stage["outputs_json"])["approval"] == (
        approval_a.report.approval.model_dump(mode="json")
    )
    assert checkpoint_count == 2


@pytest.mark.parametrize(
    "corruption",
    [
        "project-stage",
        "stage-status",
        "stage-approved-by",
        "checkpoint-missing",
        "checkpoint-stage",
        "payload-report-path",
        "payload-fingerprint",
        "payload-outcome",
        "payload-leading-topic",
        "payload-missing-evidence",
        "payload-inspection-invalid",
        "payload-inspection-missing",
    ],
)
def test_report_first_replay_rejects_tampered_unapproved_predecessor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    corruption: str,
) -> None:
    store, _candidates = prepared_project(tmp_path)
    predecessor = run_plan(tmp_path)
    original_transition = ProjectStore.save_workflow_transition
    failed = False

    def fail_once(self: ProjectStore, *args: object, **kwargs: object) -> str:
        nonlocal failed
        if not failed:
            failed = True
            raise sqlite3.OperationalError("injected approval transition failure")
        return original_transition(self, *args, **kwargs)

    monkeypatch.setattr(ProjectStore, "save_workflow_transition", fail_once)
    with pytest.raises(PlanningWriteError, match="injected approval transition failure"):
        run_plan(tmp_path, approve_topic="topic-01", author="Author")

    with store.connect() as connection:
        if corruption == "project-stage":
            connection.execute("UPDATE project_state SET stage = 'topic-approved'")
        elif corruption == "stage-status":
            connection.execute("UPDATE stages SET status = 'approved' WHERE stage = 'plan'")
        elif corruption == "stage-approved-by":
            connection.execute("UPDATE stages SET approved_by = 'Mallory' WHERE stage = 'plan'")
        elif corruption == "checkpoint-missing":
            connection.execute(
                "DELETE FROM checkpoints WHERE checkpoint_id = ?",
                (predecessor.checkpoint_id,),
            )
        elif corruption == "checkpoint-stage":
            connection.execute(
                "UPDATE checkpoints SET stage = 'plan-approval' WHERE checkpoint_id = ?",
                (predecessor.checkpoint_id,),
            )
        else:
            stage_payload = json.loads(
                connection.execute(
                    "SELECT outputs_json FROM stages WHERE stage = 'plan'"
                ).fetchone()[0]
            )
            if corruption == "payload-report-path":
                stage_payload["report_path"] = "tampered-report.json"
            elif corruption == "payload-fingerprint":
                stage_payload["plan_fingerprint"] = "f" * 64
            elif corruption == "payload-outcome":
                stage_payload["outcome"] = "analysis-note"
            elif corruption == "payload-leading-topic":
                stage_payload["leading_topic_id"] = None
            elif corruption == "payload-missing-evidence":
                stage_payload["missing_evidence"] = ["ev-tampered"]
            elif corruption == "payload-inspection-invalid":
                stage_payload["inspection"]["discovered"] = -1
            else:
                del stage_payload["inspection"]
            raw_payload = json.dumps(stage_payload, sort_keys=True)
            connection.execute(
                "UPDATE stages SET outputs_json = ? WHERE stage = 'plan'",
                (raw_payload,),
            )
            connection.execute(
                "UPDATE checkpoints SET payload_json = ? WHERE checkpoint_id = ?",
                (raw_payload, predecessor.checkpoint_id),
            )

    report_before = predecessor.report_path.read_bytes()
    with store.connect() as connection:
        project_before = tuple(connection.execute("SELECT * FROM project_state").fetchone())
        stage_before = tuple(
            connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone()
        )
        checkpoints_before = [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM checkpoints ORDER BY checkpoint_id"
            ).fetchall()
        ]

    with pytest.raises(PlanningWriteError, match="deterministic checkpoint ID collision"):
        run_plan(tmp_path, approve_topic="topic-01", author="Author")

    assert predecessor.report_path.read_bytes() == report_before
    with store.connect() as connection:
        assert tuple(connection.execute("SELECT * FROM project_state").fetchone()) == project_before
        assert (
            tuple(connection.execute("SELECT * FROM stages WHERE stage = 'plan'").fetchone())
            == stage_before
        )
        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM checkpoints ORDER BY checkpoint_id"
            ).fetchall()
        ] == checkpoints_before
