"""Report projections enter the ordinary manuscript authoring lifecycle."""

import csv
import json
import zipfile

import pytest

from cfdpaper.publication.formal_export import export_formal_manuscript
from cfdpaper.publication.manuscript import assemble_manuscript
from cfdpaper.publication.report_writing import prepare_report_writing
from cfdpaper.publication.section import _Duty


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def projection(tmp_path):
    root = tmp_path / "projection"
    records = root / "sources/records"
    records.mkdir(parents=True)
    rows = []
    for case, temperature, reference, comparison in (
        ("a", 300, 4000, 3000),
        ("b", 310, 5000, 3500),
    ):
        source = f"sources/records/{case}.json"
        write(
            root / source,
            {
                "temperature": temperature,
                "pressure": {"reference": reference, "comparison": comparison},
            },
        )
        rows.extend(
            [
                [case, "temperature", "value", temperature, "K", source, "/temperature"],
                [
                    case,
                    "pressure",
                    "reference",
                    reference / 1000,
                    "kPa",
                    source,
                    "/pressure/reference",
                ],
                [
                    case,
                    "pressure",
                    "comparison",
                    comparison / 1000,
                    "kPa",
                    source,
                    "/pressure/comparison",
                ],
            ]
        )
    source = "sources/report-values.csv"
    with (root / source).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["case_id", "quantity", "member", "value", "unit", "source", "pointer"])
        writer.writerows(rows)
    return root, {
        "source": source,
        "source_files": [source, "sources/records/a.json", "sources/records/b.json"],
        "cases": ["a", "b"],
        "quantities": [
            {
                "id": "temperature",
                "label": "Surface temperature",
                "unit": "K",
                "domain": "declared interface surface mean",
                "pointer": "/temperature",
                "quantity_kind": "absolute-temperature",
            },
            {
                "id": "pressure",
                "label": "Pressure drop",
                "unit": "Pa",
                "output_unit": "kPa",
                "domain": "declared inlet-to-outlet pressure difference",
                "reference": "/pressure/reference",
                "comparison": "/pressure/comparison",
            },
        ],
        "row_count": len(rows),
    }


def prepare(projection, tmp_path):
    root, data = projection
    return prepare_report_writing(
        root,
        data,
        tmp_path / "workspace",
        title="Synthetic report",
        question="How do the declared case metrics compare?",
        context="Synthetic software fixture, not a physical validation.",
    )


def fill_drafts(workspace):
    task = (workspace / "TASK.md").read_text(encoding="utf-8")
    math_example = json.loads(task.split("```json\n")[1].split("\n```")[0])
    for sid in ("methods", "results", "discussion"):
        path = workspace / f"sections/{sid}/draft.json"
        draft = read(path)
        text = {
            "methods": "The declared variables use the recorded operators and support domains.",
            "results": "Case a has {{value:temperature_a}} and a pressure change of "
            "{{value:pressure_a}}. The full comparison is in {{table:report_values}}.",
            "discussion": "These observed differences require a separate physical explanation.",
        }[sid]
        if sid == "methods":
            text += " The reference notation is {{math:quantity}}."
            draft["paragraphs"][0].update(math_example)
        draft["paragraphs"][0]["text"] = text
        if sid != "results":
            draft["paragraphs"][0]["evidence_ids"] = ["report_question"]
        write(path, draft)


