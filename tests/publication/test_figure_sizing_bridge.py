"""A declared source font survives import, section assembly and actual Word sizing."""

import json

import pytest
from PIL import Image, ImageDraw

from cfdpaper.publication.figure_tasks import import_figure_task, prepare_figure_task
from cfdpaper.publication.section import assemble_section, export_section_docx, prepare_section


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_import_metadata_controls_actual_word_figure_size(tmp_path):
    pytest.importorskip("docx")
    from docx import Document

    (tmp_path / "data.csv").write_text("x,y\n1,2\n2,3\n")
    task = prepare_figure_task(
        write(
            tmp_path / "task.json",
            {
                "figure_id": "f1",
                "kind": "data",
                "purpose": "Synthetic comparison",
                "claim_ceiling": "Synthetic observations only",
                "final_width_mm": 100,
                "labels": [{"text": "Synthetic value", "unit": "Pa"}],
                "sources": [
                    {"id": "data", "path": "data.csv", "role": "data", "description": "Fixture"}
                ],
            },
        ),
        tmp_path / "task",
    )
    returned = tmp_path / "returned"
    returned.mkdir()
    (returned / "plot.py").write_text("fixture_only = True  # Never executed by import.\n")
    picture = Image.new("RGB", (1200, 600), "white")
    ImageDraw.Draw(picture).line((100, 100, 1100, 500), fill="black", width=3)
    picture.save(returned / "preview.png")
    delivery = write(
        returned / "delivery.json",
        {
            "figure_id": "f1",
            "editable_sources": ["plot.py"],
            "preview": "preview.png",
            "caption": "Synthetic sizing fixture.",
            "sizing": {"source_width_mm": 200, "minimum_source_font_pt": 16},
        },
    )
    imported = import_figure_task(task, delivery, tmp_path / "imported")
    metadata = json.loads((imported / "delivery.json").read_text())
    source = write(
        imported / "input.json",
        {
            "section_id": "sizing",
            "title": "Sizing",
            "question": "Is scale preserved?",
            "figures": [
                {
                    "id": "f1",
                    "path": metadata["preview"],
                    "caption": metadata["caption"],
                    "description": "Synthetic non-scientific fixture",
                    "sizing": metadata["sizing"],
                }
            ],
            "evidence": [
                {
                    "id": "obs",
                    "kind": "observation",
                    "text": "Synthetic line",
                    "source": metadata["preview"],
                }
            ],
            "duties": [
                {"purpose": "Describe fixture", "evidence_ids": ["obs"], "figure_ids": ["f1"]}
            ],
            "style": metadata["placement_style"],
        },
    )
    writing = prepare_section(source, tmp_path / "writing")
    draft = write(
        tmp_path / "draft.json",
        {
            "title": "Sizing",
            "paragraphs": [
                {
                    "text": "Synthetic line in {{figure:f1}}.",
                    "evidence_ids": ["obs"],
                    "figure_ids": ["f1"],
                }
            ],
            "captions": {"f1": metadata["caption"]},
            "image_observations": {"f1": "author-provided"},
            "evidence_notes": [],
        },
    )
    section = assemble_section(writing, draft, tmp_path / "section")
    result = export_section_docx(section, tmp_path / "result.docx")
    placement = json.loads(result.with_suffix(".layout.json").read_text())["figures"][0]
    assert placement["minimum_font_pt"] == 8
    assert placement["width_mm"] == metadata["placement"]["width_mm"] == 100
    document = Document(result)
    assert document.inline_shapes[0].width.mm == pytest.approx(100)
    body = next(p for p in document.paragraphs if p.text.startswith("Synthetic line"))
    assert body.paragraph_format.first_line_indent.pt == 22
    assert body.paragraph_format.space_before.pt == body.paragraph_format.space_after.pt == 0
