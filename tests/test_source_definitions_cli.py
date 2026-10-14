from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cfdpaper import materials
from cfdpaper.cli import app


def _invoke(root: Path, output: Path, *arguments: str):
    return CliRunner().invoke(
        app, ["inspect", str(root), "--materials", "--output", str(output), *arguments]
    )


def _plain(text: str) -> str:
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)


def test_python_profile_indexes_definitions_after_the_preview(tmp_path: Path) -> None:
    text = "# preface\n" * 150 + "class Model:\n    def rhs(self):\n        return 1\n"
    (tmp_path / "model.py").write_bytes(text.encode("utf-8"))
    document = materials.profile_materials(tmp_path)["documents"][0]
    assert document["truncated"] is True
    assert "class Model" not in document["excerpt"]
    assert [item["qualified_name"] for item in document["definition_index"]] == [
        "Model",
        "Model.rhs",
    ]
    assert document["definition_index"][1]["start_line"] == 152
    assert "definition_index_error" not in document


def test_invalid_python_profile_keeps_source_text_and_index_error(tmp_path: Path) -> None:
    (tmp_path / "invalid.py").write_text("def incomplete(:\n    pass\n", encoding="utf-8")
    (tmp_path / "methods.txt").write_text("method prose\n", encoding="utf-8")
    profile = materials.profile_materials(tmp_path)
    invalid, prose = profile["documents"]
    assert "1: def incomplete(:" in invalid["excerpt"]
    assert invalid["definition_index"] == []
    assert invalid["definition_index_error"]["code"] == "syntax_error"
    assert invalid["definition_index_error"]["message"]
    assert "definition_index" not in prose
    assert profile["issues"] == []


def test_definition_cli_returns_exact_source_with_relative_file_locators(tmp_path: Path) -> None:
    root = tmp_path / "study"
    (root / "models").mkdir(parents=True)
    text = (
        "# ignored preface\r\n"
        "class Model:\r\n"
        "    @staticmethod\r\n"
        "    def rhs(x):\r\n"
        "        return (\r\n"
        "            x * 2\r\n"
        "        )\r\n"
    )
    source = root / "models/thermal.py"
    source.write_bytes(text.encode("utf-8"))
    before = source.read_bytes()
    output = tmp_path / "definitions"

    result = _invoke(
        root, output, "--definition", "Model.rhs", "--material-path", "models/thermal.py"
    )

    assert result.exit_code == 0, result.output
    data = json.loads((output / "source-definitions.json").read_text(encoding="utf-8"))
    assert data["qualified_names"] == ["Model.rhs"]
    assert data["issues"] == []
    definition = data["definitions"][0]
    assert definition["path"] == "models/thermal.py"
    assert definition["text"] == "".join(text.splitlines(keepends=True)[2:])
    assert definition["source"] == {
        "path": "models/thermal.py",
        "locator": "line:3-line:7",
    }
    assert definition["complete"] is True
    assert definition["truncated"] is False
    assert not (output / "materials.json").exists()
    assert source.read_bytes() == before


def test_definition_cli_and_profile_never_execute_target_code(tmp_path: Path) -> None:
    root = tmp_path / "study"
    root.mkdir()
    marker = tmp_path / "execution-marker"
    text = (
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        "raise RuntimeError('must not execute')\n"
        "@undefined_decorator()\n"
        "def rhs():\n"
        "    return 2\n"
    )
    (root / "dangerous.py").write_bytes(text.encode("utf-8"))
    result = _invoke(
        root, tmp_path / "definitions", "--definition", "rhs", "--material-path", "dangerous.py"
    )
    assert result.exit_code == 0, result.output
    profile = _invoke(root, tmp_path / "profile")
    assert profile.exit_code == 0, profile.output
    data = json.loads((tmp_path / "profile/materials.json").read_text(encoding="utf-8"))
    assert data["documents"][0]["definition_index"][0]["qualified_name"] == "rhs"
    assert not marker.exists()


def test_repeated_names_are_requested_in_every_exact_file(tmp_path: Path) -> None:
    root = tmp_path / "study"
    root.mkdir()
    content = "def first():\n    return 1\ndef second():\n    return 2\n"
    for name in ["a.py", "b.py"]:
        (root / name).write_bytes(content.encode("utf-8"))
    output = tmp_path / "definitions"
    result = _invoke(
        root,
        output,
        "--definition",
        "first",
        "--definition",
        "second",
        "--material-path",
        "a.py",
        "--material-path",
        "b.py",
    )
    assert result.exit_code == 0, result.output
    data = json.loads((output / "source-definitions.json").read_text(encoding="utf-8"))
    assert [(item["path"], item["qualified_name"]) for item in data["definitions"]] == [
        ("a.py", "first"),
        ("a.py", "second"),
        ("b.py", "first"),
        ("b.py", "second"),
    ]


