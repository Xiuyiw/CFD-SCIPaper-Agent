import importlib
import json
import sys
import zipfile

import pytest
from PIL import Image


def api():
    try:
        return importlib.import_module("cfdpaper.publication.section")
    except ModuleNotFoundError:
        pytest.fail("section lifecycle API is not implemented")


def test_case_insensitive_figure_ids_cannot_overwrite_assets(tmp_path):
    path, data = fixture_input(tmp_path)
    data["figures"][1]["id"] = "F1"
    data["duties"][0]["figure_ids"] = ["f1", "F1"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="case-insensitive"):
        api().prepare_section(path, tmp_path / "package")
    assert not (tmp_path / "package").exists()


def fixture_input(tmp_path):
    Image.new("RGB", (100, 50), "white").save(tmp_path / "plot.png")
    value = {
        "section_id": "s1",
        "title": "Thermal response",
        "question": "What changes?",
        "figures": [
            {
                "id": f"f{i}",
                "path": "plot.png",
                "caption": f"Caption {i}",
                "description": "Author describes hotter core.",
            }
            for i in (1, 2)
        ],
        "evidence": [
            {
                "id": "e1",
                "kind": "metric",
                "text": "Measured temperature",
                "source": "data.csv row 2, T",
                "value": "1.2300e3",
                "unit": "K",
            },
            {"id": "l1", "kind": "literature", "text": "Prior work", "source": "doi:example"},
        ],
        "duties": [
            {"purpose": "Compare figures", "evidence_ids": ["e1"], "figure_ids": ["f1", "f2"]}
        ],
    }
    path = tmp_path / "source.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path, value


def draft(tmp_path):
    data = {
        "title": "Thermal response",
        "paragraphs": [
            {
                "text": "The temperature is {{value:e1}} in {{figure:f1}} and {{figure:f2}}. "
                "Recirculation may contribute, consistent with {{cite:l1}}.",
                "evidence_ids": ["e1", "l1"],
                "figure_ids": ["f1", "f2"],
            }
        ],
        "captions": {"f1": "First response", "f2": "Second response"},
        "evidence_notes": ["Review the heat-source normalization."],
        "image_observations": {"f1": "viewed", "f2": "author-provided"},
    }
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data


def test_portable_multi_figure_lifecycle(tmp_path):
    source, _ = fixture_input(tmp_path)
    module = api()
    package = module.prepare_section(source, tmp_path / "package")
    dpath, _ = draft(tmp_path)
    source.unlink()
    (tmp_path / "plot.png").unlink()
    section = module.assemble_section(package, dpath, tmp_path / "section")
    md = (section / "section.md").read_text(encoding="utf-8")
    assert "1.2300e3 K" in md
    assert "Figure f1" in md and "Figure f2" in md and "[1]" in md
    assert "Recirculation may contribute" in md
    assert "normalization" not in md
    assert "normalization" in (section / "evidence-notes.md").read_text()
    assert (section / "review-packet" / "input.json").is_file()
    assert (section / "review-packet" / "draft.json").is_file()
    assert (section / "review-packet" / "section.md").is_file()
    assert (section / "review-packet" / "review-prompt.md").is_file()
    result = json.loads((section / "section.json").read_text())
    assert result["evidence"][0]["source"] == "data.csv row 2, T"


@pytest.mark.parametrize(
    "change", ["unknown", "malformed", "undeclared", "coverage", "caption", "observation"]
)
def test_draft_validation_leaves_no_output(tmp_path, change):
    module = api()
    source, _ = fixture_input(tmp_path)
    package = module.prepare_section(source, tmp_path / "package")
    path, data = draft(tmp_path)
    if change == "unknown":
        data["paragraphs"][0]["text"] += " {{value:missing}}"
    elif change == "malformed":
        data["paragraphs"][0]["text"] += " {{value e1}}"
    elif change == "undeclared":
        data["paragraphs"][0]["evidence_ids"] = ["e1"]
    elif change == "coverage":
        data["paragraphs"][0]["figure_ids"] = ["f1"]
        data["paragraphs"][0]["text"] = "{{value:e1}} {{figure:f1}}"
    elif change == "caption":
        del data["captions"]["f2"]
    else:
        del data["image_observations"]["f2"]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        module.assemble_section(package, path, tmp_path / "section")
    assert not (tmp_path / "section").exists()


