import json
import runpy
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cfdpaper.cli import app

runner = CliRunner()


@pytest.mark.parametrize(
    "options,detail",
    [
        ([], "Choose one"),
        (["--section-input", "input.json"], "--output"),
        (["--draft", "draft.json", "--output", "new"], "--package"),
        (["--approve-final", "--author", "Author"], "author review"),
        (["--layout", "near-reference"], "--docx"),
    ],
)
def test_section_write_explains_required_action(tmp_path: Path, options: list, detail: str):
    result = runner.invoke(app, ["write", str(tmp_path), "--artifact", "results-section", *options])
    assert result.exit_code != 0
    assert detail in result.stdout + result.stderr


def test_section_options_are_not_silently_ignored_for_paragraph(tmp_path: Path):
    result = runner.invoke(app, ["write", str(tmp_path), "--section-input", "input.json"])
    assert result.exit_code != 0
    assert "results-section" in result.stdout + result.stderr


@pytest.mark.parametrize("layout", ["after-text", "near-reference"])
def test_public_example_runs_through_cli(tmp_path: Path, layout: str):
    pytest.importorskip("docx")
    script = Path(__file__).resolve().parents[1] / "examples/section-writing/prepare_example.py"
    source, package, section = (tmp_path / name for name in ("source", "package", "section"))
    runpy.run_path(str(script))["prepare"](source)
    # Separate synthetic outlets exercise the user-facing table path, not pipe-case CV.
    (source / "sources").mkdir(exist_ok=True)
    (source / "sources/outlets.csv").write_text(
        "case,outlet,flow\nA,1,1\nA,2,3\n", encoding="utf-8"
    )
    input_path = source / "input.json"
    data = json.loads(input_path.read_text(encoding="utf-8"))
    data.setdefault("table_calculations", []).extend(
        [
            {
                "id": "outlet-spread",
                "source": "sources/outlets.csv",
                "operation": "population",
                "columns": {"value": "flow"},
                "units": {"value": "kg/s"},
                "group_by": "case",
                "domain": "Two synthetic outlets per case; equal outlet weights",
            }
        ]
    )
    input_path.write_text(json.dumps(data), encoding="utf-8")
    base = ["write", str(source), "--artifact", "results-section"]
    for options in (
        ["--section-input", str(source / "input.json"), "--output", str(package)],
        [
            "--package",
            str(package),
            "--draft",
            str(source / "sample-draft.json"),
            "--output",
            str(section),
        ],
        [
            "--package",
            str(section),
            "--docx",
            "--layout",
            layout,
            "--output",
            str(tmp_path / "section.docx"),
        ],
    ):
        result = runner.invoke(app, base + options)
        assert result.exit_code == 0, result.stdout + result.stderr
    assert "6.4 Pa" in (section / "section.md").read_text(encoding="utf-8")
    computed = json.loads((section / "review-packet/table-results.json").read_text())
    outlet_report = next(c for c in computed if c["id"] == "outlet-spread")
    assert outlet_report["groups"][0]["result"]["cv"] == 0.5
    assert (section / "review-packet/sources/outlets.csv").read_bytes() == (
        source / "sources/outlets.csv"
    ).read_bytes()
    with zipfile.ZipFile(tmp_path / "section.docx") as doc:
        assert len([name for name in doc.namelist() if name.startswith("word/media/")]) == 2
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps(
            {
                "suggestions": [
                    {
                        "target": "paragraph 1",
                        "comment": "Clarify the comparison",
                        "recommendation": "Retain fixed geometry",
                    }
                ]
            }
        )
    )
    result = runner.invoke(
        app,
        base
        + [
            "--package",
            str(section),
            "--review",
            str(review),
            "--output",
            str(tmp_path / "suggestions.json"),
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
