"""Synthetic lifecycle checks: these fixtures are not AI-produced scientific prose."""

import json
from pathlib import Path

import pytest
from PIL import Image

from cfdpaper.publication.manuscript import assemble_manuscript, prepare_manuscript


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fixture(tmp_path):
    sections, contracts, drafts = [], [], {}
    for index, sid in enumerate(("methods", "response", "transport"), 1):
        root = tmp_path / sid
        root.mkdir()
        (root / "sources").mkdir()
        (root / "sources" / "values.csv").write_text("case,value\na,1\na,3\n")
        Image.new("RGB", (60, 40), (index * 60, 20, 40)).save(root / "plot.png")
        data = {
            "section_id": sid,
            "title": sid.title(),
            "question": f"Purpose of {sid}?",
            "figures": [
                {
                    "id": "same",
                    "path": "plot.png",
                    "caption": sid,
                    "description": "Synthetic image for software testing.",
                }
            ],
            "evidence": [
                {
                    "id": "metric",
                    "kind": "metric",
                    "text": "Fixture mean",
                    "source": "values.csv",
                    "result_ref": {
                        "calculation_id": "mean",
                        "group": "a",
                        "field": "mean",
                        "places": 2,
                    },
                },
                {
                    "id": "ref",
                    "kind": "literature",
                    "text": "Shared test reference",
                    "source": "doi:synthetic-shared",
                },
                {
                    "id": "unique",
                    "kind": "literature",
                    "text": f"Reference for {sid}",
                    "source": f"doi:synthetic-{sid}",
                },
            ],
            "duties": [
                {
                    "purpose": "Describe the fixture",
                    "evidence_ids": ["metric"],
                    "figure_ids": ["same"],
                }
            ],
            "table_calculations": [
                {
                    "id": "mean",
                    "source": "sources/values.csv",
                    "operation": "population",
                    "columns": {"value": "value"},
                    "units": {"value": "K"},
                    "domain": "Synthetic rows",
                    "group_by": "case",
                }
            ],
        }
        write(root / "input.json", data)
        sections.append({"section_id": sid, "input": f"{sid}/input.json"})
        contracts.append(
            {
                "section_id": sid,
                "role": "methods" if index == 1 else "results",
                "title": sid.title(),
                "purpose": f"Assigned {sid} responsibility",
                "required_claim_ids": ["metric"],
                "required_figure_ids": ["same"],
            }
        )
        draft = {
            "title": sid.title(),
            "paragraphs": [
                {
                    "text": "Synthetic {{value:metric}}: {{figure:same}}, {{table:same}}, "
                    "{{equation:same}}, {{cite:unique}} and {{cite:ref}}. "
                    "Literal Figure 1 / Table 1 / Equation 1 / [1] / 12.3 stays. "
                    "Inline {{math:x}}.",
                    "evidence_ids": ["metric", "ref", "unique"],
                    "figure_ids": ["same"],
                    "inline_math": {
                        "x": {
                            "kind": "sub",
                            "children": [
                                {"kind": "symbol", "text": "T"},
                                {"kind": "text", "text": "{{cite:ref}}"},
                            ],
                        },
                        "unused": {"kind": "text", "text": "{{cite:unique}}"},
                    },
                }
            ],
            "captions": {"same": "Synthetic caption {{figure:same}} {{cite:ref}}"},
            "image_observations": {"same": "author-provided"},
            "evidence_notes": [f"Independent review note for {sid}"],
            "tables": [
                {
                    "table_id": "same",
                    "caption": sid + " {{cite:ref}}",
                    "columns": ["Metric", "Value"],
                    "rows": [["Mean", "{{value:metric}}"]],
                    "after_section_id": sid,
                    "evidence_ids": ["metric", "ref"],
                }
            ],
            "equations": [
                {
                    "equation_id": "same",
                    "expression": {
                        "kind": "fraction",
                        "children": [
                            {"kind": "text", "text": "{{value:metric}}"},
                            {"kind": "text", "text": "2"},
                        ],
                    },
                    "evidence_ids": ["metric"],
                }
            ],
        }
        write(root / "draft.json", draft)
        drafts[sid] = f"{sid}/draft.json"
    manifest = {
        "title": "Synthetic three-section manuscript",
        "spine": {"topic_id": "synthetic", "central_claim_id": "metric", "sections": contracts},
        "sections": sections,
        "context": "Public synthetic software fixture",
        "terms": {"mean": "equal-record arithmetic mean"},
    }
    return write(tmp_path / "input.json", manifest), write(tmp_path / "drafts.json", drafts)


