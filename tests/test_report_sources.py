"""Exact JSON report projection into portable, bindable numeric tables."""

from __future__ import annotations

import csv
import json
import shutil

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


@pytest.mark.parametrize(
    ("value", "unit", "target", "kind", "expected"),
    [
        (2500, "W", "kW", "ordinary", 2.5),
        (25, "degC", "K", "absolute-temperature", 298.15),
        (298.15, "K", "degC", "absolute-temperature", 25),
        (12, "K", "K", "temperature-difference", 12),
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
