"""Public task connects original regions, the real figure, and writing context."""

import json
from copy import deepcopy
from pathlib import Path

from cfdpaper import host_tools
from tests.test_surface_partition_figure import fixture


def test_changed_image_invalidates_only_its_previous_visual_reading(tmp_path):
    from cfdpaper.publication.research_workspace import (
        _figure_observation_images,
        _invalidate_changed_figure_observations,
    )

    section = tmp_path / "sections/results"
    section.mkdir(parents=True)
    (tmp_path / "manuscript-input.json").write_text(
        json.dumps(
            {"sections": [{"section_id": "results", "input": "sections/results/input.json"}]}
        ),
        encoding="utf-8",
    )
    (section / "input.json").write_text(
        json.dumps({"figures": [{"id": f, "path": f + ".png"} for f in ("field", "other")]}),
        encoding="utf-8",
    )
    for name in ("field", "other"):
        (section / (name + ".png")).write_bytes(name.encode())
    draft_path = section / "draft.json"
    original = {
        "paragraphs": [{"text": "Author interpretation retained for explicit revision."}],
        "captions": {"field": "Author caption"},
        "image_observations": {"field": "viewed", "other": "author-provided"},
        "observation_notes": {"field": "Old field observed", "other": "Unchanged note"},
    }
    draft_path.write_text(json.dumps(original), encoding="utf-8")
    before = _figure_observation_images(tmp_path)
    _invalidate_changed_figure_observations(tmp_path, before)
    assert json.loads(draft_path.read_text()) == original
    (section / "field.png").write_bytes(b"new field")
    _invalidate_changed_figure_observations(tmp_path, before)
    current = json.loads(draft_path.read_text())
    assert current["image_observations"] == {"field": "not-viewed", "other": "author-provided"}
    assert current["observation_notes"] == {"other": "Unchanged note"}
    assert current["paragraphs"] == original["paragraphs"]
    assert current["captions"] == original["captions"]
    # An already-unviewed draft is not needlessly rewritten on a later redraw.
    prior = _figure_observation_images(tmp_path)
    raw = draft_path.read_bytes()
    (section / "field.png").write_bytes(b"another field")
    _invalidate_changed_figure_observations(tmp_path, prior)
    assert draft_path.read_bytes() == raw


def test_object_diagnostics_keep_figure_reading_and_author_caption_current(tmp_path):
    materials = tmp_path / "materials"
    materials.mkdir()
    study_path, _, study, diagnostic = fixture(materials)
    (materials / "sources/definition.md").write_text(
        "Synthetic area-weighted wall.\n", encoding="utf-8"
    )
    study.update(
        title="Regional temperature comparison",
        question="Which regions change the mean?",
        time_support="Saved steady observations",
        common_conditions=["Same synthetic wall"],
        definition={"source": "sources/definition.md", "text": "Original face area weighting"},
        selected_figures=[],
    )
    study_path.write_text(json.dumps(study), encoding="utf-8")
    original = deepcopy(diagnostic)
    host_tools.research_task(tmp_path / "prepared", study=study_path)
    template = json.loads((tmp_path / "prepared/sections/results/draft.json").read_text())
    assert template["tables"][0]["columns"][2] == "Spatial SD"
    assert template["tables"][0]["columns"][3].startswith("Area fraction above ")
    result = host_tools.research_task(
        tmp_path / "attached",
        workspace=tmp_path / "prepared",
        diagnostics=diagnostic,
        diagnostic_figure={"surface_partition_panel": "contributions"},
    )
    assert diagnostic == original
    figure = result["context"]["selected_figures"][0]
    assert figure["id"] == "contributions"
    assert (tmp_path / "attached" / figure["preview"]).is_file()
    assert figure["image_observation"] == "not-viewed"
    binding = figure["reading"]["comparisons"][0]
    assert binding["calculation_id"] == "change-A"
    assert binding["reference"]["case_id"] == "A-reference"
    assert binding["comparison"]["case_id"] == "A-comparison"
    assert "source_path" not in binding["reference"]
    assert all(set(group) <= {"group", "status", "result"} for group in binding["results"])
    root = tmp_path / "attached"
    # Building a manuscript synchronizes declarations again. That sync must
    # retain the study dependency used by the linked original-face renderer.
    from cfdpaper.publication.research_workspace import _sync_diagnostics

    _sync_diagnostics(root)
    recipe = next(
        r
        for r in json.loads((root / "figure-recipes.json").read_text())
        if r["id"] == "physical-diagnostics"
    )
    assert "sections/results/study.json" in recipe["inputs"]
    assert all((root / name).is_file() for name in recipe["outputs"])
    assert any(name.endswith("-field-source-data.csv") for name in recipe["outputs"])
    # A prose-only return must not present the old cached caption as current.
    path = root / "sections/results/draft.json"
    draft = json.loads(path.read_text())
    draft["captions"]["contributions"] = "Author caption after actual figure inspection."
    draft["image_observations"]["contributions"] = "viewed"
    path.write_text(json.dumps(draft), encoding="utf-8")
    reread = host_tools._research_response("research-revision", root)
    current = reread["context"]["selected_figures"][0]
    assert current["caption"] == draft["captions"]["contributions"]
    assert current["image_observation"] == "viewed"
    assert current["reading"] == figure["reading"]
    assert Path(reread["artifacts"][recipe["script"]]).is_file()