def test_three_sections_portable_methods_math_numbering_and_notes(tmp_path):
    source, drafts = fixture(tmp_path)
    package = prepare_manuscript(source, tmp_path / "package")
    method = package / "sections/methods"
    assert "methods-sections.md" in (method / "TASK.md").read_text()
    reference = "skills/cfd-evidence-writing/references/methods-sections.md"
    assert (method / reference).read_bytes() == (
        Path(__file__).resolve().parents[2] / reference
    ).read_bytes()
    shared = read(method / "manuscript-context.json")
    assert len(shared["spine"]["sections"]) == 3
    assert shared["terms"]["mean"] == "equal-record arithmetic mean"
    # Original source assets are no longer needed after preparation.
    for sid in ("methods", "response", "transport"):
        (tmp_path / sid / "plot.png").unlink()
        (tmp_path / sid / "sources/values.csv").unlink()
    output = assemble_manuscript(package, drafts, tmp_path / "output")
    result, numbering = read(output / "section.json"), read(output / "numbering.json")
    assert [p["section_heading"] for p in result["paragraphs"] if "section_heading" in p] == [
        "Methods",
        "Response",
        "Transport",
    ]
    assert all("text" not in p for p in result["paragraphs"] if "section_heading" in p)
    assert [f["id"] for f in result["figures"]] == ["1", "2", "3"]
    assert [t["table_id"] for t in result["tables"]] == ["1", "2", "3"]
    assert [e["equation_id"] for e in result["equations"]] == ["1", "2", "3"]
    assert len({(output / f["path"]).read_bytes() for f in result["figures"]}) == 3
    assert len(result["references"]) == 4
    assert len(result["evidence"]) == 9
    for index, sid in enumerate(("methods", "response", "transport"), 1):
        assert result["paragraphs"][2 * index - 2]["section_id"] == sid
        assert result["section_objects"][sid] == {"tables": [str(index)], "equations": [str(index)]}
        paragraph = result["paragraphs"][2 * index - 1]
        assert f"Figure {index}, Table {index}, Equation {index}" in paragraph["text"]
        assert "Literal Figure 1 / Table 1 / Equation 1 / [1] / 12.3 stays." in paragraph["text"]
        assert paragraph["runs"][1]["math"]["kind"] == "sub"
        assert paragraph["runs"][1]["math"]["children"][1]["text"] == "[2]"
        assert numbering["sections"][sid]["cite"]["ref"] == 2
        assert (output / f"sections/{sid}/draft.json").read_bytes() == (
            tmp_path / sid / "draft.json"
        ).read_bytes()
        assert read(output / f"sections/{sid}/section.json")["figures"][0]["id"] == "same"
        assert f"note for {sid}" in (output / f"notes/{sid}.md").read_text()
    assert "Independent review note" not in (output / "manuscript.md").read_text(encoding="utf-8")
    assert "\ue000" not in (output / "section.json").read_text(encoding="utf-8")


def test_reordered_spine_rebinds_objects_and_shared_citations(tmp_path):
    source, drafts = fixture(tmp_path)
    original = prepare_manuscript(source, tmp_path / "original-package")
    original_output = assemble_manuscript(original, drafts, tmp_path / "original")
    data = read(source)
    data["spine"]["sections"].reverse()
    write(source, data)
    package = prepare_manuscript(source, tmp_path / "reordered-package")
    output = assemble_manuscript(package, drafts, tmp_path / "reordered")
    before, after = read(original_output / "numbering.json"), read(output / "numbering.json")
    assert before["sections"]["transport"]["figure"]["same"] == "3"
    assert after["sections"]["transport"]["figure"]["same"] == "1"
    assert after["sections"]["methods"]["table"]["same"] == "3"
    assert after["sections"]["methods"]["equation"]["same"] == "3"
    assert before["sections"]["transport"]["cite"]["unique"] == 4
    assert after["sections"]["transport"]["cite"]["unique"] == 1
    assert read(output / "section.json")["paragraphs"][1]["text"].startswith(
        "Synthetic 2.00 K: Figure 1, Table 1, Equation 1, [1] and [2]."
    )


def test_recomputes_current_packaged_source_and_preserves_old_output(tmp_path):
    source, drafts = fixture(tmp_path)
    package = prepare_manuscript(source, tmp_path / "package")
    old = assemble_manuscript(package, drafts, tmp_path / "old")
    old_bytes = (old / "section.json").read_bytes()
    (package / "sections/response/sources/values.csv").write_text("case,value\na,2\na,6\n")
    write(package / "sections/response/table-results.json", [])
    output = assemble_manuscript(package, drafts, tmp_path / "new")
    result = read(output / "section.json")
    assert "4.00 K" in result["paragraphs"][3]["text"]
    assert result["tables"][1]["rows"][0][1] == "4.00 K"
    assert result["equations"][1]["expression"]["children"][0]["text"] == "4.00 K"
    key = read(output / "numbering.json")["sections"]["response"]["evidence"]["metric"]
    assert result["resolved_values"][key]["raw_value"] == 4.0
    assert (output / result["resolved_values"][key]["source"]).is_file()
    assert (old / "section.json").read_bytes() == old_bytes
    with pytest.raises(FileExistsError):
        assemble_manuscript(package, drafts, old)
    with pytest.raises(FileExistsError):
        prepare_manuscript(source, package)


