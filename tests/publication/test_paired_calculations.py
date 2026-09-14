"""Public synthetic tests: scalar extraction and source-dependent paired contrasts."""

import json

import pytest

from cfdpaper.publication.section import _TableCalculation, assemble_section, prepare_section
from cfdpaper.publication.table_evidence import calculate_table, resolve_table_result


def definition(**changes):
    return dict(
        id="pair",
        source="sources/raw.csv",
        operation="paired_change",
        columns={"value": "value"},
        units={"value": "K"},
        domain="Same interface spatial SD",
        group_by="condition",
        pair_by="geometry",
        reference="base",
        comparison="new",
        quantity_kind="temperature-difference",
        **changes,
    )


def compute(path, config):
    keys = (
        "operation",
        "columns",
        "group_by",
        "pair_by",
        "reference",
        "comparison",
        "units",
        "quantity_kind",
        "temperature_reference",
    )
    return {**config, **calculate_table(path, **{k: config[k] for k in keys if k in config})}


def test_single_scalar_is_not_a_population_or_uncertainty(tmp_path):
    path = tmp_path / "source.csv"
    path.write_text("case,value\na,12\nb,\n", encoding="utf-8")
    result = calculate_table(
        path, operation="scalar_select", columns={"value": "value"}, group_by="case"
    )
    assert result["groups"][0]["result"] == {"value": 12}
    assert result["groups"][1]["status"] == "missing-values"
    path.write_text("case,value\na,12\na,12\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one"):
        calculate_table(
            path, operation="scalar_select", columns={"value": "value"}, group_by="case"
        )


def test_pairs_select_by_identity_not_row_order_and_keep_provenance(tmp_path):
    path = tmp_path / "source.csv"
    path.write_text("condition,geometry,value\nhot,new,7\ncold,base,5\nhot,base,10\ncold,new,3\n")
    report = compute(path, definition())
    result = resolve_table_result(
        [report],
        calculation_id="pair",
        group="cold",
        field="relative_reduction",
        percentage=True,
        places=1,
    )
    assert result["value"] == "40.0"
    assert result["csv_records"] == [3, 5]
    assert result["unit"] == "%"
    assert (
        resolve_table_result([report], calculation_id="pair", group="hot", field="difference")[
            "raw_value"
        ]
        == -3
    )


@pytest.mark.parametrize("body", ["hot,base,10\n", "hot,base,10\nhot,new,7\nhot,new,7\n"])
def test_missing_or_ambiguous_pair_cannot_be_silently_averaged(tmp_path, body):
    path = tmp_path / "source.csv"
    path.write_text("condition,geometry,value\n" + body)
    with pytest.raises(ValueError, match="expected one"):
        compute(path, definition())


def test_absolute_temperature_difference_and_origin_invariant_rise_ratio(tmp_path):
    path = tmp_path / "source.csv"
    config = definition()
    config.update(units={"value": "degC"}, quantity_kind="absolute-temperature")
    path.write_text("condition,geometry,value\nhot,base,80\nhot,new,85\n")
    report = compute(path, config)
    delta = resolve_table_result([report], calculation_id="pair", group="hot", field="difference")
    assert (delta["raw_value"], delta["unit"]) == (5, "K")
    with pytest.raises(ValueError, match="missing or nonfinite"):
        resolve_table_result([report], calculation_id="pair", group="hot", field="relative_change")
    config["temperature_reference"] = 30
    celsius_ratio = compute(path, config)["groups"][0]["result"]["relative_change"]
    config.update(units={"value": "K"}, temperature_reference=303.15)
    path.write_text("condition,geometry,value\nhot,base,353.15\nhot,new,358.15\n")
    assert compute(path, config)["groups"][0]["result"]["relative_change"] == pytest.approx(
        celsius_ratio
    )


def test_zero_denominator_keeps_difference_but_not_relative_result(tmp_path):
    path = tmp_path / "source.csv"
    path.write_text("condition,geometry,value\nhot,base,0\nhot,new,3\n")
    result = compute(path, definition())["groups"][0]["result"]
    assert result == {"difference": 3, "relative_change": None, "relative_reduction": None}


def test_old_calculation_serialization_does_not_change_reviewed_snapshots():
    old = dict(
        id="old",
        source="sources/a.csv",
        operation="population",
        columns={"value": "v"},
        units={"value": "K"},
        domain="Old supplied record",
        group_by=None,
    )
    assert _TableCalculation.model_validate(old).model_dump() == old


def test_assembly_recomputes_paired_ratio_from_changed_raw_record(tmp_path):
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources/raw.csv").write_text("condition,geometry,value\nhot,base,10\nhot,new,6\n")
    data = dict(
        section_id="results",
        title="Response",
        question="How does spread change?",
        figures=[],
        table_calculations=[definition()],
        evidence=[
            dict(
                id="reduction",
                kind="metric",
                text="Relative spatial SD reduction",
                source="sources/raw.csv; matched hot geometry pair",
                result_ref=dict(
                    calculation_id="pair", group="hot", field="relative_reduction", percentage=True
                ),
            )
        ],
        duties=[dict(purpose="Compare spread", evidence_ids=["reduction"], figure_ids=[])],
    )
    source = tmp_path / "input.json"
    source.write_text(json.dumps(data))
    package = prepare_section(source, tmp_path / "package")
    draft = dict(
        title="Response",
        paragraphs=[
            dict(
                text="Spread decreases by {{value:reduction}}.",
                evidence_ids=["reduction"],
                figure_ids=[],
            )
        ],
        captions={},
        evidence_notes=[],
        image_observations={},
    )
    draft_path = tmp_path / "draft.json"
    draft_path.write_text(json.dumps(draft))
    before = assemble_section(package, draft_path, tmp_path / "before")
    assert "40.000 %" in (before / "section.md").read_text(encoding="utf-8")
    (package / "sources/raw.csv").write_text("condition,geometry,value\nhot,base,10\nhot,new,8\n")
    after = assemble_section(package, draft_path, tmp_path / "after")
    assert "20.000 %" in (after / "section.md").read_text(encoding="utf-8")
    assert "40.000 %" not in (after / "section.md").read_text(encoding="utf-8")
    assert "40.000 %" in (before / "section.md").read_text(encoding="utf-8")
