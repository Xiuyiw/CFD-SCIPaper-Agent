"""Large source locators are readable views, never altered scientific records."""

import copy
import shutil

import numpy as np
import pytest

from cfdpaper.publication.manuscript import (
    _writing_resolution,
    prepare_manuscript,
    prepare_writing_context,
)
from tests.publication.test_manuscript import bound_fixture, read, write


def pointer(root, details):
    value = read(root / details["path"])
    for part in details["json_pointer"].strip("/").split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def large_package(tmp_path, suffix):
    source, drafts = bound_fixture(tmp_path)
    local = tmp_path / "response"
    path = local / "input.json"
    section = read(path)
    cases = ["a", "b"] * 80
    if suffix == "npz":
        np.savez(local / "sources/large.npz", case=cases, value=np.arange(160))
    else:
        (local / "sources/large.csv").write_text(
            "case,value\n" + "".join(f"{case},{i}\n" for i, case in enumerate(cases)),
            encoding="utf-8",
        )
    section["table_calculations"][0].update(
        source=f"sources/large.{suffix}", units={"value": "kg/s"}
    )
    (local / "sources/comparison.txt").write_text("Synthetic case difference.", encoding="utf-8")
    section["result_comparisons"] = [
        {
            "id": "contrast",
            "reference": {"calculation_id": "mean", "group": "a", "field": "mean"},
            "comparison": {"calculation_id": "mean", "group": "b", "field": "mean"},
            "domain": "Synthetic rows",
            "definition_source": "sources/comparison.txt:L1",
            "comparison_scope": "Only supplied synthetic cases",
            "status": "supported",
        }
    ]
    section["evidence"].append(
        {
            "id": "delta",
            "kind": "metric",
            "text": "Synthetic difference, not a scientific finding",
            "source": "sources/comparison.txt",
            "result_ref": {"calculation_id": "contrast", "group": "all", "field": "difference"},
        }
    )
    write(path, section)
    manifest = read(source)
    next(s for s in manifest["sections"] if s["section_id"] == "summary")["evidence_bindings"][
        "aliased-delta"
    ] = "response/delta"
    write(source, manifest)
    return prepare_manuscript(source, tmp_path / "package"), drafts


@pytest.mark.parametrize(
    "suffix,key,index_base", [("npz", "array_indices", 0), ("csv", "csv_records", 1)]
)
def test_large_owner_alias_and_comparison_locators_are_exact_and_portable(
    tmp_path, suffix, key, index_base
):
    package, drafts = large_package(tmp_path, suffix)
    original_report = (package / "sections/response/table-results.json").read_bytes()
    original_drafts = {sid: read(tmp_path / path) for sid, path in read(drafts).items()}
    output = prepare_writing_context(package, "summary", tmp_path / "context", drafts_path=drafts)
    payload = read(output / "context.json")
    for sid, eid in (("response", "metric"), ("summary", "shared")):
        resolved = payload["sections"][sid]["evidence"][eid]["resolved"]
        assert resolved["raw_value"] == 79
        assert key not in resolved
        summary = resolved[key + "_summary"]
        assert summary["count"] == 80
        assert summary["index_base"] == index_base
        assert summary["details"] == {
            "path": "sections/response/table-results.json",
            "json_pointer": f"/0/groups/0/{key}",
        }
        assert pointer(output, summary["details"]) == list(
            range(0 if suffix == "npz" else 2, 160 if suffix == "npz" else 162, 2)
        )
    for sid, eid in (("response", "delta"), ("summary", "aliased-delta")):
        delta = payload["sections"][sid]["evidence"][eid]["resolved"]
        assert delta["raw_value"] == 1
        for index, supporting in enumerate(delta["supporting_results"]):
            summary = supporting[key + "_summary"]
            assert summary["count"] == len(pointer(output, summary["details"])) == 80
            assert summary["details"]["json_pointer"] == f"/0/groups/{index}/{key}"
    assert (package / "sections/response/table-results.json").read_bytes() == original_report
    assert (output / "sections/response/table-results.json").read_bytes() == original_report
    for sid in ("summary", "response"):
        assert payload["sections"][sid]["draft"] == original_drafts[sid]
    assert "exact JSON Pointer" in (output / "TASK.md").read_text(encoding="utf-8")
    relocated = tmp_path / "relocated"
    shutil.move(output, relocated)
    assert len(pointer(relocated, summary["details"])) == 80


def test_small_locators_and_unrelated_scientific_arrays_are_not_projected(tmp_path):
    source, drafts = bound_fixture(tmp_path)
    package = prepare_manuscript(source, tmp_path / "package")
    output = prepare_writing_context(package, "summary", tmp_path / "context", drafts_path=drafts)
    value = read(output / "context.json")["sections"]["summary"]["evidence"]["shared"]["resolved"]
    assert value["csv_records"] == [2, 3]
    assert "csv_records_summary" not in value
    scientific = {"values": list(range(200)), "result": {"temperatures": list(range(200))}}
    assert _writing_resolution(scientific, [], "table-results.json") == scientific


def test_regional_single_record_is_preserved_and_share_uses_full_group(tmp_path):
    from cfdpaper.publication.table_evidence import calculate_table, resolve_table_result

    path = tmp_path / "regions.csv"
    path.write_text("A,Q\n" + "1,2\n" * 80, encoding="utf-8")
    report = {
        "id": "heat",
        "source": "sources/regions.csv",
        "operation": "partition",
        "units": {"area": "m^2", "rate": "W"},
        **calculate_table(path, operation="partition", columns={"area": "A", "rate": "Q"}),
    }
    before = copy.deepcopy(report)
    for field in ("regional_flux", "shares"):
        resolved = resolve_table_result(
            [report], calculation_id="heat", group="all", field=field, source_record=12
        )
        original = copy.deepcopy(resolved)
        view = _writing_resolution(resolved, [report], "table-results.json")
        assert view["source_record"] == 12
        if field == "regional_flux":
            assert view == resolved
            assert view["csv_records"] == [12]
        else:
            assert (
                view["csv_records_summary"]["details"]["json_pointer"] == "/0/groups/0/csv_records"
            )
            assert view["csv_records_summary"]["count"] == 80
            assert view["raw_value"] == resolved["raw_value"]
        assert resolved == original
    assert report == before


def test_projection_never_points_a_subset_at_a_larger_group():
    values = list(range(100))
    result = {
        "calculation_id": "mean",
        "source": "data.npz",
        "group": "a",
        "array_indices": values[:80],
    }
    reports = [
        {"id": "mean", "source": "data.npz", "groups": [{"group": "a", "array_indices": values}]}
    ]
    assert _writing_resolution(result, reports, "table-results.json") == result
