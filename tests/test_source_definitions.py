from __future__ import annotations

import json
from pathlib import Path

import pytest

from cfdpaper import materials
from cfdpaper.source_definitions import (
    SourceDefinitionError,
    python_definition_index,
    read_python_definition,
)


def test_index_preserves_source_order_and_exact_lexical_names() -> None:
    text = (
        "def first():\n"
        "    def nested():\n"
        "        return 1\n"
        "    return nested()\n"
        "class Outer:\n"
        "    class Inner:\n"
        "        async def rhs(self):\n"
        "            return 2\n"
        "    def update(self):\n"
        "        def local():\n"
        "            return 3\n"
        "        return local()\n"
    )

    definitions = python_definition_index(text)

    assert [item["qualified_name"] for item in definitions] == [
        "first",
        "first.nested",
        "Outer",
        "Outer.Inner",
        "Outer.Inner.rhs",
        "Outer.update",
        "Outer.update.local",
    ]
    assert [item["kind"] for item in definitions] == [
        "function",
        "function",
        "class",
        "class",
        "async_method",
        "method",
        "function",
    ]
    assert definitions[4] == {
        "qualified_name": "Outer.Inner.rhs",
        "name": "rhs",
        "kind": "async_method",
        "start_line": 7,
        "end_line": 8,
        "ambiguous": False,
    }
    json.dumps(definitions)


def test_decorators_and_multiline_equation_are_returned_verbatim(tmp_path: Path) -> None:
    path = tmp_path / "methods.py"
    text = (
        "# unrelated source text is retained, not executed\n"
        "class ImprovedS1:\n"
        "    @static_model(\n"
        "        parameter=2,\n"
        "    )\n"
        "    @another_decorator\n"
        "    def rhs(self, state):\n"
        "        energy = (\n"
        "            state[0] * self.coefficient\n"
        "            - self.exchange(state[1])\n"
        "        )  # equation ends here\n"
        "        return energy\n"
        "\n"
        "def unused():\n"
        "    return 0\n"
    )
    path.write_bytes(text.encode("utf-8"))
    before = path.read_bytes()

    result = read_python_definition(path, "ImprovedS1.rhs")

    assert result["text"] == "".join(text.splitlines(keepends=True)[2:12])
    assert result["qualified_name"] == "ImprovedS1.rhs"
    assert result["name"] == "rhs"
    assert result["kind"] == "method"
    assert (result["start_line"], result["end_line"]) == (3, 12)
    assert (result["excerpt_start_line"], result["excerpt_end_line"]) == (3, 12)
    assert result["complete"] is True
    assert result["truncated"] is False
    assert result["truncation_note"] is None
    assert result["source"] == {
        "path": path.as_posix(),
        "locator": "line:3-line:12",
    }
    json.dumps(result)
    assert path.read_bytes() == before


def test_class_decorators_and_nested_class_are_included(tmp_path: Path) -> None:
    path = tmp_path / "methods.py"
    text = "@outer\nclass A:\n    @inner\n    class B:\n        pass\n"
    path.write_bytes(text.encode("utf-8"))

    definitions = python_definition_index(text)
    assert [(item["start_line"], item["end_line"]) for item in definitions] == [(1, 5), (3, 5)]
    result = read_python_definition(path, "A.B")
    assert result["text"] == "    @inner\n    class B:\n        pass\n"


def test_static_reading_has_no_top_level_decorator_or_body_side_effects(tmp_path: Path) -> None:
    marker = tmp_path / "executed.txt"
    path = tmp_path / "dangerous.py"
    text = (
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        "raise RuntimeError('must never execute')\n"
        "@missing_decorator(side_effect())\n"
        "def rhs():\n"
        "    import nonexistent_solver\n"
        "    raise RuntimeError('also never execute')\n"
    )
    path.write_text(text, encoding="utf-8")

    assert python_definition_index(text)[0]["qualified_name"] == "rhs"
    result = read_python_definition(path, "rhs")
    assert result["start_line"] == 4
    assert "nonexistent_solver" in result["text"]
    assert not marker.exists()


