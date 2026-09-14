import math
import statistics

import pytest

from cfdpaper.publication.table_evidence import calculate_table, resolve_table_result


def calculate(tmp_path, values, weights, **overrides):
    path = tmp_path / "elements.csv"
    path.write_text(
        "value,measure\n" + "".join(f"{v},{w}\n" for v, w in zip(values, weights, strict=True)),
        encoding="utf-8",
    )
    definition = {
        "operation": "weighted_population",
        "columns": {"value": "value", "weight": "measure"},
        "units": {"value": "m/s", "weight": "m^2"},
        "weight_kind": "area",
        **overrides,
    }
    return {
        "id": "spatial",
        "source": "sources/elements.csv",
        **definition,
        **calculate_table(path, **definition),
    }


def result(tmp_path, values, weights, **overrides):
    return calculate(tmp_path, values, weights, **overrides)["groups"][0]["result"]


def test_unequal_weights_known_population_answer(tmp_path):
    report = calculate(tmp_path, [1, 3], [1, 3])
    assert report["rows_read"] == 2
    assert report["groups"][0]["csv_records"] == [2, 3]
    assert report["groups"][0]["status"] == "computed"
    assert report["groups"][0]["result"] == pytest.approx(
        {"weighted_mean": 2.5, "weighted_std": math.sqrt(0.75), "weight_sum": 4}
    )


@pytest.mark.parametrize("values", [[1, 3, 8], [-4, 0, 9], [17]])
def test_equal_weights_match_population_and_single_element(tmp_path, values):
    actual = result(tmp_path, values, [2] * len(values))
    assert actual["weighted_mean"] == pytest.approx(statistics.fmean(values))
    assert actual["weighted_std"] == pytest.approx(statistics.pstdev(values))


@pytest.mark.parametrize("factor", [1e-100, 0.25, 10, 1e100])
def test_positive_weight_scaling_preserves_mean_and_std(tmp_path, factor):
    base = result(tmp_path, [1, 3, 8], [2, 3, 5])
    scaled = result(tmp_path, [1, 3, 8], [2 * factor, 3 * factor, 5 * factor])
    for field in ("weighted_mean", "weighted_std"):
        assert scaled[field] == pytest.approx(base[field])
    assert scaled["weight_sum"] == pytest.approx(base["weight_sum"] * factor)


def test_same_value_element_split_preserves_statistics(tmp_path):
    original = result(tmp_path, [1, 3], [1, 3])
    split = result(tmp_path, [1, 3, 3], [1, 1, 2])
    assert split == pytest.approx(original)


def test_small_spread_at_large_offset_is_stable(tmp_path):
    actual = result(tmp_path, [1e12 + 1, 1e12 + 3], [1, 3])
    assert actual["weighted_mean"] == 1e12 + 2.5
    assert actual["weighted_std"] == pytest.approx(math.sqrt(0.75))


def test_identical_large_values_have_exactly_zero_spread(tmp_path):
    actual = result(tmp_path, [1e12 + 1, 1e12 + 1], [1, 2])
    assert actual["weighted_mean"] == 1e12 + 1
    assert actual["weighted_std"] == 0


def test_large_finite_values_do_not_overflow_squared_deviations(tmp_path):
    actual = result(tmp_path, [-1e200, 1e200], [1, 1])
    assert actual["weighted_mean"] == 0
    assert actual["weighted_std"] == pytest.approx(1e200)


def test_finite_extreme_spread_avoids_overflowing_range(tmp_path):
    actual = result(tmp_path, [-1e308, 1e308], [1, 3])
    assert actual["weighted_mean"] == pytest.approx(5e307)
    assert actual["weighted_std"] == pytest.approx(math.sqrt(0.75) * 1e308)


def test_absolute_temperature_shift_preserves_sd_and_resolves_units(tmp_path):
    celsius = calculate(
        tmp_path,
        [20, 40],
        [1, 3],
        units={"value": "degC", "weight": "mm2"},
        quantity_kind="absolute-temperature",
    )
    kelvin = calculate(
        tmp_path,
        [293.15, 313.15],
        [1, 3],
        units={"value": "K", "weight": "mm2"},
        quantity_kind="absolute-temperature",
    )
    c = celsius["groups"][0]["result"]
    k = kelvin["groups"][0]["result"]
    assert k["weighted_mean"] == pytest.approx(c["weighted_mean"] + 273.15)
    assert k["weighted_std"] == pytest.approx(c["weighted_std"])
    for report, mean_unit in ((celsius, "degC"), (kelvin, "K")):
        for field, unit in (
            ("weighted_mean", mean_unit),
            ("weighted_std", "K"),
            ("weight_sum", "mm2"),
        ):
            selected = resolve_table_result(
                [report], calculation_id="spatial", group="all", field=field
            )
            assert selected["unit"] == unit
            assert selected["csv_records"] == [2, 3]
            assert selected["source"] == "sources/elements.csv"


