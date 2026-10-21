"""Exact JSON report projection into portable, bindable numeric tables."""

from __future__ import annotations

import csv
import json
import shutil
from copy import deepcopy

import pytest

from cfdpaper.publication.parameter_evidence import _pointer
from cfdpaper.publication.table_evidence import calculate_table
from cfdpaper.report_sources import project_reports


def _report(tmp_path, name="case.json", data=None):
    path = tmp_path / "raw" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if data is None:
        data = {"pressure": {"reference": 2400, "comparison": 900}, "power": 1500}
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _paired(**changes):
    return {
        "id": "pressure-change",
        "label": "Static pressure change",
        "unit": "Pa",
        "output_unit": "kPa",
        "domain": "inlet and outlet sections",
        "reference": "/pressure/reference",
        "comparison": "/pressure/comparison",
        **changes,
    }


def _rows(output):
    with (output / "sources/report-values.csv").open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_projects_paired_endpoints_and_scalar_with_exact_source_locators(tmp_path):
    original = _report(tmp_path)
    original_bytes = original.read_bytes()
    cases = [{"id": "Case-A", "source": "raw/case.json"}]
    quantities = [
        _paired(),
        {"id": "power", "label": "Power", "unit": "W", "domain": "whole", "pointer": "/power"},
    ]
    output = tmp_path / "projected"
    result = project_reports(tmp_path, cases, quantities, output)

    assert result == {
        "source": "sources/report-values.csv",
        "source_files": ["sources/report-values.csv", "sources/records/Case-A.json"],
        "cases": ["Case-A"],
        "retained_cases": [{"id": "Case-A", "source": "sources/records/Case-A.json"}],
        "quantities": quantities,
        "row_count": 3,
    }
    assert original.read_bytes() == original_bytes
    assert (output / "sources/records/Case-A.json").read_bytes() == original_bytes
    assert _rows(output) == [
        {
            "case_id": "Case-A",
            "quantity": "pressure-change",
            "member": "reference",
            "value": "2.4",
            "unit": "kPa",
            "source": "sources/records/Case-A.json",
            "pointer": "/pressure/reference",
        },
        {
            "case_id": "Case-A",
            "quantity": "pressure-change",
            "member": "comparison",
            "value": "0.9",
            "unit": "kPa",
            "source": "sources/records/Case-A.json",
            "pointer": "/pressure/comparison",
        },
        {
            "case_id": "Case-A",
            "quantity": "power",
            "member": "value",
            "value": "1500",
            "unit": "W",
            "source": "sources/records/Case-A.json",
            "pointer": "/power",
        },
    ]
    paired = calculate_table(
        output / result["source"],
        operation="paired_change",
        columns={"value": "value"},
        group_by="case_id",
        pair_by="member",
        reference="reference",
        comparison="comparison",
        units={"value": "kPa"},
        row_filters={"quantity": "pressure-change"},
        unit_column="unit",
    )
    assert paired["groups"][0]["group"] == "Case-A"
    assert paired["groups"][0]["result"]["difference"] == pytest.approx(-1.5)


def test_common_pointer_escapes_arrays_and_inference_words_are_literal_data(tmp_path):
    _report(tmp_path, "a.json", {".inference": {"a/b~": [21, 22]}})
    _report(tmp_path, "b.json", {".inference": {"a/b~": [31, 32]}})
    pointer = "/.inference/a~1b~0/1"
    quantity = {
        "id": "probe",
        "label": "Probe value",
        "unit": "custom-unit",
        "domain": "declared probe",
        "pointer": pointer,
    }
    output = tmp_path / "projected"
    result = project_reports(
        tmp_path,
        [{"id": "A", "source": "raw/a.json"}, {"id": "B", "source": "raw/b.json"}],
        [quantity],
        output,
    )
    assert [row["value"] for row in _rows(output)] == ["22", "32"]
    assert result["row_count"] == 2

    moved = tmp_path / "relocated"
    shutil.copytree(output, moved)
    shutil.rmtree(output)
    shutil.rmtree(tmp_path / "raw")
    for row in _rows(moved):
        document = json.loads((moved / row["source"]).read_text(encoding="utf-8"))
        assert str(_pointer(document, row["pointer"])) == row["value"]


