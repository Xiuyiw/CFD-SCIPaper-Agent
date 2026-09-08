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
