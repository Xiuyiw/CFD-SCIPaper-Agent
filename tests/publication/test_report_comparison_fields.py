"""Synthetic report fields retain denominator direction and both source supports."""

import copy
import json

import pytest

from cfdpaper.publication.section import assemble_section, prepare_section
from cfdpaper.publication.table_evidence import (
    calculate_declared_table,
    calculate_result_comparison,
    resolve_table_result,
)


def declaration(name, *, paired=False, unit="Pa", kind="ordinary"):
    return {
        "id": name,
        "source": f"sources/{name}.csv",
        "operation": "paired_change" if paired else "scalar_select",
        "columns": {"value": "value"},
        "units": {"value": unit},
        "domain": "Declared pressure-drop support",
        "quantity_kind": kind,
        **({"pair_by": "station", "reference": "outlet", "comparison": "inlet"} if paired else {}),
    }


def report(tmp_path, name, value, **options):
    config = declaration(name, **options)
    path = tmp_path / f"{name}.csv"
    body = (
        f"station,value\noutlet,10\ninlet,{10 + value}\n"
        if options.get("paired")
        else f"value\n{value}\n"
    )
    path.write_text(body, encoding="utf-8")
    return {**config, **calculate_declared_table(path, config)}


def reference(parent):
    return {
        "calculation_id": parent["id"],
        "group": "all",
        "field": "difference" if parent["operation"] == "paired_change" else "value",
    }


def compare(parents, *, reverse=False, **options):
    baseline, compared = parents[::-1] if reverse else parents
    return calculate_result_comparison(
        parents,
        id="contrast",
        reference=reference(baseline),
        comparison=reference(compared),
        domain=baseline["domain"],
        definition_source="sources/method.md:L1",
        **options,
    )


def resolve(parent, field, **options):
    return resolve_table_result(
        [parent], calculation_id=parent["id"], group="all", field=field, **options
    )


