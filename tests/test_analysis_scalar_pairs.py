"""Public proposal-to-writing path for synthetic scalar and paired source records."""

import json
import shutil

import pytest

from cfdpaper.analysis_suggestions import _Candidate, compile_analysis, prepare_analysis
from cfdpaper.publication.analysis_section import _points, build_analysis_section
from cfdpaper.publication.section import assemble_section


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


@pytest.fixture
def scalar_package(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "values.csv").write_text(
        "case,configuration,record,temperature [K],pressure [Pa]\n"
        "A,new,a-new,310,8\nB,base,b-base,320,20\n"
        "A,base,a-base,300,10\nB,new,b-new,315,18\n",
        encoding="utf-8",
    )
    (raw / "method.md").write_text(
        "Synthetic temperature in K and pressure in Pa at one defined wall location.\n"
        "Base and new configurations share the stated boundary conditions within each case.\n",
        encoding="utf-8",
    )
    package = tmp_path / "package"
    prepare_analysis(raw, package)
    return package


def candidate(operation="paired_change"):
    calc = {
        "id": "contrast",
        "source": "sources/values.csv",
        "operation": operation,
        "columns": {"value": "temperature [K]"},
        "units": {"value": "K"},
        "quantity_kind": "absolute-temperature",
        "domain": "Declared wall location",
        "group_by": "case",
        "member_id": ["record"],
        "definition_source": {"path": "sources/method.md", "locator": "L1-L2"},
        "comparison": {"status": "supported", "scope": "Fixed boundaries within each case"},
        "interpretation_limits": ["Synthetic values do not validate a physical mechanism"],
    }
    if operation == "paired_change":
        calc["paired_selector"] = {
            "pair_by": "configuration",
            "reference": "base",
            "comparison": "new",
        }
    else:
        calc.update(
            group_by="record",
            columns={"value": "pressure [Pa]"},
            units={"value": "Pa"},
            quantity_kind="ordinary",
        )
    return {
        "id": "wall",
        "question": "How do the declared values differ?",
        "rationale": "Compare source records without a host-side adapter.",
        "presentation": "table",
        "calculations": [calc],
        "interpretation_limits": ["Synthetic test only"],
    }


def compile_candidate(package, chosen, output):
    return compile_analysis(
        package, write(package / "proposal.json", {"candidates": [chosen]}), "wall", output
    )


def test_generated_schema_and_guidance_expose_scalar_pair_operators(scalar_package):
    fields = read(scalar_package / "proposal-schema.json")["$defs"]["_Calculation"]["properties"]
    assert {"scalar_select", "paired_change"} <= set(fields["operation"]["enum"])
    assert "paired_selector" in fields
    assert "temperature_reference" in fields
    task = (scalar_package / "host-task.md").read_text(encoding="utf-8")
    assert "paired_selector" in task and "scalar_select" in task


def test_scalar_selection_keeps_record_identity_and_auto_metrics(scalar_package, tmp_path):
    compiled = compile_candidate(scalar_package, candidate("scalar_select"), tmp_path / "out")
    points = _points(read(compiled), compiled.parent)
    assert [(p["group"], p["raw_value"], p["csv_records"]) for p in points] == [
        ("a-new", 8, [2]),
        ("b-base", 20, [3]),
        ("a-base", 10, [4]),
        ("b-new", 18, [5]),
    ]


def test_grouped_temperature_pairs_keep_semantics_and_selected_source_order(
    scalar_package, tmp_path
):
    chosen = candidate()
    saved = _Candidate.model_validate(chosen).model_dump()
    assert saved["calculations"][0]["comparison"] == chosen["calculations"][0]["comparison"]
    assert (
        saved["calculations"][0]["paired_selector"] == chosen["calculations"][0]["paired_selector"]
    )
    assert _Candidate.model_validate(saved).model_dump() == saved
    compiled = compile_candidate(scalar_package, chosen, tmp_path / "out")
    data = read(compiled)
    calc = data["table_calculations"][0]
    assert calc["comparison"] == "new" and calc["reference"] == "base"
    assert calc["quantity_kind"] == "absolute-temperature"
    points = _points(data, compiled.parent)
    assert [(p["group"], p["raw_value"], p["unit"], p["csv_records"]) for p in points] == [
        ("A", 10, "K", [4, 2]),
        ("B", -5, "K", [3, 5]),
    ]
    report = read(compiled.parent / "table-results.json")[0]
    assert all(g["result"]["relative_change"] is None for g in report["groups"])


@pytest.mark.parametrize("with_reference", [False, True])
def test_absolute_temperature_percent_needs_reference(scalar_package, tmp_path, with_reference):
    chosen = candidate()
    chosen["metrics"] = [
        {
            "id": "relative",
            "text": "Relative change from defined thermal reference",
            "result_ref": {
                "calculation_id": "contrast",
                "group": "A",
                "field": "relative_change",
                "percentage": True,
            },
        }
    ]
    if with_reference:
        chosen["calculations"][0]["temperature_reference"] = 290
        compiled = compile_candidate(scalar_package, chosen, tmp_path / "out")
        points = _points(read(compiled), compiled.parent)
        assert points[0]["raw_value"] == 1
        assert points[0]["unit"] == "%"
    else:
        with pytest.raises(ValueError, match="missing or nonfinite"):
            compile_candidate(scalar_package, chosen, tmp_path / "out")


