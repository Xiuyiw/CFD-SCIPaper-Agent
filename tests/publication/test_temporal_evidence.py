import copy

import numpy as np
import pytest

from cfdpaper.publication.table_evidence import (
    calculate_result_comparison,
    calculate_table,
    resolve_table_result,
)


def _report(tmp_path, name="a", samples=((0, 2), (1, 6), (3, 4)), **kwargs):
    path = tmp_path / f"{name}.csv"
    path.write_text("t,v\n" + "\n".join(f"{t},{v}" for t, v in samples), encoding="utf-8")
    units = kwargs.pop("units", {"time": "s", "value": "W"})
    return {
        "id": name,
        "source": f"sources/{name}.csv",
        "operation": "temporal",
        "units": units,
        "domain": "saved history",
        **kwargs,
        **calculate_table(
            path, operation="temporal", columns={"time": "t", "value": "v"}, units=units, **kwargs
        ),
    }


def _resolve(report, field, **kwargs):
    return resolve_table_result(
        [report], calculation_id=report["id"], group="all", field=field, **kwargs
    )


def _compare(reports, field="integral"):
    return calculate_result_comparison(
        reports,
        id="contrast",
        domain="saved history",
        definition_source="methods.txt:L1",
        reference={"calculation_id": "a", "group": "all", "field": field},
        comparison={"calculation_id": "b", "group": "all", "field": field},
    )


def test_nonuniform_trapezoid_not_arithmetic_mean_and_locations(tmp_path):
    report = _report(tmp_path)
    group = report["groups"][0]
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
        "first_crossing_time": None,
    }
    assert group["result"]["time_mean"] != 4
    assert group["csv_records"] == [2, 3, 4]
    assert group["time_window"] == [0, 3]
    assert group["sampling"] == "saved-samples"
    assert group["integration_method"] == "trapezoidal-nonuniform"
    assert group["window_selection"] == "full-saved-coverage"
    assert _resolve(report, "integral")["unit"] == "J"
    assert _resolve(report, "integral")["csv_records"] == [2, 3, 4]
    assert _resolve(report, "duration")["unit"] == "s"
    assert _resolve(report, "sample_count")["unit"] == ""


@pytest.mark.parametrize("window", [[1, 3], (1, 3)])
def test_exact_window_keeps_original_record_numbers(tmp_path, window):
    report = _report(tmp_path, samples=((0, 9), (1, 2), (3, 6), (4, 8)), time_window=window)
    group = report["groups"][0]
    assert group["csv_records"] == [3, 4]
    assert group["result"]["integral"] == 8
    assert group["result"]["sample_count"] == 2
    assert group["time_window"] == [1, 3]
    assert group["window_selection"] == "exact-sampled-endpoints"


@pytest.mark.parametrize("times", [(0,), (0, 0, 3), (0, 3, 1), (0, "", 3), (0, "nan", 3)])
def test_invalid_time_samples_are_not_sorted_deduplicated_or_dropped(tmp_path, times):
    with pytest.raises(ValueError):
        _report(tmp_path, samples=[(t, 1) for t in times])


@pytest.mark.parametrize(
    "window", [[0, 2], [-1, 3], [0, 4], [1, 1], [3, 0], [0], [0, float("inf")]]
)
def test_invalid_or_unsampled_windows_are_rejected(tmp_path, window):
    with pytest.raises(ValueError):
        _report(tmp_path, time_window=window)


def test_missing_value_remains_unavailable(tmp_path):
    report = _report(tmp_path, samples=((0, 1), (1, ""), (3, 2)))
    assert report["groups"][0]["status"] == "missing-values"
    for field in ("integral", "maximum", "change"):
        with pytest.raises(ValueError, match="unavailable"):
            _resolve(report, field)
    with pytest.raises(ValueError, match="unavailable"):
        _compare([report, _report(tmp_path, "b")])


def test_cumulative_energy_change_is_not_integrated(tmp_path):
    report = _report(tmp_path, units={"time": "s", "value": "J"}, temporal_value_kind="cumulative")
    result = report["groups"][0]["result"]
    assert result["change"] == 2
    assert result["integral"] is None and result["time_mean"] is None
    assert report["groups"][0]["integration_method"] is None
    assert _resolve(report, "change")["unit"] == "J"
    for field in ("integral", "time_mean"):
        with pytest.raises(ValueError, match="missing"):
            _resolve(report, field)


