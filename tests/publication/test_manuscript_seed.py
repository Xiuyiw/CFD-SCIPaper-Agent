"""Public synthetic seed fixtures; these test connections, not scientific writing."""

import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from cfdpaper.publication.manuscript import assemble_manuscript, prepare_writing_context
from cfdpaper.publication.manuscript_seed import prepare_manuscript_seed


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def seed_fixture(root):
    sections, contracts = [], []
    for index, sid in enumerate(("methods", "response", "transport")):
        folder = root / f"analysis-{index}" / "writing"
        (folder / "sources").mkdir(parents=True)
        (folder / "sources/definition.txt").write_text("Equal-row mean for synthetic data.\n")
        (folder / "sources/unselected.txt").write_text("Not a declared dependency.\n")
        data = {
            "section_id": sid,
            "title": sid.title(),
            "question": f"What does {sid} establish?",
            "figures": [],
            "source_files": ["sources/definition.txt"],
            "evidence": [
                {
                    "id": "definition",
                    "kind": "observation",
                    "text": "Mean definition",
                    "source": "sources/definition.txt:L1",
                }
            ],
            "duties": [
                {
                    "purpose": "Explain the supplied definition",
                    "evidence_ids": ["definition"],
                    "figure_ids": [],
                }
            ],
        }
        text = "The synthetic mean uses equally weighted rows."
        ids, figures, captions = ["definition"], [], {}
        if index:
            (folder / "sources/values.csv").write_text(f"value\n{index}\n{index + 2}\n")
            Image.new("RGB", (40, 30), "white").save(folder / "plot.png")
            data["figures"] = [
                {
                    "id": "same",
                    "path": "plot.png",
                    "caption": "Synthetic image",
                    "description": "Software fixture, not a CFD field.",
                }
            ]
            data["table_calculations"] = [
                {
                    "id": "mean",
                    "source": "sources/values.csv",
                    "operation": "population",
                    "columns": {"value": "value"},
                    "units": {"value": "W"},
                    "domain": "Synthetic rows",
                }
            ]
            data["evidence"].append(
                {
                    "id": "metric",
                    "kind": "metric",
                    "text": "Mean",
                    "source": "sources/values.csv",
                    "result_ref": {
                        "calculation_id": "mean",
                        "group": "all",
                        "field": "mean",
                        "places": 2,
                    },
                }
            )
            ids.append("metric")
            figures = ["same"]
            captions = {"same": "Synthetic image"}
            text += " Mean {{value:metric}}, shown in {{figure:same}}."
        if sid == "transport":
            ids.append("borrowed")
            text += " Compare {{value:borrowed}}."
        data["duties"][0].update(evidence_ids=ids, figure_ids=figures)
        input_path = write(folder / "input.json", data)
        draft = {
            "title": sid.title(),
            "paragraphs": [{"text": text, "evidence_ids": ids, "figure_ids": figures}],
            "captions": captions,
            "image_observations": {f: "author-provided" for f in figures},
            "evidence_notes": [],
        }
        draft_path = write(root / "prose" / f"{sid}.json", draft)
        entry = {
            "section_id": sid,
            "input": str(input_path.resolve()),
            "draft": f"../prose/{sid}.json",
        }
        if sid == "transport":
            entry.update(evidence_bindings={"borrowed": "response/metric"}, depends_on=["methods"])
        sections.append(entry)
        contracts.append(
            {
                "section_id": sid,
                "title": sid.title(),
                "role": "methods" if not index else "results",
                "purpose": data["question"],
                "required_claim_ids": ids,
                "required_figure_ids": figures,
            }
        )
        assert draft_path.is_file()
    sections[0]["input"] = "../analysis-0/writing/input.json"
    library = root / "reading"
    write(library / "bibliography.json", [{"id": "ref", "title": "Synthetic reference"}])
    (library / "excerpt.md").write_text("The fixture uses equal row weights.", encoding="utf-8")
    write(
        library / "library.json",
        {
            "bibliography": "bibliography.json",
            "supports": [
                {
                    "section_id": "methods",
                    "evidence_id": "reference",
                    "reference_id": "ref",
                    "source": "excerpt.md",
                    "locator": "paragraph 1",
                    "excerpt": "equal row weights",
                    "claim": "Equal-row definition",
                    "role": "method basis",
                    "status": "supported",
                }
            ],
        },
    )
    return write(
        root / "outline/outline.json",
        {
            "title": "Three-section synthetic seed",
            "spine": {"topic_id": "synthetic", "central_claim_id": "metric", "sections": contracts},
            "sections": sections,
            "literature": "../reading/library.json",
            "terms": {"mean": "equal-row mean"},
            "keywords": ["synthetic"],
            "context": "Software test only.",
        },
    )


