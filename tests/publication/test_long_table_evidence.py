"""Long tables use explicit source selections, never a hand-maintained pivot."""

import shutil

import pytest

from cfdpaper.publication.table_evidence import calculate_table, resolve_table_result


@pytest.fixture
def long_table(tmp_path):
    path = tmp_path / "metrics.csv"
    path.write_text(
        "record_id,case,metric,domain,value,unit\n"
        "note-a,a,solver_status,whole,converged,text\n"
        "p-a,a,pressure,outlet,4.345369441169341,Pa\n"
        "t-a,a,temperature,wall,310,K\n"
        "p-b,b,pressure,outlet,2.0,Pa\n"
        "p-wall,a,pressure,wall,100,Pa\n",
        encoding="utf-8",
    )
    return path


def calculate(path, **overrides):
    return calculate_table(
        path,
        **{
            "operation": "scalar_select",
            "columns": {"value": "value"},
            "units": {"value": "Pa"},
            "group_by": "case",
            "row_filters": {"metric": "pressure", "domain": "outlet"},
            "unit_column": "unit",
            **overrides,
        },
    )


def test_long_scalar_preserves_original_records_precision_and_source(long_table):
    original = long_table.read_bytes()
    report = calculate(long_table)
    assert report["rows_read"] == 2
    assert [g["csv_records"] for g in report["groups"]] == [[3], [5]]
    assert report["groups"][0]["result"]["value"] == 4.345369441169341
    assert long_table.read_bytes() == original
    resolved = resolve_table_result(
        [
            {
                "id": "p",
                "source": "sources/metrics.csv",
                "operation": "scalar_select",
                "units": {"value": "Pa"},
                **report,
            }
        ],
        calculation_id="p",
        group="a",
        field="value",
        places=2,
    )
    assert resolved["csv_records"] == [3]
    assert resolved["value"] == "4.35"


def test_long_pair_uses_original_rows(long_table):
    report = calculate(
        long_table,
        operation="paired_change",
        group_by=None,
        pair_by="case",
        reference="a",
        comparison="b",
    )
    group = report["groups"][0]
    assert group["csv_records"] == [3, 5]
    assert group["result"]["difference"] == pytest.approx(2 - 4.345369441169341)


def test_long_population_is_explicit_aggregation(long_table):
    report = calculate(long_table, operation="population", group_by=None)
    assert report["groups"][0]["result"]["count"] == 2
    assert report["groups"][0]["csv_records"] == [3, 5]


@pytest.mark.parametrize("unit", ["kPa", "", "Pa "])
def test_selected_unit_conflict_is_located_without_conversion(long_table, unit):
    long_table.write_text(long_table.read_text().replace("2.0,Pa", f"2.0,{unit}"))
    with pytest.raises(ValueError, match=r"Unit mismatch.*:5:unit"):
        calculate(long_table)


def test_no_match_and_unknown_filter_do_not_select_a_fallback(long_table):
    with pytest.raises(ValueError, match="No records match"):
        calculate(long_table, row_filters={"metric": "Pressure"})
    with pytest.raises(ValueError, match="missing columns"):
        calculate(long_table, row_filters={"unknown": "pressure"})


@pytest.mark.parametrize("operation", ["scalar_select", "paired_change"])
def test_duplicate_selected_records_are_not_averaged(long_table, operation):
    long_table.write_text(long_table.read_text() + "p-a-copy,a,pressure,outlet,5,Pa\n")
    kwargs = (
        {}
        if operation == "scalar_select"
        else {"group_by": None, "pair_by": "case", "reference": "a", "comparison": "b"}
    )
    with pytest.raises(ValueError, match=r"one record.*source records \[3, 7\]"):
        calculate(long_table, operation=operation, **kwargs)


@pytest.mark.parametrize("raw", ["not-numeric", "nan"])
def test_selected_invalid_numeric_value_keeps_original_record_location(long_table, raw):
    long_table.write_text(long_table.read_text().replace("2.0,Pa", f"{raw},Pa"))
    with pytest.raises(ValueError, match=r":5:value"):
        calculate(long_table)


