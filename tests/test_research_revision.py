"""Explicit host revisions preserve the surrounding scientific author workspace."""

from copy import deepcopy
from pathlib import Path

import pytest

from cfdpaper.publication.manuscript import _inputs, assemble_manuscript
from tests.publication.test_manuscript import fixture, read, write


def workspace(tmp_path):
    root = tmp_path / "author"
    root.mkdir()
    manifest, _ = fixture(root)
    manifest.rename(root / "manuscript-input.json")
    for sid in ("methods", "response", "transport"):
        path = root / sid / "draft.json"
        draft = read(path)
        draft["paragraphs"][0]["paragraph_id"] = "main"
        draft["paragraphs"].append(
            {
                "paragraph_id": "retained",
                "text": "Author's untouched paragraph.",
                "evidence_ids": [],
                "figure_ids": [],
            }
        )
        draft["block_order"] = [
            "paragraph:main",
            "table:same",
            "equation:same",
            "figure:same",
            "paragraph:retained",
        ]
        write(path, draft)
    # This fact has an unambiguous owner and no conflicting local alias.
    path = root / "response/input.json"
    data = read(path)
    data["evidence"].append(
        {
            "id": "contrast",
            "kind": "metric",
            "text": "Observed contrast",
            "source": "test row",
            "value": "2",
            "unit": "K",
        }
    )
    write(path, data)
    (root / "response/author-plot.py").write_text(
        "# Author's plotting parameters\n", encoding="utf-8"
    )
    return root


def proposal(root):
    draft = read(root / "transport/draft.json")
    return {
        "paragraphs": [
            {
                "section_id": "transport",
                "paragraph_id": "main",
                "before": draft["paragraphs"][0]["text"],
                "text": "Host interpretation uses {{value:metric}} and {{value:contrast}}; "
                "{{figure:same}} and {{figure:response/same}} complement one another, "
                "with {{cite:unique}} and {{cite:ref}}.",
                "evidence_refs": [
                    "transport/metric",
                    "response/contrast",
                    "transport/unique",
                    "transport/ref",
                ],
                "figure_ids": ["same"],
            }
        ],
        "captions": [
            {
                "section_id": "response",
                "figure_id": "same",
                "before": read(root / "response/draft.json")["captions"]["same"],
                "text": "Current comparison in {{figure:same}}; {{value:metric}}.",
                "image_observation": "viewed",
                "observation_note": "Host read the current image.",
            }
        ],
    }


def api():
    from cfdpaper.publication.research_revision import apply_research_revision

    return apply_research_revision


def test_revision_addresses_existing_implicit_identity_and_native_inline_math(tmp_path):
    from cfdpaper.publication.document_blocks import paragraph_identity

    root = workspace(tmp_path)
    path = root / "transport/draft.json"
    draft = read(path)
    old = draft["paragraphs"][0]
    old.pop("paragraph_id")
    identity = paragraph_identity(old["text"], 0)
    draft["block_order"][0] = "paragraph:" + identity
    write(path, draft)
    patch = {
        "paragraphs": [
            {
                "section_id": "transport",
                "paragraph_id": identity,
                "before": old["text"],
                "text": old["text"] + " {{math:partition}}",
                "inline_math": {"partition": {"kind": "text", "text": "ΔT = w ΔTr"}},
            }
        ]
    }
    candidate = api()(root, patch, tmp_path / "revised")
    revised = read(candidate / "transport/draft.json")
    assert revised["paragraphs"][0]["paragraph_id"] == identity
    assert revised["paragraphs"][0]["inline_math"]["partition"]["text"] == "ΔT = w ΔTr"
    assert revised["block_order"] == draft["block_order"]
    assert "paragraph_id" not in read(path)["paragraphs"][0]


def test_revision_does_not_overwrite_an_author_formula_with_unchanged_body_text(tmp_path):
    root = workspace(tmp_path)
    old = read(root / "transport/draft.json")["paragraphs"][0]
    assert old["inline_math"]
    name = next(iter(old["inline_math"]))
    patch = {
        "paragraphs": [
            {
                "section_id": "transport",
                "paragraph_id": "main",
                "before": old["text"],
                "text": old["text"],
                "inline_math": {name: {"kind": "symbol", "text": "Different"}},
            }
        ]
    }
    output = tmp_path / "revised"
    with pytest.raises(ValueError, match="author formula differs"):
        api()(root, patch, output)
    assert not output.exists()


def test_explicit_revision_preserves_unselected_author_material_and_validates_bindings(tmp_path):
    source = workspace(tmp_path)
    original = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
    before = read(source / "transport/draft.json")
    result = api()(source, proposal(source), tmp_path / "candidate")
    assert result == (tmp_path / "candidate").resolve()
    updated = read(result / "transport/draft.json")
    assert updated["paragraphs"][0]["paragraph_id"] == "main"
    assert updated["paragraphs"][0]["evidence_ids"] == ["metric", "contrast", "unique", "ref"]
    assert updated["paragraphs"][1] == before["paragraphs"][1]
    for key in ("tables", "equations", "block_order", "evidence_notes", "captions"):
        assert updated[key] == before[key]
    caption = read(result / "response/draft.json")
    assert caption["image_observations"]["same"] == "viewed"
    assert caption["observation_notes"]["same"] == "Host read the current image."
    entries = {e["section_id"]: e for e in read(result / "manuscript-input.json")["sections"]}
    assert entries["transport"]["evidence_bindings"] == {"contrast": "response/contrast"}
    assert any(
        e.id == "contrast"
        for e in _inputs(result / "manuscript-input.json")[1]["transport"][1].evidence
    )
    for name, content in original.items():
        assert (source / name).read_bytes() == content
        if name not in {
            Path("manuscript-input.json"),
            Path("transport/draft.json"),
            Path("response/draft.json"),
        }:
            assert (result / name).read_bytes() == content


