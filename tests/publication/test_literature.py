"""Synthetic bibliographic fixtures test provenance plumbing, not scientific truth."""

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from cfdpaper.publication.literature import (
    copy_literature,
    literature_evidence,
    load_literature,
)


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def record(rid="first", **extra):
    return {
        "id": rid,
        "type": "article-journal",
        "title": "Synthetic heat transfer study",
        "author": [{"family": "Example", "given": "A"}],
        "issued": {"date-parts": [[2024]]},
        **extra,
    }


def support(**extra):
    return {
        "section_id": "intro",
        "evidence_id": "prior",
        "reference_id": "first",
        "source": "paper.md",
        "locator": "Synthetic source, paragraph 1",
        "excerpt": "A synthetic source passage.",
        "claim": "Author supplied interpretation, not checked by substring matching.",
        "role": "comparison",
        "status": "supported",
        **extra,
    }


def fixture(tmp_path, records=None, supports=None, **extra):
    write(tmp_path / "refs.json", [record()] if records is None else records)
    (tmp_path / "paper.md").write_bytes(b"Heading\r\nA synthetic source passage.\r\n")
    return write(
        tmp_path / "literature.json",
        {
            "bibliography": "refs.json",
            "supports": [support()] if supports is None else supports,
            **extra,
        },
    )


def test_doi_normalization_alias_and_preserved_metadata(tmp_path):
    path = fixture(
        tmp_path,
        [
            record(DOI=" https://doi.org/10.1234/ABC ", custom={"tag": "kept"}),
            record("other", DOI="doi:10.1234/abc", URL="https://example.org/paper"),
        ],
        [support(reference_id="other")],
        note="Retain workspace metadata",
    )
    library = load_literature(path)
    assert len(library["records"]) == 1
    assert library["records"][0]["DOI"] == "10.1234/abc"
    assert library["records"][0]["custom"] == {"tag": "kept"}
    assert library["records"][0]["URL"] == "https://example.org/paper"
    assert library["aliases"] == {"first": "first", "other": "first"}
    assert library["supports"][0]["reference_id"] == "first"
    assert library["note"] == "Retain workspace metadata"
    evidence = literature_evidence(library, "intro")
    assert evidence[0]["source"] == "doi:10.1234/abc"
    assert "Synthetic heat transfer study" in evidence[0]["text"]
    assert support()["claim"] not in evidence[0]["text"]
    assert support()["excerpt"] not in evidence[0]["text"]


def test_complete_fallback_deduplicates_case_and_spacing(tmp_path):
    path = fixture(
        tmp_path,
        [record(), record("second", title="  SYNTHETIC  heat transfer study ")],
    )
    library = load_literature(path)
    assert len(library["records"]) == 1
    assert library["aliases"]["second"] == "first"


def test_fallback_keeps_first_id_when_later_record_has_doi(tmp_path):
    path = fixture(tmp_path, [record(), record("with-doi", DOI="10.1234/test")])
    library = load_literature(path)
    assert library["records"][0]["id"] == "first"
    assert library["records"][0]["DOI"] == "10.1234/test"
    assert library["aliases"]["with-doi"] == "first"


def test_ambiguous_fallback_does_not_collapse_distinct_dois(tmp_path):
    path = fixture(
        tmp_path,
        [record(), record("a", DOI="10.1234/a"), record("b", DOI="10.1234/b")],
    )
    library = load_literature(path)
    assert len(library["records"]) == 3
    assert library["aliases"] == {"first": "first", "a": "a", "b": "b"}


@pytest.mark.parametrize("missing", ["title", "author", "issued"])
def test_missing_metadata_preserves_distinct_references(tmp_path, missing):
    first, second = record(), record("other")
    first.pop(missing)
    second.pop(missing)
    library = load_literature(fixture(tmp_path, [first, second]))
    assert len(library["records"]) == 2
    assert literature_evidence(library, "intro")[0]["source"] == "reference:first"


def test_bare_reference_remains_bare(tmp_path):
    library = load_literature(fixture(tmp_path, [{"id": "first"}]))
    assert literature_evidence(library, "intro")[0]["text"] == "reference:first"


def test_numeric_csl_fields_are_preserved(tmp_path):
    library = load_literature(fixture(tmp_path, [record(volume=12, issue=2, page=101)]))
    assert library["records"][0]["volume"] == 12
    assert "12. 2. 101" in literature_evidence(library, "intro")[0]["text"]


@pytest.mark.parametrize(
    "change",
    [
        {"title": "Different title"},
        {"author": [{"family": "Different"}]},
        {"issued": {"date-parts": [[2025]]}},
        {"custom": "different"},
    ],
)
def test_same_doi_conflicting_metadata_rejected(tmp_path, change):
    path = fixture(
        tmp_path,
        [
            record(DOI="10.1234/a", custom="original"),
            record("other", DOI="10.1234/a", **change),
        ],
    )
    with pytest.raises(ValueError, match="Conflicting bibliography metadata"):
        load_literature(path)


