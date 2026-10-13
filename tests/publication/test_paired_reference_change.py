"""Paired observed changes use raw values and conservative endpoint envelopes."""

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
        ["value", "reference", "half_width"]
        if half_width
        else ["value", "reference", "lower", "upper"]
    )
    return {
        "id": "paired-range",
        "source": "sources/observations.csv",
        "operation": "paired_reference_change",
        "columns": {role: role for role in roles},
        "units": dict.fromkeys(roles, unit),
        "pair_by": "case",
        "reference": "base",
        "comparison": "new",
        "reference_kind": "reported-range",
        "domain": "Author-declared matched observation",
        "method_scope": "Author-provided same measurement operator",
        "report_boundary": "Author-provided comparison scope",
        **changes,
    }


def _report(path, declaration=None):
    declaration = declaration or _declaration()
    return {**declaration, **calculate_declared_table(path, declaration)}


def _resolve(report, field, group="all", **changes):
    return resolve_table_result(
        [report], calculation_id=report["id"], group=group, field=field, **changes
    )


def _write(path, comparison_value=100):
    path.write_text(
        "case,value,reference,lower,upper,error,within\n"
        f"new,{comparison_value},75,74,77,999,true\n"
        "base,80,70,68,72,999,true\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "comparison_value,delta,difference,outside,relation",
    [
        (79, -1, -6, -3, "below"),
        (82, 2, -3, 0, "inside"),
        (85, 5, 0, 0, "inside"),
        (89, 9, 4, 0, "inside"),
        (100, 20, 15, 11, "above"),
    ],
)
def test_raw_model_and_reference_changes_keep_signed_endpoint_distance(
    tmp_path, comparison_value, delta, difference, outside, relation
):
    path = tmp_path / "observations.csv"
    _write(path, comparison_value)
    report = _report(path)
    selected = report["groups"][0]
    assert selected["csv_records"] == [3, 2]
    assert selected["status"] == "computed"
    assert selected["result"] == {
        "value": delta,
        "reference_value": 5,
        "reference_lower": 2,
        "reference_upper": 9,
        "difference": difference,
        "outside_distance": outside,
        "reference_relation": relation,
    }
    assert selected["members"] == {
        "reference": {
            "member": "base",
            "csv_record": 3,
            "values": {"value": 80, "reference": 70, "lower": 68, "upper": 72},
        },
        "comparison": {
            "member": "new",
            "csv_record": 2,
            "values": {"value": comparison_value, "reference": 75, "lower": 74, "upper": 77},
        },
    }
    for field in REFERENCE_RANGE_FIELDS:
        resolved = _resolve(report, field)
        assert resolved["raw_value"] == selected["result"][field]
        assert resolved["unit"] == "s"
        assert resolved["csv_records"] == [3, 2]
        assert resolved["source"] == "sources/observations.csv"
    assert report["method_scope"] == "Author-provided same measurement operator"
    assert report["report_boundary"] == "Author-provided comparison scope"
    engine = calculate_declared_table(path, _declaration())
    assert set(engine) == {"rows_read", "groups", "reference_kind"}
    assert "PASS" not in str(engine) and "confidence" not in str(engine)


def test_pair_direction_is_selector_based_and_reverses_interval(tmp_path):
    path = tmp_path / "observations.csv"
    _write(path)
    result = _report(path, _declaration(reference="new", comparison="base"))["groups"][0]
    assert result["csv_records"] == [2, 3]
    assert result["result"] == {
        "value": -20,
        "reference_value": -5,
        "reference_lower": -9,
        "reference_upper": -2,
        "difference": -15,
        "outside_distance": -11,
        "reference_relation": "below",
    }


@pytest.mark.parametrize("kind", ["reported-range", "figure-reading-envelope", "declared-bound"])
def test_half_width_uses_sum_of_endpoint_half_widths_not_statistical_ci(tmp_path, kind):
    path = tmp_path / "observations.csv"
    path.write_text("case,value,reference,half_width\nbase,80,70,2\nnew,90,75,3\n")
    report = _report(path, _declaration(half_width=True, reference_kind=kind))
    result = report["groups"][0]["result"]
    assert (result["reference_lower"], result["reference_upper"]) == (0, 10)
    assert (result["value"], result["reference_value"], result["difference"]) == (10, 5, 5)
    assert report["reference_kind"] == kind
    assert report["groups"][0]["members"]["comparison"]["values"]["half_width"] == 3


