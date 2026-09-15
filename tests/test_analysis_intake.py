"""Complete computable sources survive bounded previews and package relocation."""

import json
import shutil

import pytest

from cfdpaper import materials
from cfdpaper.adapters import CSVAdapter
from cfdpaper.analysis_suggestions import prepare_analysis


def test_large_csv_is_streamed_and_packaged_without_full_extraction(tmp_path, monkeypatch):
    root = tmp_path / "input"
    root.mkdir()
    source = root / "facets.csv"
    # Match the observed failure scale while keeping all records synthetic.
    with source.open("w", encoding="utf-8", newline="") as stream:
        stream.write("member,value [K],description\n")
        for index in range(52900):
            stream.write(f"{index},{300 + index / 1000},{'x' * 170}\n")
    assert source.stat().st_size > materials.MAX_FILE_BYTES

    def no_extract(*args, **kwargs):
        pytest.fail("Large CSV preview must not materialize all extracted records")

    monkeypatch.setattr(CSVAdapter, "extract", no_extract)
    prepared = tmp_path / "prepared"
    prepare_analysis(root, prepared)
    payload = json.loads((prepared / "materials.json").read_text())
    table = payload["tables"][0]
    assert table["row_count"] == 52900
    assert table["profile_scope"] == "bounded-preview"
    assert len(table["preview_rows"]) <= materials.MAX_PREVIEW_ROWS
    assert (
        sum(len(value) for row in table["preview_rows"] for value in row["values"])
        <= materials.MAX_EXCERPT_CHARS
    )
    assert table["preview_truncated"] is True
    assert table["columns"][1]["unit"] == "K"
    assert "maximum" not in table["columns"][1]
    assert "unique_count" not in table["columns"][0]
    assert table["source"]["data_locator"] == "row:2-row:52901"
    moved = tmp_path / "relocated"
    shutil.move(prepared, moved)
    expected_hash = table["source"]["source_hash"]
    shutil.rmtree(root)
    copied = moved / table["package_path"]
    assert copied.is_file()
    assert materials.source_sha256(copied) == expected_hash
    assert CSVAdapter().inventory(copied).row_count == 52900
    assert payload["source_files"] == ["sources/facets.csv"]


def test_npz_metadata_and_raw_bytes_survive_relocation_without_loading_arrays(
    tmp_path, monkeypatch
):
    np = pytest.importorskip("numpy")
    root = tmp_path / "input"
    root.mkdir()
    source = root / "field.npz"
    np.savez_compressed(
        source,
        values=np.array([301.0, 302.0]),
        coordinates=np.zeros((2, 3)),
        opaque=np.array([{"uninterpreted": True}], dtype=object),
    )
    before = source.read_bytes()

    def no_load(*args, **kwargs):
        pytest.fail("Intake must inspect headers only, never deserialize NPZ payloads")

    monkeypatch.setattr(np, "load", no_load)
    prepared = tmp_path / "prepared"
    prepare_analysis(root, prepared)
    payload = json.loads((prepared / "materials.json").read_text())
    native = payload["arrays"][0]
    assert native["arrays"] == [
        {"key": "values", "shape": [2], "dtype": "float64", "object_dtype": False},
        {"key": "coordinates", "shape": [2, 3], "dtype": "float64", "object_dtype": False},
        {"key": "opaque", "shape": [1], "dtype": "object", "object_dtype": True},
    ]
    assert "unit" not in native
    moved = tmp_path / "relocated"
    shutil.move(prepared, moved)
    shutil.rmtree(root)
    assert (moved / native["package_path"]).read_bytes() == before
    assert payload["source_files"] == ["sources/field.npz"]


def test_unreadable_npz_metadata_retains_opaque_source(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    (root / "opaque.npz").write_bytes(b"not a valid archive")
    prepared = tmp_path / "prepared"
    prepare_analysis(root, prepared)
    payload = json.loads((prepared / "materials.json").read_text())
    assert payload["arrays"][0]["metadata_issue"]
    assert payload["source_files"] == ["sources/opaque.npz"]
    assert (prepared / "sources/opaque.npz").read_bytes() == b"not a valid archive"


def test_document_budget_is_not_removed(tmp_path, monkeypatch):
    (tmp_path / "large.md").write_text("a" * 20)
    monkeypatch.setattr(materials, "MAX_FILE_BYTES", 10)
    payload = materials.profile_materials(tmp_path)
    assert payload["documents"] == []
    assert payload["issues"][0]["code"] == "size_limit"
