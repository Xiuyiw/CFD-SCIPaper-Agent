from __future__ import annotations

import json
import runpy
import shutil
from pathlib import Path

from typer.testing import CliRunner

from cfdpaper.cli import app
from cfdpaper.planning import CandidateInput


def test_generated_topic_example_produces_unapproved_candidates(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    example = repository_root / "examples" / "generated-topic"
    copied = tmp_path / "example"
    shutil.copytree(example, copied)
    project = tmp_path / "project"

    module = runpy.run_path(str(copied / "prepare_project.py"))
    module["prepare_project"](project)
    completed = CliRunner().invoke(
        app,
        ["plan", str(project), "--provider", "offline"],
    )

    assert completed.exit_code == 0, completed.stdout
    output_root = project / ".cfdpaper" / "outputs" / "plan"
    generated = CandidateInput.model_validate_json(
        (output_root / "generated-topic-candidates.json").read_text(encoding="utf-8")
    )
    report = json.loads(
        (output_root / "candidate-generation-report.json").read_text(encoding="utf-8")
    )
    ranking = json.loads((output_root / "topic-ranking.json").read_text(encoding="utf-8"))
    assert 2 <= len(generated.candidates) <= 4
    assert report["minimum_missing_data"] == []
    assert ranking["approval"] is None