@pytest.mark.parametrize("filters", [{"metric": 2}, {"": "x"}, [], "pressure"])
def test_filters_require_explicit_string_equalities(long_table, filters):
    with pytest.raises(ValueError, match="row_filters"):
        calculate(long_table, row_filters=filters)


def test_relocated_source_recomputes_without_pivot(long_table, tmp_path):
    moved = tmp_path / "relocated" / "metrics.csv"
    moved.parent.mkdir()
    shutil.copy2(long_table, moved)
    assert calculate(moved) == calculate(long_table)
    moved.write_text(moved.read_text().replace("2.0,Pa", "6.0,Pa"))
    assert calculate(moved)["groups"][1]["result"]["value"] == 6
    assert calculate(long_table)["groups"][1]["result"]["value"] == 2


def test_unit_column_requires_a_declared_value_unit(long_table):
    with pytest.raises(ValueError, match="unit_column.*value unit"):
        calculate(long_table, units=None)


def test_unfiltered_legacy_read_still_rejects_nonnumeric_values(long_table):
    with pytest.raises(ValueError):
        calculate(long_table, row_filters=None, unit_column=None)


def test_weighted_filtered_rows_keep_declared_measure_and_temperature(tmp_path):
    path = tmp_path / "weighted.csv"
    path.write_text(
        "metric,value,unit,area\nstatus,converged,text,n/a\n"
        "temperature,300,K,1\ntemperature,304,K,3\n",
        encoding="utf-8",
    )
    report = calculate_table(
        path,
        operation="weighted_population",
        columns={"value": "value", "weight": "area"},
        units={"value": "K", "weight": "m2"},
        weight_kind="area",
        quantity_kind="absolute-temperature",
        row_filters={"metric": "temperature"},
        unit_column="unit",
    )
    assert report["groups"][0]["csv_records"] == [3, 4]
    assert report["groups"][0]["result"]["weighted_mean"] == 303


def test_array_filter_retains_zero_based_original_indices(tmp_path):
    np = pytest.importorskip("numpy")
    path = tmp_path / "metrics.npz"
    np.savez(
        path,
        metric=["note", "pressure", "temperature", "pressure"],
        value=["ok", "4", "300", "2"],
        unit=["text", "Pa", "K", "Pa"],
    )
    report = calculate_table(
        path,
        operation="population",
        columns={"value": "value"},
        units={"value": "Pa"},
        row_filters={"metric": "pressure"},
        unit_column="unit",
    )
    assert report["groups"][0]["array_indices"] == [1, 3]
    assert report["groups"][0]["result"]["mean"] == 3


def test_csv_location_counts_records_not_lines_with_quoted_newline(tmp_path):
    path = tmp_path / "quoted.csv"
    path.write_text('metric,value,unit\nnote,"two\nlines",text\npressure,2,Pa\n')
    report = calculate(path, group_by=None, row_filters={"metric": "pressure"})
    assert report["groups"][0]["csv_records"] == [3]


def test_selected_missing_value_is_unavailable_not_dropped(long_table):
    long_table.write_text(long_table.read_text().replace("2.0,Pa", ",Pa"))
    group = calculate(long_table)["groups"][1]
    assert group["csv_records"] == [5]
    assert group["status"] == "missing-values"


def test_empty_unit_is_exactly_checked_for_dimensionless_metric(tmp_path):
    path = tmp_path / "ratio.csv"
    path.write_text("metric,value,unit\nratio,0.25,\n")
    report = calculate(path, group_by=None, row_filters={"metric": "ratio"}, units={"value": ""})
    assert report["groups"][0]["result"]["value"] == 0.25


def test_partition_does_not_guess_which_role_a_unit_column_describes(tmp_path):
    path = tmp_path / "partition.csv"
    path.write_text("area,rate,unit\n1,2,W\n")
    with pytest.raises(ValueError, match="unit_column.*value unit"):
        calculate_table(
            path,
            operation="partition",
            columns={"area": "area", "rate": "rate"},
            units={"area": "m2", "rate": "W"},
            unit_column="unit",
        )
