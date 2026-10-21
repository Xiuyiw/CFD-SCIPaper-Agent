"""A host gets complete compact values without duplicated full upstream reports."""

import json
from pathlib import Path

from cfdpaper.host_tools import _report_context, report_task


def test_report_context_keeps_domain_denominator_and_located_full_evidence():
    full = {
        "cases": ["A"],
        "metrics": [
            {
                "evidence_id": "rise",
                "value": "20.0",
                "unit": "%",
                "raw_value": 0.2,
                "domain": "inlet area",
                "comparison_scope": "two located reports",
                "denominator": {"evidence_id": "base", "raw_value": 100, "unit": "Pa"},
                "reference_evidence_id": "base",
                "comparison_evidence_id": "current",
                "parent_support": [
                    {
                        "role": "reference",
                        "domain": "inlet area",
                        "evidence_id": "base",
                        "original_sources": [{"source": "sources/raw.json", "pointer": "/p"}],
                    }
                ],
                "supporting_results": [{"very_long_details": "x" * 10000}],
            }
        ],
    }
    result = _report_context(full)
    row = result["metrics"][0]
    assert row["value"] == "20.0" and row["domain"] == "inlet area"
    assert row["denominator"]["evidence_id"] == "base"
    assert row["details_pointer"] == "/metrics/0"
    assert row["parent_support"][0]["evidence_id"] == "base"
    assert "supporting_results" not in row and "original_sources" not in row["parent_support"][0]
    assert full["metrics"][0]["supporting_results"][0]["very_long_details"] == "x" * 10000


def test_report_prepare_and_build_publish_same_compact_file_and_host_context(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "A.json").write_text('{"pressure": 120}', encoding="utf-8")
    question = "What does the supplied pressure report show?"
    prepared = report_task(
        tmp_path / "prepared",
        root=raw,
        title="Constructed pressure report",
        question=question,
        cases=[{"id": "A", "source": "A.json"}],
        quantities=[
            {
                "id": "pressure",
                "label": "Declared pressure",
                "unit": "Pa",
                "domain": "declared surface mean",
                "pointer": "/pressure",
            }
        ],
    )
    workspace = Path(prepared["artifacts"]["workspace"])
    full_path = Path(prepared["artifacts"]["metrics"])
    context_path = Path(prepared["artifacts"]["writing_context"])
    full = json.loads(full_path.read_text(encoding="utf-8"))
    compact = json.loads(context_path.read_text(encoding="utf-8"))
    assert compact == prepared["context"] == _report_context(full)
    assert compact["question"] == question
    assert len(context_path.read_bytes()) < len(full_path.read_bytes())
    for row in compact["metrics"]:
        index = int(row["details_pointer"].rsplit("/", 1)[1])
        assert full["metrics"][index]["evidence_id"] == row["evidence_id"]
        assert "supporting_results" not in row and "original_sources" not in row
    task = (workspace / "TASK.md").read_text(encoding="utf-8")
    assert "Read report-context.json first" in task
    assert "report-writing.json" in task
    for sid, name in json.loads((workspace / "drafts.json").read_text(encoding="utf-8")).items():
        path = workspace / name
        draft = json.loads(path.read_text(encoding="utf-8"))
        draft["paragraphs"][0]["text"] = f"Author {sid}: {{{{value:pressure_A}}}}."
        draft["paragraphs"][0]["evidence_ids"] = ["pressure_A", "report_question"]
        path.write_text(json.dumps(draft), encoding="utf-8")
    built = report_task(
        tmp_path / "built", workspace=workspace.parent, drafts=workspace / "drafts.json"
    )
    current = json.loads(Path(built["artifacts"]["writing_context"]).read_text(encoding="utf-8"))
    assert current == built["context"]
    assert current["pending_sections"] == [] and prepared["context"]["pending_sections"]
