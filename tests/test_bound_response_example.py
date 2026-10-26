"""The public constructed-response example exercises installed product entry points."""

import csv
import json
import runpy
import zipfile
from pathlib import Path


def test_bound_response_example_has_two_complementary_panels_and_native_word(tmp_path):
    script = Path(__file__).parents[1] / "examples/bound-response-report/run_example.py"
    example = runpy.run_path(str(script))
    output = tmp_path / "example"
    docx = example["run"](output)
    assert docx == output / "candidate/manuscript.docx"
    context = json.loads(
        (output / "candidate/workspace/report-context.json").read_text(encoding="utf-8")
    )
    assert len(context["metrics"]) == 15
    figure = output / "candidate/workspace/sections/results/sources/report-figure"
    with (figure / "evidence-panels-source-data.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 12
    assert {row["panel"] for row in rows} == {"1", "2"}
    assert {row["group"] for row in rows} == {"S1", "S2", "S3"}
    assert {row["x_unit"] for row in rows} == {"m/s"}
    assert {row["y_unit"] for row in rows} == {"K", "kPa"}
    for suffix in ("svg", "pdf", "png", "tiff"):
        assert (figure / f"evidence-panels.{suffix}").stat().st_size > 100
    assert (figure / "plot.py").is_file()
    markdown = (output / "candidate/manuscript/manuscript.md").read_text(encoding="utf-8")
    assert "330.000 K" in markdown
    assert "0.600 kPa" in markdown
    assert "{{value:" not in markdown
    with zipfile.ZipFile(docx) as archive:
        document = archive.read("word/document.xml")
        assert b"<w:tbl>" in document
        assert b"<w:drawing>" in document
    from docx import Document

    word = Document(docx)
    assert len(word.element.body.xpath(".//w:tbl")) == 1
    assert len(word.inline_shapes) == 1
    word_text = " ".join(word.element.body.xpath(".//w:t/text()")).replace("\u00a0", " ")
    assert "330.000 K" in word_text and "0.600 kPa" in word_text
