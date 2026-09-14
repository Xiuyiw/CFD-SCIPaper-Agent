"""The host supplies semantics; compilation checks the executable selected mapping."""

import json
import shutil

import pytest

from cfdpaper.analysis_suggestions import compile_analysis, prepare_analysis


@pytest.fixture
def package(tmp_path):
    root = tmp_path / "materials"
    root.mkdir()
    (root / "regions.csv").write_text(
        "case,region,area [m2],rate [W]\nA,inner,2,10\nA,outer,3,15\nB,inner,4,12\nB,outer,6,18\n",
        encoding="utf-8",
    )
    (root / "method.md").write_text(
        "Regions inner and outer are disjoint and cover the stated wall.\n"
        "area [m2] is area; rate [W] is integrated heat rate on each region.\n"
        "Cases A and B share boundary conditions; only geometry differs.\n",
        encoding="utf-8",
    )
    prepared = tmp_path / "package"
    prepare_analysis(root, prepared, question="Compare rate with flux")
    return prepared


def proposal(package):
    data = json.loads((package / "proposal-example.json").read_text(encoding="utf-8"))
    candidate = data["candidates"][0]
    calc = candidate["calculations"][0]
    calc["domain"] = "inner and outer wall regions, integrated rate and area"
    calc["comparison"] = {"status": "supported", "scope": "A and B at fixed boundary conditions"}
    calc["missing_questions"] = []
    calc["expected_members"] = [["inner"], ["outer"]]
    calc["expected_groups"] = ["A", "B"]
    return data


def compile_data(package, data, output=None):
    path = package / "proposal.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return compile_analysis(package, path, "regional-transport", output or package.parent / "run")


def test_proposal_comparison_survives_serialization_without_becoming_pair_selector(package):
    from cfdpaper.analysis_suggestions import _Candidate
    from cfdpaper.publication.section import _TableCalculation

    data = proposal(package)
    raw = data["candidates"][0]
    chosen = _Candidate.model_validate(raw)
    saved = chosen.model_dump()
    assert saved["calculations"][0]["comparison"] == raw["calculations"][0]["comparison"]
    assert _Candidate.model_validate(saved).model_dump() == saved
    output = compile_data(package, data)
    calc = json.loads(output.read_text(encoding="utf-8"))["table_calculations"][0]
    assert "comparison" not in calc
    assert _TableCalculation.model_validate(calc).model_dump() == calc


def test_portable_package_compiles_current_values(package, tmp_path):
    moved = tmp_path / "moved"
    shutil.copytree(package, moved)
    shutil.rmtree(package)
    result = compile_data(moved, proposal(moved))
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert len(payload["evidence"]) == 6
    assert all(item["result_ref"] for item in payload["evidence"])
    assert all(not item.get("value") for item in payload["evidence"])
    reports = json.loads((result.parent / "table-results.json").read_text(encoding="utf-8"))
    assert reports[0]["groups"][0]["result"]["rate"] == 25
    assert reports[0]["groups"][1]["result"]["mean_flux"] == 3
    assert (result.parent / "sources/method.md").is_file()
    source = moved / "sources/regions.csv"
    source.write_text(source.read_text().replace("A,inner,2,10", "A,inner,2,20"))
    rerun = compile_data(moved, proposal(moved), tmp_path / "rerun")
    updated = json.loads((rerun.parent / "table-results.json").read_text())
    assert updated[0]["groups"][0]["result"]["rate"] == 35


def test_host_package_and_schema_are_not_physics_inference(package):
    data = json.loads((package / "materials.json").read_text(encoding="utf-8"))
    assert data["question"] == "Compare rate with flux"
    assert "sources/regions.csv" in data["source_files"]
    schema = json.loads((package / "proposal-schema.json").read_text())
    assert schema["properties"]["candidates"]["maxItems"] == 3
    assert "$defs" in schema
    example = json.loads((package / "proposal-example.json").read_text())
    assert example["candidates"][0]["calculations"][0]["comparison"]["status"] == "unknown"


@pytest.mark.parametrize("status", ["unknown", "not-comparable"])
def test_selected_unqualified_comparison_rejected(package, status):
    data = proposal(package)
    data["candidates"][0]["calculations"][0]["comparison"]["status"] = status
    with pytest.raises(ValueError, match=status):
        compile_data(package, data)


