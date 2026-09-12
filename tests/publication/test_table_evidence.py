import copy
import json

import pytest

from cfdpaper.publication.table_evidence import (
    calculate_table,
    format_value,
    partition_summary,
    population_summary,
    read_numeric_table,
    resolve_table_result,
)


def test_grouped_tables_compute_each_group_and_keep_missing_groups(tmp_path):
    p = tmp_path / "flows.csv"
    p.write_text("case,mass\na,1\na,3\nb,4\nb,\n")
    result = calculate_table(p, operation="population", columns={"value": "mass"}, group_by="case")
    assert result["rows_read"] == 4
    assert result["groups"][0]["result"]["cv"] == 0.5
    assert result["groups"][0]["csv_records"] == [2, 3]
    assert result["groups"][1]["status"] == "missing-values"
    assert result["groups"][1]["result"] is None


def test_partition_table_does_not_infer_temperature_or_equal_areas(tmp_path):
    p = tmp_path / "partition.csv"
    p.write_text("A,Q\n2,8\n3,6\n")
    r = calculate_table(p, operation="partition", columns={"area": "A", "rate": "Q"})
    values = r["groups"][0]["result"]
    assert values["regional_flux"] == [4, 2]
    assert values["area"] == 5
    assert values["rate"] == 14
    assert "temperature_status" not in values


@pytest.mark.parametrize(
    "operation,columns,group",
    [
        ("average", {"value": "m"}, None),
        ("partition", {"area": "m", "rate": "m"}, None),
        ("population", {"value": "m"}, "unknown"),
    ],
)
def test_invalid_table_definition_is_not_guessed(tmp_path, operation, columns, group):
    p = tmp_path / "data.csv"
    p.write_text("m\n1\n")
    with pytest.raises(ValueError):
        calculate_table(p, operation=operation, columns=columns, group_by=group)


def test_population_cv_is_not_sample_cv_or_missing_zero():
    assert population_summary([1, 3])["cv"] == 0.5
    assert population_summary([1, None])["cv"] is None
    assert population_summary([0, 0])["cv"] is None


def test_csv_reads_all_rows_and_preserves_blanks(tmp_path):
    p = tmp_path / "source.csv"
    p.write_text("id,q\na,1\nb,\nc,3\n")
    assert [r["q"] for r in read_numeric_table(p, ["q"])] == [1, None, 3]
    p.write_text("id,q\na,nan\n")
    with pytest.raises(ValueError):
        read_numeric_table(p, ["q"])


def test_partition_identity_and_conditional_conflict():
    args = ([1, 3], [40, 60], [10, 20])
    r = partition_summary(*args, full_temperature=19)
    assert r["rate"] == 100
    assert r["regional_flux"] == [40, 20]
    assert r["shares"] == [0.4, 0.6]
    assert r["conditional_temperature"] == 17.5
    assert r["temperature_status"] == "conditional-conflict"
    assert (
        partition_summary(*args, full_temperature=19, temperature_basis="same-area-mean")[
            "temperature_status"
        ]
        == "inconsistent"
    )
    assert (
        partition_summary(*args, full_temperature=17.5)["temperature_status"]
        == "definition-missing"
    )
    assert (
        partition_summary(*args, full_temperature=17.5, temperature_basis="same-area-mean")[
            "temperature_status"
        ]
        == "consistent"
    )


def test_direct_rounding_without_double_rounding():
    value = "4.345369441169341"
    assert format_value(value, 1) == "4.3"
    assert format_value(value, 2) == "4.35"
    assert value == "4.345369441169341"
    with pytest.raises(ValueError):
        format_value(None, 1)


def test_missing_temperature_not_invented():
    assert (
        partition_summary([1], [10], [None], full_temperature=20)["conditional_temperature"] is None
    )


@pytest.fixture
def reports(tmp_path):
    definitions = [
        {
            "id": "flow",
            "source": "sources/flows.csv",
            "operation": "population",
            "columns": {"value": "mass"},
            "units": {"value": "kg/s"},
            "domain": "All outlets, equal record weights",
            "group_by": "case",
        },
        {
            "id": "heat",
            "source": "sources/regions.csv",
            "operation": "partition",
            "columns": {"area": "A", "rate": "Q"},
            "units": {"area": "cm^2", "rate": "kW"},
            "domain": "Disjoint supplied regions, heat into fluid",
            "group_by": "case",
        },
    ]
    tables = [
        "case,mass\na,1\nb,4\na,3\nb,\nzero,0\n",
        "case,A,Q\na,2,8\nb,1,5\na,3,6\nzero,1,0\n",
    ]
    output = []
    for definition, table in zip(definitions, tables, strict=True):
        path = tmp_path / definition["source"]
        path.parent.mkdir(exist_ok=True)
        path.write_text(table, encoding="utf-8")
        result = calculate_table(
            path,
            operation=definition["operation"],
            columns=definition["columns"],
            group_by=definition["group_by"],
        )
        output.append({**definition, **result})
    return json.loads(json.dumps(output))


