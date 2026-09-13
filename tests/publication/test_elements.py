import pytest

from cfdpaper.publication.elements import MathNode, SectionTable, math_text, math_xml


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
    assert table.rows[-2].cells[0].paragraphs[0].paragraph_format.keep_with_next is None
    assert document.paragraphs[-1].text == "Definition."
