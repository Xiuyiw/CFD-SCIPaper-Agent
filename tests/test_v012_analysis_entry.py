"""Mixed-metric source tables travel through the public analysis/writing route."""

import json
import shutil

import pytest

from cfdpaper.analysis_suggestions import compile_analysis, prepare_analysis
from cfdpaper.publication.analysis_section import _points, build_analysis_section
from cfdpaper.publication.section import assemble_section, export_section_docx, prepare_section


def _json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def long_analysis(tmp_path):
    raw = tmp_path / "original"
    raw.mkdir()
    (raw / "metrics.csv").write_text(
        "record_id,case,metric,domain,value,unit\n"
        "r1,a,status,device,converged,text\n"
        "r1,a,pressure_drop,device,4.345369441169341,Pa\n"
        "r2,b,temperature,wall,not-evaluated,K\n"
        "r2,b,pressure_drop,device,2,Pa\n"
        "r1,a,pressure_drop,wall,100,Pa\n",
        encoding="utf-8",
    )
    (raw / "method.md").write_text(
        "Synthetic device inlet-to-outlet pressure differences in Pa for cases a and b.\n"
        "Both use the same pressure definition and boundary conditions.\n"
        "Status, wall pressure and temperature rows are different diagnostics.\n",
        encoding="utf-8",
    )
    package = tmp_path / "analysis"
    prepare_analysis(raw, package, question="How does device pressure drop change?")
    base = {
        "source": "sources/metrics.csv",
        "columns": {"value": "value"},
        "units": {"value": "Pa"},
        "row_filters": {"metric": "pressure_drop", "domain": "device"},
        "unit_column": "unit",
        "domain": "Device inlet-to-outlet pressure difference",
        "definition_source": {"path": "sources/method.md", "locator": "L1-L3"},
        "comparison": {"status": "supported", "scope": "Same declared device definition"},
        "member_id": ["record_id"],
        "interpretation_limits": ["Synthetic discrete contrast"],
    }
    candidate = {
        "id": "pressure",
        "title": "Device pressure contrast",
        "question": "How does device pressure drop change?",
        "rationale": "Read the declared contrast from the original long table.",
        "presentation": "table",
        "presentation_reason": "The exact two-case contrast needs no additional plot.",
        "calculations": [
            {
                **base,
                "id": "scalar",
                "operation": "scalar_select",
                "group_by": "case",
                "expected_groups": ["a", "b"],
            },
            {
                **base,
                "id": "pair",
                "operation": "paired_change",
                "paired_selector": {"pair_by": "case", "reference": "a", "comparison": "b"},
                "expected_members": [["r1"], ["r2"]],
            },
        ],
        "interpretation_limits": ["Not an experimental validation."],
    }
    proposal = _json(package / "proposal.json", {"candidates": [candidate]})
    return raw, package, proposal


def _compile(package, output):
    return compile_analysis(package, package / "proposal.json", "pressure", output)


