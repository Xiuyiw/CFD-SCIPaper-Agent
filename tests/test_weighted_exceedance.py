import math

import numpy as np
import pytest

from cfdpaper.publication.table_evidence import (
    calculate_declared_table,
    calculate_table,
    resolve_table_result,
    weighted_exceedance_curve,
)


def calculate(tmp_path, values=(300, 320), weights=(1, 3), **overrides):
    path = tmp_path / "elements.csv"
    path.write_text(
        "value,measure\n"
        + "".join(f"{value},{weight}\n" for value, weight in zip(values, weights, strict=True)),
        encoding="utf-8",
    )
    definition = {
        "operation": "weighted_exceedance",
        "columns": {"value": "value", "weight": "measure"},
        "units": {"value": "K", "weight": "m2"},
        "weight_kind": "area",
        "quantity_kind": "absolute-temperature",
        "threshold": 310.0,
        **overrides,
    }
    return {
        "id": "above",
        "source": "sources/elements.csv",
        **definition,
        **calculate_declared_table(path, definition),
    }


def result(tmp_path, values=(300, 320), weights=(1, 3), **overrides):
    return calculate(tmp_path, values, weights, **overrides)["groups"][0]["result"]


def test_unequal_area_and_threshold_metadata(tmp_path):
    report = calculate(tmp_path)
    assert report["rows_read"] == 2
    assert report["groups"][0] == {
        "group": "all",
        "csv_records": [2, 3],
        "status": "computed",
        "result": {
            "weight_sum": 4,
            "measure_above": 3,
            "exceedance_fraction": 0.75,
            "count": 2,
        },
        "threshold": 310.0,
        "exceedance_relation": "above",
    }


@pytest.mark.parametrize("relation,expected", [("above", 0), ("at-or-above", 0.75)])
def test_strict_and_inclusive_threshold(tmp_path, relation, expected):
    actual = result(tmp_path, threshold=320, exceedance_relation=relation)
    assert actual["exceedance_fraction"] == expected


@pytest.mark.parametrize("factor", [1e-100, 0.25, 10, 1e100])
def test_area_scaling_preserves_fraction(tmp_path, factor):
    actual = result(tmp_path, weights=(factor, 3 * factor))
    assert actual["exceedance_fraction"] == pytest.approx(0.75)
    assert actual["weight_sum"] == pytest.approx(4 * factor)
    assert actual["measure_above"] == pytest.approx(3 * factor)


def test_same_value_element_split_preserves_measure_and_fraction(tmp_path):
    original = result(tmp_path)
    split = result(tmp_path, values=(300, 320, 320), weights=(1, 1, 2))
    assert split.pop("count") == 3
    original.pop("count")
    assert split == pytest.approx(original)


def test_threshold_distribution_is_bounded_and_nonincreasing(tmp_path):
    fractions = [
        result(tmp_path, threshold=threshold)["exceedance_fraction"]
        for threshold in (290, 300, 310, 320, 330)
    ]
    assert fractions == [1, 0.75, 0.75, 0, 0]
    assert all(0 <= fraction <= 1 for fraction in fractions)
    assert fractions == sorted(fractions, reverse=True)


@pytest.mark.parametrize("relation", ["above", "at-or-above"])
def test_curve_and_scalar_share_threshold_semantics(tmp_path, relation):
    thresholds = [330, 290, 320, 300, 310, 320]
    curve = weighted_exceedance_curve([300, 320], [1, 3], thresholds, relation)
    assert [row["threshold"] for row in curve] == thresholds
    for threshold, row in zip(thresholds, curve, strict=True):
        row.pop("threshold")
        assert row == result(tmp_path, threshold=threshold, exceedance_relation=relation)


def test_curve_duplicate_values_and_unequal_weights():
    curve = weighted_exceedance_curve([320, 300, 320], [2, 1, 3], [299, 300, 320])
    assert [row["measure_above"] for row in curve] == [6, 5, 0]
    assert [row["exceedance_fraction"] for row in curve] == [1, 5 / 6, 0]


@pytest.mark.parametrize(
    "values,weights,thresholds,relation",
    [
        ([], [], [1], "above"),
        ([1], [1, 2], [1], "above"),
        ([math.nan], [1], [1], "above"),
        ([1], [0], [1], "above"),
        ([1], [1], [], "above"),
        ([1], [1], [math.inf], "above"),
        ([1], [1], [True], "above"),
        ([1], [1], [1], "below"),
    ],
)
def test_curve_rejects_invalid_inputs(values, weights, thresholds, relation):
    with pytest.raises(ValueError):
        weighted_exceedance_curve(values, weights, thresholds, relation)


def test_temperature_and_threshold_shift_preserves_fraction(tmp_path):
    kelvin = result(tmp_path)
    celsius = result(
        tmp_path,
        values=(26.85, 46.85),
        units={"value": "degC", "weight": "m2"},
        threshold=36.85,
    )
    assert celsius == kelvin


