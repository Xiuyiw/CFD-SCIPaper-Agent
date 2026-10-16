"""Connected synthetic workspace lifecycle, not a scientific validation claim."""

import json
import shutil

import numpy as np
import pytest
from docx import Document
from PIL import Image, ImageDraw

from cfdpaper.publication.figure_tasks import import_figure_task, prepare_figure_task
from cfdpaper.publication.research_workspace import (
    attach_imported_figure,
    build_research_workspace,
    prepare_surface_workspace,
)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def study(root):
    (root / "sources").mkdir(parents=True)
    (root / "sources/definition.md").write_text(
        "Synthetic common-wall face values, physical areas, and final steady support.\n",
        encoding="utf-8",
    )
    vertices = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [4, 0, 0], [4, 1, 0]]
    for index, case in enumerate(("A", "B")):
        np.savez(
            root / f"sources/{case}.npz",
            face_value=[300.0 + 10 * index, 400.0 + 10 * index],
            area_m2=[1.0, 3.0],
            vertices_m=vertices,
            faces_connectivity=[4, 0, 1, 2, 3, 4, 1, 4, 5, 2],
            face_starts=[0, 5],
        )
    data = {
        "study_id": "surface-comparison",
        "title": "Synthetic surface comparison",
        "question": "How do these declared wall observations differ?",
        "time_support": "Final saved steady result",
        "common_conditions": ["Same wall domain", "Same prescribed heat load"],
        "definition": {"source": "sources/definition.md", "text": "Area-weighted face temperature"},
        "domain": "test wall",
        "quantity": "Temperature",
        "unit": "K",
        "coordinate_unit": "m",
        "projection_axes": [0, 1],
        "thresholds": [373.15],
        "arrays": {
            "values": "face_value",
            "weights": "area_m2",
            "vertices": "vertices_m",
            "connectivity": "faces_connectivity",
            "starts": "face_starts",
        },
        "cases": [
            {"id": case, "label": f"Case {case}", "source": f"sources/{case}.npz"}
            for case in ("A", "B")
        ],
    }
    write(root / "study.json", data)
    return root / "study.json"


def fill_drafts(workspace):
    for sid, name in read(workspace / "drafts.json").items():
        path = workspace / name
        draft, section = read(path), read(path.parent / "input.json")
        ids = [item["id"] for item in section["evidence"]]
        figures = [item["id"] for item in section["figures"]]
        text = (
            f"Author's distinct {sid} wording. "
            "A has {{value:A-mean}} with spread {{value:A-std}} and area {{value:A-exceedance-1}}; "
            "B has {{value:B-mean}}."
        )
        if figures:
            text += " {{figure:field}} and {{figure:distribution}}; {{table:surface-summary}}."
        draft["paragraphs"] = [{"text": text, "evidence_ids": ids, "figure_ids": figures}]
        draft["image_observations"] = {key: "author-provided" for key in figures}
        draft["captions"] = {key: "Author caption for " + key for key in figures}
        write(path, draft)


@pytest.fixture(scope="module")
def assets(tmp_path_factory):
    root = tmp_path_factory.mktemp("research-assets")
    source = study(root / "materials")
    prepared = prepare_surface_workspace(source, root / "prepared")
    filled = root / "filled"
    shutil.copytree(prepared, filled)
    fill_drafts(filled)
    built = build_research_workspace(filled, root / "baseline")
    return source, prepared, filled, built