def test_unknown_unrelated_candidate_does_not_block(package):
    data = proposal(package)
    data["candidates"].append({"id": "later", "missing_questions": ["Need wall domain"]})
    assert compile_data(package, data).is_file()


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("domain", "", "domain"),
        ("units", {"area": "", "rate": "W"}, "explicit units"),
        ("units", {"area": "mm2", "rate": "W"}, "conflicts"),
        ("columns", {"area": "area", "rate": "rate [W]"}, "missing columns"),
        ("definition_source", {"path": "sources/method.md", "locator": "L99"}, "outside"),
        ("definition_source", {"path": "../method.md", "locator": "L1"}, "relative"),
        ("expected_members", [["inner"], ["outer"], ["missing"]], "missing or unexpected"),
        ("expected_groups", ["A", "B", "C"], "expected groups"),
    ],
)
def test_definition_and_mapping_failures(package, field, value, match):
    data = proposal(package)
    data["candidates"][0]["calculations"][0][field] = value
    with pytest.raises(ValueError, match=match):
        compile_data(package, data)


@pytest.mark.parametrize(
    "row,match",
    [
        ("A,inner,2,10\n", "duplicate member"),
        ("A,,2,10\n", "missing group/member"),
        ("A,extra,2,\n", "missing or unexpected"),
    ],
)
def test_records_not_silently_summed(package, row, match):
    source = package / "sources/regions.csv"
    source.write_text(source.read_text() + row)
    with pytest.raises(ValueError, match=match):
        compile_data(package, proposal(package))


@pytest.mark.parametrize("value,match", [("", "missing numeric"), ("nan", "Nonfinite")])
def test_missing_numeric_and_nonfinite_rejected(package, value, match):
    source = package / "sources/regions.csv"
    source.write_text(source.read_text().replace("A,inner,2,10", f"A,inner,2,{value}"))
    with pytest.raises(ValueError, match=match):
        compile_data(package, proposal(package))


def test_explicit_metrics_keep_choice_small(package):
    data = proposal(package)
    candidate = data["candidates"][0]
    candidate["metrics"] = [
        {
            "id": "A-flux",
            "text": "Mean flux on the declared wall in case A",
            "result_ref": {"calculation_id": "transport", "group": "A", "field": "mean_flux"},
        }
    ]
    candidate["figure_plan"] = {
        "metric_ids": ["A-flux"],
        "title": "Wall flux",
        "y_label": "Mean flux [W/m2]",
        "x_label": "Configuration",
        "category_labels": {"A-flux": "Reference configuration"},
    }
    payload = json.loads(compile_data(package, data).read_text())
    assert len(payload["evidence"]) == 1
    assert payload["figure_plan"]["metric_ids"] == ["A-flux"]
    assert payload["figure_plan"]["x_label"] == "Configuration"
    assert payload["figure_plan"]["category_labels"] == {"A-flux": "Reference configuration"}


def test_no_candidates_reports_gaps(package):
    with pytest.raises(ValueError, match="Need an explicit statistical domain"):
        compile_data(package, {"candidates": [], "gaps": ["Need an explicit statistical domain"]})


def test_refuses_to_overwrite_output(package):
    compile_data(package, proposal(package))
    with pytest.raises(FileExistsError):
        compile_data(package, proposal(package))


def test_renamed_population_columns_and_zero_mean(package):
    source = package / "sources/regions.csv"
    source.write_text("experiment,probe,zeta\nA,p1,-2\nA,p2,2\nB,p1,2\nB,p2,4\n")
    (package / "sources/method.md").write_text(
        "zeta is a pressure difference in Pa at equally weighted probes.\n"
        "The fixed probe set p1,p2 is shared across experiments A and B.\n"
        "No area or temporal weighting is implied.\n"
    )
    data = proposal(package)
    calc = data["candidates"][0]["calculations"][0]
    calc.update(
        operation="population",
        columns={"value": "zeta"},
        units={"value": "Pa"},
        group_by="experiment",
        member_id=["probe"],
        expected_members=[["p1"], ["p2"]],
        domain="Equal-observation population of probes p1 and p2",
    )
    result = compile_data(package, data)
    payload = json.loads(result.read_text())
    refs = [item["result_ref"] for item in payload["evidence"]]
    assert [(ref["group"], ref["field"]) for ref in refs] == [
        ("A", "mean"),
        ("B", "mean"),
        ("B", "cv"),
    ]
    report = json.loads((result.parent / "table-results.json").read_text())[0]
    assert report["groups"][0]["result"]["cv"] is None
    assert report["groups"][1]["result"]["mean"] == 3