@pytest.mark.parametrize("change", ["duplicate", "unknown", "corrupt"])
def test_input_validation(tmp_path, change):
    module = api()
    path, data = fixture_input(tmp_path)
    if change == "duplicate":
        data["evidence"].append(data["evidence"][0])
    elif change == "unknown":
        data["duties"][0]["evidence_ids"] = ["missing"]
    else:
        (tmp_path / "plot.png").write_text("not an image")
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        module.prepare_section(path, tmp_path / "package")
    assert not (tmp_path / "package").exists()


def test_refuse_overwrite_and_review_is_separate(tmp_path):
    module = api()
    path, _ = fixture_input(tmp_path)
    package = module.prepare_section(path, tmp_path / "package")
    with pytest.raises(FileExistsError):
        module.prepare_section(path, package)
    dpath, _ = draft(tmp_path)
    section = module.assemble_section(package, dpath, tmp_path / "section")
    before = (section / "section.md").read_bytes()
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps(
            {
                "suggestions": [
                    {
                        "target": "paragraph 1",
                        "comment": "Check mechanism",
                        "recommendation": "Qualify",
                    }
                ]
            }
        )
    )
    output = module.import_section_review(section, review, tmp_path / "suggestions.json")
    assert "suggestions" in json.loads(output.read_text())
    assert "approval" not in output.read_text().lower()
    assert (section / "section.md").read_bytes() == before
    with pytest.raises(FileExistsError):
        module.import_section_review(section, review, output)
    with pytest.raises(FileExistsError):
        module.assemble_section(package, dpath, section)


def test_real_docx_editable_text_and_images(tmp_path):
    pytest.importorskip("docx")
    module = api()
    path, _ = fixture_input(tmp_path)
    package = module.prepare_section(path, tmp_path / "package")
    dpath, _ = draft(tmp_path)
    section = module.assemble_section(package, dpath, tmp_path / "section")
    output = module.export_section_docx(section, tmp_path / "section.docx")
    with zipfile.ZipFile(output) as archive:
        xml = archive.read("word/document.xml").decode()
        assert "1.2300e3 K" in xml and "First response" in xml
        assert "normalization" not in xml
        assert xml.count("<wp:inline") == 2
        assert any(name.startswith("word/media/") for name in archive.namelist())
    with pytest.raises(FileExistsError):
        module.export_section_docx(section, output)


def test_missing_optional_docx_is_actionable(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "docx", None)
    with pytest.raises(RuntimeError, match=r"cfd-paper-agent\[docs\]"):
        api().export_section_docx(tmp_path, tmp_path / "missing.docx")
    assert not (tmp_path / "missing.docx").exists()


@pytest.mark.parametrize("value", ["NaN", "inf", "-Infinity", "not numeric"])
def test_metric_value_must_be_finite(tmp_path, value):
    source, data = fixture_input(tmp_path)
    data["evidence"][0]["value"] = value
    source.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="finite"):
        api().prepare_section(source, tmp_path / "package")


def test_blank_required_text_rejected(tmp_path):
    source, data = fixture_input(tmp_path)
    data["title"] = "   "
    source.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        api().prepare_section(source, tmp_path / "package")


def test_docx_suffix_required(tmp_path):
    with pytest.raises(ValueError, match="docx"):
        api().export_section_docx(tmp_path, tmp_path / "wrong.txt")


def test_independent_outputs_preserve_author_draft(tmp_path):
    source, _ = fixture_input(tmp_path)
    module = api()
    package = module.prepare_section(source, tmp_path / "package")
    path, _ = draft(tmp_path)
    before = path.read_bytes()
    for name in ("version-1", "version-2"):
        assert module.assemble_section(package, path, tmp_path / name).is_dir()
    assert path.read_bytes() == before