def test_seed_preserves_bindings_dependencies_drafts_and_relocates(tmp_path):
    source = tmp_path / "source"
    outline = seed_fixture(source)
    before = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
    package = prepare_manuscript_seed(outline, tmp_path / "seed")
    assert package == tmp_path / "seed"
    manifest = read(package / "manuscript-input.json")
    assert manifest["keywords"] == ["synthetic"]
    assert manifest["sections"][2]["evidence_bindings"] == {"borrowed": "response/metric"}
    for sid in ("response", "transport"):
        data = read(package / f"sections/{sid}/input.json")
        original = read(Path(read(outline)["sections"][1 if sid == "response" else 2]["input"]))
        assert data["evidence"][1]["result_ref"] == {
            **original["evidence"][1]["result_ref"],
            "source_record": None,
            "percentage": False,
        }
        assert data["table_calculations"][0]["id"] == "mean"
        assert (package / f"sections/{sid}/sources/values.csv").is_file()
        assert (package / f"sections/{sid}/figures/same.png").is_file()
        assert not (package / f"sections/{sid}/sources/unselected.txt").exists()
    drafts = read(package / "drafts.json")
    for sid, path in drafts.items():
        assert (package / path).read_bytes() == (source / f"prose/{sid}.json").read_bytes()
    assert before == {
        p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()
    }
    moved = tmp_path / "relocated"
    shutil.move(package, moved)
    shutil.move(source, tmp_path / "source-unavailable")
    candidate = assemble_manuscript(moved, moved / "drafts.json", tmp_path / "candidate")
    text = (candidate / "manuscript.md").read_text(encoding="utf-8")
    assert "2.00 W" in text and "3.00 W" in text
    library = read(moved / "literature/literature.json")
    excerpt = moved / "literature" / library["supports"][0]["source"]
    assert excerpt.read_text(encoding="utf-8") == "The fixture uses equal row weights."


def test_missing_draft_is_pending_not_fake_prose(tmp_path):
    outline = seed_fixture(tmp_path / "source")
    data = read(outline)
    data["sections"][2].pop("draft")
    write(outline, data)
    package = prepare_manuscript_seed(outline, tmp_path / "seed")
    assert set(read(package / "drafts.json")) == {"methods", "response"}
    assert not (package / "sections/transport/draft.json").exists()
    assert "transport" in (package / "TASK.md").read_text(encoding="utf-8")
    assert "pending" in (package / "TASK.md").read_text(encoding="utf-8").lower()
    context = prepare_writing_context(
        package, "transport", tmp_path / "context", drafts_path=package / "drafts.json"
    )
    assert context.is_dir()
    with pytest.raises(ValueError, match="Draft"):
        assemble_manuscript(package, package / "drafts.json", tmp_path / "candidate")


@pytest.mark.parametrize("failure", ["duplicate", "alias", "missing-draft"])
def test_invalid_seed_leaves_no_output(tmp_path, failure):
    outline = seed_fixture(tmp_path / "source")
    data = read(outline)
    if failure == "duplicate":
        data["sections"].append(data["sections"][0])
    elif failure == "alias":
        data["sections"][2]["evidence_bindings"] = {"borrowed": "missing/metric"}
    else:
        data["sections"][0]["draft"] = "missing.json"
    write(outline, data)
    with pytest.raises((ValueError, FileNotFoundError)):
        prepare_manuscript_seed(outline, tmp_path / "seed")
    assert not (tmp_path / "seed").exists()


def test_comparison_definition_is_copied_without_manual_source_listing(tmp_path):
    outline = seed_fixture(tmp_path / "source")
    section_path = Path(read(outline)["sections"][1]["input"])
    data = read(section_path)
    (section_path.parent / "sources/contrast.txt").write_text("Difference of synthetic means.\n")
    second = {**data["table_calculations"][0], "id": "second"}
    data["table_calculations"].append(second)
    comparison = {
        "id": "contrast",
        "reference": {"calculation_id": "mean", "group": "all", "field": "mean"},
        "comparison": {"calculation_id": "second", "group": "all", "field": "mean"},
        "domain": "Synthetic rows",
        "definition_source": "sources/contrast.txt:L1",
        "comparison_scope": "Identical synthetic row domains",
        "status": "supported",
    }
    data["result_comparisons"] = [comparison]
    write(section_path, data)
    package = prepare_manuscript_seed(outline, tmp_path / "seed")
    copied = read(package / "sections/response/input.json")
    assert copied["result_comparisons"][0] == {**comparison, "temperature_reference": None}
    assert (package / "sections/response/sources/contrast.txt").read_bytes() == (
        section_path.parent / "sources/contrast.txt"
    ).read_bytes()
    with pytest.raises(FileExistsError):
        prepare_manuscript_seed(outline, package)


def test_alias_only_section_defers_evidence_validation_until_binding(tmp_path):
    outline = seed_fixture(tmp_path / "source")
    data = read(outline)
    entry = data["sections"][2]
    section_path = Path(entry["input"])
    section = read(section_path)
    section.update(evidence=[], figures=[], table_calculations=[])
    section["duties"][0].update(evidence_ids=["borrowed"], figure_ids=[])
    write(section_path, section)
    entry.pop("draft")
    data["spine"]["sections"][2].update(required_claim_ids=["borrowed"], required_figure_ids=[])
    write(outline, data)
    package = prepare_manuscript_seed(outline, tmp_path / "seed")
    evidence = read(package / "sections/transport/input.json")["evidence"]
    assert len(evidence) == 1
    assert evidence[0]["id"] == "borrowed"
    assert evidence[0]["value"] == "2.00"
