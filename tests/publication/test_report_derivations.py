import copy

import pytest

from cfdpaper.publication.report_derivations import compile_report_derivations
from cfdpaper.publication.table_evidence import calculate_declared_table, resolve_table_result


def inputs(tmp_path):
    data = "case,member,value,unit\nA,ref,0,Pa\nA,comp,120,Pa\nB,ref,0,Pa\nB,comp,100,Pa\n"
    path = tmp_path / "values.csv"
    path.write_text(data, encoding="utf-8")
    declaration = {
        "id": "pressure",
        "source": "sources/values.csv",
        "operation": "paired_change",
        "columns": {"value": "value"},
        "units": {"value": "Pa"},
        "domain": "same supports",
        "group_by": "case",
        "pair_by": "member",
        "reference": "ref",
        "comparison": "comp",
    }
    report = {**declaration, **calculate_declared_table(path, declaration)}
    metrics = [
        {
            "evidence_id": f"pressure_{case}",
            "case_id": case,
            "domain": "same supports",
            "original_sources": [{"source": f"sources/{case}.json", "pointer": "/pressure"}],
            **resolve_table_result(
                [report], calculation_id="pressure", group=case, field="difference"
            ),
        }
        for case in ("A", "B")
    ]
    return metrics, [report]


def derived(**changes):
    return {
        "id": "rise",
        "label": "Relative rise",
        "reference": "pressure_B",
        "comparison": "pressure_A",
        "field": "relative_change",
        "percentage": True,
        "domain": "same supports",
        "comparison_scope": "matched two-case difference",
        "definition_source": "sources/method.md:L1",
        **changes,
    }


def test_derived_percent_keeps_denominator_and_scientific_support(tmp_path):
    metrics, reports = inputs(tmp_path)
    original = copy.deepcopy((metrics, reports))
    declarations, evidence, results, rows = compile_report_derivations(
        [derived(table=True)], metrics, reports
    )
    assert results[0]["raw_value"] == pytest.approx(0.2)
    assert results[0]["label"] == "Relative rise"
    assert results[0]["value"] == "20.000" and results[0]["unit"] == "%"
    assert results[0]["denominator"] == {
        "evidence_id": "pressure_B",
        "raw_value": 100,
        "unit": "Pa",
    }
    assert results[0]["parent_support"][0]["case_id"] == "B"
    assert "source" in results[0]["parent_support"][1]["original_sources"][0]
    assert evidence[0]["evidence_role"] == "algebraic"
    assert evidence[0]["result_ref"]["percentage"] is True
    assert rows[0][-1] == "{{value:rise}}" and declarations[0]["reference"]["group"] == "B"
    assert (metrics, reports) == original


def test_reverse_percent_and_ratio_are_not_interchangeable(tmp_path):
    metrics, reports = inputs(tmp_path)
    _, _, result, _ = compile_report_derivations(
        [derived(reference="pressure_A", comparison="pressure_B")], metrics, reports
    )
    assert result[0]["raw_value"] == pytest.approx(-1 / 6)
    _, _, result, _ = compile_report_derivations(
        [derived(field="ratio", percentage=False)], metrics, reports
    )
    assert result[0]["raw_value"] == pytest.approx(1.2) and result[0]["unit"] == ""


def test_missing_parent_and_incompatible_support_are_not_silently_replaced(tmp_path):
    metrics, reports = inputs(tmp_path)
    with pytest.raises(ValueError, match="base evidence ID"):
        compile_report_derivations([derived(reference="missing")], metrics, reports)
    with pytest.raises(ValueError, match="domain"):
        compile_report_derivations([derived(domain="another surface")], metrics, reports)


def test_temperature_percentage_summary_names_the_actual_shifted_denominator(tmp_path):
    path = tmp_path / "temperature.csv"
    path.write_text("case,value\nA,320\nB,300\n", encoding="utf-8")
    declaration = {
        "id": "temperature",
        "source": "sources/temperature.csv",
        "operation": "scalar_select",
        "columns": {"value": "value"},
        "units": {"value": "K"},
        "domain": "same supports",
        "quantity_kind": "absolute-temperature",
        "group_by": "case",
    }
    report = {**declaration, **calculate_declared_table(path, declaration)}
    metrics = [
        {
            "evidence_id": f"pressure_{case}",
            "case_id": case,
            "domain": "same supports",
            "original_sources": [],
            **resolve_table_result(
                [report], calculation_id="temperature", group=case, field="value"
            ),
        }
        for case in ("A", "B")
    ]
    _, _, results, _ = compile_report_derivations(
        [derived(temperature_reference=273)], metrics, [report]
    )
    assert results[0]["denominator"]["raw_value"] == 27
    assert results[0]["denominator"]["origin"] == 273
    assert results[0]["denominator"]["source_raw_value"] == 300