@pytest.mark.parametrize("change", ["duplicate", "unknown", "wrong-owner", "figure-owner"])
def test_bad_spine_or_section_identity_leaves_no_package(tmp_path, change):
    source, _ = fixture(tmp_path)
    data = read(source)
    if change == "duplicate":
        data["sections"].append(data["sections"][0])
    elif change == "unknown":
        data["sections"][0]["section_id"] = "unknown"
    elif change == "wrong-owner":
        own = read(tmp_path / "methods/input.json")
        own["evidence"][0]["id"] = "different"
        own["duties"][0]["evidence_ids"] = ["different"]
        write(tmp_path / "methods/input.json", own)
    else:
        own = read(tmp_path / "methods/input.json")
        own["figures"][0]["id"] = "different"
        own["duties"][0]["figure_ids"] = ["different"]
        write(tmp_path / "methods/input.json", own)
    write(source, data)
    with pytest.raises(ValueError):
        prepare_manuscript(source, tmp_path / "package")
    assert not (tmp_path / "package").exists()


@pytest.mark.parametrize("change", ["missing", "extra", "coverage", "table-reference", "bad-token"])
def test_bad_drafts_fail_without_partial_output(tmp_path, change):
    source, drafts = fixture(tmp_path)
    package = prepare_manuscript(source, tmp_path / "package")
    if change in {"missing", "extra"}:
        mapping = read(drafts)
        if change == "missing":
            del mapping["methods"]
        else:
            mapping["extra"] = "methods/draft.json"
        write(drafts, mapping)
    else:
        path = tmp_path / "methods/draft.json"
        draft = read(path)
        if change == "coverage":
            draft["paragraphs"][0]["evidence_ids"].remove("metric")
        elif change == "table-reference":
            draft["paragraphs"][0]["text"] = draft["paragraphs"][0]["text"].replace(
                "{{table:same}}", "table"
            )
        else:
            draft["paragraphs"][0]["text"] += " {{figure:unknown}}"
        write(path, draft)
    with pytest.raises(ValueError):
        assemble_manuscript(package, drafts, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_cross_section_objects_rebind_after_reordering(tmp_path):
    source, drafts = fixture(tmp_path)
    path = tmp_path / "response/draft.json"
    draft = read(path)
    draft["paragraphs"][0]["text"] += (
        " Defined in {{equation:methods/same}}; compare {{table:transport/same}}"
        " and {{figure:transport/same}}. Literal Equation 1 stays."
    )
    write(path, draft)
    package = prepare_manuscript(source, tmp_path / "package")
    output = assemble_manuscript(package, drafts, tmp_path / "first")
    text = read(output / "section.json")["paragraphs"][3]["text"]
    assert "Defined in Equation 1; compare Table 3 and Figure 3" in text
    assert "Literal Equation 1 stays" in text
    manifest = read(package / "manuscript-input.json")
    manifest["spine"]["sections"].reverse()
    write(package / "manuscript-input.json", manifest)
    output = assemble_manuscript(package, drafts, tmp_path / "reordered")
    text = read(output / "section.json")["paragraphs"][3]["text"]
    assert "Defined in Equation 3; compare Table 1 and Figure 1" in text
    assert "Literal Equation 1 stays" in text
    refs = read(output / "numbering.json")["sections"]["response"]["cross_references"]
    assert refs[0] == {"kind": "equation", "section_id": "methods", "id": "same", "number": "3"}
    assert "{{equation:methods/same}}" in (output / "sections/response/draft.json").read_text()


@pytest.mark.parametrize("target", ["missing/same", "methods/missing"])
def test_unknown_cross_section_object_is_not_guessed(tmp_path, target):
    source, drafts = fixture(tmp_path)
    path = tmp_path / "response/draft.json"
    draft = read(path)
    draft["paragraphs"][0]["text"] += " {{equation:" + target + "}}"
    write(path, draft)
    package = prepare_manuscript(source, tmp_path / "package")
    with pytest.raises(ValueError, match="Unknown cross-section"):
        assemble_manuscript(package, drafts, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_markdown_keeps_objects_with_their_section(tmp_path):
    source, drafts = fixture(tmp_path)
    package = prepare_manuscript(source, tmp_path / "package")
    output = assemble_manuscript(package, drafts, tmp_path / "output")
    markdown = (output / "manuscript.md").read_text(encoding="utf-8")
    assert markdown.index("   (1)") < markdown.index("## Response")
    assert markdown.index("![Figure 1]") < markdown.index("## Response")
