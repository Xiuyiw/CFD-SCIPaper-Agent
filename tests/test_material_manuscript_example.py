"""Integration contracts, not sentence matching or scientific-quality certification."""

import csv
import json
import runpy
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from cfdpaper.publication.manuscript import assemble_manuscript


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def example(tmp_path):
    script = (
        Path(__file__).resolve().parents[1] / "examples/material-analysis/prepare_manuscript.py"
    )
    run = runpy.run_path(str(script))["run"]
    output = tmp_path / "example"
    docx = run(output)
    return output, docx, run


def test_binding_provenance_and_native_docx(example):
    output, docx, run = example
    generated = read(output / "analysis/section-input/writing/input.json")
    sid = generated["section_id"]
    packaged = read(output / f"workspace/sections/{sid}/input.json")
    original = {e["id"]: e["result_ref"] for e in generated["evidence"] if e.get("result_ref")}
    actual = {e["id"]: e["result_ref"] for e in packaged["evidence"] if e.get("result_ref")}
    assert original and actual == original
    assembled = read(output / "manuscript/section.json")
    assert {s["role"] for s in assembled["section_objects"].values()} == {"methods", "results"}
    assert not assembled["figures"]
    for value in assembled["resolved_values"].values():
        assert value["calculation_id"] == "wall"
        assert value["csv_records"]
        assert (output / "manuscript" / value["source"]).is_file()
    ns = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    }
    with ZipFile(docx) as archive:
        xml = ET.fromstring(archive.read("word/document.xml"))
    assert xml.findall(".//m:oMath/m:acc", ns)
    assert xml.findall(".//m:oMath/m:f", ns)
    math_paragraph = next(
        p for p in xml.findall(".//w:body/w:p", ns) if p.find("m:oMath", ns) is not None
    )
    props = math_paragraph.find("w:pPr", ns)
    assert props.find("w:ind", ns).get(f"{{{ns['w']}}}firstLineChars") == "200"
    spacing = props.find("w:spacing", ns)
    assert spacing.get(f"{{{ns['w']}}}before") == "0"
    assert spacing.get(f"{{{ns['w']}}}after") == "0"
    styles = [p.get(f"{{{ns['w']}}}val") for p in xml.findall(".//w:pStyle", ns)]
    assert "Heading1" in styles
    with pytest.raises(FileExistsError):
        run(output)


def test_methods_only_revision_keeps_results_and_original(example):
    output, _, _ = example
    original_path = output / "manuscript/section.json"
    original_bytes = original_path.read_bytes()
    before = read(original_path)
    draft_path = output / "methods-draft.json"
    draft = read(draft_path)
    draft["paragraphs"][0]["text"] += " The two regions cover the entire stipulated wall."
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    revised = assemble_manuscript(
        output / "workspace", output / "drafts.json", output / "methods-revised"
    )
    after = read(revised / "section.json")
    assert before["paragraphs"] != after["paragraphs"]

    def results_paragraphs(document):
        paragraphs = document["paragraphs"]
        start = next(i for i, p in enumerate(paragraphs) if p.get("section_id") == "area-flux")
        return paragraphs[start:]

    assert results_paragraphs(before) == results_paragraphs(after)
    assert before["resolved_values"] == after["resolved_values"]
    assert before["tables"] == after["tables"]
    assert original_path.read_bytes() == original_bytes


def test_source_update_recomputes_bindings_and_preserves_original(example):
    output, docx, _ = example
    old = output / "manuscript"
    saved = {p.relative_to(old): p.read_bytes() for p in old.rglob("*") if p.is_file()}
    docx_bytes = docx.read_bytes()
    source = output / "workspace/sections/area-flux/sources/regions.csv"
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows, fields = list(reader), reader.fieldnames
    rows[2]["rate [W]"] = "38"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        writer.writerows(rows)
    new = assemble_manuscript(output / "workspace", output / "drafts.json", output / "updated")
    before = read(old / "section.json")["resolved_values"]
    after = read(new / "section.json")["resolved_values"]
    for field, expected in (("rate", 80.0), ("mean_flux", 8.0)):
        key = next(k for k, v in after.items() if v["group"] == "Modified" and v["field"] == field)
        assert after[key]["raw_value"] == expected
        assert before[key]["raw_value"] != after[key]["raw_value"]
    assert read(old / "section.json")["tables"] != read(new / "section.json")["tables"]
    assert all((old / path).read_bytes() == content for path, content in saved.items())
    assert docx.read_bytes() == docx_bytes
