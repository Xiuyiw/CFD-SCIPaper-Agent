import csv
import json

import pytest

from cfdpaper.publication.analysis_section import build_analysis_section, render_analysis_figures
from cfdpaper.publication.section import assemble_section
from cfdpaper.publication.table_evidence import calculate_declared_table, resolve_table_result


def temporal_input(tmp_path, *, field="time_mean", **options):
    (tmp_path / "sources").mkdir(exist_ok=True)
    (tmp_path / "sources/history.csv").write_text("t,q\n0,2\n1,4\n3,8\n", encoding="utf-8")
    calculation = {
        "id": "history",
        "source": "sources/history.csv",
        "operation": "temporal",
        "columns": {"time": "t", "value": "q"},
        "units": {"time": "s", "value": "W"},
        "domain": "Saved model samples",
        "time_window": [0, 1],
        **options,
    }
    data = {
        "section_id": "history",
        "title": "Saved history",
        "question": "How does history vary?",
        "context": "Saved samples only.",
        "source_files": ["sources/history.csv"],
        "table_calculations": [calculation],
        "evidence": [
            {
                "id": "metric",
                "kind": "metric",
                "text": "History metric",
                "source": "sources/history.csv",
                "result_ref": {
                    "calculation_id": "history",
                    "group": "all",
                    "field": field,
                    "places": 3,
                },
            }
        ],
    }
    path = tmp_path / "analysis-input.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data


@pytest.mark.parametrize(
    "field,options,expected",
    [
        ("time_mean", {}, 3),
        ("integral", {}, 3),
        ("change", {"units": {"time": "s", "value": "J"}, "temporal_value_kind": "cumulative"}, 2),
        ("first_crossing_time", {"threshold": 3, "crossing_direction": "at-or-above"}, 1),
        ("first_crossing_time", {"threshold": 3, "crossing_direction": "at-or-below"}, 0),
    ],
)
def test_actual_plot_source_matches_bound_prose_and_window(tmp_path, field, options, expected):
    path, data = temporal_input(tmp_path, field=field, **options)
    package = build_analysis_section(path, tmp_path / "output")
    with (package.parent / "figures/analysis-1-source-data.csv").open() as stream:
        row = next(csv.DictReader(stream))
    report = {
        **data["table_calculations"][0],
        **calculate_declared_table(tmp_path / "sources/history.csv", data["table_calculations"][0]),
    }
    bound = resolve_table_result([report], **data["evidence"][0]["result_ref"])
    assert float(row["raw_value"]) == bound["raw_value"] == expected
    assert row["csv_records"] == "[2, 3]"
    assert report["groups"][0]["time_window"] == [0, 1]
    draft = {
        "title": data["title"],
        "paragraphs": [
            {
                "text": "The declared metric is {{value:metric}} in {{figure:1}}.",
                "evidence_ids": ["metric"],
                "figure_ids": ["1"],
            }
        ],
        "captions": {"1": "Declared history metric."},
        "evidence_notes": [],
        "image_observations": {"1": "not-viewed"},
    }
    draft_path = tmp_path / "draft.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    section = assemble_section(package, draft_path, tmp_path / "section")
    assert f"{expected:.3f}" in (section / "section.md").read_text(encoding="utf-8")
    assert "<text" in (package.parent / "figures/analysis-1.svg").read_text(encoding="utf-8")


def test_missing_event_fails_without_zero_or_fake_plot(tmp_path):
    path, _ = temporal_input(tmp_path, field="first_crossing_time", threshold=100)
    with pytest.raises(ValueError, match="missing"):
        render_analysis_figures(path)
    assert not (tmp_path / "figures/analysis-1.png").exists()


@pytest.mark.parametrize("compatible", [True, False])
def test_actual_comparison_plot_enforces_temporal_compatibility(tmp_path, compatible):
    path, data = temporal_input(tmp_path)
    second = dict(
        data["table_calculations"][0], id="other", time_window=[0, 1] if compatible else [1, 3]
    )
    data["table_calculations"].append(second)
    (tmp_path / "sources/methods.txt").write_text("Saved history contrast", encoding="utf-8")
    data["source_files"].append("sources/methods.txt")
    data["result_comparisons"] = [
        {
            "id": "contrast",
            "domain": "Saved model samples",
            "definition_source": "sources/methods.txt:L1",
            "comparison_scope": "Matched saved history",
            "status": "supported",
            "reference": {"calculation_id": "history", "group": "all", "field": "integral"},
            "comparison": {"calculation_id": "other", "group": "all", "field": "integral"},
        }
    ]
    data["evidence"][0]["result_ref"] = {
        "calculation_id": "contrast",
        "group": "all",
        "field": "difference",
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    if compatible:
        render_analysis_figures(path)
        with (tmp_path / "figures/analysis-1-source-data.csv").open() as stream:
            assert float(next(csv.DictReader(stream))["raw_value"]) == 0
    else:
        with pytest.raises(ValueError, match="time_window"):
            render_analysis_figures(path)