def test_tiff_is_preserved_and_embedded(tmp_path):
    pytest.importorskip("docx")
    source, data = fixture_input(tmp_path)
    Image.new("RGB", (30, 60), "gray").save(tmp_path / "original.tiff")
    data["figures"][0]["path"] = "original.tiff"
    source.write_text(json.dumps(data))
    module = api()
    package = module.prepare_section(source, tmp_path / "package")
    assert (package / "figures" / "f1.tiff").read_bytes() == (
        tmp_path / "original.tiff"
    ).read_bytes()
    dpath, _ = draft(tmp_path)
    section = module.assemble_section(package, dpath, tmp_path / "section")
    output = module.export_section_docx(section, tmp_path / "tiff.docx")
    with zipfile.ZipFile(output) as archive:
        assert any(name.endswith(".tiff") for name in archive.namelist())


@pytest.mark.parametrize(
    "review",
    [
        {"approval": True, "suggestions": []},
        {"suggestions": "approved"},
        {"suggestions": [{"target": "p1", "comment": "", "recommendation": "fix"}]},
    ],
)
def test_invalid_reviews_are_not_stored(tmp_path, review):
    module = api()
    source, _ = fixture_input(tmp_path)
    package = module.prepare_section(source, tmp_path / "package")
    dpath, _ = draft(tmp_path)
    section = module.assemble_section(package, dpath, tmp_path / "section")
    rpath = tmp_path / "review.json"
    rpath.write_text(json.dumps(review))
    with pytest.raises(ValueError):
        module.import_section_review(section, rpath, tmp_path / "stored.json")
    assert not (tmp_path / "stored.json").exists()


def test_explicit_source_files_and_observation_notes_survive_packaging(tmp_path):
    source, data = fixture_input(tmp_path)
    (tmp_path / "sources").mkdir()
    table = tmp_path / "sources" / "values.csv"
    table.write_text("x\n1\n")
    data["source_files"] = ["sources/values.csv"]
    source.write_text(json.dumps(data))
    package = api().prepare_section(source, tmp_path / "package")
    table.unlink()
    path, content = draft(tmp_path)
    content["observation_notes"] = {"f1": "Hotter core on a shared temperature scale."}
    path.write_text(json.dumps(content))
    output = api().assemble_section(package, path, tmp_path / "section")
    assert (output / "review-packet/sources/values.csv").read_text() == "x\n1\n"
    assert (
        json.loads((output / "section.json").read_text())["observation_notes"]
        == content["observation_notes"]
    )


def test_review_layout_centers_images_and_removes_theme_residue(tmp_path):
    docx = pytest.importorskip("docx")
    source, _ = fixture_input(tmp_path)
    package = api().prepare_section(source, tmp_path / "package")
    path, _ = draft(tmp_path)
    section = api().assemble_section(package, path, tmp_path / "section")
    out = api().export_section_docx(section, tmp_path / "review.docx")
    doc = docx.Document(out)
    assert not doc.styles["Title"].element.xpath("./w:pPr/w:pBdr")
    assert not doc.styles["Caption"].font.bold
    assert doc.styles["Normal"].paragraph_format.widow_control
    assert doc.sections[0].page_width.mm == pytest.approx(210, abs=0.03)
    assert doc.sections[0].page_height.mm == pytest.approx(297, abs=0.03)
    assert doc.styles["Heading 2"].font.name == "Times New Roman"
    assert str(doc.styles["Heading 2"].font.color.rgb) == "000000"
    report = json.loads(out.with_suffix(".layout.json").read_text())
    assert len(report["figures"]) == 2
    assert report["figures"][0]["minimum_font_pt"] is None
    for p in doc.paragraphs:
        if p._p.xpath(".//wp:inline"):
            assert p.alignment == 1
            assert p.paragraph_format.keep_with_next
            assert p.paragraph_format.page_break_before
    with pytest.raises(ValueError, match="Layout"):
        api().export_section_docx(section, tmp_path / "other.docx", layout="guess")