@pytest.mark.parametrize("unit", ["degC", "°C", "C", "K"])
def test_all_six_absolute_temperature_outputs_are_kelvin_differences(tmp_path, unit):
    path = tmp_path / "observations.csv"
    _write(path)
    report = _report(path, _declaration(unit=unit, quantity_kind="absolute-temperature"))
    assert set(report["units"].values()) == {unit}
    assert report["groups"][0]["members"]["reference"]["values"]["value"] == 80
    for field in REFERENCE_RANGE_FIELDS:
        assert _resolve(report, field)["unit"] == "K"
    if unit != "K":
        path.write_text(
            "case,value,reference,lower,upper\n"
            "base,353.15,343.15,341.15,345.15\nnew,373.15,348.15,347.15,350.15\n"
        )
        kelvin = _report(path, _declaration(unit="K", quantity_kind="absolute-temperature"))
        for field in REFERENCE_RANGE_FIELDS:
            assert _resolve(kelvin, field)["raw_value"] == pytest.approx(
                _resolve(report, field)["raw_value"]
            )


@pytest.mark.parametrize(
    "unit,kind", [("Pa", "ordinary"), ("s", "ordinary"), ("K", "temperature-difference")]
)
def test_nonabsolute_units_keep_declared_scale(tmp_path, unit, kind):
    path = tmp_path / "observations.csv"
    _write(path)
    report = _report(path, _declaration(unit=unit, quantity_kind=kind))
    assert {_resolve(report, f)["unit"] for f in REFERENCE_RANGE_FIELDS} == {unit}


@pytest.mark.parametrize(
    "row,half_width",
    [
        ("base,,70,68,72", False),
        ("base,80,,68,72", False),
        ("base,80,70,,72", False),
        ("new,100,75,74,", False),
        ("base,80,70,", True),
        ("new,100,,3", True),
    ],
)
def test_missing_input_does_not_invent_zero_range(tmp_path, row, half_width):
    path = tmp_path / "observations.csv"
    columns = "half_width" if half_width else "lower,upper"
    other = (
        ("new,100,75,3" if half_width else "new,100,75,74,77")
        if row.startswith("base")
        else ("base,80,70,2" if half_width else "base,80,70,68,72")
    )
    path.write_text(f"case,value,reference,{columns}\n{row}\n{other}\n")
    report = _report(path, _declaration(half_width=half_width))
    assert report["groups"][0]["status"] == "missing-values"
    assert report["groups"][0]["result"] is None
    assert len(report["groups"][0]["members"]) == 2
    with pytest.raises(ValueError, match="unavailable"):
        _resolve(report, "difference")


@pytest.mark.parametrize(
    "row,half_width,match",
    [
        ("base,80,70,72,68", False, "lower bound"),
        ("base,80,70,71,72", False, "within"),
        ("base,80,70,68,69", False, "within"),
        ("base,80,70,-2", True, "nonnegative"),
        ("base,,70,-2", True, "nonnegative"),
        ("base,True,70,68,72", False, "Invalid numeric"),
        ("base,nan,70,68,72", False, "Nonfinite"),
        ("base,80,70,68,inf", False, "Nonfinite"),
        ("base,80,70,1e309", True, "Nonfinite"),
    ],
)
def test_invalid_side_is_rejected_even_if_other_side_missing(tmp_path, row, half_width, match):
    path = tmp_path / "observations.csv"
    other = "new,,75,3" if half_width else "new,,75,74,77"
    columns = "half_width" if half_width else "lower,upper"
    path.write_text(f"case,value,reference,{columns}\n{row}\n{other}\n")
    with pytest.raises(ValueError, match=match):
        _report(path, _declaration(half_width=half_width))


def test_nonfinite_derived_endpoint_is_rejected(tmp_path):
    path = tmp_path / "observations.csv"
    path.write_text(
        "case,value,reference,lower,upper\nbase,0,-1e308,-1e308,0\nnew,1,1e308,0,1e308\n"
    )
    with pytest.raises(ValueError, match="nonfinite result"):
        _report(path)


@pytest.mark.parametrize(
    "body",
    [
        "base,80,70,68,72\n",
        "base,80,70,68,72\nnew,100,75,74,77\nnew,100,75,74,77\n",
        "base,80,70,68,72\nbase,80,70,68,72\nnew,100,75,74,77\n",
    ],
)
def test_missing_or_duplicate_member_is_not_averaged(tmp_path, body):
    path = tmp_path / "observations.csv"
    path.write_text("case,value,reference,lower,upper\n" + body)
    with pytest.raises(ValueError, match="expected one record"):
        _report(path)