@pytest.mark.parametrize("weight_kind,unit", [("area", "mm2"), ("volume", "cm3")])
def test_measure_units_and_fraction_display(tmp_path, weight_kind, unit):
    report = calculate(tmp_path, weight_kind=weight_kind, units={"value": "K", "weight": unit})
    for field, expected_unit in (
        ("weight_sum", unit),
        ("measure_above", unit),
        ("count", ""),
        ("exceedance_fraction", ""),
    ):
        resolved = resolve_table_result([report], calculation_id="above", group="all", field=field)
        assert resolved["unit"] == expected_unit
        assert resolved["csv_records"] == [2, 3]
    percentage = resolve_table_result(
        [report],
        calculation_id="above",
        group="all",
        field="exceedance_fraction",
        percentage=True,
    )
    assert (percentage["value"], percentage["unit"], percentage["raw_value"]) == (
        "75.000",
        "%",
        0.75,
    )


@pytest.mark.parametrize("field", ["weight_sum", "measure_above", "count"])
def test_percentage_display_rejects_nonfraction_fields(tmp_path, field):
    report = calculate(tmp_path)
    with pytest.raises(ValueError, match="only supported for relative quantities"):
        resolve_table_result(
            [report], calculation_id="above", group="all", field=field, percentage=True
        )


def test_npz_group_and_filter_preserve_original_indices(tmp_path):
    path = tmp_path / "field.npz"
    np.savez(path, value=[300, 310, 320, 330], measure=[1, 2, 3, 4], case=["a", "b", "a", "b"])
    definition = {
        "operation": "weighted_exceedance",
        "columns": {"value": "value", "weight": "measure"},
        "units": {"value": "K", "weight": "m2"},
        "quantity_kind": "absolute-temperature",
        "weight_kind": "area",
        "threshold": 310,
        "row_filters": {"case": "a"},
        "group_by": "case",
    }
    report = {
        "id": "above",
        "source": "sources/field.npz",
        **definition,
        **calculate_declared_table(path, definition),
    }
    assert report["groups"][0]["array_indices"] == [0, 2]
    resolved = resolve_table_result(
        [report], calculation_id="above", group="a", field="exceedance_fraction"
    )
    assert resolved["array_indices"] == [0, 2]
    assert resolved["raw_value"] == 0.75


@pytest.mark.parametrize("weight", ["", "nan", "inf", "-inf", "bad", 0, -1])
@pytest.mark.parametrize("value", [300, ""])
def test_invalid_weight_is_rejected_even_when_value_missing(tmp_path, value, weight):
    with pytest.raises(ValueError):
        calculate(tmp_path, values=(value, 320), weights=(weight, 3))


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "bad"])
def test_invalid_value_rejected(tmp_path, value):
    with pytest.raises(ValueError):
        calculate(tmp_path, values=(value, 320))


def test_missing_value_keeps_members_and_threshold_metadata(tmp_path):
    report = calculate(tmp_path, values=("", 320))
    group = report["groups"][0]
    assert group["status"] == "missing-values"
    assert group["result"] is None
    assert group["csv_records"] == [2, 3]
    assert group["threshold"] == 310
    assert group["exceedance_relation"] == "above"


@pytest.mark.parametrize("threshold", [None, True, "310", math.nan, math.inf, -math.inf])
def test_threshold_must_be_finite_numeric(tmp_path, threshold):
    with pytest.raises(ValueError, match="finite threshold"):
        calculate(tmp_path, threshold=threshold)


@pytest.mark.parametrize(
    "overrides",
    [
        {"exceedance_relation": "below"},
        {"weight_kind": None},
        {"weight_kind": "mass"},
        {"weight_kind": "volume"},
        {"units": {"value": "K", "weight": "kg"}},
        {"units": {"value": "K"}},
        {"units": {"value": "K", "weight": "m2"}, "quantity_kind": "ordinary"},
        {"units": {"value": "degC", "weight": "m2"}, "quantity_kind": "ordinary"},
        {"units": {"value": "Pa", "weight": "m2"}},
        {"columns": {"value": "value", "weight": "value"}},
        {"temperature_reference": 273.15},
        {"pair_by": "case"},
        {"reference": "a"},
        {"comparison": "b"},
        {"region_fraction": "fraction"},
        {"region_complement": True},
        {"time_window": [0, 1]},
        {"temporal_value_kind": "cumulative"},
        {"crossing_direction": "at-or-below"},
    ],
)
def test_inappropriate_options_and_units_rejected(tmp_path, overrides):
    with pytest.raises(ValueError):
        calculate(tmp_path, **overrides)


def test_exceedance_relation_not_silently_used_for_other_operations(tmp_path):
    path = tmp_path / "population.csv"
    path.write_text("value\n1\n2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exceedance_relation requires"):
        calculate_table(
            path,
            operation="population",
            columns={"value": "value"},
            exceedance_relation="at-or-above",
        )


def test_declared_unit_column_must_match_value_unit(tmp_path):
    path = tmp_path / "units.csv"
    path.write_text("value,measure,unit\n300,1,K\n320,3,degC\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unit mismatch"):
        calculate_table(
            path,
            operation="weighted_exceedance",
            columns={"value": "value", "weight": "measure"},
            units={"value": "K", "weight": "m2"},
            quantity_kind="absolute-temperature",
            weight_kind="area",
            threshold=310,
            unit_column="unit",
        )


def test_nonfinite_total_measure_rejected(tmp_path):
    with pytest.raises(ValueError, match="nonfinite measure"):
        calculate(tmp_path, weights=(1e308, 1e308))
