"""Public analysis selection, source binding and model-comparison boundaries."""

import csv
import json
import math
from copy import deepcopy

import pytest
from typer.testing import CliRunner

from cfdpaper.analysis_suggestions import compile_analysis
from cfdpaper.cli import app


def proposal():
    definition = {"path": "sources/method.md", "locator": "L1-L2"}
    calculation = {
        "id": "thermal",
        "source": "sources/faces.csv",
        "operation": "activated_response_mean",
        "group_by": "batch",
        "columns": {"concentration": "mix [mol/m3]", "temperature": "temp [K]", "area": "a [m2]"},
        "units": {"concentration": "mol/m3", "temperature": "K", "area": "m2"},
        "domain": "Selected tile faces",
        "response_model": {
            "member": "tile",
            "prefactor": 2,
            "concentration_ref": 4,
            "concentration_power": 2,
            "activation_K": 240,
            "output_power": 0.5,
            "reference_unit": "mol/m3",
            "concentration_basis": "moles per actual mixture volume",
        },
        "member_id": ["tile"],
        "expected_members": [["x"], ["y"]],
        "expected_groups": ["A", "B"],
        "row_filters": {"region": "selected"},
        "comparison": {"status": "supported", "scope": "Same tile set and scoring rule"},
        "definition_source": definition,
        "interpretation_limits": ["The model score is dimensionless."],
    }
    comparison = {
        "id": "change",
        "domain": calculation["domain"],
        "status": "supported",
        "definition_source": "sources/method.md:L1-L2",
        "comparison_scope": "Same selected faces and prescribed law",
        **{
            role: {"calculation_id": "thermal", "group": group, "field": "weighted_mean"}
            for role, group in (("reference", "A"), ("comparison", "B"))
        },
    }
    return {
        "candidates": [
            {
                "id": "scores",
                "question": "How do the selected batches compare?",
                "rationale": "Evaluate heterogeneous member states before averaging.",
                "calculations": [calculation],
                "result_comparisons": [comparison],
                "interpretation_limits": ["These are model responses, not measured outcomes."],
            }
        ]
    }


@pytest.fixture
def package(tmp_path):
    source = tmp_path / "study"
    source.mkdir()
    (source / "faces.csv").write_text(
        "batch,tile,mix [mol/m3],temp [K],a [m2],region\n"
        "A,x,1,240,4,selected\nB,x,2,240,4,selected\n"
        "A,y,bad,bad,bad,unselected\n"
        "A,y,3,120,2,selected\nB,y,6,120,2,selected\n",
        encoding="utf-8",
    )
    (source / "method.md").write_text(
        "Selected tile areas share one basis and one response law.\n"
        "The model transforms each member before it is averaged.\n",
        encoding="utf-8",
    )
    folder = tmp_path / "package"
    run = CliRunner().invoke(
        app, ["plan", str(source), "--artifact", "analysis", "--output", str(folder)]
    )
    assert run.exit_code == 0, run.output
    return folder


def test_activated_response_reaches_plot_and_writing_with_source_rows(tmp_path, package):
    data = proposal()
    path = tmp_path / "proposal.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    output = tmp_path / "result"
    run = CliRunner().invoke(
        app,
        [
            "plan",
            str(tmp_path / "study"),
            "--artifact",
            "analysis",
            "--package",
            str(package),
            "--proposal",
            str(path),
            "--select",
            "scores",
            "--output",
            str(output),
        ],
    )
    assert run.exit_code == 0, run.output
    writing = output / "section-input/writing"
    report, comparison = json.loads((writing / "table-results.json").read_text())
    mean = (4 * math.sqrt(2) * 0.25 * math.exp(-0.5) + 2 * math.sqrt(2) * 0.75 * math.exp(-1)) / 6
    assert report["groups"][0]["result"] == pytest.approx(
        {"area": 6, "count": 2, "weighted_mean": mean}
    )
    assert report["groups"][1]["result"]["weighted_mean"] == pytest.approx(2 * mean)
    assert comparison["groups"][0]["result"]["relative_change"] == pytest.approx(1.0)
    assert comparison["upstream"]["reference"]["csv_records"] == [2, 5]
    assert comparison["upstream"]["comparison"]["csv_records"] == [3, 6]
    assert comparison["upstream"]["reference"]["unit"] == "1"
    rendered = output / "section-input/figures"
    with (rendered / "analysis-1-source-data.csv").open(encoding="utf-8") as stream:
        points = list(csv.DictReader(stream))
    assert [float(point["raw_value"]) for point in points] == pytest.approx([mean, 2 * mean])
    assert (rendered / "analysis-1.svg").is_file()
    assert (writing / "sources/method.md").is_file()
    section = json.loads((writing / "input.json").read_text())
    assert [entry["result_ref"]["field"] for entry in section["evidence"]] == [
        "weighted_mean",
        "weighted_mean",
        "difference",
    ]
    assert section["table_calculations"][0]["response_model"]["activation_K"] == 240


@pytest.mark.parametrize(
    "change,error",
    [
        ("cross-model", "same calculation"),
        ("units", "same supported concentration unit"),
        ("member", "member_id must select"),
        ("blank-basis", "must not be blank"),
        ("dimensional-output", "output_unit"),
        ("missing-group", "requires group_by"),
        ("negative-area", "area"),
    ],
)
def test_invalid_activated_declarations_do_not_emit_output(package, tmp_path, change, error):
    data = proposal()
    candidate = data["candidates"][0]
    calc = candidate["calculations"][0]
    if change == "cross-model":
        second = deepcopy(calc)
        second["id"] = "alternative"
        second["response_model"]["prefactor"] = 3
        candidate["calculations"].append(second)
        candidate["result_comparisons"][0]["comparison"]["calculation_id"] = second["id"]
    elif change == "units":
        calc["response_model"]["reference_unit"] = "ppmv"
    elif change == "member":
        calc["response_model"]["member"] = "other"
    elif change == "blank-basis":
        calc["response_model"]["concentration_basis"] = " "
    elif change == "dimensional-output":
        calc["response_model"]["output_unit"] = "W"
    elif change == "missing-group":
        del calc["group_by"]
    else:
        table = package / "sources/faces.csv"
        table.write_text(table.read_text().replace("1,240,4", "1,240,-4"), encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        compile_analysis(package, data, "scores", tmp_path / "blocked")
    assert not (tmp_path / "blocked").exists()
