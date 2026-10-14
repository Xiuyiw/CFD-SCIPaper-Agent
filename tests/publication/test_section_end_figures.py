"""Explicit section-end placement preserves default ordering and figure dimensions."""

import json
import shutil

import pytest
from PIL import Image

from cfdpaper.publication.manuscript import assemble_manuscript, prepare_manuscript
from cfdpaper.publication.section import (
    _Figure,
    assemble_section,
    export_section_docx,
    prepare_section,
)


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def inputs(root, sid, placement):
    Image.new("RGB", (120, 80), "white").save(root / "plot.png")
    figure = {
        "id": "plot",
        "path": "plot.png",
        "caption": f"Response for {sid}.",
        "description": "Synthetic fixture image",
        "sizing": {"source_width_mm": 60, "target_width_mm": 60, "minimum_source_font_pt": 9},
    }
    if placement != "omitted":
        figure["placement"] = placement
    source = write(
        root / "input.json",
        {
            "section_id": sid,
            "title": sid.title(),
            "question": "What is observed?",
            "figures": [figure],
            "evidence": [
                {
                    "id": "observation",
                    "kind": "observation",
                    "text": "Supplied observation",
                    "source": "Fixture author",
                }
            ],
            "duties": [
                {
                    "purpose": "Describe the figure",
                    "evidence_ids": ["observation"],
                    "figure_ids": ["plot"],
                }
            ],
        },
    )
    draft = write(
        root / "draft.json",
        {
            "title": sid.title(),
            "paragraphs": [
                {
                    "text": f"First {sid} paragraph {{{{figure:plot}}}}.",
                    "evidence_ids": ["observation"],
                    "figure_ids": ["plot"],
                },
                {"text": f"Last {sid} paragraph.", "evidence_ids": [], "figure_ids": []},
            ],
            "captions": {"plot": f"Response for {sid}."},
            "image_observations": {"plot": "author-provided"},
            "evidence_notes": [],
        },
    )
    return source, draft


def assert_figure_block(document, caption_text, forced_break):
    captions = [i for i, p in enumerate(document.paragraphs) if p.text == caption_text]
    assert len(captions) == 1
    image = document.paragraphs[captions[0] - 1]
    caption = document.paragraphs[captions[0]]
    assert image._p.xpath(".//wp:inline")
    assert image.paragraph_format.keep_with_next is True
    assert image.paragraph_format.page_break_before is forced_break
    assert caption.paragraph_format.keep_with_next is False
    assert caption.paragraph_format.keep_together is True
    assert len(document.inline_shapes) >= 1
    assert round(document.inline_shapes[0].width / 36000, 6) == 60
    assert round(document.inline_shapes[0].height / 36000, 6) == 40


@pytest.mark.parametrize("layout", ["near-reference", "after-text"])
@pytest.mark.parametrize("placement", ["omitted", "default", "section-end"])
def test_single_section_sdk_roundtrip_order_and_word_structure(tmp_path, layout, placement):
    docx = pytest.importorskip("docx")
    source, draft = inputs(tmp_path, "results", placement)
    package = prepare_section(source, tmp_path / "prepared")
    moved = tmp_path / "moved"
    shutil.move(str(package), moved)
    candidate = assemble_section(moved, draft, tmp_path / "candidate")
    result = json.loads((candidate / "section.json").read_text(encoding="utf-8"))
    figure = result["figures"][0]
    if placement == "section-end":
        assert figure["placement"] == "section-end"
    else:
        assert "placement" not in figure
    output = export_section_docx(candidate, tmp_path / "manuscript.docx", layout=layout)
    document = docx.Document(output)
    text = [p.text for p in document.paragraphs]
    caption = text.index("Figure plot. Response for results.")
    last = text.index("Last results paragraph.")
    assert (caption > last) is (placement == "section-end" or layout == "after-text")
    assert len(document.inline_shapes) == 1
    assert_figure_block(
        document,
        "Figure plot. Response for results.",
        layout == "after-text" and placement != "section-end",
    )


@pytest.mark.parametrize("layout", ["near-reference", "after-text"])
@pytest.mark.parametrize("first_placement", ["default", "section-end"])
def test_manuscript_global_ownership_flushes_before_next_heading_and_final_section(
    tmp_path, layout, first_placement
):
    docx = pytest.importorskip("docx")
    sections, contracts, drafts = [], [], {}
    for sid in ("response", "transport"):
        local = tmp_path / sid
        local.mkdir()
        inputs(local, sid, first_placement if sid == "response" else "section-end")
        sections.append({"section_id": sid, "input": f"{sid}/input.json"})
        contracts.append(
            {
                "section_id": sid,
                "role": "results",
                "title": sid.title(),
                "purpose": "Explain observed response",
                "required_claim_ids": ["observation"],
                "required_figure_ids": ["plot"],
            }
        )
        drafts[sid] = f"{sid}/draft.json"
    source = write(
        tmp_path / "manuscript.json",
        {
            "title": "Synthetic two-section manuscript",
            "spine": {"topic_id": "test", "central_claim_id": "observation", "sections": contracts},
            "sections": sections,
        },
    )
    mapping = write(tmp_path / "drafts.json", drafts)
    package = prepare_manuscript(source, tmp_path / "prepared")
    moved = tmp_path / "moved"
    shutil.move(str(package), moved)
    candidate = assemble_manuscript(moved, mapping, tmp_path / "candidate")
    result = json.loads((candidate / "section.json").read_text(encoding="utf-8"))
    assert result["section_objects"]["response"]["figure_ids"] == ["1"]
    assert result["section_objects"]["transport"]["figure_ids"] == ["2"]
    output = export_section_docx(candidate, tmp_path / "manuscript.docx", layout=layout)
    document = docx.Document(output)
    text = [p.text for p in document.paragraphs]
    first_caption = text.index("Figure 1. Response for response.")
    if first_placement == "section-end":
        assert text.index("Last response paragraph.") < first_caption < text.index("Transport")
    elif layout == "near-reference":
        assert first_caption < text.index("Last response paragraph.")
    else:
        assert text.index("Last transport paragraph.") < first_caption
    assert text.index("Last transport paragraph.") < text.index("Figure 2. Response for transport.")
    assert len(document.inline_shapes) == 2
    assert_figure_block(
        document,
        "Figure 1. Response for response.",
        layout == "after-text" and first_placement == "default",
    )
    assert_figure_block(document, "Figure 2. Response for transport.", False)


def test_invalid_placement_is_not_silently_accepted():
    with pytest.raises(ValueError, match="placement"):
        _Figure.model_validate(
            {
                "id": "plot",
                "path": "plot.png",
                "caption": "Response",
                "description": "Fixture",
                "placement": "auto-layout",
            }
        )
