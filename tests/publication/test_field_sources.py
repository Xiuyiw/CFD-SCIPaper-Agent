import json
import runpy
import shutil
from pathlib import Path

import numpy as np
import pytest

from cfdpaper.analysis_suggestions import compile_analysis, prepare_analysis
from cfdpaper.publication.analysis_section import _points
from cfdpaper.publication.section import assemble_section, prepare_section
from cfdpaper.publication.table_evidence import calculate_table, resolve_table_result


def definition(source="sources/field.npz"):
    return dict(
        id="wall",
        source=source,
        operation="weighted_population",
        columns={"value": "temperature", "weight": "area"},
        units={"value": "K", "weight": "m2"},
        weight_kind="area",
        quantity_kind="absolute-temperature",
        domain="Exported wall elements",
    )


def compute(path, **extra):
    kwargs = definition()
    for key in ("id", "source", "domain"):
        kwargs.pop(key)
    return calculate_table(path, **kwargs, **extra)


def test_npz_reduction_uses_original_arrays_and_zero_based_locations(tmp_path):
    path = tmp_path / "field.npz"
    np.savez(path, temperature=[300.0, 320.0], area=[1.0, 3.0], irrelevant=np.zeros((5, 3)))
    result = compute(path)
    assert result["groups"][0]["result"]["weighted_mean"] == 315
    assert result["groups"][0]["array_indices"] == [0, 1]
    assert "csv_records" not in result["groups"][0]
    ref = resolve_table_result(
        [{**definition(), **result}], calculation_id="wall", group="all", field="weighted_std"
    )
    assert ref["unit"] == "K"
    assert ref["array_indices"] == [0, 1]


def test_fractional_region_and_complement_close_without_centroid_inference(tmp_path):
    path = tmp_path / "field.npz"
    np.savez(path, temperature=[300.0, 320.0], area=[1.0, 3.0], fraction=[1.0, 0.25])
    whole = compute(path)["groups"][0]["result"]
    inside = compute(path, region_fraction="fraction")["groups"][0]["result"]
    outside = compute(path, region_fraction="fraction", region_complement=True)["groups"][0][
        "result"
    ]
    assert inside["weight_sum"] == 1.75
    assert outside["weight_sum"] == 2.25
    assert outside["weighted_mean"] == 320
    assert (
        inside["weighted_mean"] * inside["weight_sum"]
        + outside["weighted_mean"] * outside["weight_sum"]
    ) == pytest.approx(whole["weighted_mean"] * whole["weight_sum"])


@pytest.mark.parametrize("fraction", [[0.0, 0.0], [1.0, 1.1], [1.0, float("nan")]])
def test_bad_or_empty_region_not_reported_as_zero_temperature(tmp_path, fraction):
    path = tmp_path / "field.npz"
    np.savez(path, temperature=[300.0, 320.0], area=[1.0, 3.0], fraction=fraction)
    with pytest.raises(ValueError):
        compute(path, region_fraction="fraction")


@pytest.mark.parametrize(
    "values", [np.ones((2, 2)), np.array([300.0]), np.array([{"bad": 1}, {"bad": 2}], dtype=object)]
)
def test_npz_does_not_flatten_mismatched_or_object_arrays(tmp_path, values):
    path = tmp_path / "field.npz"
    np.savez(path, temperature=values, area=[1.0, 3.0])
    with pytest.raises(ValueError):
        compute(path)