@pytest.mark.parametrize("problem", ["missing", "duplicate"])
def test_pair_requires_exactly_one_record_per_selector(scalar_package, tmp_path, problem):
    source = scalar_package / "sources/values.csv"
    text = source.read_text(encoding="utf-8")
    if problem == "missing":
        text = text.replace("A,base,a-base,300,10\n", "")
    else:
        text += "A,base,another-record,301,11\n"
    source.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="expected one record"):
        compile_candidate(scalar_package, candidate(), tmp_path / "out")


@pytest.mark.parametrize("operation", ["population", "scalar_select"])
def test_pair_selector_is_rejected_on_other_operations(operation):
    chosen = candidate()
    chosen["calculations"][0]["operation"] = operation
    with pytest.raises(ValueError, match="paired_change"):
        _Candidate.model_validate(chosen)


@pytest.mark.parametrize("with_reference", [False, True])
def test_temperature_scalar_metadata_survives_result_comparison_and_build(
    scalar_package, tmp_path, with_reference
):
    chosen = candidate("scalar_select")
    chosen["calculations"][0].update(
        columns={"value": "temperature [K]"},
        units={"value": "K"},
        quantity_kind="absolute-temperature",
    )
    comparison = {
        "id": "change",
        "reference": {"calculation_id": "contrast", "group": "a-base", "field": "value"},
        "comparison": {"calculation_id": "contrast", "group": "a-new", "field": "value"},
        "domain": "Declared wall location",
        "definition_source": "sources/method.md:L1-L2",
        "comparison_scope": "Fixed boundaries within case A",
        "status": "supported",
    }
    if with_reference:
        comparison["temperature_reference"] = 290
    chosen["result_comparisons"] = [comparison]
    chosen["metrics"] = [
        {
            "id": "delta",
            "text": "Signed temperature contrast",
            "result_ref": {"calculation_id": "change", "group": "all", "field": "difference"},
        }
    ]
    compiled = compile_candidate(scalar_package, chosen, tmp_path / "compiled")
    assert read(compiled)["table_calculations"][0]["quantity_kind"] == "absolute-temperature"
    report = read(compiled.parent / "table-results.json")[-1]
    assert report["groups"][0]["result"]["relative_change"] == (1 if with_reference else None)
    writing = build_analysis_section(compiled, tmp_path / "writing")
    draft = write(
        tmp_path / "draft.json",
        {
            "title": "Scalar contrast",
            "paragraphs": [
                {
                    "text": "The temperature change is {{value:delta}}.",
                    "evidence_ids": ["delta"],
                    "figure_ids": [],
                }
            ],
            "captions": {},
            "image_observations": {},
            "evidence_notes": [],
        },
    )
    result = assemble_section(writing, draft, tmp_path / "result")
    resolved = read(result / "section.json")["resolved_values"]["delta"]
    assert resolved["unit"] == "K" and resolved["raw_value"] == 10
    assert [p["csv_records"] for p in resolved["supporting_results"]] == [[4], [2]]


def test_ordinary_scalar_serialization_preserves_legacy_payload():
    from cfdpaper.publication.section import _TableCalculation

    calc = _Candidate.model_validate(candidate("scalar_select")).calculations[0]
    assert "paired_selector" not in calc.model_dump()
    table = calc.table_calculation().model_dump()
    assert "quantity_kind" not in table and "temperature_reference" not in table
    assert _TableCalculation.model_validate(table).model_dump() == table


def test_pair_source_move_change_build_and_assemble(scalar_package, tmp_path):
    moved = tmp_path / "moved"
    shutil.move(scalar_package, moved)
    chosen = candidate()
    chosen["metrics"] = [
        {
            "id": "delta",
            "text": "Signed temperature change in case A",
            "result_ref": {"calculation_id": "contrast", "group": "A", "field": "difference"},
        }
    ]
    compiled = compile_candidate(moved, chosen, tmp_path / "compiled")
    writing = build_analysis_section(compiled, tmp_path / "writing")
    draft = write(
        tmp_path / "draft.json",
        {
            "title": "Wall change",
            "paragraphs": [
                {
                    "text": "The signed change is {{value:delta}}.",
                    "evidence_ids": ["delta"],
                    "figure_ids": [],
                }
            ],
            "captions": {},
            "image_observations": {},
            "evidence_notes": [],
            "tables": [
                {
                    "table_id": "changes",
                    "caption": "Declared change",
                    "columns": ["Quantity", "Change"],
                    "rows": [["Temperature", "{{value:delta}}"]],
                    "after_section_id": "wall",
                    "evidence_ids": ["delta"],
                }
            ],
        },
    )
    first = assemble_section(writing, draft, tmp_path / "first")
    assert (first / "section.md").read_text(encoding="utf-8").count("10.000 K") == 2
    relocated = tmp_path / "relocated-writing"
    shutil.move(writing, relocated)
    source = relocated / "sources/values.csv"
    source.write_text(
        source.read_text(encoding="utf-8").replace("a-new,310", "a-new,295"), encoding="utf-8"
    )
    updated = assemble_section(relocated, draft, tmp_path / "updated")
    assert (updated / "section.md").read_text(encoding="utf-8").count("-5.000 K") == 2
    resolved = read(updated / "section.json")["resolved_values"]["delta"]
    assert resolved["csv_records"] == [4, 2] and resolved["raw_value"] == -5