def test_preserves_multiple_sources_dimensionless_metadata_and_reprojection_after_move(tmp_path):
    originals = [
        _report(tmp_path, "a.json"),
        _report(tmp_path, "b.json"),
        _report(tmp_path, "a-setup.json", {"flow": {"I": 1.25}}),
        _report(tmp_path, "b-setup.json", {"flow": {"I": 1.75}}),
        _report(tmp_path, "reference.json", [{"I": 1.1}, {"I": 1.6}]),
    ]
    original_bytes = {path: path.read_bytes() for path in originals}
    cases = [
        {
            "id": case_id,
            "source": f"raw/{case_id.lower()}.json",
            "sources": {
                "setup": f"raw/{case_id.lower()}-setup.json",
                "reference": "raw/reference.json",
            },
            "metadata": {"kind": "steady"},
        }
        for case_id in ("A", "B")
    ]
    quantities = [
        _paired(),
        {
            "id": "I",
            "label": "Dimensionless inlet index",
            "unit": "",
            "output_unit": "",
            "domain": "inlet setup",
            "pointer": "/flow/I",
            "source_key": "setup",
            "table": False,
            "metadata": {"note": ["declared setting"]},
        },
        {
            "id": "reference-I",
            "label": "Reference inlet index",
            "unit": "1",
            "domain": "reference cases",
            "pointer": {"A": "/0/I", "B": "/1/I"},
            "source_key": "reference",
        },
    ]
    input_cases, input_quantities = deepcopy(cases), deepcopy(quantities)
    output = tmp_path / "projected"
    result = project_reports(tmp_path, cases, quantities, output)

    assert cases == input_cases
    assert quantities == input_quantities
    assert result["retained_cases"] == [
        {
            **case,
            "source": f"sources/records/{case['id']}.json",
            "sources": {key: f"sources/records/{case['id']}/{key}.json" for key in case["sources"]},
        }
        for case in cases
    ]
    assert result["quantities"] == quantities
    result["quantities"][1]["metadata"]["note"].append("copy only")
    result["retained_cases"][0]["metadata"]["kind"] = "copy only"
    assert quantities == input_quantities
    assert cases == input_cases
    for path, raw in original_bytes.items():
        assert path.read_bytes() == raw
    for case, retained in zip(cases, result["retained_cases"], strict=True):
        assert (output / retained["source"]).read_bytes() == original_bytes[
            tmp_path / case["source"]
        ]
        for key, source in case["sources"].items():
            assert (output / retained["sources"][key]).read_bytes() == original_bytes[
                tmp_path / source
            ]
    rows = _rows(output)
    assert len(rows) == 8
    for case_id, index in (("A", "1.25"), ("B", "1.75")):
        row = next(row for row in rows if row["case_id"] == case_id and row["quantity"] == "I")
        assert (row["value"], row["unit"], row["source"], row["pointer"]) == (
            index,
            "",
            f"sources/records/{case_id}/setup.json",
            "/flow/I",
        )
    assert [row["pointer"] for row in rows if row["quantity"] == "reference-I"] == [
        "/0/I",
        "/1/I",
    ]
    assert set(result["source_files"]) == {result["source"]} | {row["source"] for row in rows}

    moved = tmp_path / "relocated"
    shutil.move(str(output), moved)
    shutil.rmtree(tmp_path / "raw")
    repeated = tmp_path / "reprojected"
    project_reports(moved, result["retained_cases"], result["quantities"], repeated)
    assert _rows(repeated) == rows