def test_duplicate_calculation_and_metric_ids_rejected(package):
    data = proposal(package)
    calc = data["candidates"][0]["calculations"][0]
    data["candidates"][0]["calculations"].append(calc.copy())
    with pytest.raises(ValueError, match="Calculation IDs"):
        compile_data(package, data)
    data = proposal(package)
    metric = {
        "id": "same",
        "text": "Rate",
        "result_ref": {"calculation_id": "transport", "group": "A", "field": "rate"},
    }
    data["candidates"][0]["metrics"] = [metric, metric]
    with pytest.raises(ValueError, match="Metric IDs"):
        compile_data(package, data)


def test_existing_figure_and_located_supporting_evidence_propagate(package):
    from PIL import Image

    Image.new("RGB", (40, 30), "white").save(package / "sources/field.png")
    data = proposal(package)
    candidate = data["candidates"][0]
    candidate["figures"] = [
        {
            "id": "field",
            "path": "sources/field.png",
            "caption": "Author-supplied field.",
            "description": "Synthetic blank image for transport testing, not a field observation.",
        }
    ]
    candidate["supporting_evidence"] = [
        {
            "id": "image-note",
            "text": "Synthetic image has a white background.",
            "kind": "observation",
            "source": "sources/field.png",
        },
        {
            "id": "scope-note",
            "text": "Regional flux depends on both rate and area.",
            "kind": "interpretation",
            "source": "sources/method.md:L1-L2",
        },
    ]
    result = compile_data(package, data)
    payload = json.loads(result.read_text())
    assert payload["figures"][0]["id"] == "field"
    assert (result.parent / payload["figures"][0]["path"]).is_file()
    assert "sources/field.png" in payload["source_files"]
    assert [item["id"] for item in payload["evidence"]][-2:] == ["image-note", "scope-note"]
    assert payload["evidence"][-1]["source"] == "sources/method.md:L1-L2"


def test_supporting_manual_metric_rejected(package):
    data = proposal(package)
    data["candidates"][0]["supporting_evidence"] = [
        {
            "id": "manual",
            "text": "Manual rate",
            "kind": "metric",
            "value": "25",
            "unit": "W",
            "source": "sources/method.md:L1",
        }
    ]
    with pytest.raises(ValueError, match="cannot supply metrics"):
        compile_data(package, data)


@pytest.mark.parametrize(
    "source", ["author supplied", "sources/missing.md:L1", "sources/method.md"]
)
def test_unlocated_supporting_evidence_rejected(package, source):
    data = proposal(package)
    data["candidates"][0]["supporting_evidence"] = [
        {
            "id": "observation",
            "text": "Reported observation",
            "kind": "observation",
            "source": source,
        }
    ]
    with pytest.raises(ValueError):
        compile_data(package, data)


def test_group_whitespace_preserved_for_expected_groups_and_result_refs(package):
    source = package / "sources/regions.csv"
    source.write_text(source.read_text().replace("\nA,", "\n A ,"))
    data = proposal(package)
    with pytest.raises(ValueError, match="expected groups"):
        compile_data(package, data)
    data["candidates"][0]["calculations"][0]["expected_groups"] = [" A ", "B"]
    result = compile_data(package, data)
    payload = json.loads(result.read_text())
    assert payload["evidence"][0]["result_ref"]["group"] == " A "
    report = json.loads((result.parent / "table-results.json").read_text())[0]
    assert report["groups"][0]["group"] == " A "
    assert report["groups"][0]["result"]["rate"] == 25


@pytest.mark.parametrize(
    "labels,match",
    [
        ({"unknown": "Reference"}, "unknown metric"),
        ({"transport-1-rate": " "}, "must not be blank"),
    ],
)
def test_figure_category_labels_must_reference_metrics_and_be_nonblank(package, labels, match):
    data = proposal(package)
    data["candidates"][0]["figure_plan"] = {
        "metric_ids": ["transport-1-rate"],
        "title": "Transport",
        "y_label": "Rate [W]",
        "category_labels": labels,
    }
    with pytest.raises(ValueError, match=match):
        compile_data(package, data)
