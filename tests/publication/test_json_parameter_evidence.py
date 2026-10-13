import json
import shutil
import zipfile

import pytest

from cfdpaper.publication.manuscript import (
    assemble_manuscript,
    prepare_manuscript,
    prepare_writing_context,
)
from cfdpaper.publication.manuscript_seed import prepare_manuscript_seed
from cfdpaper.publication.parameter_evidence import resolve_json_value
from cfdpaper.publication.section import assemble_section, export_section_docx, prepare_section


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def source(tmp_path, value=0.25):
    write(
        tmp_path / "sources/config.json",
        {"solver": {"max_step": value, "unit": "s"}, "a/b": {"x~y": [2.5]}},
    )
    return dict(source="sources/config.json", pointer="/solver/max_step", unit="s", places=2)


def test_exact_source_pointer_precision_and_no_mutation(tmp_path):
    ref = source(tmp_path)
    before = (tmp_path / ref["source"]).read_bytes()
    result = resolve_json_value(tmp_path, **ref, unit_pointer="/solver/unit")
    assert result["raw_value"] == 0.25 and result["value"] == "0.25"
    assert result["unit"] == "s" and result["json_pointer"] == ref["pointer"]
    assert result["source"] == ref["source"]
    assert (tmp_path / ref["source"]).read_bytes() == before
    result = resolve_json_value(tmp_path, **dict(ref, pointer="/a~1b/x~0y/0", unit="mm"))
    assert result["raw_value"] == 2.5


@pytest.mark.parametrize(
    "pointer",
    ["solver/max_step", "#/solver/max_step", "/a~2b", "/missing", "/a~1b/x~0y/01", "/a~1b/x~0y/-1"],
)
def test_invalid_or_missing_pointer_is_not_guessed(tmp_path, pointer):
    ref = source(tmp_path)
    with pytest.raises(ValueError):
        resolve_json_value(tmp_path, **dict(ref, pointer=pointer))


@pytest.mark.parametrize("value", [True, None, "0.25", [], {}, float("nan"), float("inf")])
def test_only_finite_native_numbers(tmp_path, value):
    ref = source(tmp_path, value)
    with pytest.raises(ValueError):
        resolve_json_value(tmp_path, **ref)


def test_missing_source_unit_conflict_and_no_path_escape(tmp_path):
    ref = source(tmp_path)
    with pytest.raises(ValueError, match="unit"):
        resolve_json_value(tmp_path, **dict(ref, unit="ms"), unit_pointer="/solver/unit")
    for path in (
        "../config.json",
        "config.json",
        str(tmp_path / "sources/config.json"),
        "sources/no.json",
    ):
        with pytest.raises(ValueError):
            resolve_json_value(tmp_path, **dict(ref, source=path))


def section(tmp_path):
    ref = source(tmp_path)
    value = {
        "section_id": "methods",
        "title": "Calculation methods",
        "question": "Define the timestep",
        "figures": [],
        "evidence": [
            {
                "id": "step",
                "kind": "metric",
                "source": "Run configuration",
                "text": "Maximum internal solver step",
                "json_value_ref": ref,
            }
        ],
        "duties": [
            {"purpose": "Report effective settings", "evidence_ids": ["step"], "figure_ids": []}
        ],
    }
    path = write(tmp_path / "input.json", value)
    draft = {
        "title": "Calculation methods",
        "paragraphs": [
            {
                "text": "The maximum step is {{value:step}}; see {{table:1}}.",
                "evidence_ids": ["step"],
                "figure_ids": [],
            }
        ],
        "captions": {},
        "image_observations": {},
        "evidence_notes": [],
        "tables": [
            {
                "table_id": "1",
                "after_section_id": "methods",
                "caption": "Effective solver settings",
                "columns": ["Parameter", "Value"],
                "rows": [["Maximum timestep", "{{value:step}}"]],
                "evidence_ids": ["step"],
            }
        ],
    }
    return path, value, write(tmp_path / "draft.json", draft)


