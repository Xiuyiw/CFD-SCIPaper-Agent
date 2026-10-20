"""A managed Word return continues through the real surface recipe workflow."""

import json
import shutil

import numpy as np
import pytest
from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from cfdpaper.publication.author_workspace import (
    describe_author_refresh,
    import_author_manuscript,
    prepare_author_manuscript,
)
from cfdpaper.publication.research_workspace import (
    build_research_workspace,
    prepare_surface_workspace,
)
from cfdpaper.publication.word_return import read_word_return
from tests.test_research_workspace import fill_drafts, read, study, write


@pytest.mark.parametrize("display,changed", [("Figure 1", False), ("Figure 2", True)])
def test_local_figure_abbreviation_keeps_actual_number_change(display, changed):
    before = {
        "blocks": [
            {
                "id": "results-paragraph",
                "section_id": "results",
                "text": "See {{figure:field}}.",
                "spans": [{"token": "{{figure:field}}", "text": "Fig. 1"}],
            }
        ]
    }
    after = {
        "blocks": [
            {
                **before["blocks"][0],
                "spans": [{"token": "{{figure:field}}", "text": display}],
            }
        ]
    }
    changes = describe_author_refresh(before, after)
    assert bool(changes) is changed
    if changed:
        assert changes[0]["after"] == {"{{figure:field}}": display}


def _real_author_candidate(root, built):
    managed = prepare_author_manuscript(built / "manuscript", root / "managed")
    doc = Document(managed / "manuscript.docx")
    edited_run = None
    for node in doc._element.iter(qn("w:t")):
        if node.text and "Author's distinct results wording." in node.text:
            node.text = node.text.replace(
                "Author's distinct results wording.", "The author's clearer results wording."
            )
            run = node.getparent()
            edited_run = next(r for r in Paragraph(run.getparent(), doc._body).runs if r._r is run)
            edited_run.bold = True
            break
    assert edited_run is not None
    doc.add_comment(edited_run, "Keep this author's sentence.", author="Research author")
    returned_docx = root / "author-return.docx"
    doc.save(returned_docx)
    returned = import_author_manuscript(returned_docx, managed / "candidate", root / "returned")
    assert read(returned / "merge.json")["conflicts"] == []
    return returned / "candidate"


def test_author_word_and_source_updates_share_the_current_recipe(tmp_path):
    source = study(tmp_path / "materials")
    workspace = prepare_surface_workspace(source, tmp_path / "workspace")
    fill_drafts(workspace)
    first = build_research_workspace(workspace, tmp_path / "first")
    authored = _real_author_candidate(tmp_path, first)
    working = tmp_path / "source-working"
    shutil.copytree(first / "workspace", working)
    script = working / "sections/results/figures/plot.py"
    script.write_text(
        script.read_text(encoding="utf-8") + "\n# Preserve this local author style entry.\n",
        encoding="utf-8",
    )
    local_script = script.read_bytes()
    data_path = working / "sections/results/sources/A.npz"
    with np.load(data_path, allow_pickle=False) as bundle:
        arrays = {key: bundle[key].copy() for key in bundle.files}
    arrays["face_value"] += 2.0
    np.savez(data_path, **arrays)
    selected = read(working / "sections/results/study.json")
    selected["thresholds"] = [500.0]
    write(working / "sections/results/study.json", selected)

    updated = build_research_workspace(
        working,
        tmp_path / "updated",
        baseline_dir=first,
        author_candidate=authored,
    )

    assert (updated / "workspace/sections/results/figures/plot.py").read_bytes() == local_script
    assert script.read_bytes() == local_script
    output = read_word_return(updated / "manuscript.docx")
    assert output["conflicts"] == []
    assert len(output["comments"]) == 1
    assert output["comments"][0]["text"] == "Keep this author's sentence."
    block = next(b for b in output["blocks"] if "clearer results wording" in b["text"])
    assert "377.00" in block["rendered_text"]
    assert "0.00" in block["rendered_text"]
    assert any(item.get("bold") for item in block["formatting"])
    assert "{{value:A-mean}}" in block["text"]
    assert read(updated / "workspace/sections/results/draft.json") == read(
        authored / "sections/results/draft.json"
    )
    refresh = read(updated / "refresh.json")
    assert refresh["interpretation_review_required"]
    assert "thresholds" in refresh["definition_changes"]
    assert refresh["interpretation_review_sections"]
    assert read(
        updated / "workspace/sections/results/sources/cfdpaper-surface-thresholds.json"
    ) == {"thresholds": [500.0]}


def test_another_author_project_is_not_spliced_into_current_research(tmp_path):
    source = study(tmp_path / "materials")
    workspace = prepare_surface_workspace(source, tmp_path / "workspace")
    fill_drafts(workspace)
    built = build_research_workspace(workspace, tmp_path / "first")
    managed = prepare_author_manuscript(built / "manuscript", tmp_path / "managed")
    candidate = managed / "candidate"
    manifest = read(candidate / "manuscript-input.json")
    manifest["title"] = "A different scientific project"
    (candidate / "manuscript-input.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="(?i)(identity|title|project|match|belong)"):
        build_research_workspace(
            built / "workspace", tmp_path / "wrong-project", author_candidate=candidate
        )
