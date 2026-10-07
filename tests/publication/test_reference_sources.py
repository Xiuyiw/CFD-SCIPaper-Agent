"""Display-only bibliography deduplication through the real publication routes."""

import copy
import json

import pytest

from cfdpaper.publication.literature import literature_evidence
from cfdpaper.publication.manuscript import assemble_manuscript, prepare_manuscript
from cfdpaper.publication.section import (
    assemble_section,
    export_section_docx,
    prepare_section,
    reference_source_suffix,
)


@pytest.mark.parametrize(
    "source,text",
    [
        ("https://doi.org/10.1234/test", "Author. Study. doi:10.1234/test."),
        (" HTTP://DX.DOI.ORG/10.1234/TEST ", "Study. DOI: 10.1234/test;"),
        ("doi:10.1234/test.", "Study. https://doi.org/10.1234/TEST"),
        ("10.1234/test", "Study (doi:10.1234/test)."),
        ("https://doi.org/10.1234/test;", "Study. 10.1234/test,"),
        ("doi:10.1234/a(b)", "Study. https://doi.org/10.1234/a(b)."),
        ("doi:10.1234/a(b)", "Study (doi:10.1234/a(b))."),
        ("https://doi.org/10.1234/test", "Study [doi:10.1234/test]."),
    ],
)
def test_equivalent_doi_source_is_not_appended(source, text):
    record = {"source": source, "text": text}
    original = copy.deepcopy(record)
    assert reference_source_suffix(record) == ""
    assert record == original


@pytest.mark.parametrize(
    "source,text",
    [
        ("https://example.org/paper", "Study. doi:10.1234/test."),
        ("https://doi.org/10.1234/other", "Study. doi:10.1234/test."),
        ("doi:10.1234/test", "Study. doi:10.1234/test-extra."),
        ("doi:10.1234/test-extra", "Study. doi:10.1234/test."),
        ("doi:10.1234/test; supplementary methods", "Study. doi:10.1234/test."),
        ("Full text: https://doi.org/10.1234/test", "Study. doi:10.1234/test."),
        ("https://example.org/10.1234/test", "Study. doi:10.1234/test."),
        ("doi:10.1234/test", "Study. https://example.org/10.1234/test"),
    ],
)
def test_distinct_or_meaningful_source_is_retained(source, text):
    assert reference_source_suffix({"source": source, "text": text}) == f" — {source}"


def test_csl_formatted_runs_remain_authoritative():
    record = {
        "source": "https://example.org/paper",
        "text": "CSL bibliography entry",
        "formatted_runs": [{"text": "CSL bibliography entry", "italic": True}],
    }
    original = copy.deepcopy(record)
    assert reference_source_suffix(record) == ""
    assert record == original


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize("route", ["section", "manuscript"])
def test_default_bibliography_doi_url_is_shown_once_in_markdown_and_docx(tmp_path, route):
    docx = pytest.importorskip("docx")
    # Use the product's default bibliography label, not a hand-written substitute.
    evidence = literature_evidence(
        {
            "records": [{"id": "paper", "title": "Synthetic study", "DOI": "10.1234/test"}],
            "supports": [
                {
                    "section_id": "discussion",
                    "evidence_id": "paper",
                    "reference_id": "paper",
                    "status": "supported",
                }
            ],
        },
        "discussion",
    )
    evidence[0]["source"] = "https://doi.org/10.1234/test"
    evidence.append(
        {
            "id": "other",
            "kind": "literature",
            "text": "Other study. doi:10.1234/test.",
            "source": "https://doi.org/10.1234/other",
        }
    )
    source = _write(
        tmp_path / "input.json",
        {
            "section_id": "discussion",
            "title": "Discussion",
            "question": "What differs?",
            "figures": [],
            "evidence": evidence,
            "duties": [
                {"purpose": "Compare sources", "evidence_ids": ["paper", "other"], "figure_ids": []}
            ],
        },
    )
    draft = _write(
        tmp_path / "draft.json",
        {
            "title": "Discussion",
            "paragraphs": [
                {
                    "text": "Synthetic comparison {{cite:paper}} and {{cite:other}}.",
                    "evidence_ids": ["paper", "other"],
                    "figure_ids": [],
                }
            ],
            "captions": {},
            "image_observations": {},
            "evidence_notes": [],
        },
    )
    if route == "section":
        package = prepare_section(source, tmp_path / "package")
        candidate = assemble_section(package, draft, tmp_path / "candidate")
        markdown_path = candidate / "section.md"
    else:
        manifest = _write(
            tmp_path / "manuscript-input.json",
            {
                "title": "Synthetic manuscript",
                "spine": {
                    "topic_id": "synthetic",
                    "central_claim_id": "paper",
                    "sections": [
                        {
                            "section_id": "discussion",
                            "role": "discussion",
                            "title": "Discussion",
                            "purpose": "Compare sources",
                            "required_claim_ids": ["paper", "other"],
                        }
                    ],
                },
                "sections": [{"section_id": "discussion", "input": "input.json"}],
            },
        )
        mapping = _write(tmp_path / "drafts.json", {"discussion": "draft.json"})
        package = prepare_manuscript(manifest, tmp_path / "package")
        candidate = assemble_manuscript(package, mapping, tmp_path / "candidate")
        markdown_path = candidate / "manuscript.md"
    data = json.loads((candidate / "section.json").read_text(encoding="utf-8"))
    assert [r["source"] for r in data["references"]] == [e["source"] for e in evidence]
    assert data["references"][0]["text"] == evidence[0]["text"]
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "[1] Synthetic study. doi:10.1234/test\n" in markdown
    assert "https://doi.org/10.1234/other" in markdown
    output = export_section_docx(candidate, tmp_path / "manuscript.docx")
    references = [p.text for p in docx.Document(output).paragraphs if p.text.startswith("[")]
    assert references[0] == "[1] Synthetic study. doi:10.1234/test"
    assert references[1].endswith(" — https://doi.org/10.1234/other")