def test_near_reference_layout_places_each_figure_once(tmp_path):
    docx = pytest.importorskip("docx")
    source, _ = fixture_input(tmp_path)
    package = api().prepare_section(source, tmp_path / "package")
    path, content = draft(tmp_path)
    content["paragraphs"].append(
        {"text": "Second discussion.", "evidence_ids": ["e1"], "figure_ids": ["f1"]}
    )
    path.write_text(json.dumps(content))
    section = api().assemble_section(package, path, tmp_path / "section")
    out = api().export_section_docx(section, tmp_path / "near.docx", layout="near-reference")
    doc = docx.Document(out)
    assert len(doc.inline_shapes) == 2
    texts = [p.text for p in doc.paragraphs]
    assert texts.index("Figure f1. First response") < texts.index("Second discussion.")
    assert texts.count("Figure f1. First response") == 1


def test_preparation_and_review_include_computed_tables_not_stale_json(tmp_path):
    source, data = fixture_input(tmp_path)
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources/flows.csv").write_text("case,flow\na,1\na,3\n")
    data["table_calculations"] = [
        {
            "id": "outlets",
            "source": "sources/flows.csv",
            "operation": "population",
            "columns": {"value": "flow"},
            "units": {"value": "kg/s"},
            "domain": "Net flow through terminal outlets, equal outlet weights",
            "group_by": "case",
        }
    ]
    source.write_text(json.dumps(data))
    package = api().prepare_section(source, tmp_path / "package")
    result = json.loads((package / "table-results.json").read_text())
    assert result[0]["groups"][0]["result"]["cv"] == 0.5
    assert result[0]["units"] == {"value": "kg/s"}
    # Assembly must use copied CSV, not an edited numerical result JSON.
    (package / "table-results.json").write_text("[]")
    dpath, _ = draft(tmp_path)
    section = api().assemble_section(package, dpath, tmp_path / "section")
    assert json.loads((section / "review-packet/table-results.json").read_text()) == result
    assert (section / "review-packet/sources/flows.csv").read_bytes() == (
        package / "sources/flows.csv"
    ).read_bytes()


def bound_input(tmp_path):
    source, data = fixture_input(tmp_path)
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources/flows.csv").write_text("case,flow\na,1\na,3\nb,\n")
    data["table_calculations"] = [
        {
            "id": "outlets",
            "source": "sources/flows.csv",
            "operation": "population",
            "columns": {"value": "flow"},
            "units": {"value": "kg/s"},
            "domain": "Terminal outlets with equal weights",
            "group_by": "case",
        }
    ]
    data["evidence"][0].pop("value")
    data["evidence"][0].pop("unit")
    data["evidence"][0]["result_ref"] = {
        "calculation_id": "outlets",
        "group": "a",
        "field": "mean",
        "places": 2,
    }
    source.write_text(json.dumps(data))
    return source, data


def test_result_ref_recomputes_current_table_and_retains_source(tmp_path):
    source, _ = bound_input(tmp_path)
    package = api().prepare_section(source, tmp_path / "package")
    (package / "sources/flows.csv").write_text("case,flow\na,2\na,6\nb,\n")
    (package / "table-results.json").write_text("[]")
    dpath, data = draft(tmp_path)
    data["captions"]["f1"] = "Mean flow {{value:e1}}."
    data["paragraphs"][0]["text"] = "Mean flow is {{value:e1}} in {{figure:f1}} and {{figure:f2}}."
    dpath.write_text(json.dumps(data))
    output = api().assemble_section(package, dpath, tmp_path / "section")
    result = json.loads((output / "section.json").read_text())
    assert "4.00 kg/s" in result["paragraphs"][0]["text"]
    assert result["figures"][0]["caption"] == "Mean flow 4.00 kg/s."
    resolved = result["resolved_values"]["e1"]
    assert resolved["raw_value"] == 4.0
    assert resolved["source"] == "sources/flows.csv"
    assert resolved["csv_records"] == [2, 3]


