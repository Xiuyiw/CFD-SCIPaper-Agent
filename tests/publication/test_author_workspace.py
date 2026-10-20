"""A Word edit and changed evidence must merge through the real manuscript pipeline."""

from copy import deepcopy

from docx import Document
from docx.oxml.ns import qn

from cfdpaper.publication.author_workspace import (
    import_author_manuscript,
    prepare_author_manuscript,
)
from cfdpaper.publication.formal_export import export_formal_manuscript
from cfdpaper.publication.manuscript import assemble_manuscript, prepare_manuscript
from cfdpaper.publication.word_return import read_word_return
from tests.publication.test_manuscript import fixture, read


def _edit_word(path, output, prefix, replacement):
    doc = Document(path)
    nodes = [n for n in doc._element.iter(qn("w:t")) if n.text and prefix in n.text]
    assert nodes
    node = next((n for n in nodes if n.text == prefix), nodes[0])
    node.text = node.text.replace(prefix, replacement, 1)
    doc.save(output)


def test_author_prose_and_new_number_coexist_without_rewriting_other_sections(tmp_path):
    source, drafts = fixture(tmp_path)
    prepared = prepare_manuscript(source, tmp_path / "prepared")
    base = assemble_manuscript(prepared, drafts, tmp_path / "base")
    word = export_formal_manuscript(base, tmp_path / "author.docx")
    before = read_word_return(word)
    edited = tmp_path / "edited.docx"
    _edit_word(word, edited, "Synthetic ", "Author-revised ")
    old_bytes = word.read_bytes()
    # Actual source update, not replacement of numbers in the assembled prose.
    (base / "sections/methods/sources/values.csv").write_text("case,value\na,3\na,5\n")
    current = assemble_manuscript(base, base / "drafts.json", tmp_path / "current")
    returned = import_author_manuscript(edited, current, tmp_path / "returned")
    merge = read(returned / "merge.json")
    assert merge["conflicts"] == []
    candidate = read(returned / "candidate/section.json")
    assert "Author-revised 4.00 K" in candidate["paragraphs"][1]["text"]
    for index in (3, 5):
        assert candidate["paragraphs"][index] == read(current / "section.json")["paragraphs"][index]
    assert word.read_bytes() == old_bytes
    assert read_word_return(edited)["state"]["baseline_id"] == before["baseline_id"]
    assert (returned / "author-original.docx").read_bytes() == edited.read_bytes()
    refreshed_word = export_formal_manuscript(returned / "candidate", tmp_path / "refreshed.docx")
    final = read_word_return(refreshed_word)
    assert not final["conflicts"]
    assert any("Author-revised {{value:metric}}" in b["text"] for b in final["blocks"])


def test_authored_binding_change_is_localized_not_promoted(tmp_path):
    source, drafts = fixture(tmp_path)
    prepared = prepare_manuscript(source, tmp_path / "prepared")
    base = assemble_manuscript(prepared, drafts, tmp_path / "base")
    word = export_formal_manuscript(base, tmp_path / "author.docx")
    edited = tmp_path / "edited.docx"
    _edit_word(word, edited, "2.00", "999.00")
    returned = import_author_manuscript(edited, base, tmp_path / "returned")
    merge = read(returned / "merge.json")
    assert any(c["type"] == "protected_span_modified" for c in merge["conflicts"])
    text = (returned / "candidate/manuscript.md").read_text(encoding="utf-8")
    assert "999.00" not in text
    assert (
        read(returned / "candidate/section.json")["resolved_values"]
        == read(base / "section.json")["resolved_values"]
    )