@pytest.fixture(scope="module")
def figure_candidate(tmp_path_factory):
    root = tmp_path_factory.mktemp("figure-candidate")
    (root / "context.md").write_text("Synthetic interpretation, not physical validation.\n")
    write(
        root / "task.json",
        {
            "figure_id": "mechanism",
            "kind": "schematic",
            "purpose": "Synthetic mechanism drawing",
            "claim_ceiling": "Conceptual interpretation only",
            "sources": [
                {
                    "id": "context",
                    "path": "context.md",
                    "role": "context",
                    "description": "Synthetic context",
                }
            ],
            "labels": [{"text": "Synthetic pathway", "unit": ""}],
            "final_width_mm": 100,
        },
    )
    task = prepare_figure_task(root / "task.json", root / "task")
    returned = root / "returned"
    (returned / "artwork").mkdir(parents=True)
    (returned / "artwork/figure.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><rect width="100" height="40"/></svg>'
    )
    preview = Image.new("RGB", (800, 400), "white")
    ImageDraw.Draw(preview).rectangle((20, 20, 780, 380), outline="black", width=3)
    preview.save(returned / "artwork/figure.png")
    (returned / "artwork/legend.txt").write_text("A synthetic diagram, not a field plot.\n")
    write(
        returned / "delivery.json",
        {
            "figure_id": "mechanism",
            "editable_sources": ["artwork/figure.svg"],
            "preview": "artwork/figure.png",
            "caption": "Conceptual synthesis of {{figure:results/field}}; no causal validation.",
            "title": "Synthetic interpretation",
            "legend": "Solid outline indicates a synthetic object.",
            "body_reference": (
                "The interpretation in {{figure:mechanism}} is constrained by "
                "{{figure:results/field}}, without establishing transport causation."
            ),
            "exports": ["artwork/legend.txt"],
            "sizing": {"source_width_mm": 100, "minimum_source_font_pt": 10},
        },
    )
    return import_figure_task(task, returned / "delivery.json", root / "imported")


def clone(assets, tmp_path):
    baseline = assets[3]
    root = tmp_path / "working"
    shutil.copytree(baseline / "workspace", root)
    return root, baseline


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def scalar(data, sid, identity):
    return data["resolved_values"][json.dumps([sid, identity], separators=(",", ":"))]["raw_value"]


def test_prepare_has_real_fields_definitions_and_empty_host_templates(assets):
    source, prepared, _, _ = assets
    for name in ("A.npz", "B.npz", "definition.md"):
        assert (prepared / "sections/results/sources" / name).read_bytes() == (
            source.parent / "sources" / name
        ).read_bytes()
    assert read(prepared / "sections/results/study.json")["unit"] == "K"
    assert (prepared / "sections/results/figures/plot.py").is_file()
    assert (prepared / "sections/results/figures/field.svg").is_file()
    assert (prepared / "sections/results/figures/distribution-source-data.csv").is_file()
    manifest = read(prepared / "manuscript-input.json")
    assert [entry["section_id"] for entry in manifest["sections"]] == [
        "methods",
        "results",
        "discussion",
        "conclusion",
    ]
    for name in read(prepared / "drafts.json").values():
        assert read(prepared / name)["paragraphs"][0]["text"] == ""
    section = read(prepared / "sections/results/input.json")
    fraction = next(item for item in section["evidence"] if item["id"] == "A-exceedance-1")
    assert fraction["result_ref"]["percentage"] is True
    assert (prepared / "RESEARCH.md").is_file()
    assert not (prepared / "manuscript.docx").exists()


def test_build_native_word_table_and_cross_section_values(assets):
    built = assets[3]
    data = read(built / "manuscript/section.json")
    assert scalar(data, "results", "A-mean") == 375
    assert scalar(data, "conclusion", "A-mean") == 375
    assert scalar(data, "results", "A-exceedance-1") == 0.75
    document = Document(built / "manuscript.docx")
    assert len(document.tables) == 1
    assert "75.000" in document.tables[0].rows[1].cells[3].text
    assert "%" in document.tables[0].rows[1].cells[3].text
    assert len(document.inline_shapes) == 2
    assert [figure["caption"] for figure in data["figures"]] == [
        "Author caption for field",
        "Author caption for distribution",
    ]


