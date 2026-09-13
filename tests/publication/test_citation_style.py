"""Numeric CSL adapter tests use synthetic metadata and a small original test style."""

import json
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from cfdpaper.publication.citation_style import format_numeric_bibliography

STYLE = """<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" version="1.0" class="in-text">
  <info><title>Synthetic numeric test</title><id>https://example.org/test-numeric</id>
  <updated>2026-09-13T00:00:00+00:00</updated></info>
  <citation><layout prefix="[" suffix="]"><text variable="citation-number"/></layout></citation>
  <bibliography second-field-align="flush"><layout>
    <text variable="citation-number" suffix=". "/>
    <group delimiter=". "><text variable="title" font-style="italic"/>
      <text variable="container-title"/><text variable="volume" font-weight="bold"/></group>
  </layout></bibliography>
</style>"""


@pytest.fixture
def style(tmp_path):
    path = tmp_path / "numeric.csl"
    path.write_text(STYLE, encoding="utf-8")
    return path


def records():
    return [
        {
            "id": "z:测试/1;@[]",
            "type": "article-journal",
            "title": "Zeta 温度",
            "container-title": "Synthetic Journal",
            "volume": "12",
        },
        {"id": "a", "type": "article-journal", "title": "Alpha flux"},
    ]


def node(kind, content=None):
    return {"t": kind, **({"c": content} if content is not None else {})}


def response(ids):
    paragraphs, entries = [], []
    for number, rid in enumerate(ids, 1):
        paragraphs.append(
            node("Para", [node("Cite", [[{"citationId": rid}], [node("Str", f"[{number}]")]])])
        )
        entries.append(
            node(
                "Div",
                [
                    [f"ref-{rid}", ["csl-entry"], []],
                    [
                        node(
                            "Para",
                            [
                                node(
                                    "Span",
                                    [["", ["csl-left-margin"], []], [node("Str", f"[{number}]")]],
                                ),
                                node(
                                    "Span",
                                    [
                                        ["", ["csl-right-inline"], []],
                                        [
                                            node("Emph", [node("Str", "温度 transfer")]),
                                            node("Space"),
                                            node("Strong", [node("Str", "12")]),
                                        ],
                                    ],
                                ),
                            ],
                        )
                    ],
                ],
            )
        )
    return {
        "pandoc-api-version": [1, 23, 1],
        "meta": {},
        "blocks": [
            *paragraphs,
            node("Div", [["refs", ["references", "csl-bib-body"], []], entries]),
        ],
    }


def mock_engine(monkeypatch, output):
    calls = []
    monkeypatch.setattr("cfdpaper.publication.citation_style.shutil.which", lambda name: "pandoc")

    def run(args, **kwargs):
        calls.append((args, kwargs))
        if "--citeproc" not in args:
            return SimpleNamespace(stdout=json.dumps({"pandoc-api-version": [1, 23, 1]}))
        bibliography = Path(args[args.index("--bibliography") + 1])
        assert bibliography.is_file()
        assert bibliography.parent == Path(kwargs["cwd"])
        return SimpleNamespace(stdout=json.dumps(output, ensure_ascii=False))

    monkeypatch.setattr("cfdpaper.publication.citation_style.subprocess.run", run)
    return calls


def test_numeric_runs_unicode_labels_and_literal_cite_ids(style, monkeypatch):
    source = records()
    preserved = deepcopy(source)
    calls = mock_engine(monkeypatch, response([r["id"] for r in source]))
    result = format_numeric_bibliography(source, style)
    assert [entry["id"] for entry in result] == [r["id"] for r in source]
    assert result[0]["text"] == "温度 transfer 12"
    assert result[0]["runs"] == [
        {"text": "温度 transfer", "italic": True},
        {"text": " "},
        {"text": "12", "bold": True},
    ]
    assert source == preserved
    args, kwargs = calls[-1]
    assert kwargs.get("shell", False) is False
    supplied = json.loads(kwargs["input"])
    assert supplied["blocks"][0]["c"][0]["c"][0][0]["citationId"] == source[0]["id"]
    assert not Path(kwargs["cwd"]).exists()


def test_plain_numeric_label_removed_once_and_multiple_paragraphs_preserved(style, monkeypatch):
    output = response(["first"])
    output["blocks"][-1]["c"][1][0]["c"][1] = [
        node(
            "Para",
            [
                node("Strong", [node("Str", "1.")]),
                node("Space"),
                node("Emph", [node("Str", "[1] is part of the supplied title")]),
            ],
        ),
        node("Para", [node("Str", "Second paragraph.")]),
    ]
    mock_engine(monkeypatch, output)
    result = format_numeric_bibliography([{"id": "first"}], style)[0]
    assert result["text"] == "[1] is part of the supplied title\nSecond paragraph."
    assert result["runs"][0]["italic"] is True


def test_margin_label_does_not_strip_numeric_title(style, monkeypatch):
    output = response(["first"])
    output["blocks"][-1]["c"][1][0]["c"][1][0]["c"][1]["c"][1] = [node("Str", "1. Title")]
    mock_engine(monkeypatch, output)
    assert format_numeric_bibliography([{"id": "first"}], style)[0]["text"] == "1. Title"