@pytest.mark.parametrize(
    "text,qualified_name,lines",
    [
        ("def rhs():\n    return 1\ndef rhs():\n    return 2\n", "rhs", [1, 3]),
        (
            "if selected:\n    def rhs():\n        return 1\n"
            "else:\n    def rhs():\n        return 2\n",
            "rhs",
            [2, 5],
        ),
        (
            "class A:\n    def rhs(self):\n        return 1\n"
            "class A:\n    def rhs(self):\n        return 2\n",
            "A.rhs",
            [2, 5],
        ),
        (
            "class A:\n    @property\n    def x(self):\n        return 1\n"
            "    @x.setter\n    def x(self, value):\n        pass\n",
            "A.x",
            [2, 5],
        ),
    ],
)
def test_duplicate_qualified_names_are_explicitly_ambiguous(
    tmp_path: Path, text: str, qualified_name: str, lines: list[int]
) -> None:
    path = tmp_path / "duplicate.py"
    path.write_text(text, encoding="utf-8")
    matches = [
        item for item in python_definition_index(text) if item["qualified_name"] == qualified_name
    ]
    assert [item["start_line"] for item in matches] == lines
    assert all(item["ambiguous"] for item in matches)

    with pytest.raises(SourceDefinitionError, match="ambiguous") as error:
        read_python_definition(path, qualified_name)
    assert error.value.code == "ambiguous_definition"
    assert error.value.candidates == matches


def test_exact_names_do_not_infer_inheritance_or_active_aliases(tmp_path: Path) -> None:
    path = tmp_path / "methods.py"
    path.write_text(
        "class Base:\n    def rhs(self):\n        return 1\n"
        "class ImprovedS1(Base):\n    pass\nactive = Base\n",
        encoding="utf-8",
    )
    for missing in ["rhs", "ImprovedS1.rhs", "active.rhs"]:
        with pytest.raises(SourceDefinitionError, match="not found") as error:
            read_python_definition(path, missing)
        assert error.value.code == "missing_definition"
    assert read_python_definition(path, "Base.rhs")["name"] == "rhs"


def test_truncated_read_is_exact_prefix_with_explicit_completeness(tmp_path: Path) -> None:
    path = tmp_path / "long.py"
    text = "# before\ndef rhs():\n    value = '" + "x" * 60 + "'\n    return value\n"
    path.write_bytes(text.encode("utf-8"))
    definition = text[text.index("def rhs") :]

    result = read_python_definition(path, "rhs", max_chars=25)

    assert result["text"] == definition[:25]
    assert result["complete"] is False
    assert result["truncated"] is True
    assert result["truncation_note"]
    assert result["definition_chars"] == len(definition)
    assert result["returned_chars"] == 25
    assert (result["start_line"], result["end_line"]) == (2, 4)
    assert (result["excerpt_start_line"], result["excerpt_end_line"]) == (2, 3)
    assert result["last_line_partial"] is True


def test_exact_character_boundary_is_complete(tmp_path: Path) -> None:
    path = tmp_path / "one.py"
    text = "def rhs():\n    return 1"
    path.write_bytes(text.encode("utf-8"))
    result = read_python_definition(path, "rhs", max_chars=len(text))
    assert result["text"] == text
    assert result["complete"] is True
    assert result["last_line_partial"] is False