def test_source_update_refreshes_images_tables_bindings_but_preserves_author_text(assets, tmp_path):
    work, old = clone(assets, tmp_path)
    before = snapshot(old)
    path = work / "sections/results/sources/A.npz"
    with np.load(path) as bundle:
        arrays = {key: bundle[key].copy() for key in bundle.files}
    arrays["face_value"][0] = 380
    np.savez(path, **arrays)
    drafts = {name: (work / name).read_bytes() for name in read(work / "drafts.json").values()}
    result = build_research_workspace(work, tmp_path / "updated", baseline_dir=old)
    data = read(result / "manuscript/section.json")
    assert scalar(data, "results", "A-mean") == 395
    assert scalar(data, "discussion", "A-mean") == 395
    assert scalar(data, "conclusion", "A-mean") == 395
    assert scalar(data, "results", "A-exceedance-1") == 1
    assert "100.000" in Document(result / "manuscript.docx").tables[0].rows[1].cells[3].text
    for name, raw in drafts.items():
        assert (result / "workspace" / name).read_bytes() == raw
    assert (result / "workspace/sections/results/figures/field.png").read_bytes() != (
        old / "workspace/sections/results/figures/field.png"
    ).read_bytes()
    assert read(result / "refresh.json")["figure_recipes"][0]["status"] == "executed"
    assert read(result / "refresh.json")["interpretation_review_required"] is True
    assert read(result / "manuscript/changes.json")["baseline_available"] is True
    assert snapshot(old) == before


def test_author_script_style_and_caption_remain_the_refresh_entry(assets, tmp_path):
    work, old = clone(assets, tmp_path)
    script = work / "sections/results/figures/plot.py"
    script.write_text(
        script.read_text().replace("'height_mm': 110", "'height_mm': 115"), encoding="utf-8"
    )
    author_script = script.read_bytes()
    result = build_research_workspace(work, tmp_path / "restyled", baseline_dir=old)
    assert (result / "workspace/sections/results/figures/plot.py").read_bytes() == author_script
    summary = read(result / "workspace/sections/results/figures/surface-figures.json")
    assert summary["style"]["height_mm"] == 115
    assert read(result / "refresh.json")["interpretation_review_required"] is False
    assert (
        read(result / "manuscript/section.json")["figures"][0]["caption"]
        == "Author caption for field"
    )


def test_definition_update_requires_interpretation_review_not_rewritten_prose(assets, tmp_path):
    work, old = clone(assets, tmp_path)
    path = work / "sections/results/study.json"
    data = read(path)
    data["thresholds"] = [450]
    data["time_support"] = "Declared alternate support, requires host reconciliation"
    write(path, data)
    draft = (work / "sections/discussion/draft.json").read_bytes()
    result = build_research_workspace(work, tmp_path / "definition-update", baseline_dir=old)
    refresh = read(result / "refresh.json")
    assert refresh["interpretation_review_required"] is True
    assert set(refresh["definition_changes"]) == {"thresholds", "time_support"}
    assert scalar(read(result / "manuscript/section.json"), "results", "A-exceedance-1") == 0
    assert "450.000" in Document(result / "manuscript.docx").tables[0].rows[0].cells[3].text
    assert (result / "workspace/sections/discussion/draft.json").read_bytes() == draft
    assert "Interpretation review required" in (result / "CHANGES.md").read_text(encoding="utf-8")


def test_unchanged_relocated_workspace_preserves_current_figures_and_drafts(assets, tmp_path):
    work, old = clone(assets, tmp_path)
    preserved = snapshot(work)
    result = build_research_workspace(work, tmp_path / "relocated", baseline_dir=old)
    assert read(result / "refresh.json")["figure_recipes"][0]["status"] == "unchanged"
    assert read(result / "manuscript/changes.json")["changes"] == []
    for name, raw in preserved.items():
        if name.endswith("draft.json") or "/figures/" in name:
            assert (result / "workspace" / name).read_bytes() == raw


@pytest.mark.parametrize("failure", ["script", "empty-draft"])
def test_failure_does_not_publish_partial_build_or_modify_inputs(assets, tmp_path, failure):
    work, old = clone(assets, tmp_path)
    if failure == "script":
        (work / "sections/results/figures/plot.py").write_text(
            "raise RuntimeError('fixture failure')\n"
        )
    else:
        path = work / "sections/methods/draft.json"
        data = read(path)
        data["paragraphs"][0]["text"] = ""
        write(path, data)
    original = snapshot(work)
    output = tmp_path / "failed"
    with pytest.raises((ValueError, RuntimeError)):
        build_research_workspace(work, output, baseline_dir=old)
    assert not output.exists()
    assert snapshot(work) == original