def test_prepare_uses_three_existing_section_inputs_and_real_result_refs(projection, tmp_path):
    root, data = projection
    original = {name: (root / name).read_bytes() for name in data["source_files"]}
    workspace = prepare(projection, tmp_path)
    manifest = read(workspace / "manuscript-input.json")
    assert [item["section_id"] for item in manifest["sections"]] == [
        "methods",
        "results",
        "discussion",
    ]
    assert manifest["spine"]["central_claim_id"] == "temperature_a"
    assert all(
        entry["required_claim_ids"] == []
        for entry in manifest["spine"]["sections"]
        if entry["section_id"] != "results"
    )
    for sid in ("methods", "results", "discussion"):
        section = read(workspace / f"sections/{sid}/input.json")
        metrics = [item for item in section["evidence"] if item["kind"] == "metric"]
        assert {item["id"] for item in metrics} == {
            "temperature_a",
            "temperature_b",
            "pressure_a",
            "pressure_b",
        }
        assert all(item["result_ref"] and item["value"] is None for item in metrics)
        assert all(item["unit"] == "" and item.get("json_value_ref") is None for item in metrics)
        calculations = {item["id"]: item for item in section["table_calculations"]}
        assert calculations["temperature"]["operation"] == "scalar_select"
        assert calculations["pressure"]["operation"] == "paired_change"
        assert calculations["pressure"]["pair_by"] == "member"
        assert calculations["pressure"]["units"] == {"value": "kPa"}
        assert calculations["pressure"]["row_filters"] == {"quantity": "pressure"}
        assert all("sources/report-values.csv" in item["source"] for item in metrics)
        assert all(
            "sources/records/" in item["source"] and "#/" in item["source"] for item in metrics
        )
        for name, content in original.items():
            assert (workspace / f"sections/{sid}" / name).read_bytes() == content
        draft = read(workspace / f"sections/{sid}/draft.json")
        assert draft["paragraphs"][0]["text"] == ""
    assert read(workspace / "drafts.json") == {
        sid: f"sections/{sid}/draft.json" for sid in ("methods", "results", "discussion")
    }
    summary = read(workspace / "report-writing.json")
    assert summary["row_count"] == 6 and summary["evidence_count"] == 4
    metrics = {item["evidence_id"]: item for item in summary["metrics"]}
    assert metrics["pressure_a"]["raw_value"] == -1
    assert metrics["pressure_a"]["unit"] == "kPa"
    assert metrics["temperature_b"]["raw_value"] == 310
    assert all((root / name).read_bytes() == content for name, content in original.items())
    with pytest.raises(ValueError):
        assemble_manuscript(workspace, workspace / "drafts.json", tmp_path / "unfinished")


def test_native_table_and_host_draft_assemble_export_and_recalculate(projection, tmp_path):
    workspace = prepare(projection, tmp_path)
    template = read(workspace / "sections/results/draft-template.json")
    table = template["tables"][0]
    assert table["columns"][-1] == "Result"
    assert len(table["rows"]) == 4
    assert all(row[-1].startswith("{{value:") and row[-1].endswith("}}") for row in table["rows"])
    assert template == read(workspace / "sections/results/draft.json")
    fill_drafts(workspace)
    candidate = assemble_manuscript(workspace, workspace / "drafts.json", tmp_path / "candidate")
    result = read(candidate / "section.json")
    prose = "\n".join(paragraph.get("text", "") for paragraph in result["paragraphs"])
    assert "300.000 K" in prose
    assert "-1.000 kPa" in prose
    assert "300.000 K" in [cell for row in result["tables"][0]["rows"] for cell in row]
    formal = export_formal_manuscript(candidate, tmp_path / "report.md", profile="report")
    assert "300.000 K" in formal.read_text(encoding="utf-8")
    pytest.importorskip("docx")
    docx = export_formal_manuscript(candidate, tmp_path / "report.docx", profile="report")
    with zipfile.ZipFile(docx) as archive:
        xml = archive.read("word/document.xml").decode()
    assert "<w:tbl>" in xml and "<m:sSub>" in xml
    for sid in ("methods", "results", "discussion"):
        source = workspace / f"sections/{sid}/sources/report-values.csv"
        source.write_text(
            source.read_text(encoding="utf-8").replace(",300,K,", ",315,K,"), encoding="utf-8"
        )
    refreshed = assemble_manuscript(workspace, workspace / "drafts.json", tmp_path / "refreshed")
    assert "315.000 K" in "\n".join(
        paragraph.get("text", "") for paragraph in read(refreshed / "section.json")["paragraphs"]
    )
    assert "300.000 K" in prose
    assert "300" in (projection[0] / projection[1]["source"]).read_text(encoding="utf-8")


