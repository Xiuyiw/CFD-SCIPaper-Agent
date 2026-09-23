import copy

import numpy as np
import pytest

from cfdpaper.publication.table_evidence import (
    calculate_result_comparison,
    calculate_table,
    resolve_table_result,
)


def _report(tmp_path, name, values, *, operation="population", units=None, **kwargs):
    path = tmp_path / f"{name}.csv"
    columns = {"value": "v"}
    units = units or {"value": "W"}
    if operation == "weighted_population":
        columns["weight"] = "w"
        path.write_text("v,w\n" + "\n".join(f"{v},{w}" for v, w in values))
    elif operation == "partition":
        columns = {"area": "a", "rate": "q"}
        path.write_text("a,q\n" + "\n".join(f"{a},{q}" for a, q in values))
    else:
        path.write_text("v\n" + "\n".join(str(v) for v in values))
    return {
        "id": name,
        "source": f"sources/{name}.csv",
        "operation": operation,
        "columns": columns,
        "units": units,
        "domain": "heated wall",
        "definition_source": f"sources/{name}-methods.txt:L1-L3",
        **kwargs,
        **calculate_table(path, operation=operation, columns=columns, units=units, **kwargs),
    }


def _comparison(reports, *, field="mean", **kwargs):
    return calculate_result_comparison(
        reports,
        id="contrast",
        reference={"calculation_id": "a", "group": "all", "field": field},
        comparison={"calculation_id": "b", "group": "all", "field": field},
        domain="heated wall",
        definition_source="sources/comparison.txt:L1-L3",
        **kwargs,
    )


def test_comparison_uses_raw_values_and_independent_source_records(tmp_path):
    reports = [_report(tmp_path, "a", [4.345369441169341]), _report(tmp_path, "b", [5.67891])]
    before = copy.deepcopy(reports)
    report = _comparison(reports)
    delta = 5.67891 - 4.345369441169341
    assert report["groups"][0]["result"] == {
        "difference": delta,
        "relative_change": delta / 4.345369441169341,
        "relative_reduction": -delta / 4.345369441169341,
    }
    resolved = resolve_table_result(
        [*reports, report], calculation_id="contrast", group="all", field="difference", places=8
    )
    assert resolved["raw_value"] == delta
    assert resolved["value"] == "1.33354056"
    assert resolved["unit"] == "W"
    assert "source" not in report and "csv_records" not in report["groups"][0]
    assert "source" not in resolved and "csv_records" not in resolved
    assert [item["source"] for item in resolved["supporting_results"]] == [
        "sources/a.csv",
        "sources/b.csv",
    ]
    assert [item["csv_records"] for item in resolved["supporting_results"]] == [[2], [2]]
    assert reports == before
    percentage = resolve_table_result(
        [report],
        calculation_id="contrast",
        group="all",
        field="relative_reduction",
        places=2,
        percentage=True,
    )
    assert percentage["unit"] == "%"
    assert percentage["raw_value"] == -delta / 4.345369441169341


@pytest.mark.parametrize(
    "operation,field,values,units,extra,expected",
    [
        ("population", "sum", ([1, 3], [3, 5]), {"value": "W"}, {}, 4),
        ("scalar_select", "value", ([2], [5]), {"value": "W"}, {}, 3),
        (
            "weighted_population",
            "weighted_mean",
            ([(1, 1), (3, 3)], [(2, 1), (6, 3)]),
            {"value": "W", "weight": "m2"},
            {"weight_kind": "area"},
            2.5,
        ),
        (
            "weighted_population",
            "weighted_std",
            ([(1, 1), (3, 1)], [(2, 1), (6, 1)]),
            {"value": "W", "weight": "m2"},
            {"weight_kind": "area"},
            1,
        ),
        (
            "weighted_population",
            "weight_sum",
            ([(1, 1), (3, 1)], [(2, 1), (6, 3)]),
            {"value": "W", "weight": "m2"},
            {"weight_kind": "area"},
            2,
        ),
        ("partition", "area", ([(1, 2)], [(3, 12)]), {"area": "m2", "rate": "W"}, {}, 2),
        ("partition", "rate", ([(1, 2)], [(3, 12)]), {"area": "m2", "rate": "W"}, {}, 10),
        ("partition", "mean_flux", ([(1, 2)], [(3, 12)]), {"area": "m2", "rate": "W"}, {}, 2),
    ],
)
def test_supported_scalar_fields(tmp_path, operation, field, values, units, extra, expected):
    reports = [
        _report(tmp_path, name, value, operation=operation, units=units, **extra)
        for name, value in zip(("a", "b"), values, strict=True)
    ]
    assert _comparison(reports, field=field)["groups"][0]["result"]["difference"] == expected


