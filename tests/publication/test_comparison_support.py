"""Comparison support has to change a scientific use, not just a status label."""

import copy

import pytest

from cfdpaper.publication.comparison_support import compare_observation_support


def support(case, time):
    return {
        "case_id": case,
        "association": "face",
        "spatial_domain": "heated surface",
        "operator": "area mean",
        "time": time,
        "conditions": {"power": {"value": 800.0, "unit": "W"}},
    }


def test_same_clock_time_and_shared_conditions():
    left = support("A", {"kind": "fixed", "time_s": 840.0, "origin": "heater start"})
    right = support("B", {"kind": "fixed", "time_s": 840.0, "origin": "heater start"})
    result = compare_observation_support(left, right, fixed_conditions=["power"])
    assert result["status"] == "compatible"
    assert result["purpose"] == "same-state"
    assert result["reference"]["case_id"] == "A"


def test_own_event_cannot_be_used_as_equal_exposure():
    left = support(
        "A",
        {
            "kind": "own-event",
            "event": "surface rate",
            "offset_s": -2,
            "time_s": 879.1235,
            "origin": "heater start",
        },
    )
    right = support(
        "B",
        {
            "kind": "own-event",
            "event": "surface rate",
            "offset_s": -2,
            "time_s": 1080.1767,
            "origin": "heater start",
        },
    )
    result = compare_observation_support(left, right)
    assert result["status"] == "not-comparable"
    assert any("time" in item for item in result["conflicts"])
    allowed = compare_observation_support(left, right, purpose="event-relative")
    assert allowed["status"] == "compatible"
    assert allowed["reference"]["time"]["time_s"] != allowed["comparison"]["time"]["time_s"]


def test_missing_condition_not_inferred_and_different_design_variables_allowed():
    left = support("A", {"kind": "steady"})
    right = support("B", {"kind": "steady"})
    right["conditions"]["structure"] = {"value": "changed", "unit": ""}
    assert (
        compare_observation_support(left, right, fixed_conditions=["power"])["status"]
        == "compatible"
    )
    result = compare_observation_support(left, right, fixed_conditions=["inlet"])
    assert result["status"] == "unknown"
    assert result["missing"]
    right["conditions"]["power"]["value"] = 900.0
    assert (
        compare_observation_support(left, right, fixed_conditions=["power"])["status"]
        == "not-comparable"
    )


def test_native_event_and_saved_threshold_are_different_supports():
    left = support("A", {"kind": "native-event", "event": "rate 4", "origin": "start"})
    right = support("B", {"kind": "sampled-event", "event": "temperature 550", "origin": "start"})
    result = compare_observation_support(left, right, purpose="event-timing")
    assert result["status"] == "not-comparable"


def test_common_window_must_have_same_origin_and_endpoints():
    left = support("A", {"kind": "window", "window_s": [800, 840], "origin": "start"})
    right = copy.deepcopy(left)
    right["time"]["window_s"] = [800, 844]
    assert compare_observation_support(left, right)["status"] == "not-comparable"


def test_support_unknown_or_malformed_does_not_create_approval():
    assert compare_observation_support(None, None)["status"] == "unknown"
    with pytest.raises(ValueError, match="purpose"):
        compare_observation_support({}, {}, purpose="causally proven")


def test_actual_scalar_comparison_rejects_wrong_time_and_returns_shared_support(tmp_path):
    from cfdpaper.publication.table_evidence import (
        calculate_declared_table,
        calculate_result_comparison,
    )

    path = tmp_path / "states.csv"
    path.write_text("value\n500\n", encoding="utf-8")
    declarations = []
    for case, time in (("A", 840), ("B", 844)):
        declarations.append(
            {
                "id": case,
                "source": "sources/states.csv",
                "operation": "scalar_select",
                "columns": {"value": "value"},
                "units": {"value": "K"},
                "quantity_kind": "absolute-temperature",
                "domain": "heated surface",
                "support": support(
                    case, {"kind": "fixed", "time_s": time, "origin": "heater start"}
                ),
            }
        )
    reports = [{**d, **calculate_declared_table(path, d)} for d in declarations]
    arguments = {
        "id": "contrast",
        "domain": "heated surface",
        "definition_source": "sources/method.md:L1",
        "reference": {"calculation_id": "A", "group": "all", "field": "value"},
        "comparison": {"calculation_id": "B", "group": "all", "field": "value"},
        "fixed_conditions": ["power"],
        "support_purpose": "same-state",
    }
    with pytest.raises(ValueError, match="different physical observation times"):
        calculate_result_comparison(reports, **arguments)
    reports[1]["support"]["time"]["time_s"] = 840
    result = calculate_result_comparison(reports, **arguments)
    assert result["comparison_support"]["status"] == "compatible"
    assert result["groups"][0]["result"]["difference"] == 0
