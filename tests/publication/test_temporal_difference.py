"""Saved-record differences keep both original values and their source identity."""

import copy

import numpy as np
import pytest

from cfdpaper.publication.table_evidence import (
    calculate_declared_table,
    calculate_table,
    resolve_table_result,
)
from cfdpaper.publication.temporal import TEMPORAL_FIELDS


def _report(tmp_path, samples=((0, 10, 12), (1, 20, 26), (3, 30, 34)), **options):
    path = tmp_path / "history.csv"
    path.write_text(
        "t,ref,comp\n" + "\n".join(f"{t},{ref},{comp}" for t, ref, comp in samples),
        encoding="utf-8",
    )
    declaration = {
        "id": "difference",
        "source": "sources/history.csv",
        "operation": "temporal_difference",
        "columns": {"time": "t", "reference": "ref", "comparison": "comp"},
        "units": {"time": "s", "reference": "W", "comparison": "W"},
        **options,
    }
    before = copy.deepcopy(declaration)
    result = calculate_declared_table(path, declaration)
    assert declaration == before
    return {**declaration, **result}


def _resolve(report, field, **options):
    return resolve_table_result(
        [report], calculation_id=report["id"], group="all", field=field, **options
    )


def test_same_record_difference_reuses_every_temporal_field(tmp_path):
    report = _report(tmp_path, threshold=5)
    group = report["groups"][0]
    assert report["rows_read"] == 3
    assert group["result"] == {
        "sample_count": 3,
        "duration": 3,
        "start_value": 2,
        "end_value": 4,
        "change": 2,
        "minimum": 2,
        "maximum": 6,
        "peak_time": 1,
        "time_mean": 14 / 3,
        "integral": 14,
        "first_crossing_time": 1,
    }
    assert set(group["result"]) == TEMPORAL_FIELDS
    assert group["difference_direction"] == "comparison-reference"
    assert group["difference_unit"] == "W"
    assert group["difference_quantity_kind"] == "ordinary"
    assert group["csv_records"] == [2, 3, 4]
    assert group["samples"] == [
        {"csv_record": 2, "time": 0, "reference": 10, "comparison": 12, "value": 2},
        {"csv_record": 3, "time": 1, "reference": 20, "comparison": 26, "value": 6},
        {"csv_record": 4, "time": 3, "reference": 30, "comparison": 34, "value": 4},
    ]
    assert group["sampling"] == "saved-samples"
    assert group["integration_method"] == "trapezoidal-nonuniform"
    assert group["crossing_time_kind"] == "first-matching-saved-sample"
    assert _resolve(report, "maximum")["unit"] == "W"
    assert _resolve(report, "integral")["unit"] == "J"
    assert _resolve(report, "first_crossing_time")["unit"] == "s"
    assert _resolve(report, "sample_count")["unit"] == ""
    assert _resolve(report, "time_mean")["csv_records"] == [2, 3, 4]


def test_reversed_columns_reverse_difference_without_reordering(tmp_path):
    report = _report(tmp_path, columns={"time": "t", "reference": "comp", "comparison": "ref"})
    group = report["groups"][0]
    assert group["result"]["integral"] == -14
    assert [sample["value"] for sample in group["samples"]] == [-2, -6, -4]
    assert group["samples"][1]["reference"] == 26
    assert group["samples"][1]["comparison"] == 20


@pytest.mark.parametrize("window", [[1, 3], (1, 3)])
def test_window_selects_original_samples_and_ignores_outside_missing_value(tmp_path, window):
    report = _report(
        tmp_path, samples=((0, "", 12), (1, 20, 26), (3, 30, 34), (4, 30, "")), time_window=window
    )
    group = report["groups"][0]
    assert report["rows_read"] == 4
    assert group["csv_records"] == [3, 4]
    assert [sample["csv_record"] for sample in group["samples"]] == [3, 4]
    assert group["time_window"] == [1, 3]
    assert group["window_selection"] == "exact-sampled-endpoints"
    assert group["result"]["integral"] == 10


@pytest.mark.parametrize(
    "samples",
    [((0, 1, 2), (1, "", 5), (3, 2, 3)), ((0, 1, 2), (1, 4, ""), (3, 2, 3))],
)
def test_missing_endpoint_remains_missing_and_keeps_original_other_endpoint(tmp_path, samples):
    report = _report(tmp_path, samples=samples)
    group = report["groups"][0]
    assert group["status"] == "missing-values"
    assert group["result"] is None
    assert group["samples"][1]["value"] is None
    assert (group["samples"][1]["reference"], group["samples"][1]["comparison"]) in {
        (None, 5),
        (4, None),
    }
    for field in ("integral", "maximum", "change"):
        with pytest.raises(ValueError, match="unavailable"):
            _resolve(report, field)


