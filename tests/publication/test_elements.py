import pytest

from cfdpaper.publication.elements import MathNode, SectionTable, math_text, math_xml


@pytest.mark.parametrize(
    "source,expected",
    [
        ("Change: -5.51 K.", "Change: −\u20605.51\u00a0K."),
        ("(-.51); +2.0 and -5", "(−\u2060.51); +\u20602.0 and −\u20605"),
        ("-1.20e-3 Pa", "−\u20601.20e−\u20603\u00a0Pa"),
        ("2E+4 W and 5.51 %", "2E+\u20604\u00a0W and 5.51\u00a0%"),
        ("43.40 °C; 2.939 K", "43.40\u00a0°C; 2.939\u00a0K"),
        ("5 W m^-2 K^-1", "5\u00a0W\u00a0m^−\u20602\u00a0K^−\u20601"),
        ("1.2 m/s; 3 kg m⁻³", "1.2\u00a0m/\u2060s; 3\u00a0kg\u00a0m⁻³"),
        ("5 mm and 4 minutes", "5\u00a0mm and 4 minutes"),
    ],
)
def test_scientific_display_glues_signs_and_recognized_units(source, expected):
    from cfdpaper.publication.elements import display_scientific_text

    assert display_scientific_text(source) == expected
    assert display_scientific_text(expected) == expected


@pytest.mark.parametrize(
    "source",
    [
        "Case-5.51 G1.3 ID_2E-4 run-123 1.2-3 v0.10.0 -5.51-case -5.51.dat",
        "2026-09-14 2026/09/14 10:30",
        "https://example.org/-5.51?unit=2e-3 https://example.org/5%20K",
        "[1-3] [Smith-2025] [@paper-5.51] {{value:e-3}}",
        "`x=-5.51 K` and ```x = -1.20e-3```",
        r"$x=-5.51$ $$x=-5.51$$ \(x=-5.51\) \[x=-5.51\]",
        "5 Kelvin 3 seconds; - value; thermal-support; x-5.51",
    ],
)
def test_scientific_display_preserves_nonquantity_syntax(source):
    from cfdpaper.publication.elements import display_scientific_text

    assert display_scientific_text(source) == source


def test_scientific_display_in_docx_does_not_mutate_table_source():
    docx = pytest.importorskip("docx")
    from cfdpaper.publication.elements import add_table
    from cfdpaper.publication.style import PublicationStyle

    table = SectionTable(
        table_id="case-5",
        caption="Change at 5 W",
        after_section_id="results",
        columns=["Case ID", "Change at 300 K"],
        rows=[["ID-5.51", "-5.51 K"]],
        note="Difference: -1.2e-3 Pa.",
    )
    original = table.model_dump()
    document = docx.Document()
    add_table(document, table, PublicationStyle())
    assert table.model_dump() == original
    assert document.paragraphs[0].text == "Table case-5. Change at 5\u00a0W"
    assert document.tables[0].rows[0].cells[1].text == "Change at 300\u00a0K"
    assert document.tables[0].rows[1].cells[0].text == "ID-5.51"
    assert document.tables[0].rows[1].cells[1].text == "−\u20605.51\u00a0K"
    assert document.paragraphs[-1].text == "Difference: −\u20601.2e−\u20603\u00a0Pa."


def test_docx_body_and_figure_caption_use_display_only_typesetting(tmp_path):
    import json

    docx = pytest.importorskip("docx")
    from docx.oxml.ns import qn
    from PIL import Image

    from cfdpaper.publication.section import export_section_docx

    Image.new("RGB", (800, 500), "white").save(tmp_path / "plot.png")
    prose = "Difference: -5.51 K [1-3]. Formula: "
    data = {
        "title": "Scientific display",
        "paragraphs": [
            {
                "text": prose,
                "figure_ids": ["f-5"],
                "runs": [
                    {"text": prose},
                    {"math": {"kind": "text", "text": "-5.51 K"}},
                ],
            }
        ],
        "figures": [{"id": "f-5", "path": "plot.png", "caption": "Response at 5 W."}],
        "references": [],
        "bindings": [{"evidence_id": "e-5", "value": "-5.51", "unit": "K"}],
    }
    source = tmp_path / "section.json"
    source.write_text(json.dumps(data), encoding="utf-8")
    original = source.read_bytes()
    output = export_section_docx(tmp_path, tmp_path / "display.docx", layout="near-reference")
    document = docx.Document(output)
    assert document.paragraphs[1].text == "Difference: −\u20605.51\u00a0K [1-3]. Formula: "
    assert document.paragraphs[-1].text == "Figure f-5. Response at 5\u00a0W."
    assert [node.text for node in document.element.iter(qn("m:t"))] == ["-5.51 K"]
    assert source.read_bytes() == original


