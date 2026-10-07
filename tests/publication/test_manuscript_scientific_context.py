"""Scientific relationship transport through real manuscript preparation and editing."""

import json
import shutil

import pytest

from cfdpaper.publication.manuscript import (
    assemble_manuscript,
    prepare_manuscript,
    prepare_writing_context,
)
from cfdpaper.publication.manuscript_review import prepare_manuscript_review
from cfdpaper.publication.manuscript_seed import prepare_manuscript_seed


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def study(root):
    sections, contracts, drafts = [], [], {}
    for sid, role in (("methods", "methods"), ("results", "results")):
        save(
            root / sid / "input.json",
            {
                "section_id": sid,
                "title": sid.title(),
                "question": "What do the supplied comparison records establish?",
                "figures": [],
                "evidence": [
                    {
                        "id": "basis",
                        "kind": "observation",
                        "text": "Study record",
                        "source": "author-supplied",
                    }
                ],
                "duties": [
                    {
                        "purpose": "Explain the comparison",
                        "evidence_ids": ["basis"],
                        "figure_ids": [],
                    }
                ],
            },
        )
        save(
            root / sid / "draft.json",
            {
                "title": sid.title(),
                "paragraphs": [
                    {
                        "text": "Author scientific prose.",
                        "evidence_ids": ["basis"],
                        "figure_ids": [],
                    }
                ],
                "captions": {},
                "image_observations": {},
                "evidence_notes": [],
            },
        )
        sections.append({"section_id": sid, "input": f"{sid}/input.json"})
        if sid == "results":
            sections[-1]["depends_on"] = ["methods"]
        contracts.append(
            {
                "section_id": sid,
                "role": role,
                "title": sid.title(),
                "purpose": "Explain the study",
                "required_claim_ids": ["basis"],
            }
        )
        drafts[sid] = f"{sid}/draft.json"
    source = root / "methods.txt"
    source.write_text(
        "Control uses a frozen-flow thermal stage, then a coupled check.\n"
        "Modified reports a complete-wall area-weighted temperature.\n",
        encoding="utf-8",
    )
    science = {
        "cases": [{"id": "Control"}, {"id": "Modified"}],
        "facts": [
            {
                "id": "sequence",
                "case_ids": ["Control"],
                "section_ids": ["methods"],
                "kind": "solution-stage",
                "name": "Solution sequence",
                "text": "Thermal-only warm start followed by a coupled check.",
                "stage": "thermal then coupled",
                "source": {
                    "path": "methods.txt",
                    "locator": "L1",
                    "excerpt": "Control uses a frozen-flow thermal stage, then a coupled check.",
                },
            },
            {
                "id": "operator",
                "case_ids": ["Modified"],
                "section_ids": ["results"],
                "kind": "operator",
                "name": "Wall temperature",
                "text": "The temperature is area weighted over the complete wall.",
                "domain": "complete wall",
                "operator": "area-weighted mean",
                "source": {
                    "path": "methods.txt",
                    "locator": "L2",
                    "excerpt": "Modified reports a complete-wall area-weighted temperature.",
                },
            },
        ],
        "comparisons": [
            {
                "id": "comparison",
                "case_ids": ["Control", "Modified"],
                "section_ids": ["results"],
                "fact_ids": ["sequence", "operator"],
                "status": "unknown",
                "text": "Full comparison conditions are pending.",
            }
        ],
    }
    save(root / "science.json", science)
    manifest = {
        "title": "Synthetic comparison",
        "context": "Software fixture",
        "spine": {"topic_id": "study", "central_claim_id": "basis", "sections": contracts},
        "sections": sections,
        "scientific_context": "science.json",
    }
    return save(root / "input.json", manifest), save(root / "drafts.json", drafts)


def test_science_is_copied_selected_and_not_published_as_prose(tmp_path):
    source, drafts = study(tmp_path)
    package = prepare_manuscript(source, tmp_path / "package")
    manifest = read(package / "manuscript-input.json")
    assert manifest["scientific_context"] == "scientific-context/context.json"
    methods = read(package / "sections/methods/scientific-context/context.json")
    assert [f["id"] for f in methods["facts"]] == ["sequence"]
    assert "frozen-flow" in (package / "sections/methods/scientific-context.md").read_text()
    result_context = read(package / "sections/results/manuscript-context.json")
    assert result_context["scientific_context"] == "scientific-context/context.json"
    results = read(package / "sections/results/scientific-context/context.json")
    assert results["comparisons"][0]["status"] == "unknown"
    assert results["facts"][0]["case_ids"] == ["Control"]
    candidate = assemble_manuscript(package, drafts, tmp_path / "candidate")
    assert "Author scientific prose." in (candidate / "manuscript.md").read_text()
    assert "Full comparison conditions are pending" not in (candidate / "manuscript.md").read_text()
    assert (candidate / "sections/results/review-packet/scientific-context/context.json").is_file()