def test_npz_parent_keeps_array_indices(tmp_path):
    reports = []
    for name, values in (("a", [1, 3]), ("b", [3, 5])):
        path = tmp_path / f"{name}.npz"
        np.savez(path, q=np.array(values))
        reports.append(
            {
                "id": name,
                "source": f"sources/{name}.npz",
                "operation": "population",
                "domain": "heated wall",
                "units": {"value": "W"},
                **calculate_table(path, operation="population", columns={"value": "q"}),
            }
        )
    result = resolve_table_result(
        [_comparison(reports)], calculation_id="contrast", group="all", field="difference"
    )
    assert result["raw_value"] == 2
    for item in result["supporting_results"]:
        assert item["array_indices"] == [0, 1]
        assert "csv_records" not in item


@pytest.mark.parametrize(
    "key,value,error",
    [
        ("domain", "fluid volume", "domain"),
        ("operation", "scalar_select", "unsupported"),
        ("weight_kind", "area", "weight_kind"),
        ("units", {"value": "kW"}, "unit"),
        ("quantity_kind", "temperature-difference", "Kelvin"),
    ],
)
def test_incompatible_definitions_are_rejected(tmp_path, key, value, error):
    reports = [_report(tmp_path, "a", [2]), _report(tmp_path, "b", [4])]
    reports[1][key] = value
    with pytest.raises(ValueError, match=error):
        _comparison(reports)


@pytest.mark.parametrize("field", ["cv", "count", "regional_flux", "shares", "difference"])
def test_derived_or_array_fields_cannot_be_parents(tmp_path, field):
    reports = [_report(tmp_path, "a", [2]), _report(tmp_path, "b", [4])]
    with pytest.raises(ValueError, match="unsupported"):
        _comparison(reports, field=field)


def test_parent_references_are_shallow_and_distinct(tmp_path):
    reports = [_report(tmp_path, "a", [2]), _report(tmp_path, "b", [4])]
    derived = _comparison(reports)
    derived["id"] = "a"
    with pytest.raises(ValueError, match="unsupported"):
        _comparison([derived, reports[1]])
    ref = {"calculation_id": "a", "group": "all", "field": "mean"}
    base = {"id": "contrast", "domain": "heated wall", "definition_source": "methods:L1-L2"}
    with pytest.raises(ValueError, match="must differ"):
        calculate_result_comparison(reports, reference=ref, comparison=ref, **base)
    for addition in ({"places": 2}, {"source_record": 2}, {"percentage": True}):
        with pytest.raises(ValueError, match="require only"):
            calculate_result_comparison(
                reports, reference=ref, comparison={**ref, **addition}, **base
            )


@pytest.mark.parametrize("missing", ["calculation", "group", "value", "source", "records"])
def test_missing_parent_evidence_is_an_error(tmp_path, missing):
    reports = [_report(tmp_path, "a", [2]), _report(tmp_path, "b", [4])]
    if missing == "calculation":
        reports.pop()
    elif missing == "group":
        reports[1]["groups"] = []
    elif missing == "value":
        reports[1]["groups"][0]["result"]["mean"] = None
    elif missing == "source":
        reports[1].pop("source")
    else:
        reports[1]["groups"][0].pop("csv_records")
    with pytest.raises(ValueError):
        _comparison(reports)