@pytest.mark.parametrize("unit,offset", [("degC", 0), ("°C", 0), ("C", 0), ("K", 273.15)])
def test_absolute_temperature_difference_is_kelvin_without_origin_conversion(
    tmp_path, unit, offset
):
    report = _report(
        tmp_path,
        samples=[(0, 20 + offset, 22 + offset), (1, 30 + offset, 36 + offset)],
        units={"time": "s", "reference": unit, "comparison": unit},
        quantity_kind="absolute-temperature",
        threshold=5,
    )
    group = report["groups"][0]
    assert group["difference_unit"] == "K"
    assert group["difference_quantity_kind"] == "temperature-difference"
    assert group["samples"][0]["reference"] == 20 + offset
    assert group["samples"][1]["value"] == 6
    for field in ("start_value", "end_value", "change", "minimum", "maximum", "time_mean"):
        assert _resolve(report, field)["unit"] == "K"
    assert _resolve(report, "integral")["unit"] == "K·s"
    assert _resolve(report, "first_crossing_time")["raw_value"] == 1


def test_temperature_difference_inputs_are_both_kelvin(tmp_path):
    report = _report(
        tmp_path,
        units={"time": "s", "reference": "K", "comparison": "K"},
        quantity_kind="temperature-difference",
    )
    assert _resolve(report, "time_mean")["unit"] == "K"
    assert _resolve(report, "time_mean")["raw_value"] == 14 / 3


@pytest.mark.parametrize(
    "unit,integral_unit", [("kW", "kJ"), ("MW", "MJ"), ("kg/s", "kg"), ("Pa", "Pa·s")]
)
def test_ordinary_difference_retains_declared_scale(tmp_path, unit, integral_unit):
    report = _report(tmp_path, units={"time": "s", "reference": unit, "comparison": unit})
    assert _resolve(report, "integral")["unit"] == integral_unit
    assert _resolve(report, "integral")["raw_value"] == 14
    assert _resolve(report, "change")["unit"] == unit


@pytest.mark.parametrize(
    "direction,threshold,expected",
    [
        ("at-or-above", 3, 1),
        ("at-or-above", 2, 0),
        ("at-or-above", 7, None),
        ("at-or-below", 4, 0),
        ("at-or-below", 1, None),
    ],
)
def test_crossing_is_first_selected_saved_sample(tmp_path, direction, threshold, expected):
    report = _report(tmp_path, threshold=threshold, crossing_direction=direction)
    assert report["groups"][0]["result"]["first_crossing_time"] == expected
    if expected is None:
        with pytest.raises(ValueError, match="missing"):
            _resolve(report, "first_crossing_time")


def test_peak_ties_and_threshold_are_window_local(tmp_path):
    report = _report(
        tmp_path,
        samples=((0, 1, 8), (1, 2, 8), (3, 3, 9)),
        time_window=[1, 3],
        threshold=7,
    )
    assert report["groups"][0]["result"]["peak_time"] == 1
    assert report["groups"][0]["result"]["first_crossing_time"] is None


def test_interleaved_groups_and_exact_filter_keep_original_record_numbers(tmp_path):
    path = tmp_path / "groups.csv"
    path.write_text(
        "case,t,r,c\nx,0,bad,bad\na,0,10,12\nb,0,10,13\na,1,20,26\nb,2,30,35\na,3,30,34\n",
        encoding="utf-8",
    )
    options = {
        "operation": "temporal_difference",
        "columns": {"time": "t", "reference": "r", "comparison": "c"},
        "units": {"time": "s", "reference": "W", "comparison": "W"},
        "group_by": "case",
    }
    a = calculate_table(path, row_filters={"case": "a"}, **options)
    assert a["groups"][0]["csv_records"] == [3, 5, 7]
    assert [sample["csv_record"] for sample in a["groups"][0]["samples"]] == [3, 5, 7]
    assert a["groups"][0]["result"]["integral"] == 14
    b = calculate_table(path, row_filters={"case": "b"}, **options)
    assert b["groups"][0]["result"]["integral"] == 8
    path.write_text(
        "case,t,r,c\na,0,10,12\nb,0,10,13\na,1,20,26\nb,2,30,35\na,3,30,34\n",
        encoding="utf-8",
    )
    groups = calculate_table(path, **options)["groups"]
    assert [group["csv_records"] for group in groups] == [[2, 4, 6], [3, 5]]
    assert [group["result"]["integral"] for group in groups] == [14, 8]