def test_section_source_binding_native_table_and_recalculation(tmp_path):
    path, _, draft = section(tmp_path)
    package = prepare_section(path, tmp_path / "package")
    assert (package / "sources/config.json").is_file()
    data = json.loads((package / "parameter-results.json").read_text())
    assert data["step"]["raw_value"] == 0.25
    first = assemble_section(package, draft, tmp_path / "first")
    config = package / "sources/config.json"
    content = json.loads(config.read_text())
    content["solver"]["max_step"] = 0.5
    write(config, content)
    second = assemble_section(package, draft, tmp_path / "second")
    assert "0.50 s" in (second / "section.md").read_text()
    assert "0.25 s" in (first / "section.md").read_text()
    docx = export_section_docx(second, tmp_path / "methods.docx", layout="near-reference")
    with zipfile.ZipFile(docx) as archive:
        xml = archive.read("word/document.xml").decode()
    assert "0.50" in xml and "<w:tbl>" in xml


@pytest.mark.parametrize(
    "other",
    [
        {"value": "1"},
        {"unit": "s"},
        {"kind": "observation"},
        {"result_ref": {"calculation_id": "c", "group": "all", "field": "value"}},
    ],
)
def test_parameter_ref_does_not_accept_manual_or_competing_definition(tmp_path, other):
    path, data, _ = section(tmp_path)
    data["evidence"][0].update(other)
    write(path, data)
    with pytest.raises(ValueError):
        prepare_section(path, tmp_path / "package")


@pytest.mark.parametrize("prepare", [prepare_manuscript, prepare_manuscript_seed])
def test_manuscript_binding_context_reassembly_and_change_propagation(tmp_path, prepare):
    method = tmp_path / "method"
    path, _, draft = section(method)
    other = {
        "section_id": "discussion",
        "title": "Discussion",
        "question": "Read solver support",
        "figures": [],
        "evidence": [],
        "duties": [
            {
                "purpose": "Read bound parameter",
                "evidence_ids": ["inherited-step"],
                "figure_ids": [],
            }
        ],
    }
    write(tmp_path / "other/input.json", other)
    d = {
        "title": "Discussion",
        "paragraphs": [
            {
                "text": "The result used a maximum internal step of {{value:inherited-step}}.",
                "evidence_ids": ["inherited-step"],
                "figure_ids": [],
            }
        ],
        "captions": {},
        "image_observations": {},
        "evidence_notes": [],
    }
    write(tmp_path / "other/draft.json", d)
    spine = {
        "topic_id": "method-source-fixture",
        "central_claim_id": "step",
        "sections": [
            {
                "section_id": "methods",
                "role": "methods",
                "title": "Methods",
                "purpose": "Define input",
                "required_claim_ids": ["step"],
            },
            {
                "section_id": "discussion",
                "role": "discussion",
                "title": "Discussion",
                "purpose": "Use declared parameter",
                "required_claim_ids": ["inherited-step"],
            },
        ],
    }
    outline = {
        "title": "Method source binding fixture",
        "spine": spine,
        "sections": [
            {"section_id": "methods", "input": str(path.relative_to(tmp_path))},
            {
                "section_id": "discussion",
                "input": "other/input.json",
                "depends_on": ["methods"],
                "evidence_bindings": {"inherited-step": "methods/step"},
            },
        ],
    }
    pkg = prepare(write(tmp_path / "outline.json", outline), tmp_path / "work")
    mapping = write(
        tmp_path / "draft-map.json",
        {"methods": str(draft.relative_to(tmp_path)), "discussion": "other/draft.json"},
    )
    first = assemble_manuscript(pkg, mapping, tmp_path / "first")
    moved = tmp_path / "moved"
    shutil.copytree(first, moved)
    config = moved / "sections/methods/sources/config.json"
    content = json.loads(config.read_text())
    content["solver"]["max_step"] = 0.75
    write(config, content)
    context = prepare_writing_context(
        moved, "discussion", tmp_path / "context", drafts_path=moved / "drafts.json"
    )
    packet = json.loads((context / "context.json").read_text())
    assert packet["sections"]["methods"]["evidence"]["step"]["resolved"]["raw_value"] == 0.75
    assert (
        packet["sections"]["discussion"]["evidence"]["inherited-step"]["resolved"]["raw_value"]
        == 0.75
    )
    second = assemble_manuscript(moved, moved / "drafts.json", tmp_path / "second")
    text = (second / "manuscript.md").read_text()
    assert text.count("0.75 s") >= 3 and "0.25 s" not in text
    assert "0.25 s" in (first / "manuscript.md").read_text()
