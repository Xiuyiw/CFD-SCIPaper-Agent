import json
import os
import re
from pathlib import Path

from typer.testing import CliRunner

from cfdpaper.cli import app
from cfdpaper.contracts import EvidenceRecord
from cfdpaper.indexing import ProjectIndexer
from cfdpaper.state import initialize_project
from cfdpaper.storage import ProjectStore

runner = CliRunner()
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _plain_cli_text(value: str) -> str:
    return ANSI_ESCAPE.sub("", value)


def test_init_creates_project_state_without_api_key(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()

    result = runner.invoke(app, ["init", str(project), "--project-id", "demo"])

    assert result.exit_code == 0, result.stdout
    assert (project / ".cfdpaper" / "project.db").exists()
    assert (project / ".cfdpaper" / "index_manifest.json").exists()


def test_status_resumes_initialized_project(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    assert runner.invoke(app, ["init", str(project), "--project-id", "demo"]).exit_code == 0

    result = runner.invoke(app, ["status", str(project)])

    assert result.exit_code == 0, result.stdout
    assert "demo" in result.stdout
    assert "initialized" in result.stdout


def test_init_reports_stable_user_error_for_different_project_id(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    assert runner.invoke(app, ["init", str(project), "--project-id", "first"]).exit_code == 0

    result = runner.invoke(app, ["init", str(project), "--project-id", "second"])

    assert result.exit_code == 2
    assert "already initialized as first" in result.stdout + result.stderr


def test_inspect_discovers_and_indexes_files_then_status_reports_counts(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "results.csv").write_text("case,dp\nA,12\n", encoding="utf-8")
    assert runner.invoke(app, ["init", str(project), "--project-id", "demo"]).exit_code == 0

    inspected = runner.invoke(app, ["inspect", str(project)])
    status = runner.invoke(app, ["status", str(project)])

    assert inspected.exit_code == 0, inspected.stdout
    assert "1 discovered" in inspected.stdout
    assert "1 added" in inspected.stdout
    assert status.exit_code == 0, status.stdout
    assert "inspected" in status.stdout
    assert "1 sources" in status.stdout
    assert "0 stale" in status.stdout
    assert "checkpoint inspect" in status.stdout


def test_remaining_roadmap_commands_are_explicitly_unimplemented() -> None:
    for command in ("review", "revise", "export"):
        result = runner.invoke(app, [command])

        assert result.exit_code != 0
        assert "not implemented" in result.stdout


def test_top_level_help_labels_unavailable_commands_as_roadmap() -> None:
    result = runner.invoke(app, ["--help"], terminal_width=120)

    assert result.exit_code == 0, result.stdout
    normalized = " ".join(_plain_cli_text(result.stdout).split())
    for command in ("review", "revise", "export"):
        assert f"{command} Roadmap command; not available in v0.3.0." in normalized
    for command in ("qualify", "analyze", "figure", "write"):
        assert f"{command} Roadmap command; not available in v0.3.0." not in normalized


def prepared_cli_project(tmp_path: Path) -> ProjectStore:
    initialize_project(tmp_path, "demo")
    source = tmp_path / "results.csv"
    source.write_text("case,dp\nA,12\n", encoding="utf-8")
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
    candidate_path = tmp_path / ".cfdpaper" / "inputs" / "topic_candidates.json"
    candidate_path.parent.mkdir(parents=True)
    candidate_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "candidates": [
                    {
                        "topic_id": "topic-01",
                        "title": "Pressure-loss comparison",
                        "research_question": ("How does configuration affect pressure loss?"),
                        "supporting_evidence_ids": ["ev-01"],
                        "required_evidence_kinds": ["qoi"],
                        "required_maturity": "verified",
                        "minimum_verified_evidence": 1,
                        "significance": 0.8,
                        "novelty": 0.7,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return store


def test_plan_help_exposes_real_inputs() -> None:
    result = runner.invoke(app, ["plan", "--help"])

    assert result.exit_code == 0
    help_text = _plain_cli_text(result.stdout)
    assert "--candidates" in help_text
    assert "--approve-topic" in help_text
    assert "--author" in help_text
    assert "--provider" in help_text
    assert "--regenerate" in help_text


def test_plan_cli_writes_report_and_prints_fast_inspection_boundary(
    tmp_path: Path,
) -> None:
    store = prepared_cli_project(tmp_path)

    result = runner.invoke(app, ["plan", str(tmp_path)])

    assert result.exit_code == 0, result.stdout
    assert "outcome=manuscript" in result.stdout
    assert "leading=topic-01" in result.stdout
    assert "gaps=0" in result.stdout
    assert "approval=none" in result.stdout
    assert "inspection=fast" in result.stdout
    assert "1 discovered" in result.stdout
    assert "0 added" in result.stdout
    assert "0 updated" in result.stdout
    assert "1 unchanged" in result.stdout
    assert "0 stale" in result.stdout
    assert "not a strict full hash" in result.stdout
    assert "Previous approval invalidated" not in result.stdout
    assert "topic-ranking.json" in result.stdout
    assert store.status().stage == "planned"


def test_plan_cli_reports_missing_data_when_no_author_candidate_file_exists(tmp_path: Path) -> None:
    initialize_project(tmp_path, "demo")

    result = runner.invoke(app, ["plan", str(tmp_path)])

    assert result.exit_code == 0, result.stdout
    assert "source=generated" in result.stdout
    assert "outcome=missing-evidence" in result.stdout
    assert "approval=none" in result.stdout


def test_plan_cli_auto_truthfully_falls_back_and_named_provider_fails_closed(
    tmp_path: Path,
) -> None:
    auto_project = tmp_path / "auto"
    auto_project.mkdir()
    initialize_project(auto_project, "auto")
    named_project = tmp_path / "named"
    named_project.mkdir()
    initialize_project(named_project, "named")

    auto = runner.invoke(app, ["plan", str(auto_project), "--provider", "auto"])
    named = runner.invoke(app, ["plan", str(named_project), "--provider", "openai"])

    assert auto.exit_code == 0, auto.stdout
    assert "source=generated" in auto.stdout
    assert "generation=offline-fallback" in auto.stdout
    assert "generation-gaps=" in auto.stdout
    assert "candidate-generation-report.json" in auto.stdout
    assert named.exit_code == 2
    assert "explicit-provider-unavailable" in named.stdout + named.stderr


def test_plan_cli_rejects_regenerate_for_author_candidates_without_generation(
    tmp_path: Path,
) -> None:
    prepared_cli_project(tmp_path)

    result = runner.invoke(app, ["plan", str(tmp_path), "--regenerate"])

    assert result.exit_code == 2
    error_text = " ".join(_plain_cli_text(result.stdout + result.stderr).split())
    assert "--regenerate requires generated candidates" in error_text


def test_plan_cli_requires_paired_approval_options(tmp_path: Path) -> None:
    prepared_cli_project(tmp_path)

    result = runner.invoke(
        app,
        ["plan", str(tmp_path), "--approve-topic", "topic-01"],
    )

    assert result.exit_code == 2
    error_text = _plain_cli_text(result.stdout + result.stderr)
    assert "--approve-topic and --author must be supplied together" in error_text


def test_plan_cli_reports_defensible_topic_approval(tmp_path: Path) -> None:
    store = prepared_cli_project(tmp_path)

    result = runner.invoke(
        app,
        [
            "plan",
            str(tmp_path),
            "--approve-topic",
            "topic-01",
            "--author",
            "Author",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "outcome=manuscript" in result.stdout
    assert "approval=manuscript-topic" in result.stdout
    assert store.status().stage == "topic-approved"


def test_plan_cli_prints_dynamic_topic_and_report_path_without_rich_markup(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project[raw]"
    project.mkdir()
    store = prepared_cli_project(project)
    candidate_path = project / ".cfdpaper" / "inputs" / "topic_candidates.json"
    candidate_payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate_payload["candidates"][0]["topic_id"] = "[/bold]"
    candidate_path.write_text(json.dumps(candidate_payload), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "plan",
            str(project),
            "--approve-topic",
            "[/bold]",
            "--author",
            "Author",
        ],
    )

    assert result.exit_code == 0, result.exception
    assert "leading=[/bold]" in result.stdout
    assert f"report {project / '.cfdpaper' / 'outputs' / 'plan' / 'topic-ranking.json'}" in (
        result.stdout
    )
    assert store.status().stage == "topic-approved"


def test_plan_cli_direction_only_output_does_not_imply_manuscript_eligibility(
    tmp_path: Path,
) -> None:
    store = prepared_cli_project(tmp_path)
    (tmp_path / "results.csv").unlink()

    result = runner.invoke(
        app,
        [
            "plan",
            str(tmp_path),
            "--approve-topic",
            "topic-01",
            "--author",
            "Author",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "outcome=analysis-note" in result.stdout
    assert "approval=direction-only" in result.stdout
    assert "manuscript-topic" not in result.stdout
    assert "topic-approved" not in result.stdout
    assert store.status().stage == "planned"


def test_plan_cli_error_does_not_echo_existing_report_contents(tmp_path: Path) -> None:
    prepared_cli_project(tmp_path)
    first = runner.invoke(app, ["plan", str(tmp_path)])
    assert first.exit_code == 0, first.stdout
    report_path = tmp_path / ".cfdpaper" / "outputs" / "plan" / "topic-ranking.json"
    report_path.write_text('{"secret":"REPORT-SECRET"}', encoding="utf-8")

    result = runner.invoke(app, ["plan", str(tmp_path)])

    assert result.exit_code == 2
    assert "REPORT-SECRET" not in result.stdout + result.stderr


def test_plan_cli_only_reports_approval_invalidation_when_it_occurs(
    tmp_path: Path,
) -> None:
    store = prepared_cli_project(tmp_path)
    first = runner.invoke(
        app,
        [
            "plan",
            str(tmp_path),
            "--approve-topic",
            "topic-01",
            "--author",
            "Author",
        ],
    )
    assert first.exit_code == 0, first.stdout
    (tmp_path / "results.csv").write_text("case,dp\nA,1200\n", encoding="utf-8")

    result = runner.invoke(app, ["plan", str(tmp_path)])

    assert result.exit_code == 0, result.stdout
    assert "Previous approval invalidated by project, candidate, or evidence change" in (
        result.stdout
    )
    assert store.status().stage == "planned"


def test_inspect_exposes_strict_hash_mode(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    source = project / "result.txt"
    source.write_text("value=12", encoding="utf-8")
    assert runner.invoke(app, ["init", str(project), "--project-id", "demo"]).exit_code == 0
    assert runner.invoke(app, ["inspect", str(project)]).exit_code == 0
    original = ProjectStore.open(project).get_source("result.txt")
    source.write_text("value=10", encoding="utf-8")
    stat = source.stat()
    os.utime(source, ns=(stat.st_atime_ns, original.mtime_ns))

    result = runner.invoke(app, ["inspect", str(project), "--strict-hash"])

    assert result.exit_code == 0, result.stdout
    assert "1 updated" in result.stdout