def test_missing_name_in_one_file_does_not_count_as_complete_request(tmp_path: Path) -> None:
    root = tmp_path / "study"
    root.mkdir()
    (root / "a.py").write_text("def rhs():\n    return 1\n", encoding="utf-8")
    (root / "b.py").write_text("def other():\n    return 2\n", encoding="utf-8")
    output = tmp_path / "definitions"
    result = _invoke(
        root, output, "--definition", "rhs", "--material-path", "a.py", "--material-path", "b.py"
    )
    assert result.exit_code == 3, result.output
    data = json.loads((output / "source-definitions.json").read_text(encoding="utf-8"))
    assert [item["path"] for item in data["definitions"]] == ["a.py"]
    assert data["issues"][0]["path"] == "b.py"
    assert data["issues"][0]["qualified_name"] == "rhs"
    assert data["issues"][0]["code"] == "missing_definition"
    assert "b.py" in result.output and "rhs" in result.output
    assert "--material-path" in result.output


def test_ambiguity_exposes_all_candidate_line_locators(tmp_path: Path) -> None:
    root = tmp_path / "study"
    root.mkdir()
    (root / "ambiguous.py").write_text(
        "if selection:\n    def rhs():\n        return 1\n"
        "else:\n    def rhs():\n        return 2\n",
        encoding="utf-8",
    )
    output = tmp_path / "definitions"
    result = _invoke(root, output, "--definition", "rhs", "--material-path", "ambiguous.py")
    assert result.exit_code == 3, result.output
    data = json.loads((output / "source-definitions.json").read_text(encoding="utf-8"))
    assert data["definitions"] == []
    issue = data["issues"][0]
    assert issue["code"] == "ambiguous_definition"
    assert [candidate["source"] for candidate in issue["candidates"]] == [
        {"path": "ambiguous.py", "locator": "line:2-line:3"},
        {"path": "ambiguous.py", "locator": "line:5-line:6"},
    ]
    assert "line:2-line:3" in result.output and "line:5-line:6" in result.output


