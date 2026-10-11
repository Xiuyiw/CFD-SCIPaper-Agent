"""Declared numerical envelopes are observations, not model approval or confidence intervals."""

import inspect

import numpy as np
import pytest

from cfdpaper.publication.table_evidence import (
    _TABLE_DECLARATION_KEYS,
    REFERENCE_RANGE_FIELDS,
    calculate_declared_table,
    calculate_result_comparison,
    calculate_table,
    resolve_table_result,
)


def _declaration(*, half_width=False, unit="s", **changes):
    roles = (
        {"value", "reference", "half_width"}
        if half_width
        else {"value", "reference", "lower", "upper"}
    )
    return {
        "id": "range",
        "source": "sources/reference.csv",
        "domain": "Same declared observation",
        "operation": "reference_range",
        "columns": {role: role for role in roles},
        "units": dict.fromkeys(roles, unit),
        "reference_kind": "reported-range",
        **changes,
    }


def _report(path, declaration=None):
    declaration = declaration or _declaration()
    return {**declaration, **calculate_declared_table(path, declaration)}


def _resolve(report, field, group="all", **kwargs):
    return resolve_table_result(
        [report], calculation_id=report["id"], group=group, field=field, **kwargs
    )


@pytest.mark.parametrize(
    "value,delta,outside,relation",
    [
        (7, -3, -1, "below"),
        (8, -2, 0, "inside"),
        (10, 0, 0, "inside"),
        (12, 2, 0, "inside"),
        (15, 5, 3, "above"),
    ],
)
def test_raw_numeric_comparison_ignores_existing_error_and_within_columns(
    tmp_path, value, delta, outside, relation
):
    path = tmp_path / "reference.csv"
    path.write_text(
        f"value,reference,lower,upper,error,within\n{value},10,8,12,999,true\n",
        encoding="utf-8",
    )
    report = _report(path)
    assert report["reference_kind"] == "reported-range"
    assert report["groups"][0] == {
        "group": "all",
        "csv_records": [2],
        "status": "computed",
        "result": {
            "value": value,
            "reference_value": 10,
            "reference_lower": 8,
            "reference_upper": 12,
            "difference": delta,
            "outside_distance": outside,
            "reference_relation": relation,
        },
    }
    for field in REFERENCE_RANGE_FIELDS:
        selected = _resolve(report, field)
        assert selected["raw_value"] == report["groups"][0]["result"][field]
        assert selected["unit"] == "s"
        assert selected["source"] == "sources/reference.csv"
        assert selected["csv_records"] == [2]
    assert "PASS" not in str(report) and "confidence" not in str(report)
    with pytest.raises(ValueError, match="unsupported field"):
        _resolve(report, "reference_relation")


@pytest.mark.parametrize("kind", ["reported-range", "figure-reading-envelope", "declared-bound"])
def test_half_width_yields_expected_bounds_and_preserves_range_kind(tmp_path, kind):
    path = tmp_path / "reference.csv"
    path.write_text("value,reference,half_width\n13,10,2\n", encoding="utf-8")
    report = _report(path, _declaration(half_width=True, reference_kind=kind))
    result = report["groups"][0]["result"]
    assert (result["reference_lower"], result["reference_upper"]) == (8, 12)
    assert (result["difference"], result["outside_distance"]) == (3, 1)
    assert report["reference_kind"] == kind


def test_celsius_keeps_source_values_but_reports_deltas_in_kelvin(tmp_path):
    path = tmp_path / "reference.csv"
    path.write_text("value,reference,lower,upper\n85,80,78,82\n", encoding="utf-8")
    report = _report(path, _declaration(unit="degC", quantity_kind="absolute-temperature"))
    for field in ("value", "reference_value", "reference_lower", "reference_upper"):
        assert _resolve(report, field)["unit"] == "degC"
    assert (
        _resolve(report, "difference")["raw_value"],
        _resolve(report, "difference")["unit"],
    ) == (5, "K")
    assert (
        _resolve(report, "outside_distance")["raw_value"],
        _resolve(report, "outside_distance")["unit"],
    ) == (3, "K")
    for field in REFERENCE_RANGE_FIELDS:
        with pytest.raises(ValueError, match="percentage"):
            _resolve(report, field, percentage=True)
    kelvin = _declaration(unit="K", quantity_kind="absolute-temperature")
    path.write_text("value,reference,lower,upper\n358.15,353.15,351.15,355.15\n")
    kr = _report(path, kelvin)["groups"][0]["result"]
    assert kr["difference"] == pytest.approx(5)
    assert kr["outside_distance"] == pytest.approx(3)


@pytest.mark.parametrize("unit", ["Pa", "s"])
def test_non_temperature_units_are_not_converted(tmp_path, unit):
    path = tmp_path / "reference.csv"
    path.write_text("value,reference,lower,upper\n5,7,6,9\n")
    report = _report(path, _declaration(unit=unit))
    assert _resolve(report, "difference")["unit"] == unit
    assert _resolve(report, "outside_distance")["unit"] == unit


@pytest.mark.parametrize(
    "row,half_width",
    [
        ("11,10,,12", False),
        ("11,10,8,", False),
        (",10,8,12", False),
        ("11,,8,12", False),
        ("11,10,", True),
    ],
)
def test_missing_numeric_range_remains_missing(tmp_path, row, half_width):
    path = tmp_path / "reference.csv"
    headers = "value,reference,half_width" if half_width else "value,reference,lower,upper"
    path.write_text(headers + "\n" + row + "\n")
    report = _report(path, _declaration(half_width=half_width))
    assert report["groups"][0]["status"] == "missing-values"
    assert report["groups"][0]["result"] is None
    with pytest.raises(ValueError, match="unavailable"):
        _resolve(report, "difference")


