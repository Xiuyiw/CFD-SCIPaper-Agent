"""Regression for literal scaled source units observed in actual Word output."""

import pytest

from cfdpaper.publication.elements import display_scientific_text
from cfdpaper.publication.table_evidence import display_unit


@pytest.mark.parametrize(
    "source,expected",
    [
        ("10^-6 kgmol/s", "× 10⁻⁶ kgmol·s⁻¹"),
        ("10^-6 kmol/s", "× 10⁻⁶ kmol·s⁻¹"),
        ("10^3 W", "× 10³ W"),
        ("10^+3 W", "× 10⁺³ W"),
        ("kgmol/s", "kgmol·s⁻¹"),
        ("kmol/s", "kmol·s⁻¹"),
        ("10^-6 unknown-source-unit", "10^-6 unknown-source-unit"),
        ("ppm, dry at 6% O2", "ppm, dry at 6% O2"),
    ],
)
def test_scaled_unit_display_preserves_scale_and_does_not_guess_labels(source, expected):
    assert display_unit(source) == expected
    assert display_unit(expected) == expected


def test_scaled_value_remains_one_readable_docx_quantity():
    text = "21.27 " + display_unit("10^-6 kgmol/s")
    shown = display_scientific_text(text)
    assert shown == "21.27\u00a0×\u00a010⁻⁶\u00a0kgmol·s⁻¹"
    assert display_scientific_text(shown) == shown


def test_scaled_notation_preserves_native_table_input():
    docx = pytest.importorskip("docx")
    from cfdpaper.publication.elements import SectionTable, add_table
    from cfdpaper.publication.style import PublicationStyle

    original = "21.27 " + display_unit("10^-6 kgmol/s")
    table = SectionTable(
        table_id="1",
        caption="NO source",
        after_section_id="results",
        columns=["Case", "Integrated source"],
        rows=[["A", original]],
        numeric_columns=[1],
    )
    document = docx.Document()
    add_table(document, table, PublicationStyle())
    assert table.rows[0][1] == original
    assert document.tables[0].cell(1, 1).text == "21.27\u00a0×\u00a010⁻⁶\u00a0kgmol·s⁻¹"