def test_cli_retains_helper_truncation_fields(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "study"
    root.mkdir()
    text = "def rhs():\n    value = '" + "x" * 100 + "'\n    return value\n"
    (root / "long.py").write_bytes(text.encode("utf-8"))
    monkeypatch.setattr(materials, "MAX_EXCERPT_CHARS", 20)
    output = tmp_path / "definitions"
    result = _invoke(root, output, "--definition", "rhs", "--material-path", "long.py")
    assert result.exit_code == 0, result.output
    definition = json.loads((output / "source-definitions.json").read_text(encoding="utf-8"))[
        "definitions"
    ][0]
    assert definition["text"] == text[:20]
    assert definition["complete"] is False
    assert definition["truncated"] is True
    assert definition["last_line_partial"] is True
    assert definition["truncation_note"]


@pytest.mark.parametrize(
    "arguments,expected",
    [
        (["--definition", "rhs"], "--material-path"),
        (["--definition", "rhs", "--material-path", "model.py", "--find", "rhs"], "exclusive"),
    ],
)
def test_definition_requests_need_explicit_paths_and_cannot_use_find(
    tmp_path: Path, arguments: list[str], expected: str
) -> None:
    (tmp_path / "model.py").write_text("def rhs():\n    pass\n", encoding="utf-8")
    output = tmp_path / "definitions"
    result = _invoke(tmp_path, output, *arguments)
    assert result.exit_code == 2, result.output
    assert expected in _plain(result.output)
    assert not output.exists()


def test_definition_requires_materials_and_output(tmp_path: Path) -> None:
    (tmp_path / "model.py").write_text("def rhs():\n    pass\n", encoding="utf-8")
    missing_materials = CliRunner().invoke(
        app, ["inspect", str(tmp_path), "--definition", "rhs", "--material-path", "model.py"]
    )
    assert missing_materials.exit_code == 2
    assert "--materials" in _plain(missing_materials.output)
    missing_output = CliRunner().invoke(
        app,
        [
            "inspect",
            str(tmp_path),
            "--materials",
            "--definition",
            "rhs",
            "--material-path",
            "model.py",
        ],
    )
    assert missing_output.exit_code == 2
    assert "--output" in _plain(missing_output.output)


def test_explicit_definition_reads_keep_existing_scope_and_total_size_budget(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "study"
    (root / "outputs").mkdir(parents=True)
    text = "def rhs():\n    return 1\n"
    (root / "outputs/model.py").write_bytes(text.encode("utf-8"))
    (root / "second.py").write_bytes(text.encode("utf-8"))
    monkeypatch.setattr(materials, "MAX_TOTAL_BYTES", len(text))

    def no_discovery(*args):
        raise AssertionError("exact definition requests must not scan a directory")

    monkeypatch.setattr(materials, "_discover", no_discovery)
    data = materials.read_material_definitions(
        root, ["rhs"], paths=[Path("outputs/model.py"), Path("outputs/model.py"), Path("second.py")]
    )
    assert [item["path"] for item in data["definitions"]] == ["outputs/model.py"]
    assert data["issues"][0]["path"] == "second.py"
    assert data["issues"][0]["code"] == "size_limit"


@pytest.mark.parametrize(
    "selected,code",
    [
        ("../outside.py", "outside_root"),
        ("method.txt", "unsupported_extension"),
        ("missing.py", "unreadable_source"),
    ],
)
def test_definition_path_errors_are_localized_and_actionable(
    tmp_path: Path, selected: str, code: str
) -> None:
    root = tmp_path / "study"
    root.mkdir()
    (root / "method.txt").write_text("def rhs():\n    pass\n", encoding="utf-8")
    output = tmp_path / "definitions"
    result = _invoke(root, output, "--definition", "rhs", "--material-path", selected)
    assert result.exit_code == 3, result.output
    data = json.loads((output / "source-definitions.json").read_text(encoding="utf-8"))
    assert data["issues"][0]["code"] == code
    assert "--material-path" in result.output


def test_definition_file_size_limit_is_reused(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "large.py").write_text("def rhs():\n    return 1\n", encoding="utf-8")
    monkeypatch.setattr(materials, "MAX_FILE_BYTES", 10)
    output = tmp_path / "definitions"
    result = _invoke(tmp_path, output, "--definition", "rhs", "--material-path", "large.py")
    assert result.exit_code == 3
    data = json.loads((output / "source-definitions.json").read_text(encoding="utf-8"))
    assert data["issues"][0]["code"] == "size_limit"


@pytest.mark.parametrize(
    "payload,code",
    [
        (b"def invalid(:\n", "syntax_error"),
        (b"# \xff\ndef rhs():\n    pass\n", "unsupported_encoding"),
    ],
)
def test_definition_parse_errors_remain_actionable_without_losing_json(
    tmp_path: Path, payload: bytes, code: str
) -> None:
    (tmp_path / "broken.py").write_bytes(payload)
    output = tmp_path / "definitions"
    result = _invoke(tmp_path, output, "--definition", "rhs", "--material-path", "broken.py")
    assert result.exit_code == 3, result.output
    data = json.loads((output / "source-definitions.json").read_text(encoding="utf-8"))
    assert data["issues"][0]["code"] == code
    assert data["issues"][0]["qualified_name"] == "rhs"
    assert "--find" in result.output


def test_exact_definition_selection_does_not_follow_links(tmp_path: Path) -> None:
    target = tmp_path / "target.py"
    target.write_text("def rhs():\n    return 1\n", encoding="utf-8")
    link = tmp_path / "link.py"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Symbolic-link creation is unavailable on this host")
    data = materials.read_material_definitions(tmp_path, ["rhs"], paths=[Path("link.py")])
    assert data["definitions"] == []
    assert data["issues"][0]["code"] == "skipped_link"


def test_invalid_python_still_supports_legacy_full_text_find(tmp_path: Path) -> None:
    (tmp_path / "legacy.py").write_text("\n" * 150 + "def invalid(:\n", encoding="utf-8")
    output = tmp_path / "matches"
    result = _invoke(tmp_path, output, "--find", "invalid", "--material-path", "legacy.py")
    assert result.exit_code == 0, result.output
    data = json.loads((output / "material-matches.json").read_text(encoding="utf-8"))
    assert data["matches"][0]["line"] == 151
    assert not (output / "source-definitions.json").exists()