@pytest.mark.parametrize(
    "unit,integral_unit", [("kW", "kJ"), ("MW", "MJ"), ("kg/s", "kg"), ("Pa", "Pa·s")]
)
def test_integral_units_without_scale_conversion(tmp_path, unit, integral_unit):
    report = _report(tmp_path, units={"time": "s", "value": unit})
    resolved = _resolve(report, "integral")
    assert resolved["unit"] == integral_unit
    assert resolved["raw_value"] == 14


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
def test_threshold_is_first_saved_sample_not_interpolation(
    tmp_path, direction, threshold, expected
):
    report = _report(tmp_path, threshold=threshold, crossing_direction=direction)
    assert report["groups"][0]["result"]["first_crossing_time"] == expected
    if expected is None:
        with pytest.raises(ValueError, match="missing"):
            _resolve(report, "first_crossing_time")
    else:
        assert _resolve(report, "first_crossing_time")["unit"] == "s"


def test_peak_uses_earliest_maximum_and_crossing_is_window_local(tmp_path):
    report = _report(tmp_path, samples=((0, 7), (1, 6), (3, 6)), time_window=[1, 3], threshold=7)
    assert report["groups"][0]["result"]["peak_time"] == 1
    assert report["groups"][0]["result"]["first_crossing_time"] is None


@pytest.mark.parametrize("unit,offset", [("K", 273.15), ("degC", 0)])
def test_temperature_units_and_no_absolute_temperature_ratios(tmp_path, unit, offset):
    reports = [
        _report(
            tmp_path,
            name,
            samples=[(0, 20 + offset), (1, end + offset)],
            units={"time": "s", "value": unit},
            quantity_kind="absolute-temperature",
        )
        for name, end in (("a", 25), ("b", 30))
    ]
    assert _resolve(reports[0], "change")["unit"] == "K"
    assert _resolve(reports[0], "time_mean")["unit"] == unit
    compared = _compare(reports, "maximum")
    assert compared["groups"][0]["result"]["relative_change"] is None
    assert _compare(reports, "change")["quantity_kind"] == "temperature-difference"
    with pytest.raises(ValueError, match="percentage"):
        _resolve(reports[0], "maximum", percentage=True)


def test_temperature_difference_keeps_kelvin_and_kelvin_requires_semantics(tmp_path):
    report = _report(
        tmp_path, units={"time": "s", "value": "K"}, quantity_kind="temperature-difference"
    )
    assert _resolve(report, "time_mean")["unit"] == "K"
    with pytest.raises(ValueError, match="Declare whether K"):
        _report(tmp_path, units={"time": "s", "value": "K"})


@pytest.mark.parametrize("unit", ["K", "degC"])
def test_absolute_temperature_integral_binds_but_cannot_be_compared(tmp_path, unit):
    reports = [
        _report(
            tmp_path, name, units={"time": "s", "value": unit}, quantity_kind="absolute-temperature"
        )
        for name in ("a", "b")
    ]
    assert _resolve(reports[0], "integral")["unit"] == f"{unit}·s"
    with pytest.raises(ValueError, match="temperature origin"):
        _compare(reports)


def test_threshold_time_comparison_requires_input_unit_and_quantity_kind(tmp_path):
    a = _report(
        tmp_path,
        samples=((0, 700), (1, 900)),
        threshold=800,
        units={"time": "s", "value": "K"},
        quantity_kind="absolute-temperature",
    )
    b = _report(
        tmp_path,
        "b",
        samples=((0, 700), (1, 900)),
        threshold=800,
        units={"time": "s", "value": "degC"},
        quantity_kind="absolute-temperature",
    )
    with pytest.raises(ValueError, match="input_value_unit"):
        _compare([a, b], "first_crossing_time")
    b = _report(
        tmp_path,
        "b",
        samples=((0, 700), (1, 900)),
        threshold=800,
        units={"time": "s", "value": "K"},
        quantity_kind="temperature-difference",
    )
    with pytest.raises(ValueError, match="input_quantity_kind"):
        _compare([a, b], "first_crossing_time")
    b = _report(
        tmp_path,
        "b",
        samples=((0, 700), (1, 900)),
        threshold=800,
        units={"time": "s", "value": "K"},
        quantity_kind="absolute-temperature",
    )
    comparison = _compare([a, b], "first_crossing_time")
    assert comparison["upstream"]["reference"]["input_value_unit"] == "K"
    assert comparison["upstream"]["reference"]["input_quantity_kind"] == "absolute-temperature"


