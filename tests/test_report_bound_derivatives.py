"""Derived percentages, source parameters and native formulas share report refresh."""

import json
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest

from cfdpaper.host_tools import report_task


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    Path(path).write_text(json.dumps(value), encoding="utf-8")


def prepare(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    for case, pressure in (("A", 120), ("B", 144)):
        write(raw / f"{case}.json", {"inlet": pressure, "outlet": 0})
        write(raw / f"{case}-setup.json", {"intensity": 0.06})
    write(raw / "reference.json", {"readings": [100, 120]})
    (raw / "method.md").write_text(
        "Same defined inlet/outlet supports; approximate reference.\n", encoding="utf-8"
    )
    return report_task(
        tmp_path / "prepared",
        root=raw,
        title="Bound comparison",
        question="What changes?",
        cases=[
            {
                "id": case,
                "source": f"{case}.json",
                "sources": {"setup": f"{case}-setup.json", "reference": "reference.json"},
            }
            for case in ("A", "B")
        ],
        quantities=[
            {
                "id": "drop",
                "label": "Native pressure difference",
                "unit": "Pa",
                "domain": "pressure comparison",
                "reference": "/outlet",
                "comparison": "/inlet",
            },
            {
                "id": "reference",
                "label": "Approximate reference",
                "unit": "Pa",
                "domain": "pressure comparison",
                "source_key": "reference",
                "pointer": {"A": "/readings/0", "B": "/readings/1"},
            },
            {
                "id": "intensity",
                "label": "Prescribed turbulence intensity",
                "unit": "",
                "domain": "inlet setting",
                "source_key": "setup",
                "pointer": "/intensity",
                "table": False,
            },
        ],
        derived=[
            {
                "id": "error_A",
                "label": "Relative excess over the reference",
                "reference": "reference_A",
                "comparison": "drop_A",
                "field": "relative_change",
                "percentage": True,
                "places": 2,
                "domain": "pressure comparison",
                "comparison_scope": "Numerical contrast only; reference operator unknown",
                "definition_source": "method.md:L1",
            },
            {
                "id": "ratio_A",
                "label": "Native/reference ratio",
                "reference": "reference_A",
                "comparison": "drop_A",
                "field": "ratio",
                "places": 3,
                "domain": "pressure comparison",
                "comparison_scope": "Numerical contrast only",
                "definition_source": "method.md:L1",
            },
        ],
        formulas={
            "re": {
                "source": "method.md#Re",
                "expression": {
                    "kind": "fraction",
                    "children": [
                        {"kind": "symbol", "text": "ρUD"},
                        {"kind": "symbol", "text": "μ"},
                    ],
                },
            }
        },
    )


def fill(workspace):
    for sid, name in read(workspace / "drafts.json").items():
        path = workspace / name
        draft = read(path)
        p = draft["paragraphs"][0]
        if sid == "methods":
            p.update(
                text="Author method: prescribed I={{value:intensity_A}}, with Re={{math:re}}.",
                evidence_ids=["report_question", "intensity_A"],
            )
        elif sid == "discussion":
            p.update(
                text="At the declared support, native value exceeds reference "
                "by {{value:error_A}}; "
                "the native/reference ratio is {{value:ratio_A}}. Author interpretation retained.",
                evidence_ids=["report_question", "error_A", "ratio_A"],
            )
        else:
            p["text"] = (
                "The native difference is {{value:drop_A}}; the bound comparison "
                "is in {{table:report_values}}."
            )
        write(path, draft)


def test_real_report_chain_refreshes_denominator_parameters_and_native_math(tmp_path):
    prepared = Path(prepare(tmp_path)["artifacts"]["workspace"]).parent
    summary = read(prepared / "workspace/report-writing.json")
    excess = next(m for m in summary["metrics"] if m["evidence_id"] == "error_A")
    assert excess["value"] == "20.00" and excess["unit"] == "%"
    assert excess["denominator"]["evidence_id"] == "reference_A"
    assert excess["parent_support"][0]["domain"] == "pressure comparison"
    assert "operator unknown" in excess["comparison_scope"]
    fill(prepared / "workspace")
    before = (prepared / "workspace/sections/methods/draft.json").read_bytes()
    built = report_task(
        tmp_path / "first", workspace=prepared, drafts=prepared / "workspace/drafts.json"
    )
    original_md = Path(built["artifacts"]["manuscript"]).read_text(encoding="utf-8")
    assert "20.00 %" in original_md and "1.200" in original_md and "0.060" in original_md
    with ZipFile(built["artifacts"]["docx"]) as z:
        assert b"<m:f>" in z.read("word/document.xml")
    assert (prepared / "workspace/sections/methods/draft.json").read_bytes() == before
    moved = tmp_path / "moved"
    shutil.move(tmp_path / "first", moved)
    write(moved / "projection/sources/records/A/reference.json", {"readings": [80, 120]})
    write(moved / "projection/sources/records/A/setup.json", {"intensity": 0.09})
    current = report_task(
        tmp_path / "current", workspace=moved, drafts=moved / "workspace/drafts.json"
    )
    markdown = Path(current["artifacts"]["manuscript"]).read_text(encoding="utf-8")
    assert "50.00 %" in markdown and "1.500" in markdown and "0.090" in markdown
    assert "20.00 %" not in markdown and "Author interpretation retained" in markdown
    assert read(tmp_path / "raw/reference.json")["readings"][0] == 100


def test_inlet_relation_cannot_be_compared_as_a_different_support(tmp_path):
    result = prepare(tmp_path)
    root = Path(result["artifacts"]["recipe"]).parent
    recipe = read(root / "report.json")
    recipe["derived"][0]["domain"] = "another unsupported surface"
    write(root / "report.json", recipe)
    with pytest.raises(ValueError, match="domain"):
        report_task(tmp_path / "invalid", workspace=root)
    assert not (tmp_path / "invalid").exists()
