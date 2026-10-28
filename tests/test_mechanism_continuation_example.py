"""Public constructed-input replay exercises same-identity figure and prose continuation."""

import json
import runpy
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest
from docx import Document


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def short_root():
    # Bound review packets nest two staging roots; avoid Windows MAX_PATH in the harness.
    with TemporaryDirectory(prefix="mc-") as name:
        yield Path(name)


def test_mechanism_continuation_preserves_sources_and_revises_interpretation(short_root):
    examples = Path(__file__).parents[1] / "examples"
    previous = short_root / "expression"
    runpy.run_path(str(examples / "research-expression/run_example.py"))["run"](previous)
    original = previous / "candidate/workspace/sections/results"
    original_sources = {p.name: p.read_bytes() for p in (original / "sources").glob("*.npz")}
    original_script = (original / "figures/diagnostics/plot.py").read_bytes()
    output = short_root / "continuation"
    document = runpy.run_path(str(examples / "mechanism-continuation/run_example.py"))["run"](
        previous, output
    )
    assert document == output / "interpretation-updated/manuscript.docx"
    assert document.is_file()
    for name, contents in original_sources.items():
        assert (original / "sources" / name).read_bytes() == contents
    assert (original / "figures/diagnostics/plot.py").read_bytes() == original_script

    for label, expected in (("before", 2.25), ("after", -1.75)):
        context = read(output / f"context-{label}.json")
        delta = next(r for r in context["evidence"] if r["id"] == "paired-A-all-difference_mean")
        assert delta["resolved"]["raw_value"] == pytest.approx(expected)
        assert delta["calculation"]["operation"] == "field_difference"
        assert context["passages"]
        assert all(r["id"].startswith(("paired-A-", "temperature-A")) for r in context["evidence"])

    changes = read(output / "numerical-refresh/manuscript/changes.json")
    sign_changes = [
        change
        for passage in changes["affected_passages"]["results"]
        for change in passage["result_changes"]
        if change["evidence_id"] == "paired-A-all-difference_mean"
    ]
    assert sign_changes and all(c["difference_sign_changed"] is True for c in sign_changes)
    assert "Difference sign changed" in (
        output / "numerical-refresh/manuscript/CHANGES.md"
    ).read_text(encoding="utf-8")

    final = output / "interpretation-updated/workspace/sections/results"
    working = output / "author-working/sections/results"
    original_art = Path("sources/figure-tasks/observation-support")
    updated_art = Path("sources/figure-tasks/observation-support-update-1")
    for name in ("figure.svg", "author-notes.md"):
        assert (working / original_art / name).read_bytes() == (
            final / original_art / name
        ).read_bytes()
    svg = ET.parse(final / updated_art / "figure.svg").getroot()
    texts = [node.text for node in svg.iter() if node.tag.endswith("}text")]
    assert any("-1.750 K" in text for text in texts if text)
    assert not any(node.tag.endswith("}image") for node in svg.iter())
    assert (final / "figures/diagnostics/plot.py").read_bytes() == original_script
    for case in ("A0", "B0", "B1"):
        assert (final / "sources" / f"{case}.npz").read_bytes() == original_sources[f"{case}.npz"]
    with np.load(original / "sources/A1.npz") as before, np.load(final / "sources/A1.npz") as after:
        assert after["face_value"] == pytest.approx(before["face_value"] - 4)
        for key in before.files:
            if key != "face_value":
                assert np.array_equal(after[key], before[key])
    for path in (original / "sources").glob("budget-*.csv"):
        assert (final / "sources" / path.name).read_bytes() == path.read_bytes()

    attached = read(output / "artwork-updated-workspace/sections/results/draft.json")
    old = read(working / "draft.json")
    assert attached["paragraphs"] == old["paragraphs"]
    draft = read(final / "draft.json")
    assert len(draft["paragraphs"]) == len(old["paragraphs"]) == 3
    assert "-1.750 K" in draft["captions"]["observation-support"]
    assert "falls" in draft["paragraphs"][0]["text"]
    assert "unchanged" in draft["paragraphs"][1]["text"]
    assert draft["paragraphs"][2]["paragraph_id"]
    assembled = read(output / "interpretation-updated/manuscript/section.json")
    first = read(output / "first-candidate/manuscript/section.json")
    assert (
        assembled["object_origins"]["figure"]
        == first["object_origins"]["figure"]
        == {
            "1": {"section_id": "results", "local_id": "thermal-budget"},
            "2": {"section_id": "results", "local_id": "observation-support"},
        }
    )
    assert assembled["section_orders"] == first["section_orders"]
    assert assembled["section_orders"]["results"][-2:] == [
        "paragraph:" + draft["paragraphs"][2]["paragraph_id"],
        "figure:observation-support",
    ]
    word = Document(document)
    assert len(word.inline_shapes) == 2
    text = " ".join(word.element.body.xpath(".//w:t/text()"))
    # Formal Word uses a mathematical minus, word joiner and nonbreaking quantity space.
    text = text.replace("\u2212", "-").replace("\u2060", "").replace("\u00a0", " ")
    assert "-1.750 K" in text
    assert "{{" not in text
    assert "causal heat-transfer mechanism" in text


def test_mechanism_continuation_requires_a_completed_predecessor_and_fresh_output(tmp_path):
    script = Path(__file__).parents[1] / "examples/mechanism-continuation/run_example.py"
    run = runpy.run_path(str(script))["run"]
    missing, output = tmp_path / "missing", tmp_path / "output"
    with pytest.raises(ValueError, match="research-expression"):
        run(missing, output)
    assert not output.exists()
    previous = tmp_path / "previous"
    workspace = previous / "candidate/workspace"
    workspace.mkdir(parents=True)
    (workspace / "manuscript-input.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        run(previous, previous / "nested-output")
    assert not (previous / "nested-output").exists()
    output.mkdir()
    with pytest.raises(FileExistsError):
        run(previous, output)