def test_case_specific_paired_pointers_select_exact_array_endpoints(tmp_path):
    _report(tmp_path, data=[{"p": [3000, 1000]}, {"p": [2500, 750]}])
    output = tmp_path / "projected"
    project_reports(
        tmp_path,
        [{"id": "A", "source": "raw/case.json"}, {"id": "B", "source": "raw/case.json"}],
        [
            _paired(
                reference={"A": "/0/p/0", "B": "/1/p/0"},
                comparison={"A": "/0/p/1", "B": "/1/p/1"},
            )
        ],
        output,
    )
    assert [row["value"] for row in _rows(output)] == ["3.0", "1.0", "2.5", "0.75"]
    assert [row["pointer"] for row in _rows(output)] == [
        "/0/p/0",
        "/0/p/1",
        "/1/p/0",
        "/1/p/1",
    ]


@pytest.mark.parametrize("member", ["pointer", "reference", "comparison"])
@pytest.mark.parametrize("selection", [{"A": "/power"}, {"A": "/power", "B": 3}, 3])
def test_rejects_missing_case_pointer_or_nonstring_pointer_precisely(tmp_path, member, selection):
    _report(tmp_path)
    declaration = _paired(**{member: selection})
    if member == "pointer":
        declaration.pop("reference")
        declaration.pop("comparison")
    output = tmp_path / "projected"
    with pytest.raises(ValueError) as error:
        project_reports(
            tmp_path,
            [{"id": "A", "source": "raw/case.json"}, {"id": "B", "source": "raw/case.json"}],
            [declaration],
            output,
        )
    message = str(error.value)
    case_id = "A" if selection == 3 else "B"
    assert all(part in message for part in (case_id, "raw/case.json", "pressure-change", member))
    assert not output.exists()


@pytest.mark.parametrize(
    ("sources", "source_key", "message"),
    [
        ({}, "setup", "setup"),
        ({"setup": "raw/missing.json"}, "setup", "raw/missing.json"),
        ({"../setup": "raw/case.json"}, "../setup", "portable"),
        ({"setup": "raw/case.json"}, "../setup", "portable"),
        ({"setup": "raw/case.json", "SETUP": "raw/case.json"}, "setup", "Duplicate"),
        ([], "setup", "mapping"),
    ],
)
def test_rejects_undeclared_or_invalid_extra_source(tmp_path, sources, source_key, message):
    _report(tmp_path)
    output = tmp_path / "projected"
    with pytest.raises(ValueError, match=message):
        project_reports(
            tmp_path,
            [{"id": "A", "source": "raw/case.json", "sources": sources}],
            [_paired(source_key=source_key)],
            output,
        )
    assert not output.exists()


@pytest.mark.parametrize(
    ("value", "unit", "target", "kind", "expected"),
    [
        (2500, "W", "kW", "ordinary", 2.5),
        (25, "degC", "K", "absolute-temperature", 298.15),
        (298.15, "K", "degC", "absolute-temperature", 25),
        (12, "K", "K", "temperature-difference", 12),
        (1.2, "", "", "ordinary", 1.2),
        (1.2, "", "%", "ordinary", 120),
        (120, "%", "", "ordinary", 1.2),
    ],
)
def test_uses_registered_unit_conversion_across_domains(
    tmp_path, value, unit, target, kind, expected
):
    _report(tmp_path, data={"value": value})
    declaration = {
        "id": "q",
        "label": "Declared quantity",
        "unit": unit,
        "output_unit": target,
        "quantity_kind": kind,
        "domain": "declared domain",
        "pointer": "/value",
    }
    output = tmp_path / "projected"
    project_reports(tmp_path, [{"id": "A", "source": "raw/case.json"}], [declaration], output)
    row = _rows(output)[0]
    assert float(row["value"]) == pytest.approx(expected)
    assert row["unit"] == target