@pytest.mark.parametrize("paired_reference", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_pressure_difference_has_explicit_denominator_and_source_identity(
    tmp_path, paired_reference, reverse
):
    parents = [
        report(tmp_path, "reference", 100, paired=paired_reference),
        report(tmp_path, "comparison", 120, paired=True),
    ]
    original = copy.deepcopy(parents)
    comparison = compare(parents, reverse=reverse)
    expected_change = -1 / 6 if reverse else 0.2
    expected_ratio = 5 / 6 if reverse else 1.2
    change = resolve(comparison, "relative_change", percentage=True, places=4)
    assert change["raw_value"] == pytest.approx(expected_change)
    assert change["value"] == ("-16.6667" if reverse else "20.0000")
    assert change["unit"] == "%"
    ratio = resolve(comparison, "ratio", places=4)
    assert ratio["raw_value"] == pytest.approx(expected_ratio)
    assert ratio["value"] == ("0.8333" if reverse else "1.2000")
    assert ratio["unit"] == ""
    ordered = parents[::-1] if reverse else parents
    for support, parent in zip(ratio["supporting_results"], ordered, strict=True):
        assert support["operation"] == parent["operation"]
        assert support["field"] == reference(parent)["field"]
        assert support["source"] == parent["source"]
        assert support["csv_records"] == ([2, 3] if parent["operation"] == "paired_change" else [2])
    assert set(comparison["groups"][0]["result"]) == {
        "difference",
        "relative_change",
        "relative_reduction",
    }
    assert parents == original


@pytest.mark.parametrize("reverse", [False, True])
def test_paired_ratio_is_resolved_without_changing_stored_payload(tmp_path, reverse):
    parent = report(tmp_path, "pair", 20, paired=True)
    path = tmp_path / "pair.csv"
    path.write_text("station,value\noutlet,100\ninlet,120\n", encoding="utf-8")
    if reverse:
        parent["reference"], parent["comparison"] = parent["comparison"], parent["reference"]
    parent.update(calculate_declared_table(path, parent))
    original = copy.deepcopy(parent)
    result = resolve(parent, "ratio", places=4)
    assert result["raw_value"] == pytest.approx(5 / 6 if reverse else 1.2)
    assert result["unit"] == ""
    assert result["csv_records"] == ([3, 2] if reverse else [2, 3])
    assert parent == original


def test_result_ratio_uses_original_parent_values_without_subtractive_cancellation(tmp_path):
    result = compare([report(tmp_path, "a", 1e16), report(tmp_path, "b", 1)])
    original = copy.deepcopy(result)
    assert result["groups"][0]["result"]["relative_change"] == -1
    resolved = resolve(result, "ratio")
    assert resolved["raw_value"] == 1e-16
    assert [item["raw_value"] for item in resolved["supporting_results"]] == [1e16, 1]
    assert result == original


@pytest.mark.parametrize("origin,expected", [(None, None), (20, 1.5), (40, None)])
def test_result_ratio_from_absolute_temperatures_uses_the_declared_origin(
    tmp_path, origin, expected
):
    parents = [
        report(tmp_path, "a", 40, unit="degC", kind="absolute-temperature"),
        report(tmp_path, "b", 50, unit="degC", kind="absolute-temperature"),
    ]
    result = compare(parents, temperature_reference=origin)
    if expected is None:
        with pytest.raises(ValueError, match="missing or nonfinite"):
            resolve(result, "ratio")
    else:
        assert resolve(result, "ratio")["raw_value"] == expected


@pytest.mark.parametrize("operation", ["paired_change", "result_comparison"])
def test_ratio_zero_denominator_stays_unavailable(tmp_path, operation):
    if operation == "paired_change":
        parent = report(tmp_path, "pair", 3, paired=True)
        path = tmp_path / "pair.csv"
        path.write_text("station,value\noutlet,0\ninlet,3\n", encoding="utf-8")
        parent.update(calculate_declared_table(path, parent))
    else:
        parent = compare([report(tmp_path, "a", 0), report(tmp_path, "b", 120, paired=True)])
    assert parent["groups"][0]["result"]["relative_change"] is None
    with pytest.raises(ValueError, match="missing or nonfinite"):
        resolve(parent, "ratio")


@pytest.mark.parametrize("operation", ["paired_change", "result_comparison"])
def test_ratio_does_not_accept_percentage_display(tmp_path, operation):
    parents = [report(tmp_path, "a", 100), report(tmp_path, "b", 120, paired=True)]
    parent = parents[1] if operation == "paired_change" else compare(parents)
    with pytest.raises(ValueError, match="percentage"):
        resolve(parent, "ratio", percentage=True)


@pytest.mark.parametrize(
    "change,error",
    [
        ({"units": {"value": "kPa"}}, "matching unit"),
        ({"domain": "Different support"}, "domain"),
        ({"weight_kind": "area"}, "matching weight_kind"),
    ],
)
def test_scalar_pair_comparison_keeps_unit_domain_and_weight_checks(tmp_path, change, error):
    parents = [report(tmp_path, "a", 100), report(tmp_path, "b", 120, paired=True)]
    parents[1].update(change)
    with pytest.raises(ValueError, match=error):
        compare(parents)


def test_scalar_pair_comparison_keeps_observation_support_check(tmp_path):
    parents = [report(tmp_path, "a", 100), report(tmp_path, "b", 120, paired=True)]
    for parent, time in zip(parents, (10, 20), strict=True):
        parent["support"] = {
            "case_id": parent["id"],
            "association": "scalar",
            "spatial_domain": parent["domain"],
            "operator": "pressure difference",
            "time": {"kind": "fixed", "time_s": time, "origin": "start"},
            "conditions": {},
        }
    with pytest.raises(ValueError, match="physical observation times"):
        compare(parents)


def test_absolute_temperature_pair_difference_is_not_an_absolute_temperature(tmp_path):
    pair = report(tmp_path, "pair", 20, paired=True, unit="degC", kind="absolute-temperature")
    delta = report(tmp_path, "delta", 10, unit="K", kind="temperature-difference")
    result = compare([delta, pair])
    assert result["quantity_kind"] == "temperature-difference"
    assert result["units"] == {"value": "K"}
    assert result["upstream"]["comparison"]["quantity_kind"] == "temperature-difference"
    assert resolve(result, "ratio")["raw_value"] == 2
    absolute = report(tmp_path, "absolute", 10, unit="K", kind="absolute-temperature")
    with pytest.raises(ValueError, match="matching quantity_kind"):
        compare([absolute, pair])
    with pytest.raises(ValueError, match="missing or nonfinite"):
        resolve(pair, "ratio")


@pytest.mark.parametrize("origin", [None, 10, 30])
def test_absolute_temperature_ratio_retains_existing_origin_semantics(tmp_path, origin):
    pair = report(tmp_path, "pair", 20, paired=True, unit="degC", kind="absolute-temperature")
    pair["temperature_reference"] = origin
    pair.update(calculate_declared_table(tmp_path / "pair.csv", pair))
    if origin in {None, 10}:
        with pytest.raises(ValueError, match="missing or nonfinite"):
            resolve(pair, "ratio")
    else:
        # The ratio is (comparison - origin) / (reference - origin), not C/C.
        assert resolve(pair, "ratio")["raw_value"] == 0


@pytest.mark.parametrize("value", [None, True, float("inf"), float("nan")])
def test_paired_difference_parent_requires_a_finite_scalar(tmp_path, value):
    parents = [report(tmp_path, "a", 100), report(tmp_path, "b", 120, paired=True)]
    parents[1]["groups"][0]["result"]["difference"] = value
    with pytest.raises(ValueError, match="missing or nonfinite"):
        compare(parents)


def test_paired_parent_requires_both_source_records(tmp_path):
    parents = [report(tmp_path, "a", 100), report(tmp_path, "b", 120, paired=True)]
    parents[1]["groups"][0]["csv_records"].pop()
    with pytest.raises(ValueError, match="parent.*two|unsupported parent"):
        compare(parents)


def test_result_ratio_requires_both_retained_pair_records(tmp_path):
    result = compare([report(tmp_path, "a", 100), report(tmp_path, "b", 120, paired=True)])
    result["upstream"]["comparison"]["csv_records"].pop()
    with pytest.raises(ValueError, match="invalid supporting result"):
        resolve(result, "ratio")


def test_other_cross_operation_combinations_remain_rejected(tmp_path):
    parents = [report(tmp_path, "a", 100), report(tmp_path, "b", 120, paired=True)]
    parents[0]["operation"] = "population"
    parents[0]["groups"][0]["result"] = {"mean": 100}
    with pytest.raises(ValueError, match="matching operation"):
        calculate_result_comparison(
            parents,
            id="contrast",
            reference={"calculation_id": "a", "group": "all", "field": "mean"},
            comparison=reference(parents[1]),
            domain=parents[0]["domain"],
            definition_source="sources/method.md:L1",
        )


def test_section_consumes_paired_difference_parent_and_ratio_result_ref(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "a.csv").write_text("value\n100\n", encoding="utf-8")
    (sources / "b.csv").write_text("station,value\noutlet,10\ninlet,130\n", encoding="utf-8")
    (sources / "method.md").write_text(
        "Same declared pressure-drop definition.\n", encoding="utf-8"
    )
    parents = [declaration("a"), declaration("b", paired=True)]
    data = {
        "section_id": "pressure",
        "title": "Pressure response",
        "question": "How does pressure drop compare?",
        "figures": [],
        "table_calculations": parents,
        "result_comparisons": [
            {
                "id": "contrast",
                "reference": reference(parents[0]),
                "comparison": reference(parents[1]),
                "domain": parents[0]["domain"],
                "definition_source": "sources/method.md:L1",
                "comparison_scope": "B relative to A",
                "status": "supported",
            }
        ],
        "evidence": [
            {
                "id": "ratio",
                "kind": "metric",
                "text": "Comparison-to-reference pressure-drop ratio",
                "source": "sources/method.md:L1",
                "result_ref": {"calculation_id": "contrast", "group": "all", "field": "ratio"},
            }
        ],
        "duties": [
            {"purpose": "Compare pressure drop", "evidence_ids": ["ratio"], "figure_ids": []}
        ],
    }
    source = tmp_path / "input.json"
    source.write_text(json.dumps(data), encoding="utf-8")
    package = prepare_section(source, tmp_path / "package")
    draft = {
        "title": "Pressure response",
        "paragraphs": [
            {"text": "The ratio is {{value:ratio}}.", "evidence_ids": ["ratio"], "figure_ids": []}
        ],
        "captions": {},
        "evidence_notes": [],
        "image_observations": {},
    }
    draft_path = tmp_path / "draft.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    output = assemble_section(package, draft_path, tmp_path / "assembled")
    assert "The ratio is 1.200." in (output / "section.md").read_text(encoding="utf-8")
    resolved = json.loads((output / "section.json").read_text(encoding="utf-8"))["resolved_values"][
        "ratio"
    ]
    assert resolved["raw_value"] == 1.2
    assert resolved["supporting_results"][1]["csv_records"] == [2, 3]