def test_npz_window_preserves_array_indices_and_both_values(tmp_path):
    path = tmp_path / "history.npz"
    np.savez(path, t=[0, 1, 3, 4], ref=[10, 20, 30, 40], comp=[12, 26, 34, 41])
    declaration = {
        "id": "npz",
        "source": "sources/history.npz",
        "operation": "temporal_difference",
        "columns": {"time": "t", "reference": "ref", "comparison": "comp"},
        "units": {"time": "s", "reference": "W", "comparison": "W"},
        "time_window": [1, 3],
    }
    report = {**declaration, **calculate_declared_table(path, declaration)}
    assert report["groups"][0]["samples"] == [
        {"array_index": 1, "time": 1, "reference": 20, "comparison": 26, "value": 6},
        {"array_index": 2, "time": 3, "reference": 30, "comparison": 34, "value": 4},
    ]
    assert _resolve(report, "integral")["array_indices"] == [1, 2]
    assert _resolve(report, "integral")["raw_value"] == 10


@pytest.mark.parametrize("times", [(0,), (0, 0, 3), (0, 3, 1), (0, "", 3), (0, "nan", 3)])
def test_invalid_time_samples_are_not_sorted_dropped_or_filled(tmp_path, times):
    with pytest.raises(ValueError):
        _report(tmp_path, samples=[(t, 1, 2) for t in times])


@pytest.mark.parametrize("window", [[0, 2], [-1, 3], [0, 4], [1, 1], [3, 0], [0]])
def test_window_requires_exact_saved_endpoints(tmp_path, window):
    with pytest.raises(ValueError):
        _report(tmp_path, time_window=window)


@pytest.mark.parametrize(
    "options",
    [
        {"units": None},
        {"units": {"time": "s", "value": "W"}},
        {"units": {"time": "ms", "reference": "W", "comparison": "W"}},
        {"units": {"time": "s", "reference": "W", "comparison": "kW"}},
        {"units": {"time": "s", "reference": "K", "comparison": "degC"}},
        {"units": {"time": "s", "reference": "K", "comparison": "K"}},
        {"units": {"time": "s", "reference": "degC", "comparison": "degC"}},
        {"quantity_kind": "unknown"},
        {"quantity_kind": "absolute-temperature"},
        {"quantity_kind": "temperature-difference"},
        {
            "quantity_kind": "temperature-difference",
            "units": {"time": "s", "reference": "degC", "comparison": "degC"},
        },
        {"columns": {"time": "t", "value": "ref"}},
        {"columns": {"time": "t", "reference": "ref", "comparison": "ref"}},
        {"threshold": float("nan")},
        {"crossing_direction": "rising"},
    ],
)
def test_invalid_definitions_are_not_guessed(tmp_path, options):
    with pytest.raises(ValueError):
        _report(tmp_path, **options)


@pytest.mark.parametrize(
    "options",
    [
        {"temporal_value_kind": "cumulative"},
        {"temperature_reference": 20},
        {"pair_by": "case"},
        {"reference": "base"},
        {"comparison": "new"},
        {"weight_kind": "area"},
        {"region_fraction": "fraction"},
        {"region_complement": True},
        {"unit_column": "unit"},
        {"reference_kind": "reported-range"},
    ],
)
def test_inapplicable_options_are_rejected(tmp_path, options):
    with pytest.raises(ValueError):
        _report(tmp_path, **options)


def test_percentage_and_source_record_do_not_reinterpret_difference_scalars(tmp_path):
    report = _report(tmp_path)
    with pytest.raises(ValueError, match="percentage"):
        _resolve(report, "maximum", percentage=True)
    with pytest.raises(ValueError, match="source_record"):
        _resolve(report, "maximum", source_record=2)
    with pytest.raises(ValueError, match="unsupported field"):
        _resolve(report, "relative_change")


def test_subtraction_overflow_is_not_a_computed_difference(tmp_path):
    with pytest.raises(ValueError, match="nonfinite"):
        _report(tmp_path, samples=((0, -1e308, 1e308), (1, 1, 2)))


def test_changed_original_record_refreshes_difference_and_retains_before_report(tmp_path):
    before = _report(tmp_path)
    after = _report(tmp_path, samples=((0, 10, 12), (1, 20, 24), (3, 30, 34)))
    assert _resolve(before, "integral")["raw_value"] == 14
    assert _resolve(after, "integral")["raw_value"] == 11
    assert before["groups"][0]["samples"][1]["comparison"] == 26
    assert after["groups"][0]["samples"][1]["comparison"] == 24
