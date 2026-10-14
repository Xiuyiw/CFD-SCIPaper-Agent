"""Optional local CSL records separate bibliography display from evidence claims."""

import copy
import json
import shutil

import pytest

from cfdpaper.publication.literature import (
    _reference_label,
    literature_evidence,
    validate_citation_record,
)
from cfdpaper.publication.manuscript import (
    _literature_overrides,
    assemble_manuscript,
    prepare_manuscript,
)
from cfdpaper.publication.section import (
    _Evidence,
    assemble_section,
    export_section_docx,
    prepare_section,
)

RECORD = {
    "id": "paper",
    "type": "article-journal",
    "title": "Synthetic transport study",
    "author": [{"given": "A", "family": "Example"}],
    "issued": {"date-parts": [[2024]]},
    "container-title": "Synthetic Journal",
    "volume": 12,
    "page": "101",
    "DOI": "https://doi.org/10.1234/TEST",
    "custom": {"source_tag": "preserved"},
}


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def section_input(root, sid, citation_record=None):
    evidence = {
        "id": "prior",
        "kind": "literature",
        "text": f"Original supporting claim for {sid}.",
        "source": "Author supplied local provenance",
    }
    if citation_record is not None:
        evidence["citation_record"] = citation_record
    source = write(
        root / "input.json",
        {
            "section_id": sid,
            "title": sid.title(),
            "question": "What does this source support?",
            "figures": [],
            "evidence": [evidence],
            "duties": [
                {"purpose": "Attribute the source", "evidence_ids": ["prior"], "figure_ids": []}
            ],
        },
    )
    draft = write(
        root / "draft.json",
        {
            "title": sid.title(),
            "paragraphs": [
                {
                    "text": "Attributed comparison {{cite:prior}}.",
                    "evidence_ids": ["prior"],
                    "figure_ids": [],
                }
            ],
            "captions": {},
            "image_observations": {},
            "evidence_notes": [evidence["text"]],
        },
    )
    return source, draft


def manuscript_input(root, records):
    sections, contracts, drafts = [], [], {}
    for sid, record in zip(("response", "discussion"), records, strict=True):
        local = root / sid
        local.mkdir()
        section_input(local, sid, record)
        sections.append({"section_id": sid, "input": f"{sid}/input.json"})
        contracts.append(
            {
                "section_id": sid,
                "role": "results" if sid == "response" else "discussion",
                "title": sid.title(),
                "purpose": "Attribute the source",
                "required_claim_ids": ["prior"],
            }
        )
        drafts[sid] = f"{sid}/draft.json"
    return (
        write(
            root / "manuscript.json",
            {
                "title": "Synthetic local bibliography",
                "spine": {"topic_id": "test", "central_claim_id": "prior", "sections": contracts},
                "sections": sections,
            },
        ),
        write(root / "drafts.json", drafts),
    )


def test_citation_validation_copies_and_normalizes_without_completing_metadata():
    original = copy.deepcopy(RECORD)
    checked = validate_citation_record(RECORD)
    assert RECORD == original
    assert checked["DOI"] == "10.1234/test"
    checked["custom"]["source_tag"] = "changed"
    assert RECORD["custom"]["source_tag"] == "preserved"
    assert validate_citation_record({"id": "sparse"}) == {"id": "sparse"}


@pytest.mark.parametrize(
    "change",
    [
        {"id": ""},
        {"DOI": ""},
        {"title": []},
        {"container-title": 1},
        {"URL": []},
        {"volume": True},
        {"issue": []},
        {"page": {}},
        {"author": {}},
        {"author": [1]},
        {"author": [{"family": {"name": "Example"}}]},
        {"issued": []},
        {"issued": {"date-parts": {"year": 2024}}},
        {"issued": {"date-parts": [[True]]}},
        {"publisher": {}},
    ],
)
def test_inline_record_reuses_bibliography_shape_checks(change):
    with pytest.raises(ValueError):
        validate_citation_record({**RECORD, **change})


def test_optional_field_is_literature_only_and_omitted_for_old_evidence():
    base = {"id": "prior", "kind": "literature", "text": "Claim", "source": "Source"}
    assert "citation_record" not in _Evidence.model_validate(base).model_dump()
    with pytest.raises(ValueError, match="literature"):
        _Evidence.model_validate({**base, "kind": "observation", "citation_record": RECORD})