def test_comparison_requires_same_window_kind_and_threshold_definition(tmp_path):
    a = _report(tmp_path)
    b = _report(tmp_path, "b", samples=((0, 3), (1, 7), (3, 5)))
    before = copy.deepcopy([a, b])
    assert _compare([a, b])["groups"][0]["result"]["difference"] == 3
    assert [a, b] == before
    b_window = _report(tmp_path, "b", time_window=[1, 3])
    with pytest.raises(ValueError, match="time_window"):
        _compare([a, b_window])
    b_cumulative = _report(tmp_path, "b", temporal_value_kind="cumulative")
    with pytest.raises(ValueError, match="temporal_value_kind"):
        _compare([a, b_cumulative], "change")
    a = _report(tmp_path, threshold=3)
    b = _report(tmp_path, "b", threshold=4)
    with pytest.raises(ValueError, match="threshold"):
        _compare([a, b], "first_crossing_time")


def test_group_filter_and_npz_support_preserve_source_identity(tmp_path):
    path = tmp_path / "groups.csv"
    path.write_text(
        "case,t,v,unit\nx,0,bad,bad\na,0,2,W\nb,0,3,W\na,1,6,W\nb,1,5,W\na,3,4,W\n",
        encoding="utf-8",
    )
    result = calculate_table(
        path,
        operation="temporal",
        columns={"time": "t", "value": "v"},
        units={"time": "s", "value": "W"},
        group_by="case",
        row_filters={"case": "a"},
        unit_column="unit",
    )
    assert result["groups"][0]["csv_records"] == [3, 5, 7]
    path = tmp_path / "history.npz"
    np.savez(path, t=[0.0, 1.0, 3.0], v=[2.0, 6.0, 4.0])
    report = {
        "id": "npz",
        "source": "history.npz",
        "operation": "temporal",
        "units": {"time": "s", "value": "W"},
        **calculate_table(
            path,
            operation="temporal",
            columns={"time": "t", "value": "v"},
            units={"time": "s", "value": "W"},
            time_window=[1, 3],
        ),
    }
    assert _resolve(report, "integral")["array_indices"] == [1, 2]


def test_interleaved_groups_use_each_original_time_order_and_units(tmp_path):
    path = tmp_path / "groups.csv"
    path.write_text(
        "case,t,v,unit\na,0,2,W\nb,0,3,W\na,1,6,W\nb,2,5,W\na,3,4,W\n",
        encoding="utf-8",
    )
    kwargs = {
        "operation": "temporal",
        "columns": {"time": "t", "value": "v"},
        "units": {"time": "s", "value": "W"},
        "group_by": "case",
        "unit_column": "unit",
    }
    result = calculate_table(path, **kwargs)
    assert [g["csv_records"] for g in result["groups"]] == [[2, 4, 6], [3, 5]]
    assert [g["result"]["integral"] for g in result["groups"]] == [14, 8]
    assert [g["time_window"] for g in result["groups"]] == [[0, 3], [0, 2]]
    path.write_text("case,t,v,unit\na,0,2,W\na,1,6,kW\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unit mismatch"):
        calculate_table(path, **kwargs)


def test_zero_threshold_and_comparison_keeps_both_sources(tmp_path):
    reports = [
        _report(tmp_path, name, samples=((0, -2), (1, end)), threshold=0)
        for name, end in (("a", 1), ("b", 3))
    ]
    compared = _compare(reports, "first_crossing_time")
    resolved = resolve_table_result(
        [compared], calculation_id="contrast", group="all", field="difference"
    )
    assert resolved["unit"] == "s" and resolved["raw_value"] == 0
    assert [r["csv_records"] for r in resolved["supporting_results"]] == [[2, 3], [2, 3]]
    assert [r["time_window"] for r in resolved["supporting_results"]] == [[0, 1], [0, 1]]


def test_temporal_options_do_not_change_existing_operations(tmp_path):
    path = tmp_path / "values.csv"
    path.write_text("v\n1\n3\n", encoding="utf-8")
    assert calculate_table(path, operation="population", columns={"value": "v"}) == {
        "rows_read": 2,
        "groups": [
            {
                "group": "all",
                "csv_records": [2, 3],
                "status": "computed",
                "result": {"count": 2, "sum": 4, "mean": 2, "cv": 0.5},
            }
        ],
    }
    with pytest.raises(ValueError, match="Temporal options"):
        calculate_table(path, operation="population", columns={"value": "v"}, time_window=[0, 1])


@pytest.mark.parametrize(
    "options",
    [
        {"units": {"time": "ms", "value": "W"}},
        {"threshold": float("nan")},
        {"crossing_direction": "rising"},
        {"temporal_value_kind": "average"},
    ],
)
def test_invalid_temporal_definitions_are_not_guessed(tmp_path, options):
    with pytest.raises(ValueError):
        _report(tmp_path, **options)
