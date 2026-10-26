"""A report's computed observations drive its figure and manuscript together."""

import csv
import json
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cfdpaper.cli import app
from cfdpaper.host_tools import report_task


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    Path(path).write_text(json.dumps(value), encoding="utf-8")


def prepare(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    for case, velocity, temperature, pressure in (
        ("a", 1, 320, 1000),
        ("b", 2, 310, 2500),
        ("c", 3, 305, 4500),
    ):
        write(
            root / f"{case}.json",
            {
                "u": velocity,
                "temperature": temperature,
                "pressure": {"inlet": pressure, "outlet": 0},
            },
        )
    plan = {
        "columns": 2,
        "caption": "Matched interface temperature and native pressure-report differences.",
        "panels": [
            {
                "kind": "response",
                "title": "Thermal response",
                "x_label": "Inlet velocity",
                "y_label": "Interface temperature",
                "x_calculation_id": "speed",
                "series": [{"calculation_id": "temperature", "label": "Area mean"}],
            },
            {
                "kind": "response",
                "title": "Pressure response",
                "x_label": "Inlet velocity",
                "y_label": "Pressure difference",
                "x_calculation_id": "speed",
                "series": [{"calculation_id": "drop", "field": "difference", "label": "Static"}],
            },
        ],
    }
    return report_task(
        tmp_path / "first",
        root=root,
        cases=[{"id": case, "source": f"{case}.json"} for case in ("a", "b", "c")],
        quantities=[
            {
                "id": "speed",
                "label": "Inlet velocity",
                "unit": "m/s",
                "pointer": "/u",
                "domain": "specified inlet velocity",
                "table": False,
            },
            {
                "id": "temperature",
                "label": "Interface temperature",
                "unit": "K",
                "pointer": "/temperature",
                "domain": "interface area mean",
                "quantity_kind": "absolute-temperature",
            },
            {
                "id": "drop",
                "label": "Static-pressure difference",
                "unit": "Pa",
                "output_unit": "kPa",
                "reference": "/pressure/outlet",
                "comparison": "/pressure/inlet",
                "domain": "same area-weighted inlet/outlet",
            },
        ],
        title="Matched thermal and hydraulic responses",
        question="How do the interface and pressure reports change together?",
        figure_plan=plan,
    )


def figure_root(result):
    return Path(result["artifacts"]["workspace"]) / "sections/results/sources/report-figure"


def test_report_figures_reach_host_context_drafts_and_native_export(tmp_path):
    first = prepare(tmp_path)
    workspace = Path(first["artifacts"]["workspace"])
    context = read(workspace / "report-context.json")
    assert context["figures"][0]["section_id"] == "results"
    assert context["figures"][0]["id"] == "1"
    results_input = read(workspace / "sections/results/input.json")
    assert len(results_input["figures"]) == 1
    summary = read(figure_root(first) / "figure-summary.json")
    assert summary["figures"][0]["caption"] == results_input["figures"][0]["caption"]
    assert summary["figures"][0]["caption"] == (
        "Matched interface temperature and native pressure-report differences."
    )
    draft = read(workspace / "sections/results/draft.json")
    assert draft["image_observations"] == {"1": "not-viewed"}
    assert "{{figure:1}}" in (workspace / "TASK.md").read_text(encoding="utf-8")
    for sid, name in read(workspace / "drafts.json").items():
        path = workspace / name
        current = read(path)
        current["paragraphs"][0]["text"] = (
            "Bound temperature {{value:temperature_a}} and {{figure:1}}."
            if sid == "results"
            else "Author research wording."
        )
        current["paragraphs"][0]["figure_ids"] = ["1"] if sid == "results" else []
        write(path, current)
    built = report_task(
        tmp_path / "built", workspace=tmp_path / "first", drafts=workspace / "drafts.json"
    )
    assert "320.000 K" in Path(built["artifacts"]["manuscript"]).read_text(encoding="utf-8")
    with zipfile.ZipFile(built["artifacts"]["docx"]) as archive:
        assert b"<w:drawing>" in archive.read("word/document.xml")
        assert any(name.startswith("word/media/") for name in archive.namelist())


def test_source_refresh_uses_the_retained_author_plot_and_new_source_rows(tmp_path):
    first = prepare(tmp_path)
    source = tmp_path / "first/projection/sources/records/b.json"
    document = read(source)
    document["temperature"] = 307
    write(source, document)
    script = figure_root(first) / "plot.py"
    author_script = script.read_text(encoding="utf-8") + (
        "\n# Author-selected styling remains the actual execution entry.\n"
        "(OUTPUT / 'author-script-ran.txt').write_text('kept', encoding='utf-8')\n"
    )
    script.write_text(author_script, encoding="utf-8")
    refreshed = report_task(tmp_path / "refreshed", workspace=tmp_path / "first")
    target = figure_root(refreshed)
    assert (target / "plot.py").read_text(encoding="utf-8") == author_script
    assert (target / "author-script-ran.txt").read_text(encoding="utf-8") == "kept"
    with (target / "evidence-panels-source-data.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    point = next(row for row in rows if row["group"] == "b" and row["panel"] == "1")
    assert float(point["y"]) == 307
    assert read(tmp_path / "raw/b.json")["temperature"] == 310
    assert read(source)["temperature"] == 307


def test_cli_report_preserves_the_same_figure_plan(tmp_path):
    prepare(tmp_path)
    first = tmp_path / "first"
    output = tmp_path / "cli-report"
    result = CliRunner().invoke(
        app,
        [
            "report",
            "--root",
            str(first),
            "--study",
            str(first / "report.json"),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (output / "workspace/sections/results/figures/1.png").is_file()
    assert read(output / "report.json")["figure_plan"]["columns"] == 2


def test_dimensionless_bound_value_keeps_source_unit_without_a_prose_suffix(tmp_path):
    from cfdpaper.publication.table_evidence import display_unit

    # Figure axes can still show (1); only the prose value suffix is suppressed.
    assert display_unit("1") == "1"
    source = tmp_path / "source"
    source.mkdir()
    write(source / "case.json", {"intensity": 0.068})
    result = report_task(
        tmp_path / "prepared",
        root=source,
        cases=[{"id": "A", "source": "case.json"}],
        quantities=[
            {
                "id": "intensity",
                "label": "Inlet turbulence intensity",
                "unit": "1",
                "domain": "specified inlet value",
                "pointer": "/intensity",
            }
        ],
        title="Dimensionless inlet prescription",
        question="What intensity was prescribed?",
    )
    workspace = Path(result["artifacts"]["workspace"])
    assert read(workspace / "report-context.json")["metrics"][0]["unit"] == "1"
    task = (workspace / "TASK.md").read_text(encoding="utf-8")
    assert "available numerical boundary conditions" in task
    for name in read(workspace / "drafts.json").values():
        path = workspace / name
        draft = read(path)
        draft["paragraphs"] = [
            {
                "text": "The inlet intensity is {{value:intensity_A}}.",
                "evidence_ids": ["intensity_A"],
                "figure_ids": [],
            }
        ]
        write(path, draft)
    built = report_task(
        tmp_path / "built", workspace=tmp_path / "prepared", drafts=workspace / "drafts.json"
    )
    text = Path(built["artifacts"]["manuscript"]).read_text(encoding="utf-8")
    assert "intensity is 0.068." in text
    assert "0.068 1" not in text


def test_continuation_rejects_changed_figure_units_without_executing_or_overwriting_author_plot(
    tmp_path, monkeypatch
):
    import cfdpaper.publication.render_figure as render_figure

    first = prepare(tmp_path)
    recipe_path = tmp_path / "first/report.json"
    recipe = read(recipe_path)
    next(q for q in recipe["quantities"] if q["id"] == "drop")["output_unit"] = "MPa"
    write(recipe_path, recipe)
    source = tmp_path / "first/projection/sources/records/a.json"
    script = figure_root(first) / "plot.py"
    csv_path = figure_root(first) / "evidence-panels-source-data.csv"
    protected = {path: path.read_bytes() for path in (source, script, csv_path, recipe_path)}

    def do_not_execute(_):
        pytest.fail("A changed unit must be rejected before the retained script runs")

    monkeypatch.setattr(render_figure, "_run_script", do_not_execute)
    output = tmp_path / "changed-unit"
    with pytest.raises(ValueError, match=r"units changed.*kPa.*MPa") as caught:
        report_task(output, workspace=tmp_path / "first")
    assert "new figure plan" in str(caught.value)
    assert not output.exists()
    assert all(path.read_bytes() == original for path, original in protected.items())


def test_author_caption_resolves_current_values_and_matches_all_current_figure_metadata(tmp_path):
    first = prepare(tmp_path)
    workspace = Path(first["artifacts"]["workspace"])
    recipe = read(tmp_path / "first/report.json")
    original_caption = recipe["figure_plan"]["caption"]
    source = tmp_path / "first/projection/sources/records/b.json"
    document = read(source)
    document["temperature"] = 307
    write(source, document)
    author_caption = (
        "Author comparison: {{value:temperature_b}} at the interface and "
        "{{value:drop_b}} pressure difference."
    )
    drafts = read(workspace / "drafts.json")
    for sid, name in drafts.items():
        path = workspace / name
        draft = read(path)
        draft["paragraphs"][0]["text"] = (
            "See {{figure:1}}." if sid == "results" else "Author research wording."
        )
        if sid == "results":
            draft["captions"]["1"] = author_caption
        write(path, draft)
    author_draft = workspace / drafts["results"]
    original_draft = author_draft.read_bytes()
    built = report_task(
        tmp_path / "caption-built", workspace=tmp_path / "first", drafts=workspace / "drafts.json"
    )
    current = Path(built["artifacts"]["workspace"])
    resolved = read(tmp_path / "caption-built/manuscript/sections/results/section.json")["figures"][
        0
    ]
    expected = "Author comparison: 307.000 K at the interface and 2.500 kPa pressure difference."
    assert resolved["caption"] == expected
    figures = [
        read(current / "report-writing.json")["figures"][0],
        read(current / "report-context.json")["figures"][0],
        read(figure_root(built) / "figure-summary.json")["figures"][0],
    ]
    for figure in figures:
        assert figure["caption"] == expected
        assert figure["description"] == expected
    assert expected in Path(built["artifacts"]["manuscript"]).read_text(encoding="utf-8")
    assert (
        read(tmp_path / "caption-built/report.json")["figure_plan"]["caption"] == original_caption
    )
    assert read(current / drafts["results"])["captions"]["1"] == author_caption
    assert author_draft.read_bytes() == original_draft
    assert read(tmp_path / "raw/b.json")["temperature"] == 310
