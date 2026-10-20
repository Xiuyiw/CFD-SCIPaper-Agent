"""The editable view uses existing scientific facts and persistent source identities."""

from copy import deepcopy

import pytest

from cfdpaper.publication.document_blocks import build_document


def source():
    return {
        "section_id": "methods",
        "title": "Thermal comparison",
        "paragraphs": [
            {
                "paragraph_id": "definition",
                "text": "The area is 2 m².",
                "source_text": "The area is {{value:area}}.",
                "figure_ids": [],
                "semantic_runs": [
                    {"text": "The area is "},
                    {"text": "2 m²", "token": "{{value:area}}", "span_id": "value-area-0"},
                    {"text": "."},
                ],
            },
            {"paragraph_id": "explanation", "text": "This is an area integral.", "figure_ids": []},
        ],
        "tables": [
            {
                "table_id": "properties",
                "caption": "Material properties",
                "columns": ["k"],
                "rows": [["2"]],
            }
        ],
        "equations": [{"equation_id": "balance", "expression": {"kind": "symbol", "text": "Q"}}],
        "figures": [],
        "references": [],
    }


def test_one_order_for_prose_equation_explanation_and_table():
    data = source()
    data["block_order"] = [
        "paragraph:definition",
        "equation:balance",
        "paragraph:explanation",
        "table:properties",
    ]
    result = build_document(data)
    assert [b["kind"] for b in result["blocks"]] == ["paragraph", "equation", "paragraph", "table"]
    assert result["blocks"][0]["text"] == "The area is {{value:area}}."
    assert result["blocks"][0]["spans"][0]["text"] == "2 m²"
    assert data == {**source(), "block_order": data["block_order"]}


def test_numeric_refresh_does_not_change_identity_but_changes_baseline():
    data = source()
    before = build_document(data)
    data["paragraphs"][0]["text"] = "The area is 3 m²."
    data["paragraphs"][0]["semantic_runs"][1]["text"] = "3 m²"
    after = build_document(data)
    assert [b["id"] for b in before["blocks"]] == [b["id"] for b in after["blocks"]]
    assert before["baseline_id"] != after["baseline_id"]


def test_profiles_share_facts_and_do_not_mutate_the_source():
    data = source()
    before = deepcopy(data)
    results = [build_document(data, profile=p) for p in ("research", "report", "conference")]
    assert all(r["blocks"] == results[0]["blocks"] for r in results)
    assert data == before
    with pytest.raises(ValueError, match="profile"):
        build_document(data, profile="magazine")


def test_explicit_order_cannot_omit_or_duplicate_an_object():
    data = source()
    data["block_order"] = ["paragraph:definition", "paragraph:definition"]
    with pytest.raises(ValueError, match="order"):
        build_document(data)


def test_legacy_ids_are_content_based_and_survive_insertion():
    data = source()
    for p in data["paragraphs"]:
        p.pop("paragraph_id")
    before = build_document(data)
    data["paragraphs"].insert(0, {"text": "Inserted paragraph", "figure_ids": []})
    after = build_document(data)
    assert [b["id"] for b in before["blocks"] if b["kind"] == "paragraph"] == [
        b["id"] for b in after["blocks"] if b["kind"] == "paragraph"
    ][1:]


def test_duplicate_explicit_identity_rejected():
    data = source()
    data["paragraphs"][1]["paragraph_id"] = "definition"
    with pytest.raises(ValueError, match="identity"):
        build_document(data)