@pytest.mark.parametrize("origin,relative", [(None, None), (20, 0.5), (40, None)])
def test_absolute_temperature_difference_and_explicit_origin(tmp_path, origin, relative):
    reports = [
        _report(
            tmp_path, name, [value], units={"value": "degC"}, quantity_kind="absolute-temperature"
        )
        for name, value in (("a", 40), ("b", 50))
    ]
    report = _comparison(reports, temperature_reference=origin)
    assert report["quantity_kind"] == "temperature-difference"
    assert report["units"] == {"value": "K"}
    assert report["groups"][0]["result"]["difference"] == 10
    assert report["groups"][0]["result"]["relative_change"] == relative
    assert (
        resolve_table_result([report], calculation_id="contrast", group="all", field="difference")[
            "unit"
        ]
        == "K"
    )
    if relative is None:
        with pytest.raises(ValueError, match="missing"):
            resolve_table_result(
                [report], calculation_id="contrast", group="all", field="relative_change"
            )


def test_temperature_standard_deviation_and_measure_have_nonabsolute_semantics(tmp_path):
    reports = [
        _report(
            tmp_path,
            name,
            values,
            operation="weighted_population",
            units={"value": "degC", "weight": "m2"},
            weight_kind="area",
            quantity_kind="absolute-temperature",
        )
        for name, values in (("a", [(20, 1), (22, 1)]), ("b", [(20, 2), (24, 2)]))
    ]
    sd = _comparison(reports, field="weighted_std")
    assert sd["quantity_kind"] == "temperature-difference"
    assert sd["units"] == {"value": "K"}
    assert sd["groups"][0]["result"]["relative_change"] == 1
    measure = _comparison(reports, field="weight_sum")
    assert measure["quantity_kind"] == "ordinary"
    assert measure["units"] == {"value": "m2"}
    assert measure["groups"][0]["result"]["relative_change"] == 1


def test_zero_denominator_remains_missing(tmp_path):
    report = _comparison([_report(tmp_path, "a", [0]), _report(tmp_path, "b", [4])])
    assert report["groups"][0]["result"] == {
        "difference": 4,
        "relative_change": None,
        "relative_reduction": None,
    }


@pytest.mark.parametrize("origin", [True, float("inf"), float("nan"), "20"])
def test_invalid_temperature_origin_is_rejected(tmp_path, origin):
    reports = [
        _report(tmp_path, name, [value], units={"value": "K"}, quantity_kind="absolute-temperature")
        for name, value in (("a", 300), ("b", 310))
    ]
    with pytest.raises(ValueError, match="finite absolute-temperature origin"):
        _comparison(reports, temperature_reference=origin)


def test_nonfinite_parent_is_rejected(tmp_path):
    reports = [_report(tmp_path, "a", [2]), _report(tmp_path, "b", [4])]
    reports[1]["groups"][0]["result"]["mean"] = float("inf")
    with pytest.raises(ValueError, match="nonfinite"):
        _comparison(reports)


def test_relative_overflow_is_rejected(tmp_path):
    reports = [_report(tmp_path, "a", [1e-308]), _report(tmp_path, "b", [10])]
    with pytest.raises(ValueError, match="nonfinite result"):
        _comparison(reports)


def test_paired_change_cannot_be_a_parent(tmp_path):
    reports = [_report(tmp_path, "a", [2]), _report(tmp_path, "b", [4])]
    for report in reports:
        report["operation"] = "paired_change"
        report["groups"][0]["result"] = {"difference": 2}
    with pytest.raises(ValueError, match="unsupported parent"):
        _comparison(reports, field="difference")


def test_two_groups_in_one_calculation_are_distinct_parents(tmp_path):
    report = _report(tmp_path, "a", [2])
    report["groups"].append(
        {"group": "other", "status": "computed", "csv_records": [3], "result": {"mean": 5}}
    )
    result = calculate_result_comparison(
        [report],
        id="contrast",
        reference={"calculation_id": "a", "group": "all", "field": "mean"},
        comparison={"calculation_id": "a", "group": "other", "field": "mean"},
        domain="heated wall",
        definition_source="sources/methods.txt:L1-L3",
    )
    assert result["groups"][0]["result"]["difference"] == 3
    assert result["upstream"]["reference"]["csv_records"] == [2]
    assert result["upstream"]["comparison"]["csv_records"] == [3]


def test_result_resolver_requires_both_real_supports(tmp_path):
    report = _comparison([_report(tmp_path, "a", [2]), _report(tmp_path, "b", [4])])
    report["upstream"]["comparison"].pop("csv_records")
    with pytest.raises(ValueError, match="invalid supporting result"):
        resolve_table_result([report], calculation_id="contrast", group="all", field="difference")