@pytest.mark.parametrize("target", ["paragraph", "caption"])
def test_author_changes_are_not_overwritten_and_failed_revision_has_no_output(tmp_path, target):
    source = workspace(tmp_path)
    change = proposal(source)
    change["paragraphs" if target == "paragraph" else "captions"][0]["before"] = "Old author text"
    output = tmp_path / "candidate"
    with pytest.raises(ValueError, match="Current text changed"):
        api()(source, change, output)
    assert not output.exists()


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("section_id", "missing", "Unknown section"),
        ("paragraph_id", "missing", "Unknown or ambiguous paragraph"),
        ("evidence_refs", ["response/missing"], "Unknown evidence"),
        ("evidence_refs", ["response/metric"], "author-owned local evidence"),
        ("text", "Missing {{value:missing}}", "Unknown or undeclared value"),
        ("text", "Missing {{figure:missing}}", "Unknown or undeclared figure"),
        ("text", "Missing {{figure:response/missing}}", "Unknown cross-section figure"),
        ("text", "Missing {{value:metric", "malformed"),
        ("figure_ids", ["missing"], "Unresolved IDs"),
    ],
)
def test_invalid_target_reference_or_token_is_rejected(tmp_path, field, value, match):
    source = workspace(tmp_path)
    change = proposal(source)
    change["paragraphs"][0][field] = value
    output = tmp_path / "candidate"
    with pytest.raises(ValueError, match=match):
        api()(source, change, output)
    assert not output.exists()


def test_existing_explicit_alias_is_reused_without_duplicate_evidence(tmp_path):
    source = workspace(tmp_path)
    path = source / "manuscript-input.json"
    manifest = read(path)
    manifest["sections"][2]["evidence_bindings"] = {"borrowed": "response/contrast"}
    write(path, manifest)
    change = proposal(source)
    change["paragraphs"][0]["text"] = (
        "Current {{value:metric}} and {{value:borrowed}} in {{figure:same}}."
    )
    result = api()(source, change, tmp_path / "candidate")
    assert read(result / "transport/draft.json")["paragraphs"][0]["evidence_ids"] == [
        "metric",
        "borrowed",
        "unique",
        "ref",
    ]
    assert read(result / "manuscript-input.json")["sections"][2]["evidence_bindings"] == {
        "borrowed": "response/contrast"
    }


def test_duplicate_target_and_empty_revision_are_rejected(tmp_path):
    source = workspace(tmp_path)
    change = proposal(source)
    change["paragraphs"].append(deepcopy(change["paragraphs"][0]))
    with pytest.raises(ValueError, match="Duplicate revision target"):
        api()(source, change, tmp_path / "duplicate")
    with pytest.raises(ValueError, match="nonempty"):
        api()(source, {}, tmp_path / "empty")
    assert not (tmp_path / "duplicate").exists()
    assert not (tmp_path / "empty").exists()


def test_omitted_evidence_and_figure_lists_keep_author_declarations(tmp_path):
    source = workspace(tmp_path)
    change = proposal(source)
    change["paragraphs"][0].pop("evidence_refs")
    change["paragraphs"][0].pop("figure_ids")
    change["paragraphs"][0]["text"] = "Host wording with {{value:metric}} in {{figure:same}}."
    result = api()(source, change, tmp_path / "candidate")
    before = read(source / "transport/draft.json")["paragraphs"][0]
    after = read(result / "transport/draft.json")["paragraphs"][0]
    assert after["evidence_ids"] == before["evidence_ids"]
    assert after["figure_ids"] == before["figure_ids"]


def test_output_must_be_fresh_and_outside_original(tmp_path):
    source = workspace(tmp_path)
    with pytest.raises(ValueError, match="outside"):
        api()(source, proposal(source), source / "candidate")
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(FileExistsError):
        api()(source, proposal(source), output)


def test_revised_workspace_uses_normal_assembly_without_numbering_or_object_loss(tmp_path):
    source = workspace(tmp_path)
    baseline = assemble_manuscript(source, source / "drafts.json", tmp_path / "baseline")
    revised = api()(source, proposal(source), tmp_path / "candidate")
    updated = assemble_manuscript(revised, revised / "drafts.json", tmp_path / "assembled")
    old_numbers = read(baseline / "numbering.json")
    new_numbers = read(updated / "numbering.json")
    for sid in old_numbers["sections"]:
        for kind in ("figure", "table", "equation"):
            assert old_numbers["sections"][sid][kind] == new_numbers["sections"][sid][kind]
    assert old_numbers["references"] == new_numbers["references"]
    before = read(baseline / "section.json")
    after = read(updated / "section.json")
    for key in ("tables", "equations"):
        assert before[key] == after[key]
    assert [f["id"] for f in before["figures"]] == [f["id"] for f in after["figures"]]
    assert "Host interpretation uses 2.00 K and 2 K" in (updated / "manuscript.md").read_text(
        encoding="utf-8"
    )