def test_prepare_and_build_refuse_overwrite_or_nested_output(assets, tmp_path):
    source, prepared, _, old = assets
    with pytest.raises(FileExistsError):
        prepare_surface_workspace(source, prepared)
    with pytest.raises(ValueError, match="outside"):
        build_research_workspace(old / "workspace", old / "workspace/nested")
    with pytest.raises(ValueError, match="outside"):
        build_research_workspace(old / "workspace", old)


def test_imported_figure_builds_with_global_numbering_and_preserved_sources(
    assets, figure_candidate, tmp_path
):
    work, baseline = clone(assets, tmp_path)
    discussion_input = work / "sections/discussion/input.json"
    section = read(discussion_input)
    section["evidence"] = [record for record in section["evidence"] if record["id"] != "A-mean"]
    write(discussion_input, section)
    original, imported_original = snapshot(work), snapshot(figure_candidate)
    old_draft = read(work / "sections/discussion/draft.json")
    attached = attach_imported_figure(
        work,
        figure_candidate,
        tmp_path / "attached",
        section_id="discussion",
        evidence_ids=["A-mean", "study-definition"],
        image_observation="viewed",
        observation_note="The caller inspected this synthetic outline.",
        paragraph_index=0,
    )
    new_draft = read(attached / "sections/discussion/draft.json")
    assert new_draft["paragraphs"][1:] == old_draft["paragraphs"]
    assert new_draft["image_observations"]["mechanism"] == "viewed"
    assert new_draft["observation_notes"]["mechanism"] == (
        "The caller inspected this synthetic outline."
    )
    for name, content in original.items():
        if name not in {
            "manuscript-input.json",
            "sections/discussion/input.json",
            "sections/discussion/draft.json",
        }:
            assert (attached / name).read_bytes() == content
    result = build_research_workspace(attached, tmp_path / "candidate", baseline_dir=baseline)
    numbering = read(result / "manuscript/numbering.json")
    assert numbering["sections"]["discussion"]["figure"] == {"mechanism": "3"}
    data = read(result / "manuscript/section.json")
    figure = data["figures"][2]
    assert figure["id"] == "3"
    assert figure["caption"] == "Conceptual synthesis of Figure 1; no causal validation."
    assert figure["sizing"]["target_width_mm"] == 100
    assert any(
        p.get("text", "").startswith("The interpretation in Figure 3")
        and "Figure 1" in p["text"]
        and p["figure_ids"] == ["3"]
        for p in data["paragraphs"]
    )
    document = Document(result / "manuscript.docx")
    assert len(document.inline_shapes) == 3
    assert document.inline_shapes[2].width.mm == pytest.approx(100)
    assert any(
        p.text.startswith("Figure 3. Conceptual synthesis of Figure 1") for p in document.paragraphs
    )
    assert read(result / "refresh.json")["figure_recipes"][0]["status"] == "unchanged"
    section = read(attached / "sections/discussion/input.json")
    expected_names = {
        "task.json",
        "delivery.json",
        "sources/context.md",
        "artwork/figure.svg",
        "artwork/figure.png",
        "artwork/legend.txt",
    }
    assert set(section["source_files"]) == {
        "sources/figure-tasks/mechanism/" + name for name in expected_names
    }
    for root in (attached, result / "workspace", result / "manuscript"):
        sources = root / "sections/discussion/sources/figure-tasks/mechanism"
        assert not (sources / "skills").exists()
        for name in expected_names:
            assert (sources / name).read_bytes() == imported_original[name]
    assert snapshot(work) == original
    assert snapshot(figure_candidate) == imported_original


