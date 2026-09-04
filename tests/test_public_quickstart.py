import json
import re
import shutil
import sqlite3
from pathlib import Path

import yaml
from typer.testing import CliRunner

from cfdpaper.cli import app

EXAMPLE_ROOT = Path(__file__).resolve().parents[1] / "examples" / "quickstart"
REPOSITORY_ROOT = EXAMPLE_ROOT.parents[1]
RUNNER = CliRunner()


def _invoke(arguments: list[str]):
    result = RUNNER.invoke(app, arguments)
    assert result.exit_code == 0, result.stdout
    return result


def test_public_quickstart_runs_from_a_copied_directory(tmp_path: Path) -> None:
    copied_example = tmp_path / "quickstart"
    shutil.copytree(EXAMPLE_ROOT, copied_example)
    project = copied_example / "project"
    candidates = copied_example / "candidates.json"
    source_count = sum(path.is_file() for path in project.rglob("*"))

    initialized = _invoke(["init", str(project), "--project-id", "synthetic-duct-study"])
    inspected = _invoke(["inspect", str(project)])
    planned = _invoke(["plan", str(project), "--candidates", str(candidates)])
    status = _invoke(["status", str(project)])

    assert "Initialized synthetic-duct-study" in initialized.stdout
    assert f"{source_count} discovered" in inspected.stdout
    assert "outcome=missing-evidence" in planned.stdout
    assert "leading=pressure-loss-screening" in planned.stdout
    assert "gaps=4" in planned.stdout
    assert "approval=none" in planned.stdout
    assert "Project synthetic-duct-study: planned" in status.stdout
    assert "checkpoint plan" in status.stdout

    state = project / ".cfdpaper"
    database = state / "project.db"
    report_path = state / "outputs" / "plan" / "topic-ranking.json"
    assert database.is_file()
    assert (state / "index_manifest.json").is_file()
    assert report_path.is_file()

    with sqlite3.connect(database) as connection:
        checkpoint_stages = {
            str(row[0]) for row in connection.execute("SELECT stage FROM checkpoints")
        }
    assert {"inspect", "plan"} <= checkpoint_stages

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["project_id"] == "synthetic-duct-study"
    assert report["ranking"]["outcome"] == "missing-evidence"
    assert report["approval"] is None

    checkout = str(EXAMPLE_ROOT.resolve())
    checkout_posix = EXAMPLE_ROOT.resolve().as_posix()
    for artifact in state.rglob("*"):
        if artifact.is_file():
            payload = artifact.read_bytes()
            assert checkout.encode() not in payload
            assert checkout_posix.encode() not in payload


def test_public_quickstart_sources_are_synthetic_and_path_independent() -> None:
    candidates = json.loads((EXAMPLE_ROOT / "candidates.json").read_text(encoding="utf-8"))

    assert candidates["schema_version"] == 1
    assert len(candidates["candidates"]) == 2
    evidence_ids = {
        evidence_id
        for candidate in candidates["candidates"]
        for evidence_id in candidate["supporting_evidence_ids"]
    }
    assert evidence_ids
    assert all(evidence_id.startswith("demo-") for evidence_id in evidence_ids)

    windows_user_root = "".join(("C:", chr(92), "Users", chr(92)))
    forbidden_fragments = (windows_user_root, "/home/", "/Users/", "file://")
    for path in EXAMPLE_ROOT.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert all(fragment not in text for fragment in forbidden_fragments)


def test_public_docs_match_the_v030_capability_contract() -> None:
    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    capability_section = readme.split("## Capability matrix", 1)[1].split("\n## ", 1)[0]
    state_cells = {
        match.strip().strip("`")
        for match in re.findall(r"^\|[^|]+\|([^|]+)\|[^|]+\|$", capability_section, re.MULTILINE)
        if "---" not in match and "State" not in match
    }

    assert state_cells == {"Available", "Experimental", "Roadmap"}
    for command in (
        "cfdpaper init . --project-id steady-laminar-pipe",
        "cfdpaper inspect .",
        "cfdpaper qualify . --records project-records.json --observations observations.csv "
        "--question question.json",
        "cfdpaper plan . --candidates topic-candidates.json "
        "--approve-topic steady-pipe-pressure-drop",
        "cfdpaper qualify . --approve-qoi-contract QOI_ID",
        "cfdpaper analyze .",
        "cfdpaper figure . --approve-contract FIGURE_ID",
        "cfdpaper write . --artifact results-paragraph",
    ):
        assert command in readme

    ordered_commands = (
        "cfdpaper init .",
        "cfdpaper inspect .",
        "cfdpaper qualify . --records",
        "cfdpaper plan .",
        "cfdpaper qualify . --approve-qoi-contract",
        "cfdpaper analyze .",
        "cfdpaper figure .",
        "cfdpaper write .",
    )
    positions = [readme.index(command) for command in ordered_commands]
    assert positions == sorted(positions)

    for overclaim in (
        "fully autonomous",
        "all solvers",
        "complete manuscript generation",
        "production ready",
    ):
        assert overclaim not in readme.casefold()

    linked_targets = (
        "docs/README.md",
        "docs/architecture/overview.md",
        "docs/ROADMAP.md",
        "docs/releases/v0.2.0.md",
        "docs/releases/v0.1.0.md",
        "docs/limitations.md",
        "CONTRIBUTING.md",
        "CITATION.cff",
    )
    for target in linked_targets:
        assert f"]({target})" in readme
        assert (REPOSITORY_ROOT / target).is_file()

    changelog = (REPOSITORY_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [0.3.0] — 2026-09-04" in changelog
    assert "## [0.2.0] — 2026-08-31" in changelog
    assert "alpha" not in changelog.casefold()

    citation = yaml.safe_load((REPOSITORY_ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    assert citation["cff-version"] == "1.2.0"
    assert citation["title"] == "CFD-Paper-Agent"
    assert citation["version"] == "0.3.0"
    assert citation["license"] == "Apache-2.0"

    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for operating_system in ("ubuntu-latest", "windows-latest"):
        assert operating_system in workflow
    for python_version in ('"3.10"', '"3.11"', '"3.12"'):
        assert python_version in workflow
    assert "cfd-paper-agent-0.3.0-distributions" in workflow
    assert "cfd-paper-agent-0.2.0-distributions" not in workflow
