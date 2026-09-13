import json

import pytest
from PIL import Image, ImageDraw
from typer.testing import CliRunner

from cfdpaper.cli import app

runner = CliRunner()


@pytest.mark.parametrize(
    "options,detail",
    [
        ([], "--approve-contract"),
        (["--task-input", "task.json"], "--output"),
        (["--delivery", "delivery.json", "--output", "new"], "Choose"),
        (["--task-input", "task.json", "--output", "new", "--author", "A"], "Do not mix"),
    ],
)
def test_figure_task_cli_explains_action(tmp_path, options, detail):
    result = runner.invoke(app, ["figure", str(tmp_path), *options])
    assert result.exit_code != 0
    assert detail in result.stdout + result.stderr


def test_figure_task_cli_imports_editable_candidate_without_approval(tmp_path):
    (tmp_path / "source.csv").write_text("x,y\n1,2\n2,4\n", encoding="utf-8")
    task = {
        "figure_id": "reference",
        "kind": "data",
        "purpose": "Read paired reference values",
        "claim_ceiling": "Synthetic values only",
        "sources": [{"id": "data", "path": "source.csv", "role": "data", "description": "Rows"}],
        "labels": [{"text": "Pressure drop", "unit": "Pa"}],
    }
    (tmp_path / "task.json").write_text(json.dumps(task), encoding="utf-8")
    package, imported = tmp_path / "package", tmp_path / "imported"
    result = runner.invoke(
        app,
        [
            "figure",
            str(tmp_path),
            "--task-input",
            str(tmp_path / "task.json"),
            "--output",
            str(package),
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    # This fixture tests interchange, not whether the dummy source is a scientific plot.
    (tmp_path / "plot.py").write_text("raise RuntimeError('must not execute on import')\n")
    image = Image.new("RGB", (80, 40), "white")
    ImageDraw.Draw(image).line((10, 30, 60, 10), fill="black")
    image.save(tmp_path / "figure.png")
    delivery = {
        "figure_id": "reference",
        "editable_sources": ["plot.py"],
        "preview": "figure.png",
        "caption": "Synthetic paired values.",
    }
    (tmp_path / "delivery.json").write_text(json.dumps(delivery), encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "figure",
            str(tmp_path),
            "--package",
            str(package),
            "--delivery",
            str(tmp_path / "delivery.json"),
            "--output",
            str(imported),
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "candidate imported" in result.stdout
    record = json.loads((imported / "delivery.json").read_text())
    assert record["scientific_approval"] is False
    assert (imported / "sources/data/source.csv").read_bytes() == (
        tmp_path / "source.csv"
    ).read_bytes()