@pytest.mark.parametrize("changed_definition", ["thresholds", "definition"])
def test_imported_figure_review_lists_caption_without_changed_paragraph_values(
    assets, figure_candidate, tmp_path, changed_definition
):
    work, old = clone(assets, tmp_path)
    attached = attach_imported_figure(
        work,
        figure_candidate,
        tmp_path / "attached",
        section_id="discussion",
        evidence_ids=["A-mean", "study-definition"],
    )
    baseline = build_research_workspace(attached, tmp_path / "baseline", baseline_dir=old)
    working = tmp_path / "definition-update"
    shutil.copytree(baseline / "workspace", working)
    draft_path = "sections/discussion/draft.json"
    author_draft = (working / draft_path).read_bytes()
    caption = read(working / draft_path)["captions"]["mechanism"]
    artwork_path = "sections/discussion/sources/figure-tasks/mechanism/artwork/figure.png"
    artwork = (working / artwork_path).read_bytes()
    study_path = working / "sections/results/study.json"
    data = read(study_path)
    if changed_definition == "thresholds":
        data["thresholds"] = [450]
    else:
        data["definition"]["text"] += "; revised observation interpretation"
    write(study_path, data)

    result = build_research_workspace(working, tmp_path / "updated", baseline_dir=baseline)
    refresh = read(result / "refresh.json")
    assert refresh["definition_changes"] == [changed_definition]
    assert refresh["interpretation_review_required"] is True
    assert "discussion" in refresh["interpretation_review_sections"]
    passages = read(result / "manuscript/changes.json")["affected_passages"]["discussion"]
    mechanism = next(p for p in passages if any(f["id"] == "mechanism" for f in p["figures"]))
    assert mechanism["result_changes"] == []
    assert mechanism["figures"][0]["caption"] == caption
    for root in (working, baseline / "workspace", result / "workspace", result / "manuscript"):
        assert (root / draft_path).read_bytes() == author_draft
        assert (root / artwork_path).read_bytes() == artwork
    for root in (result, result / "manuscript"):
        report = (root / "CHANGES.md").read_text(encoding="utf-8")
        assert "- Figure mechanism:" in report
        assert caption in report


def test_imported_figure_defaults_to_append_and_not_viewed(assets, figure_candidate, tmp_path):
    work, _ = clone(assets, tmp_path)
    path = work / "sections/discussion/draft.json"
    old_draft = read(path)
    attached = attach_imported_figure(
        work,
        figure_candidate,
        tmp_path / "attached",
        section_id="discussion",
        evidence_ids=[],
    )
    draft = read(attached / "sections/discussion/draft.json")
    assert draft["paragraphs"][:-1] == old_draft["paragraphs"]
    assert draft["image_observations"]["mechanism"] == "not-viewed"
    assert "mechanism" not in draft["observation_notes"]
    with pytest.raises(ValueError, match="already exists"):
        attach_imported_figure(
            attached,
            figure_candidate,
            tmp_path / "duplicate",
            section_id="discussion",
            evidence_ids=[],
        )
    with pytest.raises(FileExistsError):
        attach_imported_figure(
            work, figure_candidate, attached, section_id="discussion", evidence_ids=[]
        )
    with pytest.raises(ValueError, match="outside"):
        attach_imported_figure(
            work, figure_candidate, work / "nested", section_id="discussion", evidence_ids=[]
        )


@pytest.mark.parametrize(
    "failure",
    ["missing-token", "unknown-evidence", "section", "index", "preview", "observation", "source"],
)
def test_imported_figure_failure_preserves_inputs(assets, figure_candidate, tmp_path, failure):
    work, _ = clone(assets, tmp_path)
    imported = tmp_path / "imported"
    shutil.copytree(figure_candidate, imported)
    kwargs = {"section_id": "discussion", "evidence_ids": ["A-mean"]}
    metadata = read(imported / "delivery.json")
    if failure == "missing-token":
        metadata["body_reference"] = "Figure 3 is not a stable reference."
        write(imported / "delivery.json", metadata)
    elif failure == "unknown-evidence":
        kwargs["evidence_ids"] = ["not-an-evidence-id"]
    elif failure == "section":
        kwargs["section_id"] = "not-a-section"
    elif failure == "index":
        kwargs["paragraph_index"] = -1
    elif failure == "preview":
        (imported / metadata["preview"]).write_bytes(b"not an image")
    elif failure == "observation":
        kwargs["image_observation"] = "scientifically-approved"
    elif failure == "source":
        (imported / "sources/context.md").unlink()
    before, imported_before = snapshot(work), snapshot(imported)
    output = tmp_path / "failed"
    with pytest.raises((ValueError, OSError)):
        attach_imported_figure(work, imported, output, **kwargs)
    assert not output.exists()
    assert snapshot(work) == before
    assert snapshot(imported) == imported_before
