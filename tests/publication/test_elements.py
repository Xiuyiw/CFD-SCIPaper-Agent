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
