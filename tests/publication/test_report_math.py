"""The report entry point reuses editable manuscript math without rewriting prose."""

import copy
import json
import xml.etree.ElementTree as ET
import zipfile

import pytest

from cfdpaper.publication.elements import MathNode
from cfdpaper.publication.report_math import apply_report_formulas, normalize_report_formulas


def symbol(text):
    return {"kind": "symbol", "text": text}


def formulas():
    return {
        "Re": {
            "expression": {
                "kind": "row",
                "children": [
                    symbol("Re"),
                    symbol("="),
                    {
                        "kind": "fraction",
                        "children": [
                            {"kind": "row", "children": [symbol(c) for c in "ρUD"]},
                            symbol("μ"),
                        ],
                    },
                ],
            },
            "source": "sources/definitions.json#/Re",
        },
        "intensity": {
            "expression": {
                "kind": "row",
                "children": [
                    symbol("I"),
                    symbol("="),
                    {"kind": "text", "text": "0.16 "},
                    {
                        "kind": "sup",
                        "children": [symbol("Re"), {"kind": "text", "text": "-0.125"}],
                    },
                ],
            },
            "source": "sources/definitions.json#/intensity",
        },
        "unused": {
            "expression": symbol("z"),
            "source": "sources/definitions.json#/unused",
        },
    }


def test_normalize_validates_math_and_preserves_source_without_mutating_input():
    declarations = formulas()
    before = copy.deepcopy(declarations)
    normalized = normalize_report_formulas(declarations)
    assert normalize_report_formulas(None) == {}
    assert normalize_report_formulas({}) == {}
    assert (
        normalized["Re"]["expression"]
        == MathNode.model_validate(declarations["Re"]["expression"]).model_dump()
    )
    assert normalized["Re"]["source"] == declarations["Re"]["source"]
    normalized["Re"]["expression"]["children"][0]["text"] = "changed"
    assert declarations == before


def test_formula_definition_can_use_existing_line_locator():
    declaration = {"Re": {"expression": symbol("Re"), "source": "method.md:L21-L23"}}
    assert normalize_report_formulas(declaration)["Re"]["source"] == "method.md:L21-L23"


@pytest.mark.parametrize(
    "declarations,match",
    [
        ([], "formulas.*dictionary"),
        ({"bad id": {"expression": symbol("x"), "source": "definitions.json"}}, "ID"),
        ({"Re": {"source": "definitions.json"}}, "expression.*source"),
        (
            {"Re": {"expression": symbol("x"), "source": "definitions.json", "tex": "x"}},
            "expression.*source",
        ),
        (
            {"Re": {"expression": "Re = rho U D / mu", "source": "definitions.json"}},
            "Re.*expression.*MathNode dictionary",
        ),
        (
            {
                "Re": {
                    "expression": {"kind": "fraction", "children": [symbol("x")]},
                    "source": "definitions.json",
                }
            },
            "Re.*expression",
        ),
    ],
)
def test_invalid_formula_declarations_are_actionable(declarations, match):
    with pytest.raises(ValueError, match=match):
        normalize_report_formulas(declarations)


@pytest.mark.parametrize(
    "source",
    [
        None,
        "",
        "  ",
        "/definitions.json",
        r"C:\definitions.json",
        "../definitions.json",
        "sources/../definitions.json",
        "https://example.com/defs",
        "#/Re",
    ],
)
def test_formula_source_requires_a_nonblank_relative_file_locator(source):
    with pytest.raises(ValueError, match="Re.*source.*relative"):
        normalize_report_formulas({"Re": {"expression": symbol("x"), "source": source}})


def test_apply_only_fills_referenced_missing_math_and_preserves_author_priority():
    author_expression = {"kind": "text", "text": "Author's retained expression"}
    draft = {
        "title": "Keep this title",
        "paragraphs": [
            {
                "text": "Definition {{math:Re}} and {{math:intensity}}.",
                "inline_math": {"Re": author_expression},
            },
            {"text": "Retain literal prose I=0.16 Re^(-0.125) without rewriting it."},
        ],
        "evidence_notes": ["Author note"],
    }
    before = copy.deepcopy(draft)
    declarations = formulas()
    original_declarations = copy.deepcopy(declarations)
    result = apply_report_formulas(draft, declarations)
    assert draft == before
    assert declarations == original_declarations
    assert result["paragraphs"][0]["text"] == draft["paragraphs"][0]["text"]
    assert result["paragraphs"][0]["inline_math"]["Re"] == author_expression
    assert set(result["paragraphs"][0]["inline_math"]) == {"Re", "intensity"}
    assert "inline_math" not in result["paragraphs"][1]
    assert "formulas" not in result and "source" not in result["paragraphs"][0]
    result["paragraphs"][0]["inline_math"]["Re"]["text"] = "changed"
    result["evidence_notes"].append("new")
    assert draft == before