def test_prepare_refuses_existing_author_output(projection, tmp_path):
    workspace = prepare(projection, tmp_path)
    marker = workspace / "author-note.txt"
    marker.write_text("Keep this edit", encoding="utf-8")
    with pytest.raises(FileExistsError, match="overwrite"):
        prepare(projection, tmp_path)
    assert marker.read_text(encoding="utf-8") == "Keep this edit"


def test_research_question_remains_visible_without_forced_paragraph_citation(projection, tmp_path):
    workspace = prepare(projection, tmp_path)
    fill_drafts(workspace)
    selected = {"methods": [], "discussion": ["pressure_a"]}
    for sid, name in read(workspace / "drafts.json").items():
        path = workspace / name
        draft = read(path)
        paragraph = draft["paragraphs"][0]
        paragraph["evidence_ids"] = selected.get(
            sid, [eid for eid in paragraph["evidence_ids"] if eid != "report_question"]
        )
        write(path, draft)
    candidate = assemble_manuscript(workspace, workspace / "drafts.json", tmp_path / "candidate")
    result = read(candidate / "section.json")
    assert len(result["tables"]) == 1
    assert "How do the declared case metrics compare?" in (workspace / "TASK.md").read_text(
        encoding="utf-8"
    )
    for sid in ("methods", "results", "discussion"):
        section = read(workspace / f"sections/{sid}/input.json")
        assert any(item["id"] == "report_question" for item in section["evidence"])
    results_path = workspace / "sections/results/draft.json"
    draft = read(results_path)
    draft["paragraphs"][0]["evidence_ids"].remove("temperature_b")
    write(results_path, draft)
    with pytest.raises(ValueError, match="coverage|central claim|Required claims"):
        assemble_manuscript(workspace, workspace / "drafts.json", tmp_path / "incomplete")


def test_purpose_only_duty_keeps_explicit_evidence_and_figure_requirements():
    purpose_only = _Duty(purpose="Describe the available methods.", figure_ids=[])
    assert purpose_only.evidence_ids == []
    explicit = _Duty(
        purpose="Explain the measured contrast.", evidence_ids=["metric"], figure_ids=[]
    )
    assert explicit.evidence_ids == ["metric"]


def test_reports_without_table_rows_still_require_one_actual_results_metric(projection, tmp_path):
    for quantity in projection[1]["quantities"]:
        quantity["table"] = False
    workspace = prepare(projection, tmp_path)
    manifest = read(workspace / "manuscript-input.json")
    assert manifest["spine"]["central_claim_id"] == "temperature_a"
    contract = next(item for item in manifest["spine"]["sections"] if item["role"] == "results")
    assert contract["required_claim_ids"] == ["temperature_a"]
    for sid, name in read(workspace / "drafts.json").items():
        path = workspace / name
        draft = read(path)
        paragraph = draft["paragraphs"][0]
        paragraph["text"] = "Author method and interpretation."
        paragraph["evidence_ids"] = []
        if sid == "results":
            paragraph["text"] = "The supported value is {{value:temperature_a}}."
            paragraph["evidence_ids"] = ["temperature_a"]
        write(path, draft)
    candidate = assemble_manuscript(workspace, workspace / "drafts.json", tmp_path / "candidate")
    assert read(candidate / "section.json")["tables"] == []
    path = workspace / "sections/results/draft.json"
    draft = read(path)
    draft["paragraphs"][0]["evidence_ids"] = []
    write(path, draft)
    with pytest.raises(ValueError, match="Required claim coverage"):
        assemble_manuscript(workspace, workspace / "drafts.json", tmp_path / "incomplete")
