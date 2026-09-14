from __future__ import annotations

import json
from pathlib import Path

import pytest

from cfdpaper import materials
from cfdpaper.adapters import CSVAdapter
from cfdpaper.materials import profile_materials


def test_table_profile_preserves_headers_units_codes_and_all_row_statistics(tmp_path: Path) -> None:
    source = tmp_path / "results.csv"
    source.write_text(
        "case, pressure drop [Pa] ,group,unknown,mixed\n"
        "001,1,A,,1\n01,2,A,,text\n1,3,B,,2\n2,4,B,,3\n"
        "3,5,A,,4\n4,100,B,,5\n5,,A,,6\n6,nan,B,,7\n7,inf,A,,8\n",
        encoding="utf-8",
    )
    before = source.read_bytes()

    profile = profile_materials(tmp_path)

    assert set(profile) == {"tables", "documents", "figures", "arrays", "issues"}
    table = profile["tables"][0]
    case, pressure, group, unknown, mixed = table["columns"]
    assert table["row_count"] == 9
    assert case["name"] == "case"
    assert case["type"] == "string"
    assert case["examples"] == ["001", "01", "1", "2", "3"]
    assert case["unique_count"] == 9
    assert case["example_locators"] == [f"row:{i}" for i in range(2, 7)]
    assert pressure["name"] == " pressure drop [Pa] "
    assert pressure["label"] == "pressure drop"
    assert pressure["unit"] == "Pa"
    assert pressure["type"] == "number"
    assert pressure["minimum"] == 1
    assert pressure["maximum"] == 100
    assert pressure["missing_count"] == 1
    assert pressure["nonfinite_count"] == 2
    assert pressure["source"] == {"path": "results.csv", "locator": "row:1", "column": 2}
    assert group["unique_count"] == 2
    assert unknown["type"] == "empty"
    assert unknown["unit"] is None
    assert unknown["missing_count"] == 9
    assert mixed["type"] == "mixed"
    assert "minimum" not in mixed
    assert "case" in table["candidate_group_columns"]
    assert "group" in table["candidate_group_columns"]
    assert " pressure drop [Pa] " not in table["candidate_group_columns"]
    assert table["source"]["data_locator"] == "row:2-row:10"
    assert profile["issues"] == []
    json.dumps(profile, allow_nan=False)
    assert source.read_bytes() == before


def test_profile_uses_existing_adapter_inventory_and_extract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "sample.csv").write_text("A\n1\n", encoding="utf-8")
    calls = []
    inventory = CSVAdapter.inventory
    extract = CSVAdapter.extract

    def record_inventory(self, source):
        calls.append("inventory")
        return inventory(self, source)

    def record_extract(self, request):
        calls.append("extract")
        return extract(self, request)

    monkeypatch.setattr(CSVAdapter, "inventory", record_inventory)
    monkeypatch.setattr(CSVAdapter, "extract", record_extract)
    assert profile_materials(tmp_path)["tables"][0]["row_count"] == 1
    assert calls == ["inventory", "extract"]


def test_documents_have_bounded_line_numbered_source_text_and_images_are_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "methods.md").write_text("mean over named surface\nsecond line\nthird\n")
    (tmp_path / "settings.json").write_text('{"operator": "average"}\n')
    (tmp_path / "field.png").write_bytes(b"image bytes never inspected")
    monkeypatch.setattr(materials, "MAX_EXCERPT_LINES", 2)

    profile = profile_materials(tmp_path)

    methods, settings = profile["documents"]
    assert methods["excerpt"] == "1: mean over named surface\n2: second line"
    assert methods["truncated"] is True
    assert methods["line_count"] == 3
    assert methods["source"] == {"path": "methods.md", "locator": "line:1-line:2"}
    assert settings["excerpt"] == '1: {"operator": "average"}'
    assert settings["truncated"] is False
    assert profile["figures"] == [{"path": "field.png"}]


def test_document_character_limit_reports_partial_line(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "long.txt").write_text("x" * 50)
    monkeypatch.setattr(materials, "MAX_EXCERPT_CHARS", 12)
    document = profile_materials(tmp_path)["documents"][0]
    assert len(document["excerpt"]) == 12
    assert document["excerpt"].startswith("1: ")
    assert document["truncated"] is True


@pytest.mark.parametrize("content", ["a,b\n1\n", "a,a\n1,2\n", "\n", ",a\n1,2\n"])
def test_broken_csv_is_localized_without_losing_other_materials(
    tmp_path: Path, content: str
) -> None:
    (tmp_path / "broken.csv").write_text(content)
    (tmp_path / "good.csv").write_text("value [m]\n3\n")
    (tmp_path / "bad.txt").write_bytes(b"\xff\xfe\xff")
    profile = profile_materials(tmp_path)
    assert [table["path"] for table in profile["tables"]] == ["good.csv"]
    assert {issue["path"] for issue in profile["issues"]} == {"broken.csv", "bad.txt"}


