"""Run the public original-face example through real refresh and revision APIs."""

import csv
import json
import runpy
from pathlib import Path

import pytest


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_linked_surface_example_preserves_style_and_requests_interpretation_review(tmp_path):
    docx = pytest.importorskip("docx")
    np = pytest.importorskip("numpy")
    pytest.importorskip("shapely", minversion="2")
    script = (
        Path(__file__).parents[1] / "examples/research-expression/run_linked_surface_example.py"
    )
    output = tmp_path / "linked"
    result = runpy.run_path(str(script))["run"](output)
    assert result == output / "revised/manuscript.docx"
    first, refreshed, revised = (output / name for name in ("candidate", "refreshed", "revised"))
    relative = Path("sections/results/figures/diagnostics")
    identity = "surface-change"

    def scalar(candidate, key):
        values = read(candidate / "manuscript/section.json")["resolved_values"]
        return values[json.dumps(["results", key], separators=(",", ":"))]["raw_value"]

    assert scalar(first, "regional-change-all-difference_mean") == pytest.approx(0.5)
    assert scalar(refreshed, "regional-change-all-difference_mean") == pytest.approx(-0.5)
    assert scalar(revised, "regional-change-all-difference_mean") == pytest.approx(-0.5)
    author_script = (output / "author-working" / relative / "plot.py").read_bytes()
    assert b"STYLE.tick_pt = 9.0" in author_script
    for candidate in (refreshed, revised):
        assert (candidate / "workspace" / relative / "plot.py").read_bytes() == author_script
    for source in (output / "materials/sources").iterdir():
        copied = first / "workspace/sections/results/sources" / source.name
        assert source.read_bytes() == copied.read_bytes()
    with np.load(output / "materials/sources/comparison.npz") as original:
        with np.load(refreshed / "workspace/sections/results/sources/comparison.npz") as changed:
            np.testing.assert_allclose(changed["face_value"], original["face_value"] - 1)

    initial_figure = first / "workspace" / relative / f"{identity}.png"
    updated_figure = refreshed / "workspace" / relative / f"{identity}.png"
    assert initial_figure.read_bytes() != updated_figure.read_bytes()
    figure_dir = revised / "workspace" / relative
    for suffix in ("png", "svg", "pdf", "tiff"):
        assert (figure_dir / f"{identity}.{suffix}").stat().st_size > 100
    assert "<text" in (figure_dir / f"{identity}.svg").read_text(encoding="utf-8")
    with (figure_dir / f"{identity}-field-source-data.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        assert len(list(csv.DictReader(stream))) == 128
    with (figure_dir / f"{identity}-source-data.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [float(row["contribution"]) for row in rows] == pytest.approx([-1.25, 0.75])
    checks = read(figure_dir / "diagnostic-checks.json")[identity]
    assert checks["text_inside_canvas"] and checks["text_nonoverlapping"]
    assert checks["source_width_mm"] == pytest.approx(160, abs=0.1)

    drafts = [
        read(root / "workspace/sections/results/draft.json") for root in (first, refreshed, revised)
    ]
    assert drafts[0]["paragraphs"][0] == drafts[1]["paragraphs"][0]
    assert drafts[0]["paragraphs"][1] == drafts[1]["paragraphs"][1] == drafts[2]["paragraphs"][1]
    assert drafts[0]["captions"][identity] == drafts[1]["captions"][identity]
    assert drafts[2]["captions"][identity] != drafts[1]["captions"][identity]
    assert set(drafts[2]["captions"]) == {identity}
    assert "mean rises" in drafts[1]["paragraphs"][0]["text"]
    assert "mean falls" in drafts[2]["paragraphs"][0]["text"]
    refresh = read(refreshed / "refresh.json")
    assert refresh["interpretation_review_required"] is True
    assert "results" in refresh["interpretation_review_sections"]
    changes = read(refreshed / "manuscript/changes.json")
    passages = changes["affected_passages"]["results"]
    assert any("mean rises" in passage["text"] for passage in passages)
    report = (refreshed / "CHANGES.md").read_text(encoding="utf-8")
    assert "Interpretation review required" in report

    context = read(output / "refreshed-response.json")["context"]["selected_figures"][0]
    current = read(output / "revised-response.json")["context"]["selected_figures"][0]
    assert current["id"] == context["id"] == identity
    assert context["caption"] == drafts[1]["captions"][identity]
    assert current["caption"] == drafts[2]["captions"][identity]
    assert context["image_observation"] == "not-viewed"
    groups = context["reading"]["comparisons"][0]["results"]
    whole = next(group["result"] for group in groups if group["group"] == "all")
    assert whole["difference_mean"] == pytest.approx(-0.5)
    assert current["reading"] == context["reading"]
    word = docx.Document(result)
    assert len(word.inline_shapes) == 1
    assert word.inline_shapes[0].width.mm == pytest.approx(160, abs=0.1)
    assert word.inline_shapes[0].height.mm == pytest.approx(110, abs=0.1)
    assert "not a heat budget" in drafts[2]["captions"][identity]
    assert "negative net change" in drafts[2]["captions"][identity]
    text = "".join(word.element.body.xpath(".//w:t/text()"))
    text = text.replace("\u2212", "-").replace("\u2060", "")
    assert "mean falls" in text and "-0.500" in text and "{{" not in text