def test_original_long_table_runs_through_analysis_section_and_native_table(
    long_analysis, tmp_path
):
    raw, package, _ = long_analysis
    original = (raw / "metrics.csv").read_bytes()
    compiled = _compile(package, tmp_path / "compiled")
    data = _read(compiled)
    reports = _read(compiled.parent / "table-results.json")
    assert [g["csv_records"] for g in reports[0]["groups"]] == [[3], [5]]
    assert reports[1]["groups"][0]["csv_records"] == [3, 5]
    assert all(report["rows_read"] == 2 for report in reports)
    assert all(
        calc["row_filters"] == {"metric": "pressure_drop", "domain": "device"}
        and calc["unit_column"] == "unit"
        for calc in data["table_calculations"]
    )
    assert (compiled.parent / "sources/metrics.csv").read_bytes() == original
    selected = _read(compiled.parent / "selected-analysis.json")
    assert all(calc["member_id"] == ["record_id"] for calc in selected["calculations"])

    # The plotting consumer recalculates against the same exact selection.
    points = _points(data, compiled.parent)
    assert [point["csv_records"] for point in points] == [[3], [5], [3, 5]]
    assert points[0]["raw_value"] == 4.345369441169341
    assert points[2]["raw_value"] == pytest.approx(2 - 4.345369441169341)

    writing = build_analysis_section(compiled, tmp_path / "section-entry")
    # Exercise direct prepare as well as build_analysis_section's preparation call.
    prepared = prepare_section(writing / "input.json", tmp_path / "direct-writing")
    assert (prepared / "sources/metrics.csv").read_bytes() == original
    ids = [e["id"] for e in data["evidence"]]
    draft = _json(
        tmp_path / "draft.json",
        {
            "title": data["title"],
            "paragraphs": [
                {
                    "text": "The case values and their contrast are "
                    + ", ".join("{{value:" + key + "}}" for key in ids)
                    + ".",
                    "evidence_ids": ids,
                    "figure_ids": [],
                }
            ],
            "captions": {},
            "evidence_notes": [],
            "image_observations": {},
            "tables": [
                {
                    "table_id": "1",
                    "caption": "Synthetic pressure contrast",
                    "after_section_id": "pressure",
                    "columns": ["Quantity", "Value"],
                    "rows": [[key, "{{value:" + key + "}}"] for key in ids],
                    "evidence_ids": ids,
                }
            ],
        },
    )
    initial = assemble_section(prepared, draft, tmp_path / "initial")
    initial_text = (initial / "section.md").read_text(encoding="utf-8")
    assert "4.345" in initial_text and "-2.345" in initial_text

    moved = tmp_path / "relocated-writing"
    shutil.move(str(prepared), moved)
    current = moved / "sources/metrics.csv"
    current.write_text(
        current.read_text(encoding="utf-8").replace(
            "r2,b,pressure_drop,device,2,Pa", "r2,b,pressure_drop,device,6,Pa"
        ),
        encoding="utf-8",
    )
    updated = assemble_section(moved, draft, tmp_path / "updated")
    updated_text = (updated / "section.md").read_text(encoding="utf-8")
    assert "6.000" in updated_text and "1.655" in updated_text
    assert (initial / "section.md").read_text(encoding="utf-8") == initial_text
    assert (raw / "metrics.csv").read_bytes() == original
    assert _read(updated / "table-results.json")[1]["groups"][0]["csv_records"] == [3, 5]
    docx = pytest.importorskip("docx")
    document = docx.Document(export_section_docx(updated, tmp_path / "long-table.docx"))
    cells = [cell.text for table in document.tables for row in table.rows for cell in row.cells]
    assert any("1.655" in text for text in cells)
    assert not document.inline_shapes


def test_analysis_package_can_move_before_compilation(long_analysis, tmp_path):
    _, package, _ = long_analysis
    moved = tmp_path / "relocated-analysis"
    shutil.move(str(package), moved)
    compiled = _compile(moved, tmp_path / "compiled")
    assert _read(compiled.parent / "table-results.json")[0]["groups"][0]["csv_records"] == [3]


@pytest.mark.parametrize(
    "change,match",
    [
        ("zero-match", "No records match"),
        ("wrong-unit", "Unit mismatch.*:5:unit"),
        ("duplicate-member", "duplicate member"),
    ],
)
def test_invalid_selected_long_table_fails_before_output(long_analysis, tmp_path, change, match):
    _, package, proposal = long_analysis
    source = package / "sources/metrics.csv"
    if change == "zero-match":
        data = _read(proposal)
        for calc in data["candidates"][0]["calculations"]:
            calc["row_filters"]["metric"] = "absent"
            calc.pop("expected_groups", None)
        _json(proposal, data)
    else:
        text = source.read_text(encoding="utf-8")
        if change == "wrong-unit":
            text = text.replace("device,2,Pa", "device,2,kPa")
        else:
            text += "r1,a,pressure_drop,device,5,Pa\n"
        source.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        _compile(package, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()