def test_default_excerpt_limit_reuses_materials_budget(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "one.py"
    path.write_text("def rhs():\n    return 1\n", encoding="utf-8")
    monkeypatch.setattr(materials, "MAX_EXCERPT_CHARS", 10)
    result = read_python_definition(path, "rhs")
    assert len(result["text"]) == 10
    assert result["truncated"] is True


@pytest.mark.parametrize("line_ending", ["\n", "\r\n", "\r"])
def test_original_line_endings_are_preserved(tmp_path: Path, line_ending: str) -> None:
    path = tmp_path / "line_endings.py"
    text = line_ending.join(["# before", "def rhs():", "    return 1", ""])
    path.write_bytes(text.encode("utf-8"))
    result = read_python_definition(path, "rhs")
    assert result["text"] == line_ending.join(["def rhs():", "    return 1", ""])
    assert (result["start_line"], result["end_line"]) == (2, 3)


def test_formfeed_in_a_line_does_not_change_ast_line_locations(tmp_path: Path) -> None:
    path = tmp_path / "physical_lines.py"
    text = "# retained\fcomment\ndef rhs():\n    return '''a\fb'''\n"
    path.write_bytes(text.encode("utf-8"))
    result = read_python_definition(path, "rhs")
    assert result["start_line"] == 2
    assert result["text"] == "def rhs():\n    return '''a\fb'''\n"


def test_truncation_inside_crlf_is_reported_as_partial(tmp_path: Path) -> None:
    path = tmp_path / "crlf.py"
    text = "def rhs():\r\n    return 1\r\n"
    path.write_bytes(text.encode("utf-8"))
    result = read_python_definition(path, "rhs", max_chars=11)
    assert result["text"] == "def rhs():\r"
    assert result["last_line_partial"] is True
    assert result["excerpt_end_line"] == 1


def test_utf8_bom_and_nonascii_text_are_supported(tmp_path: Path) -> None:
    path = tmp_path / "utf8.py"
    text = "def 温差():\n    return '温差单位 K'\n"
    path.write_bytes(text.encode("utf-8-sig"))
    result = read_python_definition(path, "温差")
    assert result["text"] == text


@pytest.mark.parametrize("text", ["def rhs(:\n    pass\n", "def rhs():\n\x00", "print 1\n"])
def test_syntax_error_is_explicit_for_index_and_read(tmp_path: Path, text: str) -> None:
    path = tmp_path / "broken.py"
    path.write_text(text, encoding="utf-8")
    operations = [
        lambda: python_definition_index(text),
        lambda: read_python_definition(path, "rhs"),
    ]
    for operation in operations:
        with pytest.raises(SourceDefinitionError) as error:
            operation()
        assert error.value.code == "syntax_error"


def test_missing_file_and_definition_have_distinct_errors(tmp_path: Path) -> None:
    with pytest.raises(SourceDefinitionError) as error:
        read_python_definition(tmp_path / "missing.py", "rhs")
    assert error.value.code == "unreadable_source"
    path = tmp_path / "empty.py"
    path.write_text("# no definitions\n", encoding="utf-8")
    assert python_definition_index("# no definitions\n") == []
    with pytest.raises(SourceDefinitionError) as error:
        read_python_definition(path, "rhs")
    assert error.value.code == "missing_definition"


def test_only_utf8_python_files_are_read(tmp_path: Path) -> None:
    other = tmp_path / "methods.txt"
    other.write_text("def rhs():\n    pass\n", encoding="utf-8")
    with pytest.raises(SourceDefinitionError) as error:
        read_python_definition(other, "rhs")
    assert error.value.code == "unsupported_extension"
    invalid = tmp_path / "invalid.py"
    invalid.write_bytes(b"# coding: latin-1\ndef rhs():\n    return '\xe9'\n")
    with pytest.raises(SourceDefinitionError) as error:
        read_python_definition(invalid, "rhs")
    assert error.value.code == "unsupported_encoding"


def test_existing_material_file_size_budget_is_enforced(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "large.py"
    path.write_text("def rhs():\n    return 1\n", encoding="utf-8")
    monkeypatch.setattr(materials, "MAX_FILE_BYTES", 10)
    with pytest.raises(SourceDefinitionError) as error:
        read_python_definition(path, "rhs")
    assert error.value.code == "size_limit"


@pytest.mark.parametrize("max_chars", [0, -1, True, 1.5, "20"])
def test_invalid_character_budget_is_not_silently_adjusted(tmp_path: Path, max_chars) -> None:
    path = tmp_path / "methods.py"
    path.write_text("def rhs():\n    pass\n", encoding="utf-8")
    with pytest.raises(SourceDefinitionError) as error:
        read_python_definition(path, "rhs", max_chars=max_chars)
    assert error.value.code == "invalid_limit"