def test_exact_filter_and_groups_keep_selected_original_record_locations(tmp_path):
    path = tmp_path / "observations.csv"
    path.write_text(
        "condition,stage,case,unit,value,reference,lower,upper\n"
        "hot,old,base,s,not-numeric,70,68,72\n"
        "hot,new,new,s,100,75,74,77\n"
        "cold,new,base,s,10,11,10,12\n"
        "hot,new,base,s,80,70,68,72\n"
        "cold,new,new,s,8,10,9,11\n"
        "hot,new,other,s,0,0,-1,1\n"
    )
    report = _report(
        path, _declaration(group_by="condition", row_filters={"stage": "new"}, unit_column="unit")
    )
    assert report["rows_read"] == 5
    assert _resolve(report, "value", group="hot")["csv_records"] == [5, 3]
    assert _resolve(report, "value", group="cold")["csv_records"] == [4, 6]
    assert _resolve(report, "value", group="cold")["raw_value"] == -2
    with pytest.raises(ValueError, match="exact group"):
        _resolve(report, "value", group="HOT")
    with pytest.raises(ValueError, match="No records match"):
        _report(path, _declaration(row_filters={"stage": "NEW"}))


def test_npz_preserves_pair_array_indices_and_native_boolean_is_not_numeric(tmp_path):
    path = tmp_path / "observations.npz"
    np.savez(
        path,
        case=["new", "base"],
        value=[100, 80],
        reference=[75, 70],
        lower=[74, 68],
        upper=[77, 72],
        ignored=np.zeros((2, 2)),
    )
    report = _report(path, _declaration(source="sources/observations.npz"))
    assert _resolve(report, "value")["array_indices"] == [1, 0]
    assert report["groups"][0]["members"]["reference"]["array_index"] == 1
    np.savez(
        path,
        case=["new", "base"],
        value=[True, False],
        reference=[75, 70],
        lower=[74, 68],
        upper=[77, 72],
    )
    with pytest.raises(ValueError, match="Invalid numeric"):
        _report(path)


@pytest.mark.parametrize("field", sorted(REFERENCE_RANGE_FIELDS))
def test_scalar_source_record_and_percentage_are_not_accepted(tmp_path, field):
    path = tmp_path / "observations.csv"
    _write(path)
    report = _report(path)
    with pytest.raises(ValueError, match="scalar fields do not accept source_record"):
        _resolve(report, field, source_record=2)
    with pytest.raises(ValueError, match="percentage"):
        _resolve(report, field, percentage=True)


@pytest.mark.parametrize(
    "changes,match",
    [
        ({"reference_kind": None}, "reference_kind"),
        ({"reference_kind": "95%-confidence-interval"}, "reference_kind"),
        ({"pair_by": None}, "pair_by"),
        ({"reference": "new"}, "must differ"),
        ({"comparison": ""}, "comparison"),
        ({"units": {"value": "s"}}, "identical declared units"),
        ({"unit": "degC"}, "Celsius"),
        ({"unit": "K"}, "Declare whether K"),
        ({"quantity_kind": "unknown"}, "quantity_kind"),
        ({"unit": "s", "quantity_kind": "absolute-temperature"}, "Absolute temperature"),
        ({"unit": "s", "quantity_kind": "temperature-difference"}, "Kelvin"),
        (
            {"columns": {"value": "value", "reference": "reference", "lower": "lower"}},
            "requires value,reference",
        ),
    ],
)
def test_invalid_declarations_fail_before_reading(tmp_path, changes, match):
    with pytest.raises(ValueError, match=match):
        _report(tmp_path / "not-read.csv", _declaration(**changes))


def test_helper_signature_is_unchanged_and_pair_range_is_not_a_result_comparison_parent(tmp_path):
    assert _TABLE_DECLARATION_KEYS == set(inspect.signature(calculate_table).parameters) - {"path"}
    path = tmp_path / "observations.csv"
    _write(path)
    report = _report(path)
    ref = {"calculation_id": report["id"], "group": "all", "field": "value"}
    with pytest.raises(ValueError, match="unsupported parent operation"):
        calculate_result_comparison(
            [report],
            id="nested",
            domain=report["domain"],
            definition_source="methods.txt:L1",
            reference=ref,
            comparison={**ref, "field": "difference"},
        )