def test_numbered_markdown_table_matches_prose_and_docx_caption():
    from cfdpaper.publication.export import _markdown_table

    table = SectionTable(
        table_id="2",
        caption="Spatial diagnostics",
        after_section_id="results",
        columns=["Field", "Mean"],
        rows=[["A", "43.4 °C"]],
        evidence_ids=[],
    )
    assert _markdown_table(table, numbered=True).startswith("**Table 2. Spatial diagnostics**")
    assert _markdown_table(table).startswith("**Spatial diagnostics**")


def symbol(text):
    return {"kind": "symbol", "text": text}


@pytest.mark.parametrize(
    "kind,count,tag",
    [
        ("sub", 2, "sSub"),
        ("sup", 2, "sSup"),
        ("subsup", 3, "sSubSup"),
        ("fraction", 2, "f"),
        ("sqrt", 1, "rad"),
        ("dot", 1, "acc"),
        ("overbar", 1, "acc"),
    ],
)
def test_math_nodes_are_editable_structures(kind, count, tag):
    pytest.importorskip("docx")
    node = MathNode(kind=kind, children=[symbol("x")] * count)
    xml = math_xml(node)[0]
    assert xml.tag.endswith("}" + tag)
    assert math_text(node)
    with pytest.raises(ValueError):
        MathNode(kind=kind, children=[symbol("x")] * (count + 1))


@pytest.mark.parametrize(
    "node",
    [
        {"kind": "latex", "text": "x"},
        {"kind": "symbol"},
        {"kind": "row", "text": "discarded", "children": [symbol("x")]},
    ],
)
def test_unsupported_or_ambiguous_math_is_not_silently_rendered(node):
    with pytest.raises(ValueError):
        MathNode.model_validate(node)


def test_table_retains_rectangular_semantics_and_widths():
    with pytest.raises(ValueError, match="column count"):
        SectionTable(
            table_id="1", caption="Data", columns=["a", "b"], rows=[["1"]], after_section_id="s1"
        )
    with pytest.raises(ValueError, match="widths"):
        SectionTable(
            table_id="1",
            caption="Data",
            columns=["a"],
            rows=[["1"]],
            after_section_id="s1",
            column_widths_mm=[float("nan")],
        )


def test_numeric_headers_align_with_their_column_values():
    docx = pytest.importorskip("docx")
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    from cfdpaper.publication.elements import add_table
    from cfdpaper.publication.style import PublicationStyle

    document = docx.Document()
    add_table(
        document,
        SectionTable(
            table_id="1",
            caption="Temperature descriptors",
            after_section_id="results",
            columns=["Field", "Mean temperature", "Spatial SD"],
            rows=[["Reference", "45.60 °C", "2.939 K"], ["Modified", "43.40 °C", "5.352 K"]],
            numeric_columns=[1, 2],
            column_widths_mm=[45, 60, 55],
        ),
        PublicationStyle(),
    )
    for row in document.tables[0].rows:
        assert [cell.paragraphs[0].alignment for cell in row.cells] == [
            WD_ALIGN_PARAGRAPH.LEFT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
        ]


