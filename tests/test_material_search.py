"""Material lookup exposes real source passages without interpreting or executing them."""

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cfdpaper.cli import app
from cfdpaper.material_search import search_materials


def test_find_setting_after_initial_preview_and_multiple_terms(tmp_path):
    source = tmp_path / "设置.json"
    source.write_text(
        "\n" * 150 + '"turbulent_prandtl": 0.85\n"wall_yplus_report": null\n', encoding="utf-8"
    )
    result = search_materials(tmp_path, ["PRANDTL", "wall_yplus"])
    assert [(m["path"], m["line"]) for m in result["matches"]] == [
        ("设置.json", 151),
        ("设置.json", 152),
    ]
    assert result["matches"][0]["context"][-2]["text"] == '"turbulent_prandtl": 0.85'
    assert source.read_text(encoding="utf-8").endswith('"wall_yplus_report": null\n')


def test_script_is_only_text_and_explicit_file_bypasses_exclusion(tmp_path):
    folder = tmp_path / "outputs"
    folder.mkdir()
    source = folder / "model.py"
    source.write_text("raise RuntimeError('must never run')\nmodel = 'example'\n", encoding="utf-8")
    assert not search_materials(tmp_path, ["model"])["matches"]
    result = search_materials(tmp_path, ["model"], paths=[Path("outputs/model.py")])
    assert result["matches"][0]["line"] == 2


def test_long_line_retains_matching_text_and_true_column(tmp_path):
    text = "x" * 4500 + "wall_yplus" + "z" * 3000
    (tmp_path / "one.json").write_text(text, encoding="utf-8")
    row = search_materials(tmp_path, ["wall_yplus"])["matches"][0]["context"][0]
    assert row["line"] == 1 and row["column_start"] == 4301
    assert "wall_yplus" in row["text"] and row["truncated"]
    assert row["text"] == text[row["column_start"] - 1 : row["column_start"] - 1 + 2000]


def test_limit_and_no_match_are_distinct(tmp_path):
    (tmp_path / "setup.txt").write_text("model A\nmodel B\nmodel C\n", encoding="utf-8")
    found = search_materials(tmp_path, ["model"], limit=2)
    assert found["truncated"] and len(found["matches"]) == 2
    assert found["issues"][0]["code"] == "match_limit"
    absent = search_materials(tmp_path, ["not there"])
    assert absent["matches"] == [] and not absent["truncated"]
    assert absent["searched_files"] == ["setup.txt"]


def test_size_skip_and_outside_root_are_explicit(tmp_path, monkeypatch):
    import cfdpaper.material_search as search

    monkeypatch.setattr(search, "MAX_FILE_BYTES", 5)
    (tmp_path / "setup.txt").write_text("model too long", encoding="utf-8")
    result = search_materials(
        tmp_path, ["model"], paths=[Path("setup.txt"), Path("../outside.txt")]
    )
    assert {i["code"] for i in result["issues"]} == {"size_limit", "outside_root"}
    assert not result["matches"]


@pytest.mark.parametrize("terms,limit", [([], 50), ([" "], 50), (["x"], 0), (["x"], True)])
def test_invalid_requests(tmp_path, terms, limit):
    with pytest.raises(ValueError):
        search_materials(tmp_path, terms, limit=limit)


def test_cli_finds_method_text_and_exposes_selection(tmp_path, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    source = tmp_path / "sources"
    source.mkdir()
    (source / "setting.txt").write_text("\n" * 140 + "actual setting = 1", encoding="utf-8")
    output = tmp_path / "matches"
    result = CliRunner().invoke(
        app,
        [
            "inspect",
            str(source),
            "--materials",
            "--find",
            "actual",
            "--material-path",
            "setting.txt",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    record = json.loads((output / "material-matches.json").read_text(encoding="utf-8"))
    assert record["matches"][0]["locator"] == "L141"
    invalid = CliRunner().invoke(app, ["inspect", str(source), "--find", "actual"])
    assert invalid.exit_code != 0
    message = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", invalid.output)
    assert "require" in message and "--materials" in message


def test_selected_materials_reach_analysis_package_without_manual_copy(tmp_path):
    root = tmp_path / "study"
    (root / "outputs").mkdir(parents=True)
    table = root / "outputs/comparison.csv"
    table.write_text("case,rate [W]\nA,1\nB,2\n", encoding="utf-8")
    (root / "definition.txt").write_text("rate is integrated wall heat", encoding="utf-8")
    output = tmp_path / "analysis"
    result = CliRunner().invoke(
        app,
        [
            "plan",
            str(root),
            "--artifact",
            "analysis",
            "--material-path",
            "outputs/comparison.csv",
            "--material-path",
            "definition.txt",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads((output / "materials.json").read_text(encoding="utf-8"))
    assert set(data["source_files"]) == {"sources/outputs/comparison.csv", "sources/definition.txt"}
    assert (output / "sources/outputs/comparison.csv").read_bytes() == table.read_bytes()
    invalid = CliRunner().invoke(app, ["plan", str(root), "--material-path", "definition.txt"])
    assert invalid.exit_code != 0
    assert "analysis" in invalid.output