@pytest.mark.parametrize("metadata", [False, True])
def test_section_sdk_roundtrip_and_docx_keep_claim_outside_bibliography(tmp_path, metadata):
    docx = pytest.importorskip("docx")
    source, draft = section_input(tmp_path, "discussion", RECORD if metadata else None)
    package = prepare_section(source, tmp_path / "prepared")
    moved = tmp_path / "moved"
    shutil.move(str(package), moved)
    candidate = assemble_section(moved, draft, tmp_path / "candidate")
    result = json.loads((candidate / "section.json").read_text(encoding="utf-8"))
    claim = "Original supporting claim for discussion."
    assert result["evidence"][0]["text"] == claim
    assert claim in (candidate / "evidence-notes.md").read_text(encoding="utf-8")
    output = export_section_docx(candidate, tmp_path / "section.docx")
    references = [p.text for p in docx.Document(output).paragraphs if p.text.startswith("[")]
    markdown = (candidate / "section.md").read_text(encoding="utf-8")
    if metadata:
        label = _reference_label(validate_citation_record(RECORD))
        assert references == [f"[1] {label}"]
        assert f"[1] {label}" in markdown
        assert claim not in markdown
        assert "Author supplied local provenance" not in references[0]
        assert result["evidence"][0]["citation_record"]["DOI"] == "10.1234/test"
    else:
        assert references == [f"[1] {claim} — Author supplied local provenance"]
        assert "citation_record" not in result["evidence"][0]


@pytest.mark.parametrize("where", ["first", "second", "both"])
def test_manuscript_prefers_metadata_and_retains_each_local_claim(tmp_path, where):
    docx = pytest.importorskip("docx")
    first = RECORD if where in {"first", "both"} else None
    second = {**RECORD, "id": "local-alias"} if where in {"second", "both"} else None
    source, drafts = manuscript_input(tmp_path, [first, second])
    package = prepare_manuscript(source, tmp_path / "prepared")
    moved = tmp_path / "moved"
    shutil.move(str(package), moved)
    candidate = assemble_manuscript(moved, drafts, tmp_path / "candidate")
    result = json.loads((candidate / "section.json").read_text(encoding="utf-8"))
    assert len(result["references"]) == 1
    assert result["references"][0]["number"] == 1
    assert result["references"][0]["citation_record"]["DOI"] == "10.1234/test"
    assert [e["text"] for e in result["evidence"]] == [
        "Original supporting claim for response.",
        "Original supporting claim for discussion.",
    ]
    for sid in ("response", "discussion"):
        local = json.loads((candidate / f"sections/{sid}/input.json").read_text(encoding="utf-8"))
        assert local["evidence"][0]["text"] == f"Original supporting claim for {sid}."
    label = _reference_label(validate_citation_record(RECORD))
    assert f"[1] {label}" in (candidate / "manuscript.md").read_text(encoding="utf-8")
    output = export_section_docx(candidate, tmp_path / "manuscript.docx")
    assert [p.text for p in docx.Document(output).paragraphs if p.text.startswith("[")] == [
        f"[1] {label}"
    ]


def test_conflicting_inline_metadata_for_same_source_is_rejected(tmp_path):
    source, drafts = manuscript_input(tmp_path, [RECORD, {**RECORD, "title": "Different study"}])
    package = prepare_manuscript(source, tmp_path / "prepared")
    with pytest.raises(ValueError, match="Conflicting citation metadata"):
        assemble_manuscript(package, drafts, tmp_path / "candidate")
    assert not (tmp_path / "candidate").exists()


def test_shared_literature_and_override_preserve_detached_csl_record():
    library = {
        "records": [validate_citation_record(RECORD)],
        "supports": [
            {
                "section_id": "discussion",
                "evidence_id": "prior",
                "reference_id": "paper",
                "status": "supported",
            }
        ],
    }
    expected = copy.deepcopy(library)
    evidence = literature_evidence(library, "discussion")
    override = _literature_overrides(library, "discussion")
    assert override["prior"]["citation_record"] == expected["records"][0]
    evidence[0]["citation_record"]["custom"]["source_tag"] = "changed"
    assert library == expected
