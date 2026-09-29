"""Short numerical prose retains the full physical unit in the evidence record."""

import pytest

from cfdpaper.publication.manuscript import assemble_manuscript, prepare_manuscript
from cfdpaper.publication.section import assemble_section, prepare_section
from tests.publication.test_manuscript import fixture, read, write


def inputs(tmp_path):
    source, drafts = fixture(tmp_path)
    data = read(tmp_path / "response/input.json")
    metric = next(e for e in data["evidence"] if e["id"] == "metric")
    return source, drafts, data, metric


def test_shared_unit_does_not_change_numeric_provenance(tmp_path):
    _, _, data, _ = inputs(tmp_path)
    data["table_calculations"][0]["units"]["value"] = "Pa"
    write(tmp_path / "response/input.json", data)
    package = prepare_section(tmp_path / "response/input.json", tmp_path / "p")
    draft_path = tmp_path / "response/draft.json"
    draft = read(draft_path)
    draft["paragraphs"][0]["shared_unit"] = "Pa"
    draft["paragraphs"][0]["text"] += " Reported values are in Pa."
    write(draft_path, draft)
    result = assemble_section(package, draft_path, tmp_path / "out")
    payload = read(result / "section.json")
    assert "2.00 Pa" not in payload["paragraphs"][0]["text"]
    assert "2.00" in payload["paragraphs"][0]["text"]
    assert payload["resolved_values"]["metric"]["unit"] == "Pa"
    assert "2.00 Pa" in payload["tables"][0]["rows"][0][1]


@pytest.mark.parametrize(
    "shared,text,match",
    [
        ("K", "Reported in K.", "does not match"),
        ("Pa", "No unit here.", "appear explicitly"),
        ("Pa", "Pascaline is not a unit declaration.", "appear explicitly"),
    ],
)
def test_wrong_or_implicit_unit_rejected(tmp_path, shared, text, match):
    _, _, data, _ = inputs(tmp_path)
    data["table_calculations"][0]["units"]["value"] = "Pa"
    write(tmp_path / "response/input.json", data)
    package = prepare_section(tmp_path / "response/input.json", tmp_path / "p")
    draft_path = tmp_path / "response/draft.json"
    draft = read(draft_path)
    draft["paragraphs"][0]["shared_unit"] = shared
    draft["paragraphs"][0]["text"] += text
    write(draft_path, draft)
    with pytest.raises(ValueError, match=match):
        assemble_section(package, draft_path, tmp_path / "no")


def test_shared_display_survives_manuscript_assembly(tmp_path):
    source, drafts, data, _ = inputs(tmp_path)
    data["table_calculations"][0]["units"]["value"] = "Pa"
    write(tmp_path / "response/input.json", data)
    draft_path = tmp_path / "response/draft.json"
    draft = read(draft_path)
    draft["paragraphs"][0]["shared_unit"] = "Pa"
    draft["paragraphs"][0]["text"] += " Reported values are in Pa."
    write(draft_path, draft)
    package = prepare_manuscript(source, tmp_path / "p")
    output = assemble_manuscript(package, drafts, tmp_path / "out")
    text = (output / "manuscript.md").read_text(encoding="utf-8")
    assert "Reported values are in Pa." in text