def test_npz_original_change_reaches_bound_prose_and_table(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    np.savez(sources / "field.npz", temperature=[300.0, 320.0], area=[1.0, 3.0])
    data = dict(
        section_id="wall",
        title="Wall distribution",
        question="How warm?",
        figures=[],
        table_calculations=[definition()],
        evidence=[
            dict(
                id="mean",
                kind="metric",
                text="Area mean",
                source="sources/field.npz",
                result_ref=dict(calculation_id="wall", group="all", field="weighted_mean"),
            )
        ],
        duties=[dict(purpose="Explain mean", evidence_ids=["mean"], figure_ids=[])],
    )
    source = tmp_path / "input.json"
    source.write_text(json.dumps(data), encoding="utf-8")
    prepared = prepare_section(source, tmp_path / "writing")
    draft = dict(
        title="Wall distribution",
        paragraphs=[dict(text="Mean: {{value:mean}}.", evidence_ids=["mean"], figure_ids=[])],
        captions={},
        evidence_notes=[],
        image_observations={},
        tables=[
            dict(
                table_id="1",
                caption="Area mean",
                after_section_id="wall",
                columns=["Temperature"],
                rows=[["{{value:mean}}"]],
                evidence_ids=["mean"],
            )
        ],
    )
    draft_path = tmp_path / "draft.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    first = assemble_section(prepared, draft_path, tmp_path / "first")
    assert "315.000" in (first / "section.md").read_text(encoding="utf-8")
    np.savez(prepared / "sources/field.npz", temperature=[300.0, 340.0], area=[1.0, 3.0])
    second = assemble_section(prepared, draft_path, tmp_path / "second")
    assert (second / "section.md").read_text(encoding="utf-8").count("330.000") == 2


def test_npz_proposal_region_definition_survives_portable_pipeline(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    np.savez(raw / "field.npz", temperature=[300.0, 320.0], area=[1.0, 3.0], fraction=[1.0, 0.25])
    (raw / "method.md").write_text(
        "Synthetic facet mean temperatures in K and areas in m2.\n"
        "fraction is the explicit area overlap with region R; values are constant within facets.\n",
        encoding="utf-8",
    )
    package = tmp_path / "analysis"
    prepare_analysis(raw, package)
    calc = {
        **definition(),
        "region_fraction": "fraction",
        "region_complement": True,
        "definition_source": {"path": "sources/method.md", "locator": "L1-L2"},
        "comparison": {"status": "supported", "scope": "Supplied constant facet values"},
        "member_id": ["__index__"],
        "expected_members": [["0"], ["1"]],
        "interpretation_limits": ["Element-constant reconstruction, not subfacet resolution"],
    }
    candidate = dict(
        id="wall",
        title="Complement temperature",
        question="Where is heat concentrated?",
        rationale="Compare regional and complementary means",
        presentation="table",
        calculations=[calc],
        interpretation_limits=["Synthetic example"],
    )
    path = package / "proposal.json"
    path.write_text(json.dumps({"candidates": [candidate]}), encoding="utf-8")
    compiled = compile_analysis(package, path, "wall", tmp_path / "compiled")
    saved = json.loads(compiled.read_text(encoding="utf-8"))
    assert saved["table_calculations"][0]["region_complement"] is True
    reports = json.loads((compiled.parent / "table-results.json").read_text(encoding="utf-8"))
    assert reports[0]["groups"][0]["result"]["weighted_mean"] == 320
    assert (compiled.parent / "sources/field.npz").read_bytes() == (raw / "field.npz").read_bytes()


def test_csv_region_calculation_and_complement_definition_validation(tmp_path):
    path = tmp_path / "wall.csv"
    path.write_text("temperature,area,fraction\n300,1,1\n320,3,.25\n", encoding="utf-8")
    result = compute(path, region_fraction="fraction", region_complement=True)
    assert result["groups"][0]["result"]["weighted_mean"] == 320
    assert result["groups"][0]["csv_records"] == [2, 3]
    with pytest.raises(ValueError, match="requires"):
        compute(path, region_complement=True)


def test_npz_named_pair_reads_selector_array(tmp_path):
    path = tmp_path / "pair.npz"
    np.savez(path, pressure=[5.0, 3.0], geometry=["basic", "modified"])
    result = calculate_table(
        path,
        operation="paired_change",
        columns={"value": "pressure"},
        units={"value": "Pa"},
        pair_by="geometry",
        reference="basic",
        comparison="modified",
    )
    assert result["groups"][0]["result"]["difference"] == -2


def test_npz_grouped_weights_keep_distinct_source_indices(tmp_path):
    path = tmp_path / "groups.npz"
    np.savez(path, temperature=[300.0, 320.0, 310.0], area=[1.0, 3.0, 2.0], case=["A", "A", "B"])
    result = compute(path, group_by="case")
    assert result["groups"][0]["array_indices"] == [0, 1]
    assert result["groups"][1]["array_indices"] == [2]
    assert result["groups"][1]["result"]["weighted_mean"] == 310


def test_array_example_relocates_recomputes_and_matches_plot_inputs(tmp_path):
    script = Path(__file__).parents[2] / "examples/spatial-diagnostics/run_array_example.py"
    root = tmp_path / "original"
    runpy.run_path(str(script))["run"](root)
    data = json.loads((root / "compiled/analysis-input.json").read_text(encoding="utf-8"))
    points = _points(data, root / "compiled")
    assert [p["value"] for p in points] == ["315.000", "308.571", "320.000"]
    assert "308.571" in (root / "section/section.md").read_text(encoding="utf-8")
    reports = json.loads((root / "compiled/table-results.json").read_text(encoding="utf-8"))
    values = [r["groups"][0]["result"] for r in reports]
    assert values[1]["weight_sum"] + values[2]["weight_sum"] == values[0]["weight_sum"]
    assert sum(r["weighted_mean"] * r["weight_sum"] for r in values[1:]) == pytest.approx(1260)
    moved = tmp_path / "relocated"
    shutil.move(root, moved)
    writing = moved / "section-input/writing"
    np.savez(
        writing / "sources/wall.npz",
        temperature=[300.0, 340.0],
        area=[1.0, 3.0],
        overlap=[1.0, 0.25],
    )
    assembled = assemble_section(writing, moved / "draft.json", moved / "updated")
    text = (assembled / "section.md").read_text(encoding="utf-8")
    for number in ("330.000", "317.143", "340.000"):
        assert text.count(number) == 2