def test_fallback_conflict_and_duplicate_ids_rejected(tmp_path):
    path = fixture(tmp_path, [record(volume="1"), record("other", volume="2")])
    with pytest.raises(ValueError, match="Conflicting bibliography metadata"):
        load_literature(path)
    fixture(tmp_path, [record(), record()])
    with pytest.raises(ValueError, match="Duplicate bibliography id"):
        load_literature(path)


@pytest.mark.parametrize(
    "change,match",
    [
        ({"excerpt": "not present"}, "not found exactly"),
        ({"excerpt": " "}, "nonblank"),
        ({"excerpt": "Heading\nA synthetic"}, "not found exactly"),
        ({"source": "../paper.md"}, "relative path"),
        ({"source": "C:\\paper.md"}, "relative path"),
        ({"source": "/paper.md"}, "relative path"),
        ({"source": "missing.md"}, "not found"),
        ({"source": "refs.json"}, "UTF-8 .txt or .md"),
        ({"section_id": "../intro"}, "safe token"),
        ({"evidence_id": "bad id"}, "safe token"),
        ({"locator": " "}, "nonblank"),
        ({"claim": " "}, "nonblank"),
        ({"role": " "}, "nonblank"),
        ({"reference_id": "absent"}, "Unknown support"),
        ({"status": "verified"}, "status must"),
    ],
)
def test_invalid_supports(tmp_path, change, match):
    path = fixture(tmp_path, supports=[support(**change)])
    with pytest.raises(ValueError, match=match):
        load_literature(path)


def test_all_statuses_retained_only_supported_is_citable(tmp_path):
    path = fixture(
        tmp_path,
        supports=[
            support(),
            support(evidence_id="unconfirmed", status="needs-review"),
            support(evidence_id="rejected", status="unsupported"),
        ],
    )
    library = load_literature(path)
    assert len(library["supports"]) == 3
    assert [item["id"] for item in literature_evidence(library, "intro")] == ["prior"]
    assert literature_evidence(library, "other-section") == []


def test_duplicate_evidence_rejected_per_section(tmp_path):
    path = fixture(tmp_path, supports=[support(), support(status="unsupported")])
    with pytest.raises(ValueError, match="Duplicate literature support"):
        load_literature(path)


def test_copied_workspace_survives_relocation_and_retains_aliases(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    path = fixture(
        original,
        [record(DOI="10.1234/a"), record("alias", DOI="https://doi.org/10.1234/a")],
        [support(reference_id="alias"), support(evidence_id="later", status="needs-review")],
        note="kept",
    )
    output = tmp_path / "output"
    copied = copy_literature(path, output)
    expected = load_literature(copied)
    sources = list((output / "sources").iterdir())
    assert len(sources) == 1
    assert sources[0].read_bytes() == (original / "paper.md").read_bytes()
    assert expected["aliases"]["alias"] == "first"
    moved = tmp_path / "relocated"
    shutil.move(str(output), moved)
    shutil.rmtree(original)
    actual = load_literature(moved / "literature.json")
    assert actual == expected
    assert actual["note"] == "kept"
    with pytest.raises(ValueError, match="already exists"):
        copy_literature(moved / "literature.json", moved)


def test_explicit_alias_validation(tmp_path):
    path = fixture(tmp_path, aliases={"old": "first"})
    assert load_literature(path)["aliases"]["old"] == "first"
    fixture(tmp_path, aliases={"old": "missing"})
    with pytest.raises(ValueError, match="Unknown alias target"):
        load_literature(path)


def test_bib_import_requires_optional_pandoc(tmp_path, monkeypatch):
    path = fixture(tmp_path, bibliography="refs.bib")
    (tmp_path / "refs.bib").write_text("@article{first, title={Synthetic}}", encoding="utf-8")
    monkeypatch.setattr("cfdpaper.publication.literature.shutil.which", lambda name: None)
    with pytest.raises(ValueError, match="export your bibliography as CSL JSON"):
        load_literature(path)


def test_bib_import_uses_pandoc_without_shell(tmp_path, monkeypatch):
    path = fixture(tmp_path, bibliography="refs.bib")
    (tmp_path / "refs.bib").write_text("synthetic input", encoding="utf-8")
    monkeypatch.setattr("cfdpaper.publication.literature.shutil.which", lambda name: "pandoc")
    calls = []

    def convert(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout=json.dumps([record()]))

    monkeypatch.setattr("cfdpaper.publication.literature.subprocess.run", convert)
    assert load_literature(path)["records"][0]["id"] == "first"
    args, kwargs = calls[0]
    assert args[:5] == ["pandoc", "-f", "biblatex", "-t", "csljson"]
    assert Path(args[5]) == (tmp_path / "refs.bib").resolve()
    assert kwargs.get("shell", False) is False


def test_failed_pandoc_is_actionable(tmp_path, monkeypatch):
    path = fixture(tmp_path, bibliography="refs.bib")
    (tmp_path / "refs.bib").write_text("bad input", encoding="utf-8")
    monkeypatch.setattr("cfdpaper.publication.literature.shutil.which", lambda name: "pandoc")

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "pandoc")

    monkeypatch.setattr("cfdpaper.publication.literature.subprocess.run", fail)
    with pytest.raises(ValueError, match="export CSL JSON"):
        load_literature(path)