def test_definition_change_classified_separately_from_display(tmp_path):
    from cfdpaper.publication.author_workspace import describe_author_refresh

    source = {
        "sections": {
            "methods": {
                "input": {"table_calculations": [{"domain": "interface", "weight": "area"}]}
            }
        }
    }
    state = {
        "source_state": source,
        "blocks": [
            {
                "id": "b",
                "kind": "paragraph",
                "section_id": "methods",
                "text": "Mean temperature",
                "spans": [],
            }
        ],
    }
    current = deepcopy(state)
    after = deepcopy(source)
    after["sections"]["methods"]["input"]["table_calculations"][0]["weight"] = "unweighted"
    changes = describe_author_refresh(state, current, current_source_state=after)
    assert changes[0]["category"] == "definition"
    assert changes[0]["interpretation_required"]


def test_word_typesetting_is_not_a_changed_scientific_number():
    from cfdpaper.publication.author_workspace import describe_author_refresh

    old = {
        "blocks": [
            {
                "id": "p",
                "section_id": "methods",
                "text": "{{value:T}}",
                "spans": [{"token": "{{value:T}}", "text": "−\u206030.1\u00a0K"}],
            }
        ]
    }
    new = deepcopy(old)
    new["blocks"][0]["spans"][0]["text"] = "-30.1 K"
    assert describe_author_refresh(old, new) == []


def test_docx_context_does_not_embed_raw_csv_rows():
    from cfdpaper.publication.document_blocks import source_definition_state

    source = {
        "sections": {
            "s": {
                "sources": {"huge.csv": "RAW_FIELD" * 200000},
                "input": {"table_calculations": [{"id": "mean"}]},
            }
        }
    }
    result = source_definition_state(source)
    assert "RAW_FIELD" not in str(result)
    assert result["sections"]["s"]["input"]["table_calculations"] == [{"id": "mean"}]


def test_managed_author_copy_persists_ids_without_changing_original(tmp_path):
    source, drafts = fixture(tmp_path)
    prepared = prepare_manuscript(source, tmp_path / "prepared")
    base = assemble_manuscript(prepared, drafts, tmp_path / "base")
    original = (base / "sections/methods/draft.json").read_bytes()
    managed = prepare_author_manuscript(base, tmp_path / "managed")
    draft = read(managed / "candidate/sections/methods/draft.json")
    paragraph = read(base / "section.json")["paragraphs"][1]
    assert draft["paragraphs"][0]["paragraph_id"] == paragraph["paragraph_id"]
    assert (base / "sections/methods/draft.json").read_bytes() == original
    assert (managed / "manuscript.docx").is_file()
    assert (managed / "manuscript.md").is_file()


def test_authored_figure_abbreviation_survives_source_return_and_reexport(tmp_path):
    source, drafts = fixture(tmp_path)
    prepared = prepare_manuscript(source, tmp_path / "prepared")
    base = assemble_manuscript(prepared, drafts, tmp_path / "base")
    word = export_formal_manuscript(base, tmp_path / "author.docx")
    edited = tmp_path / "edited.docx"
    _edit_word(word, edited, "Figure 1", "Fig. 1")
    _edit_word(edited, edited, "Figure 1. ", "Fig. 1. ")
    result = import_author_manuscript(edited, base, tmp_path / "returned")
    assert read(result / "merge.json")["conflicts"] == []
    labels = read(result / "candidate/author-edits.json")["blocks"]
    assert sum(v.get("reference_labels") == {"figure": "Fig."} for v in labels.values()) == 2
    first = read_word_return(result / "manuscript.docx")
    assert not first["conflicts"]
    abbreviated = [b for b in first["blocks"] if b.get("reference_labels")]
    assert len(abbreviated) == 2
    assert all("Fig. 1" in b["rendered_text"] for b in abbreviated)
    assert "{{figure:same}}" in next(b for b in abbreviated if b["kind"] == "paragraph")["text"]
    again = import_author_manuscript(
        result / "manuscript.docx", result / "candidate", tmp_path / "again"
    )
    assert read(again / "merge.json")["conflicts"] == []
    assert (
        sum(
            b.get("reference_labels") == {"figure": "Fig."}
            for b in read_word_return(again / "manuscript.docx")["blocks"]
        )
        == 2
    )