def test_missing_pandoc_is_actionable(style, monkeypatch):
    monkeypatch.setattr("cfdpaper.publication.citation_style.shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="install Pandoc or omit the style"):
        format_numeric_bibliography(records(), style)


def test_bad_or_missing_style(tmp_path):
    path = tmp_path / "bad.csl"
    with pytest.raises(ValueError, match="not found"):
        format_numeric_bibliography(records(), path)
    path.write_text("not XML", encoding="utf-8")
    with pytest.raises(ValueError, match="standalone CSL XML"):
        format_numeric_bibliography(records(), path)


def test_dependent_style_requires_local_parent(style, monkeypatch):
    style.write_text(
        '<style><info><link rel="independent-parent" href="https://example.org/parent"/>'
        "</info></style>",
        encoding="utf-8",
    )
    monkeypatch.setattr("cfdpaper.publication.citation_style.shutil.which", lambda name: None)
    with pytest.raises(ValueError, match="standalone parent CSL file locally"):
        format_numeric_bibliography(records(), style)


@pytest.mark.parametrize("citation", ["(Example, 2024)", "1", "[2]"])
def test_nonnumeric_or_reordered_citations_rejected(style, monkeypatch, citation):
    output = response(["first"])
    output["blocks"][0]["c"][0]["c"][1] = [node("Str", citation)]
    mock_engine(monkeypatch, output)
    with pytest.raises(ValueError, match="bracket numeric"):
        format_numeric_bibliography([{"id": "first"}], style)


@pytest.mark.parametrize("problem", ["missing", "duplicate", "reordered"])
def test_missing_duplicate_or_reordered_bibliography_ids(style, monkeypatch, problem):
    output = response(["first", "second"])
    entries = output["blocks"][-1]["c"][1]
    if problem == "missing":
        entries.pop()
    elif problem == "duplicate":
        entries[1] = deepcopy(entries[0])
    else:
        entries.reverse()
    mock_engine(monkeypatch, output)
    with pytest.raises(ValueError, match="bibliography IDs"):
        format_numeric_bibliography([{"id": "first"}, {"id": "second"}], style)


def test_unsupported_structure_fails_instead_of_flattening(style, monkeypatch):
    output = response(["first"])
    output["blocks"][-1]["c"][1][0]["c"][1] = [node("BulletList", [])]
    mock_engine(monkeypatch, output)
    with pytest.raises(ValueError, match="bibliography block BulletList"):
        format_numeric_bibliography([{"id": "first"}], style)


def test_unsupported_indentation_is_not_silently_lost(style, monkeypatch):
    output = response(["first"])
    output["blocks"][-1]["c"][1][0]["c"][1][0]["c"][1]["c"][0][1] = ["csl-indent"]
    mock_engine(monkeypatch, output)
    with pytest.raises(ValueError, match="indented bibliography content"):
        format_numeric_bibliography([{"id": "first"}], style)


@pytest.mark.parametrize("failure", ["timeout", "engine", "json"])
def test_engine_errors_are_actionable(style, monkeypatch, failure):
    monkeypatch.setattr("cfdpaper.publication.citation_style.shutil.which", lambda name: "pandoc")

    def fail(*args, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired("pandoc", 60)
        if failure == "engine":
            raise subprocess.CalledProcessError(1, "pandoc")
        return SimpleNamespace(stdout="not json")

    monkeypatch.setattr("cfdpaper.publication.citation_style.subprocess.run", fail)
    with pytest.raises(RuntimeError, match="Pandoc"):
        format_numeric_bibliography(records(), style)


def test_missing_duplicate_ids_and_empty_bibliography(style):
    for bad in ([{}], [{"id": "a"}, {"id": "a"}], [{"id": " "}]):
        with pytest.raises(ValueError, match="unique nonblank"):
            format_numeric_bibliography(bad, style)
    assert format_numeric_bibliography([], style) == []


@pytest.mark.skipif(not shutil.which("pandoc"), reason="optional Pandoc is not installed")
def test_real_pandoc_preserves_numeric_order_unicode_and_emphasis(style):
    result = format_numeric_bibliography(records(), style)
    assert [entry["id"] for entry in result] == [r["id"] for r in records()]
    assert result[0]["text"] == "Zeta 温度. Synthetic Journal. 12"
    assert any(run.get("italic") and "温度" in run["text"] for run in result[0]["runs"])
    assert any(run.get("bold") and run["text"] == "12" for run in result[0]["runs"])


@pytest.mark.skipif(not shutil.which("pandoc"), reason="optional Pandoc is not installed")
def test_real_pandoc_rejects_alphabetically_renumbered_style(style):
    style.write_text(
        STYLE.replace(
            '<bibliography second-field-align="flush">',
            '<bibliography second-field-align="flush"><sort><key variable="title"/></sort>',
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="bracket numeric"):
        format_numeric_bibliography(records(), style)
