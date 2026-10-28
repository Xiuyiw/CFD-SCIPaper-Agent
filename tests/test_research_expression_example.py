"""The public expression example binds original and derived readings, including refresh."""

import csv
import json
import runpy
from pathlib import Path

import pytest
from docx import Document


def test_research_expression_preserves_originals_and_binds_changes_with_header_units(tmp_path):
    script = Path(__file__).parents[1] / "examples/research-expression/run_example.py"
    output = tmp_path / "example"
    runpy.run_path(str(script))["run"](output)

    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))

    def scalar(candidate, identity):
        values = read(candidate / "manuscript/section.json")["resolved_values"]
        key = json.dumps(["results", identity], separators=(",", ":"))
        return values[key]["raw_value"]

    first, refreshed = output / "candidate", output / "refreshed"
    for identity, expected in (
        ("paired-A-all-reference_mean", 317.5),
        ("paired-A-all-comparison_mean", 319.75),
        ("paired-A-all-difference_mean", 2.25),
        ("budget-A1-all-residual", 45),
    ):
        assert scalar(first, identity) == pytest.approx(expected)
    assert scalar(refreshed, "paired-A-all-comparison_mean") == pytest.approx(320.75)
    assert scalar(refreshed, "paired-A-all-difference_mean") == pytest.approx(3.25)
    assert scalar(refreshed, "paired-A-all-reference_mean") == pytest.approx(317.5)
    for source in (output / "materials/sources").iterdir():
        copied = first / "workspace/sections/results/sources" / source.name
        assert source.read_bytes() == copied.read_bytes()

    relative = "sections/results/figures/diagnostics"
    figure = first / "workspace" / relative
    with (figure / "thermal-budget-source-data.csv").open(encoding="utf-8", newline="") as f:
        original_rows = list(csv.DictReader(f))
    original = next(
        row
        for row in original_rows
        if row["calculation_id"] == "temperature-A1" and row["group"] == "all"
    )
    assert original["source"] == "sources/A1.npz"
    assert float(original["weighted_mean"]) == pytest.approx(319.75)
    with (figure / "thermal-budget-differences.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [float(row["difference"]) for row in rows] == pytest.approx([-3, 4, 2.25, -1, 3, 2])
    assert "<text" in (figure / "thermal-budget.svg").read_text(encoding="utf-8")
    for extension in ("svg", "pdf", "png", "tiff"):
        assert (figure / f"thermal-budget.{extension}").stat().st_size > 100

    word = Document(first / "manuscript.docx")
    assert len(word.inline_shapes) == 1
    # Formal Word blocks wrap native tables in editable content controls.
    tables = word.element.body.xpath(".//w:tbl")
    assert len(tables) == 2
    assert len(word.element.body.xpath(".//w:sdtContent//w:tbl")) == 2

    def cells(row):
        return ["".join(cell.xpath(".//w:t/text()")) for cell in row.xpath("./w:tc")]

    assert cells(tables[0].xpath("./w:tr")[0]) == [
        "Pair",
        "Reference (K)",
        "Comparison (K)",
        "Change (K)",
    ]
    assert cells(tables[0].xpath("./w:tr")[1]) == [
        "Structure A",
        "317.500",
        "319.750",
        "2.250",
    ]
    assert all("W" not in cell for row in tables[1].xpath("./w:tr")[1:] for cell in cells(row))
    assert "{{" not in " ".join(word.element.body.xpath(".//w:t/text()"))
    order = read(first / "manuscript/section.json")["section_orders"]["results"]
    assert order == [
        "paragraph:whole-response",
        "table:paired-means",
        "paragraph:regional-budget",
        "figure:thermal-budget",
        "table:local-budget",
    ]
    xml = word.element.body.xml
    positions = [
        xml.index(marker)
        for marker in (
            "The whole-interface mean rises",
            "Original whole-interface means and changes.",
            "In contrast, the footprint mean",
            "<w:drawing>",
            "Separate prescribed local energy budgets.",
        )
    ]
    assert positions == sorted(positions)
    working = output / "author-working"
    assert (working / relative / "plot.py").read_bytes() == (
        refreshed / "workspace" / relative / "plot.py"
    ).read_bytes()
    for name in read(working / "drafts.json").values():
        assert (working / name).read_bytes() == (refreshed / "workspace" / name).read_bytes()
    assert read(refreshed / "refresh.json")["interpretation_review_required"] is True