@pytest.mark.parametrize("kind,power", [("area", "2"), ("volume", "3")])
@pytest.mark.parametrize("length", ["m", "cm", "mm"])
@pytest.mark.parametrize("notation", ["plain", "caret", "superscript"])
def test_declared_measure_units(tmp_path, kind, power, length, notation):
    suffix = {"plain": power, "caret": "^" + power, "superscript": {"2": "²", "3": "³"}[power]}[
        notation
    ]
    assert (
        result(
            tmp_path,
            [1, 3],
            [1, 3],
            weight_kind=kind,
            units={"value": "Pa", "weight": length + suffix},
        )["weighted_mean"]
        == 2.5
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"weight_kind": None},
        {"weight_kind": "mass"},
        {"weight_kind": "volume"},
        {"units": {"value": "Pa", "weight": "m3"}},
        {"units": {"value": "Pa", "weight": "kg"}},
        {"units": {"value": "Pa", "weight": "m2/cm2"}},
        {"units": {"value": "Pa"}},
        {"units": {"weight": "m2"}},
        {"columns": {"value": "value"}},
        {"columns": {"value": "value", "weight": "value"}},
        {"quantity_kind": "unknown"},
        {"units": {"value": "degC", "weight": "m2"}},
        {"units": {"value": "K", "weight": "m2"}},
        {"quantity_kind": "absolute-temperature"},
        {"quantity_kind": "temperature-difference"},
        {"units": {"value": "degC", "weight": "m2"}, "quantity_kind": "temperature-difference"},
    ],
)
def test_invalid_definitions_require_correction(tmp_path, overrides):
    with pytest.raises(ValueError):
        calculate(tmp_path, [1, 3], [1, 3], **overrides)


def test_kelvin_temperature_difference_is_explicitly_supported(tmp_path):
    report = calculate(
        tmp_path,
        [-2, 2],
        [1, 1],
        quantity_kind="temperature-difference",
        units={"value": "K", "weight": "m2"},
    )
    for field in ("weighted_mean", "weighted_std"):
        assert (
            resolve_table_result([report], calculation_id="spatial", group="all", field=field)[
                "unit"
            ]
            == "K"
        )


@pytest.mark.parametrize("weight", ["", "nan", "inf", "-inf", "not-a-number", 0, -1])
@pytest.mark.parametrize("value", [1, ""])
def test_invalid_weight_rejected_even_when_value_missing(tmp_path, weight, value):
    with pytest.raises(ValueError):
        calculate(tmp_path, [value, 3], [weight, 3])


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "not-a-number"])
def test_nonfinite_or_invalid_value_rejected(tmp_path, value):
    with pytest.raises(ValueError):
        calculate(tmp_path, [value, 3], [1, 3])


def test_missing_values_preserve_group_membership_and_valid_other_groups(tmp_path):
    path = tmp_path / "grouped.csv"
    path.write_text("case,x,w\na,1,1\nb,4,1\na,3,3\nb,,2\n", encoding="utf-8")
    report = {
        "id": "spatial",
        "source": "sources/grouped.csv",
        "operation": "weighted_population",
        "units": {"value": "Pa", "weight": "m3"},
        "weight_kind": "volume",
    }
    report.update(
        calculate_table(
            path,
            operation="weighted_population",
            columns={"value": "x", "weight": "w"},
            group_by="case",
            units=report["units"],
            weight_kind="volume",
        )
    )
    assert report["rows_read"] == 4
    assert report["groups"][1] == {
        "group": "b",
        "csv_records": [3, 5],
        "status": "missing-values",
        "result": None,
    }
    for field, unit in (("weighted_mean", "Pa"), ("weighted_std", "Pa"), ("weight_sum", "m3")):
        selected = resolve_table_result([report], calculation_id="spatial", group="a", field=field)
        assert selected["csv_records"] == [2, 4]
        assert selected["unit"] == unit
        with pytest.raises(ValueError, match="missing-values"):
            resolve_table_result([report], calculation_id="spatial", group="b", field=field)


@pytest.mark.parametrize("field", ["cv", "mean", "sum", "integral"])
def test_unsupported_weighted_results_are_not_inferred(tmp_path, field):
    report = calculate(tmp_path, [1, 3], [1, 3])
    with pytest.raises(ValueError, match="unsupported field"):
        resolve_table_result([report], calculation_id="spatial", group="all", field=field)


@pytest.mark.parametrize("overrides", [{"percentage": True}, {"source_record": 2}])
def test_weighted_resolver_rejects_percentage_or_single_record(tmp_path, overrides):
    report = calculate(tmp_path, [1, 3], [1, 3])
    with pytest.raises(ValueError):
        resolve_table_result(
            [report], calculation_id="spatial", group="all", field="weighted_mean", **overrides
        )


def test_nonfinite_weight_sum_is_explicit_failure(tmp_path):
    with pytest.raises(ValueError, match="nonfinite"):
        calculate(tmp_path, [1, 3], [1e308, 1e308])
