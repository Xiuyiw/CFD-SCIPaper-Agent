import math

import pytest

from cfdpaper.scientific.activated_response import activated_response_mean


def face(member="left", c=2, t=200, area=1, group="sample"):
    return {"label": group, "id": member, "c": c, "T": t, "A": area}


def reduce(rows, **changes):
    options = dict(
        group="label",
        member="id",
        concentration="c",
        temperature="T",
        area="A",
        prefactor=2.0,
        concentration_ref=2.0,
        concentration_power=2.0,
        activation_K=400 * math.log(2),
        output_power=2.0,
        concentration_unit="mol/m3",
        reference_unit="mol/m3",
        temperature_unit="K",
        area_unit="m2",
    )
    return activated_response_mean(rows, **(options | changes))


def test_response_precedes_area_mean():
    # Temperature factors 1/4 and 1/2 yield member responses 1/4 and 16.
    rows = [face(), face("right", c="4", t="400", area="3")]
    (result,) = reduce(iter(rows))
    assert result == {"group": "sample", "count": 2, "area_m2": 4, "mean": pytest.approx(12.0625)}
    assert result["mean"] != pytest.approx((2 * (3.5 / 2) ** 2 * 2 ** (-400 / 350)) ** 2)
    assert result["mean"] != pytest.approx(((0.5 + 3 * 4) / 4) ** 2)


def test_groups_keep_valid_zeros_and_can_reuse_a_member_id_in_another_group():
    rows = [face(c=0), face(group="other"), face("right")]
    first, second = reduce(rows, activation_K=0)
    assert first == {"group": "sample", "count": 2, "area_m2": 2, "mean": pytest.approx(2)}
    assert second == {"group": "other", "count": 1, "area_m2": 1, "mean": pytest.approx(4)}
    assert reduce(rows, prefactor=0)[0]["mean"] == 0


def test_explicit_basis_is_matched_independently_of_units():
    (result,) = reduce(
        [face()],
        concentration_unit="ppmv",
        reference_unit="ppmv",
        concentration_basis="dry",
        reference_basis="dry",
    )
    assert result["mean"] == pytest.approx(0.25)


@pytest.mark.parametrize(
    "changes",
    [
        {"reference_unit": "kg/m3"},
        {"reference_unit": "ppm", "concentration_unit": "ppmv"},
        {"reference_unit": "Pa", "concentration_unit": "Pa"},
        {"temperature_unit": "degC"},
        {"area_unit": "mm2"},
        {"concentration_basis": "dry", "reference_basis": "wet"},
        {"reference_basis": "dry"},
        {"concentration_basis": " ", "reference_basis": " "},
        {"concentration_ref": 0},
        {"concentration_power": 0},
        {"output_power": -1},
        {"activation_K": -1},
        {"prefactor": -1},
        {"prefactor": math.inf},
        {"output_power": True},
        {"area": "T"},
    ],
)
def test_rejects_invalid_definition(changes):
    with pytest.raises(ValueError):
        reduce([face()], **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"id": ""},
        {"label": None},
        {"id": False},
        {"c": -1},
        {"T": 0},
        {"A": 0},
        {"A": -1},
        {"A": "nan"},
        {"T": math.inf},
        {"c": True},
        {"c": ""},
        {"c": None},
    ],
)
def test_no_dropped_member_or_imputed_value(changes):
    with pytest.raises(ValueError, match="row 2"):
        reduce([face(), face("other") | changes])


def test_missing_column_duplicate_member_and_empty_table_fail_explicitly():
    with pytest.raises(ValueError, match="row 1.*'c'"):
        reduce([{k: v for k, v in face().items() if k != "c"}])
    with pytest.raises(ValueError, match="duplicate"):
        reduce([face(1), face("1")])
    with pytest.raises(ValueError, match="at least one"):
        reduce([])


def test_overflow_cannot_turn_into_a_reported_result():
    with pytest.raises(ValueError, match="response"):
        reduce([face(c=1e280)])
    with pytest.raises(ValueError, match="area"):
        reduce([face(area=1e308), face("right", area=1e308)])


def test_a_positive_csv_value_below_numeric_range_is_not_a_physical_zero():
    with pytest.raises(ValueError, match="row 1 concentration"):
        reduce([face(c="1e-999")])
    assert reduce([face(c="0.0e-999")])[0]["mean"] == 0


def test_tiny_member_with_large_response_retains_its_weighted_contribution():
    # Neither the unscaled area fraction (1e-600) nor a large raw area*value
    # product needs to be representable to evaluate a representable mean.
    rows = [face(c=1e300, area=1e-300), face("other", c=0, area=1e300)]
    (result,) = reduce(
        rows,
        prefactor=1,
        concentration_ref=1,
        concentration_power=1,
        activation_K=0,
        output_power=1,
    )
    assert math.isclose(result["mean"], 1e-300, rel_tol=1e-12)


def test_fractional_power_can_recover_a_small_activation_without_a_false_zero():
    # exp(-2000) alone underflows in binary64; its square root underflows too,
    # but the declared fourth root exp(-500) is representable.
    (result,) = reduce([face(t=1)], prefactor=1, activation_K=2000, output_power=0.25)
    assert math.isclose(result["mean"], math.exp(-500), rel_tol=1e-12)