def test_nested_flow_accents_and_table_note_pagination():
    docx = pytest.importorskip("docx")
    from docx.oxml.ns import qn

    from cfdpaper.publication.elements import add_table
    from cfdpaper.publication.style import PublicationStyle

    node = MathNode(kind="overbar", children=[MathNode(kind="dot", children=[symbol("m")])])
    xml = math_xml(node)[0]
    assert [e.get(qn("m:val")) for e in xml.iter(qn("m:chr"))] == ["\u0305", "\u0307"]
    assert [e.text for e in xml.iter(qn("m:t"))] == ["m"]
    document = docx.Document()
    add_table(
        document,
        SectionTable(
            table_id="1",
            caption="Data",
            columns=["x"],
            rows=[["1"], ["2"]],
            after_section_id="s",
            note="Definition.",
        ),
        PublicationStyle(),
    )
    table = document.tables[0]
    assert table.rows[-1]._tr.find(qn("w:trPr")).find(qn("w:cantSplit")) is not None
    assert table.rows[-1].cells[0].paragraphs[0].paragraph_format.keep_with_next is True
    assert table.rows[-2].cells[0].paragraphs[0].paragraph_format.keep_with_next is True
    assert document.paragraphs[-1].text == "Definition."


@pytest.mark.parametrize("value", ["Re", "Im", "Nu"])
def test_multi_letter_symbols_are_not_importer_keywords(value):
    pytest.importorskip("docx")
    from docx.oxml.ns import qn

    node = MathNode(kind="sub", children=[symbol(value), symbol("D")])
    xml = math_xml(node)[0]
    base = xml.find(qn("m:e"))
    assert [item.text for item in base.iter(qn("m:t"))] == list(value)
    assert not list(base.iter(qn("m:nor")))
    assert math_text(node) == f"{value}_(D)"


@pytest.mark.parametrize("value", ["(", ")", "mean (local)"])
def test_text_parentheses_do_not_receive_normal_text_escaping(value):
    pytest.importorskip("docx")
    from docx.oxml.ns import qn

    node = MathNode(kind="text", text=value)
    runs = math_xml(node)
    assert "".join(run.find(qn("m:t")).text for run in runs) == value
    for run in runs:
        text = run.find(qn("m:t")).text
        assert "\\" not in text
        assert bool(list(run.iter(qn("m:nor")))) is (text not in {"(", ")"})
    assert math_text(node) == value


@pytest.mark.parametrize("rows,compact", [(6, True), (60, False)])
@pytest.mark.parametrize("note", ["", "Definition."])
def test_compact_tables_keep_all_rows_without_chaining_following_text(rows, compact, note):
    docx = pytest.importorskip("docx")

    from cfdpaper.publication.elements import add_table
    from cfdpaper.publication.style import PublicationStyle

    document = docx.Document()
    add_table(
        document,
        SectionTable(
            table_id="1",
            caption="Data",
            columns=["Case", "Value"],
            rows=[[f"Case {i}", str(i)] for i in range(rows)],
            after_section_id="s",
            note=note,
        ),
        PublicationStyle(),
    )
    table = document.tables[0]
    assert table.rows[0]._tr.xpath("./w:trPr/w:tblHeader")
    for i, row in enumerate(table.rows):
        assert row._tr.xpath("./w:trPr/w:cantSplit")
        expected = bool(note) if i == rows else compact or i == 0
        for cell in row.cells:
            assert cell.paragraphs[0].paragraph_format.keep_with_next is expected
    tail = document.add_paragraph("Following text.")
    assert tail.paragraph_format.keep_with_next is None
    assert [cell.text for cell in table.rows[-1].cells] == [f"Case {rows - 1}", str(rows - 1)]


def test_few_rows_with_long_wrapped_text_are_not_forced_onto_one_page():
    docx = pytest.importorskip("docx")
    from cfdpaper.publication.elements import add_table
    from cfdpaper.publication.style import PublicationStyle

    document = docx.Document()
    add_table(
        document,
        SectionTable(
            table_id="1",
            caption="Data",
            columns=["Description"],
            rows=[["Long text " * 200], ["Another row"], ["Last row"]],
            after_section_id="s",
            column_widths_mm=[30],
        ),
        PublicationStyle(),
    )
    assert (
        document.tables[0].rows[1].cells[0].paragraphs[0].paragraph_format.keep_with_next is False
    )