@pytest.mark.parametrize(
    "calculation_id,field,raw_value,unit,source_record,records",
    [
        ("flow", "count", 2, "", None, [2, 4]),
        ("flow", "sum", 4, "kg/s", None, [2, 4]),
        ("flow", "mean", 2, "kg/s", None, [2, 4]),
        ("flow", "cv", 0.5, "", None, [2, 4]),
        ("heat", "area", 5, "cm^2", None, [2, 4]),
        ("heat", "rate", 14, "kW", None, [2, 4]),
        ("heat", "mean_flux", 2.8, "(kW)/(cm^2)", None, [2, 4]),
        ("heat", "regional_flux", 2, "(kW)/(cm^2)", 4, [4]),
        ("heat", "shares", 6 / 14, "", 4, [2, 4]),
    ],
)
def test_resolve_fields_units_and_actual_support(
    reports, calculation_id, field, raw_value, unit, source_record, records
):
    original = copy.deepcopy(reports)
    resolved = resolve_table_result(
        reports,
        calculation_id=calculation_id,
        group="a",
        field=field,
        source_record=source_record,
    )
    assert resolved == {
        "value": format_value(raw_value, 3),
        "unit": unit,
        "raw_value": raw_value,
        "source": "sources/flows.csv" if calculation_id == "flow" else "sources/regions.csv",
        "csv_records": records,
        "calculation_id": calculation_id,
        "group": "a",
        "field": field,
        "source_record": source_record,
    }
    assert reports == original


@pytest.mark.parametrize(
    "calculation_id,field,source_record,value,raw_value",
    [("flow", "cv", None, "50.00", 0.5), ("heat", "shares", 4, "42.86", 6 / 14)],
)
def test_percentage_is_converted_once(
    reports, calculation_id, field, source_record, value, raw_value
):
    resolved = resolve_table_result(
        reports,
        calculation_id=calculation_id,
        group="a",
        field=field,
        source_record=source_record,
        places=2,
        percentage=True,
    )
    assert (resolved["value"], resolved["unit"], resolved["raw_value"]) == (value, "%", raw_value)


def test_resolve_rounds_original_result_not_previous_display(tmp_path):
    path = tmp_path / "round.csv"
    path.write_text("q\n4.345369441169341\n", encoding="utf-8")
    report = {
        "id": "round",
        "source": "sources/round.csv",
        "operation": "population",
        "units": {"value": "W"},
        **calculate_table(path, operation="population", columns={"value": "q"}),
    }
    args = {"calculation_id": "round", "group": "all", "field": "mean"}
    assert resolve_table_result([report], **args, places=2)["value"] == "4.35"
    assert resolve_table_result([report], **args, places=1)["value"] == "4.3"
    assert resolve_table_result([report], **args, places=0)["value"] == "4"


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"calculation_id": "missing"}, "calculation ID"),
        ({"group": "A"}, "exact group"),
        ({"group": "a "}, "exact group"),
        ({"group": "b"}, "missing-values"),
        ({"group": "zero", "field": "cv"}, "missing or nonfinite"),
        ({"field": "area"}, "unsupported field"),
        ({"field": "__import__('os')"}, "unsupported field"),
        ({"field": "mean", "source_record": 2}, "scalar fields"),
        ({"percentage": True}, "only supported for cv and shares"),
        ({"field": "count", "percentage": True}, "only supported for cv and shares"),
        ({"places": -1}, "places"),
        ({"places": 13}, "places"),
        ({"places": 1.5}, "places"),
        ({"places": True}, "places"),
        ({"percentage": "false"}, "boolean"),
    ],
)
def test_invalid_scalar_reference_is_explicit(reports, overrides, message):
    args = {"calculation_id": "flow", "group": "a", "field": "mean", **overrides}
    with pytest.raises(ValueError, match=message):
        resolve_table_result(reports, **args)


@pytest.mark.parametrize("source_record", [None, 0, 1, -1, 3, 99, "4", 4.0, True])
def test_regional_reference_uses_record_in_exact_group(reports, source_record):
    with pytest.raises(ValueError, match="source_record"):
        resolve_table_result(
            reports,
            calculation_id="heat",
            group="a",
            field="regional_flux",
            source_record=source_record,
        )


def test_partition_percentage_and_undefined_share(reports):
    with pytest.raises(ValueError, match="only supported for cv and shares"):
        resolve_table_result(
            reports,
            calculation_id="heat",
            group="a",
            field="regional_flux",
            source_record=4,
            percentage=True,
        )
    with pytest.raises(ValueError, match="missing or misaligned"):
        resolve_table_result(
            reports,
            calculation_id="heat",
            group="zero",
            field="shares",
            source_record=5,
        )


@pytest.mark.parametrize("duplicate", ["id", "group"])
def test_ambiguous_reference_is_not_first_match(reports, duplicate):
    if duplicate == "id":
        reports.append(copy.deepcopy(reports[0]))
    else:
        reports[0]["groups"].append(copy.deepcopy(reports[0]["groups"][0]))
    with pytest.raises(ValueError, match="found 2"):
        resolve_table_result(reports, calculation_id="flow", group="a", field="mean")


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), "2.0", True])
def test_missing_or_invalid_result_does_not_fall_back(reports, value):
    reports[0]["groups"][0]["result"]["mean"] = value
    with pytest.raises(ValueError, match="missing or nonfinite"):
        resolve_table_result(reports, calculation_id="flow", group="a", field="mean")


def test_missing_field_units_and_regional_alignment_raise(reports):
    del reports[0]["groups"][0]["result"]["mean"]
    with pytest.raises(ValueError, match="missing result field"):
        resolve_table_result(reports, calculation_id="flow", group="a", field="mean")
    del reports[0]["units"]["value"]
    with pytest.raises(ValueError, match="missing declared role units"):
        resolve_table_result(reports, calculation_id="flow", group="a", field="sum")
    reports[1]["groups"][0]["result"]["regional_flux"].pop()
    with pytest.raises(ValueError, match="misaligned regional values"):
        resolve_table_result(
            reports,
            calculation_id="heat",
            group="a",
            field="regional_flux",
            source_record=4,
        )