@pytest.mark.parametrize(
    "row,half_width,match",
    [
        ("11,10,12,8", False, "lower bound"),
        ("11,10,11,12", False, "within"),
        ("11,10,7,9", False, "within"),
        ("11,10,-2", True, "nonnegative"),
        (",10,-2", True, "nonnegative"),
        ("nan,10,8,12", False, "Nonfinite"),
        ("11,10,8,inf", False, "Nonfinite"),
        ("11,10,1e309", True, "Nonfinite"),
        ("1e308,1e308,1e308", True, "nonfinite result"),
    ],
)
def test_invalid_numeric_ranges_are_rejected(tmp_path, row, half_width, match):
    path = tmp_path / "reference.csv"
    headers = "value,reference,half_width" if half_width else "value,reference,lower,upper"
    path.write_text(headers + "\n" + row + "\n")
    with pytest.raises(ValueError, match=match):
        _report(path, _declaration(half_width=half_width))


def test_exact_filters_keep_csv_record_locations_and_do_not_parse_excluded_rows(tmp_path):
    path = tmp_path / "reference.csv"
    path.write_text(
        "case,stage,unit,value,reference,lower,upper\n"
        "a,old,s,not-numeric,10,8,12\n"
        "a,new,s,13,10,8,12\n"
        "b,new,s,7,10,8,12\n"
    )
    report = _report(
        path, _declaration(group_by="case", row_filters={"stage": "new"}, unit_column="unit")
    )
    assert report["rows_read"] == 2
    assert _resolve(report, "difference", group="a")["csv_records"] == [3]
    assert _resolve(report, "outside_distance", group="b")["csv_records"] == [4]
    with pytest.raises(ValueError, match="No records match"):
        _report(path, _declaration(row_filters={"stage": "NEW"}))


def test_duplicate_group_is_not_averaged(tmp_path):
    path = tmp_path / "reference.csv"
    path.write_text("case,value,reference,lower,upper\na,11,10,8,12\na,12,10,8,12\n")
    with pytest.raises(ValueError, match="exactly one.*a"):
        _report(path, _declaration(group_by="case"))


def test_npz_exact_filter_keeps_original_array_index(tmp_path):
    path = tmp_path / "reference.npz"
    np.savez(
        path,
        value=[5, 13],
        reference=[10, 10],
        lower=[8, 8],
        upper=[12, 12],
        stage=["old", "new"],
        unrelated=np.zeros((2, 2)),
    )
    declaration = _declaration(row_filters={"stage": "new"}, source="sources/reference.npz")
    report = _report(path, declaration)
    assert report["groups"][0]["array_indices"] == [1]
    assert _resolve(report, "outside_distance")["array_indices"] == [1]
    assert _resolve(report, "outside_distance")["raw_value"] == 1


@pytest.mark.parametrize(
    "changes,match",
    [
        ({"reference_kind": None}, "reference_kind"),
        ({"reference_kind": "95%-confidence-interval"}, "reference_kind"),
        (
            {"units": {"value": "s", "reference": "ms", "lower": "s", "upper": "s"}},
            "identical declared units",
        ),
        ({"units": {"value": "s"}}, "identical declared units"),
        ({"quantity_kind": "unknown"}, "quantity_kind"),
        ({"unit": "degC"}, "Celsius"),
        ({"unit": "K"}, "Declare whether K"),
        ({"unit": "s", "quantity_kind": "absolute-temperature"}, "Absolute temperature"),
        ({"unit": "degC", "quantity_kind": "temperature-difference"}, "Celsius"),
        (
            {"columns": {"value": "value", "reference": "reference", "lower": "lower"}},
            "requires value,reference",
        ),
    ],
)
def test_invalid_declarations_are_rejected_before_reading(tmp_path, changes, match):
    with pytest.raises(ValueError, match=match):
        _report(tmp_path / "not-read.csv", _declaration(**changes))


@pytest.mark.parametrize(
    "operation",
    [
        "scalar_select",
        "population",
        "paired_change",
        "weighted_population",
        "partition",
        "temporal",
    ],
)
def test_other_operations_reject_reference_kind(tmp_path, operation):
    with pytest.raises(ValueError, match="reference_kind requires"):
        calculate_table(
            tmp_path / "not-read.csv",
            operation=operation,
            columns={"value": "value"},
            reference_kind="declared-bound",
        )


def test_declaration_helper_is_complete_and_returns_only_engine_output(tmp_path):
    assert _TABLE_DECLARATION_KEYS == set(inspect.signature(calculate_table).parameters) - {"path"}
    path = tmp_path / "reference.csv"
    path.write_text("value,reference,lower,upper\n11,10,8,12\n")
    declaration = _declaration(extra_report_metadata={"label": "not an engine option"})
    result = calculate_declared_table(path, declaration)
    assert set(result) == {"rows_read", "groups", "reference_kind"}
    assert not {"id", "source", "domain", "extra_report_metadata"} & result.keys()


def test_range_is_not_automatically_a_compatible_result_comparison_parent(tmp_path):
    path = tmp_path / "reference.csv"
    path.write_text("value,reference,lower,upper\n11,10,8,12\n")
    report = _report(path)
    ref = {"calculation_id": "range", "group": "all", "field": "difference"}
    with pytest.raises(ValueError, match="unsupported parent operation"):
        calculate_result_comparison(
            [report],
            id="derived",
            domain="declared observation",
            definition_source="methods.txt:L1",
            reference=ref,
            comparison={**ref, "field": "value"},
        )