@pytest.mark.parametrize(
    "directory", [".git", ".cfdpaper", ".venv", "private-fixtures", "_local_archive", "outputs"]
)
def test_default_exclusions_but_explicit_selection_is_available(
    tmp_path: Path, directory: str
) -> None:
    folder = tmp_path / directory
    folder.mkdir()
    source = folder / "source.csv"
    source.write_text("a\n1\n")
    profile = profile_materials(tmp_path)
    assert profile["tables"] == []
    assert profile["issues"][0]["code"] == "excluded_directory"
    explicit = profile_materials(tmp_path, paths=[source.relative_to(tmp_path)])
    assert explicit["tables"][0]["path"] == f"{directory}/source.csv"


def test_selected_paths_are_rooted_deduplicated_and_missing_or_outside_are_reported(
    tmp_path: Path,
) -> None:
    (tmp_path / "source.csv").write_text("a\n1\n")
    profile = profile_materials(
        tmp_path,
        paths=[
            Path("source.csv"),
            tmp_path / "source.csv",
            Path("missing.csv"),
            Path("../outside.csv"),
            Path("unsupported.sim"),
        ],
    )
    assert len(profile["tables"]) == 1
    assert {issue["code"] for issue in profile["issues"]} == {"unreadable", "outside_root"}


def test_links_are_not_followed_in_discovery_or_explicit_selection(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.csv").write_text("a\n1\n")
    link = tmp_path / "link"
    try:
        link.symlink_to(source, target_is_directory=True)
    except OSError:
        pytest.skip("Symbolic-link creation is unavailable on this host")
    profile = profile_materials(tmp_path)
    assert [table["path"] for table in profile["tables"]] == ["source/a.csv"]
    assert any(issue["code"] == "skipped_link" for issue in profile["issues"])
    explicit = profile_materials(tmp_path, paths=[Path("link/a.csv")])
    assert explicit["tables"] == []
    assert explicit["issues"][0]["code"] == "skipped_link"
    assert profile_materials(link)["issues"][0]["code"] == "invalid_root"


@pytest.mark.parametrize("bound,value", [("MAX_FILES", 1), ("MAX_ENTRIES", 1)])
def test_discovery_limits_report_omission(
    tmp_path: Path, monkeypatch, bound: str, value: int
) -> None:
    for index in range(3):
        (tmp_path / f"{index}.csv").write_text("a\n1\n")
    monkeypatch.setattr(materials, bound, value)
    profile = profile_materials(tmp_path)
    assert len(profile["tables"]) <= 1
    assert any(issue["code"] == "discovery_limit" for issue in profile["issues"])


def test_depth_limit_and_size_limit_do_not_imply_complete_profile(
    tmp_path: Path, monkeypatch
) -> None:
    folder = tmp_path / "nested"
    folder.mkdir()
    (folder / "a.csv").write_text("a\n1\n")
    (tmp_path / "large.csv").write_text("a\n" + "1\n" * 100)
    monkeypatch.setattr(materials, "MAX_DEPTH", 0)
    monkeypatch.setattr(materials, "MAX_FILE_BYTES", 10)
    profile = profile_materials(tmp_path)
    assert profile["tables"][0]["row_count"] == 100
    assert profile["tables"][0]["profile_scope"] == "bounded-preview"
    assert {issue["code"] for issue in profile["issues"]} == {"depth_limit"}


def test_total_read_limit_applies_to_explicit_paths_too(tmp_path: Path, monkeypatch) -> None:
    paths = [Path("first.csv"), Path("second.csv")]
    for path in paths:
        (tmp_path / path).write_text("a\n1\n")
    monkeypatch.setattr(materials, "MAX_TOTAL_BYTES", 6)
    profile = profile_materials(tmp_path, paths=paths)
    assert len(profile["tables"]) == 2
    assert profile["tables"][1]["profile_scope"] == "bounded-preview"
    assert profile["issues"] == []


def test_empty_table_has_no_fabricated_data_locator_or_extrema(tmp_path: Path) -> None:
    (tmp_path / "empty.csv").write_text("value [m]\n")
    table = profile_materials(tmp_path)["tables"][0]
    assert table["row_count"] == 0
    assert table["source"]["data_locator"] is None
    assert table["columns"][0]["type"] == "empty"
    assert "minimum" not in table["columns"][0]


def test_source_mutation_between_adapter_reads_is_localized(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "changing.csv"
    source.write_text("value\n1\n")
    extract = CSVAdapter.extract

    def mutate_after_extract(self, request):
        records = extract(self, request)
        source.write_text("value\n2\n")
        return records

    monkeypatch.setattr(CSVAdapter, "extract", mutate_after_extract)
    profile = profile_materials(tmp_path)
    assert profile["tables"] == []
    assert "changed" in profile["issues"][0]["message"]


def test_invalid_root_is_an_issue(tmp_path: Path) -> None:
    profile = profile_materials(tmp_path / "missing")
    assert profile["tables"] == []
    assert profile["issues"][0]["code"] == "invalid_root"