def test_table_and_equation_use_bound_values_and_native_word_elements(tmp_path):
    docx = pytest.importorskip("docx")
    source, _ = bound_input(tmp_path)
    package = api().prepare_section(source, tmp_path / "package")
    dpath, data = draft(tmp_path)
    data["paragraphs"][0]["text"] = "Mean flow is {{value:e1}} in {{figure:f1}} and {{figure:f2}}."
    data["paragraphs"][0]["text"] += " See {{table:1}} and {{equation:1}}."
    data["tables"] = [
        {
            "table_id": "1",
            "caption": "Outlet summary",
            "columns": ["Quantity", "Value"],
            "rows": [["Mean flow", "{{value:e1}}"]],
            "after_section_id": "s1",
            "evidence_ids": ["e1"],
            "numeric_columns": [1],
            "column_widths_mm": [90, 70],
            "note": "Equal outlet weights.",
        }
    ]
    data["equations"] = [
        {
            "equation_id": "1",
            "evidence_ids": ["e1"],
            "expression": {
                "kind": "row",
                "children": [
                    {
                        "kind": "sub",
                        "children": [
                            {"kind": "symbol", "text": "q"},
                            {"kind": "text", "text": "mean"},
                        ],
                    },
                    {"kind": "text", "text": " = {{value:e1}}"},
                ],
            },
        }
    ]
    dpath.write_text(json.dumps(data))
    section = api().assemble_section(package, dpath, tmp_path / "section")
    out = api().export_section_docx(section, tmp_path / "native.docx")
    doc = docx.Document(out)
    assert len(doc.tables) == 1
    assert doc.tables[0].cell(1, 1).text == "2.00 kg/s"
    assert doc.tables[0].cell(1, 1).paragraphs[0].alignment == 2
    assert doc.tables[0].rows[0]._tr.xpath("./w:trPr/w:tblHeader")
    assert doc.element.xpath(".//m:oMath/m:sSub")
    assert "2.00 kg/s" in (section / "section.md").read_text(encoding="utf-8")
    with zipfile.ZipFile(out) as archive:
        xml = archive.read("word/document.xml").decode()
        assert "{{value" not in xml
        assert "<m:t" in xml


def test_inline_math_is_editable_and_uses_current_value_tokens(tmp_path):
    docx = pytest.importorskip("docx")
    source, _ = bound_input(tmp_path)
    package = api().prepare_section(source, tmp_path / "package")
    dpath, content = draft(tmp_path)
    content["paragraphs"][0]["text"] = (
        "The mean flow is {{math:flow}} in {{figure:f1}} and {{figure:f2}}."
    )
    content["paragraphs"][0]["inline_math"] = {
        "flow": {
            "kind": "row",
            "children": [
                {
                    "kind": "sub",
                    "children": [{"kind": "symbol", "text": "q"}, {"kind": "text", "text": "mean"}],
                },
                {"kind": "text", "text": " = {{value:e1}}"},
            ],
        }
    }
    dpath.write_text(json.dumps(content))
    section = api().assemble_section(package, dpath, tmp_path / "section")
    output = api().export_section_docx(section, tmp_path / "inline.docx")
    document = docx.Document(output)
    assert document.paragraphs[1]._p.xpath("./m:oMath/m:sSub")
    assert "2.00 kg/s" in "".join(document.paragraphs[1]._p.xpath(".//m:t/text()"))
    assert "{{" not in (section / "section.md").read_text(encoding="utf-8")
    content["paragraphs"][0]["inline_math"] = {}
    dpath.write_text(json.dumps(content))
    with pytest.raises(ValueError, match="Unresolved IDs"):
        api().assemble_section(package, dpath, tmp_path / "invalid")


@pytest.mark.parametrize("change", ["manual", "unit", "kind", "unknown", "missing"])
def test_result_ref_rejects_conflicting_or_unavailable_values(tmp_path, change):
    source, data = bound_input(tmp_path)
    record = data["evidence"][0]
    if change == "manual":
        record["value"] = "99"
    elif change == "unit":
        record["unit"] = "K"
    elif change == "kind":
        record["kind"] = "literature"
    elif change == "unknown":
        record["result_ref"]["field"] = "invented"
    else:
        record["result_ref"]["group"] = "b"
    source.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        package = api().prepare_section(source, tmp_path / "package")
        dpath, _ = draft(tmp_path)
        api().assemble_section(package, dpath, tmp_path / "section")
    assert not (tmp_path / "section").exists()