@pytest.mark.parametrize("bad", [True, False, None, "", "12", [], {}, float("nan"), float("inf")])
def test_rejects_non_native_or_nonfinite_numbers_without_partial_outputs(tmp_path, bad):
    _report(tmp_path, "a.json")
    _report(tmp_path, "b.json", {"pressure": {"reference": 10, "comparison": bad}})
    output = tmp_path / "projected"
    with pytest.raises(ValueError) as error:
        project_reports(
            tmp_path,
            [{"id": "A", "source": "raw/a.json"}, {"id": "B", "source": "raw/b.json"}],
            [_paired()],
            output,
        )
    message = str(error.value)
    assert all(part in message for part in ("B", "raw/b.json", "/pressure/comparison"))
    assert not output.exists()
    assert not list(tmp_path.glob(".section-*"))


def test_missing_pointer_does_not_fill_value_or_leave_output(tmp_path):
    _report(tmp_path, data={"pressure": {"reference": 10}})
    output = tmp_path / "projected"
    with pytest.raises(ValueError, match="/pressure/comparison"):
        project_reports(tmp_path, [{"id": "A", "source": "raw/case.json"}], [_paired()], output)
    assert not output.exists()


@pytest.mark.parametrize(
    "pointer", ["$.pressure.reference", "/pressure/*", "/pressure/~2", "/a/01"]
)
def test_rejects_dsl_wildcards_invalid_escapes_and_array_indices(tmp_path, pointer):
    _report(tmp_path, data={"pressure": {"reference": 10}, "a": [1, 2]})
    output = tmp_path / "projected"
    with pytest.raises(ValueError):
        project_reports(
            tmp_path,
            [{"id": "A", "source": "raw/case.json"}],
            [_paired(reference=pointer)],
            output,
        )
    assert not output.exists()


@pytest.mark.parametrize("field", ["cases", "quantities"])
def test_rejects_case_insensitive_duplicate_ids(tmp_path, field):
    _report(tmp_path)
    cases = [{"id": "Case-A", "source": "raw/case.json"}]
    quantities = [_paired()]
    if field == "cases":
        cases.append({"id": "case-a", "source": "raw/case.json"})
    else:
        quantities.append(_paired(id="PRESSURE-CHANGE"))
    output = tmp_path / "projected"
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        project_reports(tmp_path, cases, quantities, output)
    assert not output.exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"unit": None},
        {"unit": ""},
        {"unit": " "},
        {"output_unit": None},
        {"output_unit": " "},
        {"unit": 1},
        {"output_unit": 1},
        {"unit": "unregistered", "output_unit": "kPa"},
        {"unit": "Pa", "output_unit": "W"},
        {"quantity_kind": "guessed"},
        {"quantity_kind": "temperature-difference", "unit": "degC", "output_unit": "K"},
    ],
)
def test_does_not_guess_missing_units_or_temperature_semantics(tmp_path, changes):
    _report(tmp_path)
    output = tmp_path / "projected"
    with pytest.raises(ValueError):
        project_reports(
            tmp_path,
            [{"id": "A", "source": "raw/case.json"}],
            [_paired(**changes)],
            output,
        )
    assert not output.exists()


def test_requires_unit_to_be_declared_even_for_dimensionless_values(tmp_path):
    _report(tmp_path)
    declaration = _paired()
    del declaration["unit"]
    output = tmp_path / "projected"
    with pytest.raises(ValueError, match="unit"):
        project_reports(tmp_path, [{"id": "A", "source": "raw/case.json"}], [declaration], output)
    assert not output.exists()


def test_fresh_output_is_not_overwritten(tmp_path):
    _report(tmp_path)
    output = tmp_path / "projected"
    output.mkdir()
    marker = output / "author.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        project_reports(tmp_path, [{"id": "A", "source": "raw/case.json"}], [_paired()], output)
    assert marker.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("source", ["../outside.json", "/outside.json", "raw/missing.json"])
def test_requires_existing_relative_source_within_root(tmp_path, source):
    output = tmp_path / "projected"
    with pytest.raises(ValueError):
        project_reports(tmp_path, [{"id": "A", "source": source}], [_paired()], output)
    assert not output.exists()