def test_context_and_candidate_survive_without_original_material(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    source, drafts = study(original)
    manifest = read(source)
    for item in manifest["sections"]:
        item["draft"] = str((original / drafts.name).parent / item["section_id"] / "draft.json")
        item["input"] = str(original / item["input"])
    manifest["scientific_context"] = str(original / "science.json")
    save(original / "outline.json", manifest)
    package = prepare_manuscript_seed(original / "outline.json", tmp_path / "prepared")
    moved = tmp_path / "moved"
    shutil.move(str(package), moved)
    shutil.rmtree(original)
    context = prepare_writing_context(
        moved, "results", tmp_path / "task", drafts_path=moved / "drafts.json"
    )
    data = read(context / "context.json")
    assert data["scientific_context_path"] == "scientific-context/context.json"
    assert data["scientific_context"]["facts"][0]["stage"] == "thermal then coupled"
    assert "Scientific context" in (context / "scientific-context.md").read_text()
    candidate = assemble_manuscript(moved, moved / "drafts.json", tmp_path / "candidate")
    review = prepare_manuscript_review(candidate, tmp_path / "review")
    assert review["kind"] == "manuscript-review"
    assert (tmp_path / "review/manuscript/scientific-context/context.json").is_file()


def test_unknown_section_is_rejected_before_output(tmp_path):
    source, _ = study(tmp_path)
    data = read(tmp_path / "science.json")
    data["facts"][0]["section_ids"] = ["invented-section"]
    save(tmp_path / "science.json", data)
    with pytest.raises(ValueError, match="Unknown section"):
        prepare_manuscript(source, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


def test_changed_method_fact_and_source_reach_dependent_passages(tmp_path):
    source, drafts = study(tmp_path)
    package = prepare_manuscript(source, tmp_path / "package")
    baseline = assemble_manuscript(package, drafts, tmp_path / "baseline")
    record = baseline / "scientific-context/context.json"
    science = read(record)
    fact = science["facts"][0]
    fact["text"] = "Thermal warm start followed by twenty coupled iterations."
    changed_excerpt = "Control uses a frozen-flow thermal stage, then twenty coupled iterations."
    location = record.parent / fact["source"]["path"]
    old = location.read_text(encoding="utf-8")
    location.write_text(old.replace(fact["source"]["excerpt"], changed_excerpt), encoding="utf-8")
    fact["source"]["excerpt"] = changed_excerpt
    save(record, science)
    updated = assemble_manuscript(baseline, baseline / "drafts.json", tmp_path / "updated")
    changes = read(updated / "changes.json")
    assert set(changes["affected_sections"]) == {"methods", "results"}
    assert any(c["category"] == "scientific" for c in changes["changes"])
    assert changes["affected_passages"]["methods"][0]["text"] == "Author scientific prose."
    assert (baseline / "sections/methods/draft.json").read_bytes() == (
        updated / "sections/methods/draft.json"
    ).read_bytes()


def test_changed_source_cannot_keep_an_old_excerpt(tmp_path):
    source, _ = study(tmp_path)
    package = prepare_manuscript(source, tmp_path / "package")
    science = read(package / "scientific-context/context.json")
    path = package / "scientific-context" / science["facts"][0]["source"]["path"]
    path.write_text("Replacement solver record\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exact lines|out of bounds"):
        prepare_writing_context(package, "methods", tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


def test_method_parameters_are_visible_without_new_host_fact_for_each_number(tmp_path):
    source, _ = study(tmp_path)
    science = read(tmp_path / "science.json")
    settings = {
        "materials": {"solid": {"conductivity": 16.3}},
        "boundary_conditions": {"outlet": {"pressure": 0}},
    }
    path = save(tmp_path / "settings.json", settings)
    lines = path.read_text(encoding="utf-8").splitlines()
    for fact in science["facts"]:
        fact["source"] = {
            "path": "settings.json",
            "locator": "L1-L" + str(len(lines)),
            "excerpt": "\n".join(lines),
        }
    save(tmp_path / "science.json", science)
    package = prepare_manuscript(source, tmp_path / "package")
    context = read(package / "sections/methods/scientific-context/context.json")
    fields = context["source_parameters"]["sources"][0]["entries"]
    assert {x["pointer"]: x["value"] for x in fields} == {
        "/materials/solid/conductivity": 16.3,
        "/boundary_conditions/outlet/pressure": 0,
    }
    assert "16.3" in (package / "sections/methods/scientific-context.md").read_text()
    assert context["facts"][0]["case_ids"] == ["Control"]