def test_author_local_math_does_not_need_a_formula_library_entry():
    draft = {"paragraphs": [{"text": "Use {{math:local}}.", "inline_math": {"local": symbol("q")}}]}
    assert apply_report_formulas(draft, {}) == draft


def test_unknown_formula_identifies_paragraph_and_remedy_without_mutation():
    draft = {"paragraphs": [{"text": "Known {{math:Re}}, then unknown {{math:missing}}."}]}
    before = copy.deepcopy(draft)
    with pytest.raises(ValueError, match=r"paragraphs\[0\].*missing.*formulas\['missing'\]"):
        apply_report_formulas(draft, formulas())
    assert draft == before


@pytest.mark.parametrize("export_mode", ["section", "formal"])
def test_report_formulas_reach_native_docx_fraction_and_superscript(tmp_path, export_mode):
    pytest.importorskip("docx")
    from cfdpaper.publication.formal_export import export_formal_manuscript
    from cfdpaper.publication.section import (
        assemble_section,
        export_section_docx,
        prepare_section,
    )

    (tmp_path / "sources").mkdir()
    definitions = tmp_path / "sources/definitions.json"
    definitions.write_text(json.dumps(formulas(), ensure_ascii=False), encoding="utf-8")
    original_definitions = definitions.read_bytes()
    source = {
        "section_id": "methods",
        "title": "Native formula definitions",
        "question": "Can existing native math render the declared definitions?",
        "figures": [],
        "evidence": [
            {
                "id": "definition",
                "kind": "literature",
                "text": "Synthetic definitions",
                "source": "sources/definitions.json",
            }
        ],
        "duties": [
            {
                "purpose": "Define the synthetic notation",
                "evidence_ids": ["definition"],
                "figure_ids": [],
            }
        ],
        "source_files": ["sources/definitions.json"],
    }
    source_path = tmp_path / "input.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    draft = {
        "title": source["title"],
        "paragraphs": [
            {
                "text": "Definitions {{math:Re}} and {{math:intensity}} follow "
                "{{cite:definition}}.",
                "evidence_ids": ["definition"],
                "figure_ids": [],
            }
        ],
        "captions": {},
        "image_observations": {},
        "evidence_notes": [],
    }
    before = copy.deepcopy(draft)
    draft_path = tmp_path / "draft.json"
    draft_path.write_text(json.dumps(apply_report_formulas(draft, formulas())), encoding="utf-8")
    package = prepare_section(source_path, tmp_path / "package")
    section = assemble_section(package, draft_path, tmp_path / "section")
    export = export_section_docx if export_mode == "section" else export_formal_manuscript
    output = export(section, tmp_path / "report.docx")
    with zipfile.ZipFile(output) as archive:
        raw_xml = archive.read("word/document.xml")
    document = ET.fromstring(raw_xml)
    ns = {"m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}
    native_math = document.findall(".//m:oMath", ns)
    assert len(native_math) == 2
    fraction = native_math[0].find("m:f", ns)
    assert fraction is not None
    assert "".join(fraction.find("m:num", ns).itertext()) == "ρUD"
    assert "".join(fraction.find("m:den", ns).itertext()) == "μ"
    assert "".join(native_math[0].itertext()) == "Re=ρUDμ"
    superscript = native_math[1].find("m:sSup", ns)
    assert superscript is not None
    assert "".join(superscript.find("m:e", ns).itertext()) == "Re"
    assert "".join(superscript.find("m:sup", ns).itertext()) == "-0.125"
    assert "".join(native_math[1].itertext()) == "I=0.16 Re-0.125"
    assert b"{{math:" not in raw_xml and b"^(" not in raw_xml
    assert definitions.read_bytes() == original_definitions and draft == before
    if export_mode == "formal":
        tex = export_formal_manuscript(section, tmp_path / "report.tex").read_text(encoding="utf-8")
        assert r"\frac{\rho U D}{\mu}" in tex
        assert r"{R e}^{\text{-0.125}}" in tex
